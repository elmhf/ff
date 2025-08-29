from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status
from app.utils.validators import validate_file_content
import os
import io


@celery.task(bind=True, name='validate_medical_file')
def validate_medical_file_task(self, file_info, report_id=None):
    task_id = self.request.id
    try:
        file_path = file_info['path']
        filename = file_info['filename']
        
        # Update status to validation started
        if report_id:
            update_report_status(report_id, "validation_started")
        
        JobStatusManager.create_or_update_status(task_id, 'processing', 'Validating file...', 10)
        is_valid, validation_msg = validate_file_content(file_path, filename)
        
        if not is_valid:
            if report_id:
                update_report_status(report_id, "validation_failed")
            raise Exception(f"File validation failed: {validation_msg}")
        
        # Update status to validated
        if report_id:
            update_report_status(report_id, "validated")
        
        result = {
            'status': 'validated',
            'file_info': file_info,
            'message': validation_msg,
            'report_id': report_id
        }
        JobStatusManager.create_or_update_status(task_id, 'completed', 'File validated', 100, result)
        return result
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise


@celery.task(bind=True, name='validate_pano_media')
def validate_pano_media_task(self, file_info, report_id=None):
    task_id = self.request.id
    try:
        file_path = file_info['path']
        filename = file_info['filename']

        if report_id:
            update_report_status(report_id, "validation_started")

        JobStatusManager.create_or_update_status(task_id, 'processing', 'Validating pano image...', 10)

        # Basic header validation
        with open(file_path, 'rb') as f:
            data = f.read()
        header = data[:8]
        if not (header.startswith(b'\xff\xd8\xff') or
                header.startswith(b'\x89PNG\r\n\x1a\n') or
                header.startswith(b'II*\x00') or
                header.startswith(b'MM\x00*') or
                header.startswith(b'BM')):
            if report_id:
                update_report_status(report_id, "validation_failed")
            raise Exception('Invalid image file format')

        # Optional deeper verification via Pillow
        media_meta = None
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data))
            img.verify()
            img = Image.open(io.BytesIO(data))
            width, height = img.size
            mode = img.mode
            fmt = (img.format or '').upper()
            dpi = getattr(img, 'info', {}).get('dpi')

            allowed_modes = {'L', 'LA', 'RGB', 'RGBA'}
            min_w, min_h = 500, 300
            max_w, max_h = 10000, 10000
            if mode not in allowed_modes:
                if report_id:
                    update_report_status(report_id, "validation_failed")
                raise Exception(f'Unsupported color mode: {mode}')
            if width < min_w or height < min_h:
                if report_id:
                    update_report_status(report_id, "validation_failed")
                raise Exception(f'Image too small: {width}x{height}, min {min_w}x{min_h}')
            if width > max_w or height > max_h:
                if report_id:
                    update_report_status(report_id, "validation_failed")
                raise Exception(f'Image too large: {width}x{height}, max {max_w}x{max_h}')

            media_meta = {
                'format': fmt,
                'mode': mode,
                'width': width,
                'height': height,
                'dpi': dpi
            }
        except ImportError:
            media_meta = None

        if report_id:
            update_report_status(report_id, "validated")

        result = {
            'status': 'pano_validated',
            'file_info': {**file_info, 'media_meta': media_meta},
            'message': 'Valid pano image',
            'report_id': report_id
        }
        JobStatusManager.create_or_update_status(task_id, 'completed', 'Pano image validated', 100, result)
        return result
    except Exception as e:
        error_msg = f"Pano validation error: {str(e)}"
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise

