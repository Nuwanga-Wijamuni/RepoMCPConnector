from git import Repo, GitCommandError, Object, NULL_TREE 
from ..schemas import CommitInfo, TreeItem, DiffStats, RepoMapItem
from datetime import datetime
from typing import Optional, List
import os
import re

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

def get_file_content_at_commit(
    repo_path: str, 
    file_path: str, 
    commit_hash: Optional[str] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None
) -> Optional[dict]:
    """
    Uses GitPython to get the content of a file at a specific commit.
    Supports slicing content by line numbers.
    """
    try:
        repo = Repo(repo_path)
        
        if commit_hash is None:
            commit = repo.head.commit
        else:
            commit = repo.commit(commit_hash)
        
        blob = commit.tree / file_path
        content_data = blob.data_stream.read()
        
        # Decode content
        decoded_content = content_data.decode('utf-8')
        
        # Handle Context Trimming (Line Slicing)
        if start_line is not None or end_line is not None:
            lines = decoded_content.splitlines()
            
            # Adjust 1-based start_line to 0-based index
            start_index = (start_line - 1) if (start_line and start_line > 0) else 0
            
            # end_line is inclusive for humans, so we slice up to it
            end_index = end_line if end_line else len(lines)
            
            # Slice and rejoin
            decoded_content = "\n".join(lines[start_index:end_index])

        return {
            "path": file_path,
            "content": decoded_content,
            "encoding": "utf-8",
            "commit_hash": commit.hexsha,
            "size_bytes": len(decoded_content.encode('utf-8')) # Return size of trimmed content
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
    except ValueError as e:
        print(f"Commit not found (likely due to shallow clone): {e}")
        return None

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
    except ValueError as e:
        print(f"Commit not found (likely due to shallow clone): {e}")
        return None

def get_diff_for_commit(repo_path: str, commit_hash: str) -> Optional[dict]:
    """
    Gets the diff (file changes) for a specific commit.
    """
    try:
        repo = Repo(repo_path)
        commit = repo.commit(commit_hash)
        
        if not commit.parents:
            parent = NULL_TREE 
            parent_hash = "0000000000000000000000000000000000000000"
        else:
            parent = commit.parents[0]
            parent_hash = parent.hexsha
            
        diffs = commit.diff(parent, create_patch=True)
        
        changes = []
        for d in diffs:
            lines_added = 0
            lines_deleted = 0
            
            if d.diff:
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
    except (GitCommandError, KeyError, AttributeError, ValueError) as e:
        print(f"Error getting commit diff: {e}")
        return None

def generate_repo_map(repo_path: str, commit_hash: Optional[str] = None) -> Optional[dict]:
    """
    Generates a high-level map of the repository (classes, functions) using Regex.
    """
    try:
        repo = Repo(repo_path)
        if commit_hash is None:
            commit = repo.head.commit
        else:
            commit = repo.commit(commit_hash)
            
        repo_map = []
        
        # Walk through the entire tree
        for blob in commit.tree.traverse():
            if blob.type != 'blob':
                continue
                
            # Only analyze code files (basic heuristic)
            if not blob.path.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.cs')):
                continue
            
            # Limit: Skip massive files to avoid timeout
            if blob.size > 100_000: 
                continue

            try:
                content = blob.data_stream.read().decode('utf-8')
                definitions = _extract_definitions(content, blob.path)
                
                if definitions:
                    repo_map.append(RepoMapItem(
                        file_path=blob.path,
                        definitions=definitions
                    ))
            except UnicodeDecodeError:
                continue # Skip binary or non-utf8 files
                
        return {
            "commit_hash": commit.hexsha,
            "map": repo_map
        }
    except (GitCommandError, ValueError) as e:
        print(f"Error generating repo map: {e}")
        return None

def _extract_definitions(content: str, file_path: str) -> List[str]:
    """
    Extracts class and function definitions using Regex.
    This is a simple heuristic, not a full AST parser.
    """
    defs = []
    
    # Python Patterns
    if file_path.endswith('.py'):
        # Match 'class MyClass:' or 'def my_func('
        matches = re.findall(r'^\s*(class\s+\w+|def\s+\w+)', content, re.MULTILINE)
        defs.extend(matches)
        
    # JS/TS Patterns
    elif file_path.endswith(('.js', '.ts', '.jsx', '.tsx')):
        # Match 'function myFunc', 'class MyClass', 'const myFunc = () =>'
        matches = re.findall(r'^\s*(function\s+\w+|class\s+\w+|const\s+\w+\s*=\s*(\(.*?\)|.*?)\s*=>)', content, re.MULTILINE)
        # Clean up JS arrow functions for cleaner output
        clean_matches = []
        for m in matches:
            if isinstance(m, tuple):
                m = m[0] # Take full match
            if '=>' in m:
                # simplify 'const foo = () =>' to 'const foo'
                m = m.split('=')[0].strip()
            clean_matches.append(m)
        defs.extend(clean_matches)
        
    return defs