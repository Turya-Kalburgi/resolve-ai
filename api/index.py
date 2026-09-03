import sys
import os

# Insert parent directory to sys.path so app module can be imported cleanly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
