import os
import sys

# Directory where passenger_wsgi.py is located
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Add project root to sys.path
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Explicit hosting paths as fallback
HOSTING_PATHS = [
    "/home/vhzafsazwu/jiovendor.com/Backend/websalebackend",
    "/home/whzafszawu/jiovendor.com/Backend/websalebackend",
]
for path in HOSTING_PATHS:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

# Point to Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Ensure .env is loaded in production Passenger WSGI if present
env_file = os.path.join(CURRENT_DIR, ".env")
if os.path.exists(env_file):
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
