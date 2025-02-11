from aqt import mw
from aqt.qt import QAction, QCoreApplication
from .gui.settings import SettingsDialog
from .functions.anki2notion import anki_to_notion
from .functions.notion2anki import notion_to_anki
from .functions.my_helpers import load_config, save_config
import os

# 定义菜单文本
MENU_TEXTS = {
    '中文': {
        'settings': 'AnkiHubViaNotion设置',
        'anki_to_notion': '同步Anki到Notion',
        'notion_to_anki': '同步Notion到Anki',
    },
    'English': {
        'settings': 'AnkiHubViaNotion Settings',
        'anki_to_notion': 'Sync Anki to Notion',
        'notion_to_anki': 'Sync Notion to Anki',
    }
}

# 加载配置中的语言设置
config = load_config()
language = config.get('language', '中文')
menu_texts = MENU_TEXTS.get(language, MENU_TEXTS['中文'])

# 添加设置菜单
def open_settings():
    dialog = SettingsDialog(mw)
    dialog.language_changed.connect(update_menu_texts)
    dialog.exec()

def update_menu_texts(language):
    """更新菜单项的文字"""
    menu_texts = MENU_TEXTS.get(language, MENU_TEXTS['中文'])
    settings_action.setText(menu_texts['settings'])
    anki2notion_action.setText(menu_texts['anki_to_notion'])
    notion2anki_action.setText(menu_texts['notion_to_anki'])

settings_action = QAction(menu_texts['settings'], mw)
settings_action.triggered.connect(open_settings)
mw.form.menuTools.addAction(settings_action)

# 添加Anki到Notion同步菜单
anki2notion_action = QAction(menu_texts['anki_to_notion'], mw)
anki2notion_action.triggered.connect(anki_to_notion)
mw.form.menuTools.addAction(anki2notion_action)

# 添加Notion到Anki同步菜单
notion2anki_action = QAction(menu_texts['notion_to_anki'], mw)
notion2anki_action.triggered.connect(notion_to_anki)
mw.form.menuTools.addAction(notion2anki_action)

# 初始化配置文件，确保新的配置项存在
def init_config():
    config = load_config()
    if 'retain_source_note' not in config:
        config['retain_source_note'] = True
        save_config(config)

# 在插件加载时调用 init_config
init_config() 