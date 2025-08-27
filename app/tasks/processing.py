from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status
from app.processors.nifti import NIfTIProcessor
from app.processors.dicom import DICOMProcessor
import os
from app import create_app


@celery.task(bind=True, name='process_medical_file')
def process_medical_file_task(self, validation_result, upload_id):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            file_info = validation_result['file_info']
            report_id = validation_result.get('report_id')
            file_path = file_info['path']
            filename = file_info['filename']
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Processing medical file...', 20)
            if filename.lower().endswith(('.nii', '.nii.gz')):
                processor = NIfTIProcessor(task_id=task_id)
                processing_result = processor.process_file(file_path, upload_id, self)
            else:
                processor = DICOMProcessor(task_id=task_id)
                upload_dir = os.path.dirname(file_path)
                processing_result = processor.process_directory(upload_dir, upload_id, self)
            if report_id:
                update_report_status(report_id, "processed")
            result = {
                'status': 'processed',
                'processing_result': processing_result,
                'upload_id': upload_id,
                'file_info': file_info,
                'report_id': report_id
            }
        JobStatusManager.create_or_update_status(task_id, 'completed', 'File processed', 100, result)
        return result
    except Exception as e:
        error_msg = f"Processing error: {str(e)}"
        report_id = validation_result.get('report_id') if isinstance(validation_result, dict) else None
        if report_id:
            update_report_status(report_id, "processing_failed")
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise


