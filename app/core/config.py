from pydantic_settings import BaseSettings, SettingsConfigDict # <--- Corrected import
import os

class Settings(BaseSettings):
    """
    Loads all configuration settings from environment variables (.env file).
    
    This class uses pydantic-settings to automatically find and load
    variables from a file named ".env" in the root directory.
    """
    
    # (Phase 1) Path to the local repository for /local endpoints
    LOCAL_REPO_PATH: str = "default/path/to/repo" 

    # (Phase 2) Base directory for cloning public repositories
    CLONE_DIR: str = "/app/clones"

    # (Phase 3) Redis URL for Celery message broker
    REDIS_URL: str = "redis://redis:6379/0"

    # This line tells pydantic to load from a file named ".env"
    # and to not fail if it sees extra variables.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore") # <--- Corrected usage

# Create a single, global instance of the settings.
# Other files in our app (like main.py) will import this
# `settings` object to access the configuration.
settings = Settings()