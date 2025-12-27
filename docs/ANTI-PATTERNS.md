# Anti-Patterns and Improvement Recommendations

This document lists developer anti-patterns found in the codebase along with suggestions for fixing them. Each item is designed to be addressed independently by an agent.

---

## 1. Missing Type Hints

**Location:** `src/commands/createproject.py` (lines 32-36, 58-63, 87-88)

**Problem:**
Several functions lack complete type hints:

```python
async def update_file_tree_message(
    message: discord.Message,
    project_path: Path,
    is_running: asyncio.Event,
    error_event: asyncio.Event
):  # Missing return type
```

**Why it's bad:**
- Reduces code readability
- IDE/editor features like autocomplete work poorly
- Static type checkers cannot catch errors

**Fix:**
Add return type hints to all functions:

```python
async def update_file_tree_message(
    message: discord.Message,
    project_path: Path,
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> None:
```

**Files to modify:**
- `src/commands/createproject.py`
- `src/utils/folder_utils.py`
- `src/utils/logging.py`
- `src/bot.py`

---

## 2. Inconsistent Error Message Formatting

**Location:** `src/commands/createproject.py` (lines 132-133, 153-154, 267)

**Problem:**
Error messages use different formats:

```python
await interaction.followup.send(f"❌ Failed to create project directory:\n```\n{traceback.format_exc()}\n```")
# vs
status = f"❌ **ERROR**\n```\n{error_message}\n```"
```

**Why it's bad:**
- Inconsistent user experience
- Harder to maintain

**Fix:**
Create a utility function for error formatting:

```python
def format_error_message(title: str, error: str, include_traceback: bool = True) -> str:
    """Format an error message consistently for Discord."""
    if include_traceback:
        return f"❌ **{title}**\n```\n{error}\n```"
    return f"❌ **{title}:** {error}"
```

**Files to modify:**
- `src/utils/text_utils.py`
- `src/commands/createproject.py`

---

## 3. Missing Input Validation

**Location:** `src/commands/createproject.py` (line 105-109)

**Problem:**
The `prompt` parameter is not validated before use.

```python
async def createproject(
    interaction: discord.Interaction,
    prompt: str,
    model: Optional[str] = None
):
```

**Why it's bad:**
- Empty or whitespace-only prompts could cause issues
- Very long prompts might cause problems
- No validation of model parameter format

**Fix:**
Add input validation at the start of the function:

```python
# Validate prompt
prompt = prompt.strip()
if not prompt:
    await interaction.response.send_message("❌ Prompt cannot be empty.", ephemeral=True)
    return

if len(prompt) > 10000:  # Reasonable limit
    await interaction.response.send_message("❌ Prompt is too long (max 10,000 characters).", ephemeral=True)
    return

# Validate model if provided
if model and not re.match(r'^[a-zA-Z0-9\-_.]+$', model):
    await interaction.response.send_message("❌ Invalid model name format.", ephemeral=True)
    return
```

**Files to modify:**
- `src/commands/createproject.py`
- `src/config.py` (add `MAX_PROMPT_LENGTH` constant)

---

## 4. Logger Side Effects

**Location:** `src/utils/logging.py` (line 1-7)

**Problem:**
The `setup_logging` function is exported but creates side effects.

**Why it's bad:**
- `logger = setup_logging()` is called at module level
- Each import reconfigures logging

**Fix:**
Use a singleton pattern for logger initialization:

```python
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

# For backward compatibility
logger = get_logger()
```

**Files to modify:**
- `src/utils/logging.py`

---

## Summary

| # | Anti-Pattern | Severity | Effort |
|---|--------------|----------|--------|
| 1 | Missing Type Hints | Low | Low |
| 2 | Inconsistent Error Formatting | Low | Low |
| 3 | Missing Input Validation | High | Low |
| 4 | Logger Side Effects | Low | Low |

**Recommended Fix Order:**
1. #3 - Input validation (security)
2. #1 - Type hints (code quality)
3. #2 - Error formatting consistency
4. #4 - Logger side effects
