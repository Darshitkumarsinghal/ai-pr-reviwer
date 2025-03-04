# Use Ubuntu as base image
FROM ubuntu:20.04
# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
# Install dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Set the working directory
WORKDIR /app
# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r requirements.txt
# Copy application files
COPY app.py /app/
COPY start.sh /app/
# Make startup script executable
RUN chmod +x /app/start.sh
# Expose the API port
EXPOSE 5001
# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5001
# Start using the script
CMD ["/app/start.sh"]