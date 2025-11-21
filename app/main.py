from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

from . import schemas
from .core.config import settings
from .security import validation
from .git_logic import tools, repo_manager
import os

# Define startup/shutdown logic to connect to Redis for Rate Limiting
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to Redis using the URL from config
    try:
        redis_connection = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_connection)
        yield
    except Exception as e:
        print(f"Warning: Redis connection for rate limiting failed: {e}")
        yield
    finally:
        # Cleanup logic if needed
        if 'redis_connection' in locals():
            await redis_connection.close()

app = FastAPI(
    title="Git-Aware Semantic DevOps Server",
    description="A 'Generation 2' MCP server that provides structured, semantic answers about any public Git repository.",
    version="0.3.2",
    lifespan=lifespan
)

# --- Core Public Endpoints ---

@app.post("/public/get_tree_structure",
          response_model=schemas.TreeResponse,
          summary="Get file tree structure",
          description="Returns the full directory structure (files and folders) for the repository. Useful for mapping the project.",
          tags=["Repository Analysis"],
          dependencies=[Depends(RateLimiter(times=10, seconds=60))])
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


@app.post("/public/get_file_history",
          response_model=schemas.FileHistoryResponse,
          summary="Get commit history for a file",
          description="Returns a list of commits that modified a specific file. Includes author, date, and message.",
          tags=["Repository Analysis"],
          dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def api_get_public_file_history(request: schemas.PublicFileHistoryRequest):
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
          description="Returns the full text content of a file at a specific commit (or HEAD). Supports slicing with start_line/end_line.",
          tags=["Repository Analysis"],
          dependencies=[Depends(RateLimiter(times=20, seconds=60))])
async def api_get_public_file_content(request: schemas.PublicFileContentRequest):
    try:
        repo_path = repo_manager.get_repo(request.repo_url)
        safe_path = validation.validate_safe_path(repo_path, request.path)
        relative_path = os.path.relpath(safe_path, repo_path)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    # Pass the new arguments (start_line, end_line) to the tool function
    content_data = tools.get_file_content_at_commit(
        repo_path, 
        relative_path, 
        request.commit_hash,
        request.start_line, 
        request.end_line
    )
    
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
          tags=["Repository Analysis"],
          dependencies=[Depends(RateLimiter(times=10, seconds=60))])
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

@app.post("/public/get_repo_map",
          response_model=schemas.RepoMapResponse,
          summary="Get repository map",
          description="Returns a compressed map of the codebase (classes, functions) to give the LLM high-level context.",
          tags=["Repository Analysis"],
          dependencies=[Depends(RateLimiter(times=5, seconds=60))]) # Heavy operation, lower limit
async def api_get_repo_map(request: schemas.RepoMapRequest):
    try:
        repo_path = repo_manager.get_repo(request.repo_url)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    repo_map = tools.generate_repo_map(repo_path, request.commit_hash)
    
    if repo_map is None:
        raise HTTPException(status_code=500, detail="Failed to generate repo map")
        
    return schemas.RepoMapResponse(**repo_map)


@app.get("/", summary="Server Health Check", tags=["Health"])
def read_root():
    return {"status": "ok", "message": "Git-Aware Semantic DevOps Server is running."}