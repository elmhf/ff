import os
from PIL import Image

import numpy as np
import pydicom


def process_dicom_files(app,JobStatusManager,logger,dicom_dir, output_id, task_id=None):
    """Direct DICOM file processing function (for internal calls)"""
    try:
        logger.info(f"🔍 Processing DICOM directory directly: {dicom_dir}")
        
        if not os.path.exists(dicom_dir):
            raise FileNotFoundError(f"Directory not found: {dicom_dir}")
        
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Scanning DICOM files...', 5)
        
        # Enhanced DICOM file discovery
        dicom_files = []
        supported_extensions = {'.dcm', '.dicom', '.ima', ''}
        
        for root, dirs, files in os.walk(dicom_dir):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                
                if file_ext in supported_extensions:
                    # Quick validation to ensure it's actually a DICOM file
                    try:
                        with open(file_path, 'rb') as f:
                            # Check for DICOM magic number
                            f.seek(128)
                            if f.read(4) == b'DICM':
                                dicom_files.append(file_path)
                            elif file_ext in {'.dcm', '.dicom', '.ima'}:
                                # Try to read anyway if extension suggests DICOM
                                dicom_files.append(file_path)
                    except Exception:
                        continue
        
        if not dicom_files:
            raise Exception("No valid DICOM files found in directory")
            
        logger.info(f"📁 Found {len(dicom_files)} potential DICOM files")
        
        if task_id:
            JobStatusManager.create_or_update_status(
                task_id, 'processing', f'Loading {len(dicom_files)} DICOM files...', 15
            )
        
        # Process DICOM files with enhanced validation
        valid_slices = []
        failed_files = []
        
        for i, file_path in enumerate(dicom_files):
            try:
                ds = pydicom.dcmread(file_path, force=True)
                
                # Validate DICOM dataset
                if not hasattr(ds, 'pixel_array'):
                    failed_files.append((file_path, "No pixel data"))
                    continue
                
                pixel_array = ds.pixel_array
                if pixel_array.size == 0:
                    failed_files.append((file_path, "Empty pixel array"))
                    continue
                
                valid_slices.append((ds, file_path, pixel_array))
                
            except Exception as e:
                failed_files.append((file_path, str(e)))
                continue
            
            # Update progress every 10 files
            if task_id and i % 10 == 0:
                progress = 15 + int((i / len(dicom_files)) * 15)  # 15-30%
                JobStatusManager.create_or_update_status(
                    task_id, 'processing', f'Processing file {i+1}/{len(dicom_files)}...', progress
                )
        
        if not valid_slices:
            error_details = "; ".join([f"{os.path.basename(f)}: {e}" for f, e in failed_files[:5]])
            raise Exception(f"No valid DICOM files found. Sample errors: {error_details}")
        
        if failed_files:
            logger.warning(f"⚠️ Failed to process {len(failed_files)} files")
        
        if task_id:
            JobStatusManager.create_or_update_status(
                task_id, 'processing', 'Sorting and creating volume...', 35
            )
        
        # Enhanced slice sorting with multiple criteria
        def sort_key(slice_data):
            ds, _, _ = slice_data
            # Try multiple sorting criteria
            if hasattr(ds, 'SliceLocation') and ds.SliceLocation is not None:
                return float(ds.SliceLocation)
            elif hasattr(ds, 'ImagePositionPatient') and ds.ImagePositionPatient:
                return float(ds.ImagePositionPatient[2])  # Z-coordinate
            elif hasattr(ds, 'InstanceNumber') and ds.InstanceNumber is not None:
                return int(ds.InstanceNumber)
            else:
                return 0
        
        try:
            valid_slices.sort(key=sort_key)
        except Exception as e:
            logger.warning(f"Could not sort slices properly: {e}")
            # Fallback to filename sorting
            valid_slices.sort(key=lambda x: x[1])
        
        # Create 3D volume with enhanced processing
        pixel_data_list = []
        rescale_info = []
        
        for i, (ds, file_path, pixel_array) in enumerate(valid_slices):
            try:
                # Apply rescaling if available
                if hasattr(ds, 'RescaleSlope') and hasattr(ds, 'RescaleIntercept'):
                    slope = float(ds.RescaleSlope) if ds.RescaleSlope else 1.0
                    intercept = float(ds.RescaleIntercept) if ds.RescaleIntercept else 0.0
                    pixel_array = pixel_array.astype(np.float64) * slope + intercept
                    rescale_info.append((slope, intercept))
                else:
                    rescale_info.append((1.0, 0.0))
                
                # Ensure consistent data type
                pixel_array = pixel_array.astype(np.float64)
                pixel_data_list.append(pixel_array)
                
            except Exception as e:
                logger.warning(f"Error processing slice {i}: {e}")
                continue
            
            # Update progress
            if task_id and i % 20 == 0:
                progress = 35 + int((i / len(valid_slices)) * 10)  # 35-45%
                JobStatusManager.create_or_update_status(
                    task_id, 'processing', f'Building volume... {i}/{len(valid_slices)}', progress
                )
        
        if not pixel_data_list:
            raise Exception("Failed to create volume from DICOM files")
        
        # Stack into 3D volume
        try:
            volume = np.stack(pixel_data_list, axis=2)
            logger.info(f"📊 Created volume shape: {volume.shape}, dtype: {volume.dtype}")
        except Exception as e:
            raise Exception(f"Failed to create 3D volume: {str(e)}")
        
        # Enhanced volume normalization
        try:
            volume_min, volume_max = volume.min(), volume.max()
            if volume_max == volume_min:
                logger.warning("Constant intensity volume detected")
                volume_normalized = np.zeros_like(volume, dtype=np.uint8)
            else:
                volume_normalized = ((volume - volume_min) / (volume_max - volume_min) * 255).astype(np.uint8)
        except Exception as e:
            raise Exception(f"Volume normalization failed: {str(e)}")
        
        # Generate slices with progress tracking
        slice_counts = {}
        views_info = [
            ('axial', 2, volume_normalized.shape[2]),
            ('coronal', 1, volume_normalized.shape[1]),
            ('sagittal', 0, volume_normalized.shape[0])
        ]
        
        for view_idx, (view, axis, slice_count) in enumerate(views_info):
            progress_base = 50 + (view_idx * 15)  # 50, 65, 80
            
            if task_id:
                JobStatusManager.create_or_update_status(
                    task_id, 'processing', f'Creating {view} slices...', progress_base
                )
            
            saved_count = 0
            view_dir = os.path.join(app.config['BASE_PATH'], view)
            os.makedirs(view_dir, exist_ok=True)
            
            for i in range(slice_count):
                try:
                    if axis == 0:
                        slice_data = volume_normalized[i, :, :]
                    elif axis == 1:
                        slice_data = volume_normalized[:, i, :]
                    else:
                        slice_data = volume_normalized[:, :, i]
                    
                    # Enhanced slice validation
                    if np.any(slice_data) and np.std(slice_data) > 1:
                        img_pil = Image.fromarray(slice_data, mode='L')
                        slice_path = os.path.join(view_dir, f"{saved_count}.jpg")
                        img_pil.save(slice_path, quality=85, optimize=True)
                        saved_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to save {view} slice {i}: {e}")
                    continue
                
                # Update progress every 20 slices
                if task_id and i % 20 == 0 and slice_count > 0:
                    current_progress = progress_base + int((i / slice_count) * 15)
                    JobStatusManager.create_or_update_status(
                        task_id, 'processing', f'Creating {view} slices... ({i}/{slice_count})', current_progress
                    )
            
            slice_counts[view] = saved_count
            logger.info(f"✅ Created {saved_count} {view} slices")
        
        # Extract metadata safely
        try:
            first_slice = valid_slices[0][0]
            pixel_spacing = getattr(first_slice, 'PixelSpacing', [1.0, 1.0])
            slice_thickness = getattr(first_slice, 'SliceThickness', 1.0)
            
            # Ensure numeric values
            if isinstance(pixel_spacing, (list, tuple)) and len(pixel_spacing) >= 2:
                x_spacing = float(pixel_spacing[0])
                y_spacing = float(pixel_spacing[1])
            else:
                x_spacing = y_spacing = 1.0
                
            z_spacing = float(slice_thickness) if slice_thickness else 1.0
            
            voxel_info = {
                "x_spacing_mm": x_spacing,
                "y_spacing_mm": y_spacing,
                "z_spacing_mm": z_spacing
            }
        except Exception as e:
            logger.warning(f"Failed to extract DICOM metadata: {e}")
            voxel_info = {"x_spacing_mm": 1.0, "y_spacing_mm": 1.0, "z_spacing_mm": 1.0}
        
        result = {
            "status": "success",
            "message": "DICOM files processed successfully",
            "slice_counts": slice_counts,
            "voxel_sizes": voxel_info,
            "data_shape": list(volume.shape),
            "output_id": output_id,
            "dicom_files_processed": len(valid_slices),
            "failed_files": len(failed_files),
            "total_slices": sum(slice_counts.values())
        }
        
        if task_id:
            JobStatusManager.create_or_update_status(
                task_id, 'processing', 'DICOM processing completed', 50, result
            )
        logger.info(f"✅ DICOM processing completed")
        
        return result
        
    except Exception as e:
        error_msg = f"DICOM processing error: {str(e)}"
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        logger.error(f"❌ DICOM processing failed: {error_msg}")
        raise
