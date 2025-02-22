import os
import sys
from aqt import mw
from aqt.qt import QAction

plugin_root = os.path.dirname(__file__)
lib_path = os.path.abspath(os.path.join(plugin_root, 'lib'))
# 将 lib 目录插入到 sys.path 的首位
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)


print("lib_path:", lib_path)
print("lib目录内容:", os.listdir(lib_path))

from .core.operations.config_manager import ConfigManager
from .core.operations.sync_executor import SyncExecutor
from .core.operations.sync_strategy import AnkiToNotionStrategy, NotionToAnkiStrategy

# 初始化配置管理器（单例模式）
config_manager = ConfigManager()

def init_menu():
    # 创建菜单项
    menu_texts = config_manager.get_menu_texts()
    
    # 设置菜单
    settings_action = QAction(menu_texts['settings'], mw)
    settings_action.triggered.connect(open_settings)
    mw.form.menuTools.addAction(settings_action)

    # 同步菜单项
    anki2notion_action = QAction(menu_texts['anki_to_notion'], mw)
    anki2notion_action.triggered.connect(start_anki_to_notion)
    mw.form.menuTools.addAction(anki2notion_action)

    notion2anki_action = QAction(menu_texts['notion_to_anki'], mw)
    notion2anki_action.triggered.connect(start_notion_to_anki)
    mw.form.menuTools.addAction(notion2anki_action)

def open_settings():
    from .gui.settings_dialog import SettingsDialog
    dialog = SettingsDialog(mw)
    dialog.exec()

def start_anki_to_notion():
    config = mw.addonManager.getConfig(__name__)  # 获取当前插件配置
    executor = SyncExecutor()
    executor.execute_strategy(AnkiToNotionStrategy(config))  # 传入配置参数

def start_notion_to_anki():
    executor = SyncExecutor()
    executor.execute_strategy(NotionToAnkiStrategy())

# 插件加载时初始化
mw.addonManager.setWebExports(__name__, r"lib/.*(css|js)")
init_menu()
