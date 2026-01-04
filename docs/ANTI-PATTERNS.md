# Engineering Anti-Patterns

This document catalogs engineering anti-patterns identified in the codebase, along with recommendations for remediation.

**Last Updated:** 2025-01-03

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

## 5. Hardcoded AI Model Parameters

**Location:** `src/utils/naming.py`, `src/utils/prompt_refinement.py`

**Problem:**
Azure OpenAI API parameters are hardcoded in multiple places:
- `max_completion_tokens=50000` appears in 4 places
- `temperature=0.7` and `temperature=0.3` hardcoded without constants

**Example:**
```python
# src/utils/naming.py
response = self.client.chat.completions.create(
    model=self.deployment_name,
    messages=messages,
    max_completion_tokens=50000,  # Hardcoded
    ...
)
```

**Recommendation:**
Define named constants in config.py:
```python
MAX_COMPLETION_TOKENS = 50000
REFINEMENT_TEMPERATURE = 0.7
EXTRACTION_TEMPERATURE = 0.3
```

---

## 6. Duplicate Imports

**Location:** `src/commands/session_commands.py`, `src/config.py`

**Problem:**
Config imports are duplicated within the same file, and logging is imported multiple times inline in config.py.

**Example:**
```python
# src/commands/session_commands.py
from ..config import (MAX_PROMPT_LENGTH, ...)  # Line 21-26
from ..config import (PROJECTS_DIR, ...)       # Line 45-53 (duplicated)

# src/config.py - import logging called in 3 different exception blocks
import logging
logging.getLogger("copilot_bot").warning(...)
```

**Recommendation:**
Consolidate imports at the top of each file. Move logging import to module level in config.py.

---

## 7. Missing Configuration Validation

**Location:** `src/config.py`

**Problem:**
Environment variables are converted to integers without bounds checking, which could cause unexpected behavior:

**Example:**
```python
TIMEOUT_MINUTES = int(os.getenv("TIMEOUT_MINUTES", "30"))  # No bounds
MAX_PARALLEL_REQUESTS = int(os.getenv("MAX_PARALLEL_REQUESTS", "2"))  # No min/max
```

**Recommendation:**
Add validation with sensible bounds:
```python
TIMEOUT_MINUTES = max(1, min(120, int(os.getenv("TIMEOUT_MINUTES", "30"))))
MAX_PARALLEL_REQUESTS = max(1, min(10, int(os.getenv("MAX_PARALLEL_REQUESTS", "2"))))
```

---

## 8. Temporal Coupling

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

## 9. Over-reliance on String Formatting for Messages

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

## 10. Subprocess Without Shell Escaping Validation

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

## 11. Duplicated Azure OpenAI Call Pattern

**Location:** `src/utils/naming.py`, `src/utils/prompt_refinement.py`

**Problem:**
The same pattern is repeated for every Azure OpenAI API call:
- Create messages array
- Call Azure OpenAI
- Log response
- Check for empty/null response
- Sanitize output

**Recommendation:**
Extract into a common helper method:
```python
async def _call_azure_openai(
    self,
    messages: List[Dict[str, str]],
    temperature: float = 0.7
) -> Optional[str]:
    """Common wrapper for Azure OpenAI API calls with logging and error handling."""
    ...
```

---

## 12. Magic Numbers in Text Splitting

**Location:** `src/utils/text_utils.py`

**Problem:**
Algorithm-specific magic numbers without explanation:

**Example:**
```python
if break_point > max_length // 2:  # Why 50%?
```

**Recommendation:**
Extract to named constant:
```python
MIN_BREAK_POINT_RATIO = 0.5  # Minimum ratio of content to preserve when splitting
```

---

## 13. Missing Repository Name Validation

**Location:** `src/utils/github.py`

**Problem:**
Repository names are only validated after Azure OpenAI generation in naming.py, but not validated at the point of use in github.py.

**Recommendation:**
Add early validation in `create_repository()` to fail fast with a clear error message.

---

## Summary

| Priority | Anti-Pattern | Impact | Effort to Fix |
|----------|-------------|--------|---------------|
| High | Global Mutable State | Testing, Concurrency | Medium |
| High | Duplicated Code | Maintainability | Low |
| High | God Function | Maintainability | Medium |
| Medium | Mixed Sync/Async | Performance, Bugs | Medium |
| Medium | Missing Config Validation | Reliability | Low |
| Medium | Hardcoded AI Parameters | Flexibility | Low |
| Medium | Duplicate Imports | Code Quality | Low |
| Low | Temporal Coupling | Usability | Medium |
| Low | String Message Templates | Maintainability | Medium |
| Low | Subprocess Validation | Security | Low |

---

## Remediation Priority

1. **Phase 1 (Quick Wins):**
   - Consolidate duplicate imports
   - Add config validation (min/max bounds)
   - Extract AI parameters to constants
   - Add magic number constants for text splitting

2. **Phase 2 (Code Quality):**
   - Extract duplicated code to shared services
   - Break up god functions
   - Create Azure OpenAI helper method

3. **Phase 3 (Architecture):**
   - Introduce full dependency injection
   - Create message template system
   - Convert to async-first where appropriate
   - Add repository name validation

---

## Recently Fixed (2025-12-30)

The following anti-patterns were addressed:

1. ✅ **Magic Numbers** - Added named constants (`MAX_USERNAME_LENGTH`, `DISCORD_INVALID_WEBHOOK_TOKEN`, `MAX_DESCRIPTION_LENGTH`, `GIT_OPERATION_TIMEOUT`, etc.)

2. ✅ **Swallowed Exceptions** - Config.py now logs specific warnings for YAML parse errors, IO errors, and unexpected exceptions

3. ✅ **Tight Coupling** - Added `RepositoryService` and `NamingService` Protocol interfaces for dependency injection

4. ✅ **Leaky Abstractions** - Made private functions public by removing underscore prefixes (`create_project_directory`, `send_initial_message`, etc.)

5. ✅ **Missing Type Hints** - Added type hints for `bot` parameter in session_commands.py functions

6. ✅ **Inconsistent Error Handling** - Improved with named constants for error codes

## Recently Fixed (2025-01-03)

The following anti-patterns were addressed:

7. ✅ **Duplicate Imports (#6)** - Consolidated duplicate config imports in `session_commands.py`

8. ✅ **Missing Configuration Validation (#7)** - Added bounds checking for `TIMEOUT_MINUTES` (1-120), `MAX_PARALLEL_REQUESTS` (1-10), and `SESSION_EXPIRY_MINUTES` (5-1440) in `config.py`

9. ✅ **Hardcoded AI Model Parameters (#5)** - Extracted to named constants in `config.py`: `MAX_COMPLETION_TOKENS`, `REFINEMENT_TEMPERATURE`, `EXTRACTION_TEMPERATURE`, `NAMING_TEMPERATURE`

10. ✅ **Duplicated Azure OpenAI Call Pattern (#11)** - Created `AzureOpenAIClient` class in `src/utils/azure_openai_client.py` with common wrapper for API calls. Refactored `naming.py` and `prompt_refinement.py` to use it.

11. ✅ **God Function Anti-Pattern (#3)** - Split `createproject.py` (848→260 lines) by extracting helper functions to `createproject_helpers.py` (650+ lines). Functions extracted:
    - Message building: `_generate_folder_structure_section()`, `_generate_copilot_output_section()`, `_generate_summary_section()`, `_build_unified_message()`, `update_unified_message()`
    - Process management: `read_stream()`, `run_copilot_process()`
    - Project lifecycle: `create_project_directory()`, `send_initial_message()`, `update_final_message()`
    - GitHub integration: `handle_github_integration()`
    - Cleanup: `_handle_remove_readonly()`, `cleanup_project_directory()`, `_send_log_file()`

12. ✅ **Primitive Obsession (#15)** - Created domain objects in `src/utils/project_creation.py`:
    - `ProjectBuildState` dataclass for build status, paths, errors, process info
    - `ProjectConfiguration` dataclass for user inputs (prompt, model, options)
    - `ProjectCreationService` class to orchestrate project builds

## 14. Excessive Mocking in Tests

**Location:** `tests/` directory (especially `test_createproject.py`, `test_session_commands.py`)

**Problem:**
The test suite relies heavily on `unittest.mock.MagicMock` (360+ occurrences). Tests mock internal components like `bot`, `interaction`, `process_registry`, and `session_manager` rather than testing behavior. This makes tests brittle; refactoring internal implementation often breaks tests even if external behavior remains correct.

**Example:**
```python
# tests/test_createproject.py
mock_bot = MagicMock()
mock_bot.tree = MagicMock()
mock_bot.tree.command = MagicMock(return_value=lambda f: f)
interaction.user = MagicMock()
```

**Recommendation:**
*   Use **Fakes** or **Stubs** for external dependencies instead of mocks.
*   Test against public interfaces.
*   Use a real `CopilotBot` instance with a fake Discord client for integration tests.

---

## 15. Primitive Obsession

**Location:** `src/commands/createproject.py`, `src/commands/session_commands.py`

**Problem:**
Domain concepts are passed around as loose collections of primitive types (strings, bools, paths) rather than encapsulated objects. Functions take long lists of arguments representing the state of a project build.

**Example:**
```python
# src/commands/createproject.py
async def update_final_message(
    unified_msg, project_path, output_buffer, interaction,
    prompt, model, timed_out, error_occurred, error_message,
    process, github_status, ...
)
```

**Recommendation:**
Introduce domain objects to encapsulate state:
*   `ProjectBuildState` class to hold status, paths, errors, and process info.
*   `ProjectConfiguration` class to hold user inputs (prompt, model, options).

---

## 16. Inconsistent Error Handling

**Location:** Throughout codebase (30+ instances of `except Exception`)

**Problem:**
Broad exception catching (`except Exception`) is used frequently. This can swallow unexpected bugs (like `NameError` or `AttributeError`) and treat them as runtime failures, making debugging difficult.

**Example:**
```python
# src/commands/createproject.py
except Exception as e:
    session_log.error(f"Failed to create project directory: {e}")
```

**Recommendation:**
*   Catch specific exceptions (e.g., `OSError`, `asyncio.TimeoutError`, `discord.DiscordException`).
*   Let unexpected exceptions bubble up to a global error handler or crash the specific task so they are noticed.

---

## 17. Leaky Abstractions (Git/CLI Operations)

**Location:** `src/utils/github.py`, `src/commands/createproject.py`

**Problem:**
The application interacts with external tools (Git, Copilot CLI) by constructing raw command strings and managing subprocesses directly. Authentication secrets are manually injected into URLs and scrubbed from logs. This is error-prone and insecure.

**Example:**
```python
# src/utils/github.py
remote_url = f"https://{user.login}:{self.token}@github.com/{user.login}/{repo_name}.git"
git_commands = [["git", "remote", "add", "origin", remote_url], ...]
```

**Recommendation:**
*   Use a dedicated library for Git operations (e.g., `GitPython` or `pygit2`) instead of shell commands.
*   Abstract the "Copilot CLI" into a `CopilotClient` class that handles the subprocess management and output parsing internally.

---

## 18. Low Cohesion (Manager Classes)

**Location:** `src/utils/github.py`, `src/utils/session_manager.py`

**Problem:**
The usage of "Manager" classes (`GitHubManager`, `SessionManager`) often indicates a lack of specific domain modeling. These classes tend to become "buckets" for loosely related functionality.

**Recommendation:**
*   Rename `SessionManager` to `SessionRepository` (if it stores sessions) or `SessionService` (if it coordinates actions).
*   Split `GitHubManager` into focused responsibilities: `RepositoryCreator`, `GitUploader`, `GitHubAuthenticator`.
