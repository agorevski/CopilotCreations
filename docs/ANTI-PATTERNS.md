# Engineering Anti-Patterns

This document catalogs engineering anti-patterns identified in the codebase, along with recommendations for remediation.

---

## 1. Global Mutable State (Singletons)

**Location:** Multiple files use module-level singleton instances

**Files Affected:**
- `src/bot.py` - `_bot_instance` and `bot` global
- `src/utils/github.py` - `github_manager` singleton
- `src/utils/naming.py` - `naming_generator` singleton
- `src/utils/session_manager.py` - `_session_manager` singleton
- `src/utils/prompt_refinement.py` - `_refinement_service` singleton
- `src/utils/process_registry.py` - `_process_registry` singleton
- `src/utils/logging.py` - `_logger` and `logger` globals

**Problem:**
Singletons create hidden dependencies, make unit testing difficult (requiring `reset_*` functions), prevent running multiple instances, and can cause issues with async code due to shared mutable state.

**Example:**
```python
# src/bot.py line 146
bot = get_bot()  # Module-level instantiation
```

**Recommendation:**
Use dependency injection. Pass dependencies explicitly through constructors or function parameters. For testing, create fresh instances rather than relying on reset functions.

---

## 2. Mixed Sync/Async Patterns

**Location:** `src/utils/async_buffer.py`, `src/utils/naming.py`, `src/utils/github.py`

**Problem:**
The codebase inconsistently mixes synchronous and asynchronous code:
- `AsyncOutputBuffer` has both `append()` (async) and `append_sync()` (sync) methods with a warning about race conditions
- `naming.py` and `github.py` use synchronous API calls that should be async
- `prompt_refinement.py` wraps sync calls in `run_in_executor` 

**Example:**
```python
# src/utils/async_buffer.py lines 35-49
def append_sync(self, item: str) -> None:
    """Note: Use this only when you're certain there are no concurrent
    async operations. Prefer the async append() method."""
    self._buffer.append(item)
```

**Recommendation:**
Choose a consistent async-first approach. Use async HTTP clients (like `httpx` or `aiohttp`) instead of wrapping sync calls. Remove the `_sync` methods or document when they're safe to use.

---

## 3. God Function Anti-Pattern

**Location:** `src/commands/createproject.py`

**Problem:**
The `createproject` command function is 100+ lines with multiple responsibilities: validation, directory creation, message sending, process management, GitHub integration, cleanup, and logging. This violates the Single Responsibility Principle.

**Example:**
The `setup_createproject_command` function (lines 670-816) handles:
- Input validation
- Prompt template loading
- Directory creation
- Discord message management
- Subprocess execution
- GitHub integration
- File cleanup
- Log file generation

**Recommendation:**
Extract these responsibilities into separate classes/functions:
- `ProjectValidator` - validate inputs
- `ProjectBuilder` - orchestrate the build process
- `DiscordNotifier` - handle Discord messages
- Use the Strategy pattern for different project creation strategies

---

## 4. Duplicated Code

**Location:** `src/commands/createproject.py` and `src/commands/session_commands.py`

**Problem:**
The `_execute_project_creation` function in `session_commands.py` (lines 308-406) largely duplicates logic from `createproject.py`. Both files have similar patterns for:
- Session log initialization
- Prompt template handling
- Project directory creation
- Error handling flows

**Example:**
```python
# Both files have identical patterns:
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
unique_id = str(uuid.uuid4())[:UNIQUE_ID_LENGTH]
folder_name = f"{username}_{timestamp}_{unique_id}"
```

**Recommendation:**
Extract common project creation logic into a dedicated `ProjectCreationService` class that both commands can use.

---

## 5. Magic Numbers and Strings

**Location:** Throughout the codebase, especially `src/config.py`

**Problem:**
While many values are in `config.py`, magic numbers still appear inline:
- `[:50]` for username length limit in multiple places
- HTTP error codes like `50027` without named constants
- Various string patterns hardcoded

**Example:**
```python
# src/commands/createproject.py line 224
if e.code == 50027:  # Invalid Webhook Token
```

```python
# src/utils/folder_utils.py line 18
sanitized = sanitized[:50]  # Limit length
```

**Recommendation:**
Define named constants for all magic values:
```python
DISCORD_INVALID_WEBHOOK_TOKEN = 50027
MAX_USERNAME_LENGTH = 50
```

---

## 6. Swallowed Exceptions

**Location:** `src/config.py`

**Problem:**
Exceptions are silently caught and ignored, hiding potential configuration errors.

**Example:**
```python
# src/config.py lines 59-64
try:
    with open(CONFIG_YAML_PATH, 'r', encoding='utf-8') as f:
        PROMPT_TEMPLATES.update(yaml.safe_load(f) or {})
except Exception:
    pass  # Silently ignore config.yaml errors, use empty templates
```

**Recommendation:**
At minimum, log warnings when configuration fails to load. Consider failing fast for critical configuration or providing clear fallback behavior documentation.

---

## 7. Tight Coupling to External Services

**Location:** `src/utils/github.py`, `src/utils/naming.py`, `src/utils/prompt_refinement.py`

**Problem:**
Business logic is tightly coupled to specific external service implementations (GitHub API, Azure OpenAI). This makes:
- Unit testing require mocking specific libraries
- Switching providers difficult
- Code harder to understand in isolation

**Example:**
```python
# src/utils/github.py directly uses PyGithub
from github import Github, GithubException

class GitHubManager:
    def __init__(self):
        self._github: Optional[Github] = None
```

**Recommendation:**
Define abstract interfaces (protocols) for external services and inject implementations:
```python
class RepositoryService(Protocol):
    def create_repository(self, name: str, description: str) -> RepositoryResult: ...
```

---

## 8. Inconsistent Error Handling

**Location:** Throughout the codebase

**Problem:**
Error handling patterns vary significantly:
- Some functions return tuples `(success, message, url)`
- Some raise exceptions
- Some return `Optional` values
- Some log and continue silently

**Example:**
```python
# src/utils/github.py returns tuple
def create_repository(...) -> Tuple[bool, str, Optional[str]]:

# src/utils/naming.py returns Optional
def generate_name(...) -> Optional[str]:
```

**Recommendation:**
Adopt a consistent error handling strategy:
- Use Result types or raise custom exceptions
- Define clear error hierarchies
- Document which approach each module uses

---

## 9. Temporal Coupling

**Location:** `src/config.py`, `run.py`

**Problem:**
The `init_config()` function must be called before using configuration values like `PROMPT_TEMPLATES`, but this isn't enforced by the type system. The dependency is implicit.

**Example:**
```python
# run.py
init_config()  # Must call this first!
bot = get_bot()  # This might use config values
```

**Recommendation:**
Use lazy initialization patterns or make the configuration a proper class that initializes on first access:
```python
class Config:
    _instance = None
    
    def __init__(self):
        self._load_config()
    
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

---

## 10. Leaky Abstractions

**Location:** `src/commands/session_commands.py`

**Problem:**
The session commands module imports and directly uses internal functions from `createproject.py` that start with underscores (private convention):

**Example:**
```python
# src/commands/session_commands.py lines 28-36
from .createproject import (
    _create_project_directory,
    _send_initial_message,
    _run_copilot_process,
    _update_final_message,
    _handle_github_integration,
    _cleanup_project_directory,
    update_unified_message,
)
```

**Recommendation:**
Either make these functions part of the public API (remove underscore prefix) or extract them into a shared module that both commands can use.

---

## 11. Missing Type Hints

**Location:** Various function signatures

**Problem:**
While most of the codebase uses type hints, some are incomplete or missing:

**Example:**
```python
# src/commands/session_commands.py line 308
async def _execute_project_creation(
    interaction: discord.Interaction,
    prompt: str,
    model: Optional[str],
    bot  # Missing type hint
) -> None:
```

**Recommendation:**
Add complete type hints to all function parameters and return values. Consider using `mypy` in strict mode in CI.

---

## 12. Over-reliance on String Formatting for Messages

**Location:** `src/commands/createproject.py`, `src/commands/session_commands.py`

**Problem:**
Discord messages are constructed using f-strings with embedded formatting, making them hard to maintain and localize.

**Example:**
```python
# src/commands/createproject.py lines 138-144
summary = f"""📋 Summary
Status: {status}
Prompt: {truncated_prompt}
Model: {model if model else 'default'}
Files: {file_count} | Dirs: {dir_count}
User: {interaction.user.mention}{github_status}"""
```

**Recommendation:**
Create message template classes or use a template engine. This enables:
- Easier testing
- Potential localization
- Separation of content from logic

---

## 13. Subprocess Without Shell Escaping Validation

**Location:** `src/utils/github.py`

**Problem:**
Git commands are constructed and executed via `subprocess.run()`. While the current implementation appears safe, there's no validation that parameters don't contain shell metacharacters.

**Example:**
```python
# src/utils/github.py lines 218-227
git_commands = [
    ["git", "init"],
    ["git", "config", "user.name", git_name],  # git_name comes from API
    ...
]
```

**Recommendation:**
Add explicit validation for any values that come from external sources before passing them to subprocess commands.

---

## Summary

| Priority | Anti-Pattern | Impact | Effort to Fix |
|----------|-------------|--------|---------------|
| High | Global Mutable State | Testing, Concurrency | Medium |
| High | Duplicated Code | Maintainability | Low |
| High | God Function | Maintainability | Medium |
| Medium | Mixed Sync/Async | Performance, Bugs | Medium |
| Medium | Swallowed Exceptions | Debugging | Low |
| Medium | Tight Coupling | Testing, Flexibility | High |
| Medium | Inconsistent Error Handling | Reliability | Medium |
| Low | Magic Numbers | Readability | Low |
| Low | Leaky Abstractions | API Design | Low |
| Low | Missing Type Hints | Type Safety | Low |

---

## Remediation Priority

1. **Phase 1 (Quick Wins):**
   - Add named constants for magic numbers
   - Log swallowed exceptions
   - Add missing type hints
   - Make underscore-prefixed functions public or refactor

2. **Phase 2 (Code Quality):**
   - Extract duplicated code to shared services
   - Break up god functions
   - Standardize error handling

3. **Phase 3 (Architecture):**
   - Introduce dependency injection
   - Create service interfaces for external dependencies
   - Convert to async-first where appropriate
