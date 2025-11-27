from typing import Optional, List, Dict
import google.generativeai as genai
from .base import BaseAIProvider
from .openai_base_provider import OpenAIBaseProvider
import os
import logging
import base64

logger = logging.getLogger(__name__)

class GeminiOpenAIProvider(OpenAIBaseProvider):
    """使用OpenAI兼容接口的Gemini提供者"""
    def __init__(self):
        super().__init__(
            env_prefix='GEMINI',
            default_model='gemini-pro',
            default_api_base=''  # API_BASE必须在环境变量中提供
        )

class GeminiProvider(BaseAIProvider):
    def __init__(self):
        self.model = None
        self.model_name = None  # 添加model_name属性
        self.provider = None
        
    async def initialize(self, **kwargs):
        """初始化Gemini客户端"""
        # 检查是否配置了GEMINI_API_BASE，如果有则使用兼容OpenAI的接口
        api_base = os.getenv('GEMINI_API_BASE', '').strip()
        
        if api_base:
            logger.info(f"检测到GEMINI_API_BASE环境变量: {api_base}，使用兼容OpenAI的接口")
            self.provider = GeminiOpenAIProvider()
            await self.provider.initialize(**kwargs)
            return
            
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("未设置GEMINI_API_KEY环境变量")

        if not self.model_name:  # 如果model_name还没设置
            self.model_name = kwargs.get('model')
        
        if not self.model_name:  # 如果kwargs中也没有model
            self.model_name = 'gemini-pro'  # 最后才使用默认值
            
        logger.info(f"初始化Gemini模型: {self.model_name}")
        
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            safety_settings=safety_settings
        )
        
    async def process_message(self, 
                            message: str, 
                            prompt: Optional[str] = None,
                            images: Optional[List[Dict[str, str]]] = None,
                            **kwargs) -> str:
        """处理消息"""
        try:
            if not self.provider and not self.model:
                await self.initialize(**kwargs)
            
            if self.provider:
                return await self.provider.process_message(message, prompt, images, **kwargs)
                
            logger.info(f"实际使用的Gemini模型: {self.model_name}")

            if prompt:
                user_message = f"{prompt}\n\n{message}"
            else:
                user_message = message
            
            if images and len(images) > 0:
                try:
                    contents = []
                    contents.append({"role": "user", "parts": [{"text": user_message}]})
                    
                    for img in images:
                        try:
                            image_part = {
                                "inline_data": {
                                    "mime_type": img["mime_type"],
                                    "data": img["data"]  # 使用原始base64数据
                                }
                            }
                            contents[0]["parts"].append(image_part)
                            logger.info(f"已添加一张类型为 {img['mime_type']} 的图片，大小约 {len(img['data']) // 1000} KB")
                        except Exception as img_error:
                            logger.error(f"处理单张图片时出错: {str(img_error)}")
                    
                    response_stream = self.model.generate_content(
                        contents,
                        stream=True
                    )
                except Exception as e:
                    logger.error(f"Gemini处理带图片消息时出错: {str(e)}")
                    response_stream = self.model.generate_content(
                        [{"role": "user", "parts": [{"text": user_message}]}],
                        stream=True
                    )
            else:
                response_stream = self.model.generate_content(
                    [{"role": "user", "parts": [{"text": user_message}]}],
                    stream=True
                )
            
            full_response = ""
            for chunk in response_stream:
                if hasattr(chunk, 'text'):
                    full_response += chunk.text
            
            return full_response
            
        except Exception as e:
            logger.error(f"Gemini处理消息时出错: {str(e)}")
            return f"AI处理失败: {str(e)}" 