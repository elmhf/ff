import json
import time
import logging
from datetime import datetime
from app.celery_app import redis_client

logger = logging.getLogger(__name__)


class JobStatusManager:
    """Streamlined job status management using Redis (extracted)."""

    REDIS_TTL = 86400  # 24 hours
    MAX_RETRIES = 3

    @classmethod
    def _get_job_key(cls, job_id):
        return f"job_status:{job_id}"

    @classmethod
    def create_or_update_status(cls, job_id, status, message="", progress=0, result=None):
        if not job_id or redis_client is None:
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

        for attempt in range(cls.MAX_RETRIES):
            try:
                pipe = redis_client.pipeline()
                pipe.setex(cls._get_job_key(job_id), cls.REDIS_TTL, json.dumps(job_data))
                pipe.zadd("job_timestamps", {job_id: time.time()})
                pipe.execute()
                logger.info(f"Job status updated: {job_id} - {status} ({progress}%)")
                return job_data
            except Exception as e:
                if attempt < cls.MAX_RETRIES - 1:
                    time.sleep(0.5 * (2 ** attempt))
                else:
                    logger.error(f"Failed to store in Redis after {cls.MAX_RETRIES} attempts: {e}")
                    return None

    @classmethod
    def get_status(cls, job_id):
        if not job_id or redis_client is None:
            return None
        try:
            job_data = redis_client.get(cls._get_job_key(job_id))
            return json.loads(job_data) if job_data else None
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None


