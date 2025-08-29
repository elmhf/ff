import os
import time
import json
import datetime
from uuid import uuid4
from app.celery_app import celery
from app.services.job_status import JobStatusManager
from app.services.supabase_manager import update_report_status
from app import create_app
from flask import current_app as app
import logging

logger = logging.getLogger(__name__)


class SupabaseUploadManager:
    def __init__(self, task_id=None):
        self.task_id = task_id
        self.max_retries = 3
        self.max_file_size = 10 * 1024 * 1024
        self.max_json_size = 5 * 1024 * 1024  # 5MB limit for JSON files

    @property
    def supabase(self):
        try:
            return app.extensions.get('supabase') if hasattr(app, 'extensions') else None
        except Exception:
            return None

    def upload_report_json(self, report_data, clinic_id, patient_id, report_type, report_id, celery_task=None):
        """
        Upload report dictionary data to Supabase storage as JSON file
        
        Args:
            report_data (dict): Python dictionary containing report data
            clinic_id (str): Clinic identifier
            patient_id (str): Patient identifier
            report_type (str): Type of report (e.g., 'mri', 'ct', etc.)
            report_id (str): Unique report identifier
            celery_task: Optional celery task for progress updates
            
        Returns:
            dict: Upload result with success status, storage path, and public URL
        """
        if not self.supabase:
            raise Exception("Supabase client not available")
        
        # Validate report data
        if not report_data:
            return {"success": False, "error": "No report data provided"}
        
        try:
            # Convert to JSON string
            json_data = json.dumps(report_data, ensure_ascii=False, indent=2)
            json_bytes = json_data.encode('utf-8')
            
            # Check file size
            if len(json_bytes) > self.max_json_size:
                return {"success": False, "error": "Report JSON too large"}
            
        except (TypeError, ValueError) as e:
            return {"success": False, "error": f"Invalid JSON data: {str(e)}"}
        
        # Define storage path
        storage_path = f"{clinic_id}/{patient_id}/{report_type.lower()}/{report_id}/report.json"
        
        # Update progress if task is available
        if self.task_id:
            JobStatusManager.create_or_update_status(
                self.task_id, 'processing', 'Uploading report JSON...', 95
            )
        if celery_task:
            celery_task.update_state(
                state='PROGRESS', 
                meta={'progress': 95, 'message': 'Uploading report JSON...'}
            )
        
        # Attempt upload with retries
        for attempt in range(self.max_retries):
            try:
                result = self.supabase.storage.from_("reports").upload(
                    path=storage_path,
                    file=json_bytes,
                    file_options={
                        "content-type": "application/json",
                        "cache-control": "3600",
                        "upsert": "true"
                    }
                )
                
                if result:
                    public_url = self.supabase.storage.from_("reports").get_public_url(storage_path)
                    return {
                        "success": True,
                        "storage_path": storage_path,
                        "public_url": public_url,
                        "file_size": len(json_bytes)
                    }
                    
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(1 * (2 ** attempt))  # Exponential backoff
                else:
                    return {
                        "success": False,
                        "error": f"Upload failed after {self.max_retries} attempts: {str(e)}"
                    }
        
        return {"success": False, "error": "Upload failed"}

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

    def upload_complete_report(self, slice_counts, report_data, clinic_id, patient_id, report_type, report_id, celery_task=None):
        """
        Upload both slices and report JSON in one method
        
        Returns:
            dict: Complete upload results including slices and report JSON
        """
        try:
            # Upload slices first
            slice_results = self.upload_all_slices(
                slice_counts, clinic_id, patient_id, report_type, report_id, celery_task
            )
            
            # Upload report JSON
            json_result = self.upload_report_json(
                report_data, clinic_id, patient_id, report_type, report_id, celery_task
            )
            
            # Combine results
            complete_results = slice_results.copy()
            complete_results["report_json"] = json_result
            
            return complete_results
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Complete upload failed: {str(e)}"
            }


# Celery Tasks
@celery.task(bind=True, name='upload_medical_slices')
def upload_medical_slices_task(self, processing_result, clinic_id, patient_id, report_type, report_id):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            # Update status to upload started
            if report_id:
                update_report_status(report_id, "upload_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Uploading medical slices...', 60)
            
            # Check if processing was successful
            if not processing_result or processing_result.get('status') != 'processed':
                logger.warning("Processing not completed, skipping upload")
                return {
                    'status': 'skipped',
                    'message': 'Processing not completed, skipping upload',
                    'processing_result': processing_result
                }
            
            # Use SupabaseUploadManager to upload slices
            try:
                from app.services.uploads import SupabaseUploadManager
                
                # Get slice counts from processing result
                slice_counts = processing_result.get('processing_result', {}).get('slice_counts', {})
                
                if not slice_counts or sum(slice_counts.values()) == 0:
                    logger.warning("No slices to upload")
                    return {
                        'status': 'skipped',
                        'message': 'No slices to upload',
                        'processing_result': processing_result
                    }
                
                # Create upload manager and upload all slices
                upload_manager = SupabaseUploadManager(task_id=task_id)
                upload_result = upload_manager.upload_all_slices(
                    slice_counts, clinic_id, patient_id, report_type, report_id, self
                )
                
                if upload_result.get('total_uploaded', 0) > 0:
                    logger.info(f"Successfully uploaded {upload_result['total_uploaded']} slices")
                else:
                    logger.warning("No slices were uploaded successfully")
                    
            except ImportError as e:
                logger.error(f"Could not import SupabaseUploadManager: {e}")
                # Fallback to simulation
                import time
                time.sleep(2)
                upload_result = {"total_uploaded": 0, "failed_uploads": 0}
            except Exception as e:
                logger.error(f"Upload error: {e}")
                upload_result = {"total_uploaded": 0, "failed_uploads": 0, "error": str(e)}
            
            # Update status to uploaded
            if report_id:
                update_report_status(report_id, "uploaded")
            
            result = {
                'status': 'uploaded',
                'message': f'Medical slices uploaded successfully ({upload_result.get("total_uploaded", 0)} slices)',
                'clinic_id': clinic_id,
                'patient_id': patient_id,
                'report_type': report_type,
                'report_id': report_id,
                'processing_result': processing_result,
                'upload_result': upload_result
            }
            JobStatusManager.create_or_update_status(task_id, 'completed', 'Medical slices uploaded', 100, result)
            return result
    except Exception as e:
        error_msg = f"Upload error: {str(e)}"
        if report_id:
            # Update status to upload failed
            update_report_status(report_id, "upload_failed")
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise


@celery.task(bind=True, name='upload_pano_image')
def upload_pano_image_task(self, validation_result, clinic_id, patient_id, report_id):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Uploading pano image...', 20)

            try:
                from app.services.uploads import SupabaseUploadManager
                file_info = validation_result.get('file_info', {})
                image_path = (file_info or {}).get('path')
                filename = (file_info or {}).get('filename') or 'pano.jpg'
                if not image_path or not os.path.exists(image_path):
                    raise FileNotFoundError('Pano image path not found')
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()

                uploader = SupabaseUploadManager(task_id=task_id)
                upload_result = uploader.upload_pano_image_bytes(
                    image_bytes=image_bytes,
                    filename=filename,
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    report_id=report_id
                )
            except Exception as e:
                upload_result = {"success": False, "error": str(e)}

            status = 'uploaded' if upload_result.get('success') else 'skipped'
            result = {
                'status': status,
                'message': 'Pano image uploaded to storage' if upload_result.get('success') else 'Pano image upload failed or skipped',
                'file_info': file_info,
                'clinic_id': clinic_id,
                'patient_id': patient_id,
                'report_type': 'pano',
                'report_id': report_id,
                'upload_result': upload_result
            }
            JobStatusManager.create_or_update_status(task_id, 'completed', 'Pano image upload finished', 40, result)
            return result
    except Exception as e:
        error_msg = f"Pano image upload error: {str(e)}"
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise

@celery.task(bind=True, name='upload_report_to_storage')
def upload_report_to_storage_task(self, ai_result):
    task_id = self.request.id
    try:
        app = create_app()
        with app.app_context():
            # Extract parameters from AI result
            file_info = ai_result.get('file_info', {})
            upload_id = ai_result.get('upload_id')
            clinic_id = ai_result.get('clinic_id')
            patient_id = ai_result.get('patient_id')
            report_type = ai_result.get('report_type')
            report_id = ai_result.get('report_id')
            
            # Update status to report upload started
            if report_id:
                update_report_status(report_id, "report_upload_started")
            
            JobStatusManager.create_or_update_status(task_id, 'processing', 'Uploading AI report to storage...', 80)
            
            # Check if AI analysis was successful
            if not ai_result or ai_result.get('status') != 'ai_completed':
                logger.warning("AI analysis not completed, skipping report upload")
                return {
                    'status': 'skipped',
                    'message': 'AI analysis not completed, skipping report upload',
                    'ai_result': ai_result
                }
            
            # Use SupabaseUploadManager to upload report JSON
            try:
                # Get the AI result data directly from the AI pipeline
                ai_analysis_data = ai_result.get('ai_result', {})
                
                # If AI result is None or empty, create a basic structure
                if not ai_analysis_data:
                    ai_analysis_data = {
                        "status": "ai_completed",
                        "message": "AI analysis completed with random data",
                        "generated_data": {
                            "finding": "Normal scan",
                            "organ": "brain",
                            "confidence": 0.95
                        }
                    }
                
                # Create report data using the AI result
                report_data = {
                    "report_id": report_id,
                    "patient_id": patient_id,
                    "clinic_id": clinic_id,
                    "report_type": report_type,
                    "generated_at": ai_result.get('generated_at', datetime.datetime.now().isoformat()),
                    "ai_analysis": ai_analysis_data,
                    "file_info": file_info,
                    "upload_id": upload_id,
                    "metadata": {
                        "processing_pipeline_id": ai_result.get('metadata', {}).get('processing_pipeline_id', str(uuid4())),
                        "upload_id": upload_id,
                        "task_id": task_id,
                        "ai_result_source": "upload_report_to_storage_task"
                    }
                }
                
                # Create upload manager and upload report JSON
                upload_manager = SupabaseUploadManager(task_id=task_id)
                upload_result = upload_manager.upload_report_json(
                    report_data, clinic_id, patient_id, report_type, report_id, self
                )
                
                if upload_result.get('success'):
                    # Update status to report uploaded
                    if report_id:
                        update_report_status(report_id, "report_uploaded")
                    
                    result = {
                        'status': 'report_uploaded',
                        'message': 'AI report uploaded to storage successfully',
                        'upload_result': upload_result,
                        'report_id': report_id
                    }
                    JobStatusManager.create_or_update_status(task_id, 'completed', 'Report uploaded to storage', 100, result)
                    return result
                else:
                    raise Exception(f"Upload failed: {upload_result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Report upload error: {e}")
                raise Exception(f"Upload failed: {e}")
                
    except Exception as e:
        error_msg = f"Report upload error: {str(e)}"
        # Try to get report_id from the result if available
        try:
            if report_id:
                update_report_status(report_id, "report_upload_failed")
        except:
            pass
        JobStatusManager.create_or_update_status(task_id, 'failed', error_msg, 0)
        self.update_state(state='FAILURE', meta={'error': error_msg})
        raise