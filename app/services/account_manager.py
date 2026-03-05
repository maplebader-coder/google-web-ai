"""
账户管理服务
负责多账户轮询、Cookie轮换调度、账户状态管理
"""
import json
import random
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.config import settings
from app.models.database import async_session
from app.models.account import GoogleAccount, RequestLog
from app.core.google_client import GoogleAIClient


class AccountManager:
    """账户管理器（单例）"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # 客户端缓存 {account_id: GoogleAIClient}
        self._clients: Dict[int, GoogleAIClient] = {}
        
        # 匿名客户端（未登录模式）
        self._anonymous_client: Optional[GoogleAIClient] = None
        
        # 轮询索引
        self._round_robin_index = 0
        
        # Cookie 轮换任务
        self._rotate_task: Optional[asyncio.Task] = None
        
        # 统计
        self._total_served = 0
    
    async def start(self):
        """启动账户管理器"""
        logger.info("启动账户管理器...")
        
        # 初始化所有活跃账户的客户端
        async with async_session() as db:
            result = await db.execute(
                select(GoogleAccount).where(GoogleAccount.is_active == True)
            )
            accounts = result.scalars().all()
            
            for account in accounts:
                try:
                    await self._create_client(account)
                    logger.info(f"账户 {account.email} 客户端已初始化")
                except Exception as e:
                    logger.error(f"账户 {account.email} 客户端初始化失败: {e}")
        
        # 启动 Cookie 轮换定时任务
        self._rotate_task = asyncio.create_task(self._cookie_rotate_loop())
        
        logger.info(f"账户管理器启动完成, 活跃账户数: {len(self._clients)}")
    
    async def stop(self):
        """停止账户管理器"""
        logger.info("停止账户管理器...")
        
        # 取消轮换任务
        if self._rotate_task:
            self._rotate_task.cancel()
            try:
                await self._rotate_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有客户端
        for account_id, client in self._clients.items():
            try:
                await client.close()
            except Exception:
                pass
        self._clients.clear()
        
        logger.info("账户管理器已停止")
    
    async def _create_client(self, account: GoogleAccount) -> GoogleAIClient:
        """为账户创建客户端实例"""
        cookies_dict = json.loads(account.cookies_json) if account.cookies_json else {}
        
        client = GoogleAIClient(
            cookies_dict=cookies_dict,
            mstk=account.mstk or "",
            stkp=account.stkp or "",
            elrc=account.elrc or "",
            sca_esv=account.sca_esv or "",
            xsrf_token=account.xsrf_token or "",
            at_token=account.at_token or "",
        )
        
        self._clients[account.id] = client
        return client
    
    async def _get_anonymous_client(self) -> GoogleAIClient:
        """获取或创建匿名客户端"""
        if not self._anonymous_client:
            self._anonymous_client = GoogleAIClient(anonymous=True)
            # 初始化匿名会话
            await self._anonymous_client.initialize_session()
        return self._anonymous_client

    async def get_next_account(self) -> Optional[tuple]:
        """
        根据运行模式和轮询策略获取下一个可用账户
        
        Returns:
            tuple: (account_id, email, GoogleAIClient) 或 None
        """
        run_mode = settings.RUN_MODE
        
        # 匿名模式：直接返回匿名客户端
        if run_mode == "anonymous":
            client = await self._get_anonymous_client()
            return (0, "anonymous", client)
        
        # auto 模式：优先登录账户，无账户时降级匿名
        # login 模式：仅使用登录账户
        
        async with async_session() as db:
            # 查询所有活跃且非忙碌的账户
            result = await db.execute(
                select(GoogleAccount).where(
                    GoogleAccount.is_active == True,
                    GoogleAccount.status.in_(["idle", "busy"])  # busy 也允许（并发场景）
                ).order_by(GoogleAccount.priority.desc(), GoogleAccount.id)
            )
            accounts = result.scalars().all()
        
        if not accounts:
            if run_mode == "auto":
                logger.info("无可用登录账户，降级为匿名模式")
                client = await self._get_anonymous_client()
                return (0, "anonymous", client)
            logger.error("没有可用的账户")
            return None
        
        strategy = settings.ACCOUNT_ROTATION_STRATEGY
        
        if strategy == "round_robin":
            # 轮询
            idx = self._round_robin_index % len(accounts)
            self._round_robin_index += 1
            selected = accounts[idx]
            
        elif strategy == "random":
            # 随机
            selected = random.choice(accounts)
            
        elif strategy == "least_used":
            # 最少使用
            selected = min(accounts, key=lambda a: a.total_requests)
            
        else:
            selected = accounts[0]
        
        # 确保客户端存在
        if selected.id not in self._clients:
            try:
                await self._create_client(selected)
            except Exception as e:
                logger.error(f"创建账户 {selected.email} 客户端失败: {e}")
                return None
        
        client = self._clients[selected.id]
        return (selected.id, selected.email, client)
    
    async def report_request(self, account_id: int, success: bool, error_msg: str = ""):
        """上报请求结果"""
        async with async_session() as db:
            account = await db.get(GoogleAccount, account_id)
            if account:
                account.total_requests += 1
                if success:
                    account.success_requests += 1
                    account.status = "idle"
                    account.error_message = ""
                else:
                    account.fail_requests += 1
                    # 连续失败超过阈值则标记为error
                    if account.fail_requests > 0 and account.fail_requests % 5 == 0:
                        account.status = "error"
                        account.error_message = error_msg
                
                account.last_used_at = datetime.utcnow()
                await db.commit()
        
        self._total_served += 1
    
    async def update_account_tokens(self, account_id: int, client: GoogleAIClient):
        """将客户端的最新token同步回数据库"""
        async with async_session() as db:
            account = await db.get(GoogleAccount, account_id)
            if account:
                tokens = client.get_current_tokens()
                account.mstk = tokens.get("mstk", "")
                account.stkp = tokens.get("stkp", "")
                account.elrc = tokens.get("elrc", "")
                account.sca_esv = tokens.get("sca_esv", "")
                account.xsrf_token = tokens.get("xsrf_token", "")
                account.at_token = tokens.get("at_token", "")
                account.ei = tokens.get("ei", "")
                account.cookies_json = json.dumps(client.get_cookies_dict())
                await db.commit()
    
    async def _cookie_rotate_loop(self):
        """Cookie 轮换定时循环"""
        logger.info(f"Cookie 轮换任务启动, 间隔 {settings.COOKIE_ROTATE_INTERVAL} 秒")
        
        while True:
            try:
                await asyncio.sleep(settings.COOKIE_ROTATE_INTERVAL)
                await self._rotate_all_cookies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cookie 轮换循环异常: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试
    
    async def _rotate_all_cookies(self):
        """对所有活跃账户执行 Cookie 轮换"""
        logger.info("开始批量 Cookie 轮换...")
        
        for account_id, client in list(self._clients.items()):
            try:
                result = await client.rotate_cookies()
                if result["success"]:
                    # 同步更新后的 Cookie 到数据库
                    async with async_session() as db:
                        account = await db.get(GoogleAccount, account_id)
                        if account:
                            account.cookies_json = json.dumps(client.get_cookies_dict())
                            account.last_cookie_rotate_at = datetime.utcnow()
                            account.cookie_rotate_count += 1
                            await db.commit()
                    
                    logger.debug(f"账户 ID={account_id} Cookie 轮换成功")
                else:
                    logger.warning(f"账户 ID={account_id} Cookie 轮换失败: {result.get('error', '')}")
            except Exception as e:
                logger.error(f"账户 ID={account_id} Cookie 轮换异常: {e}")
        
        logger.info("批量 Cookie 轮换完成")
    
    async def add_account(self, email: str, cookies_json: str, display_name: str = "") -> dict:
        """
        添加新的 Google 账户
        
        Args:
            email: Google 邮箱
            cookies_json: Cookie JSON 字符串
            display_name: 显示名称
            
        Returns:
            dict: 操作结果
        """
        try:
            # 验证 cookies_json 格式
            cookies_dict = json.loads(cookies_json)
            if not isinstance(cookies_dict, dict):
                return {"success": False, "error": "Cookie 格式错误，需要 JSON 对象"}
            
            async with async_session() as db:
                # 检查是否已存在
                result = await db.execute(
                    select(GoogleAccount).where(GoogleAccount.email == email)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # 更新
                    existing.cookies_json = cookies_json
                    existing.display_name = display_name or existing.display_name
                    existing.is_active = True
                    existing.status = "idle"
                    existing.error_message = ""
                    existing.updated_at = datetime.utcnow()
                    await db.commit()
                    
                    # 重新创建客户端
                    if existing.id in self._clients:
                        await self._clients[existing.id].close()
                    await self._create_client(existing)
                    
                    # 尝试初始化会话
                    client = self._clients[existing.id]
                    init_result = await client.initialize_session()
                    if init_result.get("success"):
                        await self.update_account_tokens(existing.id, client)
                    
                    return {"success": True, "message": f"账户 {email} 已更新", "id": existing.id}
                else:
                    # 新增
                    account = GoogleAccount(
                        email=email,
                        display_name=display_name,
                        cookies_json=cookies_json,
                        is_active=True,
                        status="idle",
                    )
                    db.add(account)
                    await db.commit()
                    await db.refresh(account)
                    
                    # 创建客户端
                    await self._create_client(account)
                    
                    # 尝试初始化会话
                    client = self._clients[account.id]
                    init_result = await client.initialize_session()
                    if init_result.get("success"):
                        await self.update_account_tokens(account.id, client)
                    
                    return {"success": True, "message": f"账户 {email} 已添加", "id": account.id}
                    
        except json.JSONDecodeError:
            return {"success": False, "error": "Cookie JSON 格式无效"}
        except Exception as e:
            logger.error(f"添加账户失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def remove_account(self, account_id: int) -> dict:
        """删除账户"""
        try:
            # 关闭客户端
            if account_id in self._clients:
                await self._clients[account_id].close()
                del self._clients[account_id]
            
            async with async_session() as db:
                account = await db.get(GoogleAccount, account_id)
                if account:
                    await db.delete(account)
                    await db.commit()
                    return {"success": True, "message": f"账户 {account.email} 已删除"}
                else:
                    return {"success": False, "error": "账户不存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def toggle_account(self, account_id: int, active: bool) -> dict:
        """启用/禁用账户"""
        try:
            async with async_session() as db:
                account = await db.get(GoogleAccount, account_id)
                if account:
                    account.is_active = active
                    account.status = "idle" if active else "disabled"
                    await db.commit()
                    
                    if active and account_id not in self._clients:
                        await self._create_client(account)
                    elif not active and account_id in self._clients:
                        await self._clients[account_id].close()
                        del self._clients[account_id]
                    
                    return {"success": True, "message": f"账户已{'启用' if active else '禁用'}"}
                else:
                    return {"success": False, "error": "账户不存在"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_all_accounts(self) -> List[dict]:
        """获取所有账户信息"""
        async with async_session() as db:
            result = await db.execute(
                select(GoogleAccount).order_by(GoogleAccount.id)
            )
            accounts = result.scalars().all()
            
            return [
                {
                    "id": a.id,
                    "email": a.email,
                    "display_name": a.display_name,
                    "is_active": a.is_active,
                    "status": a.status,
                    "error_message": a.error_message,
                    "total_requests": a.total_requests,
                    "success_requests": a.success_requests,
                    "fail_requests": a.fail_requests,
                    "last_used_at": a.last_used_at.isoformat() if a.last_used_at else None,
                    "last_cookie_rotate_at": a.last_cookie_rotate_at.isoformat() if a.last_cookie_rotate_at else None,
                    "cookie_rotate_count": a.cookie_rotate_count,
                    "priority": a.priority,
                    "weight": a.weight,
                    "has_mstk": bool(a.mstk),
                    "has_cookies": bool(a.cookies_json and len(a.cookies_json) > 10),
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in accounts
            ]
    
    async def get_stats(self) -> dict:
        """获取整体统计信息"""
        async with async_session() as db:
            # 账户统计
            total_accounts = await db.scalar(select(func.count(GoogleAccount.id)))
            active_accounts = await db.scalar(
                select(func.count(GoogleAccount.id)).where(GoogleAccount.is_active == True)
            )
            error_accounts = await db.scalar(
                select(func.count(GoogleAccount.id)).where(GoogleAccount.status == "error")
            )
            
            # 请求统计
            total_requests = await db.scalar(select(func.count(RequestLog.id))) or 0
            success_requests = await db.scalar(
                select(func.count(RequestLog.id)).where(RequestLog.status == "success")
            ) or 0
            
            # 今日请求
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_requests = await db.scalar(
                select(func.count(RequestLog.id)).where(RequestLog.created_at >= today)
            ) or 0
            
            # 平均耗时
            avg_duration = await db.scalar(
                select(func.avg(RequestLog.duration_ms)).where(
                    RequestLog.status == "success",
                    RequestLog.created_at >= today
                )
            ) or 0
        
        return {
            "accounts": {
                "total": total_accounts,
                "active": active_accounts,
                "error": error_accounts,
                "clients_cached": len(self._clients),
            },
            "requests": {
                "total": total_requests,
                "success": success_requests,
                "today": today_requests,
                "avg_duration_ms": round(avg_duration, 2),
            },
            "rotation_strategy": settings.ACCOUNT_ROTATION_STRATEGY,
            "cookie_rotate_interval": settings.COOKIE_ROTATE_INTERVAL,
        }
    
    async def reinit_account(self, account_id: int) -> dict:
        """重新初始化账户会话"""
        if account_id not in self._clients:
            async with async_session() as db:
                account = await db.get(GoogleAccount, account_id)
                if not account:
                    return {"success": False, "error": "账户不存在"}
                await self._create_client(account)
        
        client = self._clients[account_id]
        result = await client.initialize_session()
        
        if result.get("success"):
            await self.update_account_tokens(account_id, client)
            
            # 更新状态
            async with async_session() as db:
                account = await db.get(GoogleAccount, account_id)
                if account:
                    account.status = "idle"
                    account.error_message = ""
                    await db.commit()
            
            return {"success": True, "message": "会话重新初始化成功", "tokens": result.get("tokens", {})}
        else:
            return {"success": False, "error": result.get("error", "初始化失败")}


# 全局单例
account_manager = AccountManager()
