import os
import time
import mimetypes
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


    def upload_pano_image(self, image_path, clinic_id, patient_id, report_id, content_type=None, max_size_bytes=50 * 1024 * 1024):
        """Upload the original panoramic image to Supabase storage under the pano folder.

        Storage path: reports/{clinic_id}/{patient_id}/pano/{report_id}/original<ext>
        """
        if not self.supabase:
            raise Exception("Supabase client not available")
        if not os.path.exists(image_path):
            return {"success": False, "error": "Pano image file not found"}
        try:
            file_size = os.path.getsize(image_path)
            if file_size == 0:
                return {"success": False, "error": "Empty pano image file"}
            if file_size > max_size_bytes:
                return {"success": False, "error": "Pano image file too large"}
        except Exception as e:
            return {"success": False, "error": f"File validation failed: {str(e)}"}

        _, ext = os.path.splitext(image_path)
        ext = ext.lower() or ".jpg"
        if not content_type:
            guessed, _ = mimetypes.guess_type(image_path)
            content_type = guessed or "image/jpeg"

        storage_path = f"{clinic_id}/{patient_id}/pano/{report_id}/original{ext}"
        for attempt in range(self.max_retries):
            try:
                with open(image_path, 'rb') as f:
                    file_data = f.read()
                result = self.supabase.storage.from_("reports").upload(
                    path=storage_path,
                    file=file_data,
                    file_options={"content-type": content_type, "cache-control": "3600", "upsert": "true"}
                )
                if result:
                    public_url = self.supabase.storage.from_("reports").get_public_url(storage_path)
                    return {"success": True, "storage_path": storage_path, "public_url": public_url, "file_size": file_size}
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (2 ** attempt))
                else:
                    return {"success": False, "error": f"Upload failed after {self.max_retries} attempts: {str(e)}"}
        return {"success": False, "error": "Upload failed"}

    def upload_pano_image_bytes(self, image_bytes, filename, clinic_id, patient_id, report_id, content_type=None, max_size_bytes=50 * 1024 * 1024):
        """Upload the original panoramic image to Supabase storage from in-memory bytes.

        Storage path: reports/{clinic_id}/{patient_id}/pano/{report_id}/original<ext>
        """
        if not self.supabase:
            raise Exception("Supabase client not available")
        if image_bytes is None:
            return {"success": False, "error": "No image data provided"}
        try:
            file_size = len(image_bytes)
            if file_size == 0:
                return {"success": False, "error": "Empty pano image data"}
            if file_size > max_size_bytes:
                return {"success": False, "error": "Pano image file too large"}
            
            # Validate that the bytes represent a valid image
            if len(image_bytes) < 8:
                return {"success": False, "error": "Image data too short to be valid"}
            
            # Check for common image headers
            header = image_bytes[:8]
            valid_headers = [
                b'\xff\xd8\xff',  # JPEG
                b'\x89PNG\r\n\x1a\n',  # PNG
                b'II*\x00',  # TIFF little-endian
                b'MM\x00*',  # TIFF big-endian
                b'BM',  # BMP
                b'GIF87a',  # GIF
                b'GIF89a'   # GIF
            ]
            
            is_valid_image = any(header.startswith(h) for h in valid_headers)
            if not is_valid_image:
                return {"success": False, "error": "Invalid image format - unrecognized header"}
                
        except Exception as e:
            return {"success": False, "error": f"Data validation failed: {str(e)}"}

        # Simplify: always use PNG format for better compatibility
        ext = '.png'
        content_type = 'image/png'

        storage_path = f"{clinic_id}/{patient_id}/pano/{report_id}/original{ext}"
        
        # Add debug logging
        print(f"DEBUG: Uploading pano image - size: {file_size}, ext: {ext}, content_type: {content_type}, path: {storage_path}")
        
        for attempt in range(self.max_retries):
            try:
                result = self.supabase.storage.from_("reports").upload(
                    path=storage_path,
                    file=image_bytes,
                    file_options={"content-type": content_type, "cache-control": "3600", "upsert": "true"}
                )
                if result:
                    public_url = self.supabase.storage.from_("reports").get_public_url(storage_path)
                    return {"success": True, "storage_path": storage_path, "public_url": public_url, "file_size": file_size}
            except Exception as e:
                print(f"DEBUG: Upload attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (2 ** attempt))
                else:
                    return {"success": False, "error": f"Upload failed after {self.max_retries} attempts: {str(e)}"}
        return {"success": False, "error": "Upload failed"}

