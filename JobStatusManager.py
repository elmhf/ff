import json
from time import time

from supabase_auth import datetime


class JobStatusManager:
    """Enhanced job status management using Redis only"""
    
    @staticmethod
    def create_or_update_status(redis_client,logger,REDIS_AVAILABLE,job_id, status, message="", progress=0, result=None):
        """Create or update job status using Redis only"""
        if not job_id or not REDIS_AVAILABLE:
            logger.error("Job ID required and Redis must be available")
            return None
            
        job_data = {
            'job_id': job_id,
            'status': status,
            'message': message,
            'progress': max(0, min(100, progress)),  # Ensure progress is between 0-100
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Store in Redis with retry logic
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                # Store job status with 24-hour expiration
                redis_client.setex(f"job_status:{job_id}", 86400, json.dumps(job_data))
                
                # Also store in a sorted set for cleanup purposes
                redis_client.zadd("job_timestamps", {job_id: time.time()})
                
                logger.info(f"📊 Job status updated: {job_id} - {status} ({progress}%)")
                return job_data
                
            except Exception as e:
                retry_count += 1
                logger.warning(f"Redis store attempt {retry_count} failed: {e}")
                if retry_count >= max_retries:
                    logger.error(f"Failed to store in Redis after {max_retries} attempts")
                    return None
                else:
                    time.sleep(0.5 * retry_count)  # Exponential backoff
        
        return None

    @staticmethod
    def get_status(job_id,redis_client, logger,REDIS_AVAILABLE):
        """Get job status from Redis"""
        if not job_id or not REDIS_AVAILABLE:
            return None
            
        try:
            job_data = redis_client.get(f"job_status:{job_id}")
            if job_data:
                return json.loads(job_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting job status from Redis: {e}")
            return None
