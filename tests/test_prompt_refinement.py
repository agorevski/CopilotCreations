"""
Tests for prompt refinement service.
"""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.utils.prompt_refinement import (
    PromptRefinementService,
    get_refinement_service,
    reset_refinement_service,
)


class TestPromptRefinementService:
    """Tests for PromptRefinementService class."""

    @pytest.fixture
    def service(self):
        """Create a fresh refinement service for each test.

        Returns:
            PromptRefinementService: A new instance of the refinement service.
        """
        return PromptRefinementService()

    def test_is_configured_false_when_missing_endpoint(self, service):
        """Test is_configured returns False when endpoint is missing.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = None
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        assert not service.is_configured()

    def test_is_configured_false_when_missing_api_key(self, service):
        """Test is_configured returns False when API key is missing.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = None
        service.deployment_name = "test-deployment"

        assert not service.is_configured()

    def test_is_configured_false_when_missing_deployment(self, service):
        """Test is_configured returns False when deployment name is missing.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = None

        assert not service.is_configured()

    def test_is_configured_true_when_all_present(self, service):
        """Test is_configured returns True when all config is present.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        assert service.is_configured()

    @pytest.mark.asyncio
    async def test_get_refinement_response_not_configured(self, service):
        """Test response when service is not configured.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = None

        response, refined = await service.get_refinement_response([], "test message")

        assert "not configured" in response.lower()
        assert refined is None

    @pytest.mark.asyncio
    async def test_get_refinement_response_success(self, service):
        """Test successful refinement response.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = "Here are some clarifying questions..."
        mock_response.choices[0].message.refusal = None
        mock_response.choices[0].finish_reason = "stop"
        mock_client.chat.completions.create.return_value = mock_response

        # Patch the private _client attribute on the underlying AzureOpenAIClient
        service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            response, refined = await service.get_refinement_response(
                [], "Build a web app"
            )

        assert "clarifying questions" in response
        assert refined is None  # No "refined prompt ready" marker

    @pytest.mark.asyncio
    async def test_get_refinement_response_with_ready_marker(self, service):
        """Test response when refined prompt is ready.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "Here's your summary.\n\n"
            "📋 **Refined Prompt Ready** - Type `/buildproject` to create your project."
        )
        mock_response.choices[0].message.refusal = None
        mock_response.choices[0].finish_reason = "stop"
        mock_client.chat.completions.create.return_value = mock_response

        # Patch the private _client attribute on the underlying AzureOpenAIClient
        service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            with patch.object(
                service, "_extract_refined_prompt", return_value="Extracted prompt"
            ):
                response, refined = await service.get_refinement_response(
                    [{"role": "user", "content": "I want a React app"}],
                    "With authentication",
                )

        assert "Refined Prompt Ready" in response
        assert refined == "Extracted prompt"

    @pytest.mark.asyncio
    async def test_get_refinement_response_handles_error(self, service):
        """Test error handling in refinement response.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        # Patch the private _client attribute on the underlying AzureOpenAIClient
        service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            response, refined = await service.get_refinement_response([], "test")

        assert "trouble processing" in response.lower()
        assert refined is None

    @pytest.mark.asyncio
    async def test_generate_initial_questions(self, service):
        """Test generating initial questions.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = "1. What framework?\n2. What database?"
        mock_response.choices[0].message.refusal = None
        mock_response.choices[0].finish_reason = "stop"
        mock_client.chat.completions.create.return_value = mock_response

        # Patch the private _client attribute on the underlying AzureOpenAIClient
        service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            response = await service.generate_initial_questions("Build a web app")

        assert "framework" in response.lower() or "database" in response.lower()

    @pytest.mark.asyncio
    async def test_finalize_prompt_with_ai(self, service):
        """Test finalizing prompt with AI extraction.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        with patch.object(
            service, "_extract_refined_prompt", return_value="Final refined prompt"
        ):
            result = await service.finalize_prompt(
                [
                    {"role": "user", "content": "Build a web app"},
                    {"role": "assistant", "content": "What framework?"},
                    {"role": "user", "content": "React"},
                ]
            )

        assert result == "Final refined prompt"

    @pytest.mark.asyncio
    async def test_finalize_prompt_fallback(self, service):
        """Test finalizing prompt falls back to user messages.

        Args:
            service: The refinement service fixture.
        """
        service.endpoint = None  # Not configured

        result = await service.finalize_prompt(
            [
                {"role": "user", "content": "Build a web app"},
                {"role": "assistant", "content": "What framework?"},
                {"role": "user", "content": "React"},
            ]
        )

        assert "Build a web app" in result
        assert "React" in result

    def test_get_system_prompt(self, service):
        """Test getting system prompt from config.

        Args:
            service: The refinement service fixture.
        """
        custom_prompt = "You are a custom assistant."

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value=custom_prompt,
        ):
            prompt = service._get_system_prompt()

        assert prompt == custom_prompt


class TestSingletonRefinementService:
    """Tests for singleton refinement service access."""

    def setup_method(self):
        """Reset the singleton before each test.

        Ensures each test starts with a fresh singleton state.
        """
        reset_refinement_service()

    def teardown_method(self):
        """Reset the singleton after each test.

        Cleans up singleton state to avoid test pollution.
        """
        reset_refinement_service()

    def test_get_refinement_service_returns_same_instance(self):
        """Test that get_refinement_service returns the same instance.

        Verifies the singleton pattern is correctly implemented.
        """
        service1 = get_refinement_service()
        service2 = get_refinement_service()

        assert service1 is service2

    def test_reset_refinement_service(self):
        """Test that reset clears the singleton.

        Verifies reset creates a new instance on next access.
        """
        service1 = get_refinement_service()
        reset_refinement_service()
        service2 = get_refinement_service()

        assert service1 is not service2


class TestRefinementResponseEdgeCases:
    """Tests for edge cases in refinement response handling."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service.

        Returns:
            PromptRefinementService: A fully configured service instance.
        """
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service

    @pytest.mark.asyncio
    async def test_empty_response_with_finish_reason(self, configured_service):
        """Test handling of empty response with finish reason.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.refusal = None
        mock_response.choices[0].finish_reason = "length"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            response, refined = await configured_service.get_refinement_response(
                [], "test"
            )

        assert "trouble processing" in response
        assert refined is None

    @pytest.mark.asyncio
    async def test_empty_response_with_usage_info(self, configured_service):
        """Test handling of empty response with usage info.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.choices[0].message.refusal = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 0
        mock_client.chat.completions.create.return_value = mock_response

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            response, refined = await configured_service.get_refinement_response(
                [], "test"
            )

        assert "trouble processing" in response
        assert refined is None

    @pytest.mark.asyncio
    async def test_response_with_refusal(self, configured_service):
        """Test handling of response with refusal message.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I cannot help with that."
        mock_response.choices[0].message.refusal = "Content policy violation"
        mock_response.choices[0].finish_reason = "stop"
        mock_client.chat.completions.create.return_value = mock_response

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            response, refined = await configured_service.get_refinement_response(
                [], "test"
            )

        assert response == "I cannot help with that."

    @pytest.mark.asyncio
    async def test_response_with_no_choices(self, configured_service):
        """Test handling of response with no choices.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = []
        mock_client.chat.completions.create.return_value = mock_response

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            # This will raise an IndexError which gets caught
            response, refined = await configured_service.get_refinement_response(
                [], "test"
            )

        assert "trouble processing" in response.lower()


class TestExtractRefinedPrompt:
    """Tests for _extract_refined_prompt method."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service.

        Returns:
            PromptRefinementService: A fully configured service instance.
        """
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service

    @pytest.mark.asyncio
    async def test_extract_not_configured(self):
        """Test extraction when service is not configured.

        Verifies that extraction returns None when service lacks configuration.
        """
        service = PromptRefinementService()
        service.endpoint = None

        result = await service._extract_refined_prompt(
            [{"role": "user", "content": "test"}]
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_success(self, configured_service):
        """Test successful prompt extraction.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "# Project Spec\n\nBuild a React app"
        mock_client.chat.completions.create.return_value = mock_response

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="Extract the prompt",
        ):
            result = await configured_service._extract_refined_prompt(
                [
                    {"role": "user", "content": "Build a web app"},
                    {"role": "assistant", "content": "What framework?"},
                ]
            )

        assert result == "# Project Spec\n\nBuild a React app"

    @pytest.mark.asyncio
    async def test_extract_empty_response(self, configured_service):
        """Test extraction with empty response.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="Extract the prompt",
        ):
            result = await configured_service._extract_refined_prompt(
                [{"role": "user", "content": "Build a web app"}]
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_extract_handles_exception(self, configured_service):
        """Test extraction handles exceptions.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="Extract the prompt",
        ):
            result = await configured_service._extract_refined_prompt(
                [{"role": "user", "content": "Build a web app"}]
            )

        assert result is None


class TestFinalizePromptFallback:
    """Tests for finalize_prompt fallback behavior."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service.

        Returns:
            PromptRefinementService: A fully configured service instance.
        """
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service

    @pytest.mark.asyncio
    async def test_fallback_when_extraction_fails(self, configured_service):
        """Test fallback to user messages when extraction fails.

        Args:
            configured_service: The configured refinement service fixture.
        """
        with patch.object(
            configured_service, "_extract_refined_prompt", return_value=None
        ):
            result = await configured_service.finalize_prompt(
                [
                    {"role": "user", "content": "Build a web app"},
                    {"role": "assistant", "content": "What framework?"},
                    {"role": "user", "content": "React with TypeScript"},
                ]
            )

        # Should concatenate user messages
        assert "Build a web app" in result
        assert "React with TypeScript" in result
        # Assistant messages should not be included
        assert "What framework?" not in result


class TestClientLazyLoading:
    """Tests for client lazy loading behavior."""

    def test_client_not_created_when_not_configured(self):
        """Test that client is not created when not configured.

        Verifies that accessing client property returns None when unconfigured.
        """
        service = PromptRefinementService()
        service.endpoint = None
        service.api_key = None
        service.deployment_name = None

        client = service.client

        assert client is None

    def test_client_created_when_configured(self):
        """Test that client is created when configured.

        Verifies that accessing client property creates AzureOpenAI client.
        """
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"

        with patch("src.utils.azure_openai_client.AzureOpenAI") as mock_azure:
            mock_client = MagicMock()
            mock_azure.return_value = mock_client

            client = service.client

            assert client == mock_client
            mock_azure.assert_called_once()


class TestStreamRefinementResponse:
    """Tests for stream_refinement_response method."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service.

        Returns:
            PromptRefinementService: A fully configured service instance.
        """
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service

    @pytest.mark.asyncio
    async def test_stream_not_configured(self):
        """Test streaming response when service is not configured.

        Verifies that streaming yields error message when unconfigured.
        """
        service = PromptRefinementService()
        service.endpoint = None

        results = []
        async for chunk in service.stream_refinement_response([], "test message"):
            results.append(chunk)

        assert len(results) == 1
        response, is_complete, refined = results[0]
        assert "not configured" in response.lower()
        assert is_complete is True
        assert refined is None

    @pytest.mark.asyncio
    async def test_stream_success(self, configured_service):
        """Test successful streaming response.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()

        # Create mock stream chunks
        mock_chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
        ]
        mock_client.chat.completions.create.return_value = iter(mock_chunks)

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            results = []
            async for chunk in configured_service.stream_refinement_response(
                [], "Build a web app"
            ):
                results.append(chunk)

        # Should have streamed chunks plus final
        assert len(results) >= 3
        final_response, is_complete, refined = results[-1]
        assert is_complete is True
        assert "Hello world!" in final_response

    @pytest.mark.asyncio
    async def test_stream_empty_response(self, configured_service):
        """Test streaming with empty response.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()

        # Empty stream
        mock_client.chat.completions.create.return_value = iter([])

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            results = []
            async for chunk in configured_service.stream_refinement_response(
                [], "test"
            ):
                results.append(chunk)

        assert len(results) == 1
        response, is_complete, refined = results[0]
        assert "trouble processing" in response
        assert is_complete is True

    @pytest.mark.asyncio
    async def test_stream_with_refined_prompt_ready(self, configured_service):
        """Test streaming when refined prompt is ready.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()

        # Create mock stream chunks with "refined prompt ready" marker
        mock_chunks = [
            MagicMock(
                choices=[
                    MagicMock(delta=MagicMock(content="Summary of your project.\n\n"))
                ]
            ),
            MagicMock(
                choices=[
                    MagicMock(delta=MagicMock(content="📋 **Refined Prompt Ready**"))
                ]
            ),
        ]
        mock_client.chat.completions.create.return_value = iter(mock_chunks)

        configured_service._ai_client._client = mock_client

        # Mock the extraction streaming
        async def mock_stream_extract(*args):
            yield "Extracted prompt content"

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            with patch.object(
                configured_service,
                "_stream_extract_refined_prompt",
                side_effect=mock_stream_extract,
            ):
                results = []
                async for chunk in configured_service.stream_refinement_response(
                    [], "test"
                ):
                    results.append(chunk)

        # Final result should have refined prompt
        final_response, is_complete, refined = results[-1]
        assert refined == "Extracted prompt content"

    @pytest.mark.asyncio
    async def test_stream_handles_exception(self, configured_service):
        """Test streaming handles exceptions.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="You are an assistant",
        ):
            results = []
            async for chunk in configured_service.stream_refinement_response(
                [], "test"
            ):
                results.append(chunk)

        assert len(results) == 1
        response, is_complete, refined = results[0]
        assert "trouble processing" in response.lower()
        assert is_complete is True


class TestStreamExtractRefinedPrompt:
    """Tests for _stream_extract_refined_prompt method."""

    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service.

        Returns:
            PromptRefinementService: A fully configured service instance.
        """
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service

    @pytest.mark.asyncio
    async def test_stream_extract_not_configured(self):
        """Test streaming extraction when not configured.

        Verifies that streaming extraction yields nothing when unconfigured.
        """
        service = PromptRefinementService()
        service.endpoint = None

        results = []
        async for chunk in service._stream_extract_refined_prompt([]):
            results.append(chunk)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_stream_extract_success(self, configured_service):
        """Test successful streaming extraction.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()

        # Create mock stream chunks
        mock_chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="# Project"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" Spec"))]),
        ]
        mock_client.chat.completions.create.return_value = iter(mock_chunks)

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="Extract the prompt",
        ):
            results = []
            async for chunk in configured_service._stream_extract_refined_prompt(
                [{"role": "user", "content": "Build a web app"}]
            ):
                results.append(chunk)

        assert len(results) == 2
        assert results[-1] == "# Project Spec"

    @pytest.mark.asyncio
    async def test_stream_extract_empty_response(self, configured_service):
        """Test streaming extraction with empty response.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = iter([])

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="Extract the prompt",
        ):
            results = []
            async for chunk in configured_service._stream_extract_refined_prompt([]):
                results.append(chunk)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_stream_extract_handles_exception(self, configured_service):
        """Test streaming extraction handles exceptions.

        Args:
            configured_service: The configured refinement service fixture.
        """
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        configured_service._ai_client._client = mock_client

        with patch(
            "src.utils.prompt_refinement.get_required_prompt_template",
            return_value="Extract the prompt",
        ):
            results = []
            async for chunk in configured_service._stream_extract_refined_prompt([]):
                results.append(chunk)

        # Should complete without yielding anything on error
        assert len(results) == 0
