from fastapi import FastAPI, HTTPException
from . import schemas
from .core.config import settings
from .security import validation
from .git_logic import tools, repo_manager
import os

app = FastAPI(
    title="Git-Aware Semantic DevOps Server",
    description="A 'Generation 2' MCP server that provides structured, semantic answers about any public Git repository.",
    version="0.3.0"
)

# --- Core Public Endpoints ---

@app.post("/public/get_tree_structure",
          response_model=schemas.TreeResponse,
          summary="Get file tree structure",
          description="Returns the full directory structure (files and folders) for the repository. Useful for mapping the project.",
          tags=["Repository Analysis"])
async def api_get_public_tree(request: schemas.PublicTreeRequest):
    """
    Input: repo_url, path (optional), commit_hash (optional)
    Output: JSON tree structure
    """
    try:
        # 1. Clone/Fetch Repo
        repo_path = repo_manager.get_repo(request.repo_url)
        
        # 2. Validate Sub-path (if provided)
        relative_path = None
        if request.path and request.path != "/":
            safe_path = validation.validate_safe_path(repo_path, request.path)
            relative_path = os.path.relpath(safe_path, repo_path)
            
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Get Tree Logic
    tree_data = tools.get_tree_at_commit(repo_path, relative_path, request.commit_hash)
    
    if tree_data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Path or commit not found: {request.path or '/'}"
        )
    return schemas.TreeResponse(**tree_data)


@app.post("/public/get_file_history",
          response_model=schemas.FileHistoryResponse,
          summary="Get commit history for a file",
          description="Returns a list of commits that modified a specific file. Includes author, date, and message.",
          tags=["Repository Analysis"])
async def api_get_public_file_history(request: schemas.PublicFileHistoryRequest):
    """
    Input: repo_url, path
    Output: List of commits for that file
    """
    try:
        repo_path = repo_manager.get_repo(request.repo_url)
        safe_path = validation.validate_safe_path(repo_path, request.path)
        relative_path = os.path.relpath(safe_path, repo_path)

    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    history = tools.get_history_for_file(repo_path, relative_path)
    
    if not history:
        raise HTTPException(
            status_code=404, 
            detail=f"File not found or no history for: {request.path}"
        )

    return schemas.FileHistoryResponse(file=relative_path, commits=history)


@app.post("/public/get_file_content",
          response_model=schemas.FileContentResponse,
          summary="Read file content",
          description="Returns the full text content of a file at a specific commit (or HEAD).",
          tags=["Repository Analysis"])
async def api_get_public_file_content(request: schemas.PublicFileContentRequest):
    """
    Input: repo_url, path, commit_hash (optional)
    Output: File content string
    """
    try:
        repo_path = repo_manager.get_repo(request.repo_url)
        safe_path = validation.validate_safe_path(repo_path, request.path)
        relative_path = os.path.relpath(safe_path, repo_path)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    content_data = tools.get_file_content_at_commit(repo_path, relative_path, request.commit_hash)
    
    if content_data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"File not found or commit invalid: {request.path}"
        )
    return schemas.FileContentResponse(**content_data)


@app.post("/public/get_commit_diff",
          response_model=schemas.CommitDiffResponse,
          summary="Get commit changes (Diff)",
          description="Returns a structured summary of changes (lines added/removed, files modified) for a specific commit hash.",
          tags=["Repository Analysis"])
async def api_get_public_commit_diff(request: schemas.PublicCommitDiffRequest):
    """
    Input: repo_url, commit_hash
    Output: Structured diff stats
    """
    try:
        repo_path = repo_manager.get_repo(request.repo_url)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    diff_data = tools.get_diff_for_commit(repo_path, request.commit_hash)
    
    if diff_data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Commit not found: {request.commit_hash}"
        )
    return schemas.CommitDiffResponse(**diff_data)


@app.get("/", summary="Server Health Check", tags=["Health"])
def read_root():
    """
    A simple health check endpoint to confirm the server is running.
    """
    return {"status": "ok", "message": "Git-Aware Semantic DevOps Server is running."}