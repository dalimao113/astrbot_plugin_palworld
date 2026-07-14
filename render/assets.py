"""游戏图标解析器(Asset Manifest 解析)——**真实游戏语义图标为三主题共享素材层**。

业务层传**语义键**(如 `element.fire` / `work.mining` / `currency.gold` / `server.online`):
- **游戏有原图**(属性/工作/货币/状态/稀有度/头目闪光突变浓缩等):`game_icon()` / `img()` 对
  **fantasy / pixel / ingame 三套主题都返回同一张真实游戏图标**(共享,图标文件只一份)。
- **游戏无原图**(server/plugin/docker/cpu 等插件扩展概念):ingame 用中性线性 SVG;
  fantasy/pixel 返回空串,由模板回退到各自 Emoji/像素图标。
- 键未知 / 素材文件缺失:ingame 回退统一缺失占位;fantasy/pixel 返回空串(模板回退 Emoji)。**绝不抛异常**。

主题只决定**展示方式**(奇幻光晕 / 像素边框 / 游戏槽位),不决定图标**来源**。
UI 组件纹理(游戏窗口/切角面板/物品槽边框,`component_uris()`)仍只供 ingame,与语义图标区分。

数据来源:`data/ingame/manifest.json` + `data/ingame/icons/*.png`。manifest 资产字段兼容 `game`(新)/`ingame`(旧)。

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

    @staticmethod
    def _asset_rel(entry: dict) -> str:
        """entry 里的真实游戏图标相对路径。兼容新字段 `game` 与旧字段 `ingame`。"""
        return entry.get("game") or entry.get("ingame") or ""

    def game_icon(self, key: str) -> str:
        """**真实游戏图标 data URI,三主题共享**。无游戏原图 / 素材文件缺失 → 空串。
        plugin_svg(游戏无此概念)不算游戏图标,这里不返回。"""
        e = self.entry(key)
        if not e:
            return ""
        rel = self._asset_rel(e)
        if not rel:
            return ""
        uri = self._uri(rel)
        return "" if uri == _MISSING_SVG else uri   # 文件缺失 → 空,交主题回退 Emoji

    def img(self, key: str, style: str = "ingame") -> str:
        """语义键 → 展示图标 data URI。
        - 游戏有原图:**三主题都返回真实游戏图标**(共享素材层)。
        - 游戏无原图:ingame 用插件扩展 SVG,再缺失→统一占位;fantasy/pixel 返回空串(模板回退 Emoji)。"""
        g = self.game_icon(key)
        if g:
            return g                             # 三主题共享
        if style == "ingame":
            e = self.entry(key)
            svg = e.get("plugin_svg") if e else None
            return self._svg_uri(svg) if svg else _MISSING_SVG
        return ""                                # fantasy/pixel:无游戏原图 → 空,模板用 text(Emoji)

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
            rel = self._asset_rel(v)
            out[name] = self._uri(rel) if rel else _MISSING_SVG
        self._uri_cache["__components__"] = out  # type: ignore[assignment]
        return out

    def game_icon_map(self, style: str = "ingame") -> dict:
        """**三主题共享**的语义图标映射(中文键 → data uri):{element, work, stat, passive_rank, pal, currency}
        + server(plugin-ext)。业务数据里属性/工种是中文,按 manifest(元素别名)+ constants(工种中文)解析。
        - 游戏有原图的语义(属性/工作/货币/状态/稀有度/头目闪光突变浓缩):三主题都取到真实游戏图标。
        - server/plugin 概念(游戏无):仅 ingame 取到中性 SVG,fantasy/pixel 为空串(模板回退 Emoji)。
        按 style 缓存。"""
        ck = f"__iconmap__::{style}"
        cached = self._uri_cache.get(ck)
        if cached is not None:
            return cached  # type: ignore[return-value]
        self._ensure_loaded()
        m = self._manifest or {}
        el_keys = (m.get("element", {}).get("_plugin_key_map") or {}).keys()  # 中文属性名
        el = {cn: self.img(f"element.{cn}", style) for cn in el_keys}
        try:
            from ..constants import WORK_LABELS  # snake -> 中文工种
            wk = {cn: self.img(f"work.{snake}", style) for snake, cn in WORK_LABELS.items()}
        except Exception:  # noqa: BLE001  constants 不可用(独立单测)时降级空表
            wk = {}
        stat = {k: self.img(f"stat.{k}", style) for k in ("hp", "attack", "defense", "weight", "hunger",
                                                          "san", "work_speed", "stamina", "speed")}
        rank = {k: self.img(f"passive_rank.{k}", style)
                for k in ("rank_down", "rank_up1", "rank_up2", "rank_up3", "rank_up3_plus", "rank_up5")}
        # server/plugin 概念(游戏无)→ ingame 用插件扩展 SVG;fantasy/pixel 空串
        server = {k: self.img(f"server.{k}", style)
                  for k in ("online", "offline", "player_count", "fps", "uptime",
                            "world_day", "load", "cpu", "memory")}
        pal = {k: self.img(f"pal.{k}", style)
               for k in ("lucky", "alpha", "mutation", "condensation", "awakening",
                         "gender_male", "gender_female", "rarity")}
        cur = {k: self.img(f"currency.{k}", style)
               for k in ("gold", "tech_point", "ancient_tech_point", "dog_coin", "bounty")}
        out = {"element": el, "work": wk, "stat": stat, "passive_rank": rank,
               "server": server, "pal": pal, "currency": cur}
        self._uri_cache[ck] = out  # type: ignore[assignment]
        return out

    def ingame_icon_map(self) -> dict:
        """向后兼容别名 → game_icon_map('ingame')。新代码用 game_icon_map(style)。"""
        return self.game_icon_map("ingame")
