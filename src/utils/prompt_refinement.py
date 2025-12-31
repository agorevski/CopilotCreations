"""
Prompt refinement service using Azure OpenAI for conversational prompt building.

This module provides AI-assisted prompt refinement through clarifying questions
and iterative improvement of project descriptions.
"""

import asyncio
from functools import partial
from typing import List, Dict, Optional, Tuple, AsyncGenerator

from openai import AzureOpenAI

from ..config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_VERSION,
    get_prompt_template
)
from .logging import logger


# Default system prompt for the refinement assistant
DEFAULT_REFINEMENT_SYSTEM_PROMPT = """You are an elite software architect and requirements analyst. Your mission is to transform vague project ideas into exhaustive, crystal-clear specifications that leave ZERO ambiguity for implementation.

When a user describes a project idea:
1. Ask 3-5 targeted clarifying questions per round (2-4 rounds total)
2. Cover: exact functionality, tech stack, data model, API design, auth, error handling, deployment, testing
3. Offer sensible defaults when asking questions
4. If user says "you decide", make explicit decisions and state them clearly
5. Never leave ambiguity - be EXPLICIT about every detail

When ready, produce a specification with these sections:
- Project Overview
- Tech Stack (exact versions)
- Feature List with acceptance criteria
- Data Model with all fields and relationships
- Architecture & Design Patterns
- Authentication & Authorization
- Error Handling Strategy
- Configuration & Environment Variables
- Testing Requirements (coverage %, specific scenarios)
- Deployment & CI/CD
- Non-Functional Requirements
- Implementation Order

NEVER use vague terms like "appropriate", "as needed", "standard" - be EXPLICIT.
Every feature must have testable acceptance criteria.
The final prompt must work with Claude Opus 4.5 with zero follow-up questions.

When you believe you have enough information, end your response with:
"📋 **Refined Prompt Ready** - Type `/buildproject` to create your project, or continue chatting to refine further."

Keep responses under 500 words during Q&A. The final specification can be longer."""


class PromptRefinementService:
    """Service for refining project prompts through AI conversation."""
    
    def __init__(self):
        """Initialize the refinement service with Azure OpenAI credentials."""
        self.endpoint = AZURE_OPENAI_ENDPOINT
        self.api_key = AZURE_OPENAI_API_KEY
        self.deployment_name = AZURE_OPENAI_DEPLOYMENT_NAME
        self.api_version = AZURE_OPENAI_API_VERSION
        self._client: Optional[AzureOpenAI] = None
    
    @property
    def client(self) -> Optional[AzureOpenAI]:
        """Lazy-load the Azure OpenAI client."""
        if self._client is None and self.is_configured():
            self._client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version
            )
        return self._client
    
    def is_configured(self) -> bool:
        """Check if Azure OpenAI integration is properly configured."""
        return bool(self.endpoint and self.api_key and self.deployment_name)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the refinement assistant."""
        custom_prompt = get_prompt_template('prompt_refinement_system')
        return custom_prompt if custom_prompt else DEFAULT_REFINEMENT_SYSTEM_PROMPT
    
    async def get_refinement_response(
        self,
        conversation_history: List[Dict[str, str]],
        user_message: str
    ) -> Tuple[str, Optional[str]]:
        """Get a refinement response from the AI assistant.
        
        Args:
            conversation_history: Previous conversation turns.
            user_message: The latest user message.
            
        Returns:
            Tuple of (assistant_response, refined_prompt_if_ready).
            The refined_prompt is extracted if the assistant indicates readiness.
        """
        if not self.is_configured():
            logger.warning("Azure OpenAI not configured for prompt refinement")
            return (
                "⚠️ AI refinement is not configured. Your messages are being collected. "
                "Type `/buildproject` when ready to create your project.",
                None
            )
        
        try:
            # Build messages array with system prompt
            messages = [
                {"role": "system", "content": self._get_system_prompt()}
            ]
            
            # Add conversation history
            messages.extend(conversation_history)
            
            # Add the new user message
            messages.append({"role": "user", "content": user_message})
            
            logger.info("Requesting prompt refinement from Azure OpenAI...")
            
            # Run synchronous API call in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    self.client.chat.completions.create,
                    model=self.deployment_name,
                    messages=messages,
                    max_completion_tokens=50000,
                    temperature=0.7,
                    stream=False
                )
            )
            
            # Log full response details for debugging
            if response.choices:
                choice = response.choices[0]
                logger.info(f"GPT Response - finish_reason: {choice.finish_reason}")
                if choice.message:
                    logger.info(f"GPT Response - content length: {len(choice.message.content) if choice.message.content else 0}")
                    if choice.message.refusal:
                        logger.warning(f"GPT Response - refusal: {choice.message.refusal}")
            else:
                logger.warning("GPT Response - no choices returned")
            
            assistant_response = response.choices[0].message.content
            logger.info(f"GPT Response (refinement): {assistant_response}")
            if not assistant_response:
                # Log additional details when empty
                logger.warning("Azure OpenAI returned empty response")
                if response.choices[0].finish_reason:
                    logger.warning(f"Finish reason: {response.choices[0].finish_reason}")
                if hasattr(response, 'usage') and response.usage:
                    logger.warning(f"Token usage - prompt: {response.usage.prompt_tokens}, completion: {response.usage.completion_tokens}")
                return ("I'm having trouble processing that. Could you try rephrasing?", None)
            
            # Check if a refined prompt is ready (look for the marker)
            refined_prompt = None
            if "refined prompt ready" in assistant_response.lower():
                refined_prompt = await self._extract_refined_prompt(
                    conversation_history + [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": assistant_response}
                    ]
                )
            
            logger.info("Received refinement response from Azure OpenAI")
            return (assistant_response, refined_prompt)
            
        except Exception as e:
            logger.error(f"Failed to get refinement response: {type(e).__name__}: {e}")
            return (
                f"⚠️ Error communicating with AI: {str(e)[:100]}. "
                "Your message has been saved. Try again or type `/buildproject` to proceed.",
                None
            )
    
    async def stream_refinement_response(
        self,
        conversation_history: List[Dict[str, str]],
        user_message: str
    ) -> AsyncGenerator[Tuple[str, bool, Optional[str]], None]:
        """Stream a refinement response from the AI assistant.
        
        Yields chunks of the response as they arrive from the API.
        
        Args:
            conversation_history: Previous conversation turns.
            user_message: The latest user message.
            
        Yields:
            Tuple of (accumulated_response, is_complete, refined_prompt_if_ready).
        """
        if not self.is_configured():
            logger.warning("Azure OpenAI not configured for prompt refinement")
            yield (
                "⚠️ AI refinement is not configured. Your messages are being collected. "
                "Type `/buildproject` when ready to create your project.",
                True,
                None
            )
            return
        
        try:
            # Build messages array with system prompt
            messages = [
                {"role": "system", "content": self._get_system_prompt()}
            ]
            
            # Add conversation history
            messages.extend(conversation_history)
            
            # Add the new user message
            messages.append({"role": "user", "content": user_message})
            
            logger.info("Starting streaming prompt refinement from Azure OpenAI...")
            
            # Run synchronous streaming API call in thread pool
            loop = asyncio.get_event_loop()
            
            # Create the streaming response
            stream = await loop.run_in_executor(
                None,
                partial(
                    self.client.chat.completions.create,
                    model=self.deployment_name,
                    messages=messages,
                    max_completion_tokens=50000,
                    temperature=0.7,
                    stream=True
                )
            )
            
            accumulated_response = ""
            
            # Process chunks from the stream
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    accumulated_response += content
                    yield (accumulated_response, False, None)
            
            # Final yield with complete response
            if not accumulated_response:
                logger.warning("Azure OpenAI returned empty streaming response")
                yield ("I'm having trouble processing that. Could you try rephrasing?", True, None)
                return
            
            # Check if a refined prompt is ready
            refined_prompt = None
            if "refined prompt ready" in accumulated_response.lower():
                refined_prompt = await self._extract_refined_prompt(
                    conversation_history + [
                        {"role": "user", "content": user_message},
                        {"role": "assistant", "content": accumulated_response}
                    ]
                )
            
            logger.info(f"Completed streaming refinement response ({len(accumulated_response)} chars)")
            yield (accumulated_response, True, refined_prompt)
            
        except Exception as e:
            logger.error(f"Failed to stream refinement response: {type(e).__name__}: {e}")
            yield (
                f"⚠️ Error communicating with AI: {str(e)[:100]}. "
                "Your message has been saved. Try again or type `/buildproject` to proceed.",
                True,
                None
            )
    
    async def _extract_refined_prompt(self, conversation_history: List[Dict[str, str]]) -> Optional[str]:
        """Extract a refined prompt from the conversation history.
        
        This makes another API call to summarize the conversation into a final prompt.
        
        Args:
            conversation_history: The full conversation history.
            
        Returns:
            The extracted refined prompt, or None if extraction fails.
        """
        if not self.is_configured():
            return None
        
        try:
            extraction_prompt = """Based on the conversation above, generate an EXHAUSTIVE project specification that leaves ZERO ambiguity.

You MUST include ALL of the following sections with EXPLICIT details:

## PROJECT SPECIFICATION

### 1. Project Overview
[One paragraph describing what this project does and its primary purpose]

### 2. Tech Stack (EXPLICIT)
- Language: [exact language and version]
- Framework: [exact framework and version]
- Database: [exact database type]
- Additional tools: [list each dependency with its purpose]

### 3. Feature List (EXHAUSTIVE)
For EACH feature discussed:
- **Feature Name**: [Clear description]
  - User story: "As a [user], I want to [action] so that [benefit]"
  - Acceptance criteria: [numbered list of TESTABLE criteria]
  - API endpoint (if applicable): [METHOD /path with request/response shapes]

### 4. Data Model
[Entity definitions with ALL fields, their types, constraints, and relationships]

### 5. Architecture & Design Patterns
- Directory structure: [explicit tree showing every folder and key files]
- Design patterns: [list each pattern to use with rationale]
- Module responsibilities: [which module handles what functionality]

### 6. Authentication & Authorization
[Exact auth mechanism, user types/roles, permissions for each role]

### 7. Error Handling Strategy
[How errors are caught, logged, formatted, and returned to users]

### 8. Configuration & Environment
[List ALL environment variables with descriptions and example values]

### 9. Testing Requirements
- Unit test targets: [specific functions/modules to test]
- Minimum coverage: [percentage]
- Integration test scenarios: [list key scenarios]
- Test data approach: [how to seed/mock]

### 10. Deployment & CI/CD
- Container: [Dockerfile requirements]
- CI pipeline steps: [exact workflow steps]
- Environment configs: [differences between dev/staging/prod]

### 11. Non-Functional Requirements
- Performance targets: [specific response times, throughput]
- Security measures: [input validation, rate limiting, CORS, etc.]
- Logging: [format, what to log, log levels]

### 12. Implementation Order
[Numbered sequence of what to build first, with dependencies noted]

CRITICAL RULES:
- NEVER use vague words like "appropriate", "as needed", "standard" - be EXPLICIT
- If something wasn't discussed, make a sensible decision and STATE IT CLEARLY
- Every feature must have testable acceptance criteria
- The output must be directly usable by Claude Opus 4.5 with NO follow-up questions needed
- Include concrete examples and specific values wherever possible

Do not include any conversational text or explanations. Output ONLY the specification."""

            messages = [
                {"role": "system", "content": "You are a technical writer creating project specifications."}
            ]
            messages.extend(conversation_history)
            messages.append({"role": "user", "content": extraction_prompt})
            
            # Run synchronous API call in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    self.client.chat.completions.create,
                    model=self.deployment_name,
                    messages=messages,
                    max_completion_tokens=50000,
                    temperature=0.3,
                    stream=False
                )
            )
            
            refined_prompt = response.choices[0].message.content
            logger.info(f"GPT Response (extraction): {refined_prompt}")
            if refined_prompt:
                logger.info(f"Extracted refined prompt ({len(refined_prompt)} chars)")
                return refined_prompt.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract refined prompt: {type(e).__name__}: {e}")
            return None
    
    async def generate_initial_questions(self, project_description: str) -> str:
        """Generate initial clarifying questions for a project description.
        
        Args:
            project_description: The user's initial project description.
            
        Returns:
            The assistant's response with clarifying questions.
        """
        response, _ = await self.get_refinement_response([], project_description)
        return response
    
    async def finalize_prompt(self, conversation_history: List[Dict[str, str]]) -> str:
        """Generate the final refined prompt from conversation history.
        
        Args:
            conversation_history: The full conversation history.
            
        Returns:
            The final refined prompt for project creation.
        """
        if not self.is_configured():
            # Fall back to concatenating user messages
            user_messages = [
                msg["content"] for msg in conversation_history 
                if msg["role"] == "user"
            ]
            return "\n\n".join(user_messages)
        
        refined = await self._extract_refined_prompt(conversation_history)
        if refined:
            return refined
        
        # Fall back to user messages if extraction fails
        user_messages = [
            msg["content"] for msg in conversation_history 
            if msg["role"] == "user"
        ]
        return "\n\n".join(user_messages)


# Singleton instance for easy access
_refinement_service: Optional[PromptRefinementService] = None


def get_refinement_service() -> PromptRefinementService:
    """Get the singleton refinement service instance.
    
    Returns:
        The refinement service instance.
    """
    global _refinement_service
    if _refinement_service is None:
        _refinement_service = PromptRefinementService()
    return _refinement_service


def reset_refinement_service() -> None:
    """Reset the refinement service (useful for testing)."""
    global _refinement_service
    _refinement_service = None
