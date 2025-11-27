from typing import Optional, List, Dict
import anthropic
from .base import BaseAIProvider
import os
import logging

logger = logging.getLogger(__name__)

class ClaudeProvider(BaseAIProvider):
    def __init__(self):
        self.client = None
        self.model = None
        self.default_model = 'claude-3-5-sonnet-latest'
        
    async def initialize(self, **kwargs):
        """初始化Claude客户端"""
        api_key = os.getenv('CLAUDE_API_KEY')
        if not api_key:
            raise ValueError("未设置CLAUDE_API_KEY环境变量")
            
        api_base = os.getenv('CLAUDE_API_BASE', '').strip()
        if api_base:
            logger.info(f"使用自定义Claude API基础URL: {api_base}")
            self.client = anthropic.Anthropic(
                api_key=api_key,
                base_url=api_base
            )
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
            
        self.model = kwargs.get('model', self.default_model)
        
    async def process_message(self, 
                            message: str, 
                            prompt: Optional[str] = None,
                            images: Optional[List[Dict[str, str]]] = None,
                            **kwargs) -> str:
        """处理消息"""
        try:
            if not self.client:
                await self.initialize(**kwargs)
                
            messages = []
            if prompt:
                messages.append({"role": "system", "content": prompt})
            
            if images and len(images) > 0:
                content = []
                
                content.append({
                    "type": "text",
                    "text": message
                })
                
                for img in images:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img["mime_type"],
                            "data": img["data"]
                        }
                    })
                    logger.info(f"已添加一张类型为 {img['mime_type']} 的图片，大小约 {len(img['data']) // 1000} KB")
                
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "user", "content": message})
            
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                messages=messages
            ) as stream:
                full_response = ""
                for text in stream.text_stream:
                    full_response += text
        
            return full_response
            
        except Exception as e:
            logger.error(f"Claude API 调用失败: {str(e)}")
            return f"AI处理失败: {str(e)}" 