from git import Repo, GitCommandError, Object, NULL_TREE # <--- Added NULL_TREE
from ..schemas import CommitInfo, TreeItem, DiffStats
from datetime import datetime
from typing import Optional
import os

def get_history_for_file(repo_path: str, file_path: str) -> list[CommitInfo]:
    """
    Uses GitPython to get the commit history for a specific file.
    """
    try:
        repo = Repo(repo_path)
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
        print(f"GitCommandError: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []

def get_file_content_at_commit(repo_path: str, file_path: str, commit_hash: Optional[str] = None) -> Optional[dict]:
    """
    Uses GitPython to get the content of a file at a specific commit.
    """
    try:
        repo = Repo(repo_path)
        
        if commit_hash is None:
            commit = repo.head.commit
        else:
            commit = repo.commit(commit_hash)
        
        blob = commit.tree / file_path
        content_data = blob.data_stream.read()
        
        return {
            "path": file_path,
            "content": content_data.decode('utf-8'),
            "encoding": "utf-8",
            "commit_hash": commit.hexsha,
            "size_bytes": blob.size
        }
    except (GitCommandError, KeyError, AttributeError) as e:
        print(f"Error getting file content: {e}")
        return None
    except UnicodeDecodeError:
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
    """
    try:
        repo = Repo(repo_path)
        
        if commit_hash is None:
            commit = repo.head.commit
        else:
            commit = repo.commit(commit_hash)
        
        if path:
            tree_obj = commit.tree / path
        else:
            tree_obj = commit.tree
            
        tree_items = []
        for item in tree_obj.trees:
            tree_items.append(TreeItem(
                path=item.path,
                type="tree",
                size=item.size,
                mode=f"{item.mode:o}"
            ))
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
        print(f"Error getting tree structure: {e}")
        return None

def get_diff_for_commit(repo_path: str, commit_hash: str) -> Optional[dict]:
    """
    Gets the diff (file changes) for a specific commit.
    """
    try:
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)
        
        # --- LOGIC FIX: Handle initial commit ---
        if not commit.parents:
            # Compare against the special empty tree so we see all files as "added"
            parent = NULL_TREE 
            parent_hash = "0000000000000000000000000000000000000000"
        else:
            parent = commit.parents[0]
            parent_hash = parent.hexsha
            
        # Use create_patch=True to ensure we can parse diff text for stats
        diffs = commit.diff(parent, create_patch=True)
        
        changes = []
        for d in diffs:
            lines_added = 0
            lines_deleted = 0
            
            # Manually parse the diff text for accurate stats
            if d.diff:
                # GitPython returns diff as bytes
                diff_text = d.diff.decode('utf-8', errors='replace')
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