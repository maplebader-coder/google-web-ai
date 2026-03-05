"""
OpenAI 兼容 API 路由
实现 /v1/chat/completions, /v1/models 等标准接口
"""
import json
import time
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, get_api_keys
from app.models.database import async_session
from app.models.account import RequestLog, ApiKey, ModelConfig
from app.services.account_manager import account_manager

router = APIRouter()


# ========== 请求预处理 ==========

def _clean_request_body(data: dict) -> dict:
    """
    清理请求体中的无效值
    很多第三方客户端（如 Cherry Studio）会将 undefined 的 JS 值
    序列化为字符串 "[undefined]"，需要将其转为 None
    """
    if not isinstance(data, dict):
        return data
    
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str) and value == "[undefined]":
            cleaned[key] = None
        elif isinstance(value, dict):
            cleaned[key] = _clean_request_body(value)
        elif isinstance(value, list):
            cleaned[key] = [
                _clean_request_body(item) if isinstance(item, dict) 
                else (None if item == "[undefined]" else item) 
                for item in value
            ]
        else:
            cleaned[key] = value
    
    return cleaned


# ========== Pydantic 模型（OpenAI 兼容格式） ==========

class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: system/user/assistant")
    content: object = Field(..., description="消息内容（字符串或多模态数组）")


class ChatCompletionRequest(BaseModel):
    """OpenAI 兼容请求体 - 宽松解析，忽略不支持的参数"""
    model: str = Field(default="google-ai-mode", description="模型名称")
    messages: List[ChatMessage] = Field(..., description="消息列表")
    stream: bool = Field(default=False, description="是否流式输出")
    temperature: Optional[float] = Field(default=None, description="温度参数（忽略）")
    max_tokens: Optional[int] = Field(default=None, description="最大输出token数（忽略）")
    top_p: Optional[float] = Field(default=None, description="Top-p参数（忽略）")
    frequency_penalty: Optional[float] = Field(default=None, description="频率惩罚（忽略）")
    presence_penalty: Optional[float] = Field(default=None, description="存在惩罚（忽略）")
    stop: Optional[object] = Field(default=None, description="停止词（忽略）")
    seed: Optional[int] = Field(default=None, description="种子（忽略）")
    user: Optional[str] = Field(default=None, description="用户标识（忽略）")
    response_format: Optional[object] = Field(default=None, description="响应格式（忽略）")
    tools: Optional[object] = Field(default=None, description="工具列表（忽略）")
    tool_choice: Optional[object] = Field(default=None, description="工具选择（忽略）")
    stream_options: Optional[object] = Field(default=None, description="流式选项（忽略）")
    reasoning_effort: Optional[str] = Field(default=None, description="推理努力（忽略）")
    
    class Config:
        # 允许额外字段，不报错
        extra = "allow"


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Usage


# ========== 鉴权依赖 ==========

async def verify_api_key(request: Request):
    """验证 API Key"""
    # 获取 Authorization header
    auth = request.headers.get("Authorization", "")
    api_key = ""
    
    if auth.startswith("Bearer "):
        api_key = auth[7:]
    
    # 如果没有配置 API Key 则跳过校验
    configured_keys = get_api_keys()
    
    if not configured_keys:
        # 检查数据库中的 API Key
        async with async_session() as db:
            result = await db.execute(select(ApiKey).where(ApiKey.is_active == True))
            db_keys = result.scalars().all()
            if not db_keys:
                return api_key  # 没有配置任何 key，跳过校验
            
            key_obj = next((k for k in db_keys if k.key == api_key), None)
            if not key_obj:
                raise HTTPException(status_code=401, detail={
                    "error": {
                        "message": "Invalid API key",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key"
                    }
                })
            
            # 检查是否过期
            if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
                raise HTTPException(status_code=403, detail={
                    "error": {
                        "message": "API key has expired",
                        "type": "invalid_request_error",
                        "code": "key_expired"
                    }
                })
                
            # 检查额度是否耗尽
            if key_obj.max_requests is not None and key_obj.total_requests >= key_obj.max_requests:
                raise HTTPException(status_code=429, detail={
                    "error": {
                        "message": "API key usage limit exceeded",
                        "type": "invalid_request_error",
                        "code": "rate_limit_exceeded"
                    }
                })
            
            # 更新使用记录
            key_obj.total_requests += 1
            key_obj.last_used_at = datetime.utcnow()
            await db.commit()
    else:
        if api_key not in configured_keys:
            raise HTTPException(status_code=401, detail={
                "error": {
                    "message": "Invalid API key",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key"
                }
            })
    
    return api_key


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数量（中文约1.5字/token，英文约4字符/token）"""
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    en_chars = len(text) - cn_chars
    return int(cn_chars / 1.5 + en_chars / 4) or 1


def _extract_text_and_images_from_content(content) -> tuple:
    """
    从消息的 content 字段中提取纯文本和图片数据
    
    Returns:
        tuple: (text: str, images: list)
    """
    if content is None:
        return "", []
    
    if isinstance(content, str):
        return content, []
    
    if isinstance(content, list):
        text_parts = []
        images = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    # 提取图片 URL 或 base64 数据
                    image_url_obj = item.get("image_url", {})
                    if isinstance(image_url_obj, dict):
                        url = image_url_obj.get("url", "")
                    else:
                        url = str(image_url_obj)
                    
                    if url:
                        images.append(url)
                        text_parts.append("[图片]")
            elif isinstance(item, str):
                text_parts.append(item)
        
        return "\n".join(text_parts), images
    
    return str(content), []


def _build_query_from_messages(messages: List[ChatMessage]) -> tuple:
    """
    将 OpenAI 格式的消息列表转换为查询文本和图片列表
    
    Returns:
        tuple: (query_text: str, image_data_list: list)
    """
    parts = []
    system_prompt = ""
    all_images = []
    
    for msg in messages:
        text, images = _extract_text_and_images_from_content(msg.content)
        
        # 收集所有图片（只保留最后一条用户消息中的图片）
        if msg.role == "user" and images:
            all_images = images  # 覆盖之前的图片，只保留最新的
        
        if msg.role == "system":
            system_prompt = text
        elif msg.role == "user":
            parts.append(text)
        elif msg.role == "assistant":
            # 助手的历史回复也作为上下文
            parts.append(f"[之前你回答了: {text[:200]}]")
    
    query = ""
    if system_prompt:
        query = f"[系统指令: {system_prompt}]\n\n"
    
    # 取最后一条用户消息作为主查询，之前的作为上下文
    if len(parts) > 1:
        context = "\n".join(parts[:-1])
        query += f"[对话上下文: {context}]\n\n{parts[-1]}"
    elif parts:
        query += parts[-1]
    else:
        query = "你好"
    
    return query, all_images


# ========== API 路由 ==========

@router.get("/v1/models")
async def list_models(api_key: str = Depends(verify_api_key)):
    """列出可用模型（从数据库读取，按 API Key 权限过滤）"""
    
    # 获取该 API Key 允许的模型列表
    allowed_model_ids = None  # None = 全部
    if api_key:
        async with async_session() as db:
            result = await db.execute(select(ApiKey).where(ApiKey.key == api_key, ApiKey.is_active == True))
            key_obj = result.scalar_one_or_none()
            if key_obj and key_obj.allowed_models:
                allowed_model_ids = [m.strip() for m in key_obj.allowed_models.split(",") if m.strip()]
    
    # 从数据库读取所有启用的模型
    async with async_session() as db:
        result = await db.execute(
            select(ModelConfig).where(ModelConfig.is_active == True).order_by(ModelConfig.sort_order.desc())
        )
        models = result.scalars().all()
    
    data = []
    for m in models:
        # 如果该 Key 有模型限制，过滤掉不在列表中的
        if allowed_model_ids and m.model_id not in allowed_model_ids:
            continue
        data.append({
            "id": m.model_id,
            "object": "model",
            "created": int(m.created_at.timestamp()) if m.created_at else 1700000000,
            "owned_by": "google",
            "permission": [],
            "root": m.model_id,
            "parent": None,
        })
    
    return {"object": "list", "data": data}


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    """
    OpenAI 兼容的 Chat Completions 接口
    先清理请求体中的 [undefined] 值，再进行 Pydantic 校验
    """
    # 预处理：读取原始 JSON 并清理无效值
    try:
        raw_body = await request.json()
        cleaned_body = _clean_request_body(raw_body)
        body = ChatCompletionRequest(**cleaned_body)
    except Exception as e:
        logger.error(f"请求体解析失败: {e}")
        raise HTTPException(status_code=400, detail={
            "error": {
                "message": f"Invalid request body: {str(e)}",
                "type": "invalid_request_error",
                "code": "invalid_body"
            }
        })
    
    request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    start_time = time.time()
    
    # 构建查询文本和提取图片
    query_text, image_data_list = _build_query_from_messages(body.messages)
    
    # 获取可用账户
    account_info = await account_manager.get_next_account()
    if not account_info:
        raise HTTPException(status_code=503, detail={
            "error": {
                "message": "No available Google accounts. Please add accounts in admin panel.",
                "type": "server_error",
                "code": "no_accounts"
            }
        })
    
    account_id, account_email, client = account_info
    client_ip = request.client.host if request.client else ""
    
    # 如果有图片，先上传获取 vsrid
    vsrid = None
    if image_data_list:
        logger.info(f"请求 {request_id}: 检测到 {len(image_data_list)} 张图片，开始上传...")
        vsrid = await client.upload_image(image_data_list[0])  # 目前只支持第一张图片
        if vsrid:
            logger.info(f"请求 {request_id}: 图片上传成功, vsrid={vsrid[:20]}...")
        else:
            logger.warning(f"请求 {request_id}: 图片上传失败，将以纯文字模式继续")
    
    logger.info(f"请求 {request_id}: 使用账户 {account_email}, query={query_text[:50]}...")
    
    if body.stream:
        # 流式响应
        return StreamingResponse(
            _stream_response(
                request_id=request_id,
                model=body.model,
                query_text=query_text,
                account_id=account_id,
                account_email=account_email,
                client=client,
                client_ip=client_ip,
                api_key=api_key,
                messages_json=json.dumps([m.model_dump() for m in body.messages], ensure_ascii=False),
                start_time=start_time,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    else:
        # 非流式响应
        try:
            result = await client.chat(query_text)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if result["success"]:
                response_text = result["text"]
                prompt_tokens = _estimate_tokens(query_text)
                completion_tokens = _estimate_tokens(response_text)
                
                # 记录日志
                await _log_request(
                    request_id=request_id,
                    account_id=account_id,
                    account_email=account_email,
                    model=body.model,
                    messages_json=json.dumps([m.model_dump() for m in body.messages], ensure_ascii=False),
                    stream=False,
                    query_text=query_text,
                    response_text=response_text,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    status="success",
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                    api_key=api_key,
                )
                
                # 上报成功
                await account_manager.report_request(account_id, True)
                # 同步 token
                await account_manager.update_account_tokens(account_id, client)
                
                return ChatCompletionResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=body.model,
                    choices=[
                        ChatCompletionChoice(
                            index=0,
                            message=ChatMessage(role="assistant", content=response_text),
                            finish_reason="stop",
                        )
                    ],
                    usage=Usage(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                    ),
                )
            else:
                error_msg = result.get("error", "Unknown error")
                duration_ms = int((time.time() - start_time) * 1000)
                
                await _log_request(
                    request_id=request_id,
                    account_id=account_id,
                    account_email=account_email,
                    model=body.model,
                    messages_json=json.dumps([m.model_dump() for m in body.messages], ensure_ascii=False),
                    stream=False,
                    query_text=query_text,
                    response_text="",
                    status="error",
                    error_message=error_msg,
                    duration_ms=duration_ms,
                    client_ip=client_ip,
                    api_key=api_key,
                )
                
                await account_manager.report_request(account_id, False, error_msg)
                
                raise HTTPException(status_code=500, detail={
                    "error": {
                        "message": error_msg,
                        "type": "server_error",
                        "code": "ai_query_failed"
                    }
                })
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chat completions 异常: {e}")
            await account_manager.report_request(account_id, False, str(e))
            raise HTTPException(status_code=500, detail={
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": "internal_error"
                }
            })


async def _stream_response(
    request_id: str,
    model: str,
    query_text: str,
    account_id: int,
    account_email: str,
    client,
    client_ip: str,
    api_key: str,
    messages_json: str,
    start_time: float,
):
    """生成 SSE 流式响应"""
    full_response = ""
    
    try:
        async for chunk_text in client.chat_stream(query_text):
            if chunk_text.startswith("[ERROR]"):
                # 错误
                error_data = {
                    "id": request_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk_text},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                
                await account_manager.report_request(account_id, False, chunk_text)
                return
            
            full_response += chunk_text
            
            # 构建 SSE 数据块
            chunk_data = {
                "id": request_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": chunk_text},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"
        
        # 发送结束标记
        end_data = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
        # 记录日志
        duration_ms = int((time.time() - start_time) * 1000)
        prompt_tokens = _estimate_tokens(query_text)
        completion_tokens = _estimate_tokens(full_response)
        
        await _log_request(
            request_id=request_id,
            account_id=account_id,
            account_email=account_email,
            model=model,
            messages_json=messages_json,
            stream=True,
            query_text=query_text,
            response_text=full_response,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            status="success",
            duration_ms=duration_ms,
            client_ip=client_ip,
            api_key=api_key,
        )
        
        await account_manager.report_request(account_id, True)
        await account_manager.update_account_tokens(account_id, client)
        
    except Exception as e:
        logger.error(f"流式响应异常: {e}")
        error_data = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"content": f"\n[Error: {str(e)}]"},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
        await account_manager.report_request(account_id, False, str(e))


async def _log_request(**kwargs):
    """记录请求日志到数据库"""
    try:
        async with async_session() as db:
            log = RequestLog(
                request_id=kwargs.get("request_id", ""),
                account_id=kwargs.get("account_id"),
                account_email=kwargs.get("account_email", ""),
                model=kwargs.get("model", ""),
                messages_json=kwargs.get("messages_json", ""),
                stream=kwargs.get("stream", False),
                query_text=kwargs.get("query_text", ""),
                response_text=kwargs.get("response_text", "")[:5000],  # 限制长度
                prompt_tokens=kwargs.get("prompt_tokens", 0),
                completion_tokens=kwargs.get("completion_tokens", 0),
                total_tokens=kwargs.get("prompt_tokens", 0) + kwargs.get("completion_tokens", 0),
                status=kwargs.get("status", "pending"),
                error_message=kwargs.get("error_message", ""),
                duration_ms=kwargs.get("duration_ms", 0),
                client_ip=kwargs.get("client_ip", ""),
                api_key_used=kwargs.get("api_key", "")[:8] + "***" if kwargs.get("api_key") else "",
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.error(f"记录请求日志失败: {e}")
