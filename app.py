from flask import Flask
import logging
import os
from routes.pr_review import pr_review_bp
import subprocess
import time
import requests
# Configure logging with more details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
app = Flask(__name__)
# Ollama config
OLLAMA_HOST = os.environ.get('OLLAMA_HOST', 'localhost')
OLLAMA_PORT = os.environ.get('OLLAMA_PORT', '11434')
OLLAMA_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
MODEL_NAME = os.environ.get('MODEL_NAME', 'deepseek-coder-v2')
# Start Ollama server in background
def start_ollama_server():
    try:
        logger.info("Starting Ollama server...")
        process = subprocess.Popen(
            ["nohup", "ollama", "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid
        )
        time.sleep(5)  # Give some time for server to start
        return True
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False
def ensure_model_pulled():
    """Ensure the model is pulled in Ollama"""
    try:
        # Check if model exists
        response = requests.get(f"{OLLAMA_URL}/api/tags")
        if response.status_code == 200:
            models = response.json().get('models', [])
            if any(model.get('name') == MODEL_NAME for model in models):
                logger.info(f"Model {MODEL_NAME} is already pulled")
                return True
                
        # Pull the model
        logger.info(f"Pulling model {MODEL_NAME}...")
        response = requests.post(
            f"{OLLAMA_URL}/api/pull",
            json={"name": MODEL_NAME}
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully pulled model {MODEL_NAME}")
            return True
        else:
            logger.error(f"Failed to pull model: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error ensuring model is pulled: {str(e)}", exc_info=True)
        return False
# Start server on app init
start_ollama_server()
logger.info("Attempting to pull model...")
ensure_model_pulled()
# Register blueprints
app.register_blueprint(pr_review_bp)
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Kubernetes probes"""
    try:
        # Check if Ollama is running
        response = requests.get(f"{OLLAMA_URL}/api/version")
        if response.status_code != 200:
            return jsonify({
                "status": "unhealthy",
                "message": "Ollama server is not responding"
            }), 503
            
        # Simply return healthy if server is responding
        return jsonify({"status": "healthy"})
        
    except requests.RequestException as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "message": f"Connection error: {str(e)}"
        }), 503
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "message": str(e)
        }), 503
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)