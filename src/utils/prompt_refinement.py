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
    AI_MAX_COMPLETION_TOKENS,
    AI_REFINEMENT_TEMPERATURE,
    AI_EXTRACTION_TEMPERATURE,
    get_prompt_template,
    get_required_prompt_template,
)
from .logging import logger


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
                api_version=self.api_version,
            )
        return self._client

    def is_configured(self) -> bool:
        """Check if Azure OpenAI integration is properly configured."""
        return bool(self.endpoint and self.api_key and self.deployment_name)

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

        try:
            # Build messages array with system prompt
            messages = [{"role": "system", "content": self._get_system_prompt()}]

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
                    max_completion_tokens=AI_MAX_COMPLETION_TOKENS,
                    temperature=AI_REFINEMENT_TEMPERATURE,
                    stream=False,
                ),
            )

            # Log full response details for debugging
            if response.choices:
                choice = response.choices[0]
                logger.info(f"GPT Response - finish_reason: {choice.finish_reason}")
                if choice.message:
                    logger.info(
                        f"GPT Response - content length: {len(choice.message.content) if choice.message.content else 0}"
                    )
                    if choice.message.refusal:
                        logger.warning(
                            f"GPT Response - refusal: {choice.message.refusal}"
                        )
            else:
                logger.warning("GPT Response - no choices returned")

            assistant_response = response.choices[0].message.content
            logger.info(f"GPT Response (refinement): {assistant_response}")
            if not assistant_response:
                # Log additional details when empty
                logger.warning("Azure OpenAI returned empty response")
                if response.choices[0].finish_reason:
                    logger.warning(
                        f"Finish reason: {response.choices[0].finish_reason}"
                    )
                if hasattr(response, "usage") and response.usage:
                    logger.warning(
                        f"Token usage - prompt: {response.usage.prompt_tokens}, completion: {response.usage.completion_tokens}"
                    )
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

        except Exception as e:
            logger.error(f"Failed to get refinement response: {type(e).__name__}: {e}")
            return (
                f"⚠️ Error communicating with AI: {str(e)[:100]}. "
                "Your message has been saved. Try again or type `/buildproject` to proceed.",
                None,
            )

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

        try:
            # Build messages array with system prompt
            messages = [{"role": "system", "content": self._get_system_prompt()}]

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
                    max_completion_tokens=AI_MAX_COMPLETION_TOKENS,
                    temperature=AI_REFINEMENT_TEMPERATURE,
                    stream=True,
                ),
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
                    logger.info(
                        f"Extracted refined prompt ({len(refined_prompt)} chars)"
                    )

            logger.info(
                f"Completed streaming refinement response ({len(accumulated_response)} chars)"
            )
            yield (accumulated_response, True, refined_prompt)

        except Exception as e:
            logger.error(
                f"Failed to stream refinement response: {type(e).__name__}: {e}"
            )
            yield (
                f"⚠️ Error communicating with AI: {str(e)[:100]}. "
                "Your message has been saved. Try again or type `/buildproject` to proceed.",
                True,
                None,
            )

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

        try:
            extraction_prompt = get_required_prompt_template("prompt_extraction")
            extraction_system = get_required_prompt_template("prompt_extraction_system")

            messages = [{"role": "system", "content": extraction_system}]
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
                    max_completion_tokens=AI_MAX_COMPLETION_TOKENS,
                    temperature=AI_EXTRACTION_TEMPERATURE,
                    stream=False,
                ),
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

        try:
            extraction_prompt = get_required_prompt_template("prompt_extraction")
            extraction_system = get_required_prompt_template("prompt_extraction_system")

            messages = [{"role": "system", "content": extraction_system}]
            messages.extend(conversation_history)
            messages.append({"role": "user", "content": extraction_prompt})

            logger.info("Starting streaming prompt extraction from Azure OpenAI...")

            # Run synchronous streaming API call in thread pool
            loop = asyncio.get_event_loop()
            stream = await loop.run_in_executor(
                None,
                partial(
                    self.client.chat.completions.create,
                    model=self.deployment_name,
                    messages=messages,
                    max_completion_tokens=AI_MAX_COMPLETION_TOKENS,
                    temperature=AI_EXTRACTION_TEMPERATURE,
                    stream=True,
                ),
            )

            accumulated_response = ""

            # Process chunks from the stream
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    accumulated_response += content
                    yield accumulated_response

            if accumulated_response:
                logger.info(
                    f"Completed streaming extraction ({len(accumulated_response)} chars)"
                )
            else:
                logger.warning("Streaming extraction returned empty response")

        except Exception as e:
            logger.error(
                f"Failed to stream extract refined prompt: {type(e).__name__}: {e}"
            )

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
