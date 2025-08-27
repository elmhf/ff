import redis, json, time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
REDIS_AVAILABLE = True  # لازم تعمل setup قبل

class JobStatusManager:
    @staticmethod
    def create_or_update_status(job_id, status, message="", progress=0, result=None):
        if not job_id or not REDIS_AVAILABLE:
            logger.error("Job ID required and Redis must be available")
            return None
        job_data = {
            'job_id': job_id,
            'status': status,
            'message': message,
            'progress': max(0, min(100, progress)),
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }
        try:
            redis_client.setex(f"job_status:{job_id}", 86400, json.dumps(job_data))
            redis_client.zadd("job_timestamps", {job_id: time.time()})
            logger.info(f"📊 Job status updated: {job_id} - {status} ({progress}%)")
            return job_data
        except Exception as e:
            logger.error(f"Failed to store in Redis: {e}")
            return None

    @staticmethod
    def get_status(job_id):
        try:
            job_data = redis_client.get(f"job_status:{job_id}")
            if job_data:
                return json.loads(job_data)
            return None
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None
