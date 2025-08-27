
import os
from config.supabase_config import get_supabase



def upload_single_slice_to_supabase(slice_path, clinic_id, patient_id, report_type, report_id, view, slice_index):
    """
    Upload a single slice image to Supabase storage and return its public URL and storage path.
    """
    try:
        supabase = get_supabase()
        if not supabase:
            return {"success": False, "error": "Supabase client not available"}
        if not os.path.exists(slice_path):
            return {"success": False, "error": f"Slice file not found: {slice_path}"}

        # Build storage path
        storage_path = f"medical_slices/{clinic_id}/{patient_id}/{report_type.lower()}/{report_id}/{view}/{slice_index}.jpg"

        # Upload to Supabase storage
        with open(slice_path, "rb") as f:
            file_data = f.read()
            response = supabase.storage.from_("medical-slices").upload(storage_path, file_data)

        if hasattr(response, "error") and response.error:
            return {"success": False, "error": str(response.error)}

        # Get public URL
        public_url = supabase.storage.from_("medical-slices").get_public_url(storage_path)

        return {
            "success": True,
            "storage_path": storage_path,
            "public_url": public_url
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
