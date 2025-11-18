from celery import Celery
from ..core.config import settings

# Initialize the Celery application
# 'git_mcp_worker' is the name of the worker instance
# broker=settings.REDIS_URL tells Celery where to send/receive messages
# backend=settings.REDIS_URL tells Celery where to store the results of tasks
celery_app = Celery(
    "git_mcp_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['app.tasks.git_tasks'] # Automatically load tasks from this module
)

# Configure Celery to use JSON for serialization (secure and standard)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],  # Ignore other content formats
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Optional: Task soft time limit (raises exception if task takes too long)
    task_soft_time_limit=600, # 10 minutes
    # Optional: Task hard time limit (kills worker if task takes too long)
    task_time_limit=660,      # 11 minutes
)

if __name__ == "__main__":
    celery_app.start()
