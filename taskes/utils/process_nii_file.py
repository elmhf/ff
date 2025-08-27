
import os
from PIL import Image

import nibabel
import numpy as np


def process_nii_file(app,logger,JobStatusManager,file_path, output_id, task_id=None):
    """Direct NIfTI file processing function (for internal calls)"""
    try:
        logger.info(f"🔍 Processing NIfTI file directly: {file_path}")
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Loading NIfTI file...', 10)
        
        # Load NIfTI file with validation
        try:
            img = nibabel.load(file_path)
            data = img.get_fdata()
            
            if data.size == 0:
                raise ValueError("Empty NIfTI data")
                
            logger.info(f"📊 Data shape: {data.shape}, dtype: {data.dtype}")
            
        except Exception as e:
            raise ValueError(f"Failed to load NIfTI file: {str(e)}")
        
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Normalizing data...', 20)
        
        # Enhanced data normalization with validation
        try:
            data_min, data_max = data.min(), data.max()
            if data_max == data_min:
                logger.warning("Constant intensity data detected")
                data_normalized = np.zeros_like(data, dtype=np.uint8)
            else:
                data_normalized = ((data - data_min) / (data_max - data_min) * 255).astype(np.uint8)
        except Exception as e:
            raise ValueError(f"Data normalization failed: {str(e)}")
        
        # Create slices with progress tracking
        slice_counts = {}
        views_info = [
            ('axial', 2, data_normalized.shape[2]),
            ('coronal', 1, data_normalized.shape[1]),
            ('sagittal', 0, data_normalized.shape[0])
        ]
        
        for view_idx, (view, axis, slice_count) in enumerate(views_info):
            progress_base = 30 + (view_idx * 20)
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
                        slice_data = data_normalized[i, :, :]
                    elif axis == 1:
                        slice_data = data_normalized[:, i, :]
                    else:
                        slice_data = data_normalized[:, :, i]
                    
                    # Only save slices with meaningful data
                    if np.any(slice_data) and np.std(slice_data) > 1:
                        img_pil = Image.fromarray(slice_data.T, mode='L')
                        slice_path = os.path.join(view_dir, f"{saved_count}.jpg")
                        img_pil.save(slice_path, quality=85, optimize=True)
                        saved_count += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to save {view} slice {i}: {e}")
                    continue
                
                # Update progress every 10 slices
                if task_id and i % 10 == 0 and slice_count > 0:
                    current_progress = progress_base + int((i / slice_count) * 15)
                    JobStatusManager.create_or_update_status(
                        task_id, 'processing', f'Creating {view} slices... ({i}/{slice_count})', current_progress
                    )
            
            slice_counts[view] = saved_count
            logger.info(f"✅ Created {saved_count} {view} slices")
        
        # Extract voxel information safely
        try:
            voxel_sizes = img.header.get_zooms()
            voxel_info = {
                "x_spacing_mm": float(voxel_sizes[0]) if len(voxel_sizes) > 0 else 1.0,
                "y_spacing_mm": float(voxel_sizes[1]) if len(voxel_sizes) > 1 else 1.0,
                "z_spacing_mm": float(voxel_sizes[2]) if len(voxel_sizes) > 2 else 1.0
            }
        except Exception as e:
            logger.warning(f"Failed to extract voxel sizes: {e}")
            voxel_info = {"x_spacing_mm": 1.0, "y_spacing_mm": 1.0, "z_spacing_mm": 1.0}
        
        result = {
            "status": "success",
            "message": "NIfTI file processed successfully",
            "slice_counts": slice_counts,
            "voxel_sizes": voxel_info,
            "data_shape": list(data.shape),
            "output_id": output_id,
            "total_slices": sum(slice_counts.values())
        }
        
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'processing', 'NIfTI processing completed', 50, result)
        logger.info(f"✅ NIfTI processing completed")
        
        return result
        
    except Exception as e:
        error_msg = f"NIfTI processing error: {str(e)}"
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        logger.error(f"❌ NIfTI processing failed: {error_msg}")
        raise
