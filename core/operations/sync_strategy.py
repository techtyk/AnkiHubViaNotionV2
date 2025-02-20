# 定义各同步方式的核心接口，使用了策略模式（Strategy Pattern）
from abc import ABC, abstractmethod
from typing import Dict, Any ,Iterable
from datetime import datetime
from aqt import mw
from ..utils import Helpers
from ..models.note import Note
import json
import os
from ..client.notion_client import NotionClient
from ..models.parse_and_converter import ToNotionConverter,parse_notion_https_for_database_id
from aqt.qt import debug
from .config_manager import ConfigManager
from .note_factory import NoteFactory



class SourceToTargetSyncStrategy(ABC):
    """同步策略抽象基类（策略模式）"""
    
    @abstractmethod
    @staticmethod
    def get_ids_from_source() -> Iterable:
        """从源侧获取需要传输的笔记id"""
        pass
    
    @abstractmethod
    def ensure_database_structure_of_target(self, note_ids:Iterable) -> None:
        """确保目标侧的数据库格式符合要求"""
        pass
    
    @abstractmethod    
    def update_database_of_target(self,note_ids:Iterable)-> Iterable:
        """更新目标测的数据库"""
        pass
    
    @abstractmethod
    @staticmethod
    def delete_source_notes(succeeded_note_ids:Iterable) -> None:
        """如有需要，安全删除已成功同步的源侧笔记"""
        pass
    
    @abstractmethod
    @staticmethod
    def show_sync_result(result) -> None:
        """同步成功后，展现同步结果"""
        pass

    def execute_sync_strategy(self):
        """执行同步操作
        实现分为5个步骤:
        Step1-提取待传输笔记的id，
        Step2-确保数据库结构符合预期，不存在或类型不匹配的属性自动更新
        Step3-更新notion数据库,Step4-删除源侧笔记（如有必要）,Step5-展示同步情况"""
        
        # Step 1——提取id
        note_ids = self.get_ids_from_source()

        # Step 2——确保数据库结构符合预期
        self.ensure_database_structure_of_target(note_ids)

        # Step 3——更新notion数据库
        result = self.update_database_of_target(note_ids)

        # Step 4——删除源侧笔记（如有必要）        
        # 根据返回结果提取实际成功同步的笔记ID
        # 添加 if op.get("operation") 的作用是为了筛选出那些实际进行了"操作"的记录。原因如下：
        # 在某些重复处理策略下（例如"keep"模式），如果笔记被判断为重复，可能不会真正调用创建或更新操作，而是直接跳过同步。在这种情况下，返回的记录可能没有包含有效的 "operation" 数据。
        # 当我们计划删除源侧（Anki）的笔记时，我们希望只删除那些已经实际同步成功并且确实进行了创建或更新操作的笔记。通过判断 op.get("operation")，可以排除掉那些被跳过（记录中可能没有 operation 信息）的笔记，从而避免误删。
        succeeded_ids = [item["operation"]["note_id"] for item in result.get("success", []) if item.get("action") in ["create", "update"]]
        # 根据配置决定是否删除源笔记
        config = mw.addonManager.getConfig("anki_repository_v2")
        if config.get("delete_source_note"):
            self.delete_source_notes(succeeded_ids)

        # Step5——展示同步情况
        self.show_sync_result(result)

class AnkiToNotionStrategy(SourceToTargetSyncStrategy):
    """Anki → Notion 同步策略"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        # 初始化时获取最新配置
        self.config_manager.reload_config()
        self.client = NotionClient(self.config_manager.get('notion_token'))
        self.database_id = parse_notion_https_for_database_id(self.config_manager.get('notion_database_url'))
    
    @staticmethod
    def get_ids_from_source():
        """获取待同步的Anki笔记"""
        # 从配置获取查询条件（根据需求文档4.1.3）
        query = mw.addonManager.getConfig(__name__).get('anki_query_string')
        # 获取完整Note对象（根据需求文档3.5）
        note_ids = mw.col.find_notes(query)
        return note_ids
    def ensure_database_structure_of_target(self, note_ids):
        """自动更新数据库结构，补充缺失或类型不匹配的属性"""
        try:
            db_info = self.client.client.databases.retrieve(database_id=self.database_id)
        except Exception as e:
            print("无法获取数据库结构信息:", e)
            return {"success": [], "failed": [{"error": "无法获取数据库结构信息"}]}

        current_properties = db_info.get("properties", {})

        # 收集所有待同步笔记中出现的字段
        required_fields = set()
        for note_id in note_ids:
            note = mw.col.get_note(note_id)
            required_fields.update(note.keys())
        
        # 添加必须的元数据字段
        required_fields.update({'Anki ID', 'Deck', 'Tags', 'Note Type', 'First Field', 
                              'Creation Time', 'Modification Time', 'Review Count', 
                              'Ease Factor', 'Interval', 'Card Type', 'Due Date', 
                              'Suspended', 'Lapses', 'Difficulty', 'Stability', 'Retrievability'})
        if "notion正文" in required_fields:
            required_fields.discard("notion正文")   #notion正文并不是必要字段（应该放到notion_children中，而不是属性中）
        # 定义预期属性类型映射
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
                response = self.client.client.databases.update(
                    database_id=self.database_id,
                    properties=new_properties
                )
                print("自动更新数据库结构，添加/更新属性：", list(new_properties.keys()))
            except Exception as e:
                print("自动更新数据库属性失败:", e)
    def update_database_of_target(self, note_ids):
        """
        更新 Notion 数据库。每次调用时都通过 mw.addonManager.getConfig 获取最新配置，
        这样用户在设置界面修改 duplicate_handling_way 后不必重启 Anki 就能生效。
        """
        # 获取最新的config参数
        config = self.config_manager.reload_config()
        
        
        # 针对每条笔记构造 Notion 页面数据
        batch_operations = []
        for note_id in note_ids:
            anki_note = NoteFactory.create("anki", note_id)
            
            operation = {
                "data": self._convert_properties(anki_note.get_properties()),
                "children": anki_note.get_children(),
                "note_id": note_id
            }
            # 修改重复检查条件：
            # 1. 从 "First Field" 读取真实的首字段名称
            # 2. 再从 properties 中取出该字段的实际值
            first_field_property_name = operation["data"]["First Field"]["rich_text"][0]["text"]["content"]
            first_field_value = operation["data"][first_field_property_name]["rich_text"][0]["text"]["content"]
            duplicate_check = {
                "filter": {
                    "and": [
                        {
                            "property": "Note Type",
                            "rich_text": {
                                "equals": operation["data"]["Note Type"]["rich_text"][0]["text"]["content"]
                            }
                        },
                        {
                            "property": first_field_property_name,
                            "rich_text": {
                                "equals": first_field_value
                            }
                        }
                    ]
                }
            }
            operation["duplicate_check"] = duplicate_check
            batch_operations.append(operation)
        
        # 调用 NotionClient 内的批量更新接口
        result = self.client.batch_update_database(
            database_id=self.database_id,
            operations=batch_operations,
            config=config
        )
        return result
    @staticmethod
    def delete_source_notes(succeeded_note_ids):
        """安全删除已成功同步的源笔记"""
        if not succeeded_note_ids:
            return
        mw.col.remNotes(succeeded_note_ids)
        mw.reset()
    @staticmethod
    def show_sync_result(result):
        """弹窗显示同步结果"""
        print("同步完成！")
        print(f"成功: {len(result['success'])}，失败: {len(result['failed'])}")
    
    @staticmethod
    def _process_note(note, model_field_ignore):
        """处理单个anki笔记的字段映射,并将结果以字典的形式输出"""
        return {
            **{k: v for k, v in note.items() if k != model_field_ignore},
            **Note.get_meta_fields_from_anki(note)
        }


    @staticmethod
    def _convert_properties(properties):
        """
        根据处理后的笔记数据构建 Notion 页面属性字典
        """
        properties = {}
        for field, value in properties.items():
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

    




class NotionToAnkiStrategy(SourceToTargetSyncStrategy):
    """Notion → Anki 同步策略"""
    


    @staticmethod
    def get_ids_from_source() -> Iterable:
        """从源侧获取需要传输的笔记id"""
        pass
    

    def ensure_database_structure_of_target(self, note_ids:Iterable) -> None:
        """确保目标侧的数据库格式符合要求"""
        pass
    
 
    def update_database_of_target(self,note_ids:Iterable)-> Iterable:
        """更新目标测的数据库"""
        pass
    

    @staticmethod
    def delete_source_notes(succeeded_note_ids:Iterable) -> None:
        """如有需要，安全删除已成功同步的源侧笔记"""
        pass
    

    @staticmethod
    def show_sync_result(result) -> None:
        """同步成功后，展现同步结果"""
        pass
        pass