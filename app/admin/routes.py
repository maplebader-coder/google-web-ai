"""
管理后台 API 路由
"""
import json
import secrets
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from loguru import logger
from sqlalchemy import select, desc, func

from app.config import settings
from app.models.database import async_session
from app.models.account import GoogleAccount, RequestLog, ApiKey, ModelConfig
from app.services.account_manager import account_manager

router = APIRouter(prefix="/admin")

templates = Jinja2Templates(directory="app/admin/templates")


# ========== 简单的管理员鉴权 ==========

def verify_admin(request: Request):
    """验证管理员登录状态（通过Cookie中的token）"""
    token = request.cookies.get("admin_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    # 简单校验：token 格式为 admin:{密码hash前16位}
    expected = f"admin:{hash(settings.ADMIN_PASSWORD) % (10**16)}"
    if token != expected:
        raise HTTPException(status_code=401, detail="登录已过期")
    return True


# ========== 页面路由 ==========

@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request):
    """管理后台主页"""
    return templates.TemplateResponse("index.html", {"request": request, "settings": settings})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """登录页面"""
    return templates.TemplateResponse("login.html", {"request": request})


# ========== API 路由 ==========

@router.post("/api/login")
async def admin_login(request: Request):
    """管理员登录"""
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")
    
    if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
        token = f"admin:{hash(settings.ADMIN_PASSWORD) % (10**16)}"
        response = JSONResponse({"success": True, "message": "登录成功"})
        response.set_cookie("admin_token", token, max_age=86400, httponly=True)
        return response
    else:
        raise HTTPException(status_code=401, detail="用户名或密码错误")


@router.post("/api/logout")
async def admin_logout():
    """注销"""
    response = JSONResponse({"success": True})
    response.delete_cookie("admin_token")
    return response


@router.get("/api/stats")
async def get_stats(auth: bool = Depends(verify_admin)):
    """获取系统统计信息"""
    stats = await account_manager.get_stats()
    return stats


@router.get("/api/accounts")
async def get_accounts(auth: bool = Depends(verify_admin)):
    """获取所有账户"""
    accounts = await account_manager.get_all_accounts()
    return {"accounts": accounts}


@router.post("/api/accounts")
async def add_account(request: Request, auth: bool = Depends(verify_admin)):
    """添加账户"""
    body = await request.json()
    email = body.get("email", "").strip()
    cookies_json = body.get("cookies_json", "").strip()
    display_name = body.get("display_name", "").strip()
    
    if not email:
        raise HTTPException(status_code=400, detail="邮箱不能为空")
    if not cookies_json:
        raise HTTPException(status_code=400, detail="Cookie 不能为空")
    
    result = await account_manager.add_account(email, cookies_json, display_name)
    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=400, detail=result["error"])


@router.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int, auth: bool = Depends(verify_admin)):
    """删除账户"""
    result = await account_manager.remove_account(account_id)
    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=400, detail=result["error"])


@router.post("/api/accounts/{account_id}/toggle")
async def toggle_account(account_id: int, request: Request, auth: bool = Depends(verify_admin)):
    """启用/禁用账户"""
    body = await request.json()
    active = body.get("active", True)
    result = await account_manager.toggle_account(account_id, active)
    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=400, detail=result["error"])


@router.post("/api/accounts/{account_id}/reinit")
async def reinit_account(account_id: int, auth: bool = Depends(verify_admin)):
    """重新初始化账户会话"""
    result = await account_manager.reinit_account(account_id)
    if result["success"]:
        return result
    else:
        raise HTTPException(status_code=400, detail=result["error"])


@router.get("/api/logs")
async def get_logs(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    auth: bool = Depends(verify_admin),
):
    """获取请求日志"""
    async with async_session() as db:
        query = select(RequestLog)
        count_query = select(func.count(RequestLog.id))
        
        if status:
            query = query.where(RequestLog.status == status)
            count_query = count_query.where(RequestLog.status == status)
        
        total = await db.scalar(count_query) or 0
        
        result = await db.execute(
            query.order_by(desc(RequestLog.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        logs = result.scalars().all()
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
            "logs": [
                {
                    "id": log.id,
                    "request_id": log.request_id,
                    "account_email": log.account_email,
                    "model": log.model,
                    "stream": log.stream,
                    "query_text": log.query_text[:100],
                    "response_text": log.response_text[:200],
                    "prompt_tokens": log.prompt_tokens,
                    "completion_tokens": log.completion_tokens,
                    "total_tokens": log.total_tokens,
                    "status": log.status,
                    "error_message": log.error_message,
                    "duration_ms": log.duration_ms,
                    "client_ip": log.client_ip,
                    "api_key_used": log.api_key_used,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]
        }


@router.get("/api/apikeys")
async def get_api_keys_list(auth: bool = Depends(verify_admin)):
    """获取 API Key 列表"""
    async with async_session() as db:
        result = await db.execute(select(ApiKey).order_by(ApiKey.id))
        keys = result.scalars().all()
        return {
            "keys": [
                {
                    "id": k.id,
                    "key": k.key[:8] + "..." + k.key[-4:] if len(k.key) > 12 else k.key,
                    "full_key": k.key,
                    "name": k.name,
                    "is_active": k.is_active,
                    "total_requests": k.total_requests,
                    "max_requests": k.max_requests,
                    "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                    "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
                    "allowed_models": k.allowed_models or "",
                    "created_at": k.created_at.isoformat() if k.created_at else None,
                }
                for k in keys
            ]
        }


@router.post("/api/apikeys")
async def create_api_key(request: Request, auth: bool = Depends(verify_admin)):
    """创建新的 API Key"""
    body = await request.json()
    name = body.get("name", "")
    max_requests = body.get("max_requests")
    expires_at_str = body.get("expires_at")
    
    expires_at = None
    if expires_at_str:
        try:
            # 尝试解析前端传来的日期字符串
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"解析过期时间失败: {expires_at_str}, error: {e}")
            
    key = f"sk-{secrets.token_hex(24)}"
    
    async with async_session() as db:
        api_key = ApiKey(
            key=key, 
            name=name, 
            is_active=True,
            max_requests=int(max_requests) if max_requests is not None and str(max_requests).isdigit() else None,
            expires_at=expires_at
        )
        db.add(api_key)
        await db.commit()
    
    return {"success": True, "key": key, "name": name}


@router.delete("/api/apikeys/{key_id}")
async def delete_api_key(key_id: int, auth: bool = Depends(verify_admin)):
    """删除 API Key"""
    async with async_session() as db:
        key = await db.get(ApiKey, key_id)
        if key:
            await db.delete(key)
            await db.commit()
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="API Key 不存在")


@router.post("/api/apikeys/{key_id}/toggle")
async def toggle_api_key(key_id: int, request: Request, auth: bool = Depends(verify_admin)):
    """启用/禁用 API Key"""
    body = await request.json()
    active = body.get("active", True)
    
    async with async_session() as db:
        key = await db.get(ApiKey, key_id)
        if key:
            key.is_active = active
            await db.commit()
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="API Key 不存在")


@router.get("/api/accounts/{account_id}/cookies")
async def get_account_cookies(account_id: int, auth: bool = Depends(verify_admin)):
    """获取账户的Cookie数据（用于编辑）"""
    async with async_session() as db:
        account = await db.get(GoogleAccount, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在")
        return {
            "id": account.id,
            "email": account.email,
            "cookies_json": account.cookies_json or "{}",
            "mstk": account.mstk or "",
            "stkp": account.stkp or "",
            "elrc": account.elrc or "",
            "sca_esv": account.sca_esv or "",
            "xsrf_token": account.xsrf_token or "",
            "at_token": account.at_token or "",
        }


@router.put("/api/accounts/{account_id}/cookies")
async def update_account_cookies(account_id: int, request: Request, auth: bool = Depends(verify_admin)):
    """更新账户的Cookie数据"""
    body = await request.json()
    cookies_json = body.get("cookies_json", "").strip()
    
    if not cookies_json:
        raise HTTPException(status_code=400, detail="Cookie 不能为空")
    
    try:
        cookies_dict = json.loads(cookies_json)
        if not isinstance(cookies_dict, dict):
            raise HTTPException(status_code=400, detail="Cookie 格式错误，需要 JSON 对象")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Cookie JSON 格式无效")
    
    async with async_session() as db:
        account = await db.get(GoogleAccount, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账户不存在")
        
        account.cookies_json = cookies_json
        account.updated_at = datetime.utcnow()
        await db.commit()
    
    # 重新创建客户端并初始化
    result = await account_manager.reinit_account(account_id)
    return {"success": True, "message": "Cookie 已更新", "reinit": result}


@router.post("/api/parse-cookies")
async def parse_cookies(request: Request, auth: bool = Depends(verify_admin)):
    """
    解析各种格式的 Cookie 数据，统一转换为 JSON 对象
    支持：
    1. JSON 对象格式: {"key": "value", ...}
    2. JSON 数组格式（Cookie-Editor插件导出）: [{"name":"key","value":"val",...}, ...]
    3. 原始 Cookie 字符串: key1=value1; key2=value2; ...
    4. Netscape/cURL 格式: 每行 domain\tpath\t...\tname\tvalue
    """
    body = await request.json()
    raw = body.get("raw", "").strip()
    
    if not raw:
        return {"success": False, "error": "请粘贴 Cookie 数据"}
    
    cookies_dict = {}
    parse_format = "unknown"
    
    # 尝试 JSON 解析
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            # 格式1: 直接的 JSON 对象
            cookies_dict = data
            parse_format = "json_object"
        elif isinstance(data, list):
            # 格式2: Cookie-Editor 数组格式 [{"name":"x","value":"y",...}, ...]
            for item in data:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    value = item.get("value", "")
                    if name:
                        cookies_dict[name] = value
            parse_format = "json_array"
    except json.JSONDecodeError:
        pass
    
    # 尝试原始 Cookie 字符串解析
    if not cookies_dict and "=" in raw:
        # 格式3: key1=value1; key2=value2
        if "\t" not in raw.split("\n")[0]:
            parts = raw.replace("\n", ";").split(";")
            for part in parts:
                part = part.strip()
                if "=" in part:
                    name, value = part.split("=", 1)
                    name = name.strip()
                    value = value.strip()
                    if name:
                        cookies_dict[name] = value
            parse_format = "cookie_string"
    
    # 尝试 Netscape/cURL 格式
    if not cookies_dict and "\t" in raw:
        lines = raw.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            fields = line.split("\t")
            if len(fields) >= 7:
                cookies_dict[fields[5]] = fields[6]
            elif len(fields) >= 2:
                cookies_dict[fields[0]] = fields[1]
        parse_format = "netscape"
    
    if not cookies_dict:
        return {"success": False, "error": "无法解析 Cookie 数据，请检查格式"}
    
    # 提取关键Cookie信息
    key_cookies = {
        "SID": cookies_dict.get("SID", ""),
        "HSID": cookies_dict.get("HSID", ""),
        "SSID": cookies_dict.get("SSID", ""),
        "SAPISID": cookies_dict.get("SAPISID", ""),
        "__Secure-1PSID": cookies_dict.get("__Secure-1PSID", ""),
        "__Secure-3PSID": cookies_dict.get("__Secure-3PSID", ""),
        "NID": cookies_dict.get("NID", ""),
    }
    has_auth = bool(key_cookies["SID"] or key_cookies["__Secure-1PSID"])
    
    return {
        "success": True,
        "format": parse_format,
        "cookies_json": json.dumps(cookies_dict, ensure_ascii=False),
        "total_cookies": len(cookies_dict),
        "key_cookies": key_cookies,
        "has_auth": has_auth,
    }


@router.get("/api/settings")
async def get_settings(auth: bool = Depends(verify_admin)):
    """获取系统设置"""
    return {
        "rotation_strategy": settings.ACCOUNT_ROTATION_STRATEGY,
        "cookie_rotate_interval": settings.COOKIE_ROTATE_INTERVAL,
        "request_timeout": settings.REQUEST_TIMEOUT,
        "max_retries": settings.MAX_RETRIES,
        "http_proxy": settings.HTTP_PROXY or "",
        "port": settings.PORT,
        "run_mode": settings.RUN_MODE,
    }


@router.post("/api/settings/run_mode")
async def set_run_mode(request: Request, auth: bool = Depends(verify_admin)):
    """切换运行模式"""
    body = await request.json()
    mode = body.get("mode", "auto")
    if mode not in ("login", "anonymous", "auto"):
        raise HTTPException(status_code=400, detail="无效的模式值")
    settings.RUN_MODE = mode
    return {"success": True, "run_mode": mode}


# ========== 模型管理 ==========

@router.get("/api/models")
async def get_models(auth: bool = Depends(verify_admin)):
    """获取所有模型列表"""
    async with async_session() as db:
        result = await db.execute(select(ModelConfig).order_by(ModelConfig.sort_order.desc()))
        models = result.scalars().all()
        return {
            "models": [
                {
                    "id": m.id,
                    "model_id": m.model_id,
                    "model_name": m.model_name,
                    "description": m.description,
                    "is_active": m.is_active,
                    "sort_order": m.sort_order,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in models
            ]
        }


@router.post("/api/models")
async def add_model(request: Request, auth: bool = Depends(verify_admin)):
    """添加模型"""
    body = await request.json()
    model_id = body.get("model_id", "").strip()
    model_name = body.get("model_name", "").strip()
    description = body.get("description", "").strip()
    sort_order = body.get("sort_order", 0)

    if not model_id:
        raise HTTPException(status_code=400, detail="模型ID不能为空")

    async with async_session() as db:
        existing = await db.execute(select(ModelConfig).where(ModelConfig.model_id == model_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"模型ID '{model_id}' 已存在")

        model = ModelConfig(
            model_id=model_id,
            model_name=model_name or model_id,
            description=description,
            sort_order=sort_order,
            is_active=True,
        )
        db.add(model)
        await db.commit()

    return {"success": True, "model_id": model_id}


@router.put("/api/models/{mid}")
async def update_model(mid: int, request: Request, auth: bool = Depends(verify_admin)):
    """更新模型信息"""
    body = await request.json()

    async with async_session() as db:
        model = await db.get(ModelConfig, mid)
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        if "model_id" in body:
            model.model_id = body["model_id"].strip()
        if "model_name" in body:
            model.model_name = body["model_name"].strip()
        if "description" in body:
            model.description = body["description"].strip()
        if "sort_order" in body:
            model.sort_order = body["sort_order"]
        if "is_active" in body:
            model.is_active = body["is_active"]

        await db.commit()

    return {"success": True}


@router.delete("/api/models/{mid}")
async def delete_model(mid: int, auth: bool = Depends(verify_admin)):
    """删除模型"""
    async with async_session() as db:
        model = await db.get(ModelConfig, mid)
        if model:
            await db.delete(model)
            await db.commit()
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="模型不存在")


@router.post("/api/models/{mid}/toggle")
async def toggle_model(mid: int, request: Request, auth: bool = Depends(verify_admin)):
    """启用/禁用模型"""
    body = await request.json()
    active = body.get("active", True)

    async with async_session() as db:
        model = await db.get(ModelConfig, mid)
        if model:
            model.is_active = active
            await db.commit()
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="模型不存在")


# ========== API Key 绑定模型（增强） ==========

@router.get("/api/apikeys/{key_id}/models")
async def get_key_allowed_models(key_id: int, auth: bool = Depends(verify_admin)):
    """获取某个 API Key 允许的模型列表"""
    async with async_session() as db:
        key = await db.get(ApiKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API Key 不存在")
        allowed = [m.strip() for m in (key.allowed_models or "").split(",") if m.strip()]
        return {"key_id": key_id, "allowed_models": allowed}


@router.put("/api/apikeys/{key_id}/models")
async def set_key_allowed_models(key_id: int, request: Request, auth: bool = Depends(verify_admin)):
    """设置 API Key 允许使用的模型列表"""
    body = await request.json()
    model_ids = body.get("model_ids", [])  # 空列表 = 允许全部

    async with async_session() as db:
        key = await db.get(ApiKey, key_id)
        if not key:
            raise HTTPException(status_code=404, detail="API Key 不存在")
        key.allowed_models = ",".join(model_ids) if model_ids else ""
        await db.commit()

    return {"success": True, "allowed_models": model_ids}
