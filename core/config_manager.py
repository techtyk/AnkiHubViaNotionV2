#config_manager.py：实现配置管理，可能采用了单例模式（Singleton Pattern）和观察者模式（Observer Pattern）

import json
import os
from typing import Dict, Any

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = {}
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), '../config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)

    def save_config(self):
        config_path = os.path.join(os.path.dirname(__file__), '../config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default=None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value
        self.save_config()

    def get_menu_texts(self) -> Dict[str, str]:
        return {
            'settings': '设置' if self.get('language') == '中文' else 'Settings',
            'anki_to_notion': '同步到Notion' if self.get('language') == '中文' else 'Sync to Notion',
            'notion_to_anki': '从Notion同步' if self.get('language') == '中文' else 'Sync from Notion'
        }