from app.celery_app import celery, REDIS_AVAILABLE
from celery import chain, group
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status


def start_complete_workflow(file_info, upload_id, clinic_id=None, patient_id=None, report_type=None, report_id=None):
    if REDIS_AVAILABLE and celery:
        from app import create_app
        app = create_app()
        with app.app_context():
            # Update status to workflow started
            if report_id:
                update_report_status(report_id, "workflow_started")
            
            workflow = chain(
                celery.signature('validate_medical_file', args=[file_info, report_id]),
                group(
                    chain(
                        celery.signature('process_medical_file', args=[upload_id]),
                        celery.signature('upload_medical_slices', args=[clinic_id, patient_id, report_type, report_id])
                    ),
                    chain(
                        celery.signature('run_ai_analysis', args=[file_info, upload_id, clinic_id, patient_id, report_type, report_id]),
                        celery.signature('upload_report_to_storage')
                    )
                ),
                celery.signature('aggregate_medical_results')
            )
            workflow_result = workflow.apply_async()
            JobStatusManager.create_or_update_status(workflow_result.id, 'queued', 'Job queued for processing', 0)
            
            # Update status to workflow in progress
            if report_id:
                update_report_status(report_id, "workflow_in_progress")
            
            return {
                'workflow_id': workflow_result.id,
            }
    else:
        return {
            'workflow_id': None,
        }


def start_pano_workflow(file_info, upload_id, clinic_id=None, patient_id=None, report_id=None):
    """Start a dedicated pano workflow: upload image -> analyze pano -> upload report JSON."""
    report_type = 'pano'
    if REDIS_AVAILABLE and celery:
        from app import create_app
        app = create_app()
        with app.app_context():
            if report_id:
                update_report_status(report_id, "workflow_started")

            workflow = chain(
                celery.signature('validate_pano_media', args=[file_info, report_id]),
                celery.signature('upload_pano_image', args=[file_info, clinic_id, patient_id, report_id]),
                celery.signature('analyze_pano_image', args=[file_info, clinic_id, patient_id, report_id]),
                celery.signature('upload_report_to_storage')
            )

            workflow_result = workflow.apply_async()
            JobStatusManager.create_or_update_status(workflow_result.id, 'queued', 'Pano job queued', 0)

            if report_id:
                update_report_status(report_id, "workflow_in_progress")

            return {
                'workflow_id': workflow_result.id,
            }
    else:
        return {
            'workflow_id': None,
        }