"""
Repository naming module using Azure OpenAI for creative name generation.

This module provides functionality to generate creative, fun, and playful
repository names based on project descriptions using Azure OpenAI GPT models.
"""

import re
from typing import Optional, Protocol

from ..config import (
    AI_MAX_COMPLETION_TOKENS,
    get_prompt_template,
)
from .azure_openai_client import AzureOpenAIClient
from .logging import logger


# Constants
MAX_REPO_NAME_LENGTH = 30  # Keep creative names short to avoid Windows path limits
MAX_DESCRIPTION_LENGTH = 350


class NamingService(Protocol):
    """Protocol for repository naming services (enables dependency injection)."""

    def is_configured(self) -> bool:
        """Check if the naming service is properly configured.

        Returns:
            bool: True if the service is configured and ready to use, False otherwise.
        """
        ...

    def generate_name(self, project_description: str) -> Optional[str]:
        """Generate a creative repository name based on the project description.

        Args:
            project_description: A description of what the project does.

        Returns:
            Optional[str]: A creative repository name, or None if generation fails.
        """
        ...

    def generate_description(self, project_description: str) -> Optional[str]:
        """Generate a repository description based on the project description.

        Args:
            project_description: A description of what the project does.

        Returns:
            Optional[str]: A concise repository description, or None if generation fails.
        """
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
        # Use the shared Azure OpenAI client
        self._ai_client = AzureOpenAIClient(
            endpoint=endpoint,
            api_key=api_key,
            deployment_name=deployment_name,
            api_version=api_version,
        )

    # Proxy properties for backwards compatibility with tests
    @property
    def endpoint(self) -> Optional[str]:
        """Get the Azure OpenAI endpoint URL.

        Returns:
            Optional[str]: The Azure OpenAI endpoint URL, or None if not configured.
        """
        return self._ai_client.endpoint

    @property
    def api_key(self) -> Optional[str]:
        """Get the Azure OpenAI API key.

        Returns:
            Optional[str]: The Azure OpenAI API key, or None if not configured.
        """
        return self._ai_client.api_key

    @property
    def deployment_name(self) -> Optional[str]:
        """Get the Azure OpenAI deployment name.

        Returns:
            Optional[str]: The Azure OpenAI deployment name, or None if not configured.
        """
        return self._ai_client.deployment_name

    @property
    def api_version(self) -> Optional[str]:
        """Get the Azure OpenAI API version.

        Returns:
            Optional[str]: The Azure OpenAI API version, or None if not configured.
        """
        return self._ai_client.api_version

    @property
    def client(self):
        """Get the Azure OpenAI client instance.

        The client is lazy-loaded on first access.

        Returns:
            AzureOpenAI: The Azure OpenAI client instance.
        """
        return self._ai_client.client

    def is_configured(self) -> bool:
        """Check if Azure OpenAI integration is properly configured.

        Returns:
            bool: True if all required Azure OpenAI credentials are configured,
                False otherwise.
        """
        return self._ai_client.is_configured()

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

        raw_name = self._ai_client.complete_sync(
            messages=messages,
            max_tokens=AI_MAX_COMPLETION_TOKENS,
            log_prefix="Naming",
        )

        if not raw_name:
            return None

        sanitized_name = self._sanitize_name(raw_name)

        if not sanitized_name:
            logger.warning(f"Sanitization resulted in empty name from: {raw_name}")
            return None

        logger.info(f"Generated repository name: {sanitized_name}")
        return sanitized_name

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

        raw_description = self._ai_client.complete_sync(
            messages=messages,
            max_tokens=AI_MAX_COMPLETION_TOKENS,
            log_prefix="Description",
        )

        if not raw_description:
            return None

        sanitized_description = self._sanitize_description(raw_description)

        if not sanitized_description:
            logger.warning(
                f"Sanitization resulted in empty description from: {raw_description}"
            )
            return None

        logger.info(f"Generated repository description: {sanitized_description}")
        return sanitized_description


# Singleton instance for easy access
naming_generator = RepositoryNamingGenerator()
