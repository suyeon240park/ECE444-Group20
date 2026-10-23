"""gunicorn settings for staging (#22). gunicorn loads this file from ``backend/`` by itself."""

import os

# Render routes traffic to $PORT.
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# One process, so the product cache (#14) is shared, with threads so that a photo
# waiting on the vision model (#42) does not block barcode lookups.
workers = 1
threads = 4

# A label photo can take up to VISION_TIMEOUT_SECONDS (60) on each vision model it
# tries; gunicorn's default of 30 s would kill the request first.
timeout = 180
