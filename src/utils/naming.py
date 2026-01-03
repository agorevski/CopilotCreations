"""
Repository naming module using Azure OpenAI for creative name generation.

This module provides functionality to generate creative, fun, and playful
repository names based on project descriptions using Azure OpenAI GPT models.
"""

import re
from typing import Optional, Protocol

from openai import AzureOpenAI

from ..config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_VERSION,
    AI_MAX_COMPLETION_TOKENS,
    get_prompt_template,
)
from .logging import logger


# Constants
MAX_REPO_NAME_LENGTH = 30  # Keep creative names short to avoid Windows path limits
MAX_DESCRIPTION_LENGTH = 350


class NamingService(Protocol):
    """Protocol for repository naming services (enables dependency injection)."""

    def is_configured(self) -> bool:
        """Check if the naming service is properly configured."""
        ...

    def generate_name(self, project_description: str) -> Optional[str]:
        """Generate a creative repository name based on the project description."""
        ...

    def generate_description(self, project_description: str) -> Optional[str]:
        """Generate a repository description based on the project description."""
        ...


class RepositoryNamingGenerator:
    """Generates creative repository names using Azure OpenAI."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment_name: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        """Initialize the naming generator with Azure OpenAI credentials.

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

    def _sanitize_name(self, name: str) -> str:
        """Sanitize the generated name to be a valid repository name.

        Args:
            name: The raw generated name from the AI model.

        Returns:
            A sanitized name suitable for a repository.
        """
        # Remove any quotes, extra whitespace, and trim
        name = name.strip().strip("\"'").strip()

        # Convert to lowercase
        name = name.lower()

        # Replace spaces and underscores with hyphens
        name = re.sub(r"[\s_]+", "-", name)

        # Remove any characters that aren't alphanumeric or hyphens
        name = re.sub(r"[^a-z0-9\-]", "", name)

        # Remove consecutive hyphens
        name = re.sub(r"-+", "-", name)

        # Remove leading/trailing hyphens
        name = name.strip("-")

        # Limit length to MAX_REPO_NAME_LENGTH characters
        if len(name) > MAX_REPO_NAME_LENGTH:
            name = name[:MAX_REPO_NAME_LENGTH].rstrip("-")

        return name

    def _sanitize_description(self, description: str) -> str:
        """Sanitize the generated description for GitHub.

        Args:
            description: The raw generated description from the AI model.

        Returns:
            A sanitized description suitable for a GitHub repository.
        """
        # Remove any quotes and trim whitespace
        description = description.strip().strip("\"'").strip()

        # Remove control characters and non-printable characters
        description = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", description)

        # Replace multiple whitespace with single space
        description = re.sub(r"\s+", " ", description)

        # Remove any emoji or special unicode characters that GitHub might reject
        # Keep only ASCII printable characters and common unicode letters
        description = "".join(
            char
            for char in description
            if ord(char) < 128 or char.isalnum() or char.isspace()
        )

        # Truncate to GitHub's max length
        if len(description) > MAX_DESCRIPTION_LENGTH:
            description = description[: MAX_DESCRIPTION_LENGTH - 3].rstrip() + "..."

        return description

    def generate_name(self, project_description: str) -> Optional[str]:
        """Generate a creative repository name based on the project description.

        Args:
            project_description: A description of what the project does.

        Returns:
            A creative repository name, or None if generation fails.
        """
        if not self.is_configured():
            logger.warning("Azure OpenAI not configured for repository naming")
            return None

        try:
            # Get the naming prompt from config
            prompt_template = get_prompt_template("repository_naming_prompt")
            if not prompt_template:
                prompt_template = (
                    "Generate a single creative, fun, and playful repository name. "
                    "Respond with ONLY the name, nothing else. Project description:"
                )

            full_prompt = f"{prompt_template} {project_description}"

            logger.info("Generating creative repository name using Azure OpenAI...")

            messages = [
                {
                    "role": "system",
                    "content": "You are a creative naming assistant. You generate short, memorable, fun repository names.",
                },
                {"role": "user", "content": full_prompt},
            ]

            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_completion_tokens=AI_MAX_COMPLETION_TOKENS,
                stop=None,
                stream=False,
            )

            raw_name = response.choices[0].message.content
            logger.info(f"GPT Response (naming): {raw_name}")
            if not raw_name:
                logger.warning("Azure OpenAI returned empty response")
                return None

            sanitized_name = self._sanitize_name(raw_name)

            if not sanitized_name:
                logger.warning(f"Sanitization resulted in empty name from: {raw_name}")
                return None

            logger.info(f"Generated repository name: {sanitized_name}")
            return sanitized_name

        except Exception as e:
            logger.error(f"Failed to generate repository name: {type(e).__name__}: {e}")
            return None

    def generate_description(self, project_description: str) -> Optional[str]:
        """Generate a repository description based on the project description.

        Args:
            project_description: A description of what the project does.

        Returns:
            A concise repository description, or None if generation fails.
        """
        if not self.is_configured():
            logger.warning("Azure OpenAI not configured for description generation")
            return None

        try:
            # Get the description prompt from config
            prompt_template = get_prompt_template("repository_description_prompt")
            if not prompt_template:
                prompt_template = (
                    "Generate a brief, professional description for a GitHub repository. "
                    "Keep it under 200 characters. Respond with ONLY the description. "
                    "Project description:"
                )

            full_prompt = f"{prompt_template} {project_description}"

            logger.info("Generating repository description using Azure OpenAI...")

            messages = [
                {
                    "role": "system",
                    "content": "You are a technical writer. You generate concise, professional repository descriptions.",
                },
                {"role": "user", "content": full_prompt},
            ]

            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_completion_tokens=AI_MAX_COMPLETION_TOKENS,
                stop=None,
                stream=False,
            )

            raw_description = response.choices[0].message.content
            logger.info(f"GPT Response (description): {raw_description}")
            if not raw_description:
                logger.warning("Azure OpenAI returned empty description")
                return None

            sanitized_description = self._sanitize_description(raw_description)

            if not sanitized_description:
                logger.warning(
                    f"Sanitization resulted in empty description from: {raw_description}"
                )
                return None

            logger.info(f"Generated repository description: {sanitized_description}")
            return sanitized_description

        except Exception as e:
            logger.error(
                f"Failed to generate repository description: {type(e).__name__}: {e}"
            )
            return None


# Singleton instance for easy access
naming_generator = RepositoryNamingGenerator()
