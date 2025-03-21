import os
import requests
import subprocess
import time
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine the configuration to use
config_name = os.environ.get('FLASK_ENV', 'development')

# Create app with specified configuration
from app import create_app

app = create_app(config_name)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 42069))

    # Start ngrok in a separate process
    subprocess.Popen(["ngrok", "start", "flask"], stdout=subprocess.PIPE)

    # Wait for ngrok to start
    time.sleep(2)

    # Get ngrok tunnel URL
    try:
        response = requests.get("http://localhost:4040/api/tunnels")
        tunnels = json.loads(response.text)["tunnels"]
        public_url = tunnels[0]["public_url"]
        print(f" * Using ngrok tunnel: {public_url}")
        app.config['BASE_URL'] = public_url
    except Exception as e:
        print(f" * Failed to get ngrok tunnel URL: {str(e)}")
        print(" * Make sure ngrok is installed and configured properly")

    app.run(host='0.0.0.0', port=port)
