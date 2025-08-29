from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
import os
import logging
from app.utils.validators import allowed_file, validate_file_content
from app.services.supabase_manager import update_report_status
from app.tasks.workflow import start_complete_workflow
from app.tasks.workflow import start_pano_workflow
from app.services.uploads import SupabaseUploadManager


upload_bp = Blueprint('upload', __name__)
logger = logging.getLogger(__name__)


@upload_bp.route('/cbct-report-generated', methods=['POST'])
def upload_medical_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in request'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if not allowed_file(file.filename):
            return jsonify({
                'error': 'File type not allowed',
                'allowed_extensions': list(current_app.config['ALLOWED_EXTENSIONS'])
            }), 400

        filename = secure_filename(file.filename)
        upload_id = request.form.get('upload_id', str(uuid.uuid4()))
        clinic_id = request.form.get('clinic_id')
        patient_id = request.form.get('patient_id')
        report_type = request.form.get('report_type') or 'cbct'
        report_id = request.form.get('report_id')

        if report_id:
            update_report_status(report_id, "file_uploaded")

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > current_app.config['MAX_FILE_SIZE']:
            if report_id:
                update_report_status(report_id, "file_too_large")
            return jsonify({'error': f'File too large. Maximum size: {current_app.config["MAX_FILE_SIZE"] / (1024*1024):.1f} MB'}), 400

        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{upload_id}_{filename}")
        file.save(save_path)

        is_valid, validation_msg = validate_file_content(save_path, filename)
        if not is_valid:
            os.remove(save_path)
            if report_id:
                update_report_status(report_id, "invalid_file")
            return jsonify({'error': validation_msg}), 400

        file_info = {
            'path': save_path,
            'filename': filename,
            'original_name': file.filename,
            'file_size': file_size
        }

        task_info = start_complete_workflow(file_info, upload_id, clinic_id, patient_id, report_id)

        return jsonify({
            'job_id': task_info['workflow_id'],
            'status': 'queued',
            'upload_id': upload_id,
            'report_id': report_id,
            'message': 'File uploaded and processing workflow started',
            'file_info': {
                'filename': filename,
                'file_size': file_size
            }
        }), 202
    except Exception as e:
        logger.error(f"Error in /cbct-report-generated: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@upload_bp.route('/pano-reports-generated', methods=['POST'])
def upload_pano_report():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in request'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # Allow image files for pano reports (jpg, jpeg, png, tiff, bmp)
        allowed_image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        file_ext = os.path.splitext(file.filename.lower())[1]
        
        if file_ext not in allowed_image_extensions:
            return jsonify({
                'error': 'File type not allowed for panoramic reports',
                'allowed_extensions': list(allowed_image_extensions),
                'received_extension': file_ext
            }), 400

        filename = secure_filename(file.filename)
        upload_id = request.form.get('upload_id', str(uuid.uuid4()))
        clinic_id = request.form.get('clinic_id')
        patient_id = request.form.get('patient_id')
        report_type = 'pano'  # Force report type to pano
        report_id = request.form.get('report_id')

        if report_id:
            update_report_status(report_id, "file_uploaded")

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        # Increase max file size for image files (50MB)
        max_image_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_image_size:
            if report_id:
                update_report_status(report_id, "file_too_large")
            return jsonify({'error': f'Image file too large. Maximum size: {max_image_size / (1024*1024):.1f} MB'}), 400

        # Read image bytes and validate header (no DICOM validation)
        try:
            file.seek(0)
            image_bytes = file.read()
            header = image_bytes[:8]
            if not (header.startswith(b'\xff\xd8\xff') or  # JPEG
                    header.startswith(b'\x89PNG\r\n\x1a\n') or  # PNG
                    header.startswith(b'II*\x00') or  # TIFF little-endian
                    header.startswith(b'MM\x00*') or  # TIFF big-endian
                    header.startswith(b'BM')):  # BMP
                if report_id:
                    update_report_status(report_id, "invalid_file")
                return jsonify({'error': 'Invalid image file format'}), 400
        except Exception as e:
            if report_id:
                update_report_status(report_id, "invalid_file")
            return jsonify({'error': f'Error reading image file: {str(e)}'}), 400

        # Save bytes to disk
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{upload_id}_{filename}")
        try:
            with open(save_path, 'wb') as out_f:
                out_f.write(image_bytes)
        except Exception as e:
            if os.path.exists(save_path):
                os.remove(save_path)
            return jsonify({'error': f'Error saving image file: {str(e)}'}), 500

        # Upload the original pano image to Supabase storage
        pano_uploader = SupabaseUploadManager()
        upload_image_result = pano_uploader.upload_pano_image_bytes(
            image_bytes=image_bytes,
            filename=filename,
            clinic_id=clinic_id,
            patient_id=patient_id,
            report_id=report_id
        )

        file_info = {
            'path': save_path,
            'filename': filename,
            'original_name': file.filename,
            'file_size': file_size,
            'pano_image_upload': upload_image_result
        }

        task_info = start_pano_workflow(file_info, upload_id, clinic_id, patient_id, report_type, report_id)

        return jsonify({
            'job_id': task_info['workflow_id'],
            'status': 'queued',
            'upload_id': upload_id,
            'report_id': report_id,
            'message': 'Panoramic file uploaded and processing workflow started',
            'file_info': {
                'filename': filename,
                'file_size': file_size,
                'pano_image_public_url': upload_image_result.get('public_url') if isinstance(upload_image_result, dict) else None
            }
        }), 202
    except Exception as e:
        logger.error(f"Error in /pano-reports: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@upload_bp.route('/3d-report', methods=['POST'])
def upload_3d_report():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part in request'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        if not allowed_file(file.filename):
            return jsonify({
                'error': 'File type not allowed',
                'allowed_extensions': list(current_app.config['ALLOWED_EXTENSIONS'])
            }), 400

        filename = secure_filename(file.filename)
        upload_id = request.form.get('upload_id', str(uuid.uuid4()))
        clinic_id = request.form.get('clinic_id')
        patient_id = request.form.get('patient_id')
        report_type = '3d'  # Force report type to 3d
        report_id = request.form.get('report_id')

        if report_id:
            update_report_status(report_id, "file_uploaded")

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > current_app.config['MAX_FILE_SIZE']:
            if report_id:
                update_report_status(report_id, "file_too_large")
            return jsonify({'error': f'File too large. Maximum size: {current_app.config["MAX_FILE_SIZE"] / (1024*1024):.1f} MB'}), 400

        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"{upload_id}_{filename}")
        file.save(save_path)

        is_valid, validation_msg = validate_file_content(save_path, filename)
        if not is_valid:
            os.remove(save_path)
            if report_id:
                update_report_status(report_id, "invalid_file")
            return jsonify({'error': validation_msg}), 400

        file_info = {
            'path': save_path,
            'filename': filename,
            'original_name': file.filename,
            'file_size': file_size
        }

        task_info = start_complete_workflow(file_info, upload_id, clinic_id, patient_id, report_type, report_id)

        return jsonify({
            'job_id': task_info['workflow_id'],
            'status': 'queued',
            'upload_id': upload_id,
            'report_id': report_id,
            'message': '3D file uploaded and processing workflow started',
            'file_info': {
                'filename': filename,
                'file_size': file_size
            }
        }), 202
    except Exception as e:
        logger.error(f"Error in /3d-report: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@upload_bp.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'Medical File Processor',
        'version': '2.1',
        'status': 'running',
        'endpoints': {
            'cbct_upload': '/cbct-report-generated',
            'pano_upload': '/pano-reports-generated',
            '3d_upload': '/3d-report',
            'status': '/job-status/<job_id>',
            'health': '/health',
            'cleanup': '/cleanup'
        }
    })


