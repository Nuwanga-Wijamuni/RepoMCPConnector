# Use the same base image as the API to ensure consistency
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies
# We need 'git' for the repo manager logic
# We strictly do NOT need the docker binary here, because the Python 'docker'
# library talks directly to the socket mounted from the host.
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first (caching layer)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Create a non-root user for security (optional but recommended)
# For simplicity in this setup, we run as root to ensure easy access to the
# mounted /var/run/docker.sock, but in high-security envs you'd configure groups.

# Command to start the Celery worker
# -A app.tasks.celery_app: Points to our Celery instance
# worker: The command to start processing tasks
# --loglevel=info: Shows us what's happening in the logs
CMD ["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info"]