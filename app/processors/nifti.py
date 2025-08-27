import nibabel as nib
import os
import logging
from .base import MedicalImageProcessor
from app.services.job_status import JobStatusManager

logger = logging.getLogger(__name__)


class NIfTIProcessor(MedicalImageProcessor):
    def process_file(self, file_path, output_id, celery_task=None):
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            self.update_progress(10, 'Loading NIfTI file...', celery_task)
            img = nib.load(file_path)
            data = img.get_fdata()
            if data.size == 0:
                raise ValueError("Empty NIfTI data")
            logger.info(f"Data shape: {data.shape}, dtype: {data.dtype}")
            self.update_progress(20, 'Normalizing data...', celery_task)
            data_normalized = self.normalize_data(data)
            slice_counts = self.save_slices(
                data_normalized,
                output_id,
                lambda p, m: self.update_progress(p, m, celery_task)
            )
            voxel_info = self._extract_voxel_info(img)
            return {
                "status": "success",
                "message": "NIfTI file processed successfully",
                "slice_counts": slice_counts,
                "voxel_sizes": voxel_info,
                "data_shape": list(data.shape),
                "output_id": output_id,
                "total_slices": sum(slice_counts.values())
            }
        except Exception as e:
            error_msg = f"NIfTI processing error: {str(e)}"
            if self.task_id:
                JobStatusManager.create_or_update_status(self.task_id, 'failed', error_msg, 0)
            logger.error(f"NIfTI processing failed: {error_msg}")
            raise

    def _extract_voxel_info(self, img):
        try:
            voxel_sizes = img.header.get_zooms()
            return {
                "x_spacing_mm": float(voxel_sizes[0]) if len(voxel_sizes) > 0 else 1.0,
                "y_spacing_mm": float(voxel_sizes[1]) if len(voxel_sizes) > 1 else 1.0,
                "z_spacing_mm": float(voxel_sizes[2]) if len(voxel_sizes) > 2 else 1.0
            }
        except Exception as e:
            logger.warning(f"Failed to extract voxel sizes: {e}")
            return {"x_spacing_mm": 1.0, "y_spacing_mm": 1.0, "z_spacing_mm": 1.0}


