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
        "validated": "file_validated",
        "processed": "file_processed",
        "uploaded": "slices_uploaded",
        "ai_completed": "ai_analysis_completed",
        "completed": "completed",
        "file_uploaded": "file_uploaded",
        "file_too_large": "file_too_large",
        "invalid_file": "invalid_file",
        "workflow_started": "workflow_started",
        "processing_sync": "processing_sync",
    }
    status_value = status_mapping.get(stage, stage)
    try:
        return supabase.table("report_ai").update({
            "status": status_value,
        }).eq("report_id", report_id).execute()
    except Exception:
        return None


