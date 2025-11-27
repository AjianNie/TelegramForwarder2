import logging
from filters.base_filter import BaseFilter
from utils.common import get_main_module

logger = logging.getLogger(__name__)

class DeleteOriginalFilter(BaseFilter):
    """
    删除原始消息过滤器，处理转发后是否要删除原始消息
    """
    
    async def _process(self, context):
        """
        处理是否删除原始消息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        event = context.event
        
        if not rule.is_delete_original:
            return True
            
        try:
            main = await get_main_module()
            user_client = main.user_client  # 获取用户客户端
            
            if event.message.grouped_id:
                async for message in user_client.iter_messages(
                        event.chat_id,
                        min_id=event.message.id - 10,
                        max_id=event.message.id + 10,
                        reverse=True
                ):
                    if message.grouped_id == event.message.grouped_id:
                        await message.delete()
                        logger.info(f'已删除媒体组消息 ID: {message.id}')
            else:
                message = await user_client.get_messages(event.chat_id, ids=event.message.id)
                await message.delete()
                logger.info(f'已删除原始消息 ID: {event.message.id}')
                
            return True
        except Exception as e:
            logger.error(f'删除原始消息时出错: {str(e)}')
            context.errors.append(f"删除原始消息错误: {str(e)}")
            return True  # 即使删除失败，也继续处理 