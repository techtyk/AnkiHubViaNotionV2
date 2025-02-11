import sys
import os
import json
import re
import traceback
import inspect
import aqt
import time
import html

# 将 lib 目录添加到 Python 路径
current_dir = os.path.dirname(__file__)
lib_path = os.path.abspath(os.path.join(current_dir, '..', 'lib'))
if lib_path not in sys.path:
    sys.path.append(lib_path)

# 导入必要的库
from aqt import mw
from aqt.utils import showInfo, showWarning
from anki.notes import Note
from anki import decks
from anki.models import NotetypeDict
from anki import notes
from anki import collection
from notion_client import Client
from datetime import datetime, timezone, timedelta
#from anki.cards import CardType  # 卡片类型枚举（例如 CardType.REV 表示复习卡片）
from anki.consts import REVLOG_REV
from anki.utils import stripHTMLMedia

# 导入 my_helpers 文件中的函数
from .my_helpers import (
    extract_database_id,
    get_rich_text_property,
    get_multi_select_property,
    timestamp_to_iso8601,
    print_all_var,
    debug_print,
    debug_card_state,
    debug_sql_params,
    add_review_log,
    load_config,
    # 其他需要的函数
)

def notion_to_anki():
    """将 Notion 中的卡片导入到 Anki"""
    try:
        # 加载配置
        config_path = os.path.abspath(os.path.join(current_dir, '..', 'config.json'))
        if not os.path.exists(config_path):
            showWarning("未找到配置文件，请先在插件设置中配置必要的信息。")
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        notion_token = config.get('notion_token')
        notion_db_url = config.get('notion_database_url')
        duplicate_handling = config.get('duplicate_handling_way', 'keep')
        retain_source = config.get('retain_source_note', True)

        if not (notion_token and notion_db_url):
            showWarning("Notion Token 或数据库 URL 未配置，请在插件设置中填写。")
            return

        # 初始化 Notion 客户端
        notion = Client(auth=notion_token)

        # 提取 Notion 数据库 ID
        database_id = extract_database_id(notion_db_url)
        if not database_id:
            showWarning("无法从提供的 URL 中提取 Notion 数据库 ID，请检查 URL 格式。")
            return

        # 查询需要导入的 Notion 页面
        pages = query_notion_pages(notion, database_id)
        if not pages:
            showInfo("未找到需要导入的 Notion 卡片。")
            return

        # 在 notion_to_anki 函数开头添加配置检查
        if config.get('retain_notion_children'):
            for page in pages:
                processed_children = save_notion_children_and_update_anki_model(page)
                # 将返回的 processed_children 添加到页面数据中，后续构造 note_meta 时可以读取到
                page['processed_notion_children'] = processed_children


        # 导入卡片到 Anki
        for page in pages:
            try:
                # 构建 Anki 笔记数据
                note_fields, note_meta = build_anki_note_fields(page)
                # 检查重复处理策略并添加笔记
                handle_duplicates_and_add_note(note_fields, note_meta, duplicate_handling)
            except Exception as e:
                # 如果导入某张卡片时发生异常，显示警告并继续
                error_message = f"导入页面 {page['id']} 时发生错误：\n{str(e)}\n{traceback.format_exc()}"
                showWarning(error_message)

        # 在成功导入 Anki 后，根据配置删除 Notion 中的笔记
        if not retain_source:
            for page in pages:
                notion.pages.update(page_id=page['id'], archived=True)

        # 刷新 Anki 界面
        mw.reset()
        showInfo("Notion 卡片已成功导入到 Anki。")

    except Exception as e:
        error_message = f"导入过程中发生错误：\n{str(e)}\n{traceback.format_exc()}"
        showWarning(error_message)

def query_notion_pages(notion, database_id):
    """查询需要导入的 Notion 页面，筛选具有 'readyMove' 标签的页面"""
    try:
        # 查询数据库，筛选具有 'readyMove' 标签的页面
        results = []
        has_more = True
        next_cursor = None

        while has_more:
            query_params = {
                "database_id": database_id,
                "filter": {
                    "property": "Tags",
                    "multi_select": {
                        "contains": "readyMove"
                    }
                },
                "page_size": 100  # 每次查询最大返回 100 条记录
            }
            if next_cursor:
                query_params["start_cursor"] = next_cursor

            response = notion.databases.query(**query_params)
            results.extend(response.get('results', []))
            has_more = response.get('has_more', False)
            next_cursor = response.get('next_cursor', None)

        return results

    except Exception as e:
        showWarning(f"查询 Notion 页面时发生错误：{str(e)}")
        return []

def get_rich_text_content(rich_text_list):
    """从富文本列表中提取纯文本内容"""
    texts = []
    for rich_text in rich_text_list:
        plain_text = rich_text.get('plain_text', '')
        texts.append(plain_text)
    return ''.join(texts)

def update_existing_note(note, note_fields, note_meta):
    """
    更新已存在的笔记字段和元数据（包括学习记录）。
    在函数结尾处增加判断：如果配置中设置了保留 notion 正文（retain_notion_children 为 True）
    且 processed_notion_children 非空，则调用 write_notion_children_to_anki_note 函数，
    使用 processed_notion_children 更新笔记中的"notion正文"字段。
    """
    col = mw.col
    model = note.model()
    # 更新模板字段
    for field_name, field_value in note_fields.items():
        if field_name in note:
            note[field_name] = field_value
        else:
            # 如果字段不存在于模型中，动态添加该字段
            new_field = col.models.newField(field_name)
            col.models.addField(model, new_field)
            col.models.save(model)
            note = col.getNote(note.id)
            note[field_name] = field_value

    # 更新元数据与学习记录
    update_fsrs_data(note, note_meta)
    update_note_meta(note, note_meta)



    # 新增部分：检查配置并更新 notion 正文
    from .my_helpers import load_config
    config = load_config()

    processed_notion_children = note_meta.get('processed_notion_children')
    if config.get('retain_notion_children') and processed_notion_children:
        write_notion_children_to_anki_note(note, processed_notion_children)



    col.update_note(note)

def update_note_meta(note, note_meta):
    """更新笔记的元数据及学习记录"""
    try:
        col = mw.col
        # 更新标签
        if 'tags' in note_meta:
            note.tags = note_meta['tags']
        # 更新牌组
        deck_name = note_meta.get('deck', 'Default')
        deck_id = col.decks.id(deck_name)
        for card in note.cards():
            card.did = deck_id
            # 更新学习记录
            study_fields_map = {
                'review_count': 'reps',    # 复习次数
                'ease_factor': 'factor',   # 易记系数（需要处理）
                'interval': 'ivl',         # 间隔
                'card_type': 'type',       # 卡片类型
                'due_date': 'due',         # 到期时间（需要处理）
                'lapses': 'lapses'         # 失误次数
            }        
            for meta_key, card_attr in study_fields_map.items():

                if meta_key in note_meta and note_meta[meta_key] is not None:
                    value = note_meta[meta_key]
                    if meta_key == 'due_date':
                        continue
                    # 特殊处理 ease_factor
                    if meta_key == 'ease_factor':
                        value = int(float(value) * 1000)                
                    else:
                        # 确保其他值也是整数
                        value = int(value)
                    # 使用处理后的 value 赋值
                    setattr(card, card_attr, value)
                    # 单独处理 due_date
            if note_meta.get('card_type') == 1 and note_meta.get('due_date') not in (None, ""):
                # 对于学习中的卡片，不处理（之后视情况补充）
                pass
            if note_meta.get('card_type') == 2 and note_meta.get('due_date') not in (None, ""):
                
                card_state_before = debug_card_state(card, '修改前')
                try:
                    value = note_meta['due_date']
                    due_date = datetime.fromisoformat(value)
                    # 确保包含时区信息
                    if due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=timezone.utc)
                    due_date = due_date.astimezone()  # 转换为本地时区 
                    # 时区转换逻辑...
                    due_date_utc = due_date.astimezone(timezone.utc)
                    current_utc = datetime.now(timezone.utc)
                    # 确保未来日期（Anki 不允许设置过去日期）
                    if due_date_utc < current_utc:
                        due_date_utc = current_utc + timedelta(days=1)
                    # 必须显式设置卡片类型
                    card.type = 2
                    card.queue = 2
                    days_offset = (due_date_utc.date() - current_utc.date()).days

                    # 手动同步状态
                    col.sched.reset_cards(ids=[int(card.id)])
                    card.due = col.sched.today + days_offset
                    col.update_card(card)   
                    # 设置卡片核心属性
                    card.type = 2
                    card.queue = 2
                    card.ivl = max(1, note_meta.get('interval', 1))  # 确保间隔≥1
                    card.factor = int(float(note_meta.get('ease_factor', 2.5)) * 1000)
                    card.reps = max(1, note_meta.get('review_count', 1))  # 复习次数≥1
                    card.lapses = note_meta.get('lapses', 0)
                        
                except Exception as e:
                    debug_print(due_date_error=str(e))

            # 导入暂停状态
            if 'suspended' in note_meta and note_meta['suspended'] is not None:
                if note_meta['suspended']:
                    # 挂起卡片
                    card.queue = -1
                    card.due = 0
                else:
                    # 取消挂起卡片
                    card.queue = 0
                    card.due = col.nextID("pos")

            # 保存卡片的修改
            col.update_card(card)

        # 保存笔记的修改
        note.flush()

        # 保存更改并刷新界面
        col.save()
        mw.reset()

    except Exception as e:
        # 抛出异常以便外层捕获
        raise e

def create_new_note(note_fields, note_meta):
    """创建新的笔记并返回 note 对象"""
    col = mw.col

    try:
        # 获取或创建牌组
        deck_name = note_meta.get('deck', 'Default')
        deck_id = col.decks.id(deck_name)

        # 获取或创建模型（Note Type）
        model_name = note_meta.get('note_type', 'Basic')
        model = col.models.byName(model_name)
        if not model:
            # 创建新模型
            model = col.models.new(model_name)
            col.models.add(model)

        # 创建新笔记
        note = Note(col, model)

        # 设置笔记字段，只导入非空字段，且不包括 'First Field'
        for field_name, field_value in note_fields.items():
            if field_value.strip() == '':
                continue  # 跳过空字段
            if field_name == 'First Field':
                continue  # 跳过 'First Field' 字段
            if field_name in note:
                note[field_name] = field_value
            else:
                # 如果字段不存在于模型中，添加新的字段
                new_field = col.models.newField(field_name)
                col.models.addField(model, new_field)
                col.models.save(model)  # 保存模型更改
                # 重新创建笔记以应用新的模型
                note = Note(col, model)
                note[field_name] = field_value

        # 设置标签
        if 'tags' in note_meta:
            note.tags = note_meta['tags']

        # 设置笔记的牌组 ID
        note.model()['did'] = deck_id

        # 添加笔记到集合
        col.addNote(note)
        col.save()

        # 调用 update_note_meta 函数，更新元数据和学习记录，包括暂停状态
        update_note_meta(note, note_meta)
        update_fsrs_data(note, note_meta)



        # 新增部分：检查配置并更新 notion 正文
        from .my_helpers import load_config
        config = load_config()
        processed_notion_children = note_meta.get('processed_notion_children')
        if config.get('retain_notion_children') and processed_notion_children:
            write_notion_children_to_anki_note(note, processed_notion_children)



        return note  # 添加返回语句

    except Exception as e:
        error_message = f"创建新笔记时发生错误：{str(e)}\n{traceback.format_exc()}"
        showWarning(error_message)

def extract_note_meta(page):
    """从 Notion 页面提取笔记的元数据"""
    properties = page.get('properties', {})
    note_meta = {}

    # 获取 Deck 名称
    deck_name = get_rich_text_property(properties, 'Deck') or 'Default'
    note_meta['deck_name'] = deck_name

    # 获取模型名称（Note Type）
    model_name = get_rich_text_property(properties, 'Note Type') or 'Basic'
    note_meta['model_name'] = model_name

    # 获取首字段名称（First Field）
    first_field_name = get_rich_text_property(properties, 'First Field')
    note_meta['first_field'] = first_field_name

    # 获取标签
    tags = get_multi_select_property(properties, 'Tags') or []
    note_meta['tags'] = tags

    return note_meta 

def build_anki_note_fields(page):
    """根据 Notion 页面生成 Anki 笔记的字段和元数据：
    1. 将 Notion 中所有元数据字段导出到 note_meta
    2. 对模板字段仅导入非空字段，但排除 'First Field'（仅作为元数据使用）
    3. 如果存在与元数据中指定的首字段名对应的属性，则保留
    """


    properties = page.get('properties', {})
    note_fields = {}
    note_meta = {}

    metadata_fields = {'Anki ID', 'Deck', 'Note Type', 'First Field', 'Tags',
                         'Creation Time', 'Modification Time', 'Review Count',
                         'Ease Factor', 'Interval', 'Card Type', 'Due Date',
                         'Suspended', 'Lapses', 'Difficulty', 'Stability', 'Retrievability'}

    for field_name, prop in properties.items():
        prop_type = prop.get('type')
        if field_name in metadata_fields:
            key = field_name.lower().replace(' ', '_')
            if prop_type == 'rich_text':
                field_content = get_rich_text_content(prop.get('rich_text', []))
                note_meta[key] = field_content
            elif prop_type == 'number':
                note_meta[key] = prop.get('number')
            elif prop_type == 'date':
                date_value = prop.get('date')
                if date_value and date_value.get('start'):
                    note_meta[key] = date_value['start']
                else:
                    note_meta[key] = None
            elif prop_type == 'multi_select':
                multi_select = prop.get('multi_select', [])
                note_meta[key] = [item.get('name') for item in multi_select]
            elif prop_type == 'checkbox':
                note_meta[key] = prop.get('checkbox', False)
            else:
                # 其他类型可根据需要添加
                note_meta[key] = None
        else:
            # 对模板字段仅导入非空内容，并排除 'First Field'
            if field_name != 'First Field' and prop_type == 'rich_text':
                field_content = get_rich_text_content(prop.get('rich_text', []))
                if field_content.strip():
                    note_fields[field_name] = field_content

    # 解决 processed_notion_children 丢失的问题，判断 page 是否包含该字段，如果有，则添加进去
    if 'processed_notion_children' in page:
        note_meta['processed_notion_children'] = page['processed_notion_children']
    


    return note_fields, note_meta

def handle_duplicates_and_add_note(note_fields, note_meta, handling_way):
    """处理重复项并将笔记导入到 Anki"""
    col = mw.col
    model_name = note_meta.get('note_type', 'Basic')
    notion_first_field = note_meta.get('first_field')  # 确保获取正确的键

    # 获取当前模型并判断首字段名
    model = col.models.byName(model_name)
    if model:
        anki_first_field = (
            model['flds'][0]['name']
            if notion_first_field == 'First Field'
            else notion_first_field
        )
    else:
        anki_first_field = notion_first_field

    # 从 note_fields 中获取首字段的值，若不存在则设为空字符串
    notion_first_field_value = note_fields.get(anki_first_field, "")
    if not anki_first_field:
        showWarning("笔记缺少首字段名称，无法判断重复。")
        return

    # 删除 readyMove 标签
    if "tags" in note_meta and isinstance(note_meta["tags"], list):
        note_meta["tags"] = [tag for tag in note_meta["tags"] if tag.lower() != "readymove"]

    # **处理首字段内容应对首字段中存在url或者html或者其他特殊字符的情况**    
    notion_search_value = escape_search_value(notion_first_field_value)

    # 判断首字段值是否为空，构造不同的搜索查询
    if notion_first_field_value.strip() == "":
        # 首字段值为空，无法匹配空字段（anki搜索无法实现）
        pass       
    else:
        # 首字段值不为空，正常构造搜索查询
        search_query = f'note:"{model_name}" {anki_first_field}:"{notion_search_value}"'
        note_ids = col.find_notes(search_query)


    # 在 Anki 中查找匹配的笔记
    note_ids = col.find_notes(search_query)


    if note_ids:
        # 根据处理方式处理重复笔记
        if handling_way == 'keep':
            pass  # 保留现有笔记
        elif handling_way == 'overwrite':
            for note_id in note_ids:
                note = col.getNote(note_id)
                update_existing_note(note, note_fields, note_meta)
        elif handling_way == 'copy':
            create_new_note(note_fields, note_meta)
    else:
        # 创建新笔记
        create_new_note(note_fields, note_meta)

def update_fsrs_data(note, note_meta):
    """更新笔记的 FSRS 数据"""
    # 更新 FSRS 参数（需要直接操作数据库）
    card = note.cards()[0]
    
    try:
        # 从 Notion 元数据获取参数
        fsrs_data = {
            'd': note_meta.get('difficulty'),
            's': note_meta.get('stability'),
            'dr': note_meta.get('retrievability')
        }
        # 更新卡片数据（兼容 Anki 24.11+）
        mw.col.db.execute(
            "UPDATE cards SET data = ? WHERE id = ?",
            json.dumps(fsrs_data),
            card.id
        )
    except Exception as e:
        debug_print(f"更新卡片 {card.id} 数据失败", e)
    note.flush()
    # 保存更改并刷新界面
    mw.col.save()
    mw.reset()

def escape_search_value(value):
    # 先转义反斜杠，再转义双引号
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return value

def save_notion_children_and_update_anki_model(page):
    """
    提取、处理 Notion 正文，并更新当前 note 所使用的模板。
    最后返回处理过的正文内容 processed_notion_children。
    """
    try:
        # 提取原始正文
        raw_children = extract_notion_children(page)
        # 处理正文（比如处理 markdown 转 html 等）
        processed_notion_children = process_notion_children(raw_children)
        
        # 获取当前页面对应的模板名称
        note_type = page.get('properties', {}) \
                        .get('Note Type', {}) \
                        .get('rich_text', [{}])[0].get('plain_text', 'Basic')
                        
        col = mw.col
        model = col.models.byName(note_type)
        if not model:
            showWarning(f"找不到对应的模板: {note_type}")
            return None
        
        temp_note = Note(col, model)
        # 更新Anki模板（传入临时笔记对象）
        update_anki_model_via_notion_children(temp_note, processed_notion_children)
        
        return processed_notion_children
    except Exception as e:
        showWarning(f"处理 Notion 正文失败: {str(e)}")
        return None

def extract_notion_children(page):
    """提取Notion页面正文内容"""
    try:
        # 获取页面ID
        page_id = page.get('id')
        if not page_id:
            debug_print("无效的页面对象，缺少ID")
            return []
            
        # 初始化Notion客户端
        notion = Client(auth=mw.addonManager.getConfig(__name__).get('notion_token'))
        
        # 递归获取所有子块
        all_blocks = []
        start_cursor = None
        
        while True:
            response = notion.blocks.children.list(
                block_id=page_id,
                start_cursor=start_cursor,
                page_size=100
            )
            
            if not response or not response.get('results'):
                break
                
            all_blocks.extend(response['results'])
            start_cursor = response.get('next_cursor')
            
            if not start_cursor:
                break

        # 提取块内容
        children_content = []
        # 新增列表计数器
        numbered_list_counter = 0
        in_numbered_list = False
        
        # 将process_rich_text移到循环外部
        def process_rich_text(rich_text):
            segments = []
            for text in rich_text:
                plain_text = text.get('plain_text', '')
                annotations = text.get('annotations', {})
                
                # 格式处理
                if annotations.get('bold'): plain_text = f"**{plain_text}**"
                if annotations.get('italic'): plain_text = f"_{plain_text}_"
                if annotations.get('strikethrough'): plain_text = f"~~{plain_text}~~"
                if annotations.get('code'): plain_text = f"`{plain_text}`"
                
                # 颜色处理
                color = annotations.get('color', 'default')
                if color != 'default':
                    style = []
                    if '_background' in color:
                        style.append(f"background-color: {color.replace('_background', '')}")
                    else:
                        style.append(f"color: {color}")
                    plain_text = f'<span style="{";".join(style)}">{plain_text}</span>'
                
                segments.append(plain_text)
            return ''.join(segments)

        for i, block in enumerate(all_blocks):
            block_type = block.get('type')
            content = block.get(block_type, {})
            
            # 处理有序列表计数
            if block_type == 'numbered_list_item':
                if not in_numbered_list or (i > 0 and all_blocks[i-1].get('type') != 'numbered_list_item'):
                    numbered_list_counter = 1
                else:
                    numbered_list_counter += 1
                in_numbered_list = True
            else:
                in_numbered_list = False

            # 处理有序列表
            if block_type == 'numbered_list_item':
                text_content = process_rich_text(content.get('rich_text', []))
                children_content.append(f"{numbered_list_counter}. {text_content}")
                continue

            # 修改列表处理逻辑
            elif block_type == 'bulleted_list_item':
                text_content = process_rich_text(content.get('rich_text', []))
                children_content.append(f"- {text_content}")
                continue

            # 修改代码块处理
            elif block_type == 'code':
                code_text = process_rich_text(content.get('rich_text', []))
                children_content.append(f"```{content.get('language', '')}\n{code_text}\n```")
                continue

            # 优化空行处理（新增逻辑）
            if block_type == 'paragraph' and not content.get('rich_text'):
                # 仅保留单个换行
                if children_content and not children_content[-1].endswith( '\n'):
                    children_content.append('\n')
                continue

            # 处理其他块类型
            text_segments = []
            if 'rich_text' in content:
                text_segments.append(process_rich_text(content['rich_text']))
            
            children_content.extend(text_segments)

        debug_print(f"提取到 {len(children_content)} 个内容块")
     
        
        return '\n\n'.join(children_content) if children_content else None

    except Exception as e:
        error_msg = f"提取Notion正文失败: {str(e)}"
        debug_print(error_msg)
        showWarning(error_msg)
        return None

def process_notion_children(children):
    """处理Notion正文内容，转换为Anki兼容格式"""
    if not children:
        return None

    try:

        processed = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', children)
        processed = re.sub(r'_(.*?)_', r'<em>\1</em>', processed)
        processed = re.sub(r'~~(.*?)~~', r'<del>\1</del>', processed)
        
        # ★ 先处理代码块，避免内联代码替换破坏代码块结构
        processed = re.sub(
            r'```(\w+)?\n([\s\S]*?)\n```',
            lambda m: '<pre><code class="{}">{}</code></pre>'.format(m.group(1) or "",
                                                                       html.escape(m.group(2))),
            processed,
            flags=re.DOTALL
        )
        
        # 再处理内联代码
        processed = re.sub(r'`([^`]+)`', r'<code>\1</code>', processed)
        
        # 处理颜色样式（保持原样）
        processed = re.sub(r'<span style="(.*?)">(.*?)</span>',
                           r'<span style="\1">\2</span>',
                           processed)
        
        # 处理无序列表：合并被空行分隔的列表项
        processed = re.sub(
            r'((?:^-\s.*(?:\n+|$))+)',
            lambda m: "<ul>\n" + "".join([
                f"<li>{line[2:]}</li>" 
                for line in m.group(1).replace('\n\n', '\n').strip().split('\n') 
                if line.strip()
            ]) + "\n</ul>\n",
            processed,
            flags=re.M
        )
        
        # 处理有序列表：合并被空行分隔的列表项
        processed = re.sub(
            r'((?:^\d+\.\s.*(?:\n+|$))+)',
            lambda m: "<ol>\n" + "".join([
                f"<li>{line.split('. ', 1)[1]}</li>" 
                for line in m.group(1).replace('\n\n', '\n').strip().split('\n') 
                if line.strip()
            ]) + "\n</ol>\n",
            processed,
            flags=re.M
        )
        
        # 增强段落处理（排除代码块部分）
        lines = []
        code_blocks = re.findall(r'<pre>.*?</pre>', processed, flags=re.DOTALL)
        non_code_parts = re.split(r'<pre>.*?</pre>', processed, flags=re.DOTALL)
        
        for i, part in enumerate(non_code_parts):
            for line in part.split('\n'):
                line = line.strip()
                if line and not line.startswith(('<', 'li>', 'pre>', 'ol>', 'ul>')):
                    lines.append(f'<p>{line}</p>')
                elif line:
                    lines.append(line)
            if i < len(code_blocks):
                lines.append(code_blocks[i])
        
        processed = '\n'.join(lines)
        
        debug_print(f"处理后的正文内容长度: {len(processed)}")
        return processed

    except Exception as e:
        error_msg = f"正文内容处理失败: {str(e)}"
        debug_print(error_msg)
        showWarning(error_msg)
        return None

def update_anki_model_via_notion_children(note, processed_children):
    """
    更新该 note 使用的模板，将 processed_children 内容用于更新模板
    仅在 processed_children 非空的情况下，更新该 note 所属的模板：
    1. 如果 note 所属模板中没有 "notion正文" 字段，则添加该字段；
    2. 如果该模板中卡片背面模板没有 <div class="notionart">{{notion正文}}</div>，则追加该内容；
    3. 如果 CSS 中没有定义 .notionart 样式，则追加该样式定义。
    注意：只对当前导入的笔记对应的模板做修改，不影响其他模板。
    """
    if not processed_children:
        return

    col = mw.col
    # 获取当前 note 的模板（模型）
    model = note.model()
    updated = False

    # 检查当前模板中是否存在 "notion正文" 字段
    existing_fields = [fld.get('name') for fld in model.get('flds', [])]
    if "notion正文" not in existing_fields:
        # 动态添加 "notion正文" 字段到模板中
        new_field = col.models.newField("notion正文")
        col.models.addField(model, new_field)
        updated = True

    # 更新卡片背面模板，添加用于展示 notion 正文的代码段
    for tmpl in model.get('tmpls', []):
        afmt = tmpl.get('afmt', '')
        insertion = '<div class="notionart">{{notion正文}}</div>'
        if insertion not in afmt:
            # 追加到卡片背面模板的末尾
            tmpl['afmt'] = afmt + "\n" + insertion
            updated = True

    # 检查 CSS 中是否已经包含 .notionart 样式，如果没有则追加
    css = model.get('css', '')
    if '.notionart' not in css:
        css += "\n.notionart {color: gray; font-style: italic;}"
        model['css'] = css
        updated = True

    if updated:
        # 保存更新后的模板
        col.models.save(model)

def write_notion_children_to_anki_note(note, processed_notion_children):
    """
    使用 processed_notion_children 作为笔记中"notion正文"字段的值。
    如果笔记所属模板中没有"notion正文"字段，则动态添加该字段，
    同时在笔记对应卡片的背面模板中追加 <div class="notionart">{{notion正文}}</div> 。
    """
    col = mw.col
    model = note.model()
    field_name = "notion正文"

    # 当前 note 中一定存在"notion正文"字段，因此无需动态添加

    # 将处理后的 Notion 正文内容写入该字段
    note[field_name] = processed_notion_children


    # 保存笔记更改到数据库
    col.update_note(note)




