import logging
import os

logger = logging.getLogger(__name__)

async def get_media_size(media):
    """获取媒体文件大小"""
    if not media:
        return 0

    try:
        if hasattr(media, 'document') and media.document:
            return media.document.size

        if hasattr(media, 'photo') and media.photo:
            largest_photo = max(media.photo.sizes, key=lambda x: x.size if hasattr(x, 'size') else 0)
            return largest_photo.size if hasattr(largest_photo, 'size') else 0

        if hasattr(media, 'size'):
            return media.size

    except Exception as e:
        logger.error(f'获取媒体大小时出错: {str(e)}')

    return 0

async def get_max_media_size():
    """获取媒体文件大小上限"""
    max_media_size_str = os.getenv('MAX_MEDIA_SIZE')
    if not max_media_size_str:
        logger.error('未设置 MAX_MEDIA_SIZE 环境变量')
        raise ValueError('必须在 .env 文件中设置 MAX_MEDIA_SIZE')
    return float(max_media_size_str) * 1024 * 1024  # 转换为字节，支持小数