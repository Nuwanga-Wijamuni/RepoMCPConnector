import os
import shutil
import hashlib
from git import Repo, GitCommandError
from ..core.config import settings
from ..security import validation

# Load the clone directory from the app settings
CLONE_DIR = settings.CLONE_DIR

# Ensure the clone directory exists on startup
if not os.path.exists(CLONE_DIR):
    try:
        os.makedirs(CLONE_DIR, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create CLONE_DIR at {CLONE_DIR}: {e}")

def get_repo(repo_url: str) -> str:
    """
    Clones or fetches a public repo and returns its local path.
    This is the core of the "public" (Phase 2) functionality.
    
    Args:
        repo_url: The public HTTPS URL of the git repository.
        
    Returns:
        The absolute local path to the cloned repository.
    """
    # 1. Validate that the URL is a safe, public HTTPS Git URL
    if not validation.is_safe_git_url(repo_url):
        raise ValueError("Invalid or unsafe Git repository URL. Only public HTTPS URLs from GitHub, GitLab, and Bitbucket are allowed.")
    
    # 2. Create a unique, safe directory name from the URL hash
    # This prevents directory traversal (e.g., ../../) and gives a stable path for caching.
    repo_hash = hashlib.md5(repo_url.encode()).hexdigest()
    repo_path = os.path.join(CLONE_DIR, repo_hash)
    
    # 3. Check if repo is already cloned and valid
    if os.path.exists(repo_path) and os.path.isdir(os.path.join(repo_path, '.git')):
        try:
            print(f"Fetching existing repo: {repo_url}")
            repo = Repo(repo_path)
            
            # Ensure the remote URL matches the request (handling potential hash collisions or URL updates)
            if repo.remotes.origin.url != repo_url:
                print(f"Updating remote URL for {repo_path}")
                repo.remotes.origin.set_url(repo_url)
            
            # Fetch latest changes
            repo.remotes.origin.fetch()
            
        except GitCommandError as e:
            print(f"Failed to fetch existing repo, attempting complete re-clone: {e}")
            # If fetch fails (e.g., repo history changed), delete and re-clone
            try:
                shutil.rmtree(repo_path)
            except OSError as cleanup_error:
                 raise RuntimeError(f"Failed to clean up corrupted repo at {repo_path}: {cleanup_error}")
            
            return _clone_repo(repo_url, repo_path)
            
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred during fetch: {e}")
    else:
        # Repo doesn't exist or is corrupted (missing .git), clone it
        if os.path.exists(repo_path):
            try:
                shutil.rmtree(repo_path)
            except OSError:
                pass # If we can't delete it, clone might fail below, which is caught
                
        return _clone_repo(repo_url, repo_path)
    
    return repo_path

def _clone_repo(repo_url: str, repo_path: str) -> str:
    """
    Internal helper function to perform the initial clone.
    """
    try:
        print(f"Cloning new repo: {repo_url} to {repo_path}")
        # We use a shallow clone (depth=50) to save disk space and time.
        # We can fetch more history later if needed.
        Repo.clone_from(repo_url, repo_path, depth=50)
        return repo_path
        
    except GitCommandError as e:
        # If clone fails, clean up the partial directory so we don't leave a mess
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
        raise RuntimeError(f"Failed to clone repo: {e}")
        
    except Exception as e:
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path, ignore_errors=True)
        raise RuntimeError(f"An unexpected error occurred during clone: {e}")