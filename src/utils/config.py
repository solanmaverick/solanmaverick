import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigManager:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_config(self, config_path: str = 'config/config.yaml'):
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load config: {str(e)}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    @property
    def discord(self) -> Dict[str, Any]:
        return self._config.get('discord', {})

    @property
    def proxy(self) -> Dict[str, Any]:
        return self._config.get('proxy', {})

    @property
    def ai(self) -> Dict[str, Any]:
        return self._config.get('ai', {})

config = ConfigManager()