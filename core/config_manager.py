#config_manager.py：实现配置管理，可能采用了单例模式（Singleton Pattern）和观察者模式（Observer Pattern）

import json
import os
from typing import Dict, Any
from aqt import mw 

class ConfigManager:
    def __init__(self):
        self.addon_name = __name__
        self._config = {}
        self.load_config()

    def load_config(self):
        """从Anki配置系统获取最新配置并更新实例"""
        config = mw.addonManager.getConfig(self.addon_name)
        if config is None:  # 精确判断是否为None
            self._config = self._get_default_config()
            logger.warning("警告，从配置文件获取配置失败，使用默认配置！")
        else:
            self._config = config
        return self._config

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
    def reload_config(self):
        """显式重新加载配置"""
        return self.load_config()

    def _get_default_config(self):
        """提供默认配置"""
        return {
            "notion_token": "",
            "notion_database_url": "",
            "delete_source_note": False,
            "duplicate_handling_way": "keep",
            "language": "中文"
        }