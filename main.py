import logging
import sys

from config import load_config, logger # Use the logger from config
from github_client import GitHubClient
from notion_client import NotionClient
from sync_logic import run_sync

def main():
    logger.info("Script started.")

    # Load configuration
    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1) # Exit if config is invalid
    except Exception as e:
        logger.exception(f"An unexpected error occurred during configuration loading: {e}")
        sys.exit(1)

    # Initialize clients
    try:
        github_client = GitHubClient(token=config['github_token'])
        notion_client = NotionClient(
            token=config['notion_token'],
            database_id=config['notion_database_id']
        )
    except ValueError as e:
        logger.error(f"Error initializing clients: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred during client initialization: {e}")
        sys.exit(1)

    # Run the synchronization process
    try:
        run_sync(github_client, notion_client)
    except Exception as e:
        # Catch any unexpected errors from the sync logic itself
        logger.exception(f"An unexpected error occurred during synchronization: {e}")
        sys.exit(1)

    logger.info("Script finished successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main() 