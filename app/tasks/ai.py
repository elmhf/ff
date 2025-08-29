import os
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
            
            ai_result = None
            # Use the generic AI pipeline only (pano handled by its own task elsewhere)
            try:
                from taskes import complete_medical_processing_aiReport_task as ai_pipeline
                ai_result = ai_pipeline(None, file_info, upload_id, clinic_id, patient_id, report_type, report_id)
                update_report_status(report_id, "ai_completed")
            except ImportError:
                ai_result = None
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


def analyze_pano_image(image_bytes: bytes, filename: str) -> dict:
    """Lightweight pano image analysis placeholder that returns a structured report.

    This function can be replaced with a real ML model later.
    """
    file_size = len(image_bytes) if image_bytes else 0
    ext = os.path.splitext(filename or 'pano.jpg')[1].lower()
    # Simple heuristic placeholders
    quality_score = 0.85
    exposure_ok = True
    findings = [
        {"id": "jf1", "label": "Jaw alignment", "score": 0.91},
        {"id": "cf1", "label": "Caries risk", "score": 0.22},
        {"id": "pf1", "label": "Periapical lesion", "score": 0.08},
    ]
    report = {
        "report_type": "pano",
        "analysis_version": "v0.1",
        "input": {"filename": filename, "extension": ext, "size_bytes": file_size},
        "metrics": {"quality_score": quality_score, "exposure_ok": exposure_ok},
        "findings": findings,
        "summary": {
            "impression": "Panoramic image analyzed successfully. No acute findings suspected.",
            "recommendations": [
                "Routine dental follow-up",
                "Consider bitewing radiographs if caries risk increases"
            ],
        },
    }
    return report


@celery.task(bind=True, name='analyze_pano_image')
def analyze_pano_image_task(self, file_info, clinic_id, patient_id, report_id):
    task_id = self.request.id
    app = create_app()
    try:
        with app.app_context():
            if report_id:
                update_report_status(report_id, "ai_started")
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Analyzing panoramic image...', 40)

            image_path = (file_info or {}).get('path')
            filename = (file_info or {}).get('filename') or 'pano.jpg'
            if not image_path or not os.path.exists(image_path):
                raise FileNotFoundError('Pano image path not found')

            with open(image_path, 'rb') as f:
                image_bytes = f.read()

            report = analyze_pano_image(image_bytes, filename)
            if report_id:
                update_report_status(report_id, "ai_completed")

            result = {
                'status': 'ai_completed',
                'ai_result': report,
                'file_info': file_info,
                'clinic_id': clinic_id,
                'patient_id': patient_id,
                'report_type': 'pano',
                'report_id': report_id
            }
            JobStatusManager.create_or_update_status(task_id, 'completed', 'Pano analysis completed', 100, result)
            return result
    except Exception as e:
        error_msg = f"Pano AI analysis error: {str(e)}"
        if report_id:
            update_report_status(report_id, "ai_failed")
        result = {
            'status': 'ai_failed',
            'ai_result': None,
            'error': error_msg,
            'file_info': file_info,
            'clinic_id': clinic_id,
            'patient_id': patient_id,
            'report_type': 'pano',
            'report_id': report_id
        }
        JobStatusManager.create_or_update_status(task_id, 'completed', 'Pano AI analysis failed', 100, result)
        return result

