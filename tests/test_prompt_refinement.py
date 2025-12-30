"""
Tests for prompt refinement service.
"""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.utils.prompt_refinement import (
    PromptRefinementService,
    get_refinement_service,
    reset_refinement_service,
    DEFAULT_REFINEMENT_SYSTEM_PROMPT,
)


class TestPromptRefinementService:
    """Tests for PromptRefinementService class."""
    
    @pytest.fixture
    def service(self):
        """Create a fresh refinement service for each test."""
        return PromptRefinementService()
    
    def test_is_configured_false_when_missing_endpoint(self, service):
        """Test is_configured returns False when endpoint is missing."""
        service.endpoint = None
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        
        assert not service.is_configured()
    
    def test_is_configured_false_when_missing_api_key(self, service):
        """Test is_configured returns False when API key is missing."""
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = None
        service.deployment_name = "test-deployment"
        
        assert not service.is_configured()
    
    def test_is_configured_false_when_missing_deployment(self, service):
        """Test is_configured returns False when deployment name is missing."""
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = None
        
        assert not service.is_configured()
    
    def test_is_configured_true_when_all_present(self, service):
        """Test is_configured returns True when all config is present."""
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        
        assert service.is_configured()
    
    @pytest.mark.asyncio
    async def test_get_refinement_response_not_configured(self, service):
        """Test response when service is not configured."""
        service.endpoint = None
        
        response, refined = await service.get_refinement_response([], "test message")
        
        assert "not configured" in response.lower()
        assert refined is None
    
    @pytest.mark.asyncio
    async def test_get_refinement_response_success(self, service):
        """Test successful refinement response."""
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Here are some clarifying questions..."
        mock_client.chat.completions.create.return_value = mock_response
        
        # Patch the private _client attribute instead of the property
        service._client = mock_client
        
        response, refined = await service.get_refinement_response([], "Build a web app")
        
        assert "clarifying questions" in response
        assert refined is None  # No "refined prompt ready" marker
    
    @pytest.mark.asyncio
    async def test_get_refinement_response_with_ready_marker(self, service):
        """Test response when refined prompt is ready."""
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
        mock_client.chat.completions.create.return_value = mock_response
        
        # Patch the private _client attribute instead of the property
        service._client = mock_client
        
        with patch.object(service, '_extract_refined_prompt', return_value="Extracted prompt"):
            response, refined = await service.get_refinement_response(
                [{"role": "user", "content": "I want a React app"}],
                "With authentication"
            )
        
        assert "Refined Prompt Ready" in response
        assert refined == "Extracted prompt"
    
    @pytest.mark.asyncio
    async def test_get_refinement_response_handles_error(self, service):
        """Test error handling in refinement response."""
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Patch the private _client attribute instead of the property
        service._client = mock_client
        
        response, refined = await service.get_refinement_response([], "test")
        
        assert "error" in response.lower()
        assert refined is None
    
    @pytest.mark.asyncio
    async def test_generate_initial_questions(self, service):
        """Test generating initial questions."""
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "1. What framework?\n2. What database?"
        mock_client.chat.completions.create.return_value = mock_response
        
        # Patch the private _client attribute instead of the property
        service._client = mock_client
        
        response = await service.generate_initial_questions("Build a web app")
        
        assert "framework" in response.lower() or "database" in response.lower()
    
    @pytest.mark.asyncio
    async def test_finalize_prompt_with_ai(self, service):
        """Test finalizing prompt with AI extraction."""
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        
        with patch.object(service, '_extract_refined_prompt', return_value="Final refined prompt"):
            result = await service.finalize_prompt([
                {"role": "user", "content": "Build a web app"},
                {"role": "assistant", "content": "What framework?"},
                {"role": "user", "content": "React"}
            ])
        
        assert result == "Final refined prompt"
    
    @pytest.mark.asyncio
    async def test_finalize_prompt_fallback(self, service):
        """Test finalizing prompt falls back to user messages."""
        service.endpoint = None  # Not configured
        
        result = await service.finalize_prompt([
            {"role": "user", "content": "Build a web app"},
            {"role": "assistant", "content": "What framework?"},
            {"role": "user", "content": "React"}
        ])
        
        assert "Build a web app" in result
        assert "React" in result
    
    def test_get_system_prompt_default(self, service):
        """Test getting default system prompt."""
        with patch('src.utils.prompt_refinement.get_prompt_template', return_value=""):
            prompt = service._get_system_prompt()
        
        assert prompt == DEFAULT_REFINEMENT_SYSTEM_PROMPT
    
    def test_get_system_prompt_custom(self, service):
        """Test getting custom system prompt from config."""
        custom_prompt = "You are a custom assistant."
        
        with patch('src.utils.prompt_refinement.get_prompt_template', return_value=custom_prompt):
            prompt = service._get_system_prompt()
        
        assert prompt == custom_prompt


class TestSingletonRefinementService:
    """Tests for singleton refinement service access."""
    
    def setup_method(self):
        """Reset the singleton before each test."""
        reset_refinement_service()
    
    def teardown_method(self):
        """Reset the singleton after each test."""
        reset_refinement_service()
    
    def test_get_refinement_service_returns_same_instance(self):
        """Test that get_refinement_service returns the same instance."""
        service1 = get_refinement_service()
        service2 = get_refinement_service()
        
        assert service1 is service2
    
    def test_reset_refinement_service(self):
        """Test that reset clears the singleton."""
        service1 = get_refinement_service()
        reset_refinement_service()
        service2 = get_refinement_service()
        
        assert service1 is not service2


class TestRefinementResponseEdgeCases:
    """Tests for edge cases in refinement response handling."""
    
    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service."""
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service
    
    @pytest.mark.asyncio
    async def test_empty_response_with_finish_reason(self, configured_service):
        """Test handling of empty response with finish reason (line 155-157)."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.refusal = None
        mock_response.choices[0].finish_reason = "length"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response
        
        configured_service._client = mock_client
        
        response, refined = await configured_service.get_refinement_response([], "test")
        
        assert "trouble processing" in response
        assert refined is None
    
    @pytest.mark.asyncio
    async def test_empty_response_with_usage_info(self, configured_service):
        """Test handling of empty response with usage info (line 158-159)."""
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
        
        configured_service._client = mock_client
        
        response, refined = await configured_service.get_refinement_response([], "test")
        
        assert "trouble processing" in response
        assert refined is None
    
    @pytest.mark.asyncio
    async def test_response_with_refusal(self, configured_service):
        """Test handling of response with refusal message (line 146-147)."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I cannot help with that."
        mock_response.choices[0].message.refusal = "Content policy violation"
        mock_response.choices[0].finish_reason = "stop"
        mock_client.chat.completions.create.return_value = mock_response
        
        configured_service._client = mock_client
        
        response, refined = await configured_service.get_refinement_response([], "test")
        
        assert response == "I cannot help with that."
    
    @pytest.mark.asyncio
    async def test_response_with_no_choices(self, configured_service):
        """Test handling of response with no choices (line 148-149)."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = []
        mock_client.chat.completions.create.return_value = mock_response
        
        configured_service._client = mock_client
        
        # This will raise an IndexError which gets caught
        response, refined = await configured_service.get_refinement_response([], "test")
        
        assert "error" in response.lower()


class TestExtractRefinedPrompt:
    """Tests for _extract_refined_prompt method."""
    
    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service."""
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service
    
    @pytest.mark.asyncio
    async def test_extract_not_configured(self):
        """Test extraction when service is not configured (line 194-195)."""
        service = PromptRefinementService()
        service.endpoint = None
        
        result = await service._extract_refined_prompt([{"role": "user", "content": "test"}])
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_extract_success(self, configured_service):
        """Test successful prompt extraction (lines 197-295)."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "# Project Spec\n\nBuild a React app"
        mock_client.chat.completions.create.return_value = mock_response
        
        configured_service._client = mock_client
        
        result = await configured_service._extract_refined_prompt([
            {"role": "user", "content": "Build a web app"},
            {"role": "assistant", "content": "What framework?"}
        ])
        
        assert result == "# Project Spec\n\nBuild a React app"
    
    @pytest.mark.asyncio
    async def test_extract_empty_response(self, configured_service):
        """Test extraction with empty response (line 287-289)."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response
        
        configured_service._client = mock_client
        
        result = await configured_service._extract_refined_prompt([
            {"role": "user", "content": "Build a web app"}
        ])
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_extract_handles_exception(self, configured_service):
        """Test extraction handles exceptions (line 293-295)."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        configured_service._client = mock_client
        
        result = await configured_service._extract_refined_prompt([
            {"role": "user", "content": "Build a web app"}
        ])
        
        assert result is None


class TestFinalizePromptFallback:
    """Tests for finalize_prompt fallback behavior."""
    
    @pytest.fixture
    def configured_service(self):
        """Create a configured refinement service."""
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        return service
    
    @pytest.mark.asyncio
    async def test_fallback_when_extraction_fails(self, configured_service):
        """Test fallback to user messages when extraction fails (lines 330-335)."""
        with patch.object(configured_service, '_extract_refined_prompt', return_value=None):
            result = await configured_service.finalize_prompt([
                {"role": "user", "content": "Build a web app"},
                {"role": "assistant", "content": "What framework?"},
                {"role": "user", "content": "React with TypeScript"}
            ])
        
        # Should concatenate user messages
        assert "Build a web app" in result
        assert "React with TypeScript" in result
        # Assistant messages should not be included
        assert "What framework?" not in result


class TestClientLazyLoading:
    """Tests for client lazy loading behavior."""
    
    def test_client_not_created_when_not_configured(self):
        """Test that client is not created when not configured (line 72)."""
        service = PromptRefinementService()
        service.endpoint = None
        service.api_key = None
        service.deployment_name = None
        
        client = service.client
        
        assert client is None
    
    def test_client_created_when_configured(self):
        """Test that client is created when configured."""
        service = PromptRefinementService()
        service.endpoint = "https://test.openai.azure.com"
        service.api_key = "test-key"
        service.deployment_name = "test-deployment"
        
        with patch('src.utils.prompt_refinement.AzureOpenAI') as mock_azure:
            mock_client = MagicMock()
            mock_azure.return_value = mock_client
            
            client = service.client
            
            assert client == mock_client
            mock_azure.assert_called_once()
