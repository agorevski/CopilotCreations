"""
Logging utilities for the Discord Copilot Bot.
"""

import logging
from datetime import datetime
from typing import List, Optional


_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """Get the application logger, initializing if needed."""
    global _logger
    if _logger is None:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        _logger = logging.getLogger("copilot_bot")
    return _logger


def setup_logging() -> logging.Logger:
    """Configure and return the application logger.
    
    Deprecated: Use get_logger() instead. This function is kept for
    backward compatibility.
    """
    return get_logger()


# For backward compatibility
logger = get_logger()


class SessionLogCollector:
    """Collects log messages for a specific session/command."""
    
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.logs: List[str] = []
        self.start_time = datetime.now()
    
    def log(self, level: str, message: str) -> None:
        """Add a log entry."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"{timestamp} | {level:<8} | [{self.session_id}] {message}"
        self.logs.append(entry)
        # Also log to main logger
        getattr(logger, level.lower(), logger.info)(f"[{self.session_id}] {message}")
    
    def info(self, message: str) -> None:
        """Log an info message."""
        self.log("INFO", message)
    
    def warning(self, message: str) -> None:
        """Log a warning message."""
        self.log("WARNING", message)
    
    def error(self, message: str) -> None:
        """Log an error message."""
        self.log("ERROR", message)
    
    def get_markdown(self, prompt: str, model: str, status: str, file_count: int, dir_count: int) -> str:
        """Generate markdown content for the log file."""
        duration = datetime.now() - self.start_time
        minutes, seconds = divmod(int(duration.total_seconds()), 60)
        
        md = f"""# Project Creation Log

## Summary
- **Session ID:** `{self.session_id}`
- **Started:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
- **Duration:** {minutes}m {seconds}s
- **Status:** {status}
- **Model:** {model}
- **Files Created:** {file_count}
- **Directories Created:** {dir_count}

## Prompt
```
{prompt}
```

## Execution Log
```
{chr(10).join(self.logs)}
```
"""
        return md
