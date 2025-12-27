"""
Text utilities for the Discord Copilot Bot.
"""

from ..config import MAX_MESSAGE_LENGTH


def truncate_output(output: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate output to the last max_length characters."""
    if len(output) <= max_length:
        return output
    return "..." + output[-(max_length - 3):]
