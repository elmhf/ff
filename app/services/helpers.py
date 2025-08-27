import os
import time
import json
import nibabel as nib
import pydicom
from flask import current_app


def _get_app_and_supabase():
    """Get Flask app and supabase whether inside app context or fallback to module-level app."""
    try:
        app = current_app  # works if within app context
        supabase = getattr(app.extensions, 'get', lambda k, d=None: None)('supabase') if hasattr(app, 'extensions') else None
        # If extensions is a dict
        if supabase is None and hasattr(app, 'extensions') and isinstance(app.extensions, dict):
            supabase = app.extensions.get('supabase')
        return app, supabase
    except Exception:
        # Fallback import if no app context
        from app import app as fallback_app  # type: ignore
        try:
            supabase = getattr(fallback_app, 'extensions', {}).get('supabase')
        except Exception:
            try:
                from app import supabase as fallback_supabase  # type: ignore
                supabase = fallback_supabase
            except Exception:
                supabase = None
        return fallback_app, supabase


def allowed_file(filename):
    """Enhanced file validation based on configured ALLOWED_EXTENSIONS."""
    app, _ = _get_app_and_supabase()
    if not filename or '.' not in filename:
        return False
    if filename.lower().endswith('.nii.gz'):
        return True
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in app.config['ALLOWED_EXTENSIONS']


def validate_file_content(file_path, filename):
    """Validate file content by inspecting header/pixels for NIfTI or DICOM."""
    try:
        if filename.lower().endswith(('.nii', '.nii.gz')):
            img = nib.load(file_path)
            data = img.get_fdata()
            return (data.size > 0, "Valid NIfTI file") if data.size > 0 else (False, "Empty NIfTI file")
        elif filename.lower().endswith(('.dcm', '.dicom', '.ima')):
            ds = pydicom.dcmread(file_path)
            return (True, "Valid DICOM file") if hasattr(ds, 'pixel_array') else (False, "DICOM has no pixel data")
        return True, "File validation passed"
    except Exception as e:
        return False, f"File validation failed: {str(e)}"


def cleanup_old_files():
    """Clean up old uploaded files from UPLOAD_FOLDER and PROCESSED_FOLDER based on age."""
    app, _ = _get_app_and_supabase()
    try:
        current_time = time.time()
        max_age = 24 * 60 * 60  # 24 hours
        for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER']]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    filepath = os.path.join(folder, filename)
                    if os.path.isfile(filepath):
                        if current_time - os.path.getmtime(filepath) > max_age:
                            os.remove(filepath)
    except Exception:
        # Best-effort cleanup; log will be handled in caller
        pass


def validate_configuration():
    """Validate application configuration and create required directories."""
    app, _ = _get_app_and_supabase()
    required_configs = [
        'UPLOAD_FOLDER', 'PROCESSED_FOLDER', 'BASE_PATH',
        'MAX_FILE_SIZE', 'ALLOWED_EXTENSIONS'
    ]
    missing_configs = []
    for config_key in required_configs:
        if not app.config.get(config_key):
            missing_configs.append(config_key)
    if missing_configs:
        raise ValueError(f"Missing required configurations: {missing_configs}")
    for directory in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER']]:
        os.makedirs(directory, exist_ok=True)
    for view in ['axial', 'coronal', 'sagittal']:
        os.makedirs(os.path.join(app.config['BASE_PATH'], view), exist_ok=True)


def update_report_status_completed(report_id, stage="completed"):
    """Update report status in database with stage information using Supabase."""
    _, supabase = _get_app_and_supabase()
    if not supabase or not report_id:
        return None
    status_mapping = {
        "validated": "file_validated",
        "processed": "file_processed",
        "uploaded": "slices_uploaded",
        "ai_completed": "ai_analysis_completed",
        "completed": "completed"
    }
    status_value = status_mapping.get(stage, stage)
    try:
        response = supabase.table("report_ai").update({
            "status": status_value,
        }).eq("report_id", report_id).execute()
        return response
    except Exception:
        return None


