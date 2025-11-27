from handlers.button.button_helpers import *
from utils.auto_delete import reply_and_delete

async def show_list(event, command, items, formatter, title, page=1):
    """显示分页列表"""

    PAGE_SIZE = KEYWORDS_PER_PAGE
    total_items = len(items)
    total_pages = (total_items + PAGE_SIZE - 1) // PAGE_SIZE

    if not items:
        try:
            return await event.edit(f'没有找到任何{title}')
        except:
            return await reply_and_delete(event,f'没有找到任何{title}')

    start = (page - 1) * PAGE_SIZE
    end = min(start + PAGE_SIZE, total_items)
    current_items = items[start:end]

    item_list = []
    for i, item in enumerate(current_items):
        formatted_item = formatter(i + start + 1, item)
        if command == 'keyword':
            parts = formatted_item.split('. ', 1)
            if len(parts) == 2:
                number = parts[0]
                content = parts[1]
                if ' (正则)' in content:
                    keyword, regex_mark = content.split(' (正则)')
                    formatted_item = f'{number}. `{keyword}` (正则)'
                else:
                    formatted_item = f'{number}. `{content}`'
        item_list.append(formatted_item)

    buttons = await create_list_buttons(total_pages, page, command)

    text = f'{title}\n{chr(10).join(item_list)}'
    if len(text) > 4096:  # Telegram消息长度限制
        text = text[:4093] + '...'

    try:
        return await event.edit(text, buttons=buttons, parse_mode='markdown')
    except:
        return await reply_and_delete(event,text, buttons=buttons, parse_mode='markdown')

