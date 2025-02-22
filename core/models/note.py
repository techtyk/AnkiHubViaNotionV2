from abc import ABC, abstractmethod
from datetime import datetime
from aqt import mw
import json
from .parse_and_converter_helper import ToNotionConverter

class BaseNote(ABC):
    """笔记抽象基类（抽象工厂模式）"""
    @abstractmethod
    def get_properties(self) -> dict:
        """获取标准化属性字典"""
        pass
    
    @abstractmethod
    def get_children(self) -> list:
        """获取子内容块（用于Notion正文）"""
        pass

    @abstractmethod
    def get_first_field_name(self) -> str:
        pass
    
    @abstractmethod
    def get_first_field_value(self) -> str:
        pass

class AnkiNote(BaseNote):
    """Anki笔记具体实现（组合模式）"""
    def __init__(self, note_id: int):
        self.note = mw.col.get_note(note_id)
        self._meta_fields = self._extract_meta_fields()
        self._template_fields = self._extract_template_fields()
    
    def _extract_meta_fields(self) -> dict:
        """提取元数据字段（原Note类的静态方法改造）"""
        card = self.note.cards()[0] if self.note.cards() else None
        meta_fields_from_anki={
            "Anki ID": str(self.note.id),
            "Deck": mw.col.decks.get(card.did)["name"] if card else "",
            "Tags": ", ".join(self.note.tags),
            "Note Type": self.note.note_type()["name"] if self.note.note_type() else "",
            "Card Type": card.type,
            "First Field": list(self.note.keys())[0] if self.note.keys() else "",
            "Creation Time": datetime.fromtimestamp(self.note.id / 1000 ,tz=datetime.now().astimezone().tzinfo).isoformat(),
            "Modification Time": datetime.fromtimestamp(self.note.mod,tz=datetime.now().astimezone().tzinfo).isoformat(),
            "Due Date": self.get_card_due_date(card).isoformat() if self.get_card_due_date(card) else None,  # 空值设为None避免发送空字符串
            "Review Count": card.reps if card else 0,
            "Ease Factor": card.factor / 1000 if card else 0,
            "Interval": card.ivl if card else 0,
            "Lapses": card.lapses if card else 0,
            "Suspended":card.queue == -1,
        }
        meta_fields_from_anki = self._write_fsrs_data(self.note, meta_fields_from_anki)
        return meta_fields_from_anki
    
    def _extract_template_fields(self) -> dict:
        """提取模板字段"""
        return {k:v for k,v in self.note.items() if k != "notion正文"}
    
    def get_properties(self) -> dict:
        """组合元数据和模板字段"""
        return {**self._meta_fields, **self._template_fields}
    
    def get_children(self) -> list:
        """获取Anki正文内容（原ToNotionConverter逻辑）"""
        if "notion正文" in self.note:
            return ToNotionConverter.convert_anki_html_to_notion_children(
                self.note["notion正文"].strip()
            )
        return []

    def get_first_field_name(self):
        return self._meta_fields.get("First Field")
    
    def get_first_field_value(self):
        first_field_name = self.get_first_field_name()
        return self._template_fields.get(first_field_name, "")

    @staticmethod
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
            # 学习中的卡片，due是Unix时间戳（秒）
            return datetime.fromtimestamp(card.due)
        elif card.type == 2:
            # 复习卡片，due 是天数
            due = (card.due - col.sched.today) * 86400 + time.time()
            return datetime.fromtimestamp(due)
        else:
            return None

    @staticmethod
    def _write_fsrs_data(note, properties):
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
            print(e)
        return properties

class NotionNote(BaseNote):
    """Notion笔记具体实现（组合模式）"""
    def __init__(self, page_data: dict):
        self.page_data = page_data
        self.properties = self._parse_properties()
        self.children = self._parse_children()
    
    def _parse_properties(self) -> dict:
        """解析Notion页面属性"""
        # 实现属性解析逻辑...
    
    def _parse_children(self) -> list:
        """解析Notion子内容块"""
        # 实现子内容解析逻辑...
    
    def get_properties(self) -> dict:
        return self.properties
    
    def get_children(self) -> list:
        return self.children

    def get_first_field_name(self) -> str:
        return self.properties.get("First Field", "")
    
    def get_first_field_value(self) -> str:
        first_field_name = self.get_first_field_name()
        return self.properties.get(first_field_name, "")

class NoteFactory:
    """笔记工厂类（工厂模式）"""
    @staticmethod
    def create(note_source: str, identifier) -> BaseNote:
        if note_source == "anki":
            return AnkiNote(identifier)
        elif note_source == "notion":
            return NotionNote(identifier)
        raise ValueError("Unsupported note source")