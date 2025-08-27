import os
import logging
import numpy as np
import pydicom
from .base import MedicalImageProcessor
from app.services.job_status import JobStatusManager

logger = logging.getLogger(__name__)


class DICOMProcessor(MedicalImageProcessor):
    SUPPORTED_EXTENSIONS = {'.dcm', '.dicom', '.ima', ''}

    def process_directory(self, dicom_dir, output_id, celery_task=None):
        try:
            if not os.path.exists(dicom_dir):
                raise FileNotFoundError(f"Directory not found: {dicom_dir}")
            self.update_progress(5, 'Scanning DICOM files...', celery_task)
            dicom_files = self._find_dicom_files(dicom_dir)
            if not dicom_files:
                raise Exception("No valid DICOM files found in directory")
            self.update_progress(15, f'Loading {len(dicom_files)} DICOM files...', celery_task)
            valid_slices = self._load_dicom_slices(dicom_files, celery_task)
            if not valid_slices:
                raise Exception("No valid DICOM files found")
            self.update_progress(35, 'Creating volume...', celery_task)
            volume = self._create_volume(valid_slices, celery_task)
            volume_normalized = self.normalize_data(volume)
            slice_counts = self.save_slices(
                volume_normalized,
                output_id,
                lambda p, m: self.update_progress(p, m, celery_task)
            )
            voxel_info = self._extract_dicom_metadata(valid_slices[0][0])
            return {
                "status": "success",
                "message": "DICOM files processed successfully",
                "slice_counts": slice_counts,
                "voxel_sizes": voxel_info,
                "data_shape": list(volume.shape),
                "output_id": output_id,
                "dicom_files_processed": len(valid_slices),
                "total_slices": sum(slice_counts.values())
            }
        except Exception as e:
            error_msg = f"DICOM processing error: {str(e)}"
            if self.task_id:
                JobStatusManager.create_or_update_status(self.task_id, 'failed', error_msg, 0)
            logger.error(f"DICOM processing failed: {error_msg}")
            raise

    def _find_dicom_files(self, dicom_dir):
        dicom_files = []
        for root, _, files in os.walk(dicom_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if self._is_dicom_file(file_path):
                    dicom_files.append(file_path)
        return dicom_files

    def _is_dicom_file(self, file_path):
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in self.SUPPORTED_EXTENSIONS:
            return False
        try:
            with open(file_path, 'rb') as f:
                f.seek(128)
                return f.read(4) == b'DICM' or file_ext in {'.dcm', '.dicom', '.ima'}
        except Exception:
            return False

    def _load_dicom_slices(self, dicom_files, celery_task=None):
        valid_slices = []
        for i, file_path in enumerate(dicom_files):
            try:
                ds = pydicom.dcmread(file_path, force=True)
                if hasattr(ds, 'pixel_array') and ds.pixel_array.size > 0:
                    valid_slices.append((ds, file_path, ds.pixel_array))
            except Exception:
                continue
            if celery_task and i % 10 == 0:
                progress = 15 + int((i / len(dicom_files)) * 15)
                self.update_progress(progress, f'Processing file {i+1}/{len(dicom_files)}...', celery_task)
        return self._sort_slices(valid_slices)

    def _sort_slices(self, slices):
        def sort_key(slice_data):
            ds, _, _ = slice_data
            if hasattr(ds, 'SliceLocation') and ds.SliceLocation is not None:
                return float(ds.SliceLocation)
            elif hasattr(ds, 'ImagePositionPatient') and ds.ImagePositionPatient:
                return float(ds.ImagePositionPatient[2])
            elif hasattr(ds, 'InstanceNumber') and ds.InstanceNumber is not None:
                return int(ds.InstanceNumber)
            return 0
        try:
            slices.sort(key=sort_key)
        except Exception:
            slices.sort(key=lambda x: x[1])
        return slices

    def _create_volume(self, valid_slices, celery_task=None):
        import numpy as np
        pixel_data_list = []
        for i, (ds, _, pixel_array) in enumerate(valid_slices):
            try:
                if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                    slope = float(ds.RescaleSlope) if ds.RescaleSlope else 1.0
                    intercept = float(ds.RescaleIntercept) if ds.RescaleIntercept else 0.0
                    pixel_array = pixel_array.astype(np.float64) * slope + intercept
                pixel_data_list.append(pixel_array.astype(np.float64))
            except Exception:
                continue
            if celery_task and i % 20 == 0:
                progress = 35 + int((i / len(valid_slices)) * 10)
                self.update_progress(progress, f'Building volume... {i}/{len(valid_slices)}', celery_task)
        if not pixel_data_list:
            raise Exception("Failed to create volume from DICOM files")
        volume = np.stack(pixel_data_list, axis=2)
        return volume

    def _extract_dicom_metadata(self, first_slice):
        try:
            pixel_spacing = getattr(first_slice, 'PixelSpacing', [1.0, 1.0])
            slice_thickness = getattr(first_slice, 'SliceThickness', 1.0)
            if isinstance(pixel_spacing, (list, tuple)) and len(pixel_spacing) >= 2:
                x_spacing = float(pixel_spacing[0])
                y_spacing = float(pixel_spacing[1])
            else:
                x_spacing = y_spacing = 1.0
            z_spacing = float(slice_thickness) if slice_thickness else 1.0
            return {
                "x_spacing_mm": x_spacing,
                "y_spacing_mm": y_spacing,
                "z_spacing_mm": z_spacing
            }
        except Exception:
            return {"x_spacing_mm": 1.0, "y_spacing_mm": 1.0, "z_spacing_mm": 1.0}


