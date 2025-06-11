import os
import yaml
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv

class Settings:
    def __init__(self, config_path: str = "config.yaml"):
        # Load environment variables from .env file first
        load_dotenv()
        
        self.config_path = config_path
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file with environment variable substitution"""
        try:
            with open(self.config_path, 'r') as f:
                config_content = f.read()
            
            # Replace environment variables
            for key, value in os.environ.items():
                config_content = config_content.replace(f"${{{key}}}", value)
                config_content = config_content.replace(f"${key}", value)
            
            return yaml.safe_load(config_content)
        except FileNotFoundError:
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration"""
        return {
            'database': {
                'type': 'postgresql',
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'name': os.getenv('DB_NAME', 'news_dashboard'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', ''),
            },
            'scrapers': {
                'max_workers': 3,
                'timeout': 300,
                'delay_between_requests': 2
            },
            'ai': {
                'gemini_api_key': os.getenv('GEMINI_API_KEY', ''),
                'model': 'gemini-1.5-flash',
                'enable_content_analysis': True
            },
            'deduplication': {
                'enabled': True,
                'similarity_threshold': 0.85,
                'max_comparison_articles': 1000
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/news_dashboard.log'
            }
        }
    
    def get(self, path: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value using dot notation.
        Example: get('database.type')
        """
        try:
            keys = path.split('.')
            val = self._config
            for key in keys:
                if isinstance(val, dict):
                    val = val[key]
                else:
                    return default
            return val
        except (KeyError, TypeError):
            return default
    
    def get_database_params(self) -> Dict[str, str]:
        """Get database connection parameters"""
        db_config = self._config.get('database', {})
        return {
            'host': db_config.get('host', 'localhost'),
            'port': db_config.get('port', 5432),
            'database': db_config.get('name', 'news_dashboard'),
            'user': db_config.get('user', 'postgres'),
            'password': db_config.get('password', '')
        }

    def is_deduplication_enabled(self) -> bool:
        """Check if deduplication is enabled in the config."""
        return self.get('deduplication.enabled', True)

    def is_debug_mode_enabled(self) -> bool:
        """Check if debug mode is enabled in the config."""
        return self.get('debug.enabled', False)

    def __repr__(self) -> str:
        return f"Settings(config_paths={self.config_paths})"