# AI Code Review Bot

An automated code review system that leverages the DeepSeek Coder model to analyze pull requests on Bitbucket and provide intelligent feedback as comments.

![AI Code Review]

## Overview

This project implements a containerized Flask application that integrates with Bitbucket to automatically review pull requests. When a PR is created or updated, the service analyzes the code changes using the DeepSeek Coder v2 model through Ollama and posts helpful comments directly on the PR.

## Features

- 🤖 Automated code reviews powered by AI
- 🔍 Detects code issues, bugs, and potential improvements
- 💬 Posts feedback as comments directly on Bitbucket PRs
- 🚀 Containerized for easy deployment
- 🔧 Configurable for different project types and standards
- 🖥️ GPU acceleration support for faster processing

## Architecture

The system consists of:

- **Flask API**: Handles webhook events from Bitbucket
- **Ollama Integration**: Manages the DeepSeek Coder model for code analysis
- **Kubernetes Deployment**: Scalable infrastructure with GPU support

## Prerequisites

- Docker
- Kubernetes cluster with GPU support (for production deployment)
- Bitbucket repository with webhook configuration

## Quick Start

### Local Development

1. Clone the repository:
   ```bash
   git clone https://your-repo-url/ai-code-review.git
   cd ai-code-review
   ```

2. Build the Docker image:
   ```bash
   docker build -t ai-code-review:latest .
   ```

3. Run the container:
   ```bash
   docker run -p 5001:5001 ai-code-review:latest
   ```

4. The service will be available at `http://localhost:5001`

### Kubernetes Deployment

1. Update the image reference in `staging-deployment.yml`:
   ```yaml
   image: <YOUR_ECR_IMAGE>
   ```

2. Apply the configuration:
   ```bash
   kubectl apply -f staging-deployment.yml
   ```

## Configuration

Configure the application through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Ollama service host | `localhost` |
| `OLLAMA_PORT` | Ollama service port | `11434` |
| `MODEL_NAME` | Model to use for code review | `deepseek-coder-v2` |

## Setting Up Webhooks

1. Go to your Bitbucket repository settings
2. Navigate to Webhooks and add a new webhook
3. Set the URL to your deployed service endpoint `/review`
4. Select the "Pull Request Created" and "Pull Request Updated" triggers
5. Save the webhook configuration

## How It Works

1. Developer creates or updates a pull request on Bitbucket
2. Webhook triggers the AI Code Review service
3. Service fetches the PR changes from Bitbucket API
4. DeepSeek Coder analyzes the code changes
5. Service posts review comments back to the pull request
6. Developers review AI suggestions and make improvements

## Development

### Project Structure

```
├── app.py                  # Main Flask application
├── routes/                 # API route definitions
│   └── pr_review.py        # PR review endpoint
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
├── start.sh                # Startup script
└── staging-deployment.yml  # Kubernetes deployment config
```

### Adding New Features

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Implement your changes
3. Test locally using Docker
4. Submit a pull request

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
