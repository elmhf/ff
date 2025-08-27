broker_url = 'redis://redis:6379/0'
result_backend = 'redis://redis:6379/0'

worker_concurrency = 4
worker_prefetch_multiplier = 1
task_acks_late = True

task_routes = {
    'tasks.long_task': {'queue': 'long'},
    'tasks.reverse_string': {'queue': 'short'},
}
