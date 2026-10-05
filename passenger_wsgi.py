import sys
import os

# Set up current directory in sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Import the Flask app as 'application' (WSGI standard required by cPanel Passenger)
from app import app as application
