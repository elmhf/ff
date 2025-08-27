from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status
from app.services.uploads import SupabaseUploadManager
from app import create_app


@celery.task(bind=True, name='upload_medical_slices')
def upload_medical_slices_task(self, processing_result, clinic_id, patient_id, report_type, report_id):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            if not all([clinic_id, patient_id, report_type, report_id]):
                return {
                    'status': 'skipped',
                    'message': 'Upload parameters not provided',
                    'processing_result': processing_result
                }
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Uploading slices...', 30)
            slice_counts = processing_result['processing_result'].get('slice_counts', {})
            if sum(slice_counts.values()) > 0:
                upload_manager = SupabaseUploadManager(task_id=task_id)
                upload_result = upload_manager.upload_all_slices(
                    slice_counts, clinic_id, patient_id, report_type, report_id, self
                )
                update_report_status(report_id, "uploaded")
            else:
                upload_result = None
            result = {
                'status': 'uploaded',
                'upload_result': upload_result,
                'processing_result': processing_result
            }
        JobStatusManager.create_or_update_status(task_id, 'completed', 'Upload completed', 100, result)
        return result
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        if report_id:
            update_report_status(report_id, "upload_failed")
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise


