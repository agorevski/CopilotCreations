"""
Azure OpenAI client wrapper with common helper methods.

This module provides a unified interface for Azure OpenAI API calls,
consolidating duplicated patterns across naming.py and prompt_refinement.py.
"""

import asyncio
from functools import partial
from typing import List, Dict, Optional, AsyncGenerator

from openai import AzureOpenAI

from ..config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_VERSION,
    AI_MAX_COMPLETION_TOKENS,
    AI_REFINEMENT_TEMPERATURE,
    AI_EXTRACTION_TEMPERATURE,
)
from .logging import logger


class AzureOpenAIClient:
    """Wrapper for Azure OpenAI API with common helper methods."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment_name: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        """Initialize the Azure OpenAI client.

        Args:
            endpoint: Azure OpenAI endpoint URL. Defaults to config value.
            api_key: Azure OpenAI API key. Defaults to config value.
            deployment_name: Azure OpenAI deployment name. Defaults to config value.
            api_version: Azure OpenAI API version. Defaults to config value.
        """
        self.endpoint = endpoint or AZURE_OPENAI_ENDPOINT
        self.api_key = api_key or AZURE_OPENAI_API_KEY
        self.deployment_name = deployment_name or AZURE_OPENAI_DEPLOYMENT_NAME
        self.api_version = api_version or AZURE_OPENAI_API_VERSION
        self._client: Optional[AzureOpenAI] = None

    @property
    def client(self) -> Optional[AzureOpenAI]:
        """Lazy-load the Azure OpenAI client.

        Returns:
            The Azure OpenAI client instance, or None if not configured.
        """
        if self._client is None and self.is_configured():
            self._client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.api_key,
                api_version=self.api_version,
            )
        return self._client

    def is_configured(self) -> bool:
        """Check if Azure OpenAI integration is properly configured.

        Returns:
            True if endpoint, api_key, and deployment_name are all set,
            False otherwise.
        """
        return bool(self.endpoint and self.api_key and self.deployment_name)

    def complete_sync(
        self,
        messages: List[Dict[str, str]],
        temperature: float = AI_REFINEMENT_TEMPERATURE,
        max_tokens: int = AI_MAX_COMPLETION_TOKENS,
        log_prefix: str = "GPT",
    ) -> Optional[str]:
        """Make a synchronous chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature. Defaults to AI_REFINEMENT_TEMPERATURE.
            max_tokens: Maximum completion tokens. Defaults to AI_MAX_COMPLETION_TOKENS.
            log_prefix: Prefix for log messages.

        Returns:
            The assistant's response content, or None if the call fails.
        """
        if not self.is_configured():
            logger.warning("Azure OpenAI not configured")
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
                stream=False,
            )

            content = response.choices[0].message.content
            logger.info(f"{log_prefix} Response: {content}")

            if not content:
                logger.warning(f"{log_prefix}: Azure OpenAI returned empty response")
                return None

            return content

        except Exception as e:
            logger.error(f"{log_prefix} API call failed: {type(e).__name__}: {e}")
            return None

    async def complete_async(
        self,
        messages: List[Dict[str, str]],
        temperature: float = AI_REFINEMENT_TEMPERATURE,
        max_tokens: int = AI_MAX_COMPLETION_TOKENS,
        log_prefix: str = "GPT",
    ) -> Optional[str]:
        """Make an asynchronous chat completion request.

        Runs the synchronous OpenAI call in a thread pool executor.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature. Defaults to AI_REFINEMENT_TEMPERATURE.
            max_tokens: Maximum completion tokens. Defaults to AI_MAX_COMPLETION_TOKENS.
            log_prefix: Prefix for log messages.

        Returns:
            The assistant's response content, or None if the call fails.
        """
        if not self.is_configured():
            logger.warning("Azure OpenAI not configured")
            return None

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                partial(
                    self.client.chat.completions.create,
                    model=self.deployment_name,
                    messages=messages,
                    max_completion_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                ),
            )

            # Log response details for debugging
            if response.choices:
                choice = response.choices[0]
                logger.info(f"{log_prefix} - finish_reason: {choice.finish_reason}")
                if choice.message:
                    content_len = (
                        len(choice.message.content) if choice.message.content else 0
                    )
                    logger.info(f"{log_prefix} - content length: {content_len}")
                    if choice.message.refusal:
                        logger.warning(
                            f"{log_prefix} - refusal: {choice.message.refusal}"
                        )
            else:
                logger.warning(f"{log_prefix} - no choices returned")

            content = response.choices[0].message.content
            logger.info(f"{log_prefix} Response: {content}")

            if not content:
                logger.warning(f"{log_prefix}: Azure OpenAI returned empty response")
                if response.choices[0].finish_reason:
                    logger.warning(
                        f"Finish reason: {response.choices[0].finish_reason}"
                    )
                if hasattr(response, "usage") and response.usage:
                    logger.warning(
                        f"Token usage - prompt: {response.usage.prompt_tokens}, "
                        f"completion: {response.usage.completion_tokens}"
                    )
                return None

            return content

        except Exception as e:
            logger.error(f"{log_prefix} API call failed: {type(e).__name__}: {e}")
            return None

    async def stream_async(
        self,
        messages: List[Dict[str, str]],
        temperature: float = AI_REFINEMENT_TEMPERATURE,
        max_tokens: int = AI_MAX_COMPLETION_TOKENS,
        log_prefix: str = "GPT",
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion response asynchronously.

        Runs the synchronous OpenAI streaming call in a thread pool executor,
        then yields accumulated content as chunks arrive.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature. Defaults to AI_REFINEMENT_TEMPERATURE.
            max_tokens: Maximum completion tokens. Defaults to AI_MAX_COMPLETION_TOKENS.
            log_prefix: Prefix for log messages.

        Yields:
            Accumulated response content as chunks arrive.
        """
        if not self.is_configured():
            logger.warning("Azure OpenAI not configured")
            return

        try:
            logger.info(f"{log_prefix}: Starting streaming request...")

            loop = asyncio.get_event_loop()
            stream = await loop.run_in_executor(
                None,
                partial(
                    self.client.chat.completions.create,
                    model=self.deployment_name,
                    messages=messages,
                    max_completion_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                ),
            )

            accumulated_response = ""

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    accumulated_response += content
                    yield accumulated_response

            if accumulated_response:
                logger.info(
                    f"{log_prefix}: Completed streaming ({len(accumulated_response)} chars)"
                )
            else:
                logger.warning(f"{log_prefix}: Streaming returned empty response")

        except Exception as e:
            logger.error(f"{log_prefix} streaming failed: {type(e).__name__}: {e}")


# Singleton instance for easy access
_azure_openai_client: Optional[AzureOpenAIClient] = None


def get_azure_openai_client() -> AzureOpenAIClient:
    """Get the singleton Azure OpenAI client instance.

    Returns:
        The Azure OpenAI client instance.
    """
    global _azure_openai_client
    if _azure_openai_client is None:
        _azure_openai_client = AzureOpenAIClient()
    return _azure_openai_client


def reset_azure_openai_client() -> None:
    """Reset the Azure OpenAI client singleton instance.

    This is useful for testing to ensure a fresh client is created
    on the next call to get_azure_openai_client().

    Returns:
        None
    """
    global _azure_openai_client
    _azure_openai_client = None
