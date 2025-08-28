from flask import current_app


def get_supabase():
    try:
        return current_app.extensions.get('supabase') if hasattr(current_app, 'extensions') else None
    except Exception:
        return None


def update_report_status(report_id, stage="completed"):
    supabase = get_supabase()
    if not supabase or not report_id:
        return None
               status_mapping = {
               # Workflow stages
               "workflow_started": "workflow_started",
               "workflow_in_progress": "workflow_in_progress",

               # Validation stages
               "validation_started": "validation_started",
               "validation_failed": "validation_failed",
               "validated": "file_validated",

               # Processing stages
               "processing_started": "processing_started",
               "processing_failed": "processing_failed",
               "processed": "file_processed",

               # Upload stages
               "upload_started": "upload_started",
               "upload_failed": "upload_failed",
               "uploaded": "slices_uploaded",

               # AI Analysis stages
               "ai_started": "ai_analysis_started",
               "ai_failed": "ai_analysis_failed",
               "ai_skipped": "ai_analysis_skipped",
               "ai_completed": "ai_analysis_completed",

               # Report Upload stages
               "report_upload_started": "report_upload_started",
               "report_upload_failed": "report_upload_failed",
               "report_upload_skipped": "report_upload_skipped",
               "report_uploaded": "report_uploaded",

               # Final stages
               "aggregation_started": "aggregation_started",
               "aggregation_failed": "aggregation_failed",
               "completed": "completed",

               # Legacy statuses
               "file_uploaded": "file_uploaded",
               "file_too_large": "file_too_large",
               "invalid_file": "invalid_file",
               "processing_sync": "processing_sync",
           }
    status_value = status_mapping.get(stage, stage)
    try:
        return supabase.table("report_ai").update({
            "status": status_value,
        }).eq("report_id", report_id).execute()
    except Exception:
        return None


