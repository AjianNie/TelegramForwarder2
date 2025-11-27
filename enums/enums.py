import enum

class ForwardMode(enum.Enum):
    WHITELIST = 'whitelist'
    BLACKLIST = 'blacklist'
    BLACKLIST_THEN_WHITELIST = 'blacklist_then_whitelist'
    WHITELIST_THEN_BLACKLIST = 'whitelist_then_blacklist'


class PreviewMode(enum.Enum):
    ON = 'on'
    OFF = 'off'
    FOLLOW = 'follow'  # 跟随原消息的预览设置

class MessageMode(enum.Enum):
    MARKDOWN = 'Markdown'
    HTML = 'HTML' 

class AddMode(enum.Enum):
    WHITELIST = 'whitelist'
    BLACKLIST = 'blacklist'

class HandleMode(enum.Enum):
    FORWARD = 'FORWARD'
    EDIT = 'EDIT'