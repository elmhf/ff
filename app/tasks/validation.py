from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status
from app.utils.validators import validate_file_content


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


