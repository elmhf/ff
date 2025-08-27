import logging
import redis
from celery import Celery
from config.config import Config

logger = logging.getLogger(__name__)

redis_client = None
celery = None
REDIS_AVAILABLE = False


def setup_redis_celery():
    global redis_client, celery, REDIS_AVAILABLE
    try:
        redis_client = redis.from_url(Config.REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
        redis_client.ping()
        REDIS_AVAILABLE = True

        celery = Celery(
            'medical_processor',
            backend=Config.CELERY_RESULT_BACKEND,
            broker=Config.CELERY_BROKER_URL,
            include=[
                'app.tasks.validation',
                'app.tasks.processing',
                'app.tasks.upload',
                'app.tasks.ai',
                'app.tasks.aggregate',
            ]
        )

        celery.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_time_limit=30 * 60,
            task_soft_time_limit=25 * 60,
            worker_prefetch_multiplier=1,
            result_expires=3600,
            broker_connection_retry_on_startup=True,
            broker_transport_options={
                'visibility_timeout': 3600,
                'retry_policy': {'timeout': 5.0}
            }
        )

        # Load additional celery settings if present
        try:
            celery.config_from_object('celeryconfig')
        except Exception:
            pass

        logger.info("✅ Redis and Celery setup successful (module)")
        return True
    except Exception as e:
        redis_client = None
        celery = None
        REDIS_AVAILABLE = False
        logger.error(f"❌ Redis/Celery setup failed (module): {e}")
        return False


# Initialize on import
setup_redis_celery()


