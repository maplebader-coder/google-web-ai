"""
应用配置模块
"""
import os
import secrets
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 应用基本配置
    APP_NAME: str = "Google AI Mode Proxy"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8787
    
    # 管理后台
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    SECRET_KEY: str = secrets.token_hex(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时
    
    # API Key 配置（用于OpenAI兼容接口鉴权）
    API_KEYS: str = ""  # 逗号分隔的多个key，为空则不校验
    
    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/proxy.db"
    
    # Google AI 相关
    GOOGLE_SEARCH_URL: str = "https://www.google.com"
    GOOGLE_LENS_URL: str = "https://lensfrontend-pa.clients6.google.com"
    
    # 请求配置
    REQUEST_TIMEOUT: int = 120
    MAX_RETRIES: int = 3
    
    # 账户轮询策略: round_robin | random | least_used
    ACCOUNT_ROTATION_STRATEGY: str = "round_robin"
    
    # Cookie 轮换间隔（秒）
    COOKIE_ROTATE_INTERVAL: int = 540  # 9分钟，留1分钟缓冲
    
    # 运行模式: login（登录Cookie模式） | anonymous（未登录模式） | auto（优先Cookie，降级匿名）
    RUN_MODE: str = "auto"
    
    # 日志
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./data/logs/app.log"
    
    # 代理（可选，用于访问Google）
    HTTP_PROXY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def get_api_keys() -> list:
    """获取有效的API Keys列表"""
    if not settings.API_KEYS:
        return []
    return [k.strip() for k in settings.API_KEYS.split(",") if k.strip()]
