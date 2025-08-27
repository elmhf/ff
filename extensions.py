import os
from flask import Flask
from celery import Celery

app = Flask(__name__)

# Redis config
app.config['CELERY_BROKER_URL'] = os.getenv("REDIS_URL", "redis://redis:6379/0")
app.config['CELERY_RESULT_BACKEND'] = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# You can add other shared objects here, e.g. logger, supabase, executor, etc.
logger = None  # Replace with your logger instance
supabase = None  # Replace with your supabase client
executor = None  # Replace with your executor instance
create_job_status = None  # Replace with your function
rate_limit_lock = None  # Replace with your lock
request_counts = {}
image_cache = {}
cache_max_size = 1000
