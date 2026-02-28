# Gunicorn configuration file
# Automatically detected by gunicorn from the working directory

import os

# Bind to the port Render provides
bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# Number of workers
workers = int(os.environ.get("WEB_CONCURRENCY", 1))

# Preload app in master process before forking workers
# This ensures import errors are visible and workers boot faster
preload_app = True

# Worker timeout (seconds) - increased for slow startup on free tier
timeout = 120

# Graceful timeout for worker restart
graceful_timeout = 30

# Log level
loglevel = "info"

# Access log
accesslog = "-"
