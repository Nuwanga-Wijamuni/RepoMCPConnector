import os
import re
from urllib.parse import urlparse

def validate_safe_path(base_dir: str, user_path: str) -> str:
    """
    Resolves a user-provided path against a base directory
    and ensures it doesn't escape that directory (Path Traversal).
    
    This is a critical security function.
    
    Returns:
        The absolute, real path if it's safe.
    
    Raises:
        ValueError: If the path is unsafe.
    """
    # 1. Normalize both paths to resolve any '..' or '.'
    base_dir = os.path.realpath(base_dir)
    
    # 2. Create the full path by joining the base dir and the user-provided path
    # os.path.join handles path separators correctly, but user_path
    # could still be malicious (e.g., "../../etc/passwd")
    full_path_raw = os.path.join(base_dir, user_path)
    
    # 3. Resolve the full path, which will "execute" any '..'
    full_path_real = os.path.realpath(full_path_raw)
    
    # 4. Get the common prefix of the *resolved* base and full paths
    common_prefix = os.path.commonprefix([base_dir, full_path_real])

    # 5. Check if the common prefix is the base directory itself.
    # If it is, the full path is guaranteed to be inside the base_dir.
    # If the user tried '..', common_prefix would be C:\, not C:\projects\my-repo
    if common_prefix != base_dir:
        raise ValueError("Path Traversal Attack detected. Path is outside the repository.")
        
    return full_path_real

def is_safe_git_url(url: str) -> bool:
    """
    Validates that a URL is a safe, public HTTPS Git URL.
    This is a critical security function for Phase 2.
    """
    try:
        parsed = urlparse(url)
        
        # 1. Must be HTTPS. Deny SSH, FTP, File, etc.
        if parsed.scheme != 'https':
            return False
            
        # 2. Must have a network location (domain)
        if not parsed.netloc:
            return False
            
        # 3. Domain must be on our strict allow-list.
        # This prevents the server from cloning from a malicious domain.
        allowed_domains = {
            'github.com',
            'gitlab.com',
            'bitbucket.org'
        }
        
        if parsed.netloc not in allowed_domains:
            # Check for subdomains (e.g., gist.github.com)
            if not any(parsed.netloc.endswith(f'.{domain}') for domain in allowed_domains):
                return False

        # 4. Path should be a valid repo path (e.g., /user/repo.git)
        # This regex checks for a path like /username/reponame or /username/reponame.git
        # It disallows paths with tricky characters that might be used in attacks.
        if not re.match(r'^/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?/?$', parsed.path):
            return False
            
        # 5. Must not contain user, password, query params, or fragments
        if parsed.query or parsed.fragment or parsed.username or parsed.password:
            return False

    except Exception:
        # Any parsing error (e.g., malformed URL) means it's invalid
        return False
        
    # If all checks pass, the URL is safe
    return True