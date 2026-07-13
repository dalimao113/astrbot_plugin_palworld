"""卡片渲染引擎：Jinja 编译缓存 + 本地 Playwright 渲染 + 远程 html_render 兜底。

职责边界（重构第一阶段）：
- 模板/CSS 字符串在 render/templates.py（任务二已拆）。
- 本模块只做“把模板+数据渲染成图片(url 或本地 PNG)”的引擎，含浏览器生命周期与缓存。
- 皮肤选择(_t)、背景图(_bg_for)、主题色(_theme)、以及 _img/_msg_card 等业务组装仍在
  plugin（依赖 event/皮肤配置），本引擎经 plugin 引用取 theme/bg/config/html_render。

⚠️ 安全：Jinja autoescape **故意关闭**（模板内含大量刻意内嵌的 HTML）。因此所有玩家可控
字段（昵称/公会名/喊话等）必须由调用方在放进 data 前用 utils.text._esc 转义，本引擎不做
自动转义——否则会引入 XSS(在渲染宿主机执行脚本)。逻辑与原 main.py 渲染方法完全一致。
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime
from typing import Optional

# ingame:标题类字段(handler 动态传入)开头的 Emoji 前缀,用于剥离(仅去开头,保留中间的玩家内容)
_LEAD_EMOJI = re.compile(
    r"^(?:\s|[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    r"\U0001F1E6-\U0001F1FF\U0000FE00-\U0000FE0F\U00002190-\U000021FF\U00002300-\U000023FF])+"
)


def _strip_lead_emoji(s):
    return _LEAD_EMOJI.sub("", s) if isinstance(s, str) else s

from astrbot.api import logger

from ..constants import CARD_WIDTH, LOG_PREFIX, RENDER_OPTIONS, SUPERSCALE


class Renderer:
    def __init__(self, plugin):
        self.plugin = plugin
        self._jinja_env = None
        self._jinja_cache: dict = {}
        self._browser = None
        self._browser_failed = False
        self._browser_lock = None
        self._pw_ctx = None

    def jinja(self, tmpl: str):
        if self._jinja_env is None:
            from jinja2 import Environment
            self._jinja_env = Environment(autoescape=False)
        t = self._jinja_cache.get(tmpl)
        if t is None:
            t = self._jinja_cache[tmpl] = self._jinja_env.from_string(tmpl)
        return t

    async def get_browser(self):
        """懒启动并复用一个 Chromium 实例(整个插件生命周期共用)。失败返回 None。
        加锁避免并发首次请求重复启动多个浏览器(泄漏)。"""
        if self._browser is not None:
            return self._browser
        if self._browser_failed:
            return None
        if self._browser_lock is None:
            self._browser_lock = asyncio.Lock()
        async with self._browser_lock:
            # 二次检查：等锁期间可能已被别的协程启动好
            if self._browser is not None:
                return self._browser
            if self._browser_failed:
                return None
            try:
                from playwright.async_api import async_playwright
                self._pw_ctx = await async_playwright().start()
                self._browser = await self._pw_ctx.chromium.launch(
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
                logger.info(f"{LOG_PREFIX} 本地 Playwright 渲染器已启动")
                return self._browser
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 本地渲染器启动失败，回退远程渲染: {e}")
                self._browser_failed = True
                return None

    async def render_local(self, tmpl: str, data: dict, width: int, dsf: float = 1.5) -> Optional[str]:
        """本地 Playwright 渲染 -> 临时 PNG 路径。"""
        browser = await self.get_browser()
        if browser is None:
            return None
        import tempfile
        import uuid as _uuid
        html = self.jinja(tmpl).render(**data)
        # zoom:2(CSS)已 2× 超采样，dsf 再 ×N → 总清晰度；地图用更高 dsf 出高清原图
        page = await browser.new_page(viewport={"width": width * SUPERSCALE, "height": 900},
                                      device_scale_factor=dsf)
        try:
            await page.set_content(html, wait_until="load")
            await page.wait_for_timeout(60)
            # 截 .page 元素而非 full_page：full_page 截的是 html(默认填满视口高 900)，
            # 内容比视口短时会在底部补一大片空白。截元素正好是内容高度。
            el = await page.query_selector(".page")
            if el is not None:
                png = await el.screenshot(type="png")
            else:
                png = await page.screenshot(type="png", full_page=True)
        finally:
            await page.close()
        tdir = tempfile.gettempdir()
        import glob as _glob                       # 顺手清掉 2 分钟前的旧卡图，避免堆积
        for old in _glob.glob(os.path.join(tdir, "palcard_*.png")):
            try:
                if time.time() - os.path.getmtime(old) > 120:
                    os.remove(old)
            except OSError:
                pass
        path = os.path.join(tdir, f"palcard_{_uuid.uuid4().hex}.png")
        with open(path, "wb") as f:
            f.write(png)
        return path

    async def render(self, tmpl: str, data: dict, width: int = CARD_WIDTH, dsf: float = 1.5) -> Optional[str]:
        p = self.plugin
        data.setdefault("theme", p._theme())
        data.setdefault("now", datetime.now().strftime("%Y-%m-%d %H:%M"))
        data.setdefault("zoom", SUPERSCALE)
        data.setdefault("cw", width)
        data.setdefault("bg", p._bg_for(tmpl))
        # 游戏语义图标 {{ icons.* }} **三主题共享注入**(fantasy/pixel 也用真实游戏图标)。
        # UI 组件纹理 {{ parts.* }} 与动态 Emoji 清理仍仅 ingame(游戏原生 UI 专属)。
        if getattr(p, "_assets", None) is not None:
            style = p._style()
            data.setdefault("icons", p._assets.game_icon_map(style))
            if style == "ingame":
                data.setdefault("parts", p._assets.component_uris())
                # 动态 Emoji 清理:标题类字段去开头 Emoji;message 卡的 Emoji icon -> 插件 SVG(未映射则不显示)
                for _k in ("title", "rank_title", "head"):
                    if isinstance(data.get(_k), str):
                        data[_k] = _strip_lead_emoji(data[_k])
                _ic = data.get("icon")
                if isinstance(_ic, str) and _ic and not _ic.startswith(("data:", "http", "/", "file")):
                    data["icon"] = p._assets.msg_icon(_ic)
        if p.config.get("local_render", False):
            try:
                path = await self.render_local(tmpl, data, width, dsf)
                if path:
                    return path
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 本地渲染失败，回退远程: {e}")
        try:
            opts = RENDER_OPTIONS if width == CARD_WIDTH else {**RENDER_OPTIONS, "viewport_width": width * SUPERSCALE}
            return await p.html_render(tmpl, data, options=opts)
        except Exception as e:  # noqa: BLE001
            logger.error(f"{LOG_PREFIX} html_render 渲染失败: {e}")
            return None

    async def close(self):
        """插件卸载时关闭浏览器与 Playwright，避免子进程泄漏。"""
        if self._browser:
            await self._browser.close()
        if self._pw_ctx:
            await self._pw_ctx.stop()
