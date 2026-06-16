"""
Enterprise Document Search System - Logging Manager
Production-grade structured logging with rotation and component separation
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
from datetime import datetime

from core.config_manager import get_config
from core.constants import LOG_MAX_BYTES, LOG_BACKUP_COUNT


class LoggerManager:
    """
    Centralized logging management for all system components
    Provides structured logging with rotation and component separation
    """
    
    _initialized = False
    _loggers = {}
    
    @classmethod
    def initialize(cls) -> None:
        """Initialize logging system"""
        if cls._initialized:
            return
        
        config = get_config()
        log_config = config.logging
        logs_dir = Path(config.paths.logs_dir)
        
        # Ensure logs directory exists
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_config.default_level))
        
        # Remove existing handlers
        root_logger.handlers.clear()
        
        # Create formatters
        if log_config.use_json:
            formatter = cls._create_json_formatter()
        else:
            formatter = logging.Formatter(
                fmt=log_config.format,
                datefmt=log_config.date_format
            )
        
        # Console handler (INFO and above)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Main application log file (all levels)
        main_log_path = logs_dir / "application.log"
        main_handler = RotatingFileHandler(
            main_log_path,
            maxBytes=log_config.rotation['max_bytes'],
            backupCount=log_config.rotation['backup_count'],
            encoding='utf-8'
        )
        main_handler.setLevel(getattr(logging, log_config.default_level))
        main_handler.setFormatter(formatter)
        root_logger.addHandler(main_handler)
        
        # Error log file (errors and critical only)
        error_log_path = logs_dir / "errors.log"
        error_handler = RotatingFileHandler(
            error_log_path,
            maxBytes=log_config.rotation['max_bytes'],
            backupCount=log_config.rotation['backup_count'],
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
        
        cls._initialized = True
        
        root_logger.info("="*80)
        root_logger.info(f"Logging system initialized - {datetime.now().isoformat()}")
        root_logger.info(f"Log directory: {logs_dir}")
        root_logger.info(f"Log level: {log_config.default_level}")
        root_logger.info("="*80)
    
    @classmethod
    def _create_json_formatter(cls):
        """Create JSON formatter for structured logging"""
        try:
            import json_log_formatter
            return json_log_formatter.JSONFormatter()
        except ImportError:
            # Fallback to standard formatter if json_log_formatter not available
            logging.warning("json_log_formatter not installed, using standard formatter")
            config = get_config()
            return logging.Formatter(
                fmt=config.logging.format,
                datefmt=config.logging.date_format
            )
    
    @classmethod
    def get_logger(cls, component: str) -> logging.Logger:
        """
        Get logger for specific component
        
        Args:
            component: Component name (discovery, extraction, indexing, ocr, etc.)
        
        Returns:
            Configured logger for the component
        """
        if not cls._initialized:
            cls.initialize()
        
        if component in cls._loggers:
            return cls._loggers[component]
        
        config = get_config()
        log_config = config.logging
        logs_dir = Path(config.paths.logs_dir)
        
        # Create component-specific logger
        logger = logging.getLogger(component)
        
        # Set component-specific level if configured
        if component in log_config.components:
            level = log_config.components[component]
            logger.setLevel(getattr(logging, level))
        else:
            logger.setLevel(getattr(logging, log_config.default_level))
        
        # Component-specific log file
        component_log_path = logs_dir / f"{component}.log"
        
        formatter = logging.Formatter(
            fmt=log_config.format,
            datefmt=log_config.date_format
        )
        
        # Try to create handler with primary logs directory
        # If that fails (permission error), fallback to temp directory
        try:
            component_handler = RotatingFileHandler(
                component_log_path,
                maxBytes=log_config.rotation['max_bytes'],
                backupCount=log_config.rotation['backup_count'],
                encoding='utf-8'
            )
        except PermissionError:
            # Fallback to temp directory if primary logs directory is inaccessible
            import tempfile
            temp_logs_dir = Path(tempfile.gettempdir()) / "docsearch_logs"
            temp_logs_dir.mkdir(parents=True, exist_ok=True)
            fallback_log_path = temp_logs_dir / f"{component}.log"
            print(f"Warning: Cannot write to {component_log_path}, using fallback: {fallback_log_path}", file=sys.stderr)
            component_handler = RotatingFileHandler(
                fallback_log_path,
                maxBytes=log_config.rotation['max_bytes'],
                backupCount=log_config.rotation['backup_count'],
                encoding='utf-8'
            )
        
        component_handler.setFormatter(formatter)
        logger.addHandler(component_handler)
        
        # Prevent propagation to avoid duplicate log entries
        logger.propagate = True
        
        cls._loggers[component] = logger
        
        return logger
    
    @classmethod
    def get_discovery_logger(cls) -> logging.Logger:
        """Get logger for discovery workers"""
        return cls.get_logger("discovery")
    
    @classmethod
    def get_extraction_logger(cls) -> logging.Logger:
        """Get logger for extraction workers"""
        return cls.get_logger("extraction")
    
    @classmethod
    def get_indexing_logger(cls) -> logging.Logger:
        """Get logger for indexing workers"""
        return cls.get_logger("indexing")
    
    @classmethod
    def get_ocr_logger(cls) -> logging.Logger:
        """Get logger for OCR workers"""
        return cls.get_logger("ocr")
    
    @classmethod
    def get_orchestrator_logger(cls) -> logging.Logger:
        """Get logger for orchestrator"""
        return cls.get_logger("orchestrator")
    
    @classmethod
    def get_api_logger(cls) -> logging.Logger:
        """Get logger for API"""
        return cls.get_logger("api")
    
    @classmethod
    def shutdown(cls) -> None:
        """Shutdown logging system gracefully"""
        if not cls._initialized:
            return
        
        root_logger = logging.getLogger()
        root_logger.info("Shutting down logging system")
        
        # Flush and close all handlers
        for handler in root_logger.handlers[:]:
            handler.flush()
            handler.close()
            root_logger.removeHandler(handler)
        
        # Flush component loggers
        for logger in cls._loggers.values():
            for handler in logger.handlers[:]:
                handler.flush()
                handler.close()
                logger.removeHandler(handler)
        
        cls._loggers.clear()
        cls._initialized = False


def setup_logging() -> None:
    """Initialize logging system (convenience function)"""
    LoggerManager.initialize()


def get_logger(component: str) -> logging.Logger:
    """
    Get logger for component (convenience function)
    
    Args:
        component: Component name
    
    Returns:
        Configured logger
    """
    return LoggerManager.get_logger(component)
