import logging
import sys
from datetime import datetime

def setup_logging():
    """Setup centralized logging configuration"""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    try:
        file_handler = logging.FileHandler(f"chatbot_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Could not set up file logging: {e}")
    
    logging.info("Logging setup complete")

# Call this at the start of your main application
setup_logging()