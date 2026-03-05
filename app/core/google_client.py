"""
Google AI Mode 客户端
负责与 Google AI Mode 接口通信，发送查询并解析响应
"""
import json
import re
import time
import hashlib
import uuid
import urllib.parse
from typing import Optional, AsyncGenerator, Dict, Any
from datetime import datetime

import httpx
from loguru import logger
from bs4 import BeautifulSoup

from app.config import settings


class GoogleAIClient:
    """Google AI Mode 客户端"""

    # 通y请求头 - 进一步模拟真实 Chrome 132
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Chromium";v="132", "Google Chrome";v="132", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    }

    FOLIF_HEADERS = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Sec-Ch-Ua": '"Chromium";v="132", "Google Chrome";v="132", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
    }

    def __init__(self, cookies_dict: dict = None, mstk: str = "", stkp: str = "",
                 elrc: str = "", sca_esv: str = "", xsrf_token: str = "",
                 at_token: str = "", proxy: Optional[str] = None,
                 anonymous: bool = False):
        self.cookies = cookies_dict or {}
        self.mstk = mstk
        self.stkp = stkp
        self.elrc = elrc
        self.sca_esv = sca_esv
        self.xsrf_token = xsrf_token
        self.at_token = at_token
        self.proxy = proxy or settings.HTTP_PROXY
        self.ei = ""
        self.anonymous = anonymous
        
        transport = None
        if self.proxy:
            transport = httpx.AsyncHTTPTransport(proxy=self.proxy)
        
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
            follow_redirects=True,
            transport=transport,
            http2=True,
        )

    async def close(self):
        await self.http_client.aclose()

    def _generate_ei(self) -> str:
        if hasattr(self, "ei") and self.ei:
            return self.ei
        import base64
        import random
        raw = bytes([random.getrandbits(8) for _ in range(16)])
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def _generate_ved(self) -> str:
        import random
        return f"1t:{random.randint(100000, 999999)}"

    def _build_cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def _generate_sapisidhash(self, origin: str = "https://www.google.com") -> str:
        sapisid = self.cookies.get("SAPISID", "")
        if not sapisid:
            sapisid = self.cookies.get("__Secure-1PAPISID", "")
        if not sapisid:
            return ""
        
        timestamp = str(int(time.time()))
        hash_input = f"{timestamp} {sapisid} {origin}"
        hash_value = hashlib.sha1(hash_input.encode()).hexdigest()
        return f"{timestamp}_{hash_value}"

    async def initialize_session(self) -> dict:
        """初始化 AI Mode 会话"""
        logger.info("正在模拟浏览器环境初始化 AI Mode 会话...")
        
        # 严格按照文档 v2.3 对齐参数
        params = {
            "udm": "50",
            "aep": "22",      # 核心：AI 模式专属标记
            "source": "hp",
            "hl": "zh-CN",    # 匹配用户截图语言
            "gl": "CN",       # 匹配地区
        }
        
        headers = dict(self.DEFAULT_HEADERS)
        headers["Cookie"] = self._build_cookie_header()
        
        try:
            resp = await self.http_client.get(
                f"{settings.GOOGLE_SEARCH_URL}/search",
                params=params,
                headers=headers,
            )
            
            if resp.status_code != 200:
                logger.error(f"初始化会话失败, HTTP {resp.status_code}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
            
            self._update_cookies_from_response(resp)
            html = resp.text
            tokens = self._extract_tokens_from_html(html)
            
            # 更新内部状态
            for key in ["mstk", "stkp", "sca_esv", "xsrf_token", "at_token", "ei"]:
                if tokens.get(key):
                    setattr(self, key, tokens[key])
            
            # 自动补全关键的 at_token (SNlM0e)
            if not self.at_token:
                sn_match = re.search(r'"SNlM0e":"([^"]+)"', html)
                if sn_match:
                    self.at_token = sn_match.group(1)
            
            logger.info(f"会话初始化完成, mstk={'已获取' if self.mstk else '未获取'}, SNlM0e={'已获取' if self.at_token else '未获取'}")
            return {"success": True, "tokens": tokens}
            
        except Exception as e:
            logger.error(f"初始化会话异常: {e}")
            return {"success": False, "error": str(e)}

    def _extract_tokens_from_html(self, html: str) -> dict:
        """从页面 HTML 中深度提取所有必要令牌"""
        tokens = {}
        
        # 1. 提取 mstk (核心鉴权)
        # data-mstk 属性出现在 folif 响应中，需优先匹配
        mstk_patterns = [
            r'data-mstk="([^"]+)"',        # folif 响应 HTML 属性（已验证）
            r'"mstk":"([^"]+)"',
            r"'mstk':'([^']+)'",
            r'mstk=([A-Za-z0-9_\-]+)',
            r'(AUtEx[A-Za-z0-9_\-\.]+)', # 兜底
        ]
        for pattern in mstk_patterns:
            match = re.search(pattern, html)
            if match:
                tokens["mstk"] = match.group(1)
                logger.debug(f"mstk 已提取，匹配模式: {pattern[:25]}")
                break
        
        if not tokens.get("mstk"):
            if "Sign in" in html or "登录" in html:
                logger.warning("检测到 Google 登录页面：Cookie 未生效，请在管理后台重新粘贴全量 Cookie")
            elif "consent.google.com" in html:
                logger.warning("检测到隐私确认页：请在浏览器中完成 Google 隐私协议确认")
        
        # 2. 提取 stkp, sca_esv, ei
        patterns = {
            "stkp": r'"stkp":"([^"]+)"',
            "sca_esv": r'"sca_esv":"([^"]+)"',
            "ei": r'"ei":"([^"]+)"',
            "xsrf_token": r'"xsrf":"([^"]+)"',
            "at_token": r'"SNlM0e":"([^"]+)"',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, html)
            if match:
                tokens[key] = match.group(1)
        
        return tokens

    async def chat(self, query: str, conversation_id: str = "") -> dict:
        """发送 AI 对话请求（非流式）"""
        logger.info(f"发送查询: {query[:50]}...")
        
        if not self.ei:
            await self.initialize_session()
        
        params = {
            "ei": self.ei or self._generate_ei(),
            "yv": "3",
            "aep": "22",
            "source": "hp",
            "udm": "50",
            "cs": "0",
            "csuir": "0",
            "q": query,
            "ved": self._generate_ved(),
        }
        
        if self.sca_esv: params["sca_esv"] = self.sca_esv
        if self.stkp: params["stkp"] = self.stkp
        if self.elrc: params["elrc"] = self.elrc
        if self.mstk: params["mstk"] = self.mstk
        
        params["async"] = f"_fmt:adl"
        
        headers = dict(self.FOLIF_HEADERS)
        headers["Cookie"] = self._build_cookie_header()
        headers["Referer"] = f"{settings.GOOGLE_SEARCH_URL}/search?udm=50&q={urllib.parse.quote(query)}&aep=22"
        
        try:
            resp = await self.http_client.get(
                f"{settings.GOOGLE_SEARCH_URL}/async/folif",
                params=params,
                headers=headers,
            )
            
            if resp.status_code != 200:
                error_body = resp.text[:500]
                logger.error(f"AI 查询失败, HTTP {resp.status_code}, 详情: {error_body}")
                return {"success": False, "text": "", "error": f"HTTP {resp.status_code}"}
            
            self._update_cookies_from_response(resp)
            response_html = resp.text
            result = self._parse_ai_response(response_html)
            
            new_elrc = self._extract_elrc_from_response(response_html)
            if new_elrc:
                self.elrc = new_elrc
                result["elrc"] = new_elrc
            
            return result
        except Exception as e:
            logger.error(f"查询异常: {e}")
            return {"success": False, "text": "", "error": str(e)}

    async def chat_stream(self, query: str, conversation_id: str = "") -> AsyncGenerator[str, None]:
        """流式 AI 对话"""
        logger.info(f"流式查询: {query[:50]}...")
        
        if not self.ei:
            await self.initialize_session()
        
        params = {
            "ei": self.ei or self._generate_ei(),
            "yv": "3",
            "aep": "22",
            "source": "hp",
            "udm": "50",
            "cs": "0",
            "csuir": "0",
            "q": query,
            "ved": self._generate_ved(),
        }
        
        if self.sca_esv: params["sca_esv"] = self.sca_esv
        if self.stkp: params["stkp"] = self.stkp
        if self.elrc: params["elrc"] = self.elrc
        if self.mstk: params["mstk"] = self.mstk
        
        params["async"] = "_fmt:adl"
        
        headers = dict(self.FOLIF_HEADERS)
        headers["Cookie"] = self._build_cookie_header()
        headers["Referer"] = f"{settings.GOOGLE_SEARCH_URL}/search?udm=50&q={urllib.parse.quote(query)}&aep=22"
        
        try:
            async with self.http_client.stream(
                "GET",
                f"{settings.GOOGLE_SEARCH_URL}/async/folif",
                params=params,
                headers=headers,
            ) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    logger.error(f"流式失败, HTTP {resp.status_code}, 详情: {error_body.decode('utf-8', 'ignore')[:500]}")
                    yield f"[ERROR] HTTP {resp.status_code}"
                    return
                
                self._update_cookies_from_response(resp)
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    extracted, buffer = self._extract_streaming_text(buffer)
                    if extracted:
                        yield extracted
                
                if buffer:
                    result = self._parse_ai_response(buffer)
                    if result.get("text"):
                        yield result["text"]
                    new_elrc = self._extract_elrc_from_response(buffer)
                    if new_elrc: self.elrc = new_elrc
                        
        except Exception as e:
            logger.error(f"流式异常: {e}")
            yield f"[ERROR] {str(e)}"

    def _parse_ai_response(self, html: str) -> dict:
        """解析 folif 返回的 HTML 响应，提取 AI 文本并更新 mstk"""
        try:
            soup = BeautifulSoup(html, "lxml")
            text_parts = []

            # 顺手从每次 folif 响应里更新 mstk（存在 data-mstk 属性中）
            mstk_tag = soup.find(attrs={"data-mstk": True})
            if mstk_tag:
                new_mstk = mstk_tag.get("data-mstk", "")
                if new_mstk:
                    self.mstk = new_mstk
                    logger.info("从 folif 响应中成功更新 mstk")

            # 移除干扰标签
            for tag in soup.find_all(['script', 'style', 'noscript']):
                tag.decompose()

            # 提取段落文本（Y3BBE 是当前 Google AI Mode 段落容器，已验证）
            for container in soup.find_all(class_='Y3BBE'):
                for noise in container.find_all(class_=['txxDge', 'rBl3me', 'vKEkVd']):
                    noise.decompose()
                text = container.get_text(separator='', strip=True)
                if text and len(text) > 1:
                    text_parts.append(text)

            # 提取列表内容（U6u95 是 AI 回复列表，已验证）
            for ul in soup.find_all('ul', class_='U6u95'):
                for li in ul.find_all('li', recursive=False):
                    for noise in li.find_all(class_=['txxDge', 'rBl3me', 'vKEkVd']):
                        noise.decompose()
                    text = li.get_text(separator='', strip=True)
                    if text and len(text) > 1:
                        text_parts.append(f"• {text}")

            if text_parts:
                final_text = "\n\n".join(text_parts)
                return {"success": True, "text": self._clean_response_text(final_text), "error": ""}
            else:
                # 调试：打印响应片段，帮助排查 Google 返回了什么
                preview = html[:800].replace("\n", " ").strip()
                logger.warning(f"_parse_ai_response: 未找到 AI 内容，响应预览: {preview}")
                return {"success": False, "text": "", "error": "无法解析AI响应内容"}
        except Exception as e:
            logger.error(f"_parse_ai_response 异常: {e}")
            return {"success": False, "text": "", "error": str(e)}

    def _clean_response_text(self, text: str) -> str:
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'AI\s*回答可能包含错误.*$', '', text, flags=re.DOTALL)
        return text.strip()

    def _extract_streaming_text(self, buffer: str) -> tuple:
        """从流式缓冲区中提取已完整到达的 Y3BBE 段落"""
        match = re.search(r'(<div[^>]*class="[^"]*Y3BBE[^"]*"[^>]*>.*?</div>)', buffer, re.DOTALL)
        if match:
            fragment = match.group(1)
            soup = BeautifulSoup(fragment, "lxml")
            for noise in soup.find_all(class_=['txxDge', 'rBl3me', 'vKEkVd', 'script', 'style']):
                noise.decompose()
            text = soup.get_text(separator="", strip=True)
            if text and len(text) > 1:
                return text, buffer[match.end():]
        return "", buffer

    def _extract_elrc_from_response(self, html: str) -> str:
        patterns = [r'"elrc":"([^"]+)"', r'elrc=([A-Za-z0-9_\-+/=]+)']
        for pattern in patterns:
            match = re.search(pattern, html)
            if match: return match.group(1)
        return ""

    def _update_cookies_from_response(self, resp: httpx.Response):
        for cookie_header in resp.headers.get_list("set-cookie"):
            try:
                parts = cookie_header.split(";")[0]
                if "=" in parts:
                    name, value = parts.split("=", 1)
                    self.cookies[name.strip()] = value.strip()
            except: pass

    async def rotate_cookies(self) -> dict:
        """Cookie 轮换"""
        sid = self.cookies.get("SID", "")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": self._build_cookie_header(),
            "User-Agent": self.DEFAULT_HEADERS["User-Agent"],
        }
        try:
            resp = await self.http_client.post(
                f"{settings.GOOGLE_SEARCH_URL}/RotateCookies",
                content=f'[1,"{sid}"]',
                headers=headers,
            )
            if resp.status_code == 200:
                self._update_cookies_from_response(resp)
                return {"success": True, "ttl": 600}
            return {"success": False}
        except: return {"success": False}

    def get_current_tokens(self) -> dict:
        return {
            "mstk": self.mstk,
            "stkp": self.stkp,
            "elrc": self.elrc,
            "ei": self.ei,
            "sca_esv": self.sca_esv,
            "xsrf_token": self.xsrf_token,
            "at_token": self.at_token,
            "cookies_count": len(self.cookies),
        }

    def get_cookies_dict(self) -> dict:
        """获取当前 Cookie 字典"""
        return dict(self.cookies)
