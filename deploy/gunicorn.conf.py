"""
Gunicorn configuration for SolarGuard deployment on Oracle Cloud Ampere A1 (Ubuntu ARM64).
Optimized for 4-core Ampere A1 with generous RAM (up to 24 GB Always Free).
"""

import os
import multiprocessing

# Server socket binding (proxied behind Nginx)
bind = os.environ.get('GUNICORN_BIND', '127.0.0.1:8000')

# Worker processes & concurrency
# On Oracle Ampere A1 (4 OCPUs), 2 workers with 4 threads each provides 8 concurrent request handlers
# while comfortably sharing memory.
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
threads = int(os.environ.get('GUNICORN_THREADS', '4'))
worker_class = 'gthread'

# Worker timeout
# 120s timeout ensures initial TensorFlow graph loading and cold inference completes without interruption
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = 30
keepalive = 5

# Logging configuration
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')

# Memory recycling
# Recycles worker after 1,000 requests to prevent gradual memory fragmentation
max_requests = 1000
max_requests_jitter = 50

# Avoid preloading to prevent TensorFlow fork locks
preload_app = False
