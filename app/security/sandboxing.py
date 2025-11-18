import os
import logging
import shlex  # <--- CRITICAL SECURITY IMPORT

# We wrap the import in a try/except block so the server 
# doesn't crash immediately if docker is not installed (Phase 1/2 usage).
try:
    import docker
    from docker.errors import ContainerError, ImageNotFound, APIError
except ImportError:
    docker = None

# Configure logging
logger = logging.getLogger(__name__)

def get_docker_client():
    """
    Safely attempts to get the Docker client.
    """
    if not docker:
        raise ImportError("The 'docker' library is not installed. Please run 'pip install docker'.")
    
    try:
        client = docker.from_env()
        client.ping() # Test connection
        return client
    except Exception as e:
        logger.error(f"Could not connect to Docker: {e}")
        raise RuntimeError("Docker is not running or not accessible. Please start Docker Desktop.")

def run_sandboxed_bisect(repo_path: str, test_command: str, bad_commit: str, good_commit: str) -> dict:
    """
    Runs a 'git bisect' operation inside a secure Docker container.
    
    Args:
        repo_path: Absolute path to the host's repository.
        test_command: The shell command to test each commit (e.g., 'npm test').
        bad_commit: The hash of the known bad commit.
        good_commit: The hash of the known good commit.
        
    Returns:
        A dict containing the result of the bisect operation.
    """
    client = get_docker_client()
    
    # 1. Define the Docker image to use. 
    # Using a lightweight image that has git installed.
    image_name = "bitnami/git:latest" 
    
    # --- SECURITY FIX ---
    # We strictly quote the user-provided command to prevent shell injection.
    # This prevents a command like "; rm -rf /" from running.
    safe_test_command = shlex.quote(test_command)
    
    # 2. Prepare the script to run INSIDE the container.
    # We use an f-string to inject the commit hashes and test command.
    bisect_script = f"""
    git config --global --add safe.directory /app
    cd /app
    
    # Reset any potential mess
    git bisect reset || true
    
    # Start bisect
    git bisect start
    git bisect bad {bad_commit}
    git bisect good {good_commit}
    
    # Run the automated bisect using the SAFE, QUOTED command
    git bisect run /bin/sh -c {safe_test_command}
    """
    
    container = None
    try:
        # 3. Pull the image if needed
        try:
            client.images.get(image_name)
        except ImageNotFound:
            logger.info(f"Pulling Docker image: {image_name}...")
            client.images.pull(image_name)

        # 4. Run the container
        logger.info(f"Starting sandbox for repo: {repo_path}")
        
        container = client.containers.run(
            image_name,
            # We wrap the entire script in single quotes for the outer shell
            # This is the second layer of security.
            command=f"/bin/sh -c {shlex.quote(bisect_script)}",
            volumes={repo_path: {'bind': '/app', 'mode': 'rw'}}, 
            working_dir="/app",
            detach=True, 
            # Security hardening:
            network_disabled=True, 
            mem_limit='512m',      
            cpu_period=100000,     
            cpu_quota=50000,
        )
        
        # 5. Wait for result (timeout after 5 minutes)
        result = container.wait(timeout=300)
        logs = container.logs().decode('utf-8')
        
        exit_code = result.get('StatusCode', 1)
        
        return {
            "success": exit_code == 0,
            "exit_code": exit_code,
            "logs": logs,
            "found_commit": _parse_bisect_result(logs)
        }

    except Exception as e:
        logger.error(f"Sandboxing error: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        # 6. Cleanup: Always remove the container
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass

def _parse_bisect_result(logs: str) -> str:
    """
    Helper to extract the bad commit hash from git bisect output.
    """
    import re
    # Look for standard git output: "123456... is the first bad commit"
    match = re.search(r'([a-f0-9]+) is the first bad commit', logs)
    if match:
        return match.group(1)
    return "Not found"