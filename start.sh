#!/bin/bash
set -e
# Install Ollama
echo "Installing Ollama..."
curl -fsSL https://ollama.com/install.sh | sh
# Make sure we have nohup
echo "Installing additional dependencies..."
apt-get update && apt-get install -y procps
# Start Flask app
echo "Starting Flask application..."
python3 -m flask run --host=0.0.0.0 --port=5001