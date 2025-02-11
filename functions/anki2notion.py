import sys
import os
import traceback
from datetime import datetime
import time
import json

# 将lib目录添加到Python路径
current_dir = os.path.dirname(__file__)
lib_path = os.path.abspath(os.path.join(current_dir, '..', 'lib'))
if lib_path not in sys.path:
    sys.path.append(lib_path)

# 导入必要的库
from aqt import mw
from aqt.utils import showInfo, showWarning
from anki.notes import Note
from notion_client import Client

# 导入 my_helpers 文件中的函数
from .my_helpers import extract_database_id, print_all_var, debug_print

def anki_to_notion():
    """将Anki中的卡片导入到Notion"""
    try:
        # 加载配置
        config_path = os.path.abspath(os.path.join(current_dir, '..', 'config.json'))
        if not os.path.exists(config_path):
            showWarning("未找到配置文件，请先在插件设置中配置必要的信息。")
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        retain_source = config.get('retain_source_note', True)

        notion_token = config.get('notion_token')
        notion_db_url = config.get('notion_database_url')
        anki_query = config.get('anki_query_string', '')
        duplicate_handling = config.get('duplicate_handling_way', 'keep')

        if not (notion_token and notion_db_url):
            showWarning("Notion Token或数据库URL未配置，请在插件设置中填写。")
            return

        # 初始化Notion客户端
        notion = Client(auth=notion_token)

        # 提取Notion数据库ID
        database_id = extract_database_id(notion_db_url)
        if not database_id:
            showWarning("无法从提供的URL中提取Notion数据库ID，请检查URL格式。")
            return

        # 获取当前数据库的详细信息
        database_info = notion.databases.retrieve(database_id=database_id)
        current_properties = database_info.get('properties', {})

        # 获取现有的标题属性名称
        title_property_name = None
        for prop_name, prop_info in current_properties.items():
            if prop_info.get('type') == 'title':
                title_property_name = prop_name
                break
        if not title_property_name:
            showWarning("无法找到数据库的标题属性，请检查数据库结构。")
            return

        # 查询Anki卡片
        note_ids = mw.col.find_notes(anki_query)
        if not note_ids:
            showInfo("未找到符合条件的Anki卡片。")
            return

        # 收集所有 Anki 卡片的字段名和元数据字段名
        all_field_names = set()
        metadata_field_names = {'Review Count', 'Ease Factor', 'Interval', 'Card Type', 'Due Date',
                                'Creation Time', 'Modification Time', 'Tags', 'Suspended', 'Lapses','Difficulty','Stability','Retrievability'}
        for note_id in note_ids:
            note = mw.col.getNote(note_id)
            all_field_names.update(note.keys())

        # 构建需要添加到数据库的新属性
        new_properties = {}

        # 添加Anki笔记字段到数据库属性
        for field_name in all_field_names:
            if field_name == title_property_name:
                continue  # 已存在的标题属性，不需要创建
            else:
                # 检查属性是否已存在
                if field_name not in current_properties:
                    # 创建新属性，使用 rich_text 类型
                    new_properties[field_name] = {
                        'rich_text': {}
                    }
                    # 更新 current_properties，防止重复添加
                    current_properties[field_name] = {'rich_text': {}}

        # 添加额外的属性（如Anki ID和Deck）
        if 'Anki ID' not in current_properties:
            new_properties['Anki ID'] = {
                'number': {}
            }
            current_properties['Anki ID'] = {'number': {}}
        if 'Deck' not in current_properties:
            new_properties['Deck'] = {
                'rich_text': {}
            }
            current_properties['Deck'] = {'rich_text': {}}

        # 添加元数据字段到数据库属性
        for metadata_field in metadata_field_names:
            if metadata_field not in current_properties:
                if metadata_field in ['Creation Time', 'Modification Time', 'Due Date']:
                    new_properties[metadata_field] = {'date': {}}
                    current_properties[metadata_field] = {'date': {}}
                elif metadata_field == 'Tags':
                    new_properties[metadata_field] = {'multi_select': {}}
                    current_properties[metadata_field] = {'multi_select': {}}
                elif metadata_field == 'Suspended':
                    new_properties[metadata_field] = {'checkbox': {}}
                    current_properties[metadata_field] = {'checkbox': {}}
                else:
                    new_properties[metadata_field] = {'number': {}}
                    current_properties[metadata_field] = {'number': {}}
            else:
                # 检查并更新已存在的属性类型
                if metadata_field == 'Due Date' and current_properties[metadata_field]['type'] != 'date':
                    new_properties[metadata_field] = {'date': {}}
                    current_properties[metadata_field] = {'date': {}}

        # 检查并添加 'Note Type' 属性
        if 'Note Type' not in current_properties:
            new_properties['Note Type'] = {
                'rich_text': {}
            }
            current_properties['Note Type'] = {'rich_text': {}}

        # 检查并添加 'First Field' 属性
        if 'First Field' not in current_properties:
            new_properties['First Field'] = {
                'rich_text': {}
            }
            current_properties['First Field'] = {'rich_text': {}}

        # 更新数据库，添加新的属性
        if new_properties:
            notion.databases.update(
                database_id=database_id,
                properties=new_properties
            )

        # 遍历Anki卡片，导入到Notion
        for note_id in note_ids:
            note = mw.col.getNote(note_id)
            # 检查是否存在非空的"notion正文"字段
            notion_content = ""
            if "notion正文" in note:
                notion_content = process_notion_content_in_anki(note["notion正文"].strip())
            # 构建Notion页面属性
            properties = build_notion_properties(note, title_property_name)
            # 如果存在"notion正文"字段，则不将其作为模板字段导入
            if "notion正文" in properties:
                del properties["notion正文"]
            # 构造页面正文的 children 块（使用"notion正文"字段的内容）
            children = None
            if notion_content:
                children = [{
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {
                                "content": notion_content
                            }
                        }]
                    }
                }]
            # 处理重复项并创建页面，将 children 参数传入
            handle_duplicates_and_create_page(notion, database_id, properties, duplicate_handling, children)
            
            # 在成功导入 Notion 后，根据配置删除 Anki 中的笔记
            if not retain_source:
                mw.col.remNotes([note_id])

        # 同步完毕后保存 Anki 数据库
        mw.col.save()

        showInfo("Anki卡片已成功同步到Notion。")

    except Exception as e:
        error_message = f"同步过程中发生错误：\n{str(e)}\n{traceback.format_exc()}"
        showWarning(error_message)

def build_notion_properties(note, title_property_name):
    """根据 Anki 笔记构建 Notion 页面属性"""
    properties = {}

    # 设置标题属性
    title_value = note[title_property_name] if title_property_name in note else ""
    properties[title_property_name] = {
        'title': [{'type': 'text', 'text': {'content': title_value}}]
    }

    # 添加 Anki ID
    properties['Anki ID'] = {
        'number': note.id
    }

    # 添加 Deck 名称
    deck_id = note.cards()[0].did
    deck_name = mw.col.decks.get(deck_id)['name']
    properties['Deck'] = {
        'rich_text': [{'type': 'text', 'text': {'content': deck_name}}]
    }

    # 添加 Note Type（模型名称）
    model_name = note.model()['name']
    properties['Note Type'] = {
        'rich_text': [{'type': 'text', 'text': {'content': model_name}}]
    }

    # 添加 First Field（首字段名称）
    all_fields = list(note.keys())
    first_field_name = all_fields[0] if all_fields else ""
    properties['First Field'] = {
        'rich_text': [{'type': 'text', 'text': {'content': first_field_name}}]
    }

    # 添加其它模板字段
    for field_name in note.keys():
        if field_name == title_property_name:
            continue
        field_value = note[field_name]
        # 如果字段名为 "notion正文" 且内容为空，则不将该字段作为模板字段导入
        if field_name == "notion正文":
            continue
        properties[field_name] = {
            'rich_text': [{'type': 'text', 'text': {'content': field_value}}]
        }

    # 添加标签（Tags）
    tags = note.tags
    properties['Tags'] = {
        'multi_select': [{'name': tag} for tag in tags]
    }

    # 添加学习记录元数据
    card = note.cards()[0]

    # 复习次数
    properties['Review Count'] = {
        'number': card.reps
    }

    # 熟练度因子（Ease Factor），Anki 中以 1000 为基数
    properties['Ease Factor'] = {
        'number': card.factor / 1000
    }

    # 间隔天数
    properties['Interval'] = {
        'number': card.ivl
    }

    # 卡片类型
    properties['Card Type'] = {
        'number': card.type
    }

    # 获取本地时区
    local_timezone = datetime.now().astimezone().tzinfo

    # Creation Time（使用 note.id，单位为毫秒）
    creation_time = datetime.fromtimestamp(note.id / 1000, tz=local_timezone)
    properties['Creation Time'] = {
        'date': {'start': creation_time.isoformat()}
    }

    # Modification Time（note.mod，单位为秒）
    modification_time = datetime.fromtimestamp(note.mod, tz=local_timezone)
    properties['Modification Time'] = {
        'date': {'start': modification_time.isoformat()}
    }

    # 添加到期日期处理
    due_date = get_card_due_date(card)
    if due_date:
        properties['Due Date'] = {
            'date': {'start': due_date.isoformat()}
        }

    # 是否挂起（Suspended）
    properties['Suspended'] = {
        'checkbox': card.queue == -1
    }

    # 遗忘次数
    properties['Lapses'] = {
        'number': card.lapses
    }

    # 从卡片的 data 字段中提取 FSRS 参数
    write_fsrs_data(note, properties)

    return properties

def get_card_due_date(card):
    """根据卡片信息获取到期日期"""
    import time

    col = mw.col
    if card.queue < 0:
        # 卡片被挂起或已删除
        return None
    elif card.type == 0:
        # 新卡片，due 表示新卡位置，无法确定具体日期
        return None
    elif card.type == 1:
        # 学习中卡片，due 是相对时间，单位为秒
        due = time.time() + (card.due * 60)
        return datetime.fromtimestamp(due)
    elif card.type == 2:
        # 复习卡片，due 是天数
        due = (card.due - col.sched.today) * 86400 + time.time()
        return datetime.fromtimestamp(due)
    else:
        return None

def handle_duplicates_and_create_page(notion, database_id, properties, handling_way, children=None):
    note_type = properties['Note Type']['rich_text'][0]['text']['content']
    first_field_name = properties['First Field']['rich_text'][0]['text']['content']
    first_field_value = properties[first_field_name]['rich_text'][0]['text']['content']

    # 构建查询过滤器
    filter_condition = {
        "and": [
            {
                "property": "Note Type",
                "rich_text": {
                    "equals": note_type
                }
            },
            {
                "property": first_field_name,
                "rich_text": {
                    "equals": first_field_value
                }
            }
        ]
    }

    # 查询是否存在重复页面
    response = notion.databases.query(
        database_id=database_id,
        filter=filter_condition
    )

    if response['results']:
        # 存在重复项
        page_id = response['results'][0]['id']
        if handling_way == 'keep':
            # 保留 Notion 中的页面，不进行操作
            pass
        elif handling_way == 'overwrite':
            # 覆盖 Notion 中的页面
            try:
                    if children:
                        notion.pages.update(parent={"database_id": database_id}, properties=properties, children=children)
                    else:
                        notion.pages.update(parent={"database_id": database_id}, properties=properties)
            except TypeError as e:
                    if "missing 1 required positional argument: 'page_id'" in str(e):
                        # 捕获到缺少 page_id 参数的错误，说明要覆盖的页面不存在，需要执行copy操作(自动创建新页面)
                        if children:
                            notion.pages.create(parent={"database_id": database_id}, properties=properties, children=children)
                        else:
                            notion.pages.create(parent={"database_id": database_id}, properties=properties)
                    else:
                        raise e
        elif handling_way == 'copy':
            # 创建新页面（可能导致重复）
            if children:
                notion.pages.create(parent={"database_id": database_id}, properties=properties, children=children)
            else:
                notion.pages.create(parent={"database_id": database_id}, properties=properties)
    else:
        # 不存在重复，直接创建新页面
        if children:
            notion.pages.create(parent={"database_id": database_id}, properties=properties, children=children)
        else:
            notion.pages.create(parent={"database_id": database_id}, properties=properties)

def timestamp_to_iso8601(ts):
    """将时间戳转换为 ISO 8601 格式"""
    return datetime.fromtimestamp(ts).isoformat()
def write_fsrs_data(note, properties):
    # 从数据库直接获取卡片数据（兼容 Anki 24.11+）
    card = note.cards()[0]
    try:
        # 使用 Anki 数据库查询获取原始数据
        card_data = mw.col.db.scalar(
            "SELECT data FROM cards WHERE id = ?", card.id
        )
        
        if card_data:
            # 使用 FSRS Helper 的解析方式
            card_data_json = json.loads(card_data)
            # 提取 FSRS 参数（使用 FSRS Helper 的字段名）
            if 'd' in card_data_json:  # 难度
                properties['Difficulty'] = {'number': card_data_json['d']}
            if 's' in card_data_json:  # 稳定性
                properties['Stability'] = {'number': card_data_json['s']}
            if 'dr' in card_data_json:  # 可提取性
                properties['Retrievability'] = {'number': card_data_json['dr']}
                
    except Exception as e:
        debug_print(f"解析卡片数据失败：{str(e)}")
        # 使用 helpers 中的调试函数记录错误
        from .my_helpers import log_error
        log_error(f"Card {card.id} 数据解析错误", e)

    return properties
def process_notion_content_in_anki(html_content):
    """
    将 Anki 笔记中 "notion正文" 字段的 HTML 格式内容转换为 Notion 兼容的格式（类似 Markdown 格式）。
    该函数实现的逻辑与 notion2anki 中 process_notion_children 函数相反。
    """
    import re
    from html import unescape

    # 1. 处理代码块：将 <pre><code class="语言">代码内容</code></pre> 转换为 Markdown 格式的代码块
    def replace_code_block(match):
        lang = match.group(1) if match.group(1) else ''
        code_content = match.group(2)
        code_content = unescape(code_content)
        return f"```{lang}\n{code_content}\n```"
    
    html_content = re.sub(
        r'<pre><code(?: class="([^"]*)")?>(.*?)</code></pre>',
        replace_code_block,
        html_content,
        flags=re.DOTALL
    )

    # 2. 处理内联代码：将 <code>代码</code> 转换为 `代码`
    html_content = re.sub(
        r'<code>(.*?)</code>',
        lambda m: f"`{unescape(m.group(1))}`",
        html_content,
        flags=re.DOTALL
    )

    # 3. 还原加粗文本：将 <strong>文本</strong> 转换为 **文本**
    html_content = re.sub(r'<strong>(.*?)</strong>', r'**\1**', html_content, flags=re.DOTALL)

    # 4. 还原斜体文本：将 <em>文本</em> 转换为 _文本_
    html_content = re.sub(r'<em>(.*?)</em>', r'_\1_', html_content, flags=re.DOTALL)

    # 5. 还原删除线：将 <del>文本</del> 转换为 ~~文本~~
    html_content = re.sub(r'<del>(.*?)</del>', r'~~\1~~', html_content, flags=re.DOTALL)

    # 6. 去除 span 标签及其属性，保留内部文本
    html_content = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', html_content, flags=re.DOTALL)

    # 7. 处理无序列表：将 <ul> 中的<li>元素转换为以"-"开头的列表项
    def replace_ul(match):
        list_content = match.group(1)
        items = re.findall(r'<li>(.*?)</li>', list_content, flags=re.DOTALL)
        return "\n".join(f"- {item.strip()}" for item in items)
    
    html_content = re.sub(r'<ul>(.*?)</ul>', replace_ul, html_content, flags=re.DOTALL)

    # 8. 处理有序列表：将 <ol> 中的<li>元素转换为以"数字. "形式呈现
    def replace_ol(match):
        list_content = match.group(1)
        items = re.findall(r'<li>(.*?)</li>', list_content, flags=re.DOTALL)
        return "\n".join(f"{i+1}. {item.strip()}" for i, item in enumerate(items))
    
    html_content = re.sub(r'<ol>(.*?)</ol>', replace_ol, html_content, flags=re.DOTALL)

    # 9. 处理段落标签：将 <p>...</p> 替换为段落内容，并以换行符分隔
    def replace_paragraph(match):
        text = match.group(1).strip()
        return text + "\n"
    
    html_content = re.sub(r'<p>(.*?)</p>', replace_paragraph, html_content, flags=re.DOTALL)

    # 10. 移除剩余的 HTML 标签
    html_content = re.sub(r'<[^>]+>', '', html_content)

    # 11. 反转义 HTML 实体
    html_content = unescape(html_content)

    return html_content.strip()

