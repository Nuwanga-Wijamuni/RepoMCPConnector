from git import Repo, GitCommandError, Object
from ..schemas import CommitInfo, TreeItem, DiffStats
from datetime import datetime
import os

def get_history_for_file(repo_path: str, file_path: str) -> list[CommitInfo]:
    """
    Uses GitPython to get the commit history for a specific file.
    
    Args:
        repo_path: The absolute path to the Git repository.
        file_path: The relative path to the file *within* the repo.
    
    Returns:
        A list of CommitInfo objects, or an empty list if file not found.
    """
    try:
        repo = Repo(repo_path)
        
        # `iter_commits` can take a path to filter by
        # We must use the relative path for this command.
        commits = list(repo.iter_commits(paths=file_path))
        
        history = []
        for c in commits:
            history.append(
                CommitInfo(
                    hash=c.hexsha,
                    author_name=str(c.author.name),
                    author_email=str(c.author.email),
                    date=c.committed_datetime,
                    message=c.message.strip()
                )
            )
        return history
    except GitCommandError as e:
        # This can happen if the file path is valid but not in Git, etc.
        print(f"GitCommandError: {e}")
        return []
    except Exception as e:
        # Catch other potential errors (e.g., repo is corrupted)
        print(f"An unexpected error occurred: {e}")
        return []

def get_file_content_at_commit(repo_path: str, file_path: str, commit_hash: Optional[str] = None) -> Optional[dict]:
    """
    Uses GitPython to get the content of a file at a specific commit.
    
    Args:
        repo_path: The absolute path to the Git repository.
        file_path: The relative path to the file *within* the repo.
        commit_hash: The commit to get. Defaults to HEAD.
    
    Returns:
        A dict with content and metadata, or None if not found.
    """
    try:
        repo = Repo(repo_path)
        
        if commit_hash is None:
            commit = repo.head.commit
        else:
            commit = repo.commit(commit_hash)
        
        # Get the blob (file data) from the commit's tree
        # The '/' operator traverses the tree
        blob = commit.tree / file_path
        
        # Read the data and decode it
        content_data = blob.data_stream.read()
        
        return {
            "path": file_path,
            "content": content_data.decode('utf-8'),
            "encoding": "utf-8",
            "commit_hash": commit.hexsha,
            "size_bytes": blob.size
        }
    except (GitCommandError, KeyError, AttributeError) as e:
        # KeyError or AttributeError if file_path doesn't exist in the tree
        print(f"Error getting file content: {e}")
        return None
    except UnicodeDecodeError:
        # Handle binary files gracefully
        return {
            "path": file_path,
            "content": "[Binary file, content not displayable]",
            "encoding": "binary",
            "commit_hash": commit.hexsha,
            "size_bytes": blob.size
        }

def get_tree_at_commit(repo_path: str, path: Optional[str] = None, commit_hash: Optional[str] = None) -> Optional[dict]:
    """
    Uses GitPython to get the file/directory tree at a specific commit.
    
    Args:
        repo_path: The absolute path to the Git repository.
        path: The subdirectory path to list. Defaults to root.
        commit_hash: The commit to get. Defaults to HEAD.
    
    Returns:
        A dict with tree info, or None if not found.
    """
    try:
        repo = Repo(repo_path)
        
        if commit_hash is None:
            commit = repo.head.commit
        else:
            commit = repo.commit(commit_hash)
        
        if path:
            # Get the tree object for the subdirectory
            tree_obj = commit.tree / path
        else:
            # Get the root tree
            tree_obj = commit.tree
            
        tree_items = []
        # List items in this tree (directories)
        for item in tree_obj.trees:
            tree_items.append(TreeItem(
                path=item.path,
                type="tree",
                size=item.size,
                mode=f"{item.mode:o}" # Format mode as octal string
            ))
        # List items in this tree (files)
        for item in tree_obj.blobs:
             tree_items.append(TreeItem(
                path=item.path,
                type="blob",
                size=item.size,
                mode=f"{item.mode:o}"
            ))
            
        return {
            "commit_hash": commit.hexsha,
            "path": path if path else "/",
            "tree": tree_items
        }
    except (GitCommandError, KeyError, AttributeError) as e:
        # KeyError or AttributeError if path doesn't exist
        print(f"Error getting tree structure: {e}")
        return None

def get_diff_for_commit(repo_path: str, commit_hash: str) -> Optional[dict]:
    """
    Gets the diff (file changes) for a specific commit.
    Compares the commit to its first parent.
    
    Args:
        repo_path: The absolute path to the Git repository.
        commit_hash: The commit to analyze.
        
    Returns:
        A dict with diff stats, or None if not found.
    """
    try:
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)
        
        # Make sure the commit has a parent
        if not commit.parents:
            # This is the initial commit, can't diff against a parent
            # We can diff against an empty tree instead
            parent = repo.tree() # Empty tree
            parent_hash = "0000000" # Conventional hash for empty tree
        else:
            parent = commit.parents[0]
            parent_hash = parent.hexsha
            
        # Get the diff, but don't generate the text patch (create_patch=False)
        # This is much faster and gives us the stats we need
        diff = commit.diff(parent, create_patch=False)
        
        changes = []
        for d in diff:
            # We use d.stats, which requires a full diff, so we must not use create_patch=False
            # Let's re-run the diff with stats enabled
            pass # The diff object from commit.diff() should contain stats
        
        # Re-running diff to get stats
        diff_with_stats = commit.diff(parent, create_patch=True)
        changes = []
        
        for d in diff_with_stats:
            # The `d.diff` property holds the text patch. We can parse stats from it
            # or use a different approach. `d.stats` is not a direct attribute.
            # A more robust way:
            lines_added = 0
            lines_deleted = 0
            
            if d.diff:
                diff_text = d.diff.decode('utf-8')
                for line in diff_text.splitlines():
                    if line.startswith('+') and not line.startswith('+++'):
                        lines_added += 1
                    elif line.startswith('-') and not line.startswith('---'):
                        lines_deleted += 1

            stats = DiffStats(
                file_path=d.a_path if d.a_path else d.b_path,
                lines_added=lines_added,
                lines_deleted=lines_deleted,
                is_new=d.new_file,
                is_deleted=d.deleted_file,
                is_renamed=d.renamed_file,
                rename_from=d.rename_from,
                rename_to=d.rename_to
            )
            changes.append(stats)
            
        return {
            "commit_hash": commit.hexsha,
            "parent_hash": parent_hash,
            "changes": changes
        }
    except (GitCommandError, KeyError, AttributeError) as e:
        print(f"Error getting commit diff: {e}")
        return None


# --- (Phase 1) /get_authorship ---
# def get_authorship_for_line(...):
#     ... (To be implemented) ...

# --- (Phase 3) /find_bug_introducing_commit ---
# ... (To be implemented in app/tasks/git_tasks.py) ..