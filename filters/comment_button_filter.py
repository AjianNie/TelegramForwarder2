import logging
import asyncio
import time
import telethon
import traceback
from telethon import Button
from filters.base_filter import BaseFilter
from telethon.tl.functions.channels import GetFullChannelRequest
from utils.common import get_main_module
from difflib import SequenceMatcher
from .rate_limiter import global_rate_limiter
import traceback
logger = logging.getLogger(__name__)

class CommentButtonFilter(BaseFilter):
    """
    评论区按钮过滤器，用于在消息中添加指向关联群组消息的按钮
    """
    
    async def _process(self, context):
        """
        为消息添加评论区按钮
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        if context.rule.only_rss:
            logger.info('只转发到RSS，跳过评论区按钮过滤器')
            return True
        
        # logger.info(f"CommentButtonFilter处理消息前，context: {context.__dict__}")
        try:
            if not context.rule or not context.rule.enable_comment_button:
                return True
                
            if not context.original_message_text and not context.event.message.media:
                return True
            
            try:
                main = await get_main_module()
                client = main.user_client if (main and hasattr(main, 'user_client')) else context.client
                
                event = context.event
                await global_rate_limiter.get_token()
                channel_entity = await client.get_entity(event.chat_id)
                channel_username = None
                # logger.info(f"获取频道实体: {channel_entity}")
                # logger.info(f"频道属性内容: {channel_entity.__dict__}")
                if hasattr(channel_entity, 'username') and channel_entity.username:
                    channel_username = channel_entity.username
                    logger.info(f"获取到频道用户名: {channel_username}")
                elif hasattr(channel_entity, 'usernames') and channel_entity.usernames:
                    for username_obj in channel_entity.usernames:
                        if username_obj.active:
                            channel_username = username_obj.username
                            logger.info(f"从 usernames 列表获取到频道用户名: {channel_username}")
                            break
                
                channel_id_str = str(channel_entity.id)
                if channel_id_str.startswith('-100'):
                    channel_id_str = channel_id_str[4:]
                elif channel_id_str.startswith('100'):
                    channel_id_str = channel_id_str[3:]
                    
                logger.info(f"处理频道ID: {channel_id_str}")
                
                if not hasattr(channel_entity, 'broadcast') or not channel_entity.broadcast:
                    return True
                    
                try:
                    await global_rate_limiter.get_token()
                    full_channel = await client(GetFullChannelRequest(channel_entity))
                    
                    if not full_channel.full_chat.linked_chat_id:
                        logger.info(f"频道 {channel_entity.id} 没有关联群组，跳过添加评论按钮")
                        return True
                        
                    linked_group_id = full_channel.full_chat.linked_chat_id
                    await global_rate_limiter.get_token()
                    linked_group = await client.get_entity(linked_group_id)
                    
                    channel_msg_id = event.message.id
                    
                    if hasattr(event.message, 'grouped_id') and event.message.grouped_id:
                        logger.info(f"检测到媒体组消息，组ID: {event.message.grouped_id}")
                        media_group_messages = []
                        
                        try:
                            await global_rate_limiter.get_token()
                            async for message in client.iter_messages(
                                channel_entity,
                                limit=20,  # 限制查询消息数量
                                offset_date=event.message.date,  # 从当前消息时间开始查询
                                reverse=False  # 从新到旧
                            ):
                                if (hasattr(message, 'grouped_id') and 
                                    message.grouped_id == event.message.grouped_id):
                                    media_group_messages.append(message)
                            
                            if media_group_messages:
                                min_id_message = min(media_group_messages, key=lambda x: x.id)
                                channel_msg_id = min_id_message.id
                                logger.info(f"使用媒体组中ID最小的消息: {channel_msg_id}")
                        except Exception as e:
                            logger.error(f"获取媒体组消息失败: {e}")
                            logger.info(f"使用原始消息ID: {channel_msg_id}")
                    
                    logger.info("等待2秒，确保消息同步完成...")
                    await asyncio.sleep(2)
                    
                    comment_link = None
                    if channel_username:
                        comment_link = f"https://t.me/{channel_username}/{channel_msg_id}?comment=1"
                        logger.info(f"构建公开频道评论区链接: {comment_link}")
                    else:
                        comment_link = f"https://t.me/c/{channel_id_str}/{channel_msg_id}?comment=1"
                        logger.info(f"构建私有频道评论区链接: {comment_link}")
                    

                    
                    try:
                        logger.info(f"尝试使用用户客户端获取群组 {linked_group_id} 的消息")
                        await global_rate_limiter.get_token()
                        group_messages = await client.get_messages(linked_group, limit=5)
                        logger.info(f"成功获取关联群组 {linked_group_id} 的 {len(group_messages)} 条消息")
                        
                        matched_msg = None
                        
                        original_message = context.original_message_text
                        if original_message:
                            logger.info(f"尝试查找内容完全匹配的消息，原始内容长度: {len(original_message)}")
                            
                            for msg in group_messages:
                                if hasattr(msg, 'message') and msg.message and msg.message == original_message:
                                    matched_msg = msg
                                    logger.info(f"找到完全匹配消息: 群组消息ID {msg.id}")
                                    break
                        
                        if not matched_msg and original_message and len(original_message) > 20:
                            
                            message_start = original_message[:20]
                            logger.info(f"尝试对前20字符进行相似度匹配: '{message_start}'")
                            
                            for msg in group_messages:
                                if hasattr(msg, 'message') and msg.message and len(msg.message) > 20:
                                    msg_start = msg.message[:20]
                                    similarity = SequenceMatcher(None, message_start, msg_start).ratio()
                                    if similarity > 0.75:
                                        matched_msg = msg
                                        logger.info(f"找到相似度匹配消息: 群组消息ID {msg.id}, 前20字符相似度: {similarity}")
                                        break
                        
                        if not matched_msg and hasattr(event.message, 'date'):
                            message_time = event.message.date
                            logger.info(f"尝试基于时间匹配，原消息时间: {message_time}")
                            
                            time_window = 1  # 分钟
                            
                            for msg in group_messages:
                                if hasattr(msg, 'date'):
                                    time_diff = abs((msg.date - message_time).total_seconds())
                                    if time_diff < time_window * 60:
                                        matched_msg = msg
                                        logger.info(f"找到时间接近的消息: 群组消息ID {msg.id}, 时间差: {time_diff}秒")
                                        break
                        
                        if not matched_msg:
                            logger.info("未找到匹配消息，尝试使用最新消息")
                            # 使用最新消息作为默认值
                            if group_messages:
                                matched_msg = group_messages[0]
                                logger.info(f"使用最新消息: 群组消息ID {matched_msg.id}")
                        
                        if matched_msg:
                            group_msg_id = matched_msg.id
                            if channel_username:
                                comment_link = f"https://t.me/{channel_username}/{channel_msg_id}?comment={group_msg_id}"
                            else:
                                comment_link = f"https://t.me/c/{channel_id_str}/{channel_msg_id}?comment={group_msg_id}"
                            logger.info(f"更新为精确评论区链接: {comment_link}")
                        
                    except Exception as e:
                        logger.warning(f"获取群组消息失败，可能是因为未加入群组: {str(e)}")
                        logger.info("将使用基本评论区链接")
                    
                    group_link = None
                    if hasattr(linked_group, 'username') and linked_group.username:
                        group_link = f"https://t.me/{linked_group.username}"
                        logger.info(f"生成群组备用链接: {group_link}")

                    context.comment_link = comment_link
                    
                    if context.is_media_group:
                        logger.info("媒体组消息的评论区按钮将由ReplyFilter处理")
                        return True
                    
                    buttons_added = False
                    
                    if comment_link:
                        comment_button = Button.url("💬 查看评论区", comment_link)
                        
                        if not context.buttons:
                            context.buttons = [[comment_button]]
                        else:
                            context.buttons.insert(0, [comment_button])
                        
                        logger.info(f"为消息添加了评论区按钮，链接: {comment_link}")
                        buttons_added = True
                    
                    
                    if not buttons_added:
                        logger.warning("未能添加任何按钮")
                except Exception as e:
                    logger.error(f"获取关联群组消息时出错: {str(e)}")
                    tb = traceback.format_exc()
                    logger.debug(f"详细错误信息: {tb}")
                    
            except Exception as e:
                logger.error(f"添加评论区按钮时出错: {str(e)}")
                logger.error(traceback.format_exc())
                
            return True 
        finally:
            # logger.info(f"CommentButtonFilter处理消息后，context: {context.__dict__}")
            pass