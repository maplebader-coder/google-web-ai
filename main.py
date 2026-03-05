"""
Google AI Mode Proxy - 主入口
基于 FastAPI 构建的 Google AI Mode 代理服务
提供 OpenAI 兼容 API 接口
"""
import os
import sys
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from sqlalchemy import select

from app.config import settings
from app.models.database import init_db, async_session
from app.models.account import ModelConfig
from app.api.openai_routes import router as openai_router
from app.admin.routes import router as admin_router
from app.services.account_manager import account_manager


# 默认模型列表（Google AI Mode 背后的 Gemini 系列）
DEFAULT_MODELS = [
    {"model_id": "gemini-2.5-pro", "model_name": "Gemini 2.5 Pro", "description": "Google最新旗舰模型，强大的推理和编程能力", "sort_order": 100},
    {"model_id": "gemini-2.0-flash", "model_name": "Gemini 2.0 Flash", "description": "快速响应模型，适合日常对话", "sort_order": 90},
    {"model_id": "gemini-2.0-flash-lite", "model_name": "Gemini 2.0 Flash Lite", "description": "轻量快速模型", "sort_order": 80},
    {"model_id": "gemini-exp", "model_name": "Gemini Experimental", "description": "实验性模型，最新特性", "sort_order": 70},
    {"model_id": "google-ai-mode", "model_name": "Google AI Mode", "description": "Google搜索AI模式（默认）", "sort_order": 60},
    {"model_id": "gemini", "model_name": "Gemini (通用别名)", "description": "通用别名，自动路由到默认模型", "sort_order": 50},
]


async def _init_default_models():
    """初始化默认模型列表（仅在数据库为空时插入）"""
    async with async_session() as db:
        result = await db.execute(select(ModelConfig))
        existing = result.scalars().all()
        if not existing:
            for m in DEFAULT_MODELS:
                db.add(ModelConfig(**m, is_active=True))
            await db.commit()
            logger.info(f"已初始化 {len(DEFAULT_MODELS)} 个默认模型")
        else:
            logger.info(f"模型列表已存在 ({len(existing)} 个)，跳过初始化")


# 配置日志
os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)
logger.remove()
logger.add(sys.stderr, level=settings.LOG_LEVEL, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add(settings.LOG_FILE, level=settings.LOG_LEVEL, rotation="10 MB", retention="7 days", compression="gz")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("=" * 60)
    logger.info(f"  {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"  服务端口: {settings.PORT}")
    logger.info(f"  管理后台: http://0.0.0.0:{settings.PORT}/admin/")
    logger.info(f"  API 地址: http://0.0.0.0:{settings.PORT}/v1/")
    logger.info("=" * 60)
    
    # 初始化数据库
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/logs", exist_ok=True)
    await init_db()
    logger.info("数据库初始化完成")
    
    # 初始化默认模型
    await _init_default_models()
    
    # 启动账户管理器
    await account_manager.start()
    
    yield
    
    # 关闭
    await account_manager.stop()
    logger.info("服务已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

# 注册路由
app.include_router(openai_router)
app.include_router(admin_router)

# 静态文件
app.mount("/static", StaticFiles(directory="app/admin/static"), name="static")


# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/")
async def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "api_docs": "/v1/models",
        "admin": "/admin/",
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
