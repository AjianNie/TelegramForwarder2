import logging
import os
import pytz
import asyncio
import apprise
from datetime import datetime
import traceback

from filters.base_filter import BaseFilter
from models.models import get_session, PushConfig
from enums.enums import PreviewMode
from .rate_limiter import global_rate_limiter

logger = logging.getLogger(__name__)

class PushFilter(BaseFilter):
    """
    推送过滤器，利用apprise库推送消息
    """
    
    async def _process(self, context):
        """
        推送消息
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 若消息应继续处理则返回True，否则返回False
        """
        rule = context.rule
        client = context.client
        event = context.event
        
        if not rule.enable_push:
            logger.info('推送未启用，跳过推送')
            return True
        
        rule_id = rule.id
        session = get_session()
        
 
        logger.info(f"推送过滤器开始处理 - 规则ID: {rule_id}")
        logger.info(f"是否是媒体组: {context.is_media_group}")
        logger.info(f"媒体组消息数量: {len(context.media_group_messages) if context.media_group_messages else 0}")
        logger.info(f"已有媒体文件数量: {len(context.media_files) if context.media_files else 0}")
        logger.info(f"是否只推送不转发: {rule.enable_only_push}")
        
        processed_files = []
        
        try:
            push_configs = session.query(PushConfig).filter(
                PushConfig.rule_id == rule_id,
                PushConfig.enable_push_channel == True
            ).all()
            
            if not push_configs:
                logger.info(f'规则 {rule_id} 没有启用的推送配置，跳过推送')
                return True
            
            if context.is_media_group or (context.media_group_messages and context.skipped_media):
                processed_files = await self._push_media_group(context, push_configs)
            elif context.media_files or context.skipped_media:
                processed_files = await self._push_single_media(context, push_configs)
            else:
                processed_files = await self._push_text_message(context, push_configs)
            
            logger.info(f'推送已发送到 {len(push_configs)} 个配置')
            return True
            
        except Exception as e:
            logger.error(f'推送过滤器处理出错: {str(e)}')
            logger.error(traceback.format_exc())
            context.errors.append(f"推送错误: {str(e)}")
            return False
        finally:
            session.close()
            
            if processed_files:
                logger.info(f'清理已处理的媒体文件，共 {len(processed_files)} 个')
                for file_path in processed_files:
                    try:
                        if os.path.exists(str(file_path)):
                            os.remove(file_path)
                            logger.info(f'删除已处理的媒体文件: {file_path}')
                    except Exception as e:
                        logger.error(f'删除媒体文件失败: {str(e)}')
    
    async def _push_media_group(self, context, push_configs):
        """推送媒体组消息"""
        rule = context.rule
        client = context.client
        event = context.event
        
        files = []
        need_cleanup = False
        
        try:
            if not context.media_group_messages and context.skipped_media:
                logger.info(f'所有媒体都超限，发送文本和提示')
                text_to_send = context.message_text or ''
                
                if rule.is_original_link:
                    context.original_link = f"\n原始消息: https://t.me/c/{str(event.chat_id)[4:]}/{event.message.id}"
                
                for message, size, name in context.skipped_media:
                    text_to_send += f"\n\n⚠️ 媒体文件 {name if name else '未命名文件'} ({size}MB) 超过大小限制"
                
                if rule.is_original_sender:
                    text_to_send = context.sender_info + text_to_send
                if rule.is_original_time:
                    text_to_send += context.time_info
                if rule.is_original_link:
                    text_to_send += context.original_link
                
                await self._send_push_notification(push_configs, text_to_send)
                return
            
            if context.media_group_messages and not context.media_files:
                logger.info(f'检测到媒体组消息但没有媒体文件，开始下载...')
                need_cleanup = True
                for message in context.media_group_messages:
                    if message.media:
                        await global_rate_limiter.get_token()
                        file_path = await message.download_media(os.path.join(os.getcwd(), 'temp'))
                        if file_path:
                            files.append(file_path)
                            logger.info(f'已下载媒体组文件: {file_path}')
            elif context.media_files:
                logger.info(f'使用SenderFilter已下载的文件: {len(context.media_files)}个')
                files = context.media_files
            elif rule.enable_only_push:
                logger.info(f'需要自己下载文件，开始下载媒体组消息...')
                need_cleanup = True
                for message in context.media_group_messages:
                    if message.media:
                        await global_rate_limiter.get_token()
                        file_path = await message.download_media(os.path.join(os.getcwd(), 'temp'))
                        if file_path:
                            files.append(file_path)
                            logger.info(f'已下载媒体文件: {file_path}')
            
            if files:
                caption_text = ""
                if rule.is_original_sender and context.sender_info:
                    caption_text += context.sender_info
                caption_text += context.message_text or ""
                
                for message, size, name in context.skipped_media:
                    caption_text += f"\n\n⚠️ 媒体文件 {name if name else '未命名文件'} ({size}MB) 超过大小限制"
                
                if rule.is_original_link and context.skipped_media:
                    original_link = f"\n原始消息: https://t.me/c/{str(event.chat_id)[4:]}/{event.message.id}"
                    caption_text += original_link
                
                if rule.is_original_time and context.time_info:
                    caption_text += context.time_info
                
                default_caption = f"收到一组媒体文件 (共{len(files)}个)"
                
                processed_files = []
                
                for config in push_configs:
                    send_mode = config.media_send_mode  # "Single" 或 "Multiple"
                    
                    valid_files = [f for f in files if os.path.exists(str(f))]
                    if not valid_files:
                        continue
                    
                    if send_mode == "Multiple":
                        try:
                            logger.info(f'尝试一次性发送 {len(valid_files)} 个文件到 {config.push_channel}，模式: {send_mode}')
                            await self._send_push_notification(
                                [config], 
                                caption_text or f"收到一组媒体文件 (共{len(valid_files)}个)", 
                                None,  # 不使用单附件参数
                                valid_files  # 使用多附件参数
                            )
                            processed_files.extend(valid_files)
                        except Exception as e:
                            logger.error(f'尝试一次性发送多个文件失败，错误: {str(e)}')
                            for i, file_path in enumerate(valid_files):
                                # 第一个文件使用完整文本，后续文件使用简短描述
                                file_caption = caption_text if i == 0 else f"媒体组的第 {i+1} 个文件"
                                await self._send_push_notification([config], file_caption, file_path)
                                processed_files.append(file_path)
                    else:
                        for i, file_path in enumerate(valid_files):
                            if i == 0:
                                file_caption = caption_text or f"收到一组媒体文件 (共{len(valid_files)}个)"
                            else:
                                file_caption = f"媒体组的第 {i+1} 个文件" if len(valid_files) > 1 else ""
                            
                            await self._send_push_notification([config], file_caption, file_path)
                            processed_files.append(file_path)
                
        except Exception as e:
            logger.error(f'推送媒体组消息时出错: {str(e)}')
            logger.error(traceback.format_exc())
            raise
        finally:
            if need_cleanup:
                for file_path in files:
                    try:
                        if os.path.exists(str(file_path)):
                            os.remove(file_path)
                            logger.info(f'删除临时文件: {file_path}')
                            if file_path in processed_files:
                                processed_files.remove(file_path)
                    except Exception as e:
                        logger.error(f'删除临时文件失败: {str(e)}')
            
            return processed_files
    
    async def _push_single_media(self, context, push_configs):
        """推送单条媒体消息"""
        rule = context.rule
        client = context.client
        event = context.event
        
        logger.info(f'推送单条媒体消息')
        
        processed_files = []
        
        if context.skipped_media and not context.media_files:
            file_size = context.skipped_media[0][1]
            file_name = context.skipped_media[0][2]
            
            text_to_send = context.message_text or ''
            text_to_send += f"\n\n⚠️ 媒体文件 {file_name} ({file_size}MB) 超过大小限制"
            
            if rule.is_original_sender:
                text_to_send = context.sender_info + text_to_send
            
            if rule.is_original_time:
                text_to_send += context.time_info
            
            if rule.is_original_link:
                original_link = f"\n原始消息: https://t.me/c/{str(event.chat_id)[4:]}/{event.message.id}"
                text_to_send += original_link
            
            await self._send_push_notification(push_configs, text_to_send)
            return processed_files
        
        files = []
        need_cleanup = False
        
        try:
            if context.media_files:
                logger.info(f'使用SenderFilter已下载的文件: {len(context.media_files)}个')
                files = context.media_files
            elif rule.enable_only_push and event.message and event.message.media:
                logger.info(f'需要自己下载文件，开始下载单个媒体消息...')
                need_cleanup = True
                await global_rate_limiter.get_token()
                file_path = await event.message.download_media(os.path.join(os.getcwd(), 'temp'))
                if file_path:
                    files.append(file_path)
                    logger.info(f'已下载媒体文件: {file_path}')
            
            for file_path in files:
                try:
                    caption = ""
                    if rule.is_original_sender and context.sender_info:
                        caption += context.sender_info
                    caption += context.message_text or ""
                    
                    if rule.is_original_time and context.time_info:
                        caption += context.time_info
                    
                    if rule.is_original_link and context.original_link:
                        caption += context.original_link
                    
                    if not caption:
                        caption = " "
                        # ext = os.path.splitext(str(file_path))[1].lower()
                        # if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        #     caption = "收到一张图片"
                        # elif ext in ['.mp4', '.avi', '.mkv', '.mov', '.webm']:
                        #     caption = "收到一个视频"
                        # elif ext in ['.mp3', '.wav', '.ogg', '.flac']:
                        #     caption = "收到一个音频文件"
                        # else:
                        #     caption = f"收到一个文件 ({ext})"
                    
                    await self._send_push_notification(push_configs, caption, file_path)
                    processed_files.append(file_path)
                    
                except Exception as e:
                    logger.error(f'推送单个媒体文件时出错: {str(e)}')
                    logger.error(traceback.format_exc())
                    raise
                
        except Exception as e:
            logger.error(f'推送单条媒体消息时出错: {str(e)}')
            logger.error(traceback.format_exc())
            raise
        finally:
            if need_cleanup:
                for file_path in files:
                    try:
                        if os.path.exists(str(file_path)):
                            os.remove(file_path)
                            logger.info(f'删除临时文件: {file_path}')
                            if file_path in processed_files:
                                processed_files.remove(file_path)
                    except Exception as e:
                        logger.error(f'删除临时文件失败: {str(e)}')
    
            return processed_files
    
    async def _push_text_message(self, context, push_configs):
        """推送纯文本消息"""
        rule = context.rule
        
        if not context.message_text:
            logger.info('没有文本内容，不发送推送')
            return []
        
        message_text = ""
        if rule.is_original_sender and context.sender_info:
            message_text += context.sender_info
        message_text += context.message_text
        if rule.is_original_time and context.time_info:
            message_text += context.time_info
        if rule.is_original_link and context.original_link:
            message_text += context.original_link
        
        await self._send_push_notification(push_configs, message_text)
        logger.info(f'文本消息推送已发送')
        
        return []
    
    async def _send_push_notification(self, push_configs, body, attachment=None, all_attachments=None):
        """发送推送通知"""
        if not body and not attachment and not all_attachments:
            logger.warning('没有内容可推送')
            return
        
        for config in push_configs:
            try:
                apobj = apprise.Apprise()
                
                service_url = config.push_channel
                if apobj.add(service_url):
                    logger.info(f'成功添加推送服务: {service_url}')
                else:
                    logger.error(f'添加推送服务失败: {service_url}')
                    continue
                
                if all_attachments and len(all_attachments) > 0 and config.media_send_mode == "Multiple":
                    logger.info(f'发送带{len(all_attachments)}个附件的推送，模式: {config.media_send_mode}')
                    send_result = await asyncio.to_thread(
                        apobj.notify,
                        body=body or f"收到{len(all_attachments)}个媒体文件",
                        attach=all_attachments
                    )
                elif attachment and os.path.exists(str(attachment)):
                    logger.info(f'发送带单个附件的推送: {os.path.basename(str(attachment))}')
                    send_result = await asyncio.to_thread(
                        apobj.notify,
                        body=body or " ",
                        attach=attachment
                    )
                else:
                    logger.info('发送纯文本推送')
                    send_result = await asyncio.to_thread(
                        apobj.notify,
                        body=body
                    )
                
                if send_result:
                    logger.info(f'推送发送成功: {service_url}')
                else:
                    logger.error(f'推送发送失败: {service_url}')
                
            except Exception as e:
                logger.error(f'发送推送时出错: {str(e)}')
                logger.error(traceback.format_exc())