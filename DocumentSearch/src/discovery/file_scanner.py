"""
File Scanner - Recursive directory traversal with filtering
"""

import os
from pathlib import Path
from typing import Iterator, Dict, Any
from fnmatch import fnmatch
from datetime import datetime

from core.logging_manager import get_logger
from core.config_manager import get_config

logger = get_logger("discovery.scanner")


class FileScanner:
    """Scans directories recursively and yields file metadata"""
    
    def __init__(self):
        self.config = get_config()
        self.exclude_patterns = self.config.discovery.exclude_patterns
        self.filter_by_extension = self.config.discovery.filter_by_extension
        self.excluded_extensions = self.config.discovery.excluded_extensions
        self.included_extensions = self.config.discovery.included_extensions
        
        # Priority folder configuration
        self.priority_folders = self.config.discovery.priority_folders
        
        # Statistics
        self.files_scanned = 0
        self.files_skipped = 0
        self.errors = 0
    
    def scan(self, root_path: str) -> Iterator[Dict[str, Any]]:
        """
        Recursively scan directory and yield file metadata
        
        Args:
            root_path: Root directory to scan
            
        Yields:
            Dictionary with file metadata
        """
        root = Path(root_path)
        
        if not root.exists():
            logger.error(f"Root path does not exist: {root_path}")
            return
        
        logger.info(f"Starting scan of {root_path}")
        
        try:
            for entry in self._walk_directory(root):
                if self._should_process_file(entry):
                    try:
                        metadata = self._get_file_metadata(entry)
                        self.files_scanned += 1
                        
                        if self.files_scanned % 10000 == 0:
                            logger.info(f"Scanned {self.files_scanned:,} files "
                                      f"(skipped: {self.files_skipped:,}, errors: {self.errors})")
                        
                        yield metadata
                        
                    except Exception as e:
                        self.errors += 1
                        logger.warning(f"Error processing file {entry.path}: {e}")
                else:
                    self.files_skipped += 1
                    
        except Exception as e:
            logger.error(f"Error scanning directory {root_path}: {e}")
    
    def _walk_directory(self, root: Path) -> Iterator[os.DirEntry]:
        """Walk directory tree, respecting exclude patterns"""
        try:
            with os.scandir(root) as iterator:
                for entry in iterator:
                    # Check if should exclude this entry
                    if self._should_exclude(entry):
                        continue

                    if entry.is_file(follow_symlinks=False):
                        yield entry
                    elif entry.is_dir(follow_symlinks=False):
                        # Recursively scan subdirectory
                        yield from self._walk_directory(Path(entry.path))
                    
        except PermissionError:
            logger.warning(f"Permission denied: {root}")
        except Exception as e:
            logger.error(f"Error walking directory {root}: {e}")
    
    def _should_exclude(self, entry: os.DirEntry) -> bool:
        """Check if path matches any exclude pattern"""
        path_str = entry.path
        name = entry.name
        
        for pattern in self.exclude_patterns:
            if fnmatch(name, pattern) or fnmatch(path_str, pattern):
                return True
        
        return False
    
    def _should_process_file(self, entry: os.DirEntry) -> bool:
        """Determine if file should be processed based on extension filtering"""
        if not self.filter_by_extension:
            # Process all files except explicitly excluded
            _, ext = os.path.splitext(entry.name)
            ext = ext.lower()
            return ext not in self.excluded_extensions
        
        _, ext = os.path.splitext(entry.name)
        ext = ext.lower()
        
        # If included_extensions is specified, only process those
        if self.included_extensions:
            return ext in self.included_extensions
        
        # Otherwise, process everything except excluded
        return ext not in self.excluded_extensions
    
    def _get_file_metadata(self, entry: os.DirEntry) -> Dict[str, Any]:
        """Extract file metadata"""
        stat = entry.stat(follow_symlinks=False)
        file_path = entry.path
        file_name = entry.name
        _, extension = os.path.splitext(file_name)
        extension = extension.lower()
        
        metadata = {
            'file_path': file_path,
            'file_name': file_name,
            'file_size': stat.st_size,
            'modified_time': stat.st_mtime,
            'created_time': stat.st_ctime,
            'extension': extension,
            'priority': self._calculate_priority(file_path)
        }
        
        return metadata
    
    def _calculate_priority(self, file_path: str) -> int:
        """Calculate priority based on folder patterns"""
        if not self.priority_folders:
            return 5  # Default priority
        
        path_str = file_path.lower()
        
        for folder_config in self.priority_folders:
            pattern = folder_config.get('pattern', '').lower()
            if pattern and pattern in path_str:
                return folder_config.get('priority', 5)
        
        return 5  # Default priority
    
    def get_stats(self) -> Dict[str, int]:
        """Get scanning statistics"""
        return {
            'files_scanned': self.files_scanned,
            'files_skipped': self.files_skipped,
            'errors': self.errors
        }
