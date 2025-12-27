# Anti-Patterns and Improvement Recommendations

This document lists developer anti-patterns found in the codebase along with suggestions for fixing them. Each item is designed to be addressed independently by an agent.

---

## 1. Global Mutable State (Singleton Bot Instance)

**Location:** `src/bot.py` (line 26)

**Problem:**
The bot is instantiated as a global module-level singleton:

```python
# Global bot instance
bot = CopilotBot()
```

**Why it's bad:**
- Makes testing difficult (tests share state)
- Creates tight coupling between modules
- Makes it hard to run multiple instances or mock the bot
- Import order dependencies can cause issues

**Fix:**
Use a factory function and dependency injection pattern:

```python
_bot_instance: Optional[CopilotBot] = None

def get_bot() -> CopilotBot:
    """Get or create the bot instance."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = CopilotBot()
    return _bot_instance

def create_bot() -> CopilotBot:
    """Create a new bot instance (useful for testing)."""
    return CopilotBot()
```

**Files to modify:**
- `src/bot.py`
- `src/commands/__init__.py`
- `run.py`

---

## 2. Missing Type Hints

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

## 3. Side Effects at Import Time

**Location:** `src/config.py` (lines 10, 18)

**Problem:**
Module-level code executes side effects during import:

```python
load_dotenv()  # IO operation at import
PROJECTS_DIR.mkdir(exist_ok=True)  # Creates directory at import
```

**Why it's bad:**
- Makes testing difficult (can't import without side effects)
- Can cause issues if imported from unexpected contexts
- Violates principle of least surprise

**Fix:**
Move side effects to explicit initialization functions:

```python
_initialized = False

def init_config() -> None:
    """Initialize configuration (load .env, create directories)."""
    global _initialized
    if _initialized:
        return
    load_dotenv()
    PROJECTS_DIR.mkdir(exist_ok=True)
    _initialized = True
```

Then call `init_config()` in `run.py` before starting the bot.

**Files to modify:**
- `src/config.py`
- `run.py`

---

## 4. Duplicated Code in Message Update Functions

**Location:** `src/commands/createproject.py` (lines 32-55 and 58-84)

**Problem:**
`update_file_tree_message` and `update_output_message` have nearly identical structure with duplicated loop logic, exception handling, and update patterns.

**Why it's bad:**
- Violates DRY (Don't Repeat Yourself)
- Bug fixes must be applied in multiple places
- Harder to maintain

**Fix:**
Extract common logic into a base update function or use a generic pattern:

```python
async def update_message_with_content(
    message: discord.Message,
    content_generator: Callable[[], str],
    is_running: asyncio.Event,
    error_event: asyncio.Event
) -> None:
    """Generic message updater that only updates when content changes."""
    last_content = ""
    while is_running.is_set() and not error_event.is_set():
        try:
            content = content_generator()
            if len(content) > MAX_MESSAGE_LENGTH:
                content = content[:MAX_MESSAGE_LENGTH - 3] + "```"
            if content != last_content:
                await message.edit(content=content)
                last_content = content
        except discord.errors.HTTPException as e:
            logger.debug(f"HTTP error: {e}")
        except Exception as e:
            logger.warning(f"Update error: {e}")
        await asyncio.sleep(UPDATE_INTERVAL)
```

**Files to modify:**
- `src/commands/createproject.py`

---

## 5. Long Function (createproject command handler)

**Location:** `src/commands/createproject.py` (lines 105-325)

**Problem:**
The `createproject` function is over 220 lines long and handles too many responsibilities.

**Why it's bad:**
- Hard to understand and test
- Violates Single Responsibility Principle
- Difficult to modify without introducing bugs

**Fix:**
Break into smaller, focused functions:

```python
async def _create_project_directory(username: str, session_log: SessionLogCollector) -> Path:
    """Create and return the project directory path."""
    ...

async def _send_initial_messages(interaction: discord.Interaction, project_path: Path, model: Optional[str]) -> Tuple[discord.Message, discord.Message]:
    """Send initial Discord messages and return message objects."""
    ...

async def _run_copilot_process(project_path: Path, prompt: str, model: Optional[str], session_log: SessionLogCollector) -> Tuple[bool, bool, str, list]:
    """Run the copilot process and return status."""
    ...

async def _send_summary(interaction: discord.Interaction, ...) -> None:
    """Send the final summary message."""
    ...
```

**Files to modify:**
- `src/commands/createproject.py`

---

## 6. Inconsistent Error Message Formatting

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

## 7. Missing Input Validation

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

## 11. Test Assertion Without Message

**Location:** `tests/test_bot.py` (line 23)

**Problem:**
Test has meaningless assertion:

```python
def test_discord_token_loaded(self):
    """Test that token config exists (may be None in test env)."""
    assert True  # This always passes
```

**Why it's bad:**
- Test provides no value
- Gives false confidence in test coverage

**Fix:**
Either remove the test or make it meaningful:

```python
def test_discord_token_config_accessible(self):
    """Test that DISCORD_BOT_TOKEN config is accessible."""
    # Verify the config value is either None or a string
    assert DISCORD_BOT_TOKEN is None or isinstance(DISCORD_BOT_TOKEN, str)
```

**Files to modify:**
- `tests/test_bot.py`

---

## 12. No Graceful Shutdown Handling

**Location:** `src/bot.py`

**Problem:**
The bot has no graceful shutdown mechanism for cleanup.

**Why it's bad:**
- Running processes may not be terminated properly
- Resources may leak
- No cleanup of temporary files

**Fix:**
Add signal handlers and cleanup:

```python
import signal
import sys

async def cleanup():
    """Cleanup resources before shutdown."""
    logger.info("Shutting down gracefully...")
    # Add cleanup logic here

def setup_signal_handlers(bot: CopilotBot):
    """Set up signal handlers for graceful shutdown."""
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(cleanup())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
```

**Files to modify:**
- `src/bot.py`

---

## 13. Potential Race Condition in Output Buffer

**Location:** `src/commands/createproject.py` (lines 157, 187, 251-253)

**Problem:**
The `output_buffer` list is shared between async tasks without synchronization:

```python
output_buffer = []  # Shared state
# Used by read_stream and update_output_message concurrently
```

**Why it's bad:**
- List operations are not atomic in Python
- Could lead to data corruption in edge cases
- May miss output during concurrent access

**Fix:**
Use asyncio-safe data structures:

```python
import asyncio

class AsyncOutputBuffer:
    """Thread-safe output buffer for async operations."""
    
    def __init__(self):
        self._buffer: list[str] = []
        self._lock = asyncio.Lock()
    
    async def append(self, item: str) -> None:
        async with self._lock:
            self._buffer.append(item)
    
    async def get_content(self) -> str:
        async with self._lock:
            return ''.join(self._buffer)
```

**Files to modify:**
- `src/commands/createproject.py` (or create new `src/utils/async_buffer.py`)

---

## 14. Unused Import in Utilities

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

| # | Anti-Pattern | Severity | Effort | Status |
|---|--------------|----------|--------|--------|
| 1 | Silent Exception Swallowing | High | Low | ✅ Fixed |
| 2 | Global Mutable State | Medium | Medium | |
| 3 | Hardcoded Magic Numbers | Low | Low | ✅ Fixed |
| 4 | Missing Type Hints | Low | Low | |
| 5 | Side Effects at Import Time | Medium | Medium | |
| 6 | Duplicated Code | Medium | Medium | |
| 7 | Long Function | Medium | High | |
| 8 | Bare Exception Handling | High | Low | ✅ Fixed |
| 9 | Inconsistent Error Formatting | Low | Low | |
| 10 | Missing Input Validation | High | Low | |
| 11 | Meaningless Test Assertion | Low | Low | |
| 12 | No Graceful Shutdown | Medium | Medium | |
| 13 | Race Condition Risk | Medium | Medium | |
| 14 | Logger Side Effects | Low | Low | |

**Recommended Fix Order:**
1. ~~#1, #8 - Silent exceptions (quick wins, high impact)~~ ✅ Done
2. #10 - Input validation (security)
3. ~~#3~~ ✅ Done, #4 - Magic numbers and type hints (code quality)
4. #11 - Fix meaningless test
5. #9 - Error formatting consistency
6. #5, #14 - Import-time side effects
7. #6 - DRY violations
8. #2, #7 - Refactoring (larger changes)
9. #12, #13 - Infrastructure improvements
