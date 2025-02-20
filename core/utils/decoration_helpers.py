import re
from datetime import datetime
from aqt.qt import debug
import functools
from . import logger
from aqt import mw
import json

#添加断点装饰器——在函数前后加上断点
def breakpoint_enforced(function):
    def function_with_breakpoint(*args, **kwargs):
        debug()
        result = function(*args, **kwargs)
        debug()
        return result
    return function_with_breakpoint

#添加尝试装饰器——在函数一旦出错就进入断点
def try_except_breakpoint(function):
    @functools.wraps(function)  # 保留原函数元信息
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {function.__name__}", exc_info=True)
            debug()
            raise
    return wrapper
