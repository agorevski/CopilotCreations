"""
Tests for repository naming utilities using Azure OpenAI.

This module tests the RepositoryNamingGenerator class which generates
creative repository names and descriptions using Azure OpenAI GPT models.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest

from src.utils.naming import RepositoryNamingGenerator, MAX_DESCRIPTION_LENGTH


class TestRepositoryNamingGeneratorInit:
    """Tests for RepositoryNamingGenerator initialization and configuration."""

    def test_init_and_configuration(self):
        """
        Tests initialization and is_configured method:
        - Loads configuration values from environment
        - Works with missing/None config values
        - is_configured returns True only when all values present
        - is_configured False with empty strings
        - Accepts custom credentials (dependency injection)
        - Defaults to config values when not provided
        """
        # Loads config
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.endpoint == "https://test.openai.azure.com/"
            assert generator.api_key == "test_key"
            assert generator.deployment_name == "gpt-52"
            assert generator.is_configured() is True

        # Works with missing config
        with (
            patch("src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", None),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.endpoint is None
            assert generator.is_configured() is False

        # is_configured False with missing endpoint, key, or deployment
        for missing in ["endpoint", "key", "deployment"]:
            patches = {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_API_KEY": "test_key",
                "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-52",
            }
            if missing == "endpoint":
                patches["AZURE_OPENAI_ENDPOINT"] = None
            elif missing == "key":
                patches["AZURE_OPENAI_API_KEY"] = None
            else:
                patches["AZURE_OPENAI_DEPLOYMENT_NAME"] = None

            with (
                patch(
                    "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                    patches["AZURE_OPENAI_ENDPOINT"],
                ),
                patch(
                    "src.utils.azure_openai_client.AZURE_OPENAI_API_KEY",
                    patches["AZURE_OPENAI_API_KEY"],
                ),
                patch(
                    "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME",
                    patches["AZURE_OPENAI_DEPLOYMENT_NAME"],
                ),
            ):
                generator = RepositoryNamingGenerator()
                assert generator.is_configured() is False

        # is_configured False with empty strings
        with (
            patch("src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT", ""),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", ""),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", ""),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.is_configured() is False

        # Custom credentials
        generator = RepositoryNamingGenerator(
            endpoint="https://custom.openai.azure.com/",
            api_key="custom_key",
            deployment_name="custom-deploy",
            api_version="2024-01-01",
        )
        assert generator.endpoint == "https://custom.openai.azure.com/"
        assert generator.api_key == "custom_key"
        assert generator.deployment_name == "custom-deploy"
        assert generator.api_version == "2024-01-01"

        # Defaults to config
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://default.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "default_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME",
                "default-deploy",
            ),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.endpoint == "https://default.openai.azure.com/"


class TestClientProperty:
    """Tests for the client property lazy loading behavior."""

    def test_client_property(self):
        """
        Tests client property:
        - Returns None when not configured
        - Lazy loads client on first access
        - Caches client (only creates once)
        """
        # Returns None when not configured
        with (
            patch("src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", None),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.client is None

        # Lazy loads and caches
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch("src.utils.azure_openai_client.AzureOpenAI") as mock_client,
        ):
            generator = RepositoryNamingGenerator()
            _ = generator.client
            _ = generator.client  # Second access
            mock_client.assert_called_once()  # Only created once


class TestSanitizeName:
    """Tests for the _sanitize_name method which cleans repository names."""

    def test_sanitize_name(self):
        """
        Tests name sanitization:
        - Removes quotes (single and double)
        - Converts to lowercase
        - Replaces spaces with hyphens
        - Replaces underscores with hyphens
        - Removes special characters
        - Collapses consecutive hyphens
        - Removes leading/trailing hyphens
        - Limits length to 50 characters
        - Handles empty input
        """
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
        ):
            generator = RepositoryNamingGenerator()

            # Removes quotes
            assert generator._sanitize_name('"pixel-wizard"') == "pixel-wizard"
            assert generator._sanitize_name("'turbo-toaster'") == "turbo-toaster"

            # Converts to lowercase
            assert generator._sanitize_name("Pixel-WIZARD") == "pixel-wizard"

            # Replaces spaces with hyphens
            assert generator._sanitize_name("pixel wizard") == "pixel-wizard"

            # Replaces underscores with hyphens
            assert generator._sanitize_name("pixel_wizard") == "pixel-wizard"

            # Removes special characters
            assert generator._sanitize_name("pixel@wizard!") == "pixelwizard"

            # Collapses consecutive hyphens
            assert generator._sanitize_name("pixel---wizard") == "pixel-wizard"

            # Removes leading/trailing hyphens
            assert generator._sanitize_name("-pixel-wizard-") == "pixel-wizard"

            # Limits length to 50
            assert len(generator._sanitize_name("a" * 100)) <= 50

            # Handles empty input
            assert generator._sanitize_name("") == ""
            assert generator._sanitize_name("   ") == ""


class TestGenerateName:
    """Tests for the generate_name method."""

    def test_generate_name(self):
        """
        Tests generate_name method:
        - Returns None when not configured
        - Successfully generates and sanitizes names
        - Handles quotes in API response
        - Returns None for empty/None response
        - Returns None when sanitization results in empty
        - Handles API exceptions gracefully
        - Uses default prompt when template missing
        - Passes correct GPT 5.2 parameters
        """
        # Not configured
        with (
            patch("src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", None),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_name("A todo list app") is None

        # Success case
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "task-master-pro"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch(
                "src.utils.naming.get_prompt_template",
                return_value="Generate a name for:",
            ),
        ):
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            assert result == "task-master-pro"

            # Verify GPT 5.2 parameters
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "gpt-52"
            assert call_kwargs["max_completion_tokens"] == 50000
            assert "max_tokens" not in call_kwargs  # Deprecated param not used
            # temperature is now passed through AzureOpenAIClient

        # Handles quotes in response
        mock_response.choices[0].message.content = '"pixel-wizard"'
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch(
                "src.utils.naming.get_prompt_template",
                return_value="Generate a name for:",
            ),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_name("Image library") == "pixel-wizard"

        # Empty/None response
        mock_response.choices[0].message.content = None
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value="Generate:"),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_name("Test") is None

        # Sanitization results in empty
        mock_response.choices[0].message.content = "@@@!!!"
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value="Generate:"),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_name("Test") is None

        # API exception
        mock_client.chat.completions.create.side_effect = Exception("API error")
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value="Generate:"),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_name("Test") is None

        # Uses default prompt when template missing
        mock_client.chat.completions.create.side_effect = None
        mock_response.choices[0].message.content = "cool-project"
        mock_client.chat.completions.create.return_value = mock_response

        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value=""),
        ):  # Empty template
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            assert result == "cool-project"
            assert (
                "A todo list app"
                in mock_client.chat.completions.create.call_args[1]["messages"][1][
                    "content"
                ]
            )


class TestGenerateDescription:
    """Tests for generate_description method."""

    def test_generate_description(self):
        """
        Tests generate_description method:
        - Returns None when not configured
        - Successfully generates description
        - Returns None for empty response
        - Returns None when sanitization results in empty (whitespace-only)
        - Handles API exceptions gracefully
        - Uses default prompt when template missing
        """
        # Not configured
        with (
            patch("src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", None),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", None),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_description("A todo list app") is None

        # Success case
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "A modern todo list application."

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch(
                "src.utils.naming.get_prompt_template",
                return_value="Generate description:",
            ),
        ):
            generator = RepositoryNamingGenerator()
            assert (
                generator.generate_description("A todo list app")
                == "A modern todo list application."
            )

        # Empty response
        mock_response.choices[0].message.content = ""
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value="Generate:"),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_description("Test") is None

        # Whitespace-only response
        mock_response.choices[0].message.content = "   "
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value="Generate:"),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_description("Test") is None

        # API exception
        mock_client.chat.completions.create.side_effect = Exception("API error")
        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value="Generate:"),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_description("Test") is None

        # Uses default prompt when template missing
        mock_client.chat.completions.create.side_effect = None
        mock_response.choices[0].message.content = "A cool project"
        mock_client.chat.completions.create.return_value = mock_response

        with (
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT",
                "https://test.openai.azure.com/",
            ),
            patch("src.utils.azure_openai_client.AZURE_OPENAI_API_KEY", "test_key"),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-52"
            ),
            patch(
                "src.utils.azure_openai_client.AZURE_OPENAI_API_VERSION",
                "2025-01-01-preview",
            ),
            patch(
                "src.utils.azure_openai_client.AzureOpenAI", return_value=mock_client
            ),
            patch("src.utils.naming.get_prompt_template", return_value=""),
        ):
            generator = RepositoryNamingGenerator()
            assert generator.generate_description("A todo list app") == "A cool project"


class TestSanitizeDescription:
    """Tests for _sanitize_description method."""

    def test_sanitize_description(self):
        """
        Tests description sanitization:
        - Removes quotes
        - Removes control characters
        - Truncates long descriptions (>350 chars) with ...
        """
        with patch("src.utils.azure_openai_client.AZURE_OPENAI_ENDPOINT", None):
            generator = RepositoryNamingGenerator()

            # Removes quotes
            assert (
                generator._sanitize_description('"A cool project"') == "A cool project"
            )

            # Removes control chars
            result = generator._sanitize_description("A project\x00\x01\x02")
            assert "\x00" not in result
            assert "A project" in result

            # Truncates long descriptions
            long_desc = "x" * 400
            result = generator._sanitize_description(long_desc)
            assert len(result) <= MAX_DESCRIPTION_LENGTH
            assert result.endswith("...")


class TestNamingConstants:
    """Tests for naming module constants and singleton."""

    def test_constants_and_singleton(self):
        """
        Tests naming constants:
        - MAX_REPO_NAME_LENGTH is 50
        - MAX_DESCRIPTION_LENGTH is 350
        - naming_generator singleton exists and is correct type
        """
        from src.utils.naming import MAX_REPO_NAME_LENGTH, naming_generator

        assert isinstance(MAX_REPO_NAME_LENGTH, int)
        assert (
            MAX_REPO_NAME_LENGTH == 30
        )  # Reduced from 50 to avoid Windows path length issues

        assert isinstance(MAX_DESCRIPTION_LENGTH, int)
        assert MAX_DESCRIPTION_LENGTH == 350

        assert naming_generator is not None
        assert isinstance(naming_generator, RepositoryNamingGenerator)
