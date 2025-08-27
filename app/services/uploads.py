import os
import time
from app.services.job_status import JobStatusManager
from flask import current_app as app


class SupabaseUploadManager:
    def __init__(self, task_id=None):
        self.task_id = task_id
        self.max_retries = 3
        self.max_file_size = 10 * 1024 * 1024

    @property
    def supabase(self):
        try:
            return app.extensions.get('supabase') if hasattr(app, 'extensions') else None
        except Exception:
            return None

    def upload_all_slices(self, slice_counts, clinic_id, patient_id, report_type, report_id, celery_task=None):
        if not self.supabase:
            raise Exception("Supabase client not available")
        upload_results = {
            "axial": [], "coronal": [], "sagittal": [],
            "total_uploaded": 0, "failed_uploads": 0,
            "storage_structure": {
                "clinic_id": clinic_id, "patient_id": patient_id,
                "report_type": report_type.lower(), "report_id": report_id
            },
            "upload_errors": []
        }
        total_slices = sum(slice_counts.values())
        if total_slices == 0:
            raise Exception("No slices to upload")
        uploaded_count = 0
        for view in ['axial', 'coronal', 'sagittal']:
            slice_count = slice_counts.get(view, 0)
            if slice_count == 0:
                continue
            for i in range(slice_count):
                result = self._upload_single_slice(view, i, clinic_id, patient_id, report_type, report_id)
                if result["success"]:
                    upload_results[view].append({
                        "slice_index": i,
                        "storage_path": result["storage_path"],
                        "public_url": result["public_url"]
                    })
                    upload_results["total_uploaded"] += 1
                else:
                    upload_results["failed_uploads"] += 1
                    upload_results["upload_errors"].append({
                        "view": view, "slice_index": i, "error": result.get("error")
                    })
                uploaded_count += 1
                if total_slices > 0 and uploaded_count % 10 == 0:
                    progress = 10 + int((uploaded_count / total_slices) * 85)
                    message = f'Uploading {view} slices... ({uploaded_count}/{total_slices})'
                    if self.task_id:
                        JobStatusManager.create_or_update_status(self.task_id, 'processing', message, progress)
                    if celery_task:
                        celery_task.update_state(state='PROGRESS', meta={'progress': progress, 'message': message})
        return upload_results

    def _upload_single_slice(self, view, slice_index, clinic_id, patient_id, report_type, report_id):
        slice_path = os.path.join(app.config['BASE_PATH'], view, f"{slice_index}.jpg")
        if not os.path.exists(slice_path):
            return {"success": False, "error": "Slice file not found"}
        try:
            file_size = os.path.getsize(slice_path)
            if file_size == 0:
                return {"success": False, "error": "Empty slice file"}
            if file_size > self.max_file_size:
                return {"success": False, "error": "Slice file too large"}
        except Exception as e:
            return {"success": False, "error": f"File validation failed: {str(e)}"}
        storage_path = f"{clinic_id}/{patient_id}/{report_type.lower()}/{report_id}/{view}/{slice_index}.jpg"
        for attempt in range(self.max_retries):
            try:
                with open(slice_path, 'rb') as f:
                    file_data = f.read()
                result = self.supabase.storage.from_("reports").upload(
                    path=storage_path,
                    file=file_data,
                    file_options={"content-type": "image/jpeg", "cache-control": "3600", "upsert": "true"}
                )
                if result:
                    public_url = self.supabase.storage.from_("reports").get_public_url(storage_path)
                    return {"success": True, "storage_path": storage_path, "public_url": public_url}
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (2 ** attempt))
                else:
                    return {"success": False, "error": f"Upload failed after {self.max_retries} attempts: {str(e)}"}
        return {"success": False, "error": "Upload failed"}


