from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status
from app import create_app


@celery.task(bind=True, name='run_ai_analysis')
def run_ai_analysis_task(self, validation_result, file_info, upload_id, clinic_id, patient_id, report_type, report_id):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            if not all([clinic_id, patient_id, report_type, report_id]):
                return {
                    'status': 'skipped',
                    'message': 'AI analysis parameters not provided',
                    'validation_result': validation_result,
                    'file_info': file_info,
                    'upload_id': upload_id,
                    'clinic_id': clinic_id,
                    'patient_id': patient_id,
                    'report_type': report_type,
                    'report_id': report_id
                }
            
            # Update status to AI started
            if report_id:
                update_report_status(report_id, "ai_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Running AI analysis...', 40)
            
            try:
                from taskes import complete_medical_processing_aiReport_task as ai_pipeline
                ai_result = ai_pipeline(None, file_info, upload_id, clinic_id, patient_id, report_type, report_id)
                # Update status to AI completed
                update_report_status(report_id, "ai_completed")
            except ImportError:
                ai_result = None
                # Update status to AI skipped
                update_report_status(report_id, "ai_skipped")
            
            result = {
                'status': 'ai_completed',
                'ai_result': ai_result,
                'validation_result': validation_result,
                'file_info': file_info,
                'upload_id': upload_id,
                'clinic_id': clinic_id,
                'patient_id': patient_id,
                'report_type': report_type,
                'report_id': report_id
            }
        JobStatusManager.create_or_update_status(task_id, 'completed', 'AI analysis completed', 100, result)
        return result
    except Exception as e:
        error_msg = f"AI analysis error: {str(e)}"
        if report_id:
            # Update status to AI failed
            update_report_status(report_id, "ai_failed")
        result = {
            'status': 'ai_failed',
            'ai_result': None,
            'error': error_msg,
            'validation_result': validation_result,
            'file_info': file_info,
            'upload_id': upload_id,
            'clinic_id': clinic_id,
            'patient_id': patient_id,
            'report_type': report_type,
            'report_id': report_id
        }
        JobStatusManager.create_or_update_status(task_id, 'completed', 'AI analysis failed but continuing', 100, result)
        return result


