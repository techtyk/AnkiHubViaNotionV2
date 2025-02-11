DEBUG = True

import re
import sys
import traceback
from aqt.utils import showText, showInfo
import importlib
import inspect
import aqt
import json
import os

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

def get_rich_text_property(properties, property_name):
    """获取 Notion 属性中的富文本内容"""
    prop = properties.get(property_name)
    if prop and prop.get('type') == 'rich_text':
        rich_text = prop.get('rich_text')
        if rich_text:
            return ''.join([item.get('plain_text', '') for item in rich_text])
    return None

def get_multi_select_property(properties, property_name):
    """获取 Notion 属性中的多选内容"""
    prop = properties.get(property_name)
    if prop and prop.get('type') == 'multi_select':
        multi_select = prop.get('multi_select')
        if multi_select:
            return [item.get('name', '') for item in multi_select]
    return None

def timestamp_to_iso8601(timestamp):
    """将时间戳转换为 ISO 8601 格式的日期字符串（使用时区感知对象）"""
    from datetime import datetime
    # 使用时区感知的 fromtimestamp，并通过 strftime 保持返回字符串结尾为 'Z'
    return datetime.fromtimestamp(timestamp, tz=datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')



def print_all_var():
    if DEBUG:
        """调试函数：显示当前函数的所有本地变量。"""
        # 获取调用者的帧
        caller_frame = sys._getframe(1)
        # 获取本地变量字典
        local_vars = caller_frame.f_locals

        # 格式化变量信息
        var_info = []
        for var_name, var_value in local_vars.items():
            try:
                var_repr = repr(var_value)
            except Exception as e:
                var_repr = f"<无法获取变量值: {e}>"
            var_info.append(f"{var_name} = {var_repr}")

        # 将变量信息合并成字符串
        var_info_str = "\n".join(var_info)

        # 弹出对话框显示变量信息
        showText(var_info_str, title="调试信息", copyBtn=True) 

# def debug_print(**kwargs):
#     if DEBUG:
#         message = "\n".join(f"{key} = {value}" for key, value in kwargs.items())
#         showInfo(message)
def debug_print(*args):
    """统一的调试输出，支持多个参数"""
    if DEBUG:
        message = " ".join(str(arg) for arg in args)
        print(f"[DEBUG] {message}")
def debug_card_state(card, stage):
    """获取卡片状态信息并返回字符串"""
    state_info = f"""
    --- 卡片状态 ({stage}) ---
    卡片ID: {card.id}
    卡片类型 (type): {card.type}
    队列类型 (queue): {card.queue}
    到期日期 (due): {card.due}
    间隔 (interval): {card.ivl}
    易记系数 (factor): {card.factor}
    复习次数 (reps): {card.reps}
    失误次数 (lapses): {card.lapses}
    """
    return state_info.strip()

def debug_module_contents(module_name):
    """
    显示指定模块中的所有类和方法。

    参数：
        module_name (str): 模块的完全限定名称，例如 'anki.scheduler'.

    使用示例：
        debug_module_contents('anki.scheduler')
    """
    try:
        # 动态导入指定模块
        module = importlib.import_module(module_name)
        
        # 获取模块中的属性列表
        attributes = dir(module)
        
        # 准备存储信息的列表
        info_lines = []
        
        for attr_name in attributes:
            attr = getattr(module, attr_name)
            # 判断属性类型
            if inspect.isclass(attr):
                attr_type = '类'
            elif inspect.isfunction(attr):
                attr_type = '函数'
            elif inspect.ismethod(attr):
                attr_type = '方法'
            else:
                attr_type = '变量'
            # 添加到信息列表
            info_lines.append(f"{attr_type}: {attr_name}")
        
        # 将信息列表合并为字符串
        info_text = f"模块 {module_name} 的内容：\n" + "\n".join(info_lines)
        
        # 使用 Anki 的弹窗显示信息
        aqt.utils.showInfo(info_text)
    
    except ImportError:
        aqt.utils.showWarning(f"无法导入模块：{module_name}")
    except Exception as e:
        aqt.utils.showWarning(f"出现错误：{str(e)}")

def debug_revlog(col, card_id):
    """检查复习日志是否成功添加"""
    logs = col.db.all("SELECT * FROM revlog WHERE cid = ?", card_id)
    debug_print(
        revlog_count=len(logs),
        last_revlog=logs[-1] if logs else None
    )

def debug_revlog_schema(col):
    """检查revlog表结构"""
    schema = col.db.all("PRAGMA table_info(revlog)")
    debug_print(revlog_schema=[x[1] for x in schema])

def debug_revlog_insert(col, card_id):
    """验证最新插入的复习记录"""
    last_log = col.db.first("""
        SELECT * FROM revlog 
        WHERE cid = ? 
        ORDER BY id DESC 
        LIMIT 1""", card_id)
    debug_print(revlog_insert=dict(last_log)) if last_log else None

def debug_revlog_params(params):
    """验证参数可序列化性（参考AnkiConnect的日志实现）"""
    try:
        json.dumps(params)
        debug_print(params_serializable=True)
    except TypeError as e:
        debug_print(params_serializable_error=str(e))

def debug_sql_params(params):
    """深度验证SQL参数类型"""
    import json
    from datetime import datetime
    
    type_map = {
        int: 'integer',
        float: 'real',
        str: 'text',
        bytes: 'blob',
        bool: 'boolean',
        datetime: 'datetime'
    }
    
    debug_data = {
        "types": [type_map.get(type(p), str(type(p))) for p in params],
        "values": [str(p)[:100] for p in params],  # 截断长字符串
        "serializable": json.dumps(params, default=str)
    }
    
    debug_print(sql_params_debug=debug_data)

def add_review_log(card, col, rating=3, manual_due=None):
    """手动添加复习日志，使卡片正确进入复习状态。

    参数：
    - card: 要操作的卡片对象
    - col: 当前的 Anki 集合（collection）对象
    - rating: 评价等级（1: Again，2: Hard，3: Good，4: Easy）
    - manual_due: 手动设置的到期日（可选）
    """
    import time

    # 获取当前时间戳（毫秒）
    now_ms = int(time.time() * 1000)

    # 计算上次间隔和当前间隔
    last_interval = card.ivl or 0
    interval = max(1, last_interval)

    # 使用提供的易度因子，或默认值
    factor = card.factor or 2500

    # 构建复习日志条目
    revlog_entry = {
        "id": now_ms,             # 唯一标识符（时间戳）
        "cid": card.id,           # 卡片 ID
        "usn": col.usn(),         # 更新序列号
        "ease": rating,           # 评价等级
        "ivl": interval,          # 间隔（天）
        "lastIvl": last_interval, # 上一次间隔
        "factor": factor,         # 易度因子
        "time": 0,                # 花费时间（毫秒）
        "type": 1                 # 日志类型（1 表示复习）
    }

    # 调用调试函数（根据需要添加）
    debug_revlog_params(revlog_entry)

    # 插入复习日志到 revlog 表
    col.db.execute("""
        INSERT INTO revlog 
        (id, cid, usn, ease, ivl, lastIvl, factor, time, type)
        VALUES 
        (:id, :cid, :usn, :ease, :ivl, :lastIvl, :factor, :time, :type)
    """, revlog_entry)

    # 如果手动设置了到期日，更新卡片的 due 属性
    if manual_due is not None:
        card.due = manual_due

    # 更新卡片状态
    col.update_card(card)

def debug_sql_params_v2(sql, params):
    """调试 SQL 语句和参数"""
    debug_print(f"执行 SQL: {sql}")
    debug_print(f"参数: {params}")

def load_config():
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {}

def save_config(config):
    """保存配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)