import redis
from celery import Celery
import logging

# Logger
logger = logging.getLogger(__name__)

# Globals
redis_client = None
celery = None
REDIS_AVAILABLE = False

def setup_redis_celery(app,logger):
    """Setup Redis and Celery with enhanced error handling"""
    global redis_client, celery, REDIS_AVAILABLE
    
    try:
        # Test Redis connection with timeout
        redis_client = redis.from_url(app.config['REDIS_URL'], socket_timeout=5, socket_connect_timeout=5)
        redis_client.ping()
        REDIS_AVAILABLE = True
        
        # Initialize Celery with better configuration
        celery = Celery(
            'medical_processor',
            backend=app.config['CELERY_RESULT_BACKEND'],
            broker=app.config['CELERY_BROKER_URL'],
            include=['tasks']  # بدلها بالباكيج اللي فيه التاسكات متاعك
        )
        
        # Enhanced Celery configuration
        celery.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_time_limit=30 * 60,  # 30 minutes
            task_soft_time_limit=25 * 60,  # 25 minutes soft limit
            worker_prefetch_multiplier=1,
            result_expires=3600,  # 1 hour
            broker_connection_retry_on_startup=True,
            broker_transport_options={
                'visibility_timeout': 3600,
                'retry_policy': {
                    'timeout': 5.0
                }
            }
        )
        
        logger.info("✅ Redis and Celery setup successful")
        return True
        
    except Exception as e:
        redis_client = None
        celery = None
        REDIS_AVAILABLE = False
        logger.error(f"❌ Redis/Celery setup failed: {e}")
        return False
