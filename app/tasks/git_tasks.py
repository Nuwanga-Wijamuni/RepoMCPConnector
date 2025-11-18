from .celery_app import celery_app
from ..git_logic import repo_manager
from ..security import sandboxing
import logging

# Configure a logger for this module to track task progress
logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def run_bisect_task(self, repo_url: str, test_command: str, bad_commit: str, good_commit: str):
    """
    Celery task to run a git bisect operation in a sandboxed environment.
    
    This task runs asynchronously. It:
    1. Ensures the repository is cloned/updated locally.
    2. Passes the local path and parameters to the Docker sandbox.
    3. Returns the result of the bisect.
    
    Args:
        self: The task instance (allows updating state).
        repo_url: Public URL of the git repo.
        test_command: The shell command to run (e.g., 'npm test').
        bad_commit: The known bad commit hash.
        good_commit: The known good commit hash.
    """
    try:
        logger.info(f"Starting bisect task for {repo_url}")
        
        # Step 1: Ensure we have the repository
        # This might take time if it's a fresh clone, which is why this is an async task.
        self.update_state(state='PROGRESS', meta={'status': 'Cloning/Fetching repository...'})
        repo_path = repo_manager.get_repo(repo_url)
        
        # Step 2: Run the secure sandbox
        self.update_state(state='PROGRESS', meta={'status': 'Running bisect in sandbox...'})
        
        # This function spins up the Docker container and waits for it to finish
        result = sandboxing.run_sandboxed_bisect(
            repo_path=repo_path,
            test_command=test_command,
            bad_commit=bad_commit,
            good_commit=good_commit
        )
        
        # Step 3: Return the result
        # If the sandbox returned success=True/False, we pass that along.
        if result['success']:
            return {
                "status": "completed",
                "bad_commit": result['found_commit'],
                "logs": result['logs']
            }
        else:
            return {
                "status": "failed",
                "error": "Bisect failed or timed out",
                "logs": result.get('logs', result.get('error', 'Unknown error'))
            }

    except Exception as e:
        logger.error(f"Task failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }