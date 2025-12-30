# Discord Copilot Bot - Usage Guide

## Setup

### Prerequisites

- Python 3.10+
- Discord bot token
- `copilot-cli` installed and configured
- (Optional) Azure OpenAI for AI-assisted prompt refinement

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/agorevski/CopilotCreations.git
   cd CopilotCreations
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env and add your DISCORD_BOT_TOKEN
   ```

4. Run the bot:
   ```bash
   python run.py
   ```

## Discord Commands

### Quick Project Creation: `/createproject`

Creates a new project using Copilot CLI with a single command.

**Parameters:**
- `prompt` (required): The prompt describing what project to create (max 500,000 characters)
- `model` (optional): The AI model to use (e.g., `gpt-4`, `claude-3-opus`)

**Example:**
```
/createproject prompt:"Create a Python Flask REST API with user authentication"
/createproject prompt:"Build a React todo app" model:gpt-4
```

---

### Conversational Project Creation (Recommended for Complex Projects)

For complex projects that need more detailed specifications, use the conversational flow with AI-assisted prompt refinement.

#### `/startproject`

Starts a new prompt-building session. The AI will ask clarifying questions to help you build a comprehensive project specification.

**Parameters:**
- `description` (optional): Initial description of your project idea

**Example:**
```
/startproject
/startproject description:"I want to build an expense tracking app"
```

After starting a session:
1. **Send messages normally** - Describe your project in as many messages as you need (no character limit!)
2. **AI asks questions** - If Azure OpenAI is configured, the bot asks clarifying questions about tech stack, features, architecture, etc.
3. **Refine iteratively** - Continue the conversation until your requirements are clear

#### `/buildproject`

Finalizes your prompt session and creates the project.

**Parameters:**
- `model` (optional): The AI model to use

**Example:**
```
/buildproject
/buildproject model:claude-3-opus
```

The bot will:
1. Compile all your messages into a refined prompt
2. Use AI to generate an exhaustive project specification with 12 detailed sections (if configured)
3. Delete all session messages from the channel (keeps chat clean)
4. Run Copilot CLI to create the project
5. Display a single status message with real-time updates

#### `/cancelprompt`

Cancels your active prompt-building session and discards all collected messages.

**Example:**
```
/cancelprompt
```

---

### Conversational Flow Example

```
User: /startproject description:I want to build a web app for tracking expenses

Bot:  📝 Prompt Session Started!
      🤖 Thanks! Let me ask some clarifying questions:
      1. What tech stack would you prefer? (React/Vue/Angular, Python/Node backend?)
      2. Should it support multiple users or single-user?
      3. Any specific features like reports, budgets, recurring expenses?

User: React frontend, Python FastAPI backend, multi-user with OAuth

Bot:  🤖 Got it! A few more questions for technical depth:
      1. Database preference? (PostgreSQL recommended for production)
      2. What API endpoints are needed? REST or GraphQL?
      3. Any specific error handling or validation requirements?

User: PostgreSQL, REST API, yes I want charts for spending trends

Bot:  🤖 Great! Final questions about deployment and testing:
      1. Deployment target? (Docker, AWS, Azure?)
      2. What test coverage percentage do you require?
      3. Any CI/CD pipeline preferences?

User: Docker containers, 80% coverage, GitHub Actions

Bot:  📋 **Refined Prompt Ready** - See attached file. Type `/buildproject` to create your project.
      [Attaches refined_prompt.md with full 12-section specification]

User: /buildproject

[All previous session messages are deleted]

Bot:  [Single unified message with real-time progress updates]
      📁 expense-wizard/
      ├── src/
      ├── tests/
      └── ...
      
      (copilot output...)
      
      📋 Summary
      Status: ✅ **COMPLETED**
      ...
```

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_BOT_TOKEN` | Discord bot token | Yes |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | No (for AI refinement) |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | No (for AI refinement) |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Azure OpenAI deployment name | No (for AI refinement) |
| `AZURE_OPENAI_API_VERSION` | Azure OpenAI API version (default: 2025-01-01-preview) | No |
| `SESSION_TIMEOUT_MINUTES` | Session expiry time (default: 30) | No |
| `TIMEOUT_MINUTES` | Process timeout in minutes (default: 30) | No |
| `MAX_PARALLEL_REQUESTS` | Max parallel copilot requests (default: 2) | No |
| `GITHUB_ENABLED` | Enable GitHub integration | No |
| `GITHUB_TOKEN` | GitHub personal access token | No |
| `GITHUB_USERNAME` | GitHub username | No |
| `GITHUB_REPO_PRIVATE` | Make repos private (default: false) | No |
| `CLEANUP_AFTER_PUSH` | Delete local folder after GitHub push (default: true) | No |

### Prompt Templates (`config.yaml`)

The `config.yaml` file contains customizable prompts:

- `createproject` - Template prepended to all project creation prompts
- `prompt_refinement_system` - System prompt for the AI refinement assistant
- `repository_naming_prompt` - Prompt for generating creative repo names
- `repository_description_prompt` - Prompt for generating repo descriptions

### `.folderignore`

Control which folders are collapsed in the folder tree display:

```gitignore
# Dependencies
node_modules/
venv/

# Build outputs
dist/
build/

# IDE
.vscode/
.idea/
```

Ignored folders appear as: `node_modules/ (1234 files)`

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

### Coverage Requirements

The project requires **>75% test coverage**. Run `pytest --cov=src` to check coverage.

Coverage configuration is in `pyproject.toml`.

## Project Output

Projects are created in the `projects/` directory. With Azure OpenAI configured, projects get creative names like `expense-wizard` or `budget-ninja`. Otherwise, the naming format is:
```
{username}_{timestamp}_{unique_id}/
```

Example: `john_doe_20231227_143052_a1b2c3d4/`

## Log Files

Session logs are collected internally for debugging but are no longer sent as attachments to keep the Discord channel clean. The unified status message contains all relevant information about the project creation.

## Troubleshooting

### Bot not responding to commands

1. Ensure the bot has proper permissions
2. Check that slash commands are synced (restart bot)
3. Verify the bot token is correct

### Bot not responding to chat messages

1. Ensure you have an active session (use `/startproject` first)
2. Check that the Message Content Intent is enabled in Discord Developer Portal
3. Messages starting with `/` are ignored (they look like commands)

### AI refinement not working

1. Verify Azure OpenAI credentials in `.env`
2. Check that the deployment name matches your Azure configuration
3. Without AI, messages are still collected but no questions are asked

### Timeout errors

Projects have a 30-minute timeout. For larger projects:
- Break into smaller prompts
- Use a faster model

### Permission errors

Ensure the bot has:
- Send Messages
- Read Message History
- Attach Files
- Use Application Commands
- **Manage Messages** (required to delete session messages after `/buildproject`)
