import os
import logging
from dotenv import load_dotenv

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """Loads configuration from environment variables."""
    load_dotenv()  # Load environment variables from .env file

    config = {
        "github_token": os.getenv("GITHUB_TOKEN"),
        "notion_token": os.getenv("NOTION_TOKEN"),
        "notion_database_id": os.getenv("NOTION_DATABASE_ID")
    }

    # Validate that all required config values are present
    missing_configs = [key for key, value in config.items() if value is None]
    if missing_configs:
        logger.error(f"Missing required configuration keys: {', '.join(missing_configs)}")
        raise ValueError(f"Missing required configuration keys: {', '.join(missing_configs)}. Please check your .env file.")

    logger.info("Configuration loaded successfully.")
    return config

if __name__ == '__main__':
    # Example of how to use the function
    try:
        app_config = load_config()
        print("Loaded configuration:")
        # Never print tokens in production code, this is just for demonstration
        # print(f"  GitHub Token: {app_config['github_token']}")
        # print(f"  Notion Token: {app_config['notion_token']}")
        print(f"  Notion DB ID: {app_config['notion_database_id']}")
        print("Note: Tokens are hidden for security.")
    except ValueError as e:
        print(f"Error loading configuration: {e}") 