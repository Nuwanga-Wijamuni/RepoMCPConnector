from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any

# --- Reusable Components ---

class CommitInfo(BaseModel):
    """
    Structured information for a single Git commit.
    """
    hash: str
    author_name: str
    author_email: str
    date: datetime
    message: str

# --- Tool: /get_file_history ---

class FileHistoryRequest(BaseModel):
    """
    Input for the /local/get_file_history endpoint.
    """
    path: str = Field(..., description="Relative path to the file within the repository.")

class FileHistoryResponse(BaseModel):
    """
    Output for the /get_file_history endpoints.
    """
    file: str
    commits: list[CommitInfo]

class PublicFileHistoryRequest(FileHistoryRequest):
    """
    Input for the /public/get_file_history endpoint.
    """
    repo_url: str = Field(..., description="The public HTTPS URL of the Git repository.")

# --- Tool: /get_file_content ---

class FileContentRequest(BaseModel):
    path: str = Field(..., description="Relative path to the file within the repository.")
    commit_hash: Optional[str] = Field(None, description="Specific commit hash. Defaults to HEAD (latest).")

class PublicFileContentRequest(FileContentRequest):
    repo_url: str = Field(..., description="The public HTTPS URL of the Git repository.")

class FileContentResponse(BaseModel):
    path: str
    content: str
    encoding: str
    commit_hash: str
    size_bytes: int

# --- Tool: /get_tree_structure ---

class TreeRequest(BaseModel):
    commit_hash: Optional[str] = Field(None, description="Specific commit hash. Defaults to HEAD (latest).")
    path: Optional[str] = Field(None, description="Subdirectory to get tree for. Defaults to root.")

class PublicTreeRequest(TreeRequest):
    repo_url: str = Field(..., description="The public HTTPS URL of the Git repository.")

class TreeItem(BaseModel):
    path: str
    type: str  # 'blob' (file) or 'tree' (directory)
    size: int
    mode: str

class TreeResponse(BaseModel):
    commit_hash: str
    path: str
    tree: List[TreeItem]

# --- Tool: /get_commit_diff ---

class CommitDiffRequest(BaseModel):
    commit_hash: str = Field(..., description="The commit hash to get the diff for.")

class PublicCommitDiffRequest(CommitDiffRequest):
    repo_url: str = Field(..., description="The public HTTPS URL of the Git repository.")

class DiffStats(BaseModel):
    lines_added: int
    lines_deleted: int
    file_path: str
    is_new: bool
    is_deleted: bool
    is_renamed: bool
    rename_from: Optional[str] = None
    rename_to: Optional[str] = None

class CommitDiffResponse(BaseModel):
    commit_hash: str
    parent_hash: str
    changes: List[DiffStats]

# --- (Phase 1) /get_authorship ---
# ... (To be implemented) ...

# --- (Phase 3) /find_bug_introducing_commit ---
# ... (To be implemented) ...