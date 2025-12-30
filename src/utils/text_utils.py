"""
Text utilities for the Discord Copilot Bot.
"""

from typing import List

from ..config import MAX_MESSAGE_LENGTH


def truncate_output(output: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Truncate output to the last max_length characters."""
    if len(output) <= max_length:
        return output
    return "..." + output[-(max_length - 3):]


def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """Split a long message into multiple chunks that fit Discord's character limit.
    
    Splits intelligently at paragraph breaks, then sentence breaks, then word breaks.
    
    Args:
        text: The text to split.
        max_length: Maximum length per chunk (default: MAX_MESSAGE_LENGTH).
    
    Returns:
        A list of message chunks, each within the max_length limit.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        
        # Find a good break point within max_length
        chunk = remaining[:max_length]
        
        # Try to break at paragraph (double newline)
        break_point = chunk.rfind('\n\n')
        if break_point > max_length // 2:
            chunks.append(remaining[:break_point].rstrip())
            remaining = remaining[break_point:].lstrip()
            continue
        
        # Try to break at single newline
        break_point = chunk.rfind('\n')
        if break_point > max_length // 2:
            chunks.append(remaining[:break_point].rstrip())
            remaining = remaining[break_point:].lstrip()
            continue
        
        # Try to break at sentence end (. ! ?)
        for sep in ['. ', '! ', '? ']:
            break_point = chunk.rfind(sep)
            if break_point > max_length // 2:
                chunks.append(remaining[:break_point + 1].rstrip())
                remaining = remaining[break_point + 1:].lstrip()
                break
        else:
            # Try to break at space
            break_point = chunk.rfind(' ')
            if break_point > max_length // 2:
                chunks.append(remaining[:break_point].rstrip())
                remaining = remaining[break_point:].lstrip()
            else:
                # Hard break if no good break point found
                chunks.append(remaining[:max_length])
                remaining = remaining[max_length:]
    
    return chunks


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
