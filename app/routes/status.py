from flask import Blueprint, jsonify
from app.services.job_status import JobStatusManager
from app.celery_app import celery
import logging

status_bp = Blueprint('status', __name__)
logger = logging.getLogger(__name__)


@status_bp.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    try:
        if not job_id:
            return jsonify({'error': 'Job ID required'}), 400
        status = JobStatusManager.get_status(job_id)
        if status:
            return jsonify(status)
        if celery:
            try:
                result = celery.AsyncResult(job_id)
                celery_status = {
                    'job_id': job_id,
                    'status': result.status.lower(),
                    'message': str(result.info) if result.info else '',
                    'progress': result.info.get('progress', 0) if isinstance(result.info, dict) else 0,
                    'result': result.result if result.successful() else None
                }
                return jsonify(celery_status)
            except Exception:
                pass
        return jsonify({'error': 'Job not found or status unavailable'}), 404
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        return jsonify({'error': 'Status check failed'}), 500


@status_bp.route('/api/running-tasks', methods=['GET'])
def list_running_tasks():
    try:
        if not celery:
            return jsonify({'error': 'Celery not available'}), 500
        i = celery.control.inspect()
        active = i.active() or {}
        running_tasks = []
        for worker, tasks in active.items():
            for task in tasks:
                running_tasks.append({
                    'id': task.get('id'),
                    'name': task.get('name'),
                    'args': task.get('args'),
                    'kwargs': task.get('kwargs'),
                    'worker': worker
                })
        return jsonify({'running_tasks': running_tasks})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


