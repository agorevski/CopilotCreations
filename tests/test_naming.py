"""
Tests for repository naming utilities using Azure OpenAI.
"""

from unittest.mock import Mock, patch, MagicMock

import pytest

from src.utils.naming import RepositoryNamingGenerator


class TestRepositoryNamingGeneratorInit:
    """Tests for RepositoryNamingGenerator initialization."""
    
    def test_init_loads_config(self):
        """Test that RepositoryNamingGenerator loads configuration on init."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator.endpoint == 'https://test.openai.azure.com/'
            assert generator.api_key == 'test_key'
            assert generator.deployment_name == 'gpt-52'
    
    def test_init_with_missing_config(self):
        """Test that RepositoryNamingGenerator works with missing config."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', None), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', None):
            generator = RepositoryNamingGenerator()
            assert generator.endpoint is None
            assert generator.api_key is None
            assert generator.deployment_name is None


class TestIsConfigured:
    """Tests for is_configured method."""
    
    def test_is_configured_all_set(self):
        """Test is_configured returns True when all settings are present."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator.is_configured() is True
    
    def test_is_configured_missing_endpoint(self):
        """Test is_configured returns False when endpoint is missing."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator.is_configured() is False
    
    def test_is_configured_missing_api_key(self):
        """Test is_configured returns False when API key is missing."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', None), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator.is_configured() is False
    
    def test_is_configured_missing_deployment(self):
        """Test is_configured returns False when deployment name is missing."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', None):
            generator = RepositoryNamingGenerator()
            assert generator.is_configured() is False
    
    def test_is_configured_empty_strings(self):
        """Test is_configured returns False with empty strings."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', ''), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', ''), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', ''):
            generator = RepositoryNamingGenerator()
            assert generator.is_configured() is False


class TestClientProperty:
    """Tests for the client property lazy loading."""
    
    def test_client_property_when_not_configured(self):
        """Test that client property returns None when not configured."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', None), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', None):
            generator = RepositoryNamingGenerator()
            assert generator.client is None
    
    def test_client_property_lazy_loads(self):
        """Test that client property creates client on first access."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI') as mock_client:
            generator = RepositoryNamingGenerator()
            _ = generator.client
            mock_client.assert_called_once_with(
                azure_endpoint='https://test.openai.azure.com/',
                api_key='test_key',
                api_version='2025-01-01-preview'
            )
    
    def test_client_property_caches_client(self):
        """Test that client property caches the client."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI') as mock_client:
            generator = RepositoryNamingGenerator()
            _ = generator.client
            _ = generator.client
            # Should only create once
            mock_client.assert_called_once()


class TestSanitizeName:
    """Tests for the _sanitize_name method."""
    
    def test_sanitize_removes_quotes(self):
        """Test that quotes are removed from the name."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('"pixel-wizard"') == 'pixel-wizard'
            assert generator._sanitize_name("'turbo-toaster'") == 'turbo-toaster'
    
    def test_sanitize_converts_to_lowercase(self):
        """Test that names are converted to lowercase."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('Pixel-WIZARD') == 'pixel-wizard'
    
    def test_sanitize_replaces_spaces_with_hyphens(self):
        """Test that spaces are replaced with hyphens."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('pixel wizard') == 'pixel-wizard'
    
    def test_sanitize_replaces_underscores_with_hyphens(self):
        """Test that underscores are replaced with hyphens."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('pixel_wizard') == 'pixel-wizard'
    
    def test_sanitize_removes_special_characters(self):
        """Test that special characters are removed."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('pixel@wizard!') == 'pixelwizard'
    
    def test_sanitize_removes_consecutive_hyphens(self):
        """Test that consecutive hyphens are collapsed."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('pixel---wizard') == 'pixel-wizard'
    
    def test_sanitize_removes_leading_trailing_hyphens(self):
        """Test that leading and trailing hyphens are removed."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('-pixel-wizard-') == 'pixel-wizard'
    
    def test_sanitize_limits_length(self):
        """Test that names are limited to 50 characters."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            long_name = 'a' * 100
            result = generator._sanitize_name(long_name)
            assert len(result) <= 50
    
    def test_sanitize_handles_empty_input(self):
        """Test that empty input returns empty string."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'):
            generator = RepositoryNamingGenerator()
            assert generator._sanitize_name('') == ''
            assert generator._sanitize_name('   ') == ''


class TestGenerateName:
    """Tests for the generate_name method."""
    
    def test_generate_name_not_configured(self):
        """Test generate_name returns None when not configured."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', None), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', None):
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            assert result is None
    
    def test_generate_name_success(self):
        """Test successful name generation."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "task-master-pro"
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate a name for:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            
            assert result == "task-master-pro"
            mock_client.chat.completions.create.assert_called_once()
            
            # Verify correct parameters are passed for GPT 5.2
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs['model'] == 'gpt-52'
            assert 'messages' in call_kwargs
            assert call_kwargs['max_completion_tokens'] == 50000
            assert call_kwargs['stop'] is None
            assert call_kwargs['stream'] is False
            # Ensure deprecated parameters are not used
            assert 'max_tokens' not in call_kwargs
            assert 'temperature' not in call_kwargs
    
    def test_generate_name_with_quotes_in_response(self):
        """Test that quotes in the response are properly sanitized."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '"pixel-wizard"'
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate a name for:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("An image processing library")
            
            assert result == "pixel-wizard"
    
    def test_generate_name_empty_response(self):
        """Test generate_name handles empty response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate a name for:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            
            assert result is None
    
    def test_generate_name_sanitization_empty_result(self):
        """Test generate_name returns None when sanitization results in empty string."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "@@@!!!"  # Will sanitize to empty
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate a name for:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            
            assert result is None
    
    def test_generate_name_api_exception(self):
        """Test generate_name handles API exceptions gracefully."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate a name for:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            
            assert result is None
    
    def test_generate_name_uses_default_prompt_when_template_missing(self):
        """Test generate_name uses default prompt when config template is missing."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "cool-project"
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value=''):  # Empty template
            generator = RepositoryNamingGenerator()
            result = generator.generate_name("A todo list app")
            
            assert result == "cool-project"
            # Verify it was called with some prompt containing the description
            call_args = mock_client.chat.completions.create.call_args
            assert "A todo list app" in call_args[1]['messages'][1]['content']


class TestNamingGeneratorSingleton:
    """Tests for the naming_generator singleton."""
    
    def test_naming_generator_singleton_exists(self):
        """Test that naming_generator singleton is created."""
        from src.utils.naming import naming_generator
        assert naming_generator is not None
        assert isinstance(naming_generator, RepositoryNamingGenerator)


class TestGenerateDescription:
    """Tests for generate_description method."""
    
    def test_generate_description_not_configured(self):
        """Test generate_description returns None when not configured."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', None), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', None):
            generator = RepositoryNamingGenerator()
            result = generator.generate_description("A todo list app")
            
            assert result is None
    
    def test_generate_description_success(self):
        """Test successful description generation."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "A modern todo list application."
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate description:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_description("A todo list app")
            
            assert result == "A modern todo list application."
    
    def test_generate_description_empty_response(self):
        """Test generate_description with empty response."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = ""
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate description:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_description("A todo list app")
            
            assert result is None
    
    def test_generate_description_sanitization_empty(self):
        """Test generate_description returns None when sanitization results in empty."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "   "  # Only whitespace
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate description:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_description("A todo list app")
            
            assert result is None
    
    def test_generate_description_api_exception(self):
        """Test generate_description handles API exceptions gracefully."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value='Generate description:'):
            generator = RepositoryNamingGenerator()
            result = generator.generate_description("A todo list app")
            
            assert result is None
    
    def test_generate_description_uses_default_prompt(self):
        """Test generate_description uses default prompt when template missing."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "A cool project"
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', 'https://test.openai.azure.com/'), \
             patch('src.utils.naming.AZURE_OPENAI_API_KEY', 'test_key'), \
             patch('src.utils.naming.AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-52'), \
             patch('src.utils.naming.AZURE_OPENAI_API_VERSION', '2025-01-01-preview'), \
             patch('src.utils.naming.AzureOpenAI', return_value=mock_client), \
             patch('src.utils.naming.get_prompt_template', return_value=''):  # Empty template
            generator = RepositoryNamingGenerator()
            result = generator.generate_description("A todo list app")
            
            assert result == "A cool project"


class TestSanitizeDescription:
    """Tests for _sanitize_description method."""
    
    def test_sanitize_description_removes_quotes(self):
        """Test that quotes are removed from description."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None):
            generator = RepositoryNamingGenerator()
            result = generator._sanitize_description('"A cool project"')
            
            assert result == "A cool project"
    
    def test_sanitize_description_removes_control_chars(self):
        """Test that control characters are removed."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None):
            generator = RepositoryNamingGenerator()
            result = generator._sanitize_description("A project\x00\x01\x02")
            
            assert "\x00" not in result
            assert "A project" in result
    
    def test_sanitize_description_truncates_long(self):
        """Test that long descriptions are truncated."""
        with patch('src.utils.naming.AZURE_OPENAI_ENDPOINT', None):
            generator = RepositoryNamingGenerator()
            long_desc = "x" * 400
            result = generator._sanitize_description(long_desc)
            
            assert len(result) <= generator.MAX_DESCRIPTION_LENGTH
            assert result.endswith("...")
