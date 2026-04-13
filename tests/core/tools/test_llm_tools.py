"""Tests for LLM tools (llm_analyze, llm_summarize)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.tools.llm_tools import LLMAnalyzeTool, LLMSummarizeTool


class TestLLMAnalyzeTool:
    """Tests for llm_analyze tool."""

    def test_tool_name_property(self):
        """Test tool name is correct."""
        tool = LLMAnalyzeTool()
        assert tool.name == "llm_analyze"

    def test_tool_description_property(self):
        """Test tool description is correct."""
        tool = LLMAnalyzeTool()
        assert "analyze" in tool.description.lower()

    def test_tool_parameters_has_content(self):
        """Test parameters schema includes content field."""
        tool = LLMAnalyzeTool()
        params = tool.parameters
        assert params["type"] == "object"
        assert "properties" in params
        assert "content" in params["properties"]

    def test_tool_parameters_has_analysis_type(self):
        """Test parameters schema includes analysis_type field."""
        tool = LLMAnalyzeTool()
        params = tool.parameters
        assert "analysis_type" in params["properties"]

    def test_tool_to_schema_format(self):
        """Test tool schema is in correct format."""
        tool = LLMAnalyzeTool()
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "llm_analyze"

    @pytest.mark.asyncio
    async def test_analyze_returns_structured_insights(self):
        """Test llm_analyze returns structured insights from LLM."""
        tool = LLMAnalyzeTool()
        mock_response = '{"key_points": ["point1", "point2"], "insights": ["insight1"], "confidence": 0.85}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await tool.execute(content="Test content to analyze")
            
            assert "key_points" in result
            assert "insights" in result
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_with_analysis_type(self):
        """Test llm_analyze respects analysis_type parameter."""
        tool = LLMAnalyzeTool()
        mock_response = '{"key_points": ["technical point"], "insights": ["technical insight"], "confidence": 0.9}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            await tool.execute(content="Technical content", analysis_type="technical")
            
            call_args = mock_call.call_args
            assert "technical" in call_args[1]["analysis_type"]

    @pytest.mark.asyncio
    async def test_analyze_handles_json_parse_error(self):
        """Test llm_analyze handles JSON parse errors gracefully."""
        tool = LLMAnalyzeTool()
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "invalid json {"
            result = await tool.execute(content="Test content")
            
            # Should return raw response or error message
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_analyze_uses_volcengine_provider(self):
        """Test llm_analyze uses volcengine as primary provider."""
        tool = LLMAnalyzeTool()
        mock_response = '{"key_points": [], "insights": [], "confidence": 0.5}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            await tool.execute(content="Test")
            
            call_args = mock_call.call_args
            assert call_args[1]["provider"] == "volcengine"

    @pytest.mark.asyncio
    async def test_analyze_fallback_to_minimax(self):
        """Test llm_analyze falls back to minimax on volcengine failure."""
        tool = LLMAnalyzeTool()
        mock_response = '{"key_points": [], "insights": [], "confidence": 0.5}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [Exception("volcengine failed"), mock_response]
            result = await tool.execute(content="Test")
            
            assert mock_call.call_count == 2
            assert "minimax" in mock_call.call_args_list[1][1]["provider"]


class TestLLMSummarizeTool:
    """Tests for llm_summarize tool."""

    def test_tool_name_property(self):
        """Test tool name is correct."""
        tool = LLMSummarizeTool()
        assert tool.name == "llm_summarize"

    def test_tool_description_property(self):
        """Test tool description is correct."""
        tool = LLMSummarizeTool()
        assert "summarize" in tool.description.lower()

    def test_tool_parameters_has_content(self):
        """Test parameters schema includes content field."""
        tool = LLMSummarizeTool()
        params = tool.parameters
        assert params["type"] == "object"
        assert "properties" in params
        assert "content" in params["properties"]

    def test_tool_parameters_has_max_length(self):
        """Test parameters schema includes max_length field."""
        tool = LLMSummarizeTool()
        params = tool.parameters
        assert "max_length" in params["properties"]

    def test_tool_to_schema_format(self):
        """Test tool schema is in correct format."""
        tool = LLMSummarizeTool()
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "llm_summarize"

    @pytest.mark.asyncio
    async def test_summarize_returns_key_points(self):
        """Test llm_summarize returns key points from content."""
        tool = LLMSummarizeTool()
        mock_response = '{"summary": "Brief summary", "key_points": ["point1", "point2"], "length": 50}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            result = await tool.execute(content="Long content to summarize")
            
            assert "summary" in result
            assert "key_points" in result
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_respects_max_length(self):
        """Test llm_summarize respects max_length parameter."""
        tool = LLMSummarizeTool()
        mock_response = '{"summary": "Short summary", "key_points": [], "length": 30}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            await tool.execute(content="Long content", max_length=100)
            
            call_args = mock_call.call_args
            assert call_args[1]["max_length"] == 100

    @pytest.mark.asyncio
    async def test_summarize_handles_json_parse_error(self):
        """Test llm_summarize handles JSON parse errors gracefully."""
        tool = LLMSummarizeTool()
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = "not valid json"
            result = await tool.execute(content="Test content")
            
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_summarize_uses_volcengine_provider(self):
        """Test llm_summarize uses volcengine as primary provider."""
        tool = LLMSummarizeTool()
        mock_response = '{"summary": "Summary", "key_points": [], "length": 20}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = mock_response
            await tool.execute(content="Test")
            
            call_args = mock_call.call_args
            assert call_args[1]["provider"] == "volcengine"

    @pytest.mark.asyncio
    async def test_summarize_fallback_to_minimax(self):
        """Test llm_summarize falls back to minimax on volcengine failure."""
        tool = LLMSummarizeTool()
        mock_response = '{"summary": "Summary", "key_points": [], "length": 20}'
        
        with patch.object(tool, '_call_llm', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [Exception("volcengine failed"), mock_response]
            result = await tool.execute(content="Test")
            
            assert mock_call.call_count == 2
            assert "minimax" in mock_call.call_args_list[1][1]["provider"]


class TestLLMToolsIntegration:
    """Integration tests for LLM tools."""

    @pytest.mark.asyncio
    async def test_both_tools_use_same_llm_client_infrastructure(self):
        """Test both tools use the same LLM client infrastructure."""
        analyze_tool = LLMAnalyzeTool()
        summarize_tool = LLMSummarizeTool()
        mock_response = '{"result": "test"}'
        
        with patch.object(analyze_tool, '_call_llm', new_callable=AsyncMock) as mock_analyze:
            with patch.object(summarize_tool, '_call_llm', new_callable=AsyncMock) as mock_summarize:
                mock_analyze.return_value = mock_response
                mock_summarize.return_value = mock_response
                
                await analyze_tool.execute(content="Test")
                await summarize_tool.execute(content="Test")
                
                assert mock_analyze.called
                assert mock_summarize.called

    @pytest.mark.asyncio
    async def test_tools_handle_empty_content(self):
        """Test tools handle empty content gracefully."""
        analyze_tool = LLMAnalyzeTool()
        summarize_tool = LLMSummarizeTool()
        mock_response = '{"error": "empty content", "key_points": [], "insights": []}'
        
        with patch.object(analyze_tool, '_call_llm', new_callable=AsyncMock) as mock_analyze:
            with patch.object(summarize_tool, '_call_llm', new_callable=AsyncMock) as mock_summarize:
                mock_analyze.return_value = mock_response
                mock_summarize.return_value = mock_response
                
                analyze_result = await analyze_tool.execute(content="")
                summarize_result = await summarize_tool.execute(content="")
                
                assert isinstance(analyze_result, str)
                assert isinstance(summarize_result, str)
