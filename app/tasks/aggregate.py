from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status
from app import create_app


@celery.task(bind=True, name='aggregate_medical_results')
def aggregate_medical_results_task(self, results_list):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            # Update status to aggregation started
            report_id = None
            if isinstance(results_list, dict):
                try:
                    results_list = [results_list[k] for k in sorted(results_list.keys())]
                except Exception:
                    results_list = list(results_list.values())
            elif not isinstance(results_list, list):
                results_list = [results_list]

            def safe_get(d, key, default=None):
                return d.get(key, default) if isinstance(d, dict) else default

            validation_result = results_list[0] if len(results_list) > 0 else {}
            ai_result = results_list[1] if len(results_list) > 1 else {}
            upload_result = results_list[2] if len(results_list) > 2 else {}

            report_id = (safe_get(validation_result, 'report_id') or
                         safe_get(ai_result, 'report_id') or
                         safe_get(upload_result, 'report_id'))
            
            # Update status to aggregation started
            if report_id:
                update_report_status(report_id, "aggregation_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Aggregating results...', 90)

            final_result = {
                'status': 'completed',
                'message': 'Medical file processing completed successfully',
                'validation_result': validation_result,
                'ai_result': safe_get(ai_result, 'ai_result'),
                'upload_result': safe_get(upload_result, 'upload_result'),
                'processing_result': safe_get(upload_result, 'processing_result'),
                'upload_id': safe_get(upload_result, 'upload_id') or safe_get(validation_result, 'upload_id'),
                'workflow_completed': True
            }

            # Update status to completed
            if report_id:
                update_report_status(report_id, "completed")

            JobStatusManager.create_or_update_status(task_id, 'completed', 'Workflow completed', 100, final_result)
            return final_result
    except Exception as e:
        error_msg = f"Aggregation error: {str(e)}"
        # Update status to aggregation failed
        if report_id:
            update_report_status(report_id, "aggregation_failed")
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise Exception(error_msg)


@celery.task(bind=True, name='aggregate_pano_medical_results')
def aggregate_pano_medical_results_task(self, results_list, file_info, upload_id, clinic_id, patient_id, report_id):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            # Update status to aggregation started
            if report_id:
                update_report_status(report_id, "aggregation_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Aggregating pano results...', 90)

            # Extract the report upload result from the previous task
            report_upload_result = results_list if isinstance(results_list, dict) else {}
            
            def safe_get(d, key, default=None):
                return d.get(key, default) if isinstance(d, dict) else default
            
            # Update status to aggregation started
            if report_id:
                update_report_status(report_id, "aggregation_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Aggregating pano results...', 90)

            final_result = {
                'status': 'completed',
                'message': 'Panoramic image processing completed successfully',
                'validation_result': 'Pano media validated successfully',
                'upload_result': 'Pano image uploaded successfully',
                'ai_result': 'Pano image analyzed successfully',
                'report_upload_result': safe_get(report_upload_result, 'upload_result'),
                'file_info': file_info,
                'clinic_id': clinic_id,
                'patient_id': patient_id,
                'report_type': 'pano',
                'upload_id': upload_id,
                'report_id': report_id,
                'workflow_completed': True
            }

            # Update status to completed
            if report_id:
                update_report_status(report_id, "completed")

            JobStatusManager.create_or_update_status(task_id, 'completed', 'Pano workflow completed', 100, final_result)
            return final_result
    except Exception as e:
        error_msg = f"Pano aggregation error: {str(e)}"
        # Update status to aggregation failed
        if report_id:
            update_report_status(report_id, "aggregation_failed")
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise Exception(error_msg)


