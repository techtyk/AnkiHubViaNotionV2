import re
from datetime import datetime
from aqt.qt import debug
from aqt import mw
import json

class Helpers:
    def __init__(self):
        pass

    @staticmethod
    def extract_database_id(url):
        """从 Notion 数据库链接中提取数据库 ID"""
        try:
            # 去除 URL 中的连字符和查询参数
            url_clean = url.replace('-', '').split('?', 1)[0]
            # 匹配 32 位十六进制的数据库 ID
            match = re.search(r'([0-9a-fA-F]{32})', url_clean)
            if match:
                database_id = match.group(1)
                # 格式化为带连字符的 UUID 形式
                database_id = f"{database_id[0:8]}-{database_id[8:12]}-{database_id[12:16]}-{database_id[16:20]}-{database_id[20:]}"
                return database_id
            else:
                return None
        except Exception as e:
            return None
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
            # 学习中卡片，due 是相对时间，单位为秒
            due = time.time() + (card.due * 60)
            return datetime.fromtimestamp(due)
        elif card.type == 2:
            # 复习卡片，due 是天数
            due = (card.due - col.sched.today) * 86400 + time.time()
            return datetime.fromtimestamp(due)
        else:
            return None
    @staticmethod
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
            debug()
        return properties