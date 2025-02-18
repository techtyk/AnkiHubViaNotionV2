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
