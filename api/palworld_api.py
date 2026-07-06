"""Palworld 官方 REST API 请求封装（aiohttp + Basic Auth + 统一超时/错误处理）。

只做 HTTP 封装，不做鉴权/业务判断。session 生命周期由 plugin 持有并复用长连接，
本模块函数接收 session / base / auth / timeout 显式依赖，便于独立测试。
逻辑与原 main.py `_api_get`/`_api_post` 完全一致。

安全：admin_password 通过 aiohttp.BasicAuth(auth) 传入，只用于 Authorization 头，
不会写进日志（失败日志只记路径与异常，不含凭据）。
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

import aiohttp

from astrbot.api import logger

from ..constants import LOG_PREFIX


async def api_get(session, base: str, auth, timeout_s: int, path: str) -> Tuple[bool, Any, int]:
    """GET 返回 (ok, json|错误信息, status)。status=0 表示连接/超时失败(真离线)，
    401/403 表示认证失败(密码错)，与离线区分开。"""
    url = base + path
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with session.get(url, auth=auth, timeout=timeout) as resp:
            if resp.status == 200:
                return True, await resp.json(content_type=None), 200
            return False, f"HTTP {resp.status}", resp.status
    except Exception as e:  # noqa: BLE001
        logger.warning(f"{LOG_PREFIX} GET {path} 失败: {e}")
        return False, str(e), 0


async def api_post(session, base: str, auth, timeout_s: int, path: str,
                   payload: Optional[dict] = None) -> Tuple[bool, str]:
    """POST 返回 (ok, 错误信息)。2xx 视为成功。"""
    url = base + path
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with session.post(
            url, json=(payload or {}), auth=auth, timeout=timeout
        ) as resp:
            if 200 <= resp.status < 300:
                return True, ""
            body = await resp.text()
            return False, f"HTTP {resp.status} {body[:80]}"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"{LOG_PREFIX} POST {path} 失败: {e}")
        return False, str(e)
