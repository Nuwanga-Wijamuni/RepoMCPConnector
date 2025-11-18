# Use an official Python runtime as a parent image
# 3.11-slim is a lightweight version of Python
FROM python:3.11-slim

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files
# PYTHONUNBUFFERED: Ensures logs are streamed to the console immediately
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container to /app
WORKDIR /app

# Install system dependencies
# GitPython requires the actual 'git' binary to be installed in the OS
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker cache
# This way, we only re-install dependencies if requirements.txt changes
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose port 8000 to the outside world
EXPOSE 8000

# Command to run the application
# We listen on 0.0.0.0 to allow external access (required for Docker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]