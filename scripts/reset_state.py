"""
Reset State Script - Clear all pipeline data for clean re-indexing
Deletes queue DB, clears working directories, and optionally wipes OpenSearch index
"""

import argparse
import shutil
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.config_manager import get_config
from core.logging_manager import get_logger
import requests

logger = get_logger("reset_state")


def confirm_action(message: str) -> bool:
    """Prompt user for confirmation"""
    response = input(f"{message} (y/N): ").strip().lower()
    return response == 'y'


def delete_directory(path: Path, name: str) -> None:
    """Delete directory and recreate it"""
    try:
        if path.exists():
            logger.info(f"Deleting {name}: {path}")
            shutil.rmtree(path, ignore_errors=True)
            logger.info(f"  ✓ Deleted {name}")
        
        logger.info(f"Recreating {name}: {path}")
        path.mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✓ Created {name}")
        
    except Exception as e:
        logger.error(f"  ✗ Error with {name}: {e}")


def delete_queue_db(config) -> None:
    """Delete the queue database file"""
    queue_db_path = Path(config.paths.queue_db) / "queues.db"
    
    try:
        if queue_db_path.exists():
            logger.info(f"Deleting queue database: {queue_db_path}")
            queue_db_path.unlink()
            logger.info("  ✓ Queue database deleted")
        else:
            logger.info("  ℹ Queue database not found (already clean)")
            
    except Exception as e:
        logger.error(f"  ✗ Error deleting queue database: {e}")


def delete_opensearch_index(config) -> None:
    """Delete the OpenSearch index"""
    index_name = config.indexing.opensearch.index_name
    hosts = config.indexing.opensearch.hosts
    
    for host in hosts:
        try:
            url = f"{host}/{index_name}"
            logger.info(f"Deleting OpenSearch index '{index_name}' at {host}")
            
            response = requests.delete(url, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"  ✓ Index '{index_name}' deleted successfully")
            elif response.status_code == 404:
                logger.info(f"  ℹ Index '{index_name}' not found (already clean)")
            else:
                logger.warning(f"  ⚠ Unexpected response: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"  ✗ Error deleting index: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Reset Document Search System state for clean re-indexing"
    )
    parser.add_argument(
        "--delete-index",
        action="store_true",
        help="Also delete the OpenSearch index (default: keep index)"
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompts"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("DOCUMENT SEARCH SYSTEM - RESET STATE")
    logger.info("=" * 80)
    
    # Load config
    try:
        config = get_config()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1
    
    # Show what will be deleted
    logger.info("\nThe following will be reset:")
    logger.info(f"  • Queue database: {Path(config.paths.queue_db) / 'queues.db'}")
    logger.info(f"  • Temp directory: {config.paths.temp_dir}")
    logger.info(f"  • Logs directory: {config.paths.logs_dir}")
    logger.info(f"  • Checkpoints directory: {config.paths.checkpoints_dir}")
    
    if args.delete_index:
        logger.info(f"  • OpenSearch index: {config.indexing.opensearch.index_name}")
    else:
        logger.info("  • OpenSearch index: KEPT (use --delete-index to remove)")
    
    # Confirm
    if not args.yes:
        logger.info("\n⚠️  WARNING: This will delete all processing state and cannot be undone!")
        if not confirm_action("\nProceed with reset?"):
            logger.info("Reset cancelled by user")
            return 0
    
    logger.info("\n" + "=" * 80)
    logger.info("Starting reset...")
    logger.info("=" * 80 + "\n")
    
    # 1. Delete queue database
    delete_queue_db(config)
    
    # 2. Clear temp directory
    delete_directory(Path(config.paths.temp_dir), "temp directory")
    
    # 3. Clear logs directory
    delete_directory(Path(config.paths.logs_dir), "logs directory")
    
    # 4. Clear checkpoints directory
    delete_directory(Path(config.paths.checkpoints_dir), "checkpoints directory")
    
    # 5. Optionally delete OpenSearch index
    if args.delete_index:
        delete_opensearch_index(config)
    
    logger.info("\n" + "=" * 80)
    logger.info("Reset complete!")
    logger.info("=" * 80)
    logger.info("\nYou can now start the orchestrator for a fresh indexing run.")
    logger.info("All metrics will start from zero.\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
