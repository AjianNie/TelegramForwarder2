from feedgen.feed import FeedGenerator
from datetime import datetime, timedelta
from ..core.config import settings
from ..models.entry import Entry
from typing import List
import logging
import os
from pathlib import Path
import markdown
import re
import json
from models.models import get_session, RSSConfig
from utils.constants import DEFAULT_TIMEZONE
import pytz  

logger = logging.getLogger(__name__)

class FeedService:
    
    
    @staticmethod
    def extract_telegram_title_and_content(content: str) -> tuple[str, str]:
        """从Telegram消息中提取标题和内容
        
        Args:
            content: 原始消息内容
            
        Returns:
            tuple: (标题, 剩余内容)
        """
        if not content:
            logger.info("输入内容为空,返回空标题和内容")
            return "", ""
            
        try:
            config_path = Path(__file__).parent.parent / 'configs' / 'title_template.json'
            logger.info(f"正在读取标题模板配置文件: {config_path}")
            with open(config_path, 'r', encoding='utf-8') as f:
                title_config = json.load(f)
                
            for pattern_info in title_config['patterns']:
                pattern_str = pattern_info['pattern']
                pattern_desc = pattern_info['description']
                logger.debug(f"尝试匹配模式: {pattern_desc} ({pattern_str})")
                
                pattern = re.compile(pattern_str, re.MULTILINE)
                
                match = pattern.match(content)
                if match:
                    title = FeedService.clean_title(match.group(1))
                    start, end = match.span(0)
                    remaining_content = content[end:].lstrip()
                    logger.info(f"成功匹配到标题模式: {pattern_desc}")
                    logger.info(f"原始内容: {content[:100]}...")  # 只显示前100个字符
                    logger.info(f"匹配模式: {pattern_str}")
                    logger.info(f"提取的标题: {title}")
                    logger.info(f"剩余内容长度: {len(remaining_content)} 字符")
                    return title, remaining_content
                    
            logger.info("未匹配到任何标题模式，使用前20个字符作为标题")
            clean_content = FeedService.clean_content(content)
            clean_content = clean_content.replace('\n', ' ').strip()
            title = clean_content[:20]
            if len(clean_content) > 20:
                title += "..."
            logger.debug(f"生成的默认标题: {title}")
            return title, content
            
        except Exception as e:
            logger.error(f"提取标题和内容时出错: {str(e)}")
            return "", content
    

    @staticmethod
    def clean_title(title: str) -> str:
        """清理标题中的特殊字符和格式标记
        
        Args:
            title: 原始标题文本
            
        Returns:
            str: 清理后的标题
        """
        if not title:
            return ""
            
        title = title.replace('*', '')
        
        title = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', title)
            
        title = title.replace('\n', ' ').strip()
        
        return title
    
    @staticmethod
    def clean_content(content: str) -> str:
        """清理内容中的特殊字符和格式标记
        
        Args:
            content: 原始内容文本
            
        Returns:
            str: 清理后的内容
        """
        if not content:
            return ""
            
        content = re.sub(r'^\*{1,2}\s*', '', content)
        
        content = re.sub(r'^\s*\n+', '', content)
        
        return content
    
    @staticmethod
    async def generate_feed_from_entries(rule_id: int, entries: List[Entry], base_url: str = None) -> FeedGenerator:
        """根据真实条目生成Feed"""
        fg = FeedGenerator()
        fg.load_extension('base', atom=True)
        rss_config = None
        
        if base_url is None:
            base_url = f"http://{settings.HOST}:{settings.PORT}"
        
        logger.info(f"生成Feed - 规则ID: {rule_id}, 条目数量: {len(entries)}, 基础URL: {base_url}")
        
        session = get_session()
        try:
            rss_config = session.query(RSSConfig).filter(RSSConfig.rule_id == rule_id).first()
            logger.info(f"获取RSS配置: {rss_config.__dict__}")
            if rss_config and rss_config.enable_rss:
                if rss_config.rule_title:
                    fg.title(rss_config.rule_title)
                else:
                    fg.title(f'TG Forwarder RSS - Rule {rule_id}')
    
                if rss_config.rule_description:
                    fg.description(rss_config.rule_description)
                else:
                    fg.description(f'TG Forwarder RSS - 规则 {rule_id} 的消息')
                    
                fg.language(rss_config.language or 'zh-CN')
            else:
                fg.title(f'TG Forwarder RSS - Rule {rule_id}')
                fg.description(f'TG Forwarder RSS - 规则 {rule_id} 的消息')
                fg.language('zh-CN')
        finally:
            session.close()
        
        fg.link(href=f'{base_url}/rss/feed/{rule_id}')
        
        for entry in entries:
            try:
                fe = fg.add_entry()
                fe.id(entry.id or entry.message_id)


                content = None
                fe.title(entry.title)

                if rss_config.is_ai_extract:
                    fe.title(entry.title)
                    content = entry.content
                else:
                    if rss_config.enable_custom_title_pattern:
                        fe.title(entry.title)
                    if rss_config.enable_custom_content_pattern:
                        content = entry.content
                    # 自动提取标题和内容
                    if rss_config.is_auto_title or rss_config.is_auto_content:
                        extracted_title, extracted_content = FeedService.extract_telegram_title_and_content(entry.content or "")
                        if rss_config.is_auto_title:
                            fe.title(extracted_title)
                        if rss_config.is_auto_content:
                            content = FeedService.convert_markdown_to_html(extracted_content)
                        else:
                            # 如果不自动提取内容，使用原始内容
                            content = FeedService.convert_markdown_to_html(entry.content or "")
                    else:
                        content = FeedService.convert_markdown_to_html(entry.content or "")

                all_media_urls = []  # 存储所有媒体URL用于后续检查
                
                if entry.media:
                    logger.info(f"处理条目 {entry.id} 的媒体文件，数量: {len(entry.media)}")
                    for idx, media in enumerate(entry.media):
                        original_url = media.url if hasattr(media, 'url') else "未知"
                        logger.info(f"媒体 {idx+1}/{len(entry.media)} - 原始URL: {original_url}")
                        
                        media_filename = os.path.basename(media.url.split('/')[-1])
                        media_url = f"/media/{entry.rule_id}/{media_filename}"
                        full_media_url = f"{base_url}{media_url}"
                        all_media_urls.append(full_media_url)
                        
                        logger.info(f"媒体 {idx+1}/{len(entry.media)} - 新URL: {full_media_url}")
                        
                        if media.type.startswith('image/'):
                            try:
                                rule_media_path = settings.get_rule_media_path(entry.rule_id)
                                media_path = os.path.join(rule_media_path, media_filename)
                                
                                img_tag = f'<p><img src="{full_media_url}" alt="{media.filename}" style="max-width:100%;height:auto;display:block;" /></p>'
                                content += img_tag
                                
                                logger.info(f"已添加图片标签到内容中: {media_filename}")
                            except Exception as e:
                                logger.error(f"添加图片标签时出错: {str(e)}")
                        elif media.type.startswith('video/'):
                            display_name = ""
                            if hasattr(media, "original_name") and media.original_name:
                                display_name = media.original_name
                            else:
                                display_name = media.filename
                            
                            video_player = f'''
                            <div style="margin:15px 0;border:1px solid #eee;padding:10px;border-radius:5px;background-color:#f9f9f9;">
                                <video controls width="100%" preload="none" poster="" seekable="true" controlsList="nodownload" style="width:100%;max-width:600px;display:block;margin:0 auto;">
                                    <source src="{full_media_url}" type="{media.type}">
                                    您的阅读器不支持HTML5视频播放/预览
                                </video>
                                <p style="text-align:center;margin-top:8px;font-size:14px;">
                                    <a href="{full_media_url}" target="_blank" style="display:inline-block;padding:6px 12px;background-color:#4CAF50;color:white;text-decoration:none;border-radius:4px;">
                                        <i class="bi bi-download"></i> 下载视频: {display_name}
                                    </a>
                                </p>
                            </div>
                            '''
                            content += video_player
                            
                            logger.info(f"添加视频播放器到内容中: {display_name}")
                        elif media.type.startswith('audio/'):
                            display_name = ""
                            if hasattr(media, "original_name") and media.original_name:
                                display_name = media.original_name
                            else:
                                display_name = media.filename
                                
                            audio_player = f'''
                            <div style="margin:15px 0;border:1px solid #eee;padding:10px;border-radius:5px;background-color:#f9f9f9;">
                                <audio controls style="width:100%;max-width:600px;display:block;margin:0 auto;">
                                    <source src="{full_media_url}" type="{media.type}">
                                    您的阅读器不支持HTML5音频播放/预览
                                </audio>
                                <p style="text-align:center;margin-top:8px;font-size:14px;">
                                    <a href="{full_media_url}" target="_blank">下载音频: {display_name}</a>
                                </p>
                            </div>
                            '''
                            content += audio_player
                            
                            logger.info(f"添加音频播放器到内容中: {display_name}")
                        else:
                            display_name = ""
                            if hasattr(media, "original_name") and media.original_name:
                                display_name = media.original_name
                            else:
                                display_name = media.filename
                            
                            file_tag = f'''
                            <div style="margin:15px 0;padding:10px;border-radius:5px;background-color:#f5f5f5;text-align:center;">
                                <a href="{full_media_url}" target="_blank" style="display:inline-block;padding:8px 16px;background-color:#4CAF50;color:white;text-decoration:none;border-radius:4px;">
                                    下载文件: {display_name}
                                </a>
                            </div>
                            '''
                            content += file_tag
                
                if not content:
                    content = "<p>该消息没有文本内容。</p>"
                    if entry.media and len(entry.media) > 0:
                        content += f"<p>包含 {len(entry.media)} 个媒体文件。</p>"
                
                if not content.startswith("<"):
                    processed_content = ""
                    paragraphs = content.split("\n\n")
                    for p in paragraphs:
                        if p.strip():
                            lines = p.split("\n")
                            processed_content += f"<p>{lines[0]}"
                            for line in lines[1:]:
                                if line.strip():
                                    processed_content += f"<br>{line}"
                            processed_content += "</p>"
                    content = processed_content if processed_content else f"<p>{content}</p>"
                
                content = re.sub(r'<br>\s*<br>', '<br>', content)
                content = re.sub(r'<p>\s*</p>', '', content)
                content = re.sub(r'<p><br></p>', '<p></p>', content)
                
                if "127.0.0.1" in content or "localhost" in content:
                    logger.warning(f"内容中包含硬编码的本地地址，将替换为: {base_url}")
                    content = content.replace(f"http://127.0.0.1:{settings.PORT}", base_url)
                    content = content.replace(f"http://localhost:{settings.PORT}", base_url)
                    content = content.replace(f"http://{settings.HOST}:{settings.PORT}", base_url)
                
                if entry.media:
                    for media in entry.media:
                        try:
                            media_filename = os.path.basename(media.url.split('/')[-1])
                            full_media_url = f"{base_url}/media/{entry.rule_id}/{media_filename}"
                            if media.type.startswith('image/') and full_media_url not in content:
                                img_tag = f'<p><img src="{full_media_url}" alt="{media.filename}" style="max-width:100%;" /></p>'
                                content += img_tag
                                logger.info(f"添加缺失的图片标签: {media_filename}")
                            
                            logger.info(f"添加媒体附件: {full_media_url}, 类型: {media.type}, 大小: {media.size}")
                            
                            # 添加enclosure
                            fe.enclosure(
                                url=full_media_url,
                                length=str(media.size) if hasattr(media, 'size') else "0",
                                type=media.type if hasattr(media, 'type') else "application/octet-stream"
                            )
                        except Exception as e:
                            logger.error(f"添加媒体附件时出错: {str(e)}")
                
                fe.content(content, type='html')
                
                fe.description(content)
                
                try:
                    published_dt = datetime.fromisoformat(entry.published)
                    fe.published(published_dt)
                except ValueError:
                    try:
                        tz = pytz.timezone(DEFAULT_TIMEZONE)
                        fe.published(datetime.now(tz))
                    except Exception as tz_error:
                        logger.warning(f"时区设置错误: {str(tz_error)}，使用UTC时区")
                        fe.published(datetime.now(pytz.UTC))
                
                if entry.author:
                    fe.author(name=entry.author)
                
                if entry.link:
                    fe.link(href=entry.link)
            except Exception as e:
                logger.error(f"添加条目到Feed时出错: {str(e)}")
                continue
        
        return fg
    
    @staticmethod
    def _extract_chat_name(link: str) -> str:
        """从Telegram链接中提取频道/群组名称"""
        if not link or 't.me/' not in link:
            return ""
        
        try:
            parts = link.split('t.me/')
            if len(parts) < 2:
                return ""
            
            channel_part = parts[1].split('/')[0]
            return channel_part
        except Exception:
            return ""



    @staticmethod
    def convert_markdown_to_html(text):
        """将Markdown格式转换为HTML，使用标准markdown库，并保留换行结构"""
        if not text:
            return ""
        
        try:
            # 预处理文本，确保连续的换行符被正确转换成段落
            # 先将连续的多个换行替换为特殊标记
            text = re.sub(r'\n{2,}', '\n\n<!-- paragraph -->\n\n', text)
            
            lines = text.split('\n')
            processed_lines = []
            for line in lines:
                if line.startswith('#'):
                    line = '\\' + line
                processed_lines.append(line + '  ')  # 添加两个空格确保换行
            text = '\n'.join(processed_lines)
            
            html = markdown.markdown(text, extensions=['extra'])
            
            html = html.replace('<p><!-- paragraph --></p>', '</p><p>')
            
            return html
        except Exception as e:
            logger.error(f"Markdown转换异常: {str(e)}")
            
            text = re.sub(r'\n{2,}', '</p><p>', text)
            
            text = text.replace('\n', '<br>')
            
            return f"<p>{text}</p>"
    
    @staticmethod
    def generate_test_feed(rule_id: int, base_url: str = None) -> FeedGenerator:
        """生成测试Feed，当没有真实条目数据时使用
        
        Args:
            rule_id: 规则ID
            base_url: 请求的基础URL，用于生成链接
            
        Returns:
            FeedGenerator: 配置好的测试Feed生成器
        """
        fg = FeedGenerator()
        fg.load_extension('base', atom=True)
        rss_config = None
        
        if base_url is None:
            base_url = f"http://{settings.HOST}:{settings.PORT}"
        
        logger.info(f"生成测试Feed - 规则ID: {rule_id}, 基础URL: {base_url}")
        
        session = get_session()
        try:
            rss_config = session.query(RSSConfig).filter(RSSConfig.rule_id == rule_id).first()
            logger.info(f"获取RSS配置: {rss_config}")
            
            if rss_config and rss_config.enable_rss:
                if rss_config.rule_title:
                    fg.title(rss_config.rule_title)
                else:
                    fg.title(f'')
    
                if rss_config.rule_description:
                    fg.description(rss_config.rule_description)
                else:
                    fg.description(f' ')
                    
                fg.language(rss_config.language or 'zh-CN')
        finally:
            session.close()
        
        feed_url = f'{base_url}/rss/feed/{rule_id}'
        logger.info(f"设置Feed链接: {feed_url}")
        fg.link(href=feed_url)
        
        try:
            tz = pytz.timezone(DEFAULT_TIMEZONE)
        except Exception as tz_error:
            logger.warning(f"时区设置错误: {str(tz_error)}，使用UTC时区")
            tz = pytz.UTC
        
        # # 只添加一条测试条目
        # try:
        #     fe = fg.add_entry()
            
        #     # 设置测试条目ID和标题
        #     entry_id = f"test-{rule_id}-1"
        #     fe.id(entry_id)
        #     fe.title(f"测试条目 - 规则 {rule_id}")
            
        #     # 生成内容，包括测试说明
        #     current_time = datetime.now(tz)
        #     content = f'''
        #     <p>这是一个测试条目，由系统自动生成，因为规则 {rule_id} 当前没有任何消息数据。</p>
        #     <p>当有消息被转发时，真实的条目将会在这里显示。</p>
        #     <hr>
        #     <p>此测试条目生成于: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}</p>
        #     '''
            
        #     # 设置内容和描述
        #     fe.content(content, type='html')
        #     fe.description(content)
            
        #     # 设置测试条目的发布时间
        #     fe.published(datetime.now(tz))
            
        #     # 设置测试条目的作者和链接
        #     fe.author(name="TG Forwarder System")
            
        #     # 使用正确的URL格式
        #     entry_url = f"{base_url}/rss/feed/{rule_id}?entry={entry_id}"
        #     logger.info(f"添加测试条目链接: {entry_url}")
        #     fe.link(href=entry_url)
            
        #     logger.info(f"成功添加测试条目")
        # except Exception as e:
        #     logger.error(f"添加测试条目时出错: {str(e)}")
        
        # logger.info(f"测试Feed生成完成，包含1个测试条目")
        return fg