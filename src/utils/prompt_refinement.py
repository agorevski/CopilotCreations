"""
Prompt refinement service using Azure OpenAI for conversational prompt building.

This module provides AI-assisted prompt refinement through clarifying questions
and iterative improvement of project descriptions.
"""

from typing import List, Dict, Optional, Tuple, AsyncGenerator

from ..config import (
    AI_REFINEMENT_TEMPERATURE,
    AI_EXTRACTION_TEMPERATURE,
    get_required_prompt_template,
)
from .azure_openai_client import AzureOpenAIClient
from .logging import logger


class PromptRefinementService:
    """Service for refining project prompts through AI conversation."""

    def __init__(self):
        """Initialize the refinement service with Azure OpenAI credentials."""
        # Use the shared Azure OpenAI client
        self._ai_client = AzureOpenAIClient()

    # Proxy properties for backwards compatibility with tests
    @property
    def endpoint(self) -> Optional[str]:
        """Azure OpenAI endpoint URL."""
        return self._ai_client.endpoint

    @endpoint.setter
    def endpoint(self, value: Optional[str]) -> None:
        """Set Azure OpenAI endpoint URL."""
        self._ai_client.endpoint = value

    @property
    def api_key(self) -> Optional[str]:
        """Azure OpenAI API key."""
        return self._ai_client.api_key

    @api_key.setter
    def api_key(self, value: Optional[str]) -> None:
        """Set Azure OpenAI API key."""
        self._ai_client.api_key = value

    @property
    def deployment_name(self) -> Optional[str]:
        """Azure OpenAI deployment name."""
        return self._ai_client.deployment_name

    @deployment_name.setter
    def deployment_name(self, value: Optional[str]) -> None:
        """Set Azure OpenAI deployment name."""
        self._ai_client.deployment_name = value

    @property
    def client(self):
        """Azure OpenAI client (lazy-loaded)."""
        return self._ai_client.client

    def is_configured(self) -> bool:
        """Check if Azure OpenAI integration is properly configured."""
        return self._ai_client.is_configured()

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the refinement assistant."""
        return get_required_prompt_template("prompt_refinement_system")

    async def get_refinement_response(
        self, conversation_history: List[Dict[str, str]], user_message: str
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
                None,
            )

        # Build messages array with system prompt
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        logger.info("Requesting prompt refinement from Azure OpenAI...")

        assistant_response = await self._ai_client.complete_async(
            messages=messages,
            temperature=AI_REFINEMENT_TEMPERATURE,
            log_prefix="Refinement",
        )

        if not assistant_response:
            return (
                "I'm having trouble processing that. Could you try rephrasing?",
                None,
            )

        # Check if a refined prompt is ready (look for the marker)
        refined_prompt = None
        if "refined prompt ready" in assistant_response.lower():
            refined_prompt = await self._extract_refined_prompt(
                conversation_history
                + [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_response},
                ]
            )

        logger.info("Received refinement response from Azure OpenAI")
        return (assistant_response, refined_prompt)

    async def stream_refinement_response(
        self, conversation_history: List[Dict[str, str]], user_message: str
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
                None,
            )
            return

        # Build messages array with system prompt
        messages = [{"role": "system", "content": self._get_system_prompt()}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        logger.info("Starting streaming prompt refinement from Azure OpenAI...")

        accumulated_response = ""
        async for chunk in self._ai_client.stream_async(
            messages=messages,
            temperature=AI_REFINEMENT_TEMPERATURE,
            log_prefix="Refinement",
        ):
            accumulated_response = chunk
            yield (accumulated_response, False, None)

        # Handle empty response
        if not accumulated_response:
            yield (
                "I'm having trouble processing that. Could you try rephrasing?",
                True,
                None,
            )
            return

        # Check if a refined prompt is ready
        refined_prompt = None
        if "refined prompt ready" in accumulated_response.lower():
            # Stream the extraction phase with visual feedback
            extraction_prefix = (
                accumulated_response
                + "\n\n📋 **Generating detailed specification...**\n\n"
            )
            extraction_accumulated = ""

            async for chunk in self._stream_extract_refined_prompt(
                conversation_history
                + [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": accumulated_response},
                ]
            ):
                extraction_accumulated = chunk
                # Yield combined response showing extraction progress
                yield (extraction_prefix + extraction_accumulated, False, None)

            if extraction_accumulated:
                refined_prompt = extraction_accumulated.strip()
                logger.info(f"Extracted refined prompt ({len(refined_prompt)} chars)")

        logger.info(
            f"Completed streaming refinement response ({len(accumulated_response)} chars)"
        )
        yield (accumulated_response, True, refined_prompt)

    async def _extract_refined_prompt(
        self, conversation_history: List[Dict[str, str]]
    ) -> Optional[str]:
        """Extract a refined prompt from the conversation history.

        This makes another API call to summarize the conversation into a final prompt.

        Args:
            conversation_history: The full conversation history.

        Returns:
            The extracted refined prompt, or None if extraction fails.
        """
        if not self.is_configured():
            return None

        extraction_prompt = get_required_prompt_template("prompt_extraction")
        extraction_system = get_required_prompt_template("prompt_extraction_system")

        messages = [{"role": "system", "content": extraction_system}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": extraction_prompt})

        refined_prompt = await self._ai_client.complete_async(
            messages=messages,
            temperature=AI_EXTRACTION_TEMPERATURE,
            log_prefix="Extraction",
        )

        if refined_prompt:
            logger.info(f"Extracted refined prompt ({len(refined_prompt)} chars)")
            return refined_prompt.strip()

        return None

    async def _stream_extract_refined_prompt(
        self, conversation_history: List[Dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """Stream extract a refined prompt from the conversation history.

        This makes a streaming API call to summarize the conversation into a final prompt.
        Yields accumulated content as it arrives for real-time display.

        Args:
            conversation_history: The full conversation history.

        Yields:
            Accumulated refined prompt content as it streams.
        """
        if not self.is_configured():
            return

        extraction_prompt = get_required_prompt_template("prompt_extraction")
        extraction_system = get_required_prompt_template("prompt_extraction_system")

        messages = [{"role": "system", "content": extraction_system}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": extraction_prompt})

        logger.info("Starting streaming prompt extraction from Azure OpenAI...")

        async for chunk in self._ai_client.stream_async(
            messages=messages,
            temperature=AI_EXTRACTION_TEMPERATURE,
            log_prefix="Extraction",
        ):
            yield chunk

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
                msg["content"] for msg in conversation_history if msg["role"] == "user"
            ]
            return "\n\n".join(user_messages)

        refined = await self._extract_refined_prompt(conversation_history)
        if refined:
            return refined

        # Fall back to user messages if extraction fails
        user_messages = [
            msg["content"] for msg in conversation_history if msg["role"] == "user"
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
