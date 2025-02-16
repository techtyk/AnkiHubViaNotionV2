# 定义各同步方式的核心接口，使用了策略模式（Strategy Pattern）
from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime
from aqt import mw
from ..utils.helpers import Helpers
import json

VALID_LANGUAGES = {'python', 'javascript', 'java', 'c', 'c++', 'c#', 'html', 'css', 
                  'sql', 'typescript', 'php', 'ruby', 'go', 'swift', 'kotlin', 
                  'plain text'}  # 根据Notion API支持的语言列表精简

class SyncStrategy(ABC):
    """同步策略抽象基类（策略模式）"""
    
    @abstractmethod
    def execute(self, config: Dict[str, Any]):
        """执行同步操作"""
        pass

class AnkiToNotionStrategy(SyncStrategy):
    """Anki → Notion 同步策略"""
    
    def execute(self, config: Dict[str, Any]):
        # 初始化 Notion 客户端，并提取数据库ID
        from .notion_client import NotionClient
        client = NotionClient(config.get('notion_token'))
        database_id = Helpers.extract_database_id(config.get('notion_database_url'))

        # 具体实现分为3个步骤:1-提取ids，2-确保数据库符合预期，3-更新notion数据库
        note_ids = self._get_anki_notes_ids()
        # 确保数据库结构符合预期，不存在或类型不匹配的属性自动更新
        self._ensure_database_structure(client, database_id, note_ids)
        result = self._update_notion_database(note_ids, config)
        self._show_sync_result(result)

    def _get_anki_notes_ids(self):
        """获取待同步的Anki笔记"""
        # 从配置获取查询条件（根据需求文档4.1.3）
        query = mw.addonManager.getConfig(__name__).get('anki_query_string')
        # 获取完整Note对象（根据需求文档3.5）
        note_ids = mw.col.find_notes(query)
        return note_ids

    

    
    def _update_notion_database(self, note_ids, config):
        """更新Notion数据库（自动添加缺失字段、修正属性类型及重复检查逻辑）"""
        from .notion_client import NotionClient

        # 初始化 Notion 客户端，并提取数据库ID
        client = NotionClient(config.get('notion_token'))
        database_id = Helpers.extract_database_id(config.get('notion_database_url'))

        
        # 针对每条笔记构造 Notion 页面数据
        batch_operations = []
        for note_id in note_ids:
            note = mw.col.get_note(note_id)
            note_body = note["notion正文"].strip() if "notion正文" in note.keys() else ""
            notion_children = self._convert_to_notion_children(note_body) if note_body else None

            processed_note = self._process_note(note)
            properties = self._convert_into_notion_properties(processed_note, config)
            
            # 构造重复检查条件
            first_field_value = properties["First Field"]["rich_text"][0]["text"]["content"]
            duplicate_check = {
                "filter": {
                    "and": [
                        {"property": "Note Type", "rich_text": {"equals": properties["Note Type"]["rich_text"][0]["text"]["content"]}},
                        {"property": "first_field", "rich_text": {"equals": first_field_value}}
                    ]
                }
            }
            # 构造 operation 字典
            operation = {
                "data": properties,
                "duplicate_check": duplicate_check,
                "handling": config.get("duplicate_handling_way", "keep")
            }
            if notion_children:
                operation["children"] = notion_children
            batch_operations.append(operation)
        
        # 调用 NotionClient 内的批量更新接口
        result = client.batch_update_database(
            database_id=database_id,
            operations=batch_operations,
            retain_source=config.get("retain_source_note", True)
        )
        return result

    def _process_note(self, note):
        """处理单个笔记的字段映射"""
        return {
            **{k: v for k, v in note.items() if k != "notion正文"},
            **self._get_meta_fields(note)
        }

    def _get_meta_fields(self, note):
        """从anki数据库中提取元数据字段（参考 anki2notion.py 207-261 行）"""
        card = note.cards()[0] if note.cards() else None
        meta_fields_from_anki={
            "Anki ID": str(note.id),
            "Deck": mw.col.decks.get(card.did)["name"] if card else "",
            "Tags": ", ".join(note.tags),
            "Note Type": note.note_type()["name"] if note.note_type() else "",
            "Card Type": card.type,
            "First Field": list(note.keys())[0] if note.keys() else "",
            "Creation Time": datetime.fromtimestamp(note.id / 1000 ,tz=datetime.now().astimezone().tzinfo).isoformat(),
            "Modification Time": datetime.fromtimestamp(note.mod,tz=datetime.now().astimezone().tzinfo).isoformat(),
            "Due Date": Helpers.get_card_due_date(card).isoformat() if Helpers.get_card_due_date(card) else None,  # 空值设为None避免发送空字符串
            "Review Count": card.reps if card else 0,
            "Ease Factor": card.factor / 1000 if card else 0,
            "Interval": card.ivl if card else 0,
            "Lapses": card.lapses if card else 0,
            "Suspended":card.queue == -1,
        }
        meta_fields_from_anki = Helpers.write_fsrs_data(note, meta_fields_from_anki)
        return meta_fields_from_anki

    def _convert_into_notion_properties(self, note_data, config):
        """
        根据处理后的笔记数据构建 Notion 页面属性字典
        """
        properties = {}
        for field, value in note_data.items():
            if value is None:
                continue
            if field in {"Creation Time", "Modification Time", "Due Date"}:
                properties[field] = {"date": {"start": str(value)}}
            elif field == "Tags":
                if isinstance(value, str):
                    tags = [tag.strip() for tag in value.split(",") if tag.strip()]
                    properties[field] = {"multi_select": [{"name": tag} for tag in tags]}
                else:
                    properties[field] = {"multi_select": value}
            elif field in {"Anki ID", "Review Count", "Ease Factor", "Interval", "Lapses", "Difficulty", "Stability", "Retrievability"}:
                try:
                    # 处理可能存在的嵌套数值结构
                    if isinstance(value, dict) and 'number' in value:
                        numeric_value = value['number']
                    else:
                        numeric_value = float(value) if '.' in str(value) else int(value)
                    properties[field] = {"number": numeric_value}
                except (ValueError, TypeError):
                    print(f"警告：字段 {field} 的值 {value} 无法转换为数字，已设置为 0")
                    properties[field] = {"number": 0}
            elif field == "Suspended":
                properties[field] = {"checkbox": bool(value)}
            elif field == "Note Type":
                properties[field] = {"rich_text": [{"text": {"content": str(value)}}]}
            elif field == "First Field":
                properties[field] = {"rich_text": [{"text": {"content": str(value)}}]}
                # 同时添加辅助字段 first_field 用于重复检查
                properties["first_field"] = {"rich_text": [{"text": {"content": str(value)}}]}
            elif field == "Card Type":
                properties[field] = {"rich_text": [{"text": {"content": str(value)}}]}
            else:
                properties[field] = {"rich_text": [{"text": {"content": str(value)}}]}
        return properties

    def _ensure_database_structure(self, client, database_id, note_ids):
        """自动更新数据库结构，补充缺失或类型不匹配的属性"""
        try:
            db_info = client.client.databases.retrieve(database_id=database_id)
        except Exception as e:
            print("无法获取数据库结构信息:", e)
            return {"success": [], "failed": [{"error": "无法获取数据库结构信息"}]}

        current_properties = db_info.get("properties", {})

        # 收集所有待同步笔记中出现的字段
        required_fields = set()
        for note_id in note_ids:

            note = mw.col.get_note(note_id)
            required_fields.update(note.keys())
        
        # 添加必须的元数据字段（参考 anki2notion.py 77-78 行）
        required_fields.update({'Anki ID', 'Deck', 'Tags', 'Note Type', 'First Field', 
                              'Creation Time', 'Modification Time', 'Review Count', 
                              'Ease Factor', 'Interval', 'Card Type', 'Due Date', 
                              'Suspended', 'Lapses', 'Difficulty', 'Stability', 'Retrievability'})
        if "notion正文" in required_fields:
            required_fields.discard("notion正文")   #notion正文并不是必要字段（应该放到notion_children中，而不是属性中）
        # 定义预期属性类型映射（参考 anki2notion 的实现）
        expected_types = {}
        for field in required_fields:
            if field in {"Creation Time", "Modification Time", "Due Date"}:
                expected_types[field] = "date"
            elif field == "Tags":
                expected_types[field] = "multi_select"
            elif field in {"Anki ID", "Review Count", "Ease Factor", "Interval", "Lapses", "Difficulty", "Stability", "Retrievability"}:
                expected_types[field] = "number"
            elif field == "Suspended":
                expected_types[field] = "checkbox"
            elif field in {"Note Type", "First Field","Card Type"}:
                expected_types[field] = "rich_text"
            else:
                expected_types[field] = "rich_text"

        new_properties = {}
        for field, expected_type in expected_types.items():
            if field not in current_properties or current_properties[field].get("type") != expected_type:
                new_properties[field] = {expected_type: {}}

        if new_properties:
            try:
                response = client.client.databases.update(
                    database_id=database_id,
                    properties=new_properties
                )
                print("自动更新数据库结构，添加/更新属性：", list(new_properties.keys()))
            except Exception as e:
                print("自动更新数据库属性失败:", e)

    def _show_sync_result(self, result):
        """弹窗显示同步结果"""
        print("同步完成！")
        print(f"成功: {len(result['success'])}，失败: {len(result['failed'])}")

    # 新增转换函数：将 Anki 笔记中的 HTML 正文转换为 Notion children 块
    def _convert_to_notion_children(self, html_content: str):
        import re
        from html import unescape
        
        # 处理代码块（提取语言参数）
        code_blocks = []
        def code_replacer(m):
            lang = m.group(1) or ''
            # 清理语言前缀（处理类似 language-python 的情况）
            lang = lang.replace('language-', '').lower()
            code = m.group(2)
            code_blocks.append({'lang': lang, 'content': unescape(code)})
            return f'__CODE_BLOCK_{len(code_blocks)-1}__'
        
        html_content = re.sub(
            r'<pre><code(?: class="([^"]*)")?>(.*?)</code></pre>',
            code_replacer, html_content, flags=re.DOTALL
        )
        
        # 处理内联格式
        replacements = [
            (r'<code>(.*?)</code>', r'`\1`'),
            (r'<strong>(.*?)</strong>', r'**\1**'),
            (r'<em>(.*?)</em>', r'_\1_'),
            (r'<del>(.*?)</del>', r'~~\1~~'),
            (r'<span[^>]*>(.*?)</span>', r'\1')
        ]
        for pattern, replacement in replacements:
            html_content = re.sub(pattern, replacement, html_content, flags=re.DOTALL)

        # 处理列表和段落
        html_content = re.sub(r'<ul>(.*?)</ul>', 
            lambda m: '\n'.join(f"- {x.group(1)}" for x in re.finditer(r'<li>(.*?)</li>', m.group(1), re.DOTALL)),
            html_content, flags=re.DOTALL)
        
        # 重建代码块结构
        children = []
        for part in re.split(r'__CODE_BLOCK_(\d+)__', html_content):
            if part.isdigit():
                index = int(part)
                children.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code_blocks[index]['content']}}],
                        "language": code_blocks[index]['lang'] if code_blocks[index]['lang'] in VALID_LANGUAGES else "plain text"
                    }
                })
            elif part.strip():
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": part.strip()}}]}
                })
        
        return children

class NotionToAnkiStrategy(SyncStrategy):
    """Notion → Anki 同步策略"""
    
    def execute(self, config: Dict[str, Any]):
        # 通过executor获取配置
        print(f"正在使用配置：{config}执行同步")
        # 具体同步逻辑...