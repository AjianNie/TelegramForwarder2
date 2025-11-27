from .base import BaseAIProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .deepseek_provider import DeepSeekProvider
from .qwen_provider import QwenProvider
from .grok_provider import GrokProvider
from .claude_provider import ClaudeProvider
import os
import logging
from utils.settings import load_ai_models
from utils.constants import DEFAULT_AI_MODEL

logger = logging.getLogger(__name__)

async def get_ai_provider(model=None):
    """获取AI提供者实例"""
    if not model:
        model = DEFAULT_AI_MODEL
    
    providers_config = load_ai_models(type="dict")
    
    provider = None
    
    for provider_name, models_list in providers_config.items():
        if model in models_list:
            if provider_name == "openai":
                provider = OpenAIProvider()
            elif provider_name == "gemini":
                provider = GeminiProvider()
            elif provider_name == "deepseek":
                provider = DeepSeekProvider()
            elif provider_name == "qwen":
                provider = QwenProvider()
            elif provider_name == "grok":
                provider = GrokProvider()
            elif provider_name == "claude":
                provider = ClaudeProvider()
            break
    
    if not provider:
        raise ValueError(f"不支持的模型: {model}")

    return provider


__all__ = [
    'BaseAIProvider',
    'OpenAIProvider',
    'GeminiProvider',
    'DeepSeekProvider',
    'QwenProvider',
    'GrokProvider',
    'ClaudeProvider',
    'get_ai_provider'
]