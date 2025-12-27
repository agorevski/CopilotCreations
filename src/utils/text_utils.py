"""
Text utilities for the Discord Copilot Bot.
"""

from ..config import MAX_MESSAGE_LENGTH


def truncate_output(output: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate output to the last max_length characters."""
    if len(output) <= max_length:
        return output
    return "..." + output[-(max_length - 3):]


def format_error_message(title: str, error: str, include_traceback: bool = True) -> str:
    """Format an error message consistently for Discord.
    
    Args:
        title: The error title (e.g., "Failed to create project directory").
        error: The error message or traceback.
        include_traceback: If True, wraps error in a code block.
    
    Returns:
        A consistently formatted error message.
    """
    if include_traceback:
        return f"❌ **{title}**\n```\n{error}\n```"
    return f"❌ **{title}:** {error}"
