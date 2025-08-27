from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import uuid
import os
import logging
from app.utils.validators import allowed_file, validate_file_content
from app.services.supabase_manager import update_report_status
from app.tasks.workflow import start_complete_workflow


upload_bp = Blueprint('upload', __name__)
logger = logging.getLogger(__name__)


@upload_bp.route('/upload-medical-file', methods=['POST'])
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
        report_type = request.form.get('report_type')
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
            'message': 'File uploaded and processing workflow started',
            'file_info': {
                'filename': filename,
                'file_size': file_size
            }
        }), 202
    except Exception as e:
        logger.error(f"Error in /upload-medical-file: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@upload_bp.route('/', methods=['GET'])
def index():
    return jsonify({
        'service': 'Medical File Processor',
        'version': '2.1',
        'status': 'running',
        'endpoints': {
            'upload': '/upload-medical-file',
            'status': '/job-status/<job_id>',
            'health': '/health',
            'cleanup': '/cleanup'
        }
    })


