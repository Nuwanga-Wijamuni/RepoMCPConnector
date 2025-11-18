from fastapi import FastAPI, HTTPException
from . import schemas
from .core.config import settings
from .security import validation
from .git_logic import tools, repo_manager
import os

app = FastAPI(
    title="Git-Aware Semantic DevOps Server",
    description="A 'Generation 2' MCP server that provides structured, semantic answers about Git repositories.",
    version="0.2.0" # Updated to reflect new features
)

# --- Phase 1: Local Endpoints ---

@app.post("/local/get_file_history", 
          response_model=schemas.FileHistoryResponse,
          summary="(Phase 1) Get commit history for a local file",
          tags=["Local Tools"])
async def api_get_local_file_history(request: schemas.FileHistoryRequest):
    """
    Gets the full commit history for a single file in the pre-configured
    `LOCAL_REPO_PATH` repository.
    """
    repo_path = settings.LOCAL_REPO_PATH
    
    try:
        # 1. Security: Validate the user's file path
        safe_path = validation.validate_safe_path(repo_path, request.path)
        
        # 2. Get the relative path for the git command
        relative_path = os.path.relpath(safe_path, repo_path)
        
    except ValueError as e:
        # Raised by validate_safe_path on path traversal
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Run the core Git logic
    history = tools.get_history_for_file(repo_path, relative_path)
    
    if not history:
        raise HTTPException(
            status_code=404, 
            detail=f"File not found or no history for: {request.path}"
        )

    # 4. Return the structured JSON response
    return schemas.FileHistoryResponse(file=relative_path, commits=history)

@app.post("/local/get_file_content",
          response_model=schemas.FileContentResponse,
          summary="(Phase 1) Get file content from local repo",
          tags=["Local Tools"])
async def api_get_local_file_content(request: schemas.FileContentRequest):
    repo_path = settings.LOCAL_REPO_PATH
    try:
        safe_path = validation.validate_safe_path(repo_path, request.path)
        relative_path = os.path.relpath(safe_path, repo_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    content_data = tools.get_file_content_at_commit(repo_path, relative_path, request.commit_hash)
    
    if content_data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"File not found or commit invalid: {request.path}"
        )
    return schemas.FileContentResponse(**content_data)

@app.post("/local/get_tree_structure",
          response_model=schemas.TreeResponse,
          summary="(Phase 1) Get tree structure from local repo",
          tags=["Local Tools"])
async def api_get_local_tree(request: schemas.TreeRequest):
    repo_path = settings.LOCAL_REPO_PATH
    relative_path = None
    
    try:
        # Only validate if a sub-path is requested
        if request.path and request.path != "/":
            safe_path = validation.validate_safe_path(repo_path, request.path)
            relative_path = os.path.relpath(safe_path, repo_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tree_data = tools.get_tree_at_commit(repo_path, relative_path, request.commit_hash)
    
    if tree_data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Path or commit not found: {request.path or '/'}"
        )
    return schemas.TreeResponse(**tree_data)

@app.post("/local/get_commit_diff",
          response_model=schemas.CommitDiffResponse,
          summary="(Phase 1) Get commit diff from local repo",
          tags=["Local Tools"])
async def api_get_local_commit_diff(request: schemas.CommitDiffRequest):
    repo_path = settings.LOCAL_REPO_PATH
    
    diff_data = tools.get_diff_for_commit(repo_path, request.commit_hash)
    
    if diff_data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Commit not found: {request.commit_hash}"
        )
    return schemas.CommitDiffResponse(**diff_data)


# --- Phase 2: Public Endpoints ---

@app.post("/public/get_file_history",
          response_model=schemas.FileHistoryResponse,
          summary="(Phase 2) Get commit history for a public file",
          tags=["Public Tools"])
async def api_get_public_file_history(request: schemas.PublicFileHistoryRequest):
    """
    Gets the full commit history for a file from *any* public Git repository.
    The server will clone or fetch the repo on demand.
    """
    try:
        # 1. Security: Validate URL and clone/fetch the repo
        repo_path = repo_manager.get_repo(request.repo_url)
        
        # 2. Security: Validate the user's file path
        safe_path = validation.validate_safe_path(repo_path, request.path)
        relative_path = os.path.relpath(safe_path, repo_path)

    except (ValueError, RuntimeError) as e:
        # Catches unsafe URLs, path traversal, or clone/fetch failures
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Run the core Git logic
    history = tools.get_history_for_file(repo_path, relative_path)
    
    if not history:
        raise HTTPException(
            status_code=404, 
            detail=f"File not found or no history for: {request.path} in {request.repo_url}"
        )

    # 4. Return the structured JSON response
    return schemas.FileHistoryResponse(file=relative_path, commits=history)

@app.post("/public/get_file_content",
          response_model=schemas.FileContentResponse,
          summary="(Phase 2) Get file content from public repo",
          tags=["Public Tools"])
async def api_get_public_file_content(request: schemas.PublicFileContentRequest):
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

@app.post("/public/get_tree_structure",
          response_model=schemas.TreeResponse,
          summary="(Phase 2) Get tree structure from public repo",
          tags=["Public Tools"])
async def api_get_public_tree(request: schemas.PublicTreeRequest):
    try:
        repo_path = repo_manager.get_repo(request.repo_url)
        relative_path = None
        if request.path and request.path != "/":
            safe_path = validation.validate_safe_path(repo_path, request.path)
            relative_path = os.path.relpath(safe_path, repo_path)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    tree_data = tools.get_tree_at_commit(repo_path, relative_path, request.commit_hash)
    
    if tree_data is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Path or commit not found: {request.path or '/'}"
        )
    return schemas.TreeResponse(**tree_data)

@app.post("/public/get_commit_diff",
          response_model=schemas.CommitDiffResponse,
          summary="(Phase 2) Get commit diff from public repo",
          tags=["Public Tools"])
async def api_get_public_commit_diff(request: schemas.PublicCommitDiffRequest):
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


# --- Phase 3: Async Endpoints (Placeholders) ---

# @app.post("/public/find_bug_introducing_commit", tags=["Public Tools (Async)"])
# async def api_find_bug_commit(...):
#     # (Phase 3) To be implemented
#     # This will call a celery task:
#     # task = git_tasks.run_bisect.delay(...)
#     # return {"job_id": task.id, "status": "PENDING"}
#     pass

# @app.get("/jobs/status/{job_id}", tags=["Public Tools (Async)"])
# async def api_get_job_status(job_id: str):
#     # (Phase 3) To be implemented
#     # This will check the status of the Celery task
#     # task = git_tasks.run_bisect.AsyncResult(job_id)
#     # return {"status": task.status, "result": task.result}
#     pass


@app.get("/", summary="Server Health Check", tags=["Health"])
def read_root():
    """
    A simple health check endpoint to confirm the server is running.
    """
    return {"status": "ok", "message": "Git-Aware Semantic DevOps Server is running."}