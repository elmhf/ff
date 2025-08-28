from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status, get_supabase
from app import create_app
import logging

logger = logging.getLogger(__name__)

@celery.task(bind=True, name='upload_medical_slices')
def upload_medical_slices_task(self, clinic_id, patient_id, report_type, report_id):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            # Update status to upload started
            if report_id:
                update_report_status(report_id, "upload_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Uploading medical slices...', 60)
            
            # Simulate upload process
            import time
            time.sleep(2)
            
            # Update status to uploaded
            if report_id:
                update_report_status(report_id, "uploaded")
            
            result = {
                'status': 'uploaded',
                'message': 'Medical slices uploaded successfully',
                'clinic_id': clinic_id,
                'patient_id': patient_id,
                'report_type': report_type,
                'report_id': report_id
            }
            JobStatusManager.create_or_update_status(task_id, 'completed', 'Medical slices uploaded', 100, result)
            return result
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        if report_id:
            # Update status to upload failed
            update_report_status(report_id, "upload_failed")
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise

@celery.task(bind=True, name='upload_report_to_storage')
def upload_report_to_storage_task(self, ai_result):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            # Update status to report upload started
            if report_id:
                update_report_status(report_id, "report_upload_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Uploading AI report to storage...', 80)
            
            # Get Supabase client
            supabase = get_supabase()
            if not supabase:
                raise Exception("Supabase client not available")
            
            # Check if AI analysis was successful
            if not ai_result or ai_result.get('status') != 'ai_completed':
                logger.warning("AI analysis not completed, skipping report upload")
                return {
                    'status': 'skipped',
                    'message': 'AI analysis not completed, skipping report upload',
                    'ai_result': ai_result
                }
            
            # Extract parameters from AI result
            file_info = ai_result.get('file_info', {})
            upload_id = ai_result.get('upload_id')
            clinic_id = ai_result.get('clinic_id')
            patient_id = ai_result.get('patient_id')
            report_type = ai_result.get('report_type')
            report_id = ai_result.get('report_id')
            
            # Import the upload function
            try:
                from taskes.utils.upload_report_to_storage import upload_report_to_storage
                
                # Generate report data (this should come from AI analysis)
                # For now, we'll create a basic report structure
                import datetime
                from uuid import uuid4
                
                # Extract AI result data
                ai_analysis_data = ai_result.get('ai_result', {})
                if isinstance(ai_analysis_data, dict) and 'generated_data' in ai_analysis_data:
                    # Use the generated data from AI pipeline
                    ai_analysis_data = ai_analysis_data.get('generated_data', {})
                
                report_data = {
                    "report_id": report_id,
                    "patient_id": patient_id,
                    "clinic_id": clinic_id,
                    "report_type": report_type,
                    "generated_at": datetime.datetime.now().isoformat(),
                    "ai_analysis": ai_analysis_data,
                    "file_info": file_info,
                    "upload_id": upload_id,
                    "metadata": {
                        "processing_pipeline_id": str(uuid4()),
                        "upload_id": upload_id,
                        "task_id": task_id
                    }
                }
                
                # Upload report to Supabase storage
                upload_result = upload_report_to_storage(
                    report_data, clinic_id, patient_id, report_type, report_id, logger, supabase
                )
                
                if upload_result.get('success'):
                    # Update status to report uploaded
                    if report_id:
                        update_report_status(report_id, "report_uploaded")
                    
                    result = {
                        'status': 'report_uploaded',
                        'message': 'AI report uploaded to storage successfully',
                        'upload_result': upload_result,
                        'report_id': report_id
                    }
                    JobStatusManager.create_or_update_status(task_id, 'completed', 'Report uploaded to storage', 100, result)
                    return result
                else:
                    raise Exception(f"Upload failed: {upload_result.get('error', 'Unknown error')}")
                    
            except ImportError as e:
                logger.error(f"Could not import upload_report_to_storage: {e}")
                raise Exception(f"Upload module not available: {e}")
                
    except Exception as e:
        error_msg = f"Report upload error: {str(e)}"
        # Try to get report_id from the result if available
        try:
            if report_id:
                update_report_status(report_id, "report_upload_failed")
        except:
            pass
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise


