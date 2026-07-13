"""ingame 主题图标解析器(Asset Manifest 解析)。

业务层传**语义键**(如 `element.fire` / `work.mining` / `server.online`),按当前皮肤解析:
- `ingame`  → 真实游戏图标 base64 data URI;缺失(pending/plugin-ext)时回退**统一缺失占位**,绝不抛异常。
- `fantasy` / `pixel` → 原 Emoji/文字(manifest 的 `fallback`),视觉与现状完全一致。

数据来源:`data/ingame/manifest.json` + `data/ingame/icons/*.png`(见该目录 README / tools/game_data)。

设计约束:
- **本模块不依赖 astrbot**,可独立单测(stub 无关)。
- 图标 base64 惰性加载 + 缓存;manifest 惰性加载 + 缓存。
- 同时支持「资产键」(element.fire)与「插件内部键」(element.火 / work.emit_flame),
  后者经 manifest 各命名空间的 `_plugin_key_map` 归一。
"""
from __future__ import annotations

import base64
import json
import os
import threading
from typing import Optional

# 统一「缺失图标」:中性圆角方块 + 问号,明确非游戏原图。ingame 素材缺失时用它,不报错、不塞 Emoji。
_MISSING_SVG = (
    "data:image/svg+xml;utf8,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40'%3E"
    "%3Crect x='3' y='3' width='34' height='34' rx='8' fill='none' "
    "stroke='%23808499' stroke-width='2' stroke-dasharray='4 3'/%3E"
    "%3Ctext x='20' y='26' font-size='18' text-anchor='middle' fill='%23808499'%3E?%3C/text%3E%3C/svg%3E"
)


class AssetResolver:
    """按语义键 + 皮肤解析图标。一个 base_dir(插件根目录)一个实例。"""

    # 插件扩展 SVG 的临时描边色(游戏无此概念,配色待截图校准前用中性暖线)。
    # <img> 无法继承 currentColor,故内嵌时替换成具体色。
    PLUGIN_INK = "#d8c9a0"

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.ingame_dir = os.path.join(base_dir, "data", "ingame")
        self._lock = threading.Lock()
        self._manifest: Optional[dict] = None
        self._flat: dict[str, dict] = {}      # 归一后的 资产键/别名键 -> entry
        self._uri_cache: dict[str, str] = {}  # ingame 相对路径 -> data uri

    # ---- manifest ----
    def _ensure_loaded(self) -> None:
        if self._manifest is not None:
            return
        with self._lock:
            if self._manifest is not None:
                return
            path = os.path.join(self.ingame_dir, "manifest.json")
            try:
                with open(path, encoding="utf-8") as f:
                    m = json.load(f)
            except Exception:  # noqa: BLE001  缺 manifest 不致命,全部回退
                m = {}
            flat: dict[str, dict] = {}
            for ns, entries in m.items():
                if ns.startswith("_") or not isinstance(entries, dict):
                    continue
                pkmap = entries.get("_plugin_key_map") or {}
                for k, v in entries.items():
                    if k.startswith("_") or not isinstance(v, dict):
                        continue
                    # plugin_ext 的子键本身即带点(server.online);其余拼成 ns.sub
                    full = k if ns == "plugin_ext" else f"{ns}.{k}"
                    flat[full] = v
                # 插件内部键别名:element.火 -> element.neutral 的 entry
                for plug_key, asset_sub in pkmap.items():
                    target = entries.get(asset_sub)
                    if isinstance(target, dict):
                        flat[f"{ns}.{plug_key}"] = target
            self._flat = flat
            self._manifest = m

    def entry(self, key: str) -> Optional[dict]:
        self._ensure_loaded()
        return self._flat.get(key)

    # ---- 取图 / 取文字 ----
    def _uri(self, rel: str) -> str:
        """ingame 相对路径(相对 data/ingame)-> base64 png data uri;失败返回缺失占位。"""
        cached = self._uri_cache.get(rel)
        if cached is not None:
            return cached
        path = os.path.join(self.ingame_dir, rel)
        try:
            with open(path, "rb") as f:
                uri = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
        except Exception:  # noqa: BLE001
            uri = _MISSING_SVG
        self._uri_cache[rel] = uri
        return uri

    def _svg_uri(self, rel: str) -> str:
        """插件扩展 SVG(rel 无扩展名,如 svg/cpu)-> data URI;失败→缺失占位。"""
        cache_key = "svg::" + rel
        cached = self._uri_cache.get(cache_key)
        if cached is not None:
            return cached
        path = os.path.join(self.ingame_dir, rel + ".svg")
        try:
            with open(path, encoding="utf-8") as f:
                svg = f.read().replace("currentColor", self.PLUGIN_INK)
            uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
        except Exception:  # noqa: BLE001
            uri = _MISSING_SVG
        self._uri_cache[cache_key] = uri
        return uri

    def img(self, key: str, style: str = "ingame") -> str:
        """ingame 皮肤:图标 data URI(游戏图标优先,其次插件扩展 SVG,再缺失→统一占位)。
        fantasy/pixel:返回空串(用 text)。"""
        if style != "ingame":
            return ""
        e = self.entry(key)
        if not e:
            return _MISSING_SVG
        rel = e.get("ingame")
        if rel:
            return self._uri(rel)
        svg = e.get("plugin_svg")
        if svg:
            return self._svg_uri(svg)
        return _MISSING_SVG

    def text(self, key: str, style: str = "fantasy") -> str:
        """fantasy/pixel 皮肤用:返回 manifest 的 fallback(原 Emoji/文字)。未知键→空串。"""
        e = self.entry(key)
        return (e.get("fallback") or "") if e else ""

    def resolve(self, key: str, style: str) -> dict:
        """统一入口。返回 {'img': data_uri_or_empty, 'text': fallback_or_empty}。
        模板:{% if a.img %}<img src="{{a.img}}">{% else %}{{a.text}}{% endif %}。"""
        return {"img": self.img(key, style), "text": self.text(key, style)}

    @property
    def missing_uri(self) -> str:
        return _MISSING_SVG

    # message 卡的动态 icon(handler 传的 Emoji)-> 插件扩展 SVG 语义键。未列的返回空(ingame 不显示 Emoji)。
    _MSG_MAP = {
        "🔴": "server.offline", "🟢": "server.online", "👥": "server.player_count",
        "🔑": "plugin.admin", "🔒": "plugin.admin", "🔓": "plugin.admin", "🚫": "plugin.admin",
        "✅": "plugin.success", "❌": "plugin.error", "⚠️": "plugin.error", "⚠": "plugin.error",
        "🔍": "plugin.search", "✏️": "plugin.edit", "✏": "plugin.edit", "🔗": "plugin.link",
        "🔔": "plugin.notify_on", "🔕": "plugin.notify_off", "💾": "plugin.backup", "⏪": "plugin.backup",
        "📋": "plugin.audit", "🔬": "plugin.selfcheck", "🛠️": "plugin.selfcheck", "🛠": "plugin.selfcheck",
        "🛰️": "plugin.selfcheck", "🛰": "plugin.selfcheck",
    }

    def msg_icon(self, emoji: str) -> str:
        """message 卡的 Emoji icon -> 插件扩展 SVG data uri;未映射的返回空串(ingame 不显示 Emoji)。"""
        key = self._MSG_MAP.get((emoji or "").strip())
        return self.img(key, "ingame") if key else ""

    def component_uris(self) -> dict[str, str]:
        """ingame 通用组件纹理 {名字: data uri},供模板 CSS 的 {{ parts.* }} 注入。
        走 manifest 的 component 命名空间,不硬编码路径。结果缓存。"""
        cached = self._uri_cache.get("__components__")
        if cached is not None:
            return cached  # type: ignore[return-value]
        self._ensure_loaded()
        comp = (self._manifest or {}).get("component", {})
        out: dict[str, str] = {}
        for name, v in comp.items():
            if name.startswith("_") or not isinstance(v, dict):
                continue
            rel = v.get("ingame")
            out[name] = self._uri(rel) if rel else _MISSING_SVG
        self._uri_cache["__components__"] = out  # type: ignore[assignment]
        return out

    def ingame_icon_map(self) -> dict:
        """给 ingame 模板用的中文键图标映射:{element:{中文:uri}, work:{中文标签:uri}, stat:{键:uri}}。
        业务数据里属性/工种是中文,这里按 manifest(元素别名)+ constants(工种中文)解析成图标。缓存。"""
        cached = self._uri_cache.get("__iconmap__")
        if cached is not None:
            return cached  # type: ignore[return-value]
        self._ensure_loaded()
        m = self._manifest or {}
        el_keys = (m.get("element", {}).get("_plugin_key_map") or {}).keys()  # 中文属性名
        el = {cn: self.img(f"element.{cn}", "ingame") for cn in el_keys}
        try:
            from ..constants import WORK_LABELS  # snake -> 中文工种
            wk = {cn: self.img(f"work.{snake}", "ingame") for snake, cn in WORK_LABELS.items()}
        except Exception:  # noqa: BLE001  constants 不可用(独立单测)时降级空表
            wk = {}
        stat = {k: self.img(f"stat.{k}", "ingame") for k in ("hp", "defense", "weight", "hunger")}
        rank = {k: self.img(f"passive_rank.{k}", "ingame")
                for k in ("rank_down", "rank_up1", "rank_up2", "rank_up3", "rank_up3_plus")}
        # server/plugin 概念(游戏无)→ 插件扩展 SVG
        server = {k: self.img(f"server.{k}", "ingame")
                  for k in ("online", "offline", "player_count", "fps", "uptime",
                            "world_day", "load", "cpu", "memory")}
        pal = {k: self.img(f"pal.{k}", "ingame") for k in ("lucky", "alpha", "mutation", "condensation")}
        cur = {k: self.img(f"currency.{k}", "ingame")
               for k in ("gold", "tech_point", "ancient_tech_point", "dog_coin", "bounty")}
        out = {"element": el, "work": wk, "stat": stat, "passive_rank": rank,
               "server": server, "pal": pal, "currency": cur}
        self._uri_cache["__iconmap__"] = out  # type: ignore[assignment]
        return out
