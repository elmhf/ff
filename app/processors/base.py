import numpy as np
from PIL import Image
import os
import logging
from app.services.job_status import JobStatusManager
from flask import current_app

logger = logging.getLogger(__name__)


class MedicalImageProcessor:
    def __init__(self, task_id=None):
        self.task_id = task_id

    def update_progress(self, progress, message, celery_task=None):
        if self.task_id:
            JobStatusManager.create_or_update_status(self.task_id, 'processing', message, progress)
        if celery_task:
            celery_task.update_state(state='PROGRESS', meta={'progress': progress, 'message': message})

    def normalize_data(self, data):
        try:
            data_min, data_max = data.min(), data.max()
            if data_max == data_min:
                logger.warning("Constant intensity data detected")
                return np.zeros_like(data, dtype=np.uint8)
            return ((data - data_min) / (data_max - data_min) * 255).astype(np.uint8)
        except Exception as e:
            raise ValueError(f"Data normalization failed: {str(e)}")

    def save_slices(self, volume_data, output_id, progress_callback=None):
        slice_counts = {}
        views_info = [
            ('axial', 2, volume_data.shape[2]),
            ('coronal', 1, volume_data.shape[1]),
            ('sagittal', 0, volume_data.shape[0])
        ]
        for view_idx, (view, axis, slice_count) in enumerate(views_info):
            if progress_callback:
                progress_callback(30 + (view_idx * 20), f'Creating {view} slices...')
            saved_count = self._save_view_slices(volume_data, view, axis, slice_count, progress_callback)
            slice_counts[view] = saved_count
            logger.info(f"Created {saved_count} {view} slices")
        return slice_counts

    def _save_view_slices(self, data, view, axis, slice_count, progress_callback=None):
        saved_count = 0
        view_dir = os.path.join(current_app.config['BASE_PATH'], view)
        os.makedirs(view_dir, exist_ok=True)
        for i in range(slice_count):
            try:
                slice_data = self._extract_slice(data, axis, i)
                if np.any(slice_data) and np.std(slice_data) > 1:
                    img_pil = Image.fromarray(slice_data.T if axis == 2 else slice_data, mode='L')
                    slice_path = os.path.join(view_dir, f"{saved_count}.jpg")
                    img_pil.save(slice_path, quality=85, optimize=True)
                    saved_count += 1
            except Exception as e:
                logger.warning(f"Failed to save {view} slice {i}: {e}")
                continue
        return saved_count

    def _extract_slice(self, data, axis, index):
        if axis == 0:
            return data[index, :, :]
        elif axis == 1:
            return data[:, index, :]
        else:
            return data[:, :, index]


