"""Standardized logging configuration for the IntelliPredict application."""

import logging
import sys

def setup_logger(name: str = "intellipredict") -> logging.Logger:
    """Sets up a logger with a standard format.
    
    Args:
        name: Name of the logger.
        
    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        
    return logger

# Default logger instance
logger = setup_logger()
