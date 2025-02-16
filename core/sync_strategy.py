# 定义各同步方式的核心接口，使用了策略模式（Strategy Pattern）
from abc import ABC, abstractmethod
from typing import Dict, Any
from aqt.qt import debug
from datetime import datetime
from aqt import mw

class SyncStrategy(ABC):
    """同步策略抽象基类（策略模式）"""
    
    @abstractmethod
    def execute(self, config: Dict[str, Any]):
        """执行同步操作"""
        pass

class AnkiToNotionStrategy(SyncStrategy):
    """Anki → Notion 同步策略"""
    
    def execute(self, config: Dict[str, Any]):
        # 具体实现分为四个步骤
        notes = self._get_anki_notes()
        processed_notes=self._process_notes(notes, config)
        result=self._update_notion_database(processed_notes, config)
        debug()
        self._show_sync_result(result)

    def _get_anki_notes(self):
        """获取待同步的Anki笔记"""
        # 从配置获取查询条件（根据需求文档4.1.3）
        query = mw.addonManager.getConfig(__name__).get('anki_query_string')
        # 获取完整Note对象（根据需求文档3.5）
        note_ids = mw.col.find_notes(query)
        return [mw.col.get_note(nid) for nid in note_ids]

    
    def _process_notes(self, notes, config):
        """处理笔记字段映射（基础实现）"""
        processed_notes = []
        for note in notes:
            # 获取模板字段（排除Notion正文字段）
            template_fields = {
                name: value 
                for name, value in note.items()
                if name != "notion正文"
            }
            
            # 提取元数据（根据需求文档3.5）
            meta_fields = {
                "Anki ID": str(note.id),
                "Deck": (mw.col.decks.get(note.cards()[0].did) or {}).get("name", "") if note.cards() else "",
                "Tags": ", ".join(note.tags),
                "Card Type": note.model()['name'],
                "Creation Time": datetime.fromtimestamp(note.id / 1000).isoformat(),
                "Modification Time": datetime.fromtimestamp(note.mod).isoformat()
            }
            
            # 合并字段（后续可添加字段映射配置）
            processed_note = {**template_fields, **meta_fields}
            processed_notes.append(processed_note)
            
            # 调试输出（后续可替换为logger）
            print(f"处理笔记 {note.id} -> 字段数: {len(processed_note)}")
        
        return processed_notes
    
    def _update_notion_database(self, notes, config):
        """更新Notion数据库（自动添加缺失字段）"""
        from .notion_client import NotionClient  # 假设已实现客户端
        from ..utils.helpers import Helpers
        # 初始化 Notion 客户端，并提取数据库ID
        client = NotionClient(config.get('notion_token'))
        database_id = Helpers.extract_database_id(config.get('notion_database_url'))
        
        # 确保数据库结构符合预期，如果不符合就自动更新数据库
        self._ensure_database_structure(client, database_id, notes)

        
        # 针对每条笔记构造 Notion 页面数据
        batch_operations = []
        
        for note_data in notes:
            # 构建Notion页面属性
            properties = {
                prop_name: {"rich_text": [{"text": {"content": str(value)}}]}
                for prop_name, value in note_data.items()
            }
            # 构建重复检查过滤器（这里以 "Anki ID" 字段为依据）
            duplicate_check = {
                "filter": {
                    "property": "Anki ID",
                    "rich_text": {"equals": str(note_data.get("Anki ID", ""))}
                }
            }
            batch_operations.append({
                "data": properties,
                "duplicate_check": duplicate_check,
                "handling": config.get('duplicate_handling_way', 'keep')
            })
        
        # 调用 NotionClient 内的批量更新接口
        result = client.batch_update_database(
            database_id=database_id,
            operations=batch_operations,
            retain_source=config.get('retain_source_note', True)
        )
        
        print(f"已更新 {len(result['success'])} 条笔记，失败 {len(result['failed'])} 条")
        return result
    def _ensure_database_structure(self, client, database_id, notes):
                # 确保当前数据库的结构符合预期，如果不符合就自动更新
        try:
            db_info = client.client.databases.retrieve(database_id=database_id)
        except Exception as e:
            print("无法获取数据库结构信息:", e)
            return {"success": [], "failed": [{"error": "无法获取数据库结构信息"}]}
        current_properties = db_info.get('properties', {})
        
        # 收集所有待同步笔记中出现的字段
        required_fields = set()
        for note_data in notes:
            required_fields.update(note_data.keys())
        
        # 检查缺失或类型不匹配的属性（本例要求所有字段均为 rich_text，以保证后续构造数据格式一致）
        new_properties = {}
        for field in required_fields:
            # 如果属性不存在，或存在但类型不是 rich_text，都重新设置
            if field not in current_properties or current_properties[field].get('type') != 'rich_text':
                new_properties[field] = {'rich_text': {}}
        
        # 如果有需要更新的属性，则调用 API 自动更新数据库结构
        if new_properties:
            try:
                response = client.client.databases.update(
                    database_id=database_id,
                    properties=new_properties
                )
                print("自动更新数据库结构，添加属性：", list(new_properties.keys()))
            except Exception as e:
                print("自动更新数据库属性失败:", e)
    def _show_sync_result(self):
        """弹窗显示同步结果"""
        # 实现结果提示逻辑
        print("同步完成！")

class NotionToAnkiStrategy(SyncStrategy):
    """Notion → Anki 同步策略"""
    
    def execute(self, config: Dict[str, Any]):
        # 通过executor获取配置
        print(f"正在使用配置：{config}执行同步")
        # 具体同步逻辑...