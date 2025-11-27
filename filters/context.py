import copy

class MessageContext:
    """
    消息上下文类，包含处理消息所需的所有信息
    """
    
    def __init__(self, client, event, chat_id, rule):
        """
        初始化消息上下文
        
        Args:
            client: 机器人客户端
            event: 消息事件
            chat_id: 聊天ID
            rule: 转发规则
        """
        self.client = client
        self.event = event
        self.chat_id = chat_id
        self.rule = rule
        
        self.original_message_text = event.message.text or ''
        
        self.message_text = event.message.text or ''
        
        self.check_message_text = event.message.text or ''
        
        self.media_files = []
        
        self.sender_info = ''
        
        self.time_info = ''
        
        self.original_link = ''
        
        self.buttons = event.message.buttons if hasattr(event.message, 'buttons') else None
        
        self.should_forward = True
        
        self.is_media_group = event.message.grouped_id is not None
        self.media_group_id = event.message.grouped_id
        self.media_group_messages = []
        
        self.skipped_media = []
        
        self.errors = []
        
        self.forwarded_messages = []
        
        self.comment_link = None
        
    def clone(self):
        """创建上下文的副本"""
        return copy.deepcopy(self) 