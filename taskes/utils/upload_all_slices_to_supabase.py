
import os
import time
from config.supabase_config import get_supabase
from utils import upload_single_slice_to_supabase


def upload_all_slices_to_supabase(app,JobStatusManager,logger,slice_counts, clinic_id, patient_id, report_type, report_id, task_id=None):
    """Direct slice upload to Supabase function (for internal calls)"""
    try:
        logger.info(f"📤 Starting slice upload directly")
        
        supabase = get_supabase()
        if not supabase:
            raise Exception("Supabase client not available")
        
        if task_id:
            JobStatusManager.create_or_update_status(
                task_id, 'processing', 'Initializing upload...', 5
            )
        
        upload_results = {
            "axial": [],
            "coronal": [],
            "sagittal": [],
            "total_uploaded": 0,
            "failed_uploads": 0,
            "storage_structure": {
                "clinic_id": clinic_id,
                "patient_id": patient_id,
                "report_type": report_type.lower(),
                "report_id": report_id
            },
            "upload_errors": []
        }
        
        views = ['axial', 'coronal', 'sagittal']
        total_slices = sum(slice_counts.values())
        uploaded_count = 0
        
        if total_slices == 0:
            raise Exception("No slices to upload")
        
        for view_idx, view in enumerate(views):
            view_dir = os.path.join(app.config['BASE_PATH'], view)
            slice_count = slice_counts.get(view, 0)
            
            if slice_count == 0:
                logger.info(f"⏭️ Skipping {view} view - no slices")
                continue
            
            logger.info(f"📤 Uploading {slice_count} {view} slices...")
            
            for i in range(slice_count):
                slice_path = os.path.join(view_dir, f"{i}.jpg")
                
                if os.path.exists(slice_path):
                    max_retries = 3
                    retry_count = 0
                    upload_success = False
                    
                    while retry_count < max_retries and not upload_success:
                        try:
                            result = upload_single_slice_to_supabase(
                                slice_path, clinic_id, patient_id, report_type, report_id, view, i
                            )
                            
                            if result["success"]:
                                upload_results[view].append({
                                    "slice_index": i,
                                    "storage_path": result["storage_path"],
                                    "public_url": result["public_url"]
                                })
                                upload_results["total_uploaded"] += 1
                                upload_success = True
                            else:
                                retry_count += 1
                                if retry_count >= max_retries:
                                    upload_results["failed_uploads"] += 1
                                    upload_results["upload_errors"].append({
                                        "view": view,
                                        "slice_index": i,
                                        "error": result.get("error", "Unknown error")
                                    })
                                    logger.error(f"Failed to upload {view} slice {i} after {max_retries} attempts")
                                else:
                                    time.sleep(1 * retry_count)  # Exponential backoff
                                    
                        except Exception as e:
                            retry_count += 1
                            if retry_count >= max_retries:
                                upload_results["failed_uploads"] += 1
                                upload_results["upload_errors"].append({
                                    "view": view,
                                    "slice_index": i,
                                    "error": str(e)
                                })
                                logger.error(f"Exception uploading {view} slice {i}: {e}")
                            else:
                                time.sleep(1 * retry_count)
                    
                    uploaded_count += 1
                    
                    # Update progress
                    if task_id and total_slices > 0:
                        progress = 10 + int((uploaded_count / total_slices) * 85)  # 10-95% range
                        message = f'Uploading {view} slices... ({uploaded_count}/{total_slices})'
                        
                        JobStatusManager.create_or_update_status(task_id, 'processing', message, progress)
                else:
                    logger.warning(f"Slice file not found: {slice_path}")
                    upload_results["failed_uploads"] += 1
                    uploaded_count += 1
        
        # Calculate success rate
        success_rate = (upload_results["total_uploaded"] / total_slices * 100) if total_slices > 0 else 0
        
        final_message = f'Upload completed: {upload_results["total_uploaded"]}/{total_slices} slices ({success_rate:.1f}%)'
        
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'processing', final_message, 100, upload_results)
        logger.info(f"📊 {final_message}")
        
        return upload_results
        
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        if task_id:
            JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        logger.error(f"❌ Upload failed: {error_msg}")
        raise
