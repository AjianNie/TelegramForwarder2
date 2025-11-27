import re
import os
import logging
from utils.common import get_main_module, get_user_id
from utils.constants import TEMP_DIR

logger = logging.getLogger(__name__)

async def handle_message_link(client, event):
    """处理 Telegram 消息链接"""
    if not event.message.text:
        return

    match = re.match(r'https?://t\.me/(?:c/(\d+)|([^/]+))/(\d+)', event.message.text)
    if not match:
        return

    try:
        chat_id = None
        message_id = int(match.group(3))

        if match.group(1):  # 私有频道格式
            chat_id = int('-100' + match.group(1))
        else:  # 公开频道格式
            chat_name = match.group(2)
            try:
                entity = await client.get_entity(chat_name)
                chat_id = entity.id
            except Exception as e:
                logger.error(f'获取频道信息失败: {str(e)}')
                await reply_and_delete(event,'⚠️ 无法访问该频道，请确保已关注该频道。')
                return

        main = await get_main_module()
        user_client = main.user_client

        message = await user_client.get_messages(chat_id, ids=message_id)
        if not message:
            await reply_and_delete(event,'⚠️ 无法获取该消息，可能是消息已被删除或无权限访问。')
            return

        if message.grouped_id:
            await handle_media_group(client, user_client, chat_id, message, event)
        else:
            await handle_single_message(client, message, event)


    except Exception as e:
        logger.error(f'处理消息链接时出错: {str(e)}')
        await reply_and_delete(event,'⚠️ 处理消息时出错，请确保链接正确且有权限访问该消息。')

async def handle_media_group(client, user_client, chat_id, message, event):
    """处理媒体组消息"""
    files = []  # 将 files 移到外层作用域
    try:
        media_group_messages = []
        caption = None
        buttons = None
        
        async for grouped_message in user_client.iter_messages(
            chat_id,
            limit=20,
            min_id=message.id - 10,
            max_id=message.id + 10
        ):
            if grouped_message.grouped_id == message.grouped_id:
                media_group_messages.append(grouped_message)
                if not caption:
                    caption = grouped_message.text
                    buttons = grouped_message.buttons if hasattr(grouped_message, 'buttons') else None

        if media_group_messages:
            for msg in media_group_messages:
                if msg.media:
                    try:
                        file_path = await msg.download_media(TEMP_DIR)
                        if file_path:
                            files.append(file_path)
                            logger.info(f'已下载媒体文件: {file_path}')
                    except Exception as e:
                        logger.error(f'下载媒体文件失败: {str(e)}')

            if files:
                await client.send_file(
                    event.chat_id,
                    files,
                    caption=caption,
                    parse_mode='Markdown',
                    buttons=buttons
                )
                logger.info(f'已转发媒体组消息，共 {len(files)} 个文件')

    except Exception as e:
        logger.error(f'处理媒体组消息时出错: {str(e)}')
        raise
    finally:
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f'已删除临时文件: {file_path}')
            except Exception as e:
                logger.error(f'删除临时文件失败 {file_path}: {str(e)}')

async def handle_single_message(client, message, event):
    """处理单条消息"""
    parse_mode = 'Markdown'
    buttons = message.buttons if hasattr(message, 'buttons') else None
    file_path = None

    try:
        if message.media:
            file_path = await message.download_media(TEMP_DIR)
            if file_path:
                logger.info(f'已下载媒体文件: {file_path}')
                caption = message.text if message.text else ''
                await client.send_file(
                    event.chat_id,
                    file_path,
                    caption=caption,
                    parse_mode=parse_mode,
                    buttons=buttons
                )
                logger.info('已转发单条媒体消息')
        else:
            await client.send_message(
                event.chat_id,
                message.text,
                parse_mode=parse_mode,
                link_preview=True,
                buttons=buttons
            )
            logger.info('已转发文本消息')

    except Exception as e:
        logger.error(f'处理单条消息时出错: {str(e)}')
        raise
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f'已删除临时文件: {file_path}')
            except Exception as e:
                logger.error(f'删除临时文件失败 {file_path}: {str(e)}')
