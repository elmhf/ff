from flask import Blueprint, jsonify
from datetime import datetime
import logging
from app.celery_app import celery, REDIS_AVAILABLE, redis_client
from flask import current_app

health_bp = Blueprint('health', __name__)
logger = logging.getLogger(__name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {
            'redis': REDIS_AVAILABLE,
            'celery': celery is not None,
            'supabase': (current_app.extensions.get('supabase') is not None) if hasattr(current_app, 'extensions') else False
        }
    }
    if REDIS_AVAILABLE:
        try:
            redis_client.ping()
            health_status['services']['redis_connection'] = True
        except Exception:
            health_status['services']['redis_connection'] = False
            health_status['status'] = 'degraded'
    supabase = current_app.extensions.get('supabase') if hasattr(current_app, 'extensions') else None
    if supabase:
        try:
            supabase.table("report_ai").select("*").limit(1).execute()
            health_status['services']['supabase_connection'] = True
        except Exception:
            health_status['services']['supabase_connection'] = False
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code


@health_bp.route('/cleanup', methods=['POST'])
def cleanup_files():
    try:
        from app.services.helpers import cleanup_old_files
        cleanup_old_files()
        return jsonify({'message': 'Cleanup completed successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Cleanup failed: {str(e)}'}), 500


