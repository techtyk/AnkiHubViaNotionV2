from aqt.qt import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
    QCheckBox, QComboBox, pyqtSignal
)
import json
import os
from aqt.qt import QCoreApplication

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

# 语言文本字典
LANGUAGE_TEXTS = {
    '中文': {
        'window_title': 'AnkiRepository 设置',
        'interface_language': '界面语言：',
        'notion_token': 'Notion Token:',
        'notion_db_url': 'Notion Database URL:',
        'anki_query_string': 'Anki 查询字符串:',
        'duplicate_handling': '重复卡片处理方式(keep/overwrite/copy):',
        'delete_source_note': '删除源侧笔记',
        'save': '保存',
        'prompt': '提示',
        'settings_saved': '设置已保存',
        'notion_children_option': '将Notion笔记导入Anki时保留正文'
    },
    'English': {
        'window_title': 'AnkiRepository Settings',
        'interface_language': 'Interface Language:',
        'notion_token': 'Notion Token:',
        'notion_db_url': 'Notion Database URL:',
        'anki_query_string': 'Anki Query String:',
        'duplicate_handling': 'Duplicate Handling (keep/overwrite/copy):',
        'delete_source_note': 'Delete Source Note',
        'save': 'Save',
        'prompt': 'Prompt',
        'settings_saved': 'Settings Saved',
        'notion_children_option': 'Retain Notion Content When'
    }
}

class SettingsDialog(QDialog):
    language_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super(SettingsDialog, self).__init__(parent)

        # 加载配置中的语言设置
        self.config = load_config()
        self.language = self.config.get('language', '中文')

        # 获取当前语言的文本
        self.texts = LANGUAGE_TEXTS.get(self.language, LANGUAGE_TEXTS['中文'])

        self.setWindowTitle(self.texts['window_title'])
        self.layout = QVBoxLayout()

        # 添加语言选择下拉框
        self.language_label = QLabel(self.texts['interface_language'])
        self.language_combo = QComboBox()
        self.language_combo.addItems(['中文', 'English'])
        self.language_combo.setCurrentText(self.language)
        self.language_combo.currentTextChanged.connect(self.change_language)
        self.layout.addWidget(self.language_label)
        self.layout.addWidget(self.language_combo)

        # Notion Token
        self.notion_token_label = QLabel(self.texts['notion_token'])
        self.notion_token_input = QLineEdit()
        self.layout.addWidget(self.notion_token_label)
        self.layout.addWidget(self.notion_token_input)

        # Notion Database URL
        self.notion_db_url_label = QLabel(self.texts['notion_db_url'])
        self.notion_db_url_input = QLineEdit()
        self.layout.addWidget(self.notion_db_url_label)
        self.layout.addWidget(self.notion_db_url_input)

        # Anki Query String
        self.anki_query_label = QLabel(self.texts['anki_query_string'])
        self.anki_query_input = QLineEdit()
        self.layout.addWidget(self.anki_query_label)
        self.layout.addWidget(self.anki_query_input)

        # Duplicate Handling Way
        self.duplicate_handling_label = QLabel(self.texts['duplicate_handling'])
        self.duplicate_handling_input = QLineEdit()
        self.layout.addWidget(self.duplicate_handling_label)
        self.layout.addWidget(self.duplicate_handling_input)

        # Retain Source Note
        self.delete_source_checkbox = QCheckBox(self.texts['delete_source_note'])
        self.layout.addWidget(self.delete_source_checkbox)

        # Retain Notion Content
        self.notion_children_checkbox = QCheckBox(self.texts['notion_children_option'])
        self.layout.addWidget(self.notion_children_checkbox)

        # Save Button
        self.save_button = QPushButton(self.texts['save'])
        self.save_button.clicked.connect(self.save_settings)
        self.layout.addWidget(self.save_button)

        self.setLayout(self.layout)

        # 加载配置
        self.load_settings()

    def change_language(self, text):
        """当语言选择改变时，更新界面文本并发送信号"""
        self.language = text
        self.texts = LANGUAGE_TEXTS.get(self.language, LANGUAGE_TEXTS['中文'])
        self.reload_ui()
        # 更新配置中的语言设置
        self.config['language'] = self.language
        save_config(self.config)
        # 发送语言改变的信号
        self.language_changed.emit(self.language)

    def reload_ui(self):
        """重新加载界面文本"""
        self.setWindowTitle(self.texts['window_title'])
        self.language_label.setText(self.texts['interface_language'])
        self.notion_token_label.setText(self.texts['notion_token'])
        self.notion_db_url_label.setText(self.texts['notion_db_url'])
        self.anki_query_label.setText(self.texts['anki_query_string'])
        self.duplicate_handling_label.setText(self.texts['duplicate_handling'])
        self.delete_source_checkbox.setText(self.texts['delete_source_note'])
        self.notion_children_checkbox.setText(self.texts['notion_children_option'])
        self.save_button.setText(self.texts['save'])

    def load_settings(self):
        """加载配置文件中的设置信息"""
        self.notion_token_input.setText(self.config.get('notion_token', ''))
        self.notion_db_url_input.setText(self.config.get('notion_database_url', ''))
        self.anki_query_input.setText(self.config.get('anki_query_string', ''))
        self.duplicate_handling_input.setText(self.config.get('duplicate_handling_way', 'keep'))
        self.delete_source_checkbox.setChecked(self.config.get('delete_source_note', True))
        self.notion_children_checkbox.setChecked(self.config.get('retain_notion_children', False))
        self.language_combo.setCurrentText(self.config.get('language', '中文'))

    def save_settings(self):
        """保存设置信息到配置文件"""
        self.config.update({
            'notion_token': self.notion_token_input.text(),
            'notion_database_url': self.notion_db_url_input.text(),
            'anki_query_string': self.anki_query_input.text(),
            'duplicate_handling_way': self.duplicate_handling_input.text(),
            'delete_source_note': self.delete_source_checkbox.isChecked(),
            'retain_notion_children': self.notion_children_checkbox.isChecked(),
            'language': self.language_combo.currentText()
        })
        save_config(self.config)
        QMessageBox.information(self, self.texts['prompt'], self.texts['settings_saved'])
        self.close() 