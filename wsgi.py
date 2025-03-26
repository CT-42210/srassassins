import os
import sys

# Set base path
base_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, base_dir)

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine the configuration to use
config_name = os.environ.get('FLASK_ENV', 'production')  # Note: Using 'production' as default for WSGI

# Create app with specified configuration
from app import create_app
application = create_app(config_name)  # Standard name for WSGI applications

# For compatibility with some WSGI servers
app = application

if __name__ == '__main__':
    application.run()