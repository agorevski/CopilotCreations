"""
Logging utilities for the Discord Copilot Bot.
"""

import logging
from datetime import datetime
from typing import List


def setup_logging() -> logging.Logger:
    """Configure and return the application logger."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("copilot_bot")


logger = setup_logging()


class SessionLogCollector:
    """Collects log messages for a specific session/command."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logs: List[str] = []
        self.start_time = datetime.now()
    
    def log(self, level: str, message: str):
        """Add a log entry."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"{timestamp} | {level:<8} | [{self.session_id}] {message}"
        self.logs.append(entry)
        # Also log to main logger
        getattr(logger, level.lower(), logger.info)(f"[{self.session_id}] {message}")
    
    def info(self, message: str):
        """Log an info message."""
        self.log("INFO", message)
    
    def warning(self, message: str):
        """Log a warning message."""
        self.log("WARNING", message)
    
    def error(self, message: str):
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
