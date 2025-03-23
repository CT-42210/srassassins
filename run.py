import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine the configuration to use
config_name = os.environ.get('FLASK_ENV', 'development')

# Create app with specified configuration
from app import create_app
app = create_app(config_name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 42069)))
