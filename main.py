"""
AstrBot 帕鲁(Palworld)服务器管家插件

- 群友可查询服务器状态 / 在线玩家 / 服务器设置
- 管理员(白名单 QQ)可发公告 / 踢 / 封 / 解封 / 存档 / 关服
- 所有回复一律输出精美卡片图片(html_render)，不发纯文字
  (仅渲染失败时兜底纯文字错误提示)

对接 thijsvanloef/palworld-server-docker 的官方 REST API。
目标环境：AstrBot 4.25.5

Author: dalimao113
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, Any

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp

# ----------------------------------------------------------------------
# 重构第一阶段：常量 / 模板 / 纯函数已迁出为独立模块（逻辑零变更）。
# 这些名字仍以模块全局形式回到本命名空间，下方业务代码引用方式不变。
# ----------------------------------------------------------------------
from .constants import *  # noqa: F401,F403  (LOG_PREFIX/ELEM_CN/CARD_WIDTH/RENDER_OPTIONS/SETTINGS_FIELDS 等)
from .utils.text import _esc, egg_to_cn  # noqa: F401
from .utils import security as _security
from .render.templates import (  # noqa: F401
    STYLES,
    TEMPLATE_KEYS,
    STYLE_NAMES,
    STYLE_ALIAS,
)
# 命令注册表：子命令→处理器 的单一事实来源，驱动 _dispatch 与 _SUB_ALIASES。
from .commands.router import ALIAS_MAP as COMMAND_ALIAS_MAP, COMMAND_TOKENS
# 配置默认值(规范来源) + 启动合法性校验。
from . import config as _config
# 存档拉取/缓存/负缓存/强制存盘 编排服务（palsave.py 只管纯解析）。
from .services.save_service import SaveService
# REST 请求 + Docker socket 操作封装（含高危操作权限风险注释）。
from .api import palworld_api, docker_api
# 卡片渲染引擎(Jinja 缓存 + Playwright + html_render 兜底)。
from .render.renderer import Renderer


@register(
    "astrbot_plugin_palworld",
    "dalimao113",
    "帕鲁(Palworld)服务器查询与管理插件，所有回复输出精美卡片图片",
    "1.2.2",
    "https://github.com/dalimao113/astrbot_plugin_palworld",
)
class PalworldPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._cooldown: dict[str, float] = {}          # group_id -> 上次查询时间戳
        self._pending: dict[str, dict] = {}            # sender_id -> 待确认操作
        self._shout_cd: dict[str, float] = {}          # qq -> 上次喊话时间(冷却)
        self._call_cd: dict[str, float] = {}           # 目标qq -> 上次被喊时间(冷却)
        self._bg = self._load_bg()                     # 头部背景图(默认+每卡专属)，空则头部回退纯色
        self._load_paldex()                            # 加载图鉴/配种数据(data/*.json)
        # 持久化状态(后台轮询用)：广播群、在线集合、服务器上下线状态等
        self._data_dir = StarTools.get_data_dir("astrbot_plugin_palworld")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_path = self._data_dir / "state.json"
        self.state = self._load_state()
        self._lock = asyncio.Lock()
        self._client = None                            # aiocqhttp 客户端缓存
        self._save = SaveService(self)                 # 存档拉取/缓存/负缓存/强制存盘编排
        self._renderer = Renderer(self)                # 卡片渲染引擎
        self._poll_task = asyncio.create_task(self._poll_loop())  # 后台轮询(上下线播报/掉线告警)
        self._last_save_use = 0.0                       # 上次有人用存档类指令(背包/队伍/我)的时间
        self._prewarm_task = asyncio.create_task(self._prewarm_loop())  # 预热浏览器+存档缓存
        logger.info(f"{LOG_PREFIX} 插件已加载，API={self._api_base()}")
        self._check_config()

    def _check_config(self):
        """启动时校验配置，把问题以清晰中文写进日志（只提示，不阻断加载）。"""
        try:
            issues = _config.validate_config(self.config)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 配置校验异常(忽略): {e}")
            return
        for level, msg in issues:
            (logger.error if level == "错误" else logger.warning)(
                f"{LOG_PREFIX} 配置{level}：{msg}")
        if not issues:
            logger.info(f"{LOG_PREFIX} 配置校验通过")

    # ------------------------------------------------------------------
    # 持久化状态
    # ------------------------------------------------------------------
    def _load_state(self) -> dict:
        try:
            if self._state_path.exists():
                return json.loads(self._state_path.read_text("utf-8"))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 状态文件读取失败，重置: {e}")
        return {"groups": [], "online": {}, "server_up": None, "fail_count": 0, "initialized": False}

    def _save_state(self):
        # 原子写：先写同目录临时文件再 os.replace() 替换，避免写一半崩溃损坏 state.json
        # （损坏会导致加载失败被重置 → 丢绑定/审计）。os.replace 在同一文件系统上是原子的。
        tmp = None
        try:
            data = json.dumps(self.state, ensure_ascii=False, separators=(",", ":"))
            tmp = self._state_path.with_name(f"{self._state_path.name}.tmp.{os.getpid()}")
            tmp.write_text(data, "utf-8")
            os.replace(str(tmp), str(self._state_path))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 状态文件写入失败: {e}")
            if tmp is not None:
                try:
                    tmp.unlink()
                except Exception:  # noqa: BLE001
                    pass

    def _register_group(self, gid: str):
        """自动登记用过指令的群为广播目标。"""
        if gid and gid not in self.state.get("groups", []):
            self.state.setdefault("groups", []).append(gid)
            self._save_state()
            logger.info(f"{LOG_PREFIX} 新登记广播群 {gid}")

    def _load_one_bg(self, stem: str) -> str:
        """按文件名(无扩展名)在插件目录找图并 base64 内嵌；找不到返回空串。"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for ext in ("jpg", "jpeg", "png", "webp"):
            path = os.path.join(base_dir, f"{stem}.{ext}")
            if os.path.exists(path):
                try:
                    with open(path, "rb") as _f:
                        raw = _f.read()
                    mime = {"png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
                    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"{LOG_PREFIX} 背景图 {stem}.{ext} 加载失败: {e}")
        return ""

    def _load_bg(self) -> dict:
        """加载头部背景图：bg.jpg=默认(所有卡)，bg_<卡名>.jpg=该卡专属。
        卡名：status/players/settings/help/stats/rank/profile/message。"""
        result = {"default": self._load_one_bg("bg")}
        loaded = []
        for key in ("status", "players", "settings", "help", "stats", "rank", "profile",
                    "message", "daily", "paldex", "breed", "reverse", "item", "facility", "tech", "grid"):
            uri = self._load_one_bg(f"bg_{key}")
            if uri:
                result[key] = uri
                loaded.append(key)
        logger.info(f"{LOG_PREFIX} 头部背景图：默认={'有' if result['default'] else '无'}，"
                    f"专属={loaded or '无'}")
        return result

    def _bg_for(self, tmpl: str) -> str:
        """按模板取对应专属背景图，没有专属则用默认。"""
        key = TEMPLATE_KEYS.get(tmpl)
        if key and self._bg.get(key):
            return self._bg[key]
        return self._bg.get("default", "")

    # ------------------------------------------------------------------
    # 卡片风格(皮肤)：fantasy 奇幻玻璃 / pixel 像素羊皮纸
    # ------------------------------------------------------------------
    def _style(self) -> str:
        # 卡片风格由 WebUI 配置 card_style 控制(fantasy/pixel)
        st = self.config.get("card_style", "fantasy")
        return st if st in STYLES else "fantasy"

    def _t(self, key: str) -> str:
        """取当前风格下该卡的模板字符串。"""
        return STYLES[self._style()].get(key, STYLES["fantasy"][key])

    # ------------------------------------------------------------------
    # 图鉴 / 配种 数据层（代码与数据分离：只读 data/*.json）
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_idx(s) -> str:
        """归一化图鉴号：去前导0、保留字母变体。'024B'->'24B'，'001'->'1'。"""
        m = re.match(r"0*([0-9]+[A-Za-z]?)", str(s))
        return m.group(1) if m else str(s)

    def _load_paldex(self):
        self._pals: list = []
        self._pal_by_name: dict = {}     # 中文名 -> pal
        self._pal_by_dev: dict = {}      # 存档 char_id(小写) -> pal
        self._pal_idx: dict = {}         # 归一化图鉴号 -> pal
        self._name_idx: dict = {}        # 中文名 -> 归一化图鉴号
        self._breed: dict = {}           # frozenset({亲A号,亲B号}) -> 子代号
        self._breed_rev: dict = {}       # 子代号 -> [(亲A号,亲B号), ...]  (反向配种用)
        self._drop_index: dict = {}      # 物品中文名 -> [{pal,index,dev,rate,min,max}] (掉落反查)
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        try:
            with open(os.path.join(base, "paldex.json"), encoding="utf-8") as _f:
                raw = json.loads(_f.read())
        except Exception as e:  # noqa: BLE001
            logger.error(f"{LOG_PREFIX} 图鉴数据 data/paldex.json 加载失败: {e}")
            return
        for p in raw:
            idx = str(p.get("pal_index", ""))
            nm = p.get("pal_name")
            if not idx or not idx[0].isdigit() or not nm or nm == "zh_Hans_Text":
                continue   # 排除 Boss/人类(-1/-2)与未翻译占位
            ni = self._norm_idx(idx)
            self._pals.append(p)
            self._pal_by_name[nm] = p
            self._pal_idx[ni] = p
            self._name_idx[nm] = ni
            dev = str(p.get("pal_dev_name", "")).lower()
            if dev:
                self._pal_by_dev.setdefault(dev, p)
            for dd in (p.get("item_drops") or []):   # 掉落反查索引：物品 -> 掉它的帕鲁
                inm = dd.get("item_name")
                if inm:
                    self._drop_index.setdefault(inm, []).append({
                        "pal": nm, "index": idx,
                        "dev": p.get("pal_dev_name", ""),   # 原始大小写，_pal_icon 按文件名找图
                        "rate": dd.get("drop_rate", 0),
                        "min": dd.get("min_drop"), "max": dd.get("max_drop")})
        try:
            with open(os.path.join(base, "breeding.json"), encoding="utf-8") as _f:
                bd = json.loads(_f.read())
            for child, pairs in bd.items():
                c = self._norm_idx(child)
                for pa, pb in pairs:
                    a, b = self._norm_idx(pa), self._norm_idx(pb)
                    self._breed[frozenset((a, b))] = c
                    self._breed_rev.setdefault(c, []).append((a, b))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 配种表 data/breeding.json 加载失败: {e}")
        # 物品图鉴数据
        self._items: list = []
        self._item_by_name: dict = {}
        self._item_by_id: dict = {}      # item_id -> item(取中文名/图标)
        try:
            with open(os.path.join(base, "items.json"), encoding="utf-8") as _f:
                idata = json.loads(_f.read())
            for it in idata:
                nm = it.get("name")
                if it.get("item_id"):
                    self._item_by_id.setdefault(it["item_id"], it)
                if nm and nm != "zh_Hans_Text":
                    self._items.append(it)
                    self._item_by_name.setdefault(nm, it)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 物品数据 data/items.json 加载失败: {e}")
        # 设施图鉴数据
        self._buildings: list = []
        self._building_by_name: dict = {}
        try:
            with open(os.path.join(base, "buildings.json"), encoding="utf-8") as _f:
                bdata = json.loads(_f.read())
            for it in bdata:
                nm = it.get("name")
                if nm:
                    self._buildings.append(it)
                    self._building_by_name.setdefault(nm, it)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 设施数据 data/buildings.json 加载失败: {e}")
        # 科技图鉴数据
        self._tech: list = []
        self._tech_by_name: dict = {}
        try:
            with open(os.path.join(base, "tech.json"), encoding="utf-8") as _f:
                tdata = json.loads(_f.read())
            for it in tdata:
                nm = it.get("name")
                if nm:
                    self._tech.append(it)
                    self._tech_by_name.setdefault(nm, it)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 科技数据 data/tech.json 加载失败: {e}")
        # 词条(被动技能) id -> {name,rank,sign,effect}; 主动技能枚举 -> 中文名
        self._passives: dict = {}
        self._wazas: dict = {}
        try:
            with open(os.path.join(base, "passives.json"), encoding="utf-8") as _f:
                self._passives = json.loads(_f.read())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 词条数据 data/passives.json 加载失败: {e}")
        try:
            with open(os.path.join(base, "wazas.json"), encoding="utf-8") as _f:
                self._wazas = json.loads(_f.read())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 技能数据 data/wazas.json 加载失败: {e}")
        # 制作配方 item_id -> {mats, bench}（物品详情显示材料+制作台）
        self._recipes: dict = {}
        try:
            with open(os.path.join(base, "recipes.json"), encoding="utf-8") as _f:
                self._recipes = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 设施建造配方 building_id -> {mats, tech}（设施详情显示建造材料+解锁科技）
        self._build_recipes: dict = {}
        try:
            with open(os.path.join(base, "building_recipes.json"), encoding="utf-8") as _f:
                self._build_recipes = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 帕鲁额外数据 dev_name -> {egg, lv_min, lv_max}（图鉴卡：蛋型/刷新等级）
        self._pal_extra: dict = {}
        try:
            with open(os.path.join(base, "pal_extra.json"), encoding="utf-8") as _f:
                self._pal_extra = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 物品额外数据 item_id -> {gold, cap, rank, weight}（物品卡：售价/帕鲁球捕获力）
        self._item_extra: dict = {}
        try:
            with open(os.path.join(base, "item_extra.json"), encoding="utf-8") as _f:
                self._item_extra = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 属性克制表 元素 -> {strong, weak, color, en}（/帕鲁属性克制）
        self._elements: dict = {}
        try:
            with open(os.path.join(base, "elements.json"), encoding="utf-8") as _f:
                self._elements = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 帕鲁刷新点位(地图百分比) dev_name -> {day:[[l,t]], night, r}（/帕鲁栖息区域）
        self._pal_spawns: dict = {}
        try:
            with open(os.path.join(base, "pal_spawns.json"), encoding="utf-8") as _f:
                self._pal_spawns = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 任务(主线/支线) [{id,name,type,desc,objective,coords,exp,rewards,next,group,order}]（/帕鲁任务）
        self._missions: list = []
        self._mission_by_name: dict = {}
        try:
            with open(os.path.join(base, "missions.json"), encoding="utf-8") as _f:
                self._missions = json.loads(_f.read())
            self._mission_by_name = {m["name"]: m for m in self._missions}
        except Exception:  # noqa: BLE001
            pass
        # boss(塔主/突袭) [{name,category,dev,pal,element,location,difficulty,level,hp,drops}]（/帕鲁塔主 /帕鲁突袭）
        self._bosses: list = []
        try:
            with open(os.path.join(base, "bosses.json"), encoding="utf-8") as _f:
                self._bosses = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 主动技能 [{name,element,power,cooldown,effect,desc,is_fruit}]（/帕鲁技能）
        self._skills: list = []
        self._skill_full: dict = {}
        try:
            with open(os.path.join(base, "skills.json"), encoding="utf-8") as _f:
                self._skills = json.loads(_f.read())
            self._skill_full = {s["name"]: s for s in self._skills}
        except Exception:  # noqa: BLE001
            pass
        # 钓鱼战利品 {spot, catch:[{name,qty,rate}]}（/帕鲁钓鱼）
        self._fishing: dict = {}
        try:
            with open(os.path.join(base, "fishing.json"), encoding="utf-8") as _f:
                self._fishing = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 增益料理 [{name,item_id,effect}]（/帕鲁料理）
        self._cuisine: list = []
        try:
            with open(os.path.join(base, "cuisine.json"), encoding="utf-8") as _f:
                self._cuisine = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 武器 [{name,attack,tech,ammo}]（/帕鲁武器，源 paldb）
        self._weapons: list = []
        try:
            with open(os.path.join(base, "weapons.json"), encoding="utf-8") as _f:
                self._weapons = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 商人 [{id,name,currency,note,items:[{name,item_id,price,stock}]}]（/帕鲁商人 /帕鲁哪里买）
        # 来源:客户端 pak DT_ItemShopCreateData。建 物品名->商店 索引供"哪里买"用。
        self._merchants: list = []
        self._item_shops: dict = {}
        try:
            with open(os.path.join(base, "merchants.json"), encoding="utf-8") as _f:
                self._merchants = json.loads(_f.read())
            for sh in self._merchants:
                for it in sh.get("items", []):
                    self._item_shops.setdefault(it["name"], []).append(
                        {"shop": sh["name"], "currency": sh["currency"], "price": it.get("price"), "stock": it.get("stock")})
        except Exception:  # noqa: BLE001
            pass
        # 竞技场(对手队伍/段位奖励)。来源:paldb /cn/Arena。商店在 merchants.json「竞技场商店」。
        self._arena: dict = {}
        try:
            with open(os.path.join(base, "arena.json"), encoding="utf-8") as _f:
                self._arena = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 技能中文名 -> {power, elem, cd, desc}，聚合自图鉴各帕鲁的 active_skills(队伍卡技能详情用)
        self._skill_by_name: dict = {}
        for p in self._pals:
            for s in (p.get("active_skills") or []):
                nm = s.get("name")
                if nm and nm not in self._skill_by_name:
                    desc = re.sub(r"<[^>]+>", "", s.get("description") or "").replace("\r\n", " ").strip()
                    self._skill_by_name[nm] = {"power": s.get("power") or 0,
                                               "elem": ELEM_CN.get(s.get("element_type"), ""),
                                               "cd": s.get("cool_down_time") or 0, "desc": desc[:34]}
        logger.info(f"{LOG_PREFIX} 图鉴 {len(self._pals)} 只 / 配种 {len(self._breed)} 组合 / "
                    f"物品 {len(self._items)} / 设施 {len(self._buildings)} / 科技 {len(self._tech)} / "
                    f"词条 {len(self._passives)} / 技能 {len(self._wazas)} 已加载")

    def _find_pal(self, q: str):
        q = (q or "").strip()
        if not q:
            return None
        if q in self._pal_by_name:            # 1. 精确名
            return self._pal_by_name[q]
        ni = self._norm_idx(q).upper()        # 2. 图鉴编号(13 / 13B / 13b / 013B 变种都支持)
        if ni and ni in self._pal_idx:
            return self._pal_idx[ni]
        for nm, p in self._pal_by_name.items():   # 3. 包含匹配(模糊)
            if q in nm or nm in q:
                return p
        return None

    def _suggest_pals(self, q: str, n: int = 6) -> list:
        q = (q or "").strip()
        return [nm for nm in self._pal_by_name if q and (q in nm or nm in q)][:n]

    def _pal_icon(self, dev_name: str) -> str:
        """读取 data/images/<dev_name>.png(从游戏解包的透明帕鲁图标) -> base64 data uri。无图返回空。"""
        if not dev_name:
            return ""
        cache = getattr(self, "_icon_cache", None)
        if cache is None:
            cache = self._icon_cache = {}
        if dev_name in cache:
            return cache[dev_name]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images", f"{dev_name}.png")
        if os.path.exists(path):
            try:
                with open(path, "rb") as _f:
                    uri = "data:image/png;base64," + base64.b64encode(_f.read()).decode("ascii")
                cache[dev_name] = uri    # 命中才缓存(未命中不缓存，方便图标后补)
                return uri
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 帕鲁图标 {dev_name} 读取失败: {e}")
        return ""

    def _item_icon(self, item_id: str) -> str:
        """读取 data/images/items/<item_id>.png(游戏物品图标) -> base64 data uri。无图返回空。"""
        if not item_id:
            return ""
        cache = getattr(self, "_item_icon_cache", None)
        if cache is None:
            cache = self._item_icon_cache = {}
        if item_id in cache:
            return cache[item_id]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images", "items", f"{item_id}.png")
        if os.path.exists(path):
            try:
                with open(path, "rb") as _f:
                    uri = "data:image/png;base64," + base64.b64encode(_f.read()).decode("ascii")
                cache[item_id] = uri
                return uri
            except Exception:  # noqa: BLE001
                pass
        return ""

    def _sub_icon(self, subdir: str, name: str) -> str:
        """读取 data/images/<subdir>/<name>.png(设施/科技图标) -> base64 data uri。无图返回空。"""
        if not name:
            return ""
        attr = f"_icon_cache_{subdir}"
        cache = getattr(self, attr, None)
        if cache is None:
            cache = {}
            setattr(self, attr, cache)
        if name in cache:
            return cache[name]
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images", subdir, f"{name}.png")
        if os.path.exists(path):
            try:
                with open(path, "rb") as _f:
                    uri = "data:image/png;base64," + base64.b64encode(_f.read()).decode("ascii")
                cache[name] = uri
                return uri
            except Exception:  # noqa: BLE001
                pass
        return ""

    def _pal_card_data(self, p: dict) -> dict:
        def clean(s):
            return (s or "").replace("\r\n", " ").replace("\n", " ").strip()
        skills = sorted(p.get("active_skills", []), key=lambda s: s.get("level_learned", 0))
        sk = [{"name": s.get("name", "?"), "power": s.get("power", 0),
               "cd": s.get("cool_down_time", 0), "elem": ELEM_CN.get(s.get("element_type"), "")}
              for s in skills][:6]
        works = [{"k": WORK_LABELS.get(k, k), "lv": v}
                 for k, v in (p.get("work_suitability") or {}).items() if v]
        drops = []
        for dd in (p.get("item_drops") or []):
            nm = dd.get("item_name")
            if not nm:
                continue
            mn, mx = dd.get("min_drop"), dd.get("max_drop")
            qty = f"{mn}-{mx}" if (mn and mx and mn != mx) else (str(mx) if mx else "")
            drops.append({"name": nm, "rate": dd.get("drop_rate", ""), "qty": qty,
                          "icon": self._item_icon(dd.get("item_id"))})
        drops = drops[:10]
        st = p.get("stats") or {}
        dev = p.get("pal_dev_name", "")
        ex = (self._pal_extra or {}).get(dev) or {}
        # 牧场产出：有牧场适性时，从伙伴技能描述里识别出现的物品名
        ranch = []
        if (p.get("work_suitability") or {}).get("monster_farm"):
            pdesc = p.get("partner_skill_description") or ""
            for it in (self._items or []):
                inm = it.get("name")
                if inm and len(inm) >= 2 and inm in pdesc:
                    ranch.append({"name": inm, "icon": self._item_icon(it.get("item_id"))})
            ranch = ranch[:4]

        def num(v):
            return v if v not in (None, "") else "—"
        # 刷新等级范围
        lv = ""
        if "lv_min" in ex and "lv_max" in ex:
            lv = f"Lv.{ex['lv_min']}" if ex["lv_min"] == ex["lv_max"] else f"Lv.{ex['lv_min']}~{ex['lv_max']}"
        # 价格(图鉴里的 price 是帕鲁本体售价)
        price = p.get("price")
        try:
            price = int(float(price)) if price not in (None, "") else None
        except (TypeError, ValueError):
            price = None
        cap = p.get("capture_rate_correct")
        if cap not in (None, ""):
            try:
                cap = round(float(cap), 1)
                cap = int(cap) if cap == int(cap) else cap   # 1.0→1、去浮点精度尾巴(0.800000011→0.8)
            except (TypeError, ValueError):
                cap = None
        egg = egg_to_cn(ex.get("egg", ""))
        return {
            "name": p["pal_name"], "index": p["pal_index"], "elements": p.get("elements", []),
            "icon": self._pal_icon(dev),
            "rarity": min(int(p.get("rarity", 0) or 0), 5), "nocturnal": bool(p.get("nocturnal")),
            "desc": clean(p.get("pal_description"))[:120],
            "partner_title": p.get("partner_skill_title", ""),
            "partner_desc": clean(p.get("partner_skill_description"))[:90],
            "skills": sk, "works": works, "drops": drops, "ranch": ranch,
            "hp": num(st.get("hp")), "atk": num(st.get("melee_attack")), "defense": num(st.get("defense")),
            "shot": num(st.get("shot_attack")), "stamina": num(st.get("stamina")),
            "walk": num(st.get("walk_speed")), "run": num(st.get("run_speed")),
            "ride": num(st.get("ride_sprint_speed")), "transport": num(st.get("transport_speed")),
            "food": num(st.get("food_amount")), "size": st.get("size", ""),
            "egg": egg, "lv": lv, "price": price, "cap": cap,
        }

    # ------------------------------------------------------------------
    # 网格列表：模糊搜索 / 全表浏览 + 分页（图鉴/物品/设施/科技 通用）
    # ------------------------------------------------------------------
    def _ordered_pals(self) -> list:
        if getattr(self, "_ord_pals", None) is None:
            def sk(p):
                m = re.match(r"0*(\d+)", str(p.get("pal_index", "")))
                return (int(m.group(1)) if m else 99999, str(p.get("pal_index", "")))
            self._ord_pals = [{"no": str(p.get("pal_index", "?")), "name": p.get("pal_name", ""),
                               "k": "pal", "ik": p.get("pal_dev_name", "")}
                              for p in sorted(self._pals, key=sk)]
        return self._ord_pals

    @staticmethod
    def _item_category(t: str) -> str:
        """原始 type -> 10 大类。"""
        t = t or ""
        if t == "Blueprint":
            return "蓝图"
        if t == "Essential_PalGear":
            return "帕鲁装备"
        if t.startswith("Weapon"):
            return "武器"
        if t in ("ArmorHead", "ArmorBody", "Shield", "Glider"):
            return "防具"
        if t == "Accessory":
            return "饰品"
        if t.startswith("Food"):
            return "食物"
        if t.startswith("Material"):
            return "材料"
        if t in ("SPWeaponCaptureBall", "CaptureItemModifier"):
            return "捕获球"
        if t.startswith("Essential") or t in ("Money", "ReturnToBaseCamp"):
            return "重要物品"
        if t.startswith("Consume") or t in ("Drug", "Medicine"):
            return "消耗品"
        return "其它"

    def _ordered_items(self) -> list:
        if getattr(self, "_ord_items", None) is None:
            self._ord_items = [{"no": str(i + 1), "name": it.get("name", ""),
                                "k": "item", "ik": it.get("item_id", ""),
                                "cat": self._item_category(it.get("type"))}
                               for i, it in enumerate(self._items)]
        return self._ord_items

    def _ordered_buildings(self) -> list:
        if getattr(self, "_ord_buildings", None) is None:
            self._ord_buildings = [{"no": str(i + 1), "name": it.get("name", ""),
                                    "k": "building", "ik": it.get("id", "")}
                                   for i, it in enumerate(self._buildings)]
        return self._ord_buildings

    def _ordered_tech(self) -> list:
        if getattr(self, "_ord_tech", None) is None:
            ordered = sorted(self._tech, key=lambda t: (t.get("level") or 0))
            self._ord_tech = [{"no": str(i + 1), "name": it.get("name", ""),
                               "k": "tech", "ik": it.get("id", "")}
                              for i, it in enumerate(ordered)]
        return self._ord_tech

    def _grid_icon(self, e: dict) -> str:
        k, ik = e.get("k"), e.get("ik")
        if k == "pal":
            return self._pal_icon(ik)
        if k == "item":
            return self._item_icon(ik)
        if k == "building":
            return self._sub_icon("buildings", ik)
        if k == "tech":
            return self._sub_icon("tech", ik)
        return ""

    @staticmethod
    def _parse_page_args(args: list[str]):
        """末位若是纯数字则当页码，其余拼成查询词。返回 (query, page)。"""
        a = list(args)
        page = 1
        if a and a[-1].isdigit():
            page = max(1, int(a[-1]))
            a = a[:-1]
        return " ".join(a).strip(), page

    @staticmethod
    def _page(pool: list, page: int, base_cmd: str, size: int = 18):
        """通用分页：返回 (本页切片, 第几页/共几页副标题, 翻页提示)。"""
        total = max(1, (len(pool) + size - 1) // size)
        page = max(1, min(page, total))
        chunk = pool[(page - 1) * size: page * size]
        sub = f"第 {page}/{total} 页" if total > 1 else ""
        hint = f"发「{base_cmd} {page + 1}」看下一页" if page < total else ""
        return chunk, sub, hint

    async def _render_grid(self, event, title: str, emoji: str, entries: list,
                           page: int, base_cmd: str, query: str):
        total = len(entries)
        pages = max(1, (total + GRID_PAGE_SIZE - 1) // GRID_PAGE_SIZE)
        page = min(max(1, page), pages)
        sl = entries[(page - 1) * GRID_PAGE_SIZE: page * GRID_PAGE_SIZE]
        cells = [{"no": e.get("no", ""), "name": e.get("name", ""), "icon": self._grid_icon(e)} for e in sl]
        if query:
            sub = f"含「{query}」· 共 {total} 个 · 第 {page}/{pages} 页"
        else:
            sub = f"全部 {total} 个 · 第 {page}/{pages} 页"
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            qpart = f" {query}" if query else ""
            pager = f"发送「{base_cmd}{qpart} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("grid"),
                               {"title": title, "emoji": emoji, "sub": sub, "cells": cells, "pager": pager})

    async def _cmd_paldex(self, event: AstrMessageEvent, args: list[str]):
        if not self._pals:
            return await self._msg_card(event, "📕", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失或损坏。", color="#E5484D")
        query, page = self._parse_page_args(args)
        if not query:
            return await self._render_grid(event, "帕鲁图鉴", "📕",
                                           self._ordered_pals(), page, "/帕鲁图鉴", "")
        if query in self._pal_by_name:   # 精确命中 -> 详情卡
            return await self._img(event, self._t("paldex"), self._pal_card_data(self._pal_by_name[query]))
        matches = [e for e in self._ordered_pals() if query in e["name"]]
        if len(matches) == 1:
            return await self._img(event, self._t("paldex"),
                                   self._pal_card_data(self._pal_by_name[matches[0]["name"]]))
        if not matches:
            return await self._msg_card(event, "🔍", "查无此帕鲁",
                                        desc=f"没有名字含「{query}」的帕鲁。", color="#F5A623")
        return await self._render_grid(event, "帕鲁图鉴", "📕", matches, page, "/帕鲁图鉴", query)

    async def _cmd_pal_index(self, event: AstrMessageEvent, args: list[str]):
        """按图鉴编号查帕鲁详情(/帕鲁编号 13B)。独立指令，不走翻页解析，避免编号被当页码。"""
        if not self._pals:
            return await self._msg_card(event, "📕", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失或损坏。", color="#E5484D")
        q = " ".join(args).strip()
        if not q:
            return await self._msg_card(event, "✏️", "请输入图鉴编号",
                                        desc="用法：/帕鲁编号 <编号>\n例：/帕鲁编号 13B（变种）、/帕鲁编号 13",
                                        color="#E5484D")
        p = self._find_pal(q)   # _find_pal 支持编号(含 13B 变种)，也兼容名字
        if not p:
            return await self._msg_card(event, "🔍", "查无此编号",
                                        desc=f"没有编号「{q}」的帕鲁。变种记得带字母，如 13B。", color="#F5A623")
        return await self._img(event, self._t("paldex"), self._pal_card_data(p))

    async def _cmd_breed(self, event: AstrMessageEvent, args: list[str]):
        if not self._breed:
            return await self._msg_card(event, "🧬", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        if len(args) < 2:
            return await self._msg_card(event, "✏️", "请输入两只亲代",
                                        desc="用法：/帕鲁配种 <亲A> <亲B>\n例：/帕鲁配种 棉悠悠 捣蛋猫", color="#E5484D")
        na, nb = args[0], args[1]
        pa, pb = self._find_pal(na), self._find_pal(nb)
        missing = [n for n, pp in ((na, pa), (nb, pb)) if not pp]
        if missing:
            return await self._msg_card(event, "🔍", "查无帕鲁",
                                        desc="找不到：" + "、".join(missing) + "\n请确认帕鲁名是否正确。", color="#F5A623")
        child = self._breed_result(pa, pb)
        if not child:
            return await self._msg_card(event, "🤷", "这对配不出来",
                                        desc=f"{pa['pal_name']} + {pb['pal_name']} 暂无配种结果。", color="#9a8a91")

        def brief(x):
            return {"name": x["pal_name"], "index": x["pal_index"], "elements": x.get("elements", []),
                    "icon": self._pal_icon(x.get("pal_dev_name"))}
        # 子代继续配种：C + 亲A、C + 亲B 各能配出什么
        child_breeds = []
        for partner in (pa, pb):
            if partner["pal_name"] == child["pal_name"]:
                continue
            r = self._breed_result(child, partner)
            if r:
                child_breeds.append({"partner": partner["pal_name"], "result": r["pal_name"],
                                     "partner_icon": self._pal_icon(partner.get("pal_dev_name")),
                                     "result_icon": self._pal_icon(r.get("pal_dev_name"))})
        data = {"a": brief(pa), "b": brief(pb),
                "c": {**brief(child), "rarity": min(int(child.get("rarity", 0) or 0), 5)},
                "child_name": child["pal_name"], "child_breeds": child_breeds}
        return await self._img(event, self._t("breed"), data)

    def _find_item(self, q: str):
        q = (q or "").strip()
        if not q:
            return None
        if q in self._item_by_name:
            return self._item_by_name[q]
        for nm, it in self._item_by_name.items():
            if q in nm or nm in q:
                return it
        return None

    def _item_detail(self, event, it: dict):
        # 制作配方：材料(名+数量+图标,图标按材料名匹配现有物品图标) + 制作台
        rec = (self._recipes or {}).get(it.get("item_id")) or {}
        mats = []
        for m in rec.get("mats", []):
            meta = self._item_by_name.get(m.get("name"))
            mats.append({"name": m.get("name"), "count": m.get("count"),
                         "icon": self._item_icon(meta.get("item_id")) if meta else ""})
        # 交易价格 + 帕鲁球捕获力（item_extra: gold 商人参考价 / cap 捕获力 / rank 等级）
        ex = (self._item_extra or {}).get(it.get("item_id")) or {}
        price = ex.get("gold")
        sphere = None
        cap = ex.get("cap")
        if cap:
            try:
                capn = int(cap) if float(cap).is_integer() else round(float(cap), 1)
            except (TypeError, ValueError):
                capn = cap
            sphere = {"cap": capn, "rank": ex.get("rank")}
        return self._img(event, self._t("item"), {
            "name": it["name"], "type": self._item_type_cn(it.get("type")),
            "description": (it.get("description") or "").replace("\r\n", "\n"),
            "materials": mats, "benches": rec.get("bench", []),
            "price": price, "sphere": sphere,
            "icon": self._item_icon(it.get("item_id"))})

    async def _cmd_item(self, event: AstrMessageEvent, args: list[str]):
        if not self._items:
            return await self._msg_card(event, "🎒", "物品数据未加载",
                                        desc="data/items.json 缺失或损坏。", color="#E5484D")
        query, page = self._parse_page_args(args)
        if not query:                                # 空输入 -> 分类菜单
            cats = {}
            for e in self._ordered_items():
                cats[e["cat"]] = cats.get(e["cat"], 0) + 1
            menu = [{"name": n, "emoji": em, "count": cats[n]} for n, em in ITEM_CAT_META if cats.get(n)]
            return await self._img(event, self._t("itemcat"),
                                   {"total": len(self._items), "cats": menu})
        cat_names = {n for n, _ in ITEM_CAT_META}
        if query in cat_names:                       # 类别名 -> 该类网格
            emoji = dict(ITEM_CAT_META).get(query, "🎒")
            entries = [e for e in self._ordered_items() if e["cat"] == query]
            if not entries:
                return await self._msg_card(event, "🎒", "该分类暂无物品", desc=f"「{query}」分类下没有物品。", color="#9a8a91")
            return await self._render_grid(event, query, emoji, entries, page, "/帕鲁物品", query)
        if query in self._item_by_name:              # 精确名 -> 详情
            return await self._item_detail(event, self._item_by_name[query])
        matches = [e for e in self._ordered_items() if query in e["name"]]
        if len(matches) == 1:
            return await self._item_detail(event, self._item_by_name[matches[0]["name"]])
        if not matches:
            return await self._msg_card(event, "🔍", "查无此物品",
                                        desc=f"没有名字含「{query}」的物品。\n可发「/帕鲁物品」看分类菜单。", color="#F5A623")
        return await self._render_grid(event, "物品图鉴", "🎒", matches, page, "/帕鲁物品", query)

    @staticmethod
    def _item_type_cn(t: str) -> str:
        t = t or ""
        if t in ITEM_TYPE_CN:
            return ITEM_TYPE_CN[t]
        for k, v in ITEM_TYPE_CN.items():   # 复合类型(如 MaterialOre)子串匹配
            if k in t:
                return v
        return t or "物品"

    @staticmethod
    def _find_in(by_name: dict, q: str):
        q = (q or "").strip()
        if not q:
            return None
        if q in by_name:
            return by_name[q]
        for nm, it in by_name.items():   # 包含匹配(模糊)
            if q in nm or nm in q:
                return it
        return None

    def _facility_detail(self, event, it: dict):
        # 建造材料 + 建造方式（设施都是建造菜单按 B 放置，解锁对应科技后可建）
        rec = (self._build_recipes or {}).get(it.get("id")) or {}
        mats = []
        for m in rec.get("mats", []):
            meta = self._item_by_name.get(m.get("name"))
            mats.append({"name": m.get("name"), "count": m.get("count"),
                         "icon": self._item_icon(meta.get("item_id")) if meta else ""})
        build = ""
        if mats:
            tech = rec.get("tech")
            build = "🔨 建造方式：在建造菜单（按 B）中放置" + (f"，需先解锁科技 Lv.{tech}" if tech else "")
        return self._img(event, self._t("facility"), {
            "name": it["name"], "category": it.get("category") or "",
            "description": (it.get("description") or "").replace("\r\n", "\n"),
            "materials": mats, "build": build,
            "icon": self._sub_icon("buildings", it.get("id"))})

    async def _cmd_facility(self, event: AstrMessageEvent, args: list[str]):
        if not self._buildings:
            return await self._msg_card(event, "🏗️", "设施数据未加载",
                                        desc="data/buildings.json 缺失或损坏。", color="#E5484D")
        query, page = self._parse_page_args(args)
        if not query:
            return await self._render_grid(event, "设施图鉴", "🏗️",
                                           self._ordered_buildings(), page, "/帕鲁设施", "")
        if query in self._building_by_name:
            return await self._facility_detail(event, self._building_by_name[query])
        matches = [e for e in self._ordered_buildings() if query in e["name"]]
        if len(matches) == 1:
            return await self._facility_detail(event, self._building_by_name[matches[0]["name"]])
        if not matches:
            return await self._msg_card(event, "🔍", "查无此设施",
                                        desc=f"没有名字含「{query}」的设施。", color="#F5A623")
        return await self._render_grid(event, "设施图鉴", "🏗️", matches, page, "/帕鲁设施", query)

    def _tech_detail(self, event, it: dict):
        is_boss = bool(it.get("is_boss"))
        level = it.get("level") or 0
        points = it.get("points") or 0
        if is_boss:
            unlock = ("🏛️ 古代科技：需消耗「古代科技点」在科技栏解锁。\n"
                      "古代科技点通过击败 野外头目 / 高塔塔主(BOSS) / 地牢头目 获得，"
                      "击败后还可重复挑战刷点。")
        else:
            parts = []
            if level:
                parts.append(f"角色等级达到 Lv.{level}")
            if points:
                parts.append(f"消耗 {points} 个技术点")
            unlock = ("🔓 " + "，".join(parts) + " 即可在科技栏解锁。") if parts else ""
        return self._img(event, self._t("tech"), {
            "name": it["name"], "level": level,
            "points": points, "is_boss": is_boss, "unlock": unlock,
            "description": (it.get("description") or "").replace("\r\n", "\n"),
            "icon": self._sub_icon("tech", it.get("id"))})

    async def _cmd_tech(self, event: AstrMessageEvent, args: list[str]):
        if not self._tech:
            return await self._msg_card(event, "🔬", "科技数据未加载",
                                        desc="data/tech.json 缺失或损坏。", color="#E5484D")
        query, page = self._parse_page_args(args)
        if not query:
            return await self._render_grid(event, "科技图鉴", "🔬",
                                           self._ordered_tech(), page, "/帕鲁科技", "")
        if query in self._tech_by_name:
            return await self._tech_detail(event, self._tech_by_name[query])
        matches = [e for e in self._ordered_tech() if query in e["name"]]
        if len(matches) == 1:
            return await self._tech_detail(event, self._tech_by_name[matches[0]["name"]])
        if not matches:
            return await self._msg_card(event, "🔍", "查无此科技",
                                        desc=f"没有名字含「{query}」的科技。", color="#F5A623")
        return await self._render_grid(event, "科技图鉴", "🔬", matches, page, "/帕鲁科技", query)

    def _breed_result(self, pa: dict, pb: dict):
        ci = self._breed.get(frozenset((self._name_idx.get(pa["pal_name"]), self._name_idx.get(pb["pal_name"]))))
        return self._pal_idx.get(ci) if ci else None

    async def _cmd_reverse(self, event: AstrMessageEvent, args: list[str]):
        if not self._breed_rev:
            return await self._msg_card(event, "🔄", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        if not args:
            return await self._msg_card(event, "✏️", "请输入想配出的帕鲁",
                                        desc="用法：/帕鲁反配种 <帕鲁名>\n例：/帕鲁反配种 空涡龙", color="#E5484D")
        q, page = self._parse_page_args(args)   # 末位数字=页码
        p = self._find_pal(q)
        if not p:
            sug = self._suggest_pals(q)
            desc = f"没找到「{q}」。" + ("\n是不是想查：" + "、".join(sug) if sug else "")
            return await self._msg_card(event, "🔍", "查无此帕鲁", desc=desc, color="#F5A623")
        combos = self._breed_rev.get(self._name_idx.get(p["pal_name"]), [])
        if not combos:
            return await self._msg_card(event, "🤷", "没有配种组合",
                                        desc=f"「{p['pal_name']}」没有可配出的亲代组合（可能是初始/特殊帕鲁）。", color="#9a8a91")
        PS = 14
        pages = max(1, (len(combos) + PS - 1) // PS)
        page = min(max(1, page), pages)
        rows = []
        for a, b in combos[(page - 1) * PS: page * PS]:
            pa, pb = self._pal_idx.get(a), self._pal_idx.get(b)
            if pa and pb:
                rows.append({"a": pa["pal_name"], "b": pb["pal_name"],
                             "a_icon": self._pal_icon(pa.get("pal_dev_name")),
                             "b_icon": self._pal_icon(pb.get("pal_dev_name"))})
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁反配种 {p['pal_name']} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("reverse"), {
            "target": p["pal_name"], "target_index": p["pal_index"],
            "target_icon": self._pal_icon(p.get("pal_dev_name")),
            "total": len(combos), "page": page, "pages": pages, "rows": rows, "pager": pager})

    async def _cmd_drop(self, event: AstrMessageEvent, args: list[str]):
        """掉落反查：给物品名，列出掉落它的帕鲁(按掉率降序，取前20)。"""
        if not self._pals:
            return await self._msg_card(event, "🎁", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失或损坏。", color="#E5484D")
        q, page = self._parse_page_args(args)   # 末位数字=页码
        # 无参 -> 掉落物品目录(全部)；有关键词且非精确 -> 按关键词过滤的目录
        if not q:
            return await self._drop_catalog(event, page, None)
        if q in self._drop_index:
            key = q
        else:
            cands = [k for k in self._drop_index if q in k]
            if not cands:
                return await self._msg_card(
                    event, "🔍", "没找到掉落物品",
                    desc=f"没有掉落物品含「{q}」。\n发 /帕鲁哪里掉 看全部掉落物品目录。",
                    color="#F5A623")
            if len(cands) > 1:               # 多匹配 -> 列出匹配的物品目录(可翻页)
                return await self._drop_catalog(event, page, q)
            key = cands[0]
        entries = sorted(self._drop_index[key], key=lambda x: -(x.get("rate") or 0))
        PS = 12
        pages = max(1, (len(entries) + PS - 1) // PS)
        page = min(max(1, page), pages)
        rows = []
        for e in entries[(page - 1) * PS: page * PS]:
            mn, mx = e.get("min"), e.get("max")
            qty = f"{mn}-{mx}" if (mn and mx and mn != mx) else (str(mx) if mx else "")
            rate = e.get("rate") or 0
            try:
                rate = int(rate) if float(rate) == int(rate) else round(float(rate), 1)
            except (TypeError, ValueError):
                rate = 0
            rows.append({"pal": e["pal"], "index": e["index"],
                         "icon": self._pal_icon(e["dev"]), "rate": rate, "qty": qty})
        it = (self._item_by_name or {}).get(key)
        item_icon = self._item_icon(it.get("item_id")) if it else ""
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁哪里掉 {key} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("drop"), {
            "item": key, "item_icon": item_icon, "total": len(entries),
            "page": page, "pages": pages, "rows": rows, "pager": pager})

    async def _drop_catalog(self, event: AstrMessageEvent, page: int, filt: Optional[str]):
        """掉落物品目录：列出所有(或含关键词的)可被帕鲁掉落的物品，按来源数降序，分页。"""
        keys = list(self._drop_index.keys())
        if filt:
            keys = [k for k in keys if filt in k]
        if not keys:
            return await self._msg_card(
                event, "🔍", "没找到掉落物品",
                desc=f"没有掉落物品含「{filt}」。", color="#F5A623")
        keys.sort(key=lambda k: -len(self._drop_index[k]))   # 掉它的帕鲁越多越靠前
        PS = 16
        pages = max(1, (len(keys) + PS - 1) // PS)
        page = min(max(1, page), pages)
        rows = []
        for name in keys[(page - 1) * PS: page * PS]:
            it = (self._item_by_name or {}).get(name)
            rows.append({"name": name,
                         "icon": self._item_icon(it.get("item_id")) if it else "",
                         "count": len(self._drop_index[name])})
        if filt:
            sub = f"含「{filt}」{len(keys)} 种 · 第 {page}/{pages} 页"
        else:
            sub = f"共 {len(keys)} 种掉落物品 · 第 {page}/{pages} 页"
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = (f"发「/帕鲁哪里掉 {filt} {nxt}」翻页" if filt
                     else f"发「/帕鲁哪里掉 {nxt}」翻页")
        return await self._img(event, self._t("droplist"),
                               {"sub": sub, "rows": rows, "pager": pager})

    # ------------------------------------------------------------------
    # 配种路线规划（/帕鲁怎么配 <目标>）：从玩家现有帕鲁出发的最短多步配种链
    # ------------------------------------------------------------------
    def _breed_route(self, owned: set, target: str):
        """正向 BFS：从 owned(拥有的图鉴号集合) 逐步配出更多，求配出 target 的最短链。
        返回 拓扑序步骤 [(父A号,父B号,子号)] / "owned"(已拥有) / None(配不出)。"""
        if target in owned:
            return "owned"
        reach = {o: None for o in owned}      # 节点 -> 亲代(a,b) 或 None(=拥有的叶子)
        depth = {o: 0 for o in owned}
        for _ in range(60):
            changed = False
            for c, pairs in self._breed_rev.items():
                if c in reach:
                    continue
                for a, b in pairs:
                    if a in reach and b in reach:
                        reach[c] = (a, b)
                        depth[c] = max(depth[a], depth[b]) + 1
                        changed = True
                        break
            if target in reach or not changed:
                break
        if target not in reach or reach[target] is None:
            return None
        steps, seen = [], set()

        def expand(n):
            if n in seen or reach.get(n) is None:
                return
            seen.add(n)
            a, b = reach[n]
            expand(a)
            expand(b)
            steps.append((a, b, n))
        expand(target)
        return steps

    async def _cmd_breed_route(self, event: AstrMessageEvent, args: list[str]):
        if not self._breed_rev:
            return await self._msg_card(event, "🧬", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        if not args:
            return await self._msg_card(event, "✏️", "请输入想配出的帕鲁",
                                        desc="用法：/帕鲁怎么配 <帕鲁名>\n会用你帕鲁箱现有的帕鲁，算出最短配种路线。",
                                        color="#E5484D")
        q = " ".join(args).strip()
        p = self._find_pal(q)
        if not p:
            sug = self._suggest_pals(q)
            return await self._msg_card(event, "🔍", "查无此帕鲁",
                                        desc=f"没找到「{q}」。" + ("\n是不是：" + "、".join(sug) if sug else ""),
                                        color="#F5A623")
        target = self._name_idx.get(p["pal_name"])
        qq = str(event.get_sender_id())
        self._last_save_use = time.time()
        profiles = await self._fetch_save_profiles(max_age=self._fresh_ttl())
        sp = self._match_save_profile(self.state.get("bindings", {}).get(qq), profiles) if profiles else None
        if sp is None:
            return await self._msg_card(
                event, "🔗", "读不到你的帕鲁箱",
                desc="请先 /帕鲁绑定 <游戏名> 并上线一次，让我能读到你的帕鲁箱，再算配种路线。\n"
                     "（也可发 /帕鲁反配种 看通用配对）", color="#F5A623")
        owned = set()
        for pal in sp.get("party", []) + sp.get("palbox", []):
            pp = self._pal_by_dev.get(str(pal.get("char_id", "")).lower())
            if pp:
                owned.add(self._norm_idx(str(pp.get("pal_index", ""))))
        owned.discard("")
        if not owned:
            return await self._msg_card(event, "📦", "你的帕鲁箱是空的",
                                        desc="先去抓几只帕鲁，再来规划配种路线～", color="#9a8a91")
        route = self._breed_route(owned, target)
        if route == "owned":
            return await self._msg_card(event, "✅", "你已经有这只啦",
                                        desc=f"「{p['pal_name']}」已经在你的帕鲁箱里了，不用配。", color="#30A46C")
        if not route:
            return await self._msg_card(
                event, "🤷", "现有帕鲁配不出",
                desc=f"用你现在的帕鲁，暂时配不出「{p['pal_name']}」（还缺一些基础帕鲁）。\n"
                     "多抓几只、或发 /帕鲁反配种 看它的直接配对。", color="#F5A623")
        steps = []
        for i, (a, b, c) in enumerate(route, 1):
            pa, pb, pc = self._pal_idx.get(a), self._pal_idx.get(b), self._pal_idx.get(c)
            steps.append({
                "n": i,
                "a": (pa or {}).get("pal_name", a), "a_icon": self._pal_icon((pa or {}).get("pal_dev_name", "")),
                "a_owned": a in owned,
                "b": (pb or {}).get("pal_name", b), "b_icon": self._pal_icon((pb or {}).get("pal_dev_name", "")),
                "b_owned": b in owned,
                "c": (pc or {}).get("pal_name", c), "c_icon": self._pal_icon((pc or {}).get("pal_dev_name", "")),
                "is_target": c == target})
        return await self._img(event, self._t("route"), {
            "target": p["pal_name"], "target_icon": self._pal_icon(p.get("pal_dev_name")),
            "steps": steps, "n_steps": len(steps),
            "sub": f"用你现有帕鲁 · {len(steps)} 步配出"})

    # ------------------------------------------------------------------
    # 词条继承概率计算（/帕鲁继承 父A词条 | 母B词条）
    # ------------------------------------------------------------------
    # 从父母「词条池」继承的词条数量分布（社区大量实测得出的模型）：
    #   继承 1 个 40% / 2 个 30% / 3 个 20% / 4 个 10%。
    # 之后若孩子词条没满 4 格，空格还有概率随机刷出新词条（不影响已继承的目标词条）。
    _INHERIT_DIST = {1: 0.40, 2: 0.30, 3: 0.20, 4: 0.10}

    def _passive_name_index(self) -> dict:
        """惰性构建：词条中文名(去空格) -> id，含部分别名。"""
        idx = getattr(self, "_pass_name_idx", None)
        if idx is not None:
            return idx
        idx = {}
        for pid, m in (self._passives or {}).items():
            nm = (m.get("name") or "").strip()
            if nm:
                idx.setdefault(nm, pid)
                idx.setdefault(nm.replace(" ", ""), pid)
        self._pass_name_idx = idx
        return idx

    def _resolve_passive(self, token: str):
        """词条名(模糊) -> (id, meta)。先精确，再去等级后缀，再包含匹配。找不到返回 (None,None)。"""
        token = (token or "").strip()
        if not token:
            return None, None
        nidx = self._passive_name_index()
        pv = self._passives or {}
        key = token.replace(" ", "")
        if key in nidx:
            pid = nidx[key]
            return pid, pv[pid]
        # 包含匹配（如「攻击力」匹配「提升攻击力Lv2」）；取名字最短的一条
        hits = [(pid, m) for pid, m in pv.items()
                if key in (m.get("name", "").replace(" ", "")) or (m.get("name", "").replace(" ", "")) in key]
        if hits:
            hits.sort(key=lambda x: len(x[1].get("name", "")))
            return hits[0]
        return None, None

    @staticmethod
    def _comb(n: int, k: int) -> int:
        from math import comb
        if k < 0 or k > n:
            return 0
        return comb(n, k)

    def _p_subset_inherited(self, s: int, n: int) -> float:
        """父母去重词条池大小 n，求「指定 s 个目标词条全部被孩子继承」的概率。"""
        if s <= 0:
            return 1.0
        if s > n or s > 4:
            return 0.0
        total = 0.0
        for k, pk in self._INHERIT_DIST.items():
            m = min(k, n)               # 实际从池中继承的数量
            if m < s:
                continue
            total += pk * self._comb(n - s, m - s) / self._comb(n, m)
        return total

    def _inherit_count_dist(self, n: int) -> list:
        """孩子从父母池继承「恰好 j 个」词条的概率分布 [(j, p)]，j=1..min(4,n)。"""
        agg = {}
        for k, pk in self._INHERIT_DIST.items():
            j = min(k, n)
            agg[j] = agg.get(j, 0.0) + pk
        return sorted(agg.items())

    def _passive_chip(self, pid: str, meta: dict) -> dict:
        """词条 -> 展示用(名/效果/星级/配色档)。复用 _passive_view 的配色规则。"""
        v = self._passive_view(pid)
        return {"name": v["name"], "effect": meta.get("effect", ""),
                "rank": v["rank"], "color": v["color"], "stars": "★" * (v["rank"] or 1)}

    @staticmethod
    def _split_parents(text: str):
        """'A1,A2 | B1,B2' -> (['A1','A2'], ['B1','B2'])。分隔符容错。"""
        for sep in ["|", "｜", " vs ", " VS ", "／", " / ", "×", " x "]:
            if sep in text:
                left, right = text.split(sep, 1)
                return left, right
        # 没有显式分隔符：尝试用「配」「和」（词条名里不含这两个字，安全）
        for sep in ["配", "和"]:
            if sep in text:
                left, right = text.split(sep, 1)
                return left, right
        return text, ""

    @staticmethod
    def _split_passives(s: str) -> list:
        import re as _re
        parts = _re.split(r"[，,、+＋]", s)
        return [x.strip() for x in parts if x.strip()]

    async def _cmd_inherit(self, event: AstrMessageEvent, args: list):
        if not self._passives:
            return await self._msg_card(event, "🧬", "词条数据未加载",
                                        desc="data/passives.json 未就绪。", color="#E5484D")
        raw = " ".join(args).strip()
        left, right = self._split_parents(raw)
        a_tokens = self._split_passives(left)
        b_tokens = self._split_passives(right)
        if not a_tokens and not b_tokens:
            return await self._msg_card(
                event, "🧬", "词条继承概率计算",
                desc=("算一算两只亲代的词条，孩子能同时继承的概率。\n"
                      "用法：/帕鲁继承 父代词条 ｜ 母代词条\n"
                      "多个词条用逗号隔开，两只亲代用「｜」隔开。\n\n"
                      "例：/帕鲁继承 卓绝技艺 ｜ 金刚之躯\n"
                      "例：/帕鲁继承 提升攻击Lv3,高速工作Lv3 ｜ 神速,金刚之躯"),
                head="🧬 词条继承", color="#7ab8ff")

        def resolve_list(tokens):
            out, unknown = [], []
            for t in tokens:
                pid, meta = self._resolve_passive(t)
                if pid:
                    out.append((pid, meta))
                else:
                    unknown.append(t)
            return out, unknown

        a_res, a_unk = resolve_list(a_tokens)
        b_res, b_unk = resolve_list(b_tokens)
        unknown = a_unk + b_unk
        # 去重词条池（按 id）
        pool_ids = []
        for pid, _ in a_res + b_res:
            if pid not in pool_ids:
                pool_ids.append(pid)
        n = len(pool_ids)
        if n == 0:
            tip = ("，".join(unknown[:4]) + " 等") if unknown else "（空）"
            return await self._msg_card(event, "🔍", "没认出这些词条",
                                        desc=f"无法识别：{tip}\n请用游戏里的词条全名，如「提升攻击力Lv3」「狂暴之力」。\n发 /帕鲁推荐词条 <帕鲁> 可看常见词条名。",
                                        color="#F5A623")
        pv = self._passives
        a_chips = [self._passive_chip(pid, m) for pid, m in a_res]
        b_chips = [self._passive_chip(pid, m) for pid, m in b_res]
        pool_chips = [self._passive_chip(pid, pv[pid]) for pid in pool_ids]
        # 每个词条单独继承率
        p_each = self._p_subset_inherited(1, n)
        for c in pool_chips:
            c["p_single"] = round(p_each * 100)
        # 集齐全部（最多 4 个，超出则不可能）
        want = min(n, 4)
        p_all = self._p_subset_inherited(n, n) if n <= 4 else 0.0
        # 继承数量分布
        dist = [{"j": j, "p": round(p * 100)} for j, p in self._inherit_count_dist(n)]
        # 头条解读
        if n <= 4:
            headline = f"孩子同时继承这 {n} 个词条 ≈ {round(p_all*100)}%"
        else:
            headline = f"亲代共 {n} 个不同词条，但孩子最多只有 4 格，无法全继承"
        shared = [c["name"] for pid, c in zip(pool_ids, pool_chips)
                  if any(x[0] == pid for x in a_res) and any(x[0] == pid for x in b_res)]
        data = {
            "a_chips": a_chips, "b_chips": b_chips, "pool": pool_chips,
            "n": n, "headline": headline, "p_all": round(p_all * 100),
            "feasible": n <= 4, "dist": dist, "want": want,
            "shared": shared, "unknown": unknown,
        }
        return await self._img(event, self._t("inherit"), data)

    # ------------------------------------------------------------------
    # 竞技场（/帕鲁竞技场 [段位]）
    # ------------------------------------------------------------------
    _ARENA_EMOJI = {"青铜": "🥉", "白银": "🥈", "黄金": "🥇", "铂金": "💠", "钻石": "💎", "大师": "👑"}
    _ARENA_ALIAS = {"青铜": "青铜", "bronze": "青铜", "白银": "白银", "silver": "白银",
                    "黄金": "黄金", "gold": "黄金", "铂金": "铂金", "platinum": "铂金",
                    "钻石": "钻石", "diamond": "钻石", "大师": "大师", "master": "大师"}

    @staticmethod
    def _arena_reward_str(items: list) -> str:
        return " · ".join(f"{r['name']}×{r['qty']}" for r in items) if items else "—"

    async def _cmd_arena(self, event: AstrMessageEvent, args: list):
        if not self._arena or not self._arena.get("teams"):
            return await self._msg_card(event, "🏟️", "竞技场数据未加载",
                                        desc="data/arena.json 缺失或损坏。", color="#E5484D")
        tiers = self._arena.get("tiers", [])
        teams = self._arena.get("teams", [])
        rewards = {r["tier"]: r for r in self._arena.get("rewards", [])}
        levels = self._arena.get("tier_levels", {})
        q = " ".join(args).strip().lower()
        tier = self._ARENA_ALIAS.get(q) if q else None
        if not tier and q:
            for t in tiers:                       # 容错：含段位名即可
                if t in q or q in t:
                    tier = t
                    break
        if not tier:                              # 总览
            rows = []
            for t in tiers:
                rw = rewards.get(t, {})
                rows.append({"tier": t, "emoji": self._ARENA_EMOJI.get(t, "🏟️"),
                             "level": levels.get(t, "?"),
                             "count": sum(1 for tm in teams if tm["tier"] == t),
                             "first": self._arena_reward_str(rw.get("first", []))})
            return await self._img(event, self._t("arena"),
                                   {"tiers": rows, "shop": self._arena.get("shop_ref", "竞技场商店")})
        # 段位详情
        tier_teams = [tm for tm in teams if tm["tier"] == tier]
        view = [{"trainer": tm["trainer"], "level": tm["level"],
                 "pals": [{"name": p["name"], "icon": self._pal_icon(p["dev"])} for p in tm["pals"]]}
                for tm in tier_teams]
        rw = rewards.get(tier, {})
        return await self._img(event, self._t("arena_tier"),
                               {"tier": tier, "emoji": self._ARENA_EMOJI.get(tier, "🏟️"),
                                "level": levels.get(tier, "?"), "teams": view,
                                "first": rw.get("first", []), "repeat": rw.get("repeat", [])})

    # ------------------------------------------------------------------
    # 配置读取
    # ------------------------------------------------------------------
    def _api_base(self) -> str:
        return str(self.config.get("api_base", "http://palworld-server:8212")).rstrip("/")

    def _theme(self) -> str:
        return str(self.config.get("card_theme_color") or DEFAULT_THEME)

    def _timeout(self) -> int:
        return int(self.config.get("request_timeout", 5))

    def _confirm_timeout(self) -> int:
        return int(self.config.get("confirm_timeout", 60))

    def _effective_cooldown(self) -> int:
        return max(int(self.config.get("query_cooldown", 10)), HARD_MIN_COOLDOWN)

    def _admins(self) -> list[str]:
        return [str(q).strip() for q in (self.config.get("admin_qq") or []) if str(q).strip()]

    def _is_admin(self, qq: str) -> bool:
        return str(qq) in self._admins()

    # --- 后台广播相关配置 ---
    def _enable_broadcast(self) -> bool:
        return bool(self.config.get("enable_broadcast", True))

    def _poll_interval(self) -> int:
        return max(int(self.config.get("poll_interval", 60)), 20)   # 硬下限 20s

    def _notify_join_left(self) -> bool:
        return bool(self.config.get("notify_player_join_left", True))

    def _notify_server_down(self) -> bool:
        return bool(self.config.get("notify_server_down", True))

    def _offline_threshold(self) -> int:
        return max(int(self.config.get("offline_alert_threshold", 2)), 1)

    def _broadcast_targets(self) -> list[str]:
        """配置了 broadcast_groups 就用它，否则用自动登记的群。"""
        cfg = [str(g).strip() for g in (self.config.get("broadcast_groups") or []) if str(g).strip()]
        return cfg if cfg else [str(g) for g in self.state.get("groups", [])]

    # ------------------------------------------------------------------
    # HTTP 封装(aiohttp 异步 + Basic Auth + 超时)
    # ------------------------------------------------------------------
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _auth(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth("admin", str(self.config.get("admin_password", "")))

    # REST 请求封装已移至 api.palworld_api（统一超时/错误处理），此处保留薄包装。
    async def _api_get(self, path: str) -> Tuple[bool, Any, int]:
        return await palworld_api.api_get(
            await self._get_session(), self._api_base(), self._auth(), self._timeout(), path)

    async def _api_post(self, path: str, payload: Optional[dict] = None) -> Tuple[bool, str]:
        return await palworld_api.api_post(
            await self._get_session(), self._api_base(), self._auth(), self._timeout(), path, payload)

    # ------------------------------------------------------------------
    # 容器资源(CPU/内存)：经 docker.sock 读 Docker API(只读)
    # ------------------------------------------------------------------
    async def _docker_stats(self) -> Optional[dict]:
        if not self.config.get("enable_host_stats", True):
            return None
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        if not os.path.exists(sock):
            return None   # 未挂载 docker.sock，静默跳过(卡片不显示负载)
        return await docker_api.container_stats(sock, container)

    # ------------------------------------------------------------------
    # 存档解析：经 docker.sock 拉服务器存档(Level.sav + Players/*.sav)解析玩家档案
    # （背包/队伍/等级/技术点）。强制存盘后拉取，带 TTL 缓存。
    # ------------------------------------------------------------------
    def _fresh_ttl(self) -> int:
        """个人自助查询(我/背包/队伍/箱/据点/公会)的缓存有效期(秒)：与强存节流对齐
        (force_save_min_interval，默认15)，让玩家游戏内刚获取的物品/帕鲁/天赋点尽快查到
        最新，而非等满 save_cache_ttl(默认120s)。榜单类聚合查询不传，沿用长缓存。"""
        return max(int(self.config.get("force_save_min_interval", 15)), 0)

    async def _fetch_save_data(self, force_save: bool = True, max_age=None) -> Optional[dict]:
        # 缓存/负缓存/强制存盘/拉取编排已移至 services.save_service.SaveService。
        return await self._save.fetch_save_data(force_save, max_age)

    async def _fetch_save_profiles(self, force_save: bool = True, max_age=None) -> Optional[dict]:
        return await self._save.fetch_profiles(force_save, max_age)

    async def _fetch_guilds(self, force_save: bool = True, max_age=None) -> Optional[list]:
        return await self._save.fetch_guilds(force_save, max_age)

    async def _pull_save_files(self, sock: str, container: str, save_dir: str) -> str:
        # docker archive 拉取 + tar 安全解包已移至 api.docker_api.pull_save_files。
        return await docker_api.pull_save_files(sock, container, save_dir)

    # ------------------------------------------------------------------
    # docker.sock 控制原语：exec / 容器动作 / 一次性辅助容器（重置存档要用）
    # ⚠️ 高危：均经 docker.sock，必须由上层管理员白名单 + 二次确认保护。见 api/docker_api.py。
    # ------------------------------------------------------------------
    _demux_docker_stream = staticmethod(docker_api.demux_docker_stream)

    async def _docker_exec(self, sock: str, container: str, cmd: list,
                           timeout: int = 20) -> Tuple[int, str]:
        return await docker_api.docker_exec(sock, container, cmd, timeout)

    async def _docker_container_action(self, sock: str, container: str,
                                       action: str, timeout: int = 90) -> None:
        return await docker_api.container_action(sock, container, action, timeout)

    async def _docker_image_of(self, sock: str, container: str) -> str:
        return await docker_api.image_of(sock, container)

    async def _docker_run_helper(self, sock: str, image: str, src_container: str,
                                 cmd: list, timeout: int = 120) -> Tuple[int, str]:
        return await docker_api.run_helper(sock, image, src_container, cmd, timeout)

    # 默认存档基目录(容器内)：SaveGames/0，其下每个世界一个 32 位十六进制 GUID 子目录。
    _DEFAULT_SAVEGAMES_BASE = "/palworld/Pal/Saved/SaveGames/0"

    def _configured_save_dir(self) -> str:
        # 留空=自动探测(见 _resolve_save_dir)。不再写死某台机器的世界 GUID，换机即用。
        return str(self.config.get("save_dir_in_container", "") or "").strip()

    def _save_games_base(self) -> str:
        """SaveGames/0 基目录：配置了完整存档路径就取其父目录，否则用默认基目录。
        供删档/恢复等按目录批处理用(不依赖具体世界 GUID，即便未配置也可用)。"""
        configured = self._configured_save_dir()
        if configured:
            return configured.rsplit("/", 1)[0]
        return self._DEFAULT_SAVEGAMES_BASE

    async def _resolve_container(self, sock: str) -> str:
        """解析帕鲁服容器名：配置的容器存在即用；否则自动探测镜像/名字含 palworld 的
        运行中容器。带进程级缓存。探测不到时回退配置值(默认 palworld-server)。"""
        configured = str(self.config.get("docker_container", "palworld-server")).strip() or "palworld-server"
        cached = getattr(self, "_resolved_container", None)
        if cached:
            return cached
        resolved = configured
        if os.path.exists(sock):
            try:
                # docker socket 读操作已封装到 api.docker_api（inspect/list）。
                ok = await docker_api.inspect_container(sock, configured) is not None
                if not ok:
                    conts = await docker_api.list_containers(sock)
                    # 打分择优：同机可能并存 palworld 周边容器(web 前后端/数据库)，
                    # 只认游戏服(镜像/名字含 palworld+server，且不含 web/db 关键字)。
                    best, best_sc = None, 0
                    for c in (conts or []):
                        names = [str(n).lstrip("/") for n in (c.get("Names") or [])]
                        if not names:
                            continue
                        text = (str(c.get("Image", "")) + " " + " ".join(names)).lower()
                        if "palworld" not in text:
                            continue
                        if any(k in text for k in
                               ("web", "frontend", "backend", "postgres", "redis",
                                "nginx", "mysql", "mariadb", "mongo")):
                            continue   # 明显是周边服务，跳过
                        sc = 1
                        if "palworld-server" in text or "palworld_server" in text:
                            sc += 10
                        if "server" in text:
                            sc += 3
                        if names[0] == "palworld-server":
                            sc += 2
                        if sc > best_sc:
                            best, best_sc = names[0], sc
                    if best:
                        resolved = best
            except Exception as e:  # noqa: BLE001
                logger.debug(f"{LOG_PREFIX} 容器自动探测失败(回退配置值): {e}")
        self._resolved_container = resolved
        if resolved != configured:
            logger.info(f"{LOG_PREFIX} 帕鲁服容器自动探测为：{resolved}")
        return resolved

    async def _resolve_save_dir(self, sock: str, container: str) -> str:
        """容器内世界存档目录：自动探测 SaveGames/0/ 下含 Level.sav 的世界目录。
        删档重开后 GUID 可能变化、且各机 GUID 不同，因此不写死；配置留空也能定位。带缓存。"""
        configured = self._configured_save_dir()
        cached = getattr(self, "_resolved_save_dir", None)
        if cached:
            return cached
        base = self._save_games_base()   # .../SaveGames/0
        dirs = []
        try:
            script = (f'for d in "{base}"/*/; do '
                      f'[ -f "$d/Level.sav" ] && printf "%s\\n" "$d"; done')
            _, out = await self._docker_exec(sock, container, ["/bin/sh", "-c", script])
            dirs = [ln.strip().rstrip("/") for ln in out.splitlines() if ln.strip()]
        except Exception as e:  # noqa: BLE001
            logger.debug(f"{LOG_PREFIX} 存档目录探测失败(回退配置值): {e}")
        # 优先级：配置值仍有效(稳态) > 唯一的 32 位 GUID 世界目录 > 探测到的第一个 > 配置值兜底
        if configured and configured in dirs:
            resolved = configured
        else:
            guids = [d for d in dirs if re.fullmatch(r"[0-9A-Fa-f]{32}", d.rsplit("/", 1)[-1])]
            if len(guids) == 1:
                resolved = guids[0]
            elif dirs:
                resolved = dirs[0]
            else:
                resolved = configured   # 可能为空 → 上层拉档失败并进负缓存，自检会提示
        self._resolved_save_dir = resolved
        if resolved and resolved != configured:
            logger.info(f"{LOG_PREFIX} 存档目录自动探测为：{resolved}")
        return resolved

    def _parse_save_dir(self, save_dir: str) -> dict:
        """同步(放线程池)：解析存档 -> {'profiles':{playerId大写hex:档案}, 'guilds':[公会]}。"""
        import sys, uuid, importlib
        # palwork 定位：插件内优先(市场安装后仓库整体在插件目录内，自包含)，
        # 找不到再回退旧的外部路径 astrbot/data/palwork(兼容作者本机现有开发部署)。
        here = os.path.dirname(os.path.abspath(__file__))
        pw = os.path.join(here, "palwork")
        if not os.path.isfile(os.path.join(pw, "palsave.py")):
            pw = os.path.abspath(os.path.join(here, "..", "..", "palwork"))
        if pw not in sys.path:
            sys.path.insert(0, pw)
        import palsave
        # 机器人进程长驻：palsave 可能是早先缓存的旧版本，每次插件加载后重载一次，
        # 拿到最新解析逻辑(改了 palsave.py 重载插件即可，无需重启整个容器)
        if not getattr(self, "_palsave_reloaded", False):
            importlib.reload(palsave)
            self._palsave_reloaded = True
        raw = palsave.extract_profiles(save_dir)
        profiles = {}
        for uid, p in raw.items():
            try:
                hexid = uuid.UUID(str(uid)).hex.upper()
            except Exception:  # noqa: BLE001
                hexid = str(uid)
            p["player_id"] = hexid
            profiles[hexid] = p
        try:
            guilds = palsave.extract_guilds(save_dir)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 公会解析失败: {e}")
            guilds = []
        return {"profiles": profiles, "guilds": guilds}

    def _match_save_profile(self, binding: dict, profiles: dict) -> Optional[dict]:
        """绑定记录 -> 该玩家存档档案。先用 userId→playerId 映射，再昵称兜底。"""
        if not binding or not profiles:
            return None
        uid = binding.get("userId") or ""
        pid = (self.state.get("uid2pid", {}) or {}).get(uid)
        if pid and pid in profiles:
            return profiles[pid]
        name = binding.get("name")
        if name:
            matches = [p for p in profiles.values() if p.get("nickname") == name]
            if len(matches) == 1:
                return matches[0]
            # 同名多档=歧义：宁可查不到也不能命中错人(隐私)。需管理员用 playerId 精确处理。
        return None

    # ------------------------------------------------------------------
    # 在线玩家世界地图（/帕鲁地图，仅管理员，仅在线玩家）
    # ------------------------------------------------------------------
    def _load_map(self) -> bool:
        """加载地图变换/区域/底图(base64)，缓存。成功返回 True。"""
        if getattr(self, "_map_ready", None) is not None:
            return self._map_ready
        self._map_ready = False
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        try:
            with open(os.path.join(base, "map_transform.json"), encoding="utf-8") as _f:
                t = json.loads(_f.read())
            self._map_mu, self._map_mv = t["mu"], t["mv"]   # 世界坐标->图片百分比(0~1) 仿射
            with open(os.path.join(base, "map_regions.json"), encoding="utf-8") as _f:
                reg = json.loads(_f.read())
            self._map_regions = [(n, d["X"], d["Y"]) for n, d in reg.items()]
            # 地图底图优先级：4096² 高清 hd.jpg > 2048² png > 1280 压缩图
            hd = os.path.join(base, "worldmap_hd.jpg")
            png = os.path.join(base, "worldmap.png")
            if os.path.exists(hd):
                with open(hd, "rb") as _f:
                    self._map_img = "data:image/jpeg;base64," + base64.b64encode(_f.read()).decode("ascii")
            elif os.path.exists(png):
                with open(png, "rb") as _f:
                    self._map_img = "data:image/png;base64," + base64.b64encode(_f.read()).decode("ascii")
            else:
                with open(os.path.join(base, "worldmap_render.jpg"), "rb") as _f:
                    img = _f.read()
                self._map_img = "data:image/jpeg;base64," + base64.b64encode(img).decode("ascii")
            self._map_ready = True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 地图素材加载失败: {e}")
        return self._map_ready

    def _world_to_mappct(self, wx: float, wy: float):
        """游戏世界坐标 -> 地图图片百分比 (left%, top%)。返回 (left%, top%, wx, wy)。"""
        mu, mv = self._map_mu, self._map_mv
        left = (mu[0] * wx + mu[1] * wy + mu[2]) * 100.0
        top = (mv[0] * wx + mv[1] * wy + mv[2]) * 100.0
        return left, top, wx, wy

    def _nearest_region(self, wx: float, wy: float) -> str:
        best, bd = "未知区域", None
        for name, rx, ry in self._map_regions:
            d = (wx - rx) ** 2 + (wy - ry) ** 2
            if bd is None or d < bd:
                bd, best = d, name
        return best

    async def _cmd_map(self, event: AstrMessageEvent):
        if not self._load_map():
            return await self._msg_card(event, "🗺️", "地图素材缺失",
                                        desc="data/worldmap_render.jpg / map_transform.json 未就绪。", color="#E5484D")
        ok, data, status = await self._api_get("/v1/api/players")
        if not ok:
            return await self._query_fail_card(event, status)
        raw = (data or {}).get("players", []) if isinstance(data, dict) else []
        players = []
        for i, p in enumerate(raw, 1):
            try:
                wx = float(p.get("location_x")); wy = float(p.get("location_y"))
            except (TypeError, ValueError):
                continue
            left, top, px, py = self._world_to_mappct(wx, wy)
            gx = round((wy - 158000) / 459)   # 世界坐标 -> 游戏内地图坐标(与游戏地图一致)
            gy = round((wx + 123888) / 459)
            players.append({"no": i, "name": p.get("name") or "玩家", "level": p.get("level", "?"),
                            "region": self._nearest_region(px, py), "coord": f"{gx}, {gy}",
                            "left": round(max(0, min(100, left)), 2), "top": round(max(0, min(100, top)), 2)})
        if not players:
            return await self._msg_card(event, "🗺️", "当前无人在线",
                                        desc="服务器现在没有在线玩家，地图上没有可标注的位置。", color="#9a8a91")
        sub = f"{len(players)} 人在线 · {datetime.now().strftime('%H:%M')}"
        return await self._img(event, self._t("map"),
                               {"subtitle": sub, "mapimg": self._map_img, "players": players},
                               width=MAP_WIDTH, dsf=1.6)

    # ------------------------------------------------------------------
    # 属性克制图（/帕鲁属性克制）
    # ------------------------------------------------------------------
    def _element_data(self) -> dict:
        order = ["无", "火", "水", "草", "雷", "冰", "地", "暗", "龙"]
        el = self._elements or {}
        elems = []
        for cn in order:
            v = el.get(cn)
            if not v:
                continue
            elems.append({
                "cn": cn, "emoji": ELEM_EMOJI.get(cn, ""), "color": v.get("color", "#888"),
                "strong": [{"cn": s, "emoji": ELEM_EMOJI.get(s, "")} for s in v.get("strong", [])],
                "weak": [{"cn": w, "emoji": ELEM_EMOJI.get(w, "")} for w in v.get("weak", [])],
            })
        return {"elems": elems}

    async def _cmd_element(self, event: AstrMessageEvent):
        if not self._elements:
            return await self._msg_card(event, "⚔️", "克制数据缺失",
                                        desc="data/elements.json 未就绪。", color="#E5484D")
        return await self._img(event, self._t("element"), self._element_data())

    # ------------------------------------------------------------------
    # 栖息区域（/帕鲁栖息区域 <名>）：在世界地图上涂出该帕鲁刷新热区
    # ------------------------------------------------------------------
    def _mappct_to_world(self, leftpct: float, toppct: float):
        """地图图片百分比 -> 世界坐标(_world_to_mappct 的逆变换，用于就近归属区域)。"""
        a, b, c = self._map_mu
        d, e, f = self._map_mv
        L = leftpct / 100.0 - c
        T = toppct / 100.0 - f
        det = a * e - b * d
        # 世界坐标量级达 1e5、系数 ~1e-6，det 正常就在 ~1e-13，阈值须极小只挡真奇异
        if abs(det) < 1e-30:
            return 0.0, 0.0
        return (L * e - b * T) / det, (a * T - L * d) / det

    def _habitat_data(self, p: dict) -> dict:
        dev = p.get("pal_dev_name", "")
        sp = (self._pal_spawns or {}).get(dev) or {}
        day = sp.get("day") or []
        night = sp.get("night") or []
        pts = list(day) + list(night)
        els = p.get("elements", []) or []
        cn = els[0].replace("属性", "").strip() if els else ""
        color = (self._elements or {}).get(cn, {}).get("color") or "#ff6a3d"
        # 各刷新点就近归属「主要生物群系」-> 统计占比(用精选大区，避免就近偏到小锚点)
        region_count: dict = {}
        for x, y in pts:
            wx, wy = self._mappct_to_world(x, y)
            best, bd = None, None
            for bn, (bx, by) in MAJOR_BIOMES.items():
                dd = (wx - bx) ** 2 + (wy - by) ** 2
                if bd is None or dd < bd:
                    bd, best = dd, bn
            if best:
                region_count[best] = region_count.get(best, 0) + 1
        top = sorted(region_count.items(), key=lambda kv: -kv[1])[:6]
        regions = [{"name": n, "pct": max(1, round(c * 100.0 / len(pts)))} for n, c in top] if pts else []
        points = [{"l": round(x, 2), "t": round(y, 2)} for x, y in pts]
        return {"name": p["pal_name"], "index": p.get("pal_index", "?"),
                "icon": self._pal_icon(dev), "elements": els, "color": color,
                "mapimg": self._map_img, "points": points, "regions": regions,
                "nocturnal": bool(p.get("nocturnal")), "count": len(pts),
                "has_day": bool(day), "has_night": bool(night)}

    async def _cmd_habitat(self, event: AstrMessageEvent, args: list):
        if not self._pals:
            return await self._msg_card(event, "🗺️", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失或损坏。", color="#E5484D")
        if not self._load_map():
            return await self._msg_card(event, "🗺️", "地图素材缺失",
                                        desc="worldmap / map_transform.json 未就绪。", color="#E5484D")
        q = " ".join(args).strip()
        if not q:
            return await self._msg_card(event, "🗺️", "请指定帕鲁",
                                        desc="例：/帕鲁栖息区域 棉悠悠", color="#F5A623")
        p = self._find_pal(q)
        if not p:
            sug = self._suggest_pals(q)
            desc = "未找到该帕鲁。" + ("\n你是否想找：" + " / ".join(sug) if sug else "")
            return await self._msg_card(event, "🔍", "查无此帕鲁", desc=desc, color="#F5A623")
        data = self._habitat_data(p)
        if not data["points"]:
            return await self._msg_card(event, "🗺️", f"{p['pal_name']} 无野外刷新点",
                                        desc="该帕鲁可能是 BOSS／塔主／配种或活动获取，地图上没有野生栖息点。",
                                        color="#9a8a91")
        return await self._img(event, self._t("habitat"), data, width=MAP_WIDTH, dsf=1.6)

    # ------------------------------------------------------------------
    # 推荐词条（/帕鲁推荐词条 <名>）：按帕鲁角色推荐高价值被动词条
    # ------------------------------------------------------------------
    def _passrec_data(self, p: dict) -> dict:
        pv = self._passives or {}

        def mk(key: str):
            m = pv.get(key)
            if not m:
                return None
            rk = int(m.get("rank") or 0)
            return {"name": m.get("name", ""), "effect": m.get("effect", ""),
                    "rank": rk, "stars": "★" * rk}

        def collect(keys: list):
            out, seen = [], set()
            for k in keys:
                e = mk(k)
                if e and e["name"] and e["name"] not in seen:
                    seen.add(e["name"])
                    out.append(e)
            return out

        ws = {k: v for k, v in (p.get("work_suitability") or {}).items() if v}
        els = p.get("elements", []) or []
        cn = els[0].replace("属性", "").strip() if els else ""
        color = (self._elements or {}).get(cn, {}).get("color") or "#e8c466"
        is_prod = any(k in PROD_WORK_KEYS for k in ws)
        is_trans = bool(ws.get("transport"))
        roles = ["战斗"] + (["生产"] if is_prod else []) + (["搬运"] if is_trans else [])
        sections = [{"title": "🏆 通用强力（万金油）", "color": "#e8c466", "items": collect(PASS_UNIVERSAL)}]
        combat = collect(PASS_COMBAT)
        eb = PASS_ELEM_BOOST.get(cn)
        if eb:
            e = mk(eb)
            if e and e["name"] not in {x["name"] for x in combat}:
                combat.insert(1, e)
        sections.append({"title": "⚔️ 战斗向", "color": color, "items": combat})
        if is_prod:
            sections.append({"title": "🔨 生产向（基地干活）", "color": "#7CFC9A", "items": collect(PASS_PRODUCE)})
        if is_trans:
            sections.append({"title": "📦 搬运向", "color": "#7ab8ff", "items": collect(PASS_TRANSPORT)})
        return {"name": p["pal_name"], "index": p.get("pal_index", "?"),
                "icon": self._pal_icon(p.get("pal_dev_name", "")), "elements": els,
                "color": color, "roles": roles, "sections": sections}

    async def _cmd_passrec(self, event: AstrMessageEvent, args: list):
        if not self._pals:
            return await self._msg_card(event, "📜", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失或损坏。", color="#E5484D")
        if not self._passives:
            return await self._msg_card(event, "📜", "词条数据缺失",
                                        desc="data/passives.json 未就绪。", color="#E5484D")
        q = " ".join(args).strip()
        if not q:
            return await self._msg_card(event, "📜", "请指定帕鲁",
                                        desc="例：/帕鲁推荐词条 棉悠悠", color="#F5A623")
        p = self._find_pal(q)
        if not p:
            sug = self._suggest_pals(q)
            desc = "未找到该帕鲁。" + ("\n你是否想找：" + " / ".join(sug) if sug else "")
            return await self._msg_card(event, "🔍", "查无此帕鲁", desc=desc, color="#F5A623")
        return await self._img(event, self._t("passrec"), self._passrec_data(p))

    # ------------------------------------------------------------------
    # 任务（/帕鲁任务 /帕鲁主线 /帕鲁支线）
    # ------------------------------------------------------------------
    def _find_mission(self, q: str):
        q = (q or "").strip()
        if not q:
            return None
        if q in self._mission_by_name:
            return self._mission_by_name[q]
        hits = [m for m in self._missions if q in m["name"]]
        return hits[0] if len(hits) == 1 else None

    def _mission_detail_data(self, m: dict) -> dict:
        is_main = m.get("type") == "主线"
        grp = ""
        if not is_main:
            grp = MISSION_GROUP_CN.get(m.get("group", ""), "") if m.get("group") is not None else ""
            if grp == "其它委托" and not m.get("group"):
                grp = "委托"
        return {
            "name": m["name"], "emoji": "📜" if is_main else "📋",
            "tlabel": "主线任务" if is_main else "支线任务",
            "tcolor": "#e8c466" if is_main else "#7ab8ff",
            "order": m.get("order") if is_main else 0,
            "group": grp, "desc": m.get("desc", ""),
            "objective": m.get("objective", ""), "coords": m.get("coords", ""),
            "exp": m.get("exp", ""), "rewards": m.get("rewards", []),
            "nextname": m.get("next", "") if is_main else "",
        }

    async def _cmd_mission(self, event: AstrMessageEvent, args: list):
        if not self._missions:
            return await self._msg_card(event, "📜", "任务数据未加载",
                                        desc="data/missions.json 缺失或损坏。", color="#E5484D")
        q = " ".join(args).strip()
        if not q or q in ("主线", "主线任务"):
            return await self._cmd_mainquest(event, [a for a in args if a not in ("主线", "主线任务")])
        if q in ("支线", "支线任务"):
            return await self._cmd_subquest(event, [])
        m = self._find_mission(q)
        if m:
            return await self._img(event, self._t("mission"), self._mission_detail_data(m))
        hits = [x for x in self._missions if q in x["name"]]
        if not hits:
            return await self._msg_card(event, "🔍", "查无此任务",
                                        desc=f"没有名字含「{q}」的任务。\n发「/帕鲁主线」或「/帕鲁支线」看任务列表。", color="#F5A623")
        rows = [{"tag": (str(x["order"]) if x["type"] == "主线" else "支"), "name": x["name"],
                 "brief": x.get("objective") or (f"经验+{x['exp']}" if x.get("exp") else "")} for x in hits[:30]]
        return await self._img(event, self._t("missionlist"),
                               {"title": f"📜 含「{q}」的任务", "subtitle": f"{len(hits)} 个",
                                "rows": rows, "detailhint": f"/帕鲁任务 {hits[0]['name']}", "pagehint": ""})

    async def _cmd_mainquest(self, event: AstrMessageEvent, args: list):
        if not self._missions:
            return await self._msg_card(event, "📜", "任务数据未加载", desc="data/missions.json 缺失。", color="#E5484D")
        mains = sorted([m for m in self._missions if m["type"] == "主线"], key=lambda x: x.get("order", 999))
        page = 1
        if args and args[-1].isdigit():
            page = max(1, int(args[-1]))
        size = 16
        total_pages = max(1, (len(mains) + size - 1) // size)
        page = min(page, total_pages)
        chunk = mains[(page - 1) * size: page * size]
        rows = [{"tag": str(m.get("order", "")), "name": m["name"],
                 "brief": (m.get("desc", "")[:22] or m.get("objective", ""))} for m in chunk]
        pagehint = f"发「/帕鲁主线 {page + 1}」看下一页" if page < total_pages else ""
        return await self._img(event, self._t("missionlist"),
                               {"title": "📜 主线任务", "subtitle": f"共 {len(mains)} 个 · 第 {page}/{total_pages} 页",
                                "rows": rows, "detailhint": "/帕鲁任务 启动巨鹫之像", "pagehint": pagehint})

    async def _cmd_subquest(self, event: AstrMessageEvent, args: list):
        if not self._missions:
            return await self._msg_card(event, "📋", "任务数据未加载", desc="data/missions.json 缺失。", color="#E5484D")
        subs = [m for m in self._missions if m["type"] == "支线"]
        q = " ".join(a for a in args if not a.isdigit()).strip()
        cn2key = {v: k for k, v in MISSION_GROUP_CN.items()}
        if q:   # 按 NPC 分组筛选（中文名或英文键）
            key = cn2key.get(q) or (q if q in MISSION_GROUP_CN else None)
            if key is not None:
                subs = [m for m in subs if m.get("group", "") == key]
            else:
                subs = [m for m in subs if q in m["name"]]
            if not subs:
                groups = "、".join(v for v in MISSION_GROUP_CN.values() if v != "其它委托")
                return await self._msg_card(event, "🔍", "没有匹配的支线",
                                            desc=f"可按 NPC 分组查：{groups}\n例：/帕鲁支线 佐伊", color="#F5A623")
        rows = [{"tag": MISSION_GROUP_CN.get(m.get("group", ""), "委托")[:2], "name": m["name"],
                 "brief": (m.get("desc", "")[:22] or m.get("objective", ""))} for m in subs[:30]]
        sub = f"共 {len(subs)} 个" + (f" · {q}" if q else " · 8 类 NPC 委托")
        return await self._img(event, self._t("missionlist"),
                               {"title": "📋 支线任务", "subtitle": sub, "rows": rows,
                                "detailhint": f"/帕鲁任务 {subs[0]['name']}" if subs else "/帕鲁任务 <名>",
                                "pagehint": "可加 NPC 名筛选，如 /帕鲁支线 农民" if not q else ""})

    # ------------------------------------------------------------------
    # Boss（/帕鲁塔主 /帕鲁突袭 /帕鲁boss <名>）
    # ------------------------------------------------------------------
    def _find_boss(self, q: str):
        q = (q or "").strip()
        if not q:
            return None
        exact = [b for b in self._bosses if q in (b["name"], b.get("pal"), b.get("short"), b.get("human"))]
        if exact:
            return exact[0]
        hits = [b for b in self._bosses
                if any(q in (b.get(k) or "") for k in ("name", "pal", "short", "human"))]
        return hits[0] if len(hits) == 1 else None

    def _counter_pals(self, elems: list, n: int = 3) -> list:
        """从图鉴里挑出指定属性的高基础战力帕鲁名(用于 BOSS 克制推荐)。"""
        elset = set(elems)
        cands = []
        for p in self._pals:
            pels = {e.replace("属性", "") for e in (p.get("elements") or [])}
            if elset & pels:
                st = p.get("stats") or {}
                score = st.get("hp", 0) * 0.5 + st.get("shot_attack", 0) + st.get("defense", 0)
                cands.append((score, p.get("pal_name")))
        cands.sort(key=lambda x: -x[0])
        out = []
        for _, nm in cands:
            if nm and nm not in out:
                out.append(nm)
            if len(out) >= n:
                break
        return out

    def _boss_detail_data(self, b: dict) -> dict:
        els = [e for e in (b.get("element") or "").split("/") if e]
        color = "#e8c466"
        if els:
            color = (self._elements or {}).get(els[0], {}).get("color") or color
        is_tower = b.get("category") == "塔主"
        # 攻略提示：被克属性 + 推荐等级
        weak = []
        for e in els:
            weak += (self._elements or {}).get(e, {}).get("weak", [])
        tip_parts = []
        if weak:
            weak_uniq = list(dict.fromkeys(weak))
            tip_parts.append("它的属性怕 " + "、".join(weak_uniq) + " 系——带这些属性的帕鲁/武器更克它")
            recs = self._counter_pals(weak_uniq, 3)
            if recs:
                tip_parts.append("推荐打手：" + "、".join(recs))
        if b.get("level"):
            tip_parts.append(f"建议练到 Lv.{b['level']} 左右再来打")
        if is_tower:
            tip_parts.append("塔主战限时、限带 5 只帕鲁，注意躲技能、备好治疗")
        else:
            tip_parts.append("突袭 boss 血厚，建议多人或满配队伍速攻")
        return {"name": b.get("short") or b["name"], "emoji": "🗼" if is_tower else "👹",
                "catlabel": b.get("category", "Boss"), "color": color,
                "elements": [e + "属性" for e in els], "difficulty": b.get("difficulty", ""),
                "level": b.get("level", ""), "hp": b.get("hp", ""), "location": b.get("location", ""),
                "drops": b.get("drops", []), "icon": self._pal_icon(b.get("dev", "")),
                "tip": "；".join(tip_parts) + "。"}

    async def _cmd_boss(self, event: AstrMessageEvent, args: list, category: str = ""):
        if not self._bosses:
            return await self._msg_card(event, "👹", "Boss 数据未加载",
                                        desc="data/bosses.json 缺失或损坏。", color="#E5484D")
        q, page = self._parse_page_args(args)
        if q:
            b = self._find_boss(q)
            if b:
                return await self._img(event, self._t("boss"), self._boss_detail_data(b))
            hits = [x for x in self._bosses
                    if any(q in (x.get(k) or "") for k in ("name", "pal", "short", "human"))]
            if not hits:
                return await self._msg_card(event, "🔍", "查无此 Boss",
                                            desc=f"没有名字含「{q}」的 Boss。\n发「/帕鲁塔主」或「/帕鲁突袭」看列表。", color="#F5A623")
            pool = hits
        else:
            pool = [b for b in self._bosses if b["category"] == category] if category else self._bosses
        title = {"塔主": "🗼 高塔塔主", "突袭": "👹 突袭 Boss"}.get(category, "👹 Boss 一览")
        base = {"塔主": "/帕鲁塔主", "突袭": "/帕鲁突袭"}.get(category, "/帕鲁boss")
        chunk, psub, phint = self._page(pool, page, base)
        rows = [{"tag": (b.get("element") or "—")[:2], "name": b.get("short") or b["name"],
                 "brief": f"Lv.{b.get('level') or '?'} · HP {b.get('hp') or '?'}" + (f" · {b['location']}" if b.get("location") else "")}
                for b in chunk]
        return await self._img(event, self._t("missionlist"),
                               {"title": title, "subtitle": f"共 {len(pool)} 个" + (f" · {psub}" if psub else ""),
                                "rows": rows, "detailhint": f"/帕鲁boss {chunk[0].get('short') or chunk[0]['name']}" if chunk else "/帕鲁boss <名>",
                                "pagehint": phint})

    # ------------------------------------------------------------------
    # 商人（/帕鲁商人 [名]  /帕鲁哪里买 <物品>）
    # ------------------------------------------------------------------
    @staticmethod
    def _stock_label(stock) -> str:
        """商店库存文案：-1=无限补货(常驻)，>0=有限库存，0/空=不显示。"""
        if stock == -1:
            return "常驻∞"
        if stock and stock > 0:
            return f"库存{stock}"
        return ""

    async def _cmd_merchant(self, event: AstrMessageEvent, args: list):
        if not self._merchants:
            return await self._msg_card(event, "🏪", "商人数据未加载",
                                        desc="data/merchants.json 缺失或损坏。", color="#E5484D")
        q = " ".join(args).strip()
        if not q:   # 商店总览
            rows = [{"name": s["name"], "sub": s["currency"], "right": f"{len(s['items'])} 件"} for s in self._merchants]
            return await self._img(event, self._t("merchant"),
                                   {"emoji": "🏪", "icon": self._sub_icon("misc", "merchant"),
                                    "title": "🏪 商人一览", "badges": [f"{len(self._merchants)} 个商店"],
                                    "note": "", "rows": rows,
                                    "foot": "发「/帕鲁商人 沙漠商人」看某商店卖什么；「/帕鲁哪里买 <物品>」查某物品哪买。"})
        sh = next((s for s in self._merchants if s["name"] == q), None) \
            or next((s for s in self._merchants if q in s["name"]), None)
        if not sh:
            names = "、".join(s["name"] for s in self._merchants)
            return await self._msg_card(event, "🔍", "没有这个商店",
                                        desc=f"现有商店：{names}\n或用「/帕鲁哪里买 <物品>」查物品。", color="#F5A623")
        cur = sh["currency"]
        rows = [{"name": it["name"],
                 "sub": self._stock_label(it.get("stock")),
                 "right": (f"{it['price']} {cur}" if it.get("price") else cur)} for it in sh["items"]]
        return await self._img(event, self._t("merchant"),
                               {"emoji": "🧙", "icon": self._sub_icon("misc", "merchant"),
                                "title": sh["name"], "badges": [f"货币 {cur}", f"{len(sh['items'])} 件商品"],
                                "note": sh.get("note", ""), "rows": rows,
                                "foot": "「金币」价为商人参考价，不同地区略有浮动。"})

    async def _cmd_wheretobuy(self, event: AstrMessageEvent, args: list):
        if not self._merchants:
            return await self._msg_card(event, "🏪", "商人数据未加载", desc="data/merchants.json 缺失。", color="#E5484D")
        q = " ".join(args).strip()
        if not q:
            return await self._msg_card(event, "🛒", "查什么物品？",
                                        desc="例：/帕鲁哪里买 帕鲁球", color="#F5A623")
        # 精确 -> 模糊
        shops = self._item_shops.get(q)
        item_name = q
        if not shops:
            cand = [nm for nm in self._item_shops if q in nm]
            if len(cand) >= 1:
                item_name = cand[0]
                shops = self._item_shops.get(item_name)
        if not shops:
            return await self._msg_card(event, "🛒", f"商人那买不到「{q}」",
                                        desc="该物品可能不在商店出售（需制作/采集/打怪掉落）。\n可发「/帕鲁物品 " + q + "」看获取方式。",
                                        color="#9a8a91")
        rows = [{"name": sp["shop"],
                 "sub": self._stock_label(sp.get("stock")),
                 "right": (f"{sp['price']} {sp['currency']}" if sp.get("price") else sp["currency"])} for sp in shops]
        return await self._img(event, self._t("merchant"),
                               {"emoji": "🛒", "title": f"哪里买 · {item_name}", "badges": [f"{len(shops)} 处出售"],
                                "note": "", "rows": rows,
                                "foot": "勋章/赏金/竞技场币 商店需用对应特殊货币兑换。"})

    # ------------------------------------------------------------------
    # 钓鱼（/帕鲁钓鱼）
    # ------------------------------------------------------------------
    async def _cmd_fishing(self, event: AstrMessageEvent, args: list):
        catch = (self._fishing or {}).get("catch") or []
        if not catch:
            return await self._msg_card(event, "🎣", "钓鱼数据未加载",
                                        desc="data/fishing.json 缺失或损坏。", color="#E5484D")
        rows = [{"name": c["name"], "sub": (f"×{c['qty']}" if c.get("qty") and c["qty"] != "1" else ""),
                 "right": c.get("rate", "")} for c in catch]
        return await self._img(event, self._t("merchant"),
                               {"emoji": "🎣", "title": "🎣 钓鱼可获得",
                                "badges": [f"{len(catch)} 种钓获物", "水边钓点"],
                                "note": "在水边用钓竿钓鱼，有概率钓上以下物品（概率为单次大致值）：",
                                "rows": rows,
                                "foot": "钓点遍布各水域；稀有设计图/钥匙/帕鲁之魂都能钓到，刷概率多试几次。"})

    # ------------------------------------------------------------------
    # 工作适性排行（/帕鲁工作 <工种>）
    # ------------------------------------------------------------------
    async def _cmd_work(self, event: AstrMessageEvent, args: list):
        if not self._pals:
            return await self._msg_card(event, "🔨", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失。", color="#E5484D")
        q, page = self._parse_page_args(args)
        if not q:
            works = "、".join(dict.fromkeys(WORK_LABELS.values()))
            return await self._msg_card(event, "🔨", "查哪个工种？",
                                        desc=f"可查工种：{works}\n例：/帕鲁工作 采矿", color="#F5A623")
        key = WORK_ALIAS.get(q) or next((k for k, v in WORK_LABELS.items() if v == q), None)
        if not key:
            works = "、".join(dict.fromkeys(WORK_LABELS.values()))
            return await self._msg_card(event, "🔍", "没有这个工种",
                                        desc=f"可查工种：{works}", color="#F5A623")
        pool = [(p, (p.get("work_suitability") or {}).get(key, 0)) for p in self._pals]
        pool = [(p, lv) for p, lv in pool if lv]
        pool.sort(key=lambda t: (-t[1], int(re.match(r"0*(\d+)", str(t[0].get("pal_index", "999"))).group(1))
                                 if re.match(r"0*(\d+)", str(t[0].get("pal_index", ""))) else 999))
        if not pool:
            return await self._msg_card(event, "🔨", "暂无数据", desc=f"没有帕鲁有「{WORK_LABELS.get(key, q)}」适性。", color="#9a8a91")
        wname = WORK_LABELS.get(key, q)
        chunk, psub, phint = self._page(pool, page, f"/帕鲁工作 {wname}")
        rows = [{"tag": f"Lv{lv}", "name": p["pal_name"],
                 "brief": "·".join(p.get("elements", [])) + (f" · No.{p.get('pal_index')}" if p.get("pal_index") else "")}
                for p, lv in chunk]
        return await self._img(event, self._t("missionlist"),
                               {"title": f"🔨 {wname} · 适性排行",
                                "subtitle": f"共 {len(pool)} 只 · 适性 Lv 越高越强" + (f" · {psub}" if psub else ""),
                                "rows": rows, "detailhint": f"/帕鲁图鉴 {chunk[0][0]['pal_name']}" if chunk else "",
                                "pagehint": phint or "Lv4 为最高级，能做高阶工作且更快"})

    # ------------------------------------------------------------------
    # 武器数据（/帕鲁武器 [名]）
    # ------------------------------------------------------------------
    async def _cmd_weapon(self, event: AstrMessageEvent, args: list):
        if not self._weapons:
            return await self._msg_card(event, "🔫", "武器数据未加载",
                                        desc="data/weapons.json 缺失。", color="#E5484D")
        q = " ".join(args).strip()
        if q and not q.isdigit():   # 查某武器
            hits = [w for w in self._weapons if q in w["name"]]
            if len(hits) == 1:
                w = hits[0]
                rows = [{"name": "攻击力", "right": str(w["attack"])},
                        {"name": "解锁科技", "right": f"Lv.{w['tech']}" if w.get("tech") else "—"},
                        {"name": "弹药", "right": w.get("ammo") or "近战/无需弹药"}]
                return await self._img(event, self._t("merchant"),
                                       {"emoji": "🔫", "icon": self._item_icon(w.get("item_id", "")),
                                        "title": w["name"], "badges": [f"攻击 {w['attack']}"],
                                        "note": "", "rows": rows,
                                        "foot": "攻击力为基础值，实际伤害还受属性克制/词条/弹药影响。"})
            if not hits:
                return await self._msg_card(event, "🔍", "查无此武器",
                                            desc=f"没有名字含「{q}」的武器。发「/帕鲁武器」看全部。", color="#F5A623")
            pool = hits
        else:
            pool = self._weapons
        page = 1
        if args and args[-1].isdigit():
            page = max(1, int(args[-1]))
        size = 20
        total = max(1, (len(pool) + size - 1) // size)
        page = min(page, total)
        chunk = pool[(page - 1) * size: page * size]
        rows = [{"tag": str(w["attack"]), "name": w["name"],
                 "brief": (f"科技Lv{w['tech']}" if w.get("tech") else "") + (f" · {w['ammo']}" if w.get("ammo") else "")}
                for w in chunk]
        ph = f"发「/帕鲁武器 {page + 1}」看下一页" if page < total else ""
        return await self._img(event, self._t("missionlist"),
                               {"title": "🔫 武器 · 攻击力榜", "subtitle": f"共 {len(pool)} 把 · 第 {page}/{total} 页 · 数字为攻击力",
                                "rows": rows, "detailhint": f"/帕鲁武器 {chunk[0]['name']}" if chunk else "/帕鲁武器 <名>",
                                "pagehint": ph})

    # ------------------------------------------------------------------
    # 增益料理（/帕鲁料理 [效果]）
    # ------------------------------------------------------------------
    async def _cmd_cuisine(self, event: AstrMessageEvent, args: list):
        if not self._cuisine:
            return await self._msg_card(event, "🍳", "料理数据未加载",
                                        desc="data/cuisine.json 缺失。", color="#E5484D")
        q, page = self._parse_page_args(args)
        pool = self._cuisine
        if q:   # 按效果/名称筛选（攻击/防御/工作速度/SAN/配种 等）
            pool = [c for c in self._cuisine if q in c["effect"] or q in c["name"]]
            if not pool:
                return await self._msg_card(event, "🔍", "没有匹配的料理",
                                            desc=f"没有效果/名字含「{q}」的料理。\n可试：攻击、防御、工作速度、SAN、配种、经验。", color="#F5A623")
        chunk, psub, phint = self._page(pool, page, f"/帕鲁料理 {q}".rstrip())
        rows = [{"tag": "🍴", "name": c["name"], "brief": c["effect"]} for c in chunk]
        sub = (f"含「{q}」· {len(pool)} 道" if q else f"{len(pool)} 道增益料理") + (f" · {psub}" if psub else "")
        return await self._img(event, self._t("missionlist"),
                               {"title": "🍳 增益料理", "subtitle": sub, "rows": rows,
                                "detailhint": f"/帕鲁物品 {chunk[0]['name']}" if chunk else "",
                                "pagehint": phint or "可按效果筛选，如 /帕鲁料理 攻击 / 工作速度 / 配种"})

    # ------------------------------------------------------------------
    # 最佳坐骑/移速榜（/帕鲁坐骑）
    # ------------------------------------------------------------------
    async def _cmd_mount(self, event: AstrMessageEvent, args: list):
        if not self._pals:
            return await self._msg_card(event, "🐎", "图鉴数据未加载", desc="data/paldex.json 缺失。", color="#E5484D")
        # 可骑乘 = ride_sprint_speed 明显大于 run_speed 的帕鲁(坐骑加速)
        pool = []
        for p in self._pals:
            st = p.get("stats") or {}
            ride = st.get("ride_sprint_speed") or 0
            run = st.get("run_speed") or 0
            if ride and ride > run and ride >= 700:   # 阈值滤掉非坐骑的默认值
                pool.append((p, ride, st.get("stamina") or 0))
        pool.sort(key=lambda t: -t[1])
        if not pool:
            return await self._msg_card(event, "🐎", "暂无坐骑数据", desc="数据缺失。", color="#9a8a91")
        _, page = self._parse_page_args(args)
        chunk, psub, phint = self._page(pool, page, "/帕鲁坐骑")
        rows = [{"tag": str(int(ride)), "name": p["pal_name"],
                 "brief": "·".join(p.get("elements", [])) + f" · 耐力{int(stam)}"}
                for p, ride, stam in chunk]
        return await self._img(event, self._t("missionlist"),
                               {"title": "🐎 坐骑 · 奔跑速度榜",
                                "subtitle": f"共 {len(pool)} 只可骑乘 · 数字为骑乘奔跑速度" + (f" · {psub}" if psub else ""),
                                "rows": rows, "detailhint": f"/帕鲁图鉴 {chunk[0][0]['pal_name']}" if chunk else "",
                                "pagehint": phint or "数值越大跑越快；耐力高续航更久"})

    # ------------------------------------------------------------------
    # 帕鲁对比（/帕鲁对比 <A> <B>）
    # ------------------------------------------------------------------
    async def _cmd_compare(self, event: AstrMessageEvent, args: list):
        if not self._pals:
            return await self._msg_card(event, "⚖️", "图鉴数据未加载", desc="data/paldex.json 缺失。", color="#E5484D")
        if len(args) < 2:
            return await self._msg_card(event, "⚖️", "要对比哪两只？",
                                        desc="例：/帕鲁对比 棉悠悠 火绒狐", color="#F5A623")
        pa, pb = self._find_pal(args[0]), self._find_pal(args[1])
        if not pa or not pb:
            miss = args[0] if not pa else args[1]
            return await self._msg_card(event, "🔍", "查无此帕鲁", desc=f"找不到「{miss}」。", color="#F5A623")

        def num(v):
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return 0
        STATS = [("生命值", "hp"), ("近战攻击", "melee_attack"), ("远程攻击", "shot_attack"),
                 ("防御力", "defense"), ("耐力", "stamina"), ("走路速度", "walk_speed"),
                 ("奔跑速度", "run_speed"), ("骑乘速度", "ride_sprint_speed")]
        sa, sb = pa.get("stats") or {}, pb.get("stats") or {}
        stats = []
        for lbl, k in STATS:
            va, vb = num(sa.get(k)), num(sb.get(k))
            stats.append({"label": lbl, "lval": va, "rval": vb, "lwin": va > vb, "rwin": vb > va})
        wa, wb = pa.get("work_suitability") or {}, pb.get("work_suitability") or {}
        works = [{"label": WORK_LABELS[k], "l": wa.get(k, 0), "r": wb.get(k, 0)}
                 for k in WORK_LABELS if wa.get(k) or wb.get(k)]

        def side(p):
            return {"name": p["pal_name"], "icon": self._pal_icon(p.get("pal_dev_name", "")),
                    "elements": "·".join(p.get("elements", [])),
                    "color": (self._elements or {}).get((p.get("elements") or [""])[0].replace("属性", ""), {}).get("color") or "#e8c466"}
        return await self._img(event, self._t("compare"),
                               {"left": side(pa), "right": side(pb), "stats": stats, "works": works})

    # ------------------------------------------------------------------
    # 主动技能（/帕鲁技能 <名/属性>）
    # ------------------------------------------------------------------
    async def _cmd_skill(self, event: AstrMessageEvent, args: list):
        if not self._skills:
            return await self._msg_card(event, "✨", "技能数据未加载",
                                        desc="data/skills.json 缺失或损坏。", color="#E5484D")
        q, page = self._parse_page_args(args)
        ELS = ("无", "火", "水", "雷", "草", "冰", "地", "暗", "龙")
        if not q:
            return await self._msg_card(event, "✨", "查哪个技能？",
                                        desc="例：/帕鲁技能 火球术\n也可按属性查：/帕鲁技能 火\n或只看技能果实：/帕鲁技能 果实",
                                        color="#F5A623")
        if q in ("果实", "技能果实", "fruit"):       # 技能果实清单
            pool = [s for s in self._skills if s.get("is_fruit")]
            chunk, psub, phint = self._page(pool, page, "/帕鲁技能 果实")
            rows = [{"tag": s["element"], "name": s["name"],
                     "brief": f"威力{s['power']} · 冷却{s['cooldown']}s · {s['desc'][:14]}"} for s in chunk]
            return await self._img(event, self._t("missionlist"),
                                   {"title": "🍐 技能果实", "subtitle": f"{len(pool)} 个可通过果实学会" + (f" · {psub}" if psub else ""),
                                    "rows": rows, "detailhint": f"/帕鲁技能 {chunk[0]['name']}" if chunk else "/帕鲁技能 <名>",
                                    "pagehint": phint})
        if q in ELS:
            pool = [s for s in self._skills if s["element"] == q]
            chunk, psub, phint = self._page(pool, page, f"/帕鲁技能 {q}")
            rows = [{"tag": s["power"] or "—", "name": s["name"],
                     "brief": f"冷却{s['cooldown']}s · {s['desc'][:16]}"} for s in chunk]
            return await self._img(event, self._t("missionlist"),
                                   {"title": f"✨ {q}属性技能", "subtitle": f"共 {len(pool)} 个" + (f" · {psub}" if psub else ""),
                                    "rows": rows, "detailhint": f"/帕鲁技能 {chunk[0]['name']}" if chunk else "/帕鲁技能 <名>",
                                    "pagehint": phint or "tag 为威力值"})
        s = self._skill_full.get(q) or next((x for x in self._skills if q in x["name"]), None)
        if not s:
            return await self._msg_card(event, "🔍", "查无此技能",
                                        desc=f"没有名字含「{q}」的主动技能。\n可按属性查，如 /帕鲁技能 火。", color="#F5A623")
        color = (self._elements or {}).get(s["element"], {}).get("color") or "#e8c466"
        return await self._img(event, self._t("skill"),
                               {"name": s["name"], "emoji": ELEM_EMOJI.get(s["element"], "✨"),
                                "element": s["element"], "color": color, "power": s["power"],
                                "cooldown": s["cooldown"], "effect": s.get("effect", ""),
                                "desc": s.get("desc", ""), "is_fruit": s.get("is_fruit", False)})

    # ------------------------------------------------------------------
    # 渲染封装：优先用本地 Playwright(快、可并行、无网络往返)，失败回退 AstrBot 远程 t2i
    # ------------------------------------------------------------------
    async def _get_browser(self):
        # Playwright 浏览器/本地渲染/Jinja 编译已移至 render.renderer.Renderer。
        return await self._renderer.get_browser()

    async def _render_local(self, tmpl: str, data: dict, width: int, dsf: float = 1.5) -> Optional[str]:
        return await self._renderer.render_local(tmpl, data, width, dsf)

    async def _render(self, tmpl: str, data: dict, width: int = CARD_WIDTH, dsf: float = 1.5) -> Optional[str]:
        return await self._renderer.render(tmpl, data, width, dsf)


    async def _img(self, event: AstrMessageEvent, tmpl: str, data: dict, width: int = CARD_WIDTH, dsf: float = 1.5):
        """渲染成图片结果；失败兜底纯文字。width 可加宽，dsf 可提清晰度(地图用)。"""
        url = await self._render(tmpl, data, width=width, dsf=dsf)
        if url:
            return event.image_result(url)
        return event.plain_result("⚠️ 卡片渲染失败，请稍后再试或联系管理员。")

    async def _msg_card(self, event, icon, title, desc="", head="帕鲁服务器管家", color=None):
        return await self._img(event, self._t("message"), {
            "icon": icon, "title": title, "desc": desc, "head": head,
            "color": color or self._theme(),
        })

    async def _offline_card(self, event):
        return await self._img(event, self._t("message"), {
            "icon": "🔴", "title": "服务器离线", "head": "🎮 帕鲁服务器",
            "desc": "无法连接到帕鲁服务器，可能正在重启或已关闭，请稍后再试。",
            "color": "#E5484D",
        })

    async def _auth_error_card(self, event):
        return await self._img(event, self._t("message"), {
            "icon": "🔑", "title": "认证失败", "head": "🎮 帕鲁服务器",
            "desc": "服务器可连接，但 REST API 密码不正确。\n请检查插件配置 admin_password "
                    "是否等于服务器 ADMIN_PASSWORD。",
            "color": "#E5484D",
        })

    async def _query_fail_card(self, event, status: int):
        """查询失败统一处理：401/403 => 认证失败；其余 => 离线。"""
        if status in (401, 403):
            return await self._auth_error_card(event)
        return await self._offline_card(event)

    async def _no_perm_card(self, event):
        return await self._img(event, self._t("message"), {
            "icon": "🚫", "title": "无权限", "head": "🎮 帕鲁服务器",
            "desc": "该指令仅限管理员使用，你不在管理员白名单中。",
            "color": "#E5484D",
        })

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    @staticmethod
    def _fmt_uptime(seconds) -> str:
        try:
            s = int(seconds)
        except (TypeError, ValueError):
            return "—"
        d, s = divmod(s, 86400)
        h, s = divmod(s, 3600)
        m, _ = divmod(s, 60)
        if d:
            return f"{d}天{h}时"
        if h:
            return f"{h}时{m}分"
        return f"{m}分"

    @staticmethod
    def _ping_color(ping) -> str:
        try:
            p = float(ping)
        except (TypeError, ValueError):
            return "#9a9aa8"
        if p < 80:
            return "#30A46C"   # 绿
        if p < 150:
            return "#F5A623"   # 橙
        return "#E5484D"       # 红

    # ------------------------------------------------------------------
    # 指令入口：正则匹配「帕鲁」开头，手动解析子命令。
    # 用 regex 而非 command，是为了支持无空格写法(帕鲁在线/帕鲁状态)，
    # 同时兼容带空格(帕鲁 在线)与可选指令前缀「/」(/帕鲁、/帕鲁帮助)。
    # 只匹配「帕鲁」后接已知子命令或空白/结尾，避免误触普通聊天(如「帕鲁太好玩了」)。
    # ------------------------------------------------------------------
    # 已知子命令别名全集：供“无空格粘连指令”兜底做最长前缀匹配(见 _split_glued_sub)。
    # 直接派生自命令注册表(commands/router.py)，与 _dispatch 天然同源，无需再手工维护。
    _SUB_ALIASES = COMMAND_TOKENS

    def _split_glued_sub(self, sub: str, args: list) -> tuple:
        """无空格粘连兜底：sub 未命中任何已知子命令、但以某个已知别名开头时，
        按最长前缀拆成 (别名, [剩余]+原args)。例:帕鲁图鉴皮皮鸡 -> 图鉴 皮皮鸡。
        精确命中的 sub 原样返回；仅取长度>=2 的别名做前缀(避免单字误吞)，长别名优先。"""
        if not sub or sub in self._SUB_ALIASES:
            return sub, args
        order = getattr(self, "_sub_alias_order", None)
        if order is None:
            order = self._sub_alias_order = sorted(
                (a for a in self._SUB_ALIASES if len(a) >= 2), key=len, reverse=True)
        for alias in order:
            if sub.startswith(alias) and len(sub) > len(alias):
                rest = sub[len(alias):].strip()
                return alias, (([rest] + list(args)) if rest else list(args))
        return sub, args

    @filter.regex(r"^\s*/?帕鲁(?:\s|$|状态|在线|玩家|设置|统计|热力图|在线热力|热力|热度|heatmap|图鉴编号|编号查询|编号|palid|战力榜|战力排行|战力|最强帕鲁|power|闪光墙|闪光帕鲁|闪光|幸运帕鲁|shiny|lucky|头目墙|alpha墙|alpha|头目收集|排行|肝帝榜|榜|图鉴榜|图鉴排行|收集榜|图鉴收集|dexrank|资产榜|身价榜|财富榜|土豪榜|wealth|公会战力|工会战力|guildpower|更新公告|更新内容|更新日志|补丁说明|patchnotes|更新资讯|图鉴|反配种|反向配种|反向|反查|反配|怎么配出|怎么配|如何配|配种路线|配种链|breedroute|配种|继承|词条继承|继承计算|词条遗传|遗传|继承率|inherit|哪里掉|哪里爆|掉落|爆什么|掉什么|爆率|drop|竞技场|竞技|斗技场|arena|物品|道具|设施|建筑|科技|技术|属性克制|克制图|克制|属性|element|栖息区域|栖息地|栖息|分布|habitat|推荐词条|推荐|词条|passive|任务攻略|任务|主线任务|主线|支线任务|支线|quest|mission|塔主|高塔|tower|突袭boss|突袭|raid|boss|BOSS|头目|首领|商人|商店|merchant|shop|哪里买|哪买|在哪买|哪里有卖|技能|主动技能|技能果实|skill|钓鱼|fishing|钓|工作适性|工作|适性|work|坐骑|骑乘|mount|对比|比较|compare|vs|料理|食物|做菜|cuisine|武器|weapon|帮助|菜单|绑定|我|档案|背包|物品栏|队伍|出战|帕鲁箱|箱子|箱|仓库|可孵化|可配种|可配|能配出|孵化|hatchable|查帕鲁|据点|基地|据点帕鲁|基地帕鲁|工作帕鲁|basecamp|base|症状|伤病|治疗|怎么治|cure|symptom|公会榜|公会肝帝榜|公会帕鲁箱|公会帕鲁|公会终端|工会帕鲁|公会|工会|guild|订阅|退订|取消订阅|找人|查人|喊话|喊人|喊|审计|日志|自检|诊断|健康检查|自检诊断|体检|selfcheck|healthcheck|地图|map|公告|踢|封|解封|解绑|unbind|重置存档|删档重开|删档|重开|重置世界|resetworld|reset|恢复存档|还原存档|恢复|还原|回档|回滚|rollback|备份列表|备份管理|备份|backups|backup|restore|重启服务器|重启服务|重启|restart|reboot|存档|关服|确认)")
    async def palworld(self, event: AstrMessageEvent):
        raw = (event.message_str or "").strip()
        # 去掉可选的「/」前缀和指令词「帕鲁」，剩余既可能是「在线」也可能是「在线 参数」
        if raw.startswith("/"):
            raw = raw[1:].lstrip()
        if raw.startswith("帕鲁"):
            raw = raw[len("帕鲁"):].strip()
        parts = raw.split()
        sub = parts[0] if parts else "状态"
        args = parts[1:]
        # 无空格粘连兜底：帕鲁图鉴皮皮鸡/帕鲁物品木材 -> 拆成 子命令+参数(未命中时才拆)
        sub, args = self._split_glued_sub(sub, args)
        # 安全：全局兜底限制参数个数/长度、清洗控制字符，防超长输入刷屏/撑大渲染(§8)。
        args = _security.clamp_args(args)

        # 自动登记本群为广播目标(上下线播报/掉线告警发往这些群)
        gid = event.get_group_id()
        if gid:
            self._register_group(str(gid))

        # 顶层异常兜底：单条脏数据/新版本枚举等导致的未预期异常，不把 traceback 抛给玩家
        try:
            async for result in self._dispatch(event, sub, args):
                yield result
        except Exception as e:  # noqa: BLE001
            logger.exception(f"{LOG_PREFIX} 指令「{sub}」处理异常: {e}")
            yield await self._msg_card(
                event, "⚠️", "出了点问题",
                desc="处理这条指令时出了点小状况，稍后再试～\n若持续失败请联系管理员。",
                color="#F5A623")

    # ------------------------------------------------------------------
    # Phase 4：LLM 工具（群友自然语言提问，bot 自动调用并出卡）
    # 需机器人本身启用了 LLM 并允许函数调用；插件只负责注册工具。
    # ------------------------------------------------------------------
    @filter.llm_tool(name="palworld_server_status")
    async def llm_server_status(self, event: AstrMessageEvent):
        """当用户用自然语言询问帕鲁(Palworld)游戏服务器的运行状态、当前在线人数、服务器开没开/在不在线、FPS、已运行多久、版本等总体情况时调用。会自动发送一张服务器状态卡片图。"""
        yield await self._cmd_status(event)

    @filter.llm_tool(name="palworld_online_players")
    async def llm_online_players(self, event: AstrMessageEvent):
        """当用户询问帕鲁服务器当前有哪些玩家在线、在线名单、有谁在玩、多少人在线时调用。会自动发送在线玩家列表卡片图。"""
        yield await self._cmd_players(event)

    @filter.llm_tool(name="palworld_server_settings")
    async def llm_server_settings(self, event: AstrMessageEvent):
        """当用户询问帕鲁服务器的设置、各种倍率(经验/捕捉/掉落)、难度、是否开启 PVP 等世界规则配置时调用。会自动发送服务器设置卡片图。"""
        yield await self._cmd_settings(event)

    async def _dispatch(self, event: AstrMessageEvent, sub: str, args: list[str]):
        # 注册表驱动分发（commands/router.py 的 CommandSpec）。行为与旧 if 链严格一致：
        # 未知→帮助；先管理员鉴权(必要时写警告日志)，再冷却门，最后按 pass_args/extra 调 handler。
        sender = str(event.get_sender_id())
        spec = COMMAND_ALIAS_MAP.get(sub)
        if spec is None:
            yield await self._cmd_help(event)
            return
        if spec.admin and not self._is_admin(sender):
            if spec.log_denied:
                logger.warning(f"{LOG_PREFIX} 非白名单用户 {sender} 尝试执行「{spec.canonical}」")
            yield await self._no_perm_card(event)
            return
        if spec.cooldown and not self._pass_cooldown(event):
            return
        handler = getattr(self, spec.handler)
        if spec.pass_args:
            yield await handler(event, args, *spec.extra)
        else:
            yield await handler(event, *spec.extra)

    # ------------------------------------------------------------------
    # 冷却
    # ------------------------------------------------------------------
    def _pass_cooldown(self, event: AstrMessageEvent) -> bool:
        # 不限流：任何人都能连发同样/不同样的指令，同群多人并发也各自都出图。
        # (服务器压力由存档服务(SaveService)的拉取锁 + 缓存 TTL 兜底，不需要前端冷却)
        return True

    # ------------------------------------------------------------------
    # 查询指令实现
    # ------------------------------------------------------------------
    async def _cmd_status(self, event: AstrMessageEvent):
        ok_m, metrics, status = await self._api_get("/v1/api/metrics")
        if not ok_m:
            return await self._query_fail_card(event, status)
        ok_i, info, _ = await self._api_get("/v1/api/info")
        info = info if ok_i and isinstance(info, dict) else {}
        m = metrics if isinstance(metrics, dict) else {}
        load = await self._docker_stats()   # 容器 CPU/内存(未挂 socket 时为 None)
        # 合并在线玩家列表(含在线时长，时长取自后台轮询记录的 since)
        ok_p, pdata, _ = await self._api_get("/v1/api/players")
        now = int(time.time())
        online_state = self.state.get("online", {})
        raw = (pdata or {}).get("players", []) if (ok_p and isinstance(pdata, dict)) else []
        players = []
        for p in raw:
            since = online_state.get(str(p.get("userId")), {}).get("since")
            players.append({
                "name": p.get("name", "未知"), "level": p.get("level", "?"),
                "ping": round(float(p.get("ping", 0))) if p.get("ping") is not None else 0,
                "ping_color": self._ping_color(p.get("ping")),
                "dur": self._fmt_uptime(now - since) if since else "",
            })
        return await self._img(event, self._t("status"), {
            "online": True,
            "servername": info.get("servername", "Palworld Server"),
            "version": info.get("version", "—"),
            "cur": m.get("currentplayernum", 0),
            "maxn": m.get("maxplayernum", 0),
            "fps": m.get("serverfps", "—"),
            "days": m.get("days", "—"),
            "uptime": self._fmt_uptime(m.get("uptime")),
            "load": load,
            "players": players,
        })

    async def _cmd_players(self, event: AstrMessageEvent):
        ok, data, status = await self._api_get("/v1/api/players")
        if not ok:
            return await self._query_fail_card(event, status)
        raw = (data or {}).get("players", []) if isinstance(data, dict) else []
        players = []
        for p in raw:
            players.append({
                "name": p.get("name", "未知"),
                "level": p.get("level", "?"),
                "ping": round(float(p.get("ping", 0))) if p.get("ping") is not None else 0,
                "ping_color": self._ping_color(p.get("ping")),
            })
        return await self._img(event, self._t("players"), {
            "players": players, "count": len(players),
        })

    async def _cmd_settings(self, event: AstrMessageEvent):
        ok, data, status = await self._api_get("/v1/api/settings")
        if not ok:
            return await self._query_fail_card(event, status)
        s = data if isinstance(data, dict) else {}
        items = []
        for label, key, suffix in SETTINGS_FIELDS:
            if key in s and s[key] is not None:
                val = s[key]
                if isinstance(val, float):
                    val = round(val, 2)
                items.append({"k": label, "v": f"{val}{suffix}"})
        # PVP 开关单独处理(布尔)
        pvp = s.get("bEnablePlayerToPlayerDamage")
        if pvp is not None:
            items.append({"k": "PVP", "v": "开启" if pvp else "关闭"})
        if not items:
            return await self._msg_card(
                event, "⚙️", "暂无可显示的设置",
                desc="服务器未返回可识别的设置字段。", head="⚙️ 服务器设置")
        return await self._img(event, self._t("settings"), {"items": items})

    async def _cmd_stats(self, event: AstrMessageEvent):
        return await self._img(event, self._t("stats"), self._stats_data())

    def _pal_power(self, brief: dict) -> int:
        """帕鲁综合战力评分(社区近似:基础三围×天赋×等级×浓缩×被动×alpha)。仅用于横向排序对比。"""
        p = self._pal_by_dev.get(str(brief.get("char_id", "")).lower())
        st = (p or {}).get("stats") or {}
        base = st.get("hp", 0) * 0.5 + st.get("shot_attack", 0) + st.get("defense", 0)
        if base <= 0:
            base = 100.0
        lvl = int(brief.get("level", 1) or 1)
        ivsum = (int(brief.get("iv_hp", 0) or 0) + int(brief.get("iv_atk", 0) or 0)
                 + int(brief.get("iv_def", 0) or 0))
        iv_factor = 1 + ivsum / 300.0          # 天赋 0~100 三项 → 最高 ×2
        lvl_factor = 1 + lvl * 0.04            # 等级成长(50级≈3倍)
        rank_factor = 1 + (int(brief.get("rank", 1) or 1) - 1) * 0.1   # 浓缩 1~5
        pb = 0.0
        for pid in brief.get("passives", []):
            sign = self._passive_view(pid).get("sign", 0)
            pb += 0.05 if sign > 0 else (-0.05 if sign < 0 else 0)
        alpha = 1.2 if brief.get("is_alpha") else 1.0
        return int(base * iv_factor * lvl_factor * rank_factor * (1 + pb) * alpha)

    # 无主(据点公会共享)帕鲁在存档里被复制进每个成员档案，跨玩家聚合时需按 iid 去重，
    # 归到统一的"据点共享"名下只计一次，避免同一只被计 N 次 / 挂 N 个主人。
    _SHARED_OWNER = "🏰 据点共享"

    def _iter_prof_pals(self, prof: dict, seen_shared: set, include_shared: bool = True):
        """遍历单个档案的 队伍/箱/据点 帕鲁，yield (pal, owner_label)。
        跨玩家聚合时对共享据点帕鲁按 iid 去重(seen_shared)——只在首次出现时产出一次，
        归到 _SHARED_OWNER；include_shared=False 时(玩家个人向排行)彻底排除共享帕鲁。"""
        owner = prof.get("nickname") or "?"
        for keyn in ("party", "palbox", "basecamp"):
            for pal in prof.get(keyn, []):
                if pal.get("shared"):
                    iid = str(pal.get("iid") or "")
                    if not iid or iid in seen_shared:
                        continue          # 无 iid 无法去重 / 已计过 -> 跳过，绝不重复计
                    seen_shared.add(iid)
                    if not include_shared:
                        continue          # 个人向排行(资产/图鉴)不把公会共享帕鲁算给任何个人
                    yield pal, self._SHARED_OWNER
                else:
                    yield pal, owner

    async def _cmd_power_rank(self, event: AstrMessageEvent):
        """全服战力榜：遍历所有玩家的队伍/箱/据点帕鲁，按综合战力 Top15。"""
        self._last_save_use = time.time()
        profiles = await self._fetch_save_profiles()
        if not profiles:
            return await self._msg_card(
                event, "🛰️", "暂时读不到存档",
                desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        allpals = []
        seen_shared = set()
        for prof in profiles.values():
            for pal, owner in self._iter_prof_pals(prof, seen_shared):
                allpals.append((self._pal_power(pal), pal, owner))
        if not allpals:
            return await self._msg_card(event, "📦", "全服暂无帕鲁",
                                        desc="存档里还没有可统计的帕鲁。", color="#9a8a91")
        allpals.sort(key=lambda x: -x[0])
        top = allpals[:15]
        mxp = top[0][0] or 1
        rows = []
        for i, (pw, pal, owner) in enumerate(top, 1):
            p = self._pal_by_dev.get(str(pal.get("char_id", "")).lower())
            name = pal.get("nickname") or (p or {}).get("pal_name") or pal.get("char_id", "?")
            rows.append({
                "rank": i, "name": _esc(name), "owner": _esc(owner),
                "level": pal.get("level", 1), "power": pw, "pct": int(pw / mxp * 100),
                "icon": self._pal_icon((p or {}).get("pal_dev_name", "")),
                "lucky": bool(pal.get("lucky")), "alpha": bool(pal.get("is_alpha")),
                "medal": ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)})
        return await self._img(event, self._t("power"),
                               {"rows": rows, "sub": f"全服最强帕鲁 Top{len(rows)} · 共 {len(allpals)} 只"})

    async def _collection_wall(self, event, field, title, badge, label, empty):
        """收藏墙通用：遍历全服帕鲁筛 field(lucky/is_alpha) 为真的，网格展示。"""
        self._last_save_use = time.time()
        profiles = await self._fetch_save_profiles()
        if not profiles:
            return await self._msg_card(
                event, "🛰️", "暂时读不到存档",
                desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        items, owner_cnt = [], {}
        seen_shared = set()
        for prof in profiles.values():
            for pal, owner in self._iter_prof_pals(prof, seen_shared):
                if pal.get(field):
                    p = self._pal_by_dev.get(str(pal.get("char_id", "")).lower())
                    name = pal.get("nickname") or (p or {}).get("pal_name") or pal.get("char_id", "?")
                    items.append({"name": _esc(name), "owner": _esc(owner), "badge": badge,
                                  "icon": self._pal_icon((p or {}).get("pal_dev_name", ""))})
                    owner_cnt[owner] = owner_cnt.get(owner, 0) + 1
        if not items:
            return await self._msg_card(event, badge, f"全服还没有{label}帕鲁",
                                        desc=empty, color="#9a8a91")
        items.sort(key=lambda x: x["owner"])     # 同主人聚一起
        owners = sorted(owner_cnt.items(), key=lambda x: -x[1])
        top = " ".join(f"{_esc(o)}×{c}" for o, c in owners[:3])
        return await self._img(event, self._t("shiny"), {
            "title": title, "badge": badge, "rows": items[:30],
            "sub": f"共 {len(items)} 只{label} · {len(owner_cnt)} 位训练师", "top_owners": top})

    async def _cmd_shiny(self, event: AstrMessageEvent):
        return await self._collection_wall(
            event, "lucky", "✨ 全服闪光墙", "✨", "闪光",
            "闪光(幸运)帕鲁非常稀有～多抓多孵，第一只闪光说不定就是你的！")

    async def _cmd_alpha(self, event: AstrMessageEvent):
        return await self._collection_wall(
            event, "is_alpha", "👑 全服头目墙", "👑", "头目",
            "头目(Alpha)是地图上的强力 BOSS 帕鲁，捕获它们填满这面墙吧！")

    _WEEK_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    async def _cmd_heatmap(self, event: AstrMessageEvent):
        """在线热力图：按 星期×小时 的平均在线人数着色(7×24)。数据由后台轮询埋点累积。"""
        heat = self.state.get("heat", {})
        total_samples = sum(v[1] for v in heat.values() if isinstance(v, list) and len(v) == 2)
        if total_samples < 48:    # 数据太少(不足约1天)先不出图，避免误导
            return await self._msg_card(
                event, "📊", "热力数据攒集中",
                desc=f"在线热力图需要后台持续采样，目前样本还太少（{total_samples}）。\n"
                     "过一两天数据多了再来看～", color="#F5A623", head="🔥 在线热力图")
        # 计算每格平均在线，找峰值用于归一化着色
        avg = {}
        mx = 0.0
        for wd in range(7):
            for h in range(24):
                b = heat.get(f"{wd}-{h}")
                if b and b[1] > 0:
                    a = b[0] / b[1]
                    avg[(wd, h)] = a
                    mx = max(mx, a)
        rows = []
        peak = (0.0, 0, 0)   # (avg, wd, h)
        for wd in range(7):
            cells = []
            for h in range(24):
                a = avg.get((wd, h), 0.0)
                if a > peak[0]:
                    peak = (a, wd, h)
                if a <= 0 or mx <= 0:
                    lvl = 0
                else:
                    lvl = min(4, int(a / mx * 4 + 0.999) or 1)   # 1~4 档
                cells.append(lvl)
            rows.append({"label": self._WEEK_CN[wd], "cells": cells})
        days = max(1, total_samples * self._poll_interval() // 86400)
        sub = f"按星期×小时的平均在线人数 · 累计采样约 {days} 天"
        hint = ""
        if peak[0] > 0:
            hint = f"最热时段：{self._WEEK_CN[peak[1]]} {peak[2]:02d}:00 前后（约 {peak[0]:.1f} 人）"
        return await self._img(event, self._t("heatmap"),
                               {"rows": rows, "sub": sub, "hint": hint})

    async def _cmd_rank(self, event: AstrMessageEvent):
        raw = self._rank_list(10)
        maxsec = raw[0]["sec"] if raw else 1
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rows = []
        for i, r in enumerate(raw, 1):
            rows.append({
                "name": _esc(r["name"]), "online": r["online"],
                "dur": self._fmt_uptime(r["sec"]),
                "pct": round(r["sec"] / maxsec * 100) if maxsec else 0,
                "medal": medals.get(i, str(i)),
            })
        return await self._img(event, self._t("rank"), {"rows": rows})

    async def _cmd_dex_rank(self, event: AstrMessageEvent):
        """图鉴收集榜：全服玩家按拥有的不同帕鲁种类数排行(复用 rank 模板)。"""
        self._last_save_use = time.time()
        profiles = await self._fetch_save_profiles()
        if not profiles:
            return await self._msg_card(
                event, "🛰️", "暂时读不到存档",
                desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        total = len(self._pals) or 1
        board = []
        seen_shared = set()
        for prof in profiles.values():
            species = set()
            for pal, owner in self._iter_prof_pals(prof, seen_shared, include_shared=False):
                p = self._pal_by_dev.get(str(pal.get("char_id", "")).lower())
                if p and p.get("pal_index"):
                    species.add(p["pal_index"])
            if species:
                board.append((len(species), prof.get("nickname") or "?"))
        if not board:
            return await self._msg_card(event, "📖", "暂无图鉴数据",
                                        desc="还没有可统计的玩家帕鲁收集。", color="#9a8a91")
        board.sort(key=lambda x: -x[0])
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rows = []
        for i, (n, owner) in enumerate(board[:15], 1):
            rows.append({"name": _esc(owner), "online": False,
                         "dur": f"{n}/{total}", "pct": round(n / total * 100),
                         "medal": medals.get(i, str(i))})
        return await self._img(event, self._t("rank"), {
            "rows": rows, "rank_title": "📖 图鉴收集榜",
            "rank_sub": f"全服图鉴收集进度 · 共 {total} 种 · {len(board)} 位训练师"})

    async def _cmd_wealth(self, event: AstrMessageEvent):
        """帕鲁资产榜：全服玩家按所有帕鲁的总身价(paldex price)排行(复用 rank 模板)。"""
        self._last_save_use = time.time()
        profiles = await self._fetch_save_profiles()
        if not profiles:
            return await self._msg_card(
                event, "🛰️", "暂时读不到存档",
                desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        board = []
        seen_shared = set()
        for prof in profiles.values():
            worth, cnt = 0, 0
            for pal, owner in self._iter_prof_pals(prof, seen_shared, include_shared=False):
                p = self._pal_by_dev.get(str(pal.get("char_id", "")).lower())
                if p:
                    worth += int(p.get("price", 0) or 0)
                    cnt += 1
            if worth > 0:
                board.append((worth, prof.get("nickname") or "?", cnt))
        if not board:
            return await self._msg_card(event, "💰", "暂无资产数据",
                                        desc="还没有可估值的玩家帕鲁。", color="#9a8a91")
        board.sort(key=lambda x: -x[0])
        mx = board[0][0] or 1
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rows = []
        for i, (worth, owner, cnt) in enumerate(board[:15], 1):
            rows.append({"name": f"{_esc(owner)}（{cnt}只）", "online": False,
                         "dur": f"{worth:,}", "pct": round(worth / mx * 100),
                         "medal": medals.get(i, str(i))})
        return await self._img(event, self._t("rank"), {
            "rows": rows, "rank_title": "💰 帕鲁资产榜",
            "rank_sub": f"全服帕鲁总身价排行(金币) · {len(board)} 位训练师"})

    async def _cmd_guild_power(self, event: AstrMessageEvent):
        """公会战力榜：各公会成员帕鲁战力总和排行(复用 rank 模板，无公会名用队长代称)。"""
        self._last_save_use = time.time()
        data = await self._fetch_save_data()
        profiles = (data or {}).get("profiles") if data else None
        guilds = (data or {}).get("guilds") if data else None
        if not profiles or not guilds:
            return await self._msg_card(
                event, "🛰️", "暂时读不到公会/存档",
                desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")

        def norm(x):
            return str(x).replace("-", "").upper()
        prof_by_norm = {norm(k): v for k, v in profiles.items()}
        board = []
        seen_shared = set()   # 共享据点帕鲁全局去重：同一只只计入一个公会一次，不跨会/跨员重复累加
        for g in guilds:
            total = 0
            members = g.get("members", [])
            for m in members:
                prof = prof_by_norm.get(norm(m.get("uid", "")))
                if not prof:
                    continue
                for pal, owner in self._iter_prof_pals(prof, seen_shared):
                    total += self._pal_power(pal)
            if total <= 0:
                continue
            leader = next((m["name"] for m in members if m.get("uid") == g.get("admin_uid")),
                          (members[0]["name"] if members else "?"))
            board.append((total, leader, len(members)))
        if not board:
            return await self._msg_card(event, "⚔️", "暂无公会战力数据",
                                        desc="还没有可统计的公会帕鲁战力。", color="#9a8a91")
        board.sort(key=lambda x: -x[0])
        mx = board[0][0] or 1
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rows = []
        for i, (total, leader, mcnt) in enumerate(board[:15], 1):
            rows.append({"name": f"{_esc(leader)} 的公会（{mcnt}人）", "online": False,
                         "dur": f"{total:,}", "pct": round(total / mx * 100),
                         "medal": medals.get(i, str(i))})
        return await self._img(event, self._t("rank"), {
            "rows": rows, "rank_title": "⚔️ 公会战力榜",
            "rank_sub": f"各公会成员帕鲁战力总和 · {len(board)} 个公会"})

    async def _cmd_help(self, event: AstrMessageEvent):
        # 一行一条指令，玩家一眼看清；指令清单硬编码在 HELP_TMPL 模板里。
        return await self._img(event, self._t("help"), {})

    # ------------------------------------------------------------------
    # Phase 3：玩家绑定 / 个人卡 / 订阅
    # ------------------------------------------------------------------
    def _find_player_by_name(self, name: str):
        """按游戏名在 当前在线 / 历史记录 中找 userId。返回 (uid, info) 或 (None, None)。"""
        for uid, info in self.state.get("online", {}).items():
            if info.get("name") == name:
                return uid, info
        for uid, t in self.state.get("totals", {}).items():
            if t.get("name") == name:
                return uid, {"name": t.get("name")}
        return None, None

    def _profile_data(self, qq: str):
        b = self.state.get("bindings", {}).get(str(qq))
        if not b:
            return None
        name = b.get("name")
        uid = b.get("userId") or ""
        online = self.state.get("online", {})
        info = online.get(uid) if uid else None
        if not info:    # uid 缺失或变了，用名字兜底
            for u, i in online.items():
                if i.get("name") == name:
                    info, uid = i, u
                    break
        is_on = info is not None
        level = info.get("level", "?") if info else "?"
        wk = self._week_id()
        t = self.state.get("totals", {}).get(uid, {}) if uid else {}
        week = t.get("week", 0) if t.get("week_id") == wk else 0
        total = t.get("total", 0)
        # 本周排名
        rl = [(u, (tt.get("week", 0) if tt.get("week_id") == wk else 0))
              for u, tt in self.state.get("totals", {}).items()]
        rl = sorted([x for x in rl if x[1] > 0], key=lambda x: x[1], reverse=True)
        rank = "—"
        for idx, (u, _) in enumerate(rl, 1):
            if u == uid:
                rank = f"#{idx}"
                break
        return {"name": _esc(name), "online": is_on, "level": level,
                "week_dur": self._fmt_uptime(int(week)), "total_dur": self._fmt_uptime(int(total)),
                "rank": rank, "titles": self._titles_for(uid, str(qq))}

    def _do_bind(self, qq: str, uid: str, name: str):
        """落库一条绑定（以 userId 为主键，名字仅作显示）。"""
        bs = self.state.setdefault("bindings", {})
        ts = bs.get(qq, {}).get("ts") or int(time.time())   # 保留首次绑定时间(开荒元老用)
        bs[qq] = {"name": name, "userId": uid, "ts": ts}
        self._save_state()

    def _bind_owner(self, uid: str, exclude_qq: str = "") -> Optional[str]:
        """返回已绑定该 userId 的其它 QQ(排除 exclude_qq)；无则 None。
        用于阻止冒名绑定他人角色(绑定即可绕过'查他人仅管理员'门控查看私密档案)。"""
        u = str(uid or "").replace("-", "").upper()
        if not u:
            return None
        for q, b in (self.state.get("bindings", {}) or {}).items():
            if str(q) == str(exclude_qq):
                continue
            if str(b.get("userId") or "").replace("-", "").upper() == u:
                return str(q)
        return None

    async def _do_bind_checked(self, event, qq: str, uid: str, name: str, ok_desc: str):
        """带归属校验的绑定：该角色已被别的 QQ 绑定则拒绝，否则落库并回成功卡。"""
        if self._bind_owner(uid, qq):
            return await self._msg_card(
                event, "🔒", "该角色已被绑定",
                desc="这个游戏角色已被其他 QQ 绑定，无法重复绑定。\n"
                     "如需换绑，请联系管理员用 /帕鲁解绑 <QQ或角色名> 先解绑。",
                color="#E5484D")
        self._do_bind(qq, uid, name)
        return await self._msg_card(event, "🔗", "绑定成功", desc=_esc(ok_desc), color="#30A46C")

    async def _bind_ambiguous_card(self, event, name, cands):
        """同名多人，列候选让用户用 userId 精确绑定。"""
        lines = [f"• {_esc(c['name'])} Lv.{c.get('level', '—')} → {c['uid']}" for c in cands]
        return await self._msg_card(
            event, "🧭", "有多个同名玩家",
            desc=f"「{_esc(name)}」对应多个账号，请复制你的 userId 精确绑定：\n" + "\n".join(lines)
                 + "\n\n然后发：/帕鲁绑定 <上面的 userId>",
            head="🔗 绑定 · 需指定", color="#F5A623")

    async def _cmd_bind(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            return await self._msg_card(event, "✏️", "请提供游戏角色名",
                                        desc="用法：/帕鲁绑定 <游戏名>\n请在游戏内在线时绑定，我才能精确认出你。",
                                        color="#E5484D")
        arg = " ".join(args).strip()
        qq = str(event.get_sender_id())
        online = self.state.get("online", {})
        totals = self.state.get("totals", {})

        # 方案B：直接按 userId 绑定（已知 userId 或 steam_ 前缀）
        if arg in online or arg in totals or arg.lower().startswith("steam_"):
            info = online.get(arg) or totals.get(arg)
            if not info:
                return await self._msg_card(event, "❓", "未找到该 userId",
                                            desc=f"`{_esc(arg)}` 没在在线/历史记录里出现过，请确认无误，或上线后用游戏名绑定。",
                                            color="#E5484D")
            return await self._do_bind_checked(
                event, qq, arg, info.get("name", "玩家"),
                f"已绑定到角色「{info.get('name', '玩家')}」。\n发 /帕鲁我 查看个人档案。")

        # 方案A：按游戏名，优先在线精确定位 userId
        on = [{"uid": uid, "name": i.get("name"), "level": i.get("level", "—")}
              for uid, i in online.items() if i.get("name") == arg]
        if len(on) == 1:
            return await self._do_bind_checked(
                event, qq, on[0]["uid"], arg,
                f"已绑定到在线角色「{arg}」。\n发 /帕鲁我 查看个人档案。")
        if len(on) >= 2:
            return await self._bind_ambiguous_card(event, arg, on)
        # 不在线，退而查历史
        hist = [{"uid": uid, "name": t.get("name"), "level": "—"}
                for uid, t in totals.items() if t.get("name") == arg]
        if len(hist) == 1:
            return await self._do_bind_checked(
                event, qq, hist[0]["uid"], arg,
                f"已绑定到角色「{arg}」（按历史记录）。\n发 /帕鲁我 查看个人档案。")
        if len(hist) >= 2:
            return await self._bind_ambiguous_card(event, arg, hist)
        return await self._msg_card(event, "🌙", "没找到这个角色",
                                    desc=f"在线和历史里都没有「{_esc(arg)}」。请**先上线**再发 /帕鲁绑定 <游戏名>，"
                                         f"这样我才能精确认出你的账号。", color="#F5A623")

    async def _cmd_unbind(self, event: AstrMessageEvent, args: list[str]):
        """管理员解绑：/帕鲁解绑 <QQ号 或 角色名>。用于换绑/纠错(冒名绑定的清除)。"""
        if not args:
            return await self._msg_card(event, "✏️", "请提供要解绑的 QQ 或角色名",
                                        desc="用法：/帕鲁解绑 <QQ号 或 角色名>", color="#E5484D")
        key = " ".join(args).strip()
        bs = self.state.get("bindings", {}) or {}
        removed = []
        if key in bs:   # 按 QQ 精确解绑
            removed.append((key, bs[key].get("name")))
            del bs[key]
        else:           # 按角色名解绑(可能命中多个)
            for q, b in list(bs.items()):
                if b.get("name") == key:
                    removed.append((q, b.get("name")))
                    del bs[q]
        if not removed:
            return await self._msg_card(event, "🔍", "没找到该绑定",
                                        desc=f"没有 QQ 或角色名为「{_esc(key)}」的绑定记录。", color="#F5A623")
        self._save_state()
        lines = "\n".join(f"• QQ {q} → {_esc(n)}" for q, n in removed)
        return await self._msg_card(event, "🔓", "已解绑",
                                    desc=f"已解除以下绑定：\n{lines}\n对应用户可重新 /帕鲁绑定。",
                                    color="#30A46C")

    async def _fetch_qq_avatar(self, qq: str) -> str:
        """QQ 头像 -> base64 data URI（缓存 1 天）。失败返回空串(模板退回表情)。"""
        qq = str(qq)
        if not qq.isdigit():
            return ""
        cache = getattr(self, "_avatar_cache", None)
        if cache is None:
            cache = self._avatar_cache = {}
        hit = cache.get(qq)
        if hit and time.time() - hit[0] < 86400:
            return hit[1]
        url = f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"
        uri = ""
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status == 200:
                        b = await r.read()
                        if len(b) > 800:   # 太小多半是默认占位图，仍可用
                            uri = "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"{LOG_PREFIX} QQ头像获取失败: {e}")
        cache[qq] = (time.time(), uri)
        return uri

    async def _cmd_profile(self, event: AstrMessageEvent):
        qq = str(event.get_sender_id())
        data = self._profile_data(qq)
        if not data:
            return await self._msg_card(event, "🔗", "你还没绑定角色",
                                        desc="先发 /帕鲁绑定 <游戏名> 绑定你的帕鲁角色，再用 /帕鲁我 查看档案。",
                                        color="#F5A623")
        self._last_save_use = time.time()   # 标记活跃，让后台预热持续保温缓存
        sp = None
        profiles = await self._fetch_save_profiles(max_age=self._fresh_ttl())
        if profiles:
            sp = self._match_save_profile(self.state.get("bindings", {}).get(qq), profiles)
        data.update(self._profile_save_extra(sp))
        data["avatar"] = await self._fetch_qq_avatar(qq)
        return await self._img(event, self._t("profile"), data)

    # ---- 存档档案展示构建 ----
    @staticmethod
    def _gender_cn(g: str) -> str:
        return {"male": "♂ 公", "female": "♀ 母"}.get(g, "")

    # 玩家状态点 日文内部名 -> 中文(与游戏内"状态点"界面一致)
    _STATUS_CN = {"最大HP": "生命值", "最大SP": "耐力", "攻撃力": "攻击力",
                  "所持重量": "负重", "捕獲率": "捕获力", "作業速度": "工作速度"}
    _STATUS_ORDER = ["最大HP", "最大SP", "攻撃力", "所持重量", "捕獲率", "作業速度"]

    def _status_view(self, status: dict) -> list:
        """玩家加点 -> [{name, points}]，固定 6 项顺序。"""
        status = status or {}
        return [{"name": self._STATUS_CN[k], "points": int(status.get(k, 0) or 0)}
                for k in self._STATUS_ORDER]

    def _passive_view(self, pid: str) -> dict:
        """词条 id -> 展示字段。rank 1~4(4=传说级)，sign 正/负/中。未知词条原样显示。"""
        meta = (self._passives or {}).get(pid) or {}
        rank = int(meta.get("rank", 0) or 0)
        sign = int(meta.get("sign", 0) or 0)
        # 配色：负面=红；正面按 rank 金/紫/蓝/青；中性=灰
        if sign < 0:
            color = "bad"
        elif rank >= 4:
            color = "legend"
        elif rank == 3:
            color = "epic"
        elif rank == 2:
            color = "rare"
        elif rank == 1:
            color = "common"
        else:
            color = "neutral"
        return {"name": meta.get("name") or pid, "rank": rank, "sign": sign,
                "effect": meta.get("effect", ""), "color": color,
                "arrows": ("▾" if sign < 0 else "▴") * (rank if rank else 1)}

    def _waza_name(self, wid: str) -> str:
        wid = str(wid).split("::")[-1]   # 容错：去掉可能残留的 EPalWazaID:: 前缀
        return (self._wazas or {}).get(wid, wid)

    def _waza_view(self, wid: str) -> dict:
        """技能枚举 -> 展示字段(中文名 + 属性 + 威力 + 简短描述)。"""
        name = self._waza_name(wid)
        d = (self._skill_by_name or {}).get(name, {})
        return {"name": name, "elem": d.get("elem", ""), "power": d.get("power", 0),
                "cd": d.get("cd", 0), "desc": d.get("desc", "")}

    # 帕鲁健康状态(存档 PhysicalHealth) -> (中文标签, 卡片配色档)。健康时存档无该字段。
    _HEALTH_CN = {"Dying": ("濒死", "bad"), "Severe": ("重伤", "warn"),
                  "MinorInjury": ("轻伤", "warn"), "MediumInjury": ("中伤", "warn"),
                  "MajorInjury": ("重伤", "warn"), "Fracture": ("骨折", "warn"),
                  "Weakness": ("虚弱", "warn"), "Cold": ("感冒", "warn"),
                  "Bruise": ("擦伤", "warn"), "Depression": ("消沉", "warn")}

    # 帕鲁伤病/低状态 -> {治疗方法, 可用道具item_id}(游戏知识)。用于 /帕鲁症状(图文卡) + 据点提示。
    # 帕鲁机制：药品(Herbs/Medicines/LuxuryMedicines)治「伤病状态」；恢复药(Potion)回HP；
    # SAN 无专门药，靠 温泉/床休息 + 高级料理 + 减少加班。
    _SYMPTOM_CURE = {
        "濒死": {"desc": "HP 危急！放进「帕鲁终端(圆桌)」会自动慢慢恢复；紧急时喂恢复药或复活药。",
                 "items": ["Potion_High", "Potion", "PalRevive", "PalHealingGrenade"]},
        "轻伤": {"desc": "喂「低品质药品」，或让它休息一会即可恢复。",
                 "items": ["Herbs", "Medicines"]},
        "中伤": {"desc": "喂「药品」治疗，或让它在牧场/床上休息自愈。",
                 "items": ["Medicines", "Herbs"]},
        "重伤": {"desc": "喂「药品」治疗伤病，或让它在牧场/床上休息自愈。伤越重用越高级的药品。",
                 "items": ["LuxuryMedicines", "Medicines", "Herbs"]},
        "骨折": {"desc": "喂「高品质药品」，或在据点建「床」让它躺床休息恢复。",
                 "items": ["LuxuryMedicines", "Medicines"]},
        "虚弱": {"desc": "喂「药品」+ 让它休息即可恢复。",
                 "items": ["Medicines", "Herbs"]},
        "感冒": {"desc": "喂「药品」退烧治疗。",
                 "items": ["Medicines", "Herbs"]},
        "擦伤": {"desc": "喂「低品质药品」或让它休息一会。",
                 "items": ["Herbs", "Medicines"]},
        "消沉": {"desc": "SAN 太低导致。建「温泉」泡澡、「床」休息，喂高级料理，别连续加班。",
                 "items": ["Pizza", "Cake", "Hamburger"]},
        "低SAN": {"desc": "SAN(理智)低没有专门药——建「温泉」让它泡澡回 SAN、建「床」休息、"
                          "喂高级料理(披萨/蛋糕等)、减少连续加班。SAN 归零会摸鱼甚至发疯逃跑。",
                  "items": ["Pizza", "Cake", "Hamburger", "Salad"]},
        "饥饿": {"desc": "在据点放「饲料箱」并补充食材，或建牧场让它自产口粮。",
                 "items": ["Salad", "Pizza", "CheeseBurger"]},
        "挨饿": {"desc": "已经饿坏了！赶紧在据点放「饲料箱」补满食材，或建牧场自产口粮，否则会掉血。",
                 "items": ["Salad", "Pizza", "CheeseBurger", "Hamburger"]},
        "扭伤": {"desc": "据点工作伤——在据点建「床」让它躺床休息恢复，或喂「药品」。",
                 "items": ["Medicines", "Herbs"]},
        "消沉扭伤": {"desc": "又消沉又扭伤(SAN低+受伤)：建「温泉」泡澡回SAN、「床」休息，喂高级料理，扭伤会一起养好。",
                     "items": ["Pizza", "Cake", "Medicines"]},
        "发烧": {"desc": "喂「药品」退烧，让它在床上休息。",
                 "items": ["Medicines", "Herbs"]},
        "挫伤": {"desc": "喂「低品质药品」或让它休息一会。",
                 "items": ["Herbs", "Medicines"]},
    }
    # 据点帕鲁真实状态枚举 -> 中文(FullStomach/SanityValue 是真实值，断粮会归 0；
    # 饥饿状态另用 HungerType 校验、工作病看 WorkerSick)。中文名与 _SYMPTOM_CURE 的 key 对齐。
    _HUNGER_CN = {"Starvation": "挨饿", "Hunger": "饥饿", "Hungry": "饥饿"}   # Normal/空=正常
    _WORKERSICK_CN = {"Weakness": "虚弱", "Sprain": "扭伤", "DepressionSprain": "消沉扭伤",
                      "Depression": "消沉", "Cold": "感冒", "Fever": "发烧",
                      "Bruise": "挫伤", "BoneFracture": "骨折", "Fracture": "骨折"}

    @classmethod
    def _health_view(cls, health: str) -> dict:
        """'' / Good=健康(无标记)；Dying=濒死(放终端可恢复)；Severe=重伤。"""
        h = str(health or "").split("::")[-1]
        if h in ("", "Good"):
            return {"hurt": False, "label": "", "tone": ""}
        label, tone = cls._HEALTH_CN.get(h, (h, "warn"))
        return {"hurt": True, "label": label, "tone": tone}

    @staticmethod
    def _rarity_tier(rarity: int) -> str:
        """图鉴稀有度 -> 配色档(与游戏帕鲁箱底框色一致)。"""
        r = int(rarity or 0)
        if r >= 20:
            return "legend"     # 传说(红/彩)
        if r >= 10:
            return "epic"       # 史诗(金)
        if r >= 8:
            return "rare"       # 稀有(紫)
        if r >= 5:
            return "uncommon"   # 优良(蓝)
        return "common"         # 普通(灰)

    def _safe_views(self, fn, items, label: str = "") -> list:
        """对一批记录逐条套用视图构建 fn，坏的那条跳过并 log，不拖垮整张卡。
        用于队伍/据点等"遍历多条记录构卡"的循环，容忍新版本新字段/脏数据。"""
        out = []
        for it in items or []:
            try:
                out.append(fn(it))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 跳过异常{label}记录 {it!r}: {e}")
        return out

    def _pal_view(self, pal: dict) -> dict:
        """_pal_brief 原始字段 -> 卡片展示字段(中文名/图标/属性/词条/技能)。"""
        p = self._pal_by_dev.get(str(pal.get("char_id", "")).lower())
        condense = max(0, int(pal.get("rank", 1) or 1) - 1)   # 浓缩星 0~4
        rarity = int((p.get("rarity") if p else 0) or 0)
        # 种族基础值 / 工作速度 / 工作适性 / 伙伴技能（均来自图鉴 paldex，准确数据）
        stats = (p.get("stats") or {}) if p else {}
        wsu = (p.get("work_suitability") or {}) if p else {}
        works = sorted(
            ({"name": WORK_LABELS.get(k, k), "icon": WORK_ICON.get(k, "⚙️"), "level": int(v)}
             for k, v in wsu.items() if v and int(v) > 0),
            key=lambda w: -w["level"])
        partner = {"title": p.get("partner_skill_title", "") if p else "",
                   "desc": p.get("partner_skill_description", "") if p else ""}
        return {
            "name": p["pal_name"] if p else pal.get("char_id", "未知帕鲁"),
            "index": str(p.get("pal_index", "")) if p else "",
            "icon": self._pal_icon(p.get("pal_dev_name")) if p else "",
            "elements": p.get("elements", []) if p else [],
            "level": pal.get("level", 1), "gender": self._gender_cn(pal.get("gender", "")),
            "alpha": bool(pal.get("is_alpha")), "lucky": bool(pal.get("lucky")),
            "nickname": _esc(pal.get("nickname", "")), "hp": pal.get("hp", 0),
            "health": self._health_view(pal.get("health", "")),
            "condense": condense, "rarity": rarity, "rtier": self._rarity_tier(rarity),
            "iv_hp": pal.get("iv_hp", 0), "iv_atk": pal.get("iv_atk", 0), "iv_def": pal.get("iv_def", 0),
            "passives": [self._passive_view(x) for x in pal.get("passives", [])],
            "wazas": [self._waza_view(x) for x in pal.get("equip_waza", [])],
            "base_atk": int(stats.get("shot_attack") or stats.get("melee_attack") or 0),
            "base_def": int(stats.get("defense") or 0),
            "craft_speed": int((p.get("craft_speed") if p else 0) or 0),
            "works": works, "partner": partner,
        }

    def _profile_save_extra(self, sp: Optional[dict]) -> dict:
        """个人卡的存档区块数据。无存档时 has_save=False(模板隐藏该区)。"""
        if not sp:
            return {"has_save": False, "s_level": 0, "tech": 0, "recipes": 0,
                    "hp": 0, "shield": 0, "stomach": 0, "status": [],
                    "max_hp": 0, "max_sp": 0, "weight": 0,
                    "party": [], "party_n": 0, "bag_n": 0,
                    "palbox_n": 0, "pal_total": 0, "dex_owned": 0, "dex_total": 0, "hurt_n": 0}
        party = [self._pal_view(p) for p in sp.get("party", [])]
        palbox = sp.get("palbox", [])
        allpals = list(party) + palbox   # 队伍是已渲染视图，箱是原始；只用于计数/收集
        # 图鉴收集度：拥有的不同种类数（按 char_id 去重）
        owned_species = set()
        hurt_n = 0
        for p in palbox:
            cid = str(p.get("char_id", "")).lower()
            if cid in self._pal_by_dev:
                owned_species.add(self._pal_by_dev[cid].get("pal_index"))
            if self._health_view(p.get("health", "")).get("hurt"):
                hurt_n += 1
        for p in party:
            if p.get("index"):
                owned_species.add(p["index"])
            if p.get("health", {}).get("hurt"):
                hurt_n += 1
        # 玩家面板真实数值：存档只存「当前HP」与「投点」，最大值由 基础 + 投点 算出
        #   最大HP=500+HP点×100(存档双样本实测吻合)；最大耐力=100+SP点×10；负重=300+重量点×50
        st_raw = sp.get("status") or {}
        def _pt(k):
            return int(st_raw.get(k, 0) or 0)
        max_hp = 500 + _pt("最大HP") * 100
        max_sp = 100 + _pt("最大SP") * 10
        weight = 300 + _pt("所持重量") * 50
        return {"has_save": True, "s_level": sp.get("level", 1),
                "tech": sp.get("tech_points", 0), "recipes": sp.get("recipes", 0),
                "hp": sp.get("hp", 0), "shield": sp.get("shield", 0),
                "stomach": sp.get("stomach", 0), "status": self._status_view(sp.get("status")),
                "max_hp": max_hp, "max_sp": max_sp, "weight": weight,
                "party": party, "party_n": len(party),
                "bag_n": len(sp.get("inventory", [])),
                "palbox_n": len(palbox), "pal_total": len(party) + len(palbox),
                "dex_owned": len({x for x in owned_species if x}),
                "dex_total": len(self._pals or []), "hurt_n": hurt_n}

    def _inv_cells(self, sp: dict) -> list:
        """背包物品 -> 卡片格子(中文名+图标+数量)，按品类再按数量排序。"""
        cells = []
        for it in sp.get("inventory", []):
            try:
                meta = self._item_by_id.get(it.get("id"))
                cells.append({"name": meta["name"] if meta else it.get("id", "?"),
                              "icon": self._item_icon(it.get("id")),
                              "cat": self._item_category(meta.get("type")) if meta else "",
                              "count": it.get("count", 1)})
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 跳过异常背包物品 {it!r}: {e}")
        cells.sort(key=lambda c: (c["cat"], -c["count"]))
        return cells

    async def _resolve_target_sp(self, event: AstrMessageEvent, args: list[str]):
        """解析背包/队伍的查询目标。返回 (sp, 显示名, 错误结果)。
        无参=查自己；带名=仅管理员可查他人(炫耀向公开+详细仅本人/管理 的'详细'走自己/管理)。"""
        qq = str(event.get_sender_id())
        self._last_save_use = time.time()   # 标记活跃，让后台预热持续保温缓存
        profiles = await self._fetch_save_profiles(max_age=self._fresh_ttl())
        if not profiles:
            return None, "", await self._msg_card(
                event, "🛰️", "暂时读不到存档",
                desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        name = " ".join(args).strip()
        if name:   # 查他人 -> 仅管理员
            if not self._is_admin(qq):
                return None, "", await self._msg_card(
                    event, "🔒", "只能查看自己的",
                    desc="查看他人详细背包/队伍仅限管理员。\n发 /帕鲁背包 或 /帕鲁队伍 查看你自己的。",
                    color="#F5A623")
            # 支持用 userId/playerId 精确指定(解决重名歧义)：profiles 以 playerId 为键
            if name in profiles:
                p = profiles[name]
                return p, _esc(p.get("nickname") or name), None
            matches = [p for p in profiles.values() if p.get("nickname") == name]
            if len(matches) == 1:
                return matches[0], _esc(name), None
            if len(matches) >= 2:
                return None, "", await self._msg_card(
                    event, "🧭", "存在重名玩家",
                    desc=f"存档里有多个叫「{_esc(name)}」的角色，无法确定是谁。\n"
                         f"请改用 userId/playerId 精确指定。", color="#F5A623")
            return None, "", await self._msg_card(
                event, "🔍", "查无此玩家",
                desc=f"存档里没有叫「{_esc(name)}」的角色（需对方登录过本服）。", color="#F5A623")
        # 查自己
        b = self.state.get("bindings", {}).get(qq)
        if not b:
            return None, "", await self._msg_card(
                event, "🔗", "你还没绑定角色",
                desc="先发 /帕鲁绑定 <游戏名> 绑定，再查背包/队伍。", color="#F5A623")
        sp = self._match_save_profile(b, profiles)
        if not sp:
            return None, "", await self._msg_card(
                event, "🌙", "暂无你的存档数据",
                desc="服务器存档里还没有你的角色数据，先上线游戏并活动一会儿再试。", color="#9a8a91")
        return sp, _esc(b.get("name") or sp.get("nickname") or "玩家"), None

    async def _cmd_bag(self, event: AstrMessageEvent, args: list[str]):
        """背包物品网格（分页）。末位数字=页码；其余参数(管理员)=目标玩家名。"""
        page = 1
        a = list(args)
        if a and a[-1].isdigit():
            page = max(1, int(a[-1])); a = a[:-1]
        sp, name, err = await self._resolve_target_sp(event, a)
        if err:
            return err
        cells = self._inv_cells(sp)
        total = len(cells)
        pages = max(1, (total + BAG_PAGE_SIZE - 1) // BAG_PAGE_SIZE)
        page = min(page, pages)
        start = (page - 1) * BAG_PAGE_SIZE
        shown = cells[start:start + BAG_PAGE_SIZE]
        tgt = " ".join(a)
        tgt_part = (" " + tgt) if tgt else ""
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁背包{tgt_part} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("bag"),
                               {"name": name, "total": total, "page": page, "pages": pages,
                                "cells": shown, "pager": pager})

    async def _cmd_team(self, event: AstrMessageEvent, args: list[str]):
        sp, name, err = await self._resolve_target_sp(event, args)
        if err:
            return err
        pals = self._safe_views(self._pal_view, sp.get("party", []), "队伍")
        if not pals:
            return await self._msg_card(event, "🥚", f"{name} 还没有出战帕鲁",
                                        desc="队伍是空的，去抓几只帕鲁带上吧～", color="#9a8a91")
        # 多只出战时用 2 列宽卡(920)压高宽比，单只用窄单列(540)避免半张空白
        multi = len(pals) > 1
        width = 920 if multi else CARD_WIDTH
        return await self._img(event, self._t("team"),
                               {"title": f"🐾 {name} 的出战队伍",
                                "subtitle": f"共 {len(pals)} 只帕鲁 · 数据来自存档",
                                "pals": pals, "team_cols": 2 if multi else 1},
                               width=width)

    @staticmethod
    def _palbox_sorted(box: list) -> list:
        # 闪光/头目优先，再按等级降序（编号即此顺序）
        return sorted(box, key=lambda p: (not p.get("lucky"), not p.get("is_alpha"), -(p.get("level") or 0)))

    async def _cmd_palbox(self, event: AstrMessageEvent, args: list[str]):
        """帕鲁箱网格（分页）。末位数字=页码；其余参数(管理员)=目标玩家名。"""
        page = 1
        a = list(args)
        if a and a[-1].isdigit():
            page = max(1, int(a[-1])); a = a[:-1]
        sp, name, err = await self._resolve_target_sp(event, a)
        if err:
            return err
        box = self._palbox_sorted(sp.get("palbox", []))
        if not box:
            return await self._msg_card(event, "📦", f"{name} 的帕鲁箱是空的",
                                        desc="还没在帕鲁箱里存放帕鲁～", color="#9a8a91")
        total = len(box)
        pages = max(1, (total + PALBOX_PAGE_SIZE - 1) // PALBOX_PAGE_SIZE)
        page = min(page, pages)
        start = (page - 1) * PALBOX_PAGE_SIZE
        cells = []
        for i, p in enumerate(box[start:start + PALBOX_PAGE_SIZE], start + 1):
            try:
                c = self._pal_view(p); c["no"] = i; cells.append(c)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 跳过异常帕鲁箱记录 #{i}: {e}")
        tgt = " ".join(a)
        tgt_part = (" " + tgt) if tgt else ""
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁箱{tgt_part} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        hurt = sum(1 for p in box if self._health_view(p.get("health", "")).get("hurt"))
        if hurt:
            note = f"⚠ {hurt} 只受伤（🔴濒死 / 🟠重伤），放进帕鲁终端即可慢慢恢复"
            pager = (note + " · " + pager) if pager else note
        return await self._img(event, self._t("palbox"),
                               {"name": name, "total": total, "page": page, "pages": pages,
                                "cells": cells, "pager": pager, "tgt": tgt_part})

    async def _cmd_palbox_query(self, event: AstrMessageEvent, args: list[str]):
        """按编号查帕鲁箱里某只帕鲁的详细面板。末位数字=编号；其余(管理员)=目标玩家名。"""
        idx = None
        a = list(args)
        if a and a[-1].isdigit():
            idx = int(a[-1]); a = a[:-1]
        if idx is None:
            return await self._msg_card(event, "🔢", "请提供帕鲁编号",
                                        desc="用法：/帕鲁箱查询 <编号>（编号在 /帕鲁箱 列表里）\n例：/帕鲁箱查询 5",
                                        color="#E5484D")
        sp, name, err = await self._resolve_target_sp(event, a)
        if err:
            return err
        box = self._palbox_sorted(sp.get("palbox", []))
        if not box:
            return await self._msg_card(event, "📦", f"{name} 的帕鲁箱是空的",
                                        desc="还没在帕鲁箱里存放帕鲁～", color="#9a8a91")
        if idx < 1 or idx > len(box):
            return await self._msg_card(event, "🔢", "编号超出范围",
                                        desc=f"{name} 的帕鲁箱共 {len(box)} 只，请发 1~{len(box)} 的编号。",
                                        color="#F5A623")
        pal = self._pal_view(box[idx - 1])
        return await self._img(event, self._t("team"),
                               {"title": f"📦 {name} 的帕鲁 #{idx}",
                                "subtitle": f"{pal['name']}（图鉴 #{pal['index']}） · 帕鲁箱详情", "pals": [pal]})

    @staticmethod
    def _work_cn(camel: str) -> str:
        """当前工作枚举(Mining/EmitFlame) -> 中文；空=待命。"""
        if not camel:
            return "待命"
        snake = re.sub(r"([A-Z])", r"_\1", camel).lower().lstrip("_")
        return WORK_LABELS.get(snake, camel)

    def _basecamp_view(self, pal: dict) -> dict:
        """据点工作帕鲁 -> 卡片展示：工作适性(带等级)/血量(当前/最大)/饱食%/SAN/工作病/战斗伤。
        注意：Hp 是「当前血量」非最大值(会浮动)，最大值按公式算；FullStomach/SanityValue
        是真实值(断粮时确实归 0)，饥饿状态另用 HungerType 枚举校验、工作病用 WorkerSick。"""
        v = self._pal_view(pal)
        p = self._pal_by_dev.get(str(pal.get("char_id", "")).lower())
        works = []
        if p:
            ws = p.get("work_suitability") or {}
            works = sorted([{"k": WORK_LABELS.get(k, k), "lv": lv} for k, lv in ws.items() if lv],
                           key=lambda x: -x["lv"])   # 适性等级高的在前
        v["works"] = works
        v["current_work"] = self._work_cn(pal.get("current_work", ""))
        v["working"] = bool(pal.get("current_work"))
        # 血量：存档 Hp 是「当前血量」(实时，会因挨饿/受伤/被攻击浮动，不是最大值)。
        # 最大血量 = 500 + 5×Lv + floor(基础HP × 0.5 × Lv × (1 + 0.3×个体值/100)) × 浓缩系数
        # (双样本实测吻合：Lv24/IV35→1548、Lv26/IV93→1793)
        stats = (p or {}).get("stats") or {}
        cur_hp = pal.get("hp", 0) or 0
        base_hp = int(stats.get("hp", 0) or 0)
        lvl = int(pal.get("level", 1) or 1)
        iv = int(pal.get("iv_hp", 0) or 0)
        if base_hp:
            core = 500 + 5 * lvl + int(base_hp * 0.5 * lvl * (1 + 0.3 * iv / 100))
            cond = 1 + 0.05 * max(0, int(pal.get("rank", 1) or 1) - 1)   # 浓缩每星 +5%(近似)
            max_hp = round(core * cond)
        else:
            max_hp = 0
        v["hp"] = cur_hp
        v["max_hp"] = max_hp
        v["hp_pct"] = round(cur_hp / max_hp * 100) if max_hp else 0
        # 饱食度 %：FullStomach / 该种上限(max_full_stomach)。据点断粮时为 0%
        max_stom = int(stats.get("max_full_stomach", 0) or 0)
        stom = pal.get("stomach", 0) or 0
        v["stomach"] = round(stom / max_stom * 100) if max_stom else round(stom)
        # 饥饿状态：用 HungerType 枚举(可靠，游戏逻辑写入)
        hunger = self._HUNGER_CN.get(pal.get("hunger", ""), "")
        v["hunger_label"] = hunger
        v["hungry"] = bool(hunger)                 # 饥饿/挨饿
        v["starving"] = bool(hunger)               # 模板/统计沿用的字段名
        # SAN 与「理智低」：SanityValue(缺省=100健康) + 工作病消沉(Depression)佐证
        wsick = pal.get("worker_sick", "")
        v["sanity"] = round(pal.get("sanity", 100) or 0)
        v["low_san"] = ("Depression" in str(wsick)) or (v["sanity"] < 40)
        # 工作病：用 WorkerSick 枚举
        v["sick_label"] = self._WORKERSICK_CN.get(wsick, "") if wsick not in ("", "None") else ""
        v["sick"] = bool(v["sick_label"])
        # 治疗建议：饥饿 + 工作病 + 战斗伤(PhysicalHealth) + 理智低 各自的治疗方法(多状态全列)
        syms, seen = [], set()
        if hunger:
            syms.append(hunger)                    # 挨饿/饥饿
        if v["sick_label"]:
            syms.append("擦伤" if v["sick_label"] == "挫伤" else v["sick_label"])
        if v["health"]["hurt"]:
            syms.append(v["health"]["label"])      # 战斗伤 轻伤/重伤/濒死…
        if v["low_san"] and "Depression" not in str(wsick):
            syms.append("低SAN")                    # 理智低但还没消沉，给回SAN建议
        cure = []
        for sym in syms:
            if sym in seen:
                continue
            seen.add(sym)
            c = self._SYMPTOM_CURE.get(sym)
            if c:
                cure.append({"symptom": sym, "desc": c["desc"],
                             "drugs": self._symptom_items(c["items"])})
        v["cure_tips"] = cure                       # [{symptom, desc, drugs:[{name,icon}]}]
        return v

    async def _cmd_basecamp(self, event: AstrMessageEvent, args: list[str]):
        """据点工作帕鲁状态（分页）。末位数字=页码；其余参数(管理员)=目标玩家名。"""
        page = 1
        a = list(args)
        if a and a[-1].isdigit():
            page = max(1, int(a[-1])); a = a[:-1]
        sp, name, err = await self._resolve_target_sp(event, a)
        if err:
            return err
        base = sp.get("basecamp", [])
        # 闪光/头目优先，再按等级降序
        base = sorted(base, key=lambda p: (not p.get("lucky"), not p.get("is_alpha"), -(p.get("level") or 0)))
        cells = self._safe_views(self._basecamp_view, base, "据点")
        # 统计口径覆盖全部据点帕鲁（不随分页变化）
        hurt = sum(1 for c in cells if c["health"]["hurt"])
        hungry = sum(1 for c in cells if c["starving"])
        low_san = sum(1 for c in cells if c["low_san"])
        total = len(cells)
        pages = max(1, (total + BASECAMP_PAGE_SIZE - 1) // BASECAMP_PAGE_SIZE)
        page = min(page, pages)
        start = (page - 1) * BASECAMP_PAGE_SIZE
        shown = cells[start:start + BASECAMP_PAGE_SIZE]
        tgt = " ".join(a)
        tgt_part = (" " + tgt) if tgt else ""
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁据点{tgt_part} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("basecamp"),
                               {"name": name, "total": total, "hurt": hurt,
                                "hungry": hungry, "low_san": low_san, "cells": shown,
                                "page": page, "pages": pages, "pager": pager})

    def _symptom_items(self, ids: list) -> list:
        """治疗道具 id 列表 -> [{name, icon}] (带游戏物品图标)。"""
        out = []
        for iid in ids:
            meta = self._item_by_id.get(iid) if hasattr(self, "_item_by_id") else None
            out.append({"name": (meta or {}).get("name", iid), "icon": self._item_icon(iid)})
        return out

    async def _cmd_symptom(self, event: AstrMessageEvent, args: list[str]):
        """帕鲁伤病/低状态治疗查询(/帕鲁症状 [状态])：图文卡展示治疗道具(游戏图标)。"""
        q = " ".join(args).strip()
        keys = list(self._SYMPTOM_CURE)
        if not q:
            # 无参：症状目录(名字+方法摘要，引导选具体查)
            rows = [{"name": k, "desc": v["desc"], "items": self._symptom_items(v["items"])}
                    for k, v in self._SYMPTOM_CURE.items()]
            return await self._img(event, self._t("symptom"),
                                   {"single": False, "rows": rows,
                                    "sub": "帕鲁伤病·治疗速查 · 发 /帕鲁症状 <状态> 看大图"})
        # 匹配单个症状(含 SAN/理智别名)
        hit = None
        for k in keys:
            if q in k or k in q or (q.lower() in ("san", "理智", "精神") and k == "低SAN"):
                hit = k
                break
        if not hit:
            return await self._msg_card(
                event, "🔍", "没找到该症状",
                desc="可查：" + "、".join(keys) + "\n或直接发 /帕鲁症状 看全部。", color="#F5A623")
        v = self._SYMPTOM_CURE[hit]
        return await self._img(event, self._t("symptom"),
                               {"single": True, "name": hit, "desc": v["desc"],
                                "items": self._symptom_items(v["items"]),
                                "sub": "帕鲁伤病 · 治疗方法"})

    async def _cmd_hatchable(self, event: AstrMessageEvent, args: list[str]):
        """根据玩家帕鲁箱里拥有的帕鲁，算出还能配/孵出哪些没有的新帕鲁。"""
        if not self._breed:
            return await self._msg_card(event, "🥚", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        a = list(args)
        page = 1
        if a and a[-1].isdigit():
            page = max(1, int(a[-1])); a = a[:-1]
        sp, name, err = await self._resolve_target_sp(event, a)
        if err:
            return err
        box = sp.get("palbox", [])
        if not box:
            return await self._msg_card(event, "📦", f"{name} 的帕鲁箱是空的",
                                        desc="先抓些帕鲁放进帕鲁箱，再来看能配出什么～", color="#9a8a91")
        owned = set()
        for p in box:
            pl = self._pal_by_dev.get(str(p.get("char_id", "")).lower())
            if pl:
                idx = self._name_idx.get(pl.get("pal_name"))
                if idx:
                    owned.add(idx)
        new = {}
        ol = list(owned)
        for i in range(len(ol)):
            for j in range(i + 1, len(ol)):
                child = self._breed.get(frozenset((ol[i], ol[j])))
                if child and child not in owned and child not in new:
                    new[child] = (ol[i], ol[j])
        if not new:
            return await self._msg_card(event, "🥚", f"{name} 暂无新帕鲁可孵化",
                                        desc=f"已拥有 {len(owned)} 种帕鲁，它们两两配种暂时配不出你还没有的新种类。\n多抓些不同种类再来看看～",
                                        color="#9a8a91")
        results = []
        for child, (a_, b_) in new.items():
            cp, pa, pb = self._pal_idx.get(child), self._pal_idx.get(a_), self._pal_idx.get(b_)
            if cp and pa and pb:
                results.append((cp, pa, pb))

        def order(t):
            m = re.match(r"0*(\d+)", str(t[0].get("pal_index", "")))
            return int(m.group(1)) if m else 99999
        results.sort(key=order)
        tgt = " ".join(a)
        base = "/帕鲁可孵化" + ((" " + tgt) if tgt else "")
        chunk, psub, phint = self._page(results, page, base, size=12)
        rows = [{"name": cp["pal_name"], "icon": self._pal_icon(cp.get("pal_dev_name", "")),
                 "a": pa["pal_name"], "a_icon": self._pal_icon(pa.get("pal_dev_name", "")),
                 "b": pb["pal_name"], "b_icon": self._pal_icon(pb.get("pal_dev_name", ""))}
                for cp, pa, pb in chunk]
        return await self._img(event, self._t("hatch"),
                               {"title": f"{name} 可孵化的新帕鲁",
                                "subtitle": f"拥有 {len(owned)} 种 · 可配出 {len(results)} 种新帕鲁" + (f" · {psub}" if psub else ""),
                                "rows": rows,
                                "pager": phint or "「新帕鲁 ← 亲A ＋ 亲B」即配方；发 /帕鲁配种 亲A 亲B 看后代详情"})

    # ------------------------------------------------------------------
    # 公会信息（/帕鲁公会）：从存档 GroupSaveDataMap 解析公会成员
    # ------------------------------------------------------------------
    async def _find_my_guild(self, event: AstrMessageEvent, args: list[str]):
        """定位查询者(或管理员指定玩家)所属公会。返回 (guild, 错误结果)。"""
        guilds = await self._fetch_guilds(max_age=self._fresh_ttl())
        if guilds is None:
            return None, await self._msg_card(event, "🛰️", "暂时读不到存档",
                                              desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        if not guilds:
            return None, await self._msg_card(event, "🏳️", "服务器里还没有公会",
                                              desc="存档里没有解析到公会数据。", color="#9a8a91")
        qq = str(event.get_sender_id())
        b = self.state.get("bindings", {}).get(qq)
        name = " ".join(args).strip()
        if name:
            if not self._is_admin(qq):
                return None, await self._msg_card(event, "🔒", "只能查看自己的公会",
                                                  desc="查看他人公会仅限管理员。", color="#F5A623")
            g = next((x for x in guilds if any(m["name"] == name for m in x["members"])), None)
            if not g:
                return None, await self._msg_card(event, "🔍", "查无该玩家的公会", desc=f"没找到「{_esc(name)}」所在的公会。", color="#F5A623")
            return g, None
        pid = (self.state.get("uid2pid", {}) or {}).get(b.get("userId")) if b else None
        myname = b.get("name") if b else None
        g = None
        if pid:
            g = next((x for x in guilds if any(m["uid"] == pid for m in x["members"])), None)
        if not g and myname:
            g = next((x for x in guilds if any(m["name"] == myname for m in x["members"])), None)
        if not g:
            return None, await self._msg_card(event, "🔗", "没找到你的公会",
                                              desc="先 /帕鲁绑定 你的角色（并在游戏里加入/创建公会）再查。", color="#F5A623")
        return g, None

    async def _cmd_guild_pals(self, event: AstrMessageEvent, args: list[str]):
        """公会终端帕鲁：聚合本公会所有成员帕鲁箱里的帕鲁（分页网格）。"""
        self._last_save_use = time.time()
        a = list(args)
        page = 1
        if a and a[-1].isdigit():
            page = max(1, int(a[-1])); a = a[:-1]
        g, err = await self._find_my_guild(event, a)
        if err:
            return err
        profiles = await self._fetch_save_profiles(max_age=self._fresh_ttl()) or {}
        by_name = {p.get("nickname"): p for p in profiles.values()}
        box = []
        for m in g["members"]:
            prof = by_name.get(m["name"])
            if prof:
                box.extend(prof.get("palbox", []))
        box = self._palbox_sorted(box)
        leader = _esc(next((m["name"] for m in g["members"] if m["uid"] == g.get("admin_uid")), g["members"][0]["name"]))
        gname = f"「{leader}」的公会"
        if not box:
            return await self._msg_card(event, "📦", f"{gname} 终端里没有帕鲁",
                                        desc="公会成员还没在帕鲁箱里存放帕鲁，或成员存档暂未读到。", color="#9a8a91")
        total = len(box)
        pages = max(1, (total + PALBOX_PAGE_SIZE - 1) // PALBOX_PAGE_SIZE)
        page = min(page, pages)
        start = (page - 1) * PALBOX_PAGE_SIZE
        cells = []
        for i, p in enumerate(box[start:start + PALBOX_PAGE_SIZE], start + 1):
            try:
                c = self._pal_view(p); c["no"] = i; cells.append(c)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 跳过异常帕鲁箱记录 #{i}: {e}")
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁公会帕鲁 {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        hurt = sum(1 for p in box if self._health_view(p.get("health", "")).get("hurt"))
        if hurt:
            note = f"⚠ {hurt} 只受伤（🔴濒死 / 🟠重伤），放进帕鲁终端即可慢慢恢复"
            pager = (note + " · " + pager) if pager else note
        return await self._img(event, self._t("palbox"),
                               {"name": f"{gname} · 公会终端", "total": total, "page": page, "pages": pages,
                                "cells": cells, "pager": pager, "tgt": ""})

    async def _cmd_guild(self, event: AstrMessageEvent, args: list[str]):
        self._last_save_use = time.time()
        guilds = await self._fetch_guilds(max_age=self._fresh_ttl())
        if guilds is None:
            return await self._msg_card(event, "🛰️", "暂时读不到存档",
                                        desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        if not guilds:
            return await self._msg_card(event, "🏳️", "服务器里还没有公会",
                                        desc="存档里没有解析到公会数据。", color="#9a8a91")
        qq = str(event.get_sender_id())
        b = self.state.get("bindings", {}).get(qq)
        page = 1
        a = list(args)
        if a and a[-1].isdigit():
            page = max(1, int(a[-1])); a = a[:-1]
        name = " ".join(a).strip()
        g = None
        if name:    # 带名查 -> 仅管理员
            if not self._is_admin(qq):
                return await self._msg_card(event, "🔒", "只能查看自己的公会",
                                            desc="查看他人公会仅限管理员。\n发 /帕鲁公会 查看你自己的。", color="#F5A623")
            g = next((x for x in guilds if any(m["name"] == name for m in x["members"])), None)
            if not g:
                return await self._msg_card(event, "🔍", "查无该玩家的公会",
                                            desc=f"没找到「{_esc(name)}」所在的公会。", color="#F5A623")
        else:       # 查自己：绑定 -> playerId / 昵称 匹配成员
            pid = (self.state.get("uid2pid", {}) or {}).get(b.get("userId")) if b else None
            myname = b.get("name") if b else None
            if pid:
                g = next((x for x in guilds if any(m["uid"] == pid for m in x["members"])), None)
            if not g and myname:
                g = next((x for x in guilds if any(m["name"] == myname for m in x["members"])), None)
            if not g:
                return await self._msg_card(event, "🔗", "没找到你的公会",
                                            desc="先 /帕鲁绑定 你的角色（并在游戏里加入/创建公会）再查。", color="#F5A623")
        members = sorted(g["members"], key=lambda m: (m["uid"] != g.get("admin_uid"), m["name"]))
        leader = _esc(next((m["name"] for m in members if m["uid"] == g.get("admin_uid")), members[0]["name"]))
        total = len(members)
        rank = "个人" if total <= 1 else ("小型" if total <= 5 else ("中型" if total <= 15 else "大型"))
        pages = max(1, (total + GUILD_PAGE_SIZE - 1) // GUILD_PAGE_SIZE)
        page = min(page, pages)
        start = (page - 1) * GUILD_PAGE_SIZE
        shown = members[start:start + GUILD_PAGE_SIZE]
        view = [{"name": _esc(m["name"]), "is_leader": m["uid"] == g.get("admin_uid"), "no": start + i + 1}
                for i, m in enumerate(shown)]
        tgt_part = (" " + name) if name else ""
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁公会{tgt_part} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("guild"),
                               {"gname": f"「{leader}」的公会", "leader": leader, "total": total,
                                "rank": rank, "members": view,
                                "page": page, "pages": pages, "pager": pager})

    async def _cmd_guild_rank(self, event: AstrMessageEvent):
        """公会肝帝榜：按公会汇总成员本周在线时长排名。"""
        self._last_save_use = time.time()
        guilds = await self._fetch_guilds()
        if guilds is None:
            return await self._msg_card(event, "🛰️", "暂时读不到存档",
                                        desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        if not guilds:
            return await self._msg_card(event, "🏳️", "服务器里还没有公会", color="#9a8a91")
        wk = self._week_id()
        totals = self.state.get("totals", {})
        online = set(self.state.get("online", {}))
        pid2uid = {str(p): u for u, p in (self.state.get("uid2pid", {}) or {}).items() if p}
        rows = []
        for g in guilds:
            sec = 0; any_on = False
            for m in g["members"]:
                uid = pid2uid.get(m["uid"])
                if uid:
                    t = totals.get(uid, {})
                    if t.get("week_id") == wk:
                        sec += int(t.get("week", 0) or 0)
                    if uid in online:
                        any_on = True
            leader = next((m["name"] for m in g["members"] if m["uid"] == g.get("admin_uid")),
                          g["members"][0]["name"])
            rows.append({"name": f"「{_esc(leader)}」的公会 · {len(g['members'])}人",
                         "sec": sec, "online": any_on})
        rows = [r for r in rows if r["sec"] > 0]
        rows.sort(key=lambda x: x["sec"], reverse=True)
        if not rows:
            return await self._msg_card(event, "📊", "本周还没有公会在线记录",
                                        desc="公会成员上线后会自动统计在线时长上榜～", color="#9a8a91")
        maxsec = rows[0]["sec"] or 1
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        view = [{"name": r["name"], "online": r["online"], "dur": self._fmt_uptime(r["sec"]),
                 "pct": round(r["sec"] / maxsec * 100) if maxsec else 0, "medal": medals.get(i, str(i))}
                for i, r in enumerate(rows[:10], 1)]
        return await self._img(event, self._t("rank"),
                               {"rows": view, "rank_title": "🏆 公会肝帝榜",
                                "rank_sub": "本周各公会在线时长排行 · 看哪个公会最肝～"})

    async def _cmd_sub(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            return await self._msg_card(event, "✏️", "请提供要订阅的角色名",
                                        desc="用法：/帕鲁订阅 <游戏名>\n该玩家上线时会 @ 你。", color="#E5484D")
        name = " ".join(args).strip()
        qq = str(event.get_sender_id())
        lst = self.state.setdefault("subs", {}).setdefault(name, [])
        if qq not in lst:
            lst.append(qq)
            self._save_state()
        return await self._msg_card(event, "🔔", "订阅成功",
                                    desc=f"「{_esc(name)}」上线时会在群里 @ 你。\n退订发 /帕鲁退订 {_esc(name)}。",
                                    color="#30A46C")

    async def _cmd_unsub(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            return await self._msg_card(event, "✏️", "请提供要退订的角色名",
                                        desc="用法：/帕鲁退订 <游戏名>", color="#E5484D")
        name = " ".join(args).strip()
        qq = str(event.get_sender_id())
        lst = self.state.get("subs", {}).get(name, [])
        if qq in lst:
            lst.remove(qq)
            if not lst:
                self.state["subs"].pop(name, None)
            self._save_state()
            return await self._msg_card(event, "🔕", "已退订",
                                        desc=f"不再提醒「{_esc(name)}」的上线。", color="#9a8a91")
        return await self._msg_card(event, "🤔", "你没有订阅该角色",
                                    desc=f"「{_esc(name)}」不在你的订阅里。", color="#9a8a91")

    async def _cmd_find(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            return await self._msg_card(event, "✏️", "请提供要查找的角色名",
                                        desc="用法：/帕鲁找人 <游戏名>", color="#E5484D")
        name = " ".join(args).strip()
        for info in self.state.get("online", {}).values():
            if info.get("name") == name:
                return await self._msg_card(event, "✅", f"{_esc(name)} 在线",
                                            desc=f"角色「{_esc(name)}」当前在线（Lv.{info.get('level','?')}）。",
                                            color="#30A46C")
        return await self._msg_card(event, "🌙", f"{_esc(name)} 不在线",
                                    desc=f"角色「{_esc(name)}」当前不在服务器里。", color="#9a8a91")

    # ------------------------------------------------------------------
    # 互动：群↔游戏喊话 / 喊人上线
    # ------------------------------------------------------------------
    async def _cmd_shout(self, event: AstrMessageEvent, args: list[str]):
        if not self.config.get("enable_shout", True):
            return await self._msg_card(event, "🚫", "喊话功能已关闭", color="#9a8a91")
        msg = " ".join(args).strip()
        if not msg:
            return await self._msg_card(event, "✏️", "请输入要喊的内容",
                                        desc="用法：/帕鲁喊话 <内容>\n会广播到游戏里给在线玩家看。", color="#E5484D")
        msg = _security.clip(msg, _security.MAX_SHOUT)
        qq = str(event.get_sender_id())
        now = time.time()
        cd = max(int(self.config.get("shout_cooldown", 30)), 5)
        remain = int(self._shout_cd.get(qq, 0) + cd - now)
        if remain > 0:
            return await self._msg_card(event, "⏳", "喊话冷却中",
                                        desc=f"还需等待 {remain} 秒再喊~", color="#F5A623")
        nick = event.get_sender_name() or "群友"
        ingame = f"群友·{nick}说:{msg}"
        ok, err = await self._api_post("/v1/api/announce", {"message": ingame})
        if ok:
            self._shout_cd[qq] = now
            return await self._msg_card(event, "📣", "已喊话到游戏内",
                                        desc=_esc(ingame), head="📣 群→游戏 喊话", color="#30A46C")
        return await self._fail_card(event, err)

    async def _cmd_call(self, event: AstrMessageEvent, args: list[str]):
        if not event.get_group_id():
            return await self._msg_card(event, "💬", "请在群里使用",
                                        desc="「喊人上线」需要在群里 @ 对方。", color="#9a8a91")
        if not args:
            return await self._msg_card(event, "✏️", "请提供要喊的角色名",
                                        desc="用法：/帕鲁喊 <游戏名>\n（对方需先 /帕鲁绑定 过 QQ）", color="#E5484D")
        name = _security.clip(" ".join(args).strip(), _security.MAX_NAME)
        # 已在线就不用喊
        for info in self.state.get("online", {}).values():
            if info.get("name") == name:
                return await self._msg_card(event, "✅", f"{_esc(name)} 已经在线啦",
                                            desc="TA 正在帕鲁岛冒险中~", color="#30A46C")
        # 找绑定的 QQ
        uid, _ = self._find_player_by_name(name)
        target_qq = None
        for q, b in self.state.get("bindings", {}).items():
            if b.get("name") == name or (uid and b.get("userId") == uid):
                target_qq = q
                break
        if not target_qq:
            return await self._msg_card(event, "🤷", "喊不到这位玩家",
                                        desc=f"「{_esc(name)}」还没用 /帕鲁绑定 绑定 QQ，暂时喊不到~", color="#F5A623")
        now = time.time()
        if now - self._call_cd.get(target_qq, 0) < max(int(self.config.get("shout_cooldown", 30)), 5):
            return await self._msg_card(event, "⏳", "TA 刚被喊过",
                                        desc="歇一会儿再喊，别催太急啦~", color="#F5A623")
        self._call_cd[target_qq] = now
        nick = event.get_sender_name() or "群友"
        return event.chain_result([
            Comp.At(qq=target_qq),
            Comp.Plain(f" 🐾 {nick} 喊你上线玩帕鲁啦！"),
        ])

    # ------------------------------------------------------------------
    # 管理指令实现
    # ------------------------------------------------------------------
    async def _cmd_announce(self, event: AstrMessageEvent, args: list[str]):
        message = _security.clip(" ".join(args).strip(), _security.MAX_ANNOUNCE)
        if not message:
            return await self._msg_card(event, "✏️", "请输入公告内容",
                                        desc="用法：/帕鲁公告 <内容>", color="#E5484D")
        ok, err = await self._api_post("/v1/api/announce", {"message": message})
        self._log_admin(event, "公告", message, ok)
        if ok:
            return await self._msg_card(event, "📢", "公告已发送",
                                        desc=_esc(message), head="📢 服务器公告", color="#30A46C")
        return await self._fail_card(event, err)

    async def _cmd_kick(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            return await self._msg_card(event, "✏️", "请提供玩家 userId",
                                        desc="用法：/帕鲁踢 <userId> [理由]", color="#E5484D")
        userid = _security.clip(args[0], _security.MAX_USERID)
        reason = _security.clip(" ".join(args[1:]).strip(), _security.MAX_REASON) or "你已被踢出服务器"
        ok, err = await self._api_post("/v1/api/kick", {"userid": userid, "message": reason})
        self._log_admin(event, "踢人", f"{userid} | {reason}", ok)
        if ok:
            return await self._msg_card(event, "👢", "已踢出玩家",
                                        desc=f"userId: {_esc(userid)}\n理由: {_esc(reason)}", color="#30A46C")
        return await self._fail_card(event, err)

    async def _cmd_ban(self, event: AstrMessageEvent, args: list[str]):
        # 危险操作：二次确认
        if not args:
            return await self._msg_card(event, "✏️", "请提供玩家 userId",
                                        desc="用法：/帕鲁封 <userId> [理由]", color="#E5484D")
        userid = _security.clip(args[0], _security.MAX_USERID)
        reason = _security.clip(" ".join(args[1:]).strip(), _security.MAX_REASON) or "你已被封禁"
        self._set_pending(event, "封禁", "/v1/api/ban",
                          {"userid": userid, "message": reason},
                          f"封禁玩家 {userid}")
        return await self._confirm_card(event, f"即将封禁玩家 {userid}", reason)

    async def _cmd_unban(self, event: AstrMessageEvent, args: list[str]):
        if not args:
            return await self._msg_card(event, "✏️", "请提供玩家 userId",
                                        desc="用法：/帕鲁解封 <userId>", color="#E5484D")
        userid = _security.clip(args[0], _security.MAX_USERID)
        ok, err = await self._api_post("/v1/api/unban", {"userid": userid})
        self._log_admin(event, "解封", userid, ok)
        if ok:
            return await self._msg_card(event, "🔓", "已解封玩家",
                                        desc=f"userId: {_esc(userid)}", color="#30A46C")
        return await self._fail_card(event, err)

    async def _cmd_save(self, event: AstrMessageEvent, args: list[str]):
        ok, err = await self._api_post("/v1/api/save", {})
        self._log_admin(event, "存档", "-", ok)
        if ok:
            return await self._msg_card(event, "💾", "存档成功",
                                        desc="服务器世界已保存。", color="#30A46C")
        return await self._fail_card(event, err)

    async def _cmd_shutdown(self, event: AstrMessageEvent, args: list[str]):
        # 危险操作：二次确认
        if not args or not args[0].isdigit():
            return await self._msg_card(event, "✏️", "请提供等待秒数",
                                        desc="用法：/帕鲁关服 <秒数> [提示语]", color="#E5484D")
        waittime = int(args[0])
        message = " ".join(args[1:]).strip() or "服务器即将关闭"
        self._set_pending(event, "关服", "/v1/api/shutdown",
                          {"waittime": waittime, "message": message},
                          f"{waittime}秒后关服")
        return await self._confirm_card(event, f"即将在 {waittime} 秒后关服", message)

    async def _cmd_reset(self, event: AstrMessageEvent, args: list[str]):
        """删档重开（极危险）：备份→停服→清空世界→以新档重启。需二次确认。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return await self._msg_card(
                event, "🚫", "无法重置存档",
                desc="该操作需要容器挂载 docker.sock。当前未检测到，已中止。",
                color="#E5484D")
        self._pending[str(event.get_sender_id())] = {
            "action": "重置存档", "kind": "reset", "ts": time.time(),
            "desc": "清空当前世界并以全新世界重启",
        }
        n = self._confirm_timeout()
        return await self._img(event, self._t("message"), {
            "icon": "🧨", "title": "危险：重置整服存档",
            "head": "⚠️ 不可逆操作 · 需二次确认",
            "desc": ("将【清空当前世界】——地图、据点、全部玩家进度都会归零，"
                     "并以一个全新世界重启服务器。\n\n"
                     "• 旧存档会先自动打包备份到容器内\n"
                     "  /palworld/Pal/Saved/manual_resets/\n"
                     "• 服务器会先停机，约 1 分钟后以新档重新上线\n"
                     "• 玩家需重新进服建号\n"
                     "• 地图迷雾是玩家本机数据，重开后需各自重新探索\n\n"
                     f"确认无误请在 {n} 秒内回复「/帕鲁确认」，超时自动作废。"),
            "color": "#E5484D",
        })

    async def _do_reset_save(self, event: AstrMessageEvent, pending: dict):
        """执行删档重开。返回结果卡片。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        sg = self._save_games_base()   # .../SaveGames/0(配置留空时用默认基目录)
        bk = RESET_BACKUP_DIR
        wiped = 0
        try:
            # 0. 通知在线玩家并落盘（REST 不可用就跳过，不影响后续）
            self._enter_maint(300)    # 抑制停机期间的掉线/恢复误报
            await self._api_post("/v1/api/announce",
                                 {"message": "Server is resetting to a NEW world. Shutting down..."})
            await self._api_post("/v1/api/save", {})
            await asyncio.sleep(1.0)
            image = await self._docker_image_of(sock, container)
            # 1. 停服（unless-stopped 下手动 stop 不会自动重启）
            await self._docker_container_action(sock, container, "stop", timeout=90)
            # 2. 起一次性容器：备份每个世界目录，再清空其内容（保留目录壳）
            script = (
                "set -e; "
                f'SG="{sg}"; BK="{bk}"; TS="{ts}"; '
                'mkdir -p "$BK"; n=0; '
                'for d in "$SG"/*/; do '
                '  d="${d%/}"; [ -f "$d/Level.sav" ] || continue; '
                '  name=$(basename "$d"); '
                '  tar czf "$BK/${name}_$TS.tar.gz" -C "$SG" "$name"; '
                '  rm -rf "$d/Level.sav" "$d/LevelMeta.sav" "$d/Players" "$d/backup"; '
                '  n=$((n+1)); '
                'done; '
                'echo "WIPED=$n"'
            )
            code, out = await self._docker_run_helper(
                sock, image, container, ["/bin/sh", "-c", script], timeout=120)
            m = re.search(r"WIPED=(\d+)", out or "")
            wiped = int(m.group(1)) if m else 0
            if code != 0:
                # 清理失败：仍尝试把服务器拉起来，避免停在停机态
                await self._docker_container_action(sock, container, "start", timeout=60)
                self._save.invalidate()
                self._resolved_save_dir = None
                self._log_admin(event, "重置存档", f"清理失败 code={code}", False)
                return await self._fail_card(
                    event, f"清理脚本退出码 {code}，已自动重启服务器。\n{(out or '')[:120]}")
            # 3. 重新启动 → 服务器生成全新世界
            await self._docker_container_action(sock, container, "start", timeout=60)
            # 4. 失效缓存，下次查询会重新探测新世界目录
            self._save.invalidate()
            self._resolved_save_dir = None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 重置存档失败: {e}")
            # 尽力把服务器恢复运行
            try:
                await self._docker_container_action(sock, container, "start", timeout=60)
            except Exception:  # noqa: BLE001
                pass
            self._log_admin(event, "重置存档", str(e)[:60], False)
            return await self._fail_card(event, f"重置过程中出错：{e}")
        self._log_admin(event, "重置存档", f"已备份并清空 {wiped} 个世界(_{ts})", True)
        return await self._msg_card(
            event, "🌱", "存档已重置",
            desc=(f"已备份并清空 {wiped} 个世界，服务器正在以全新世界重启。\n"
                  "约 1 分钟后即可进服建号。\n"
                  f"旧档备份：容器内 {bk}/*_{ts}.tar.gz\n"
                  "如需还原可用 /帕鲁恢复存档"),
            head="🌱 全新世界", color="#30A46C")

    @staticmethod
    def _pretty_backup_ts(ts: str) -> str:
        """20260619_123456 -> 2026-06-19 12:34:56；非法格式原样返回。"""
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", ts or "")
        if not m:
            return ts or "?"
        y, mo, d, h, mi, s = m.groups()
        return f"{y}-{mo}-{d} {h}:{mi}:{s}"

    @staticmethod
    def _pretty_world_ts(fname: str) -> str:
        """备份文件名 palworld-save-2026-06-29_03-00-00.tar.gz -> 06-29 03:00；非法原样。"""
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-\d{2}", fname or "")
        return f"{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}" if m else (fname or "?")

    async def _list_backups(self, sock: str, container: str) -> list:
        """列出镜像每天备份(/palworld/backups/*.tar.gz)：[{fname,pretty,size}] 按时间倒序(最新在前)。"""
        script = (
            f'BD="{IMAGE_BACKUP_DIR}"; [ -d "$BD" ] || exit 0; '
            'for f in "$BD"/palworld-save-*.tar.gz; do [ -f "$f" ] || continue; '
            '  sz=$(du -h "$f" 2>/dev/null | cut -f1); '
            '  printf "%s|%s\\n" "$(basename "$f")" "$sz"; done | sort -r'
        )
        try:
            _, out = await self._docker_exec(sock, container, ["/bin/sh", "-c", script])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 列出备份失败: {e}")
            return []
        rows = []
        for line in (out or "").splitlines():
            if "|" in line:
                fn, sz = line.split("|", 1)
                fn = fn.strip()
                if fn:
                    rows.append({"fname": fn, "pretty": self._pretty_world_ts(fn), "size": sz.strip()})
        return rows

    async def _prune_backups(self, sock: str, container: str) -> None:
        """清理两套备份：①镜像每日tar(backup_keep_max) ②游戏引擎高频快照(engine_backup_keep)。"""
        keep = int(self.config.get("backup_keep_max", 0) or 0)
        if keep > 0:
            script = (
                f'BD="{IMAGE_BACKUP_DIR}"; KEEP={keep}; [ -d "$BD" ] || exit 0; '
                'ls -1 "$BD"/palworld-save-*.tar.gz 2>/dev/null | sort | head -n -$KEEP | while read f; do rm -f "$f"; done; '
                'echo "KEPT=$(ls -1 "$BD"/palworld-save-*.tar.gz 2>/dev/null | wc -l)"'
            )
            try:
                _, out = await self._docker_exec(sock, container, ["/bin/sh", "-c", script])
                logger.debug(f"{LOG_PREFIX} 每日备份清理: {out.strip()}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 每日备份清理失败: {e}")
        # 顺手清理游戏引擎高频快照(backup/world)，防涨满磁盘
        ekeep = int(self.config.get("engine_backup_keep", 30) or 0)
        if ekeep > 0:
            wd = await self._resolve_save_dir(sock, container)
            script2 = (
                f'BW="{wd}/{BACKUP_WORLD_SUBDIR}"; KEEP={ekeep}; [ -d "$BW" ] || exit 0; '
                'ls -1d "$BW"/*/ 2>/dev/null | sort | head -n -$KEEP | while read d; do rm -rf "$d"; done; '
                'echo "KEPT=$(ls -1d "$BW"/*/ 2>/dev/null | wc -l)"'
            )
            try:
                _, out = await self._docker_exec(sock, container, ["/bin/sh", "-c", script2])
                logger.debug(f"{LOG_PREFIX} 引擎快照清理: {out.strip()}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 引擎快照清理失败: {e}")

    async def _check_backup_prune(self) -> None:
        """后台节流(每小时一次)：按份数上限清理两套备份。"""
        if (int(self.config.get("backup_keep_max", 0) or 0) <= 0
                and int(self.config.get("engine_backup_keep", 30) or 0) <= 0):
            return
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return
        now = time.time()
        if now - self.state.get("backup_pruned", 0) < 3600:
            return
        self.state["backup_pruned"] = now
        self._save_state()
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        await self._prune_backups(sock, container)

    _UPDATE_KW = ("update", "patch", "version", "ver.", "hotfix", "v1.", "v2.",
                  "补丁", "更新", "版本", "修复")

    async def _fetch_latest_patchnote(self):
        """拉帕鲁官方更新公告(优先官方源+更新关键词)，返回 {title,text,url,img} 或 None。"""
        try:
            session = await self._get_session()
            url = ("https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
                   "?appid=1623730&count=15&maxlength=2000")
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return None
                d = await r.json()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"{LOG_PREFIX} 拉更新公告失败: {e}")
            return None
        items = d.get("appnews", {}).get("newsitems", [])
        official = [it for it in items if "community_announcements" in (it.get("feedname", "") or "")]
        pool = official or items
        # 严格按标题筛真·更新公告：含更新词、且排除促销/活动(否则会误中夏促等)
        excl = ("sale", "summer", "discount", "% off", "wishlist", "促销", "折扣", "giveaway")
        title_kw = ("update", "patch", "hotfix", "ver.", "v0.", "v1.", "v2.", "补丁", "更新")

        def is_patch(it):
            t = (it.get("title", "") or "").lower()
            if any(e in t for e in excl):
                return False
            return any(k in t for k in title_kw)
        cands = [it for it in pool if is_patch(it)]
        if not cands:
            return None     # 没有明确的更新公告(最近可能只有促销/活动) -> 不误发
        it = cands[0]   # 已按时间倒序，取最新
        raw = it.get("contents", "") or ""
        img = ""
        m = (re.search(r"\[img\][^\]]*?(https?://\S+?)\[/img\]", raw)
             or re.search(r'<img[^>]+src=["\']([^"\']+)', raw)
             or re.search(r"(https?://\S+?\.(?:png|jpe?g))", raw))
        if m:
            img = m.group(1).replace("{STEAM_CLAN_IMAGE}",
                                     "https://clan.akamai.steamstatic.com/images")
        text = re.sub(r"\[/?[a-z]+[^\]]*\]", "", raw)        # 去 BBCode
        text = re.sub(r"<[^>]+>", "", text)                  # 去 HTML
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {"title": it.get("title", ""), "text": text[:1800],
                "url": it.get("url", ""), "img": img}

    def _any_chat_provider(self):
        """拿一个可用于翻译的文本聊天 provider：优先当前对话 provider；
        若全局 LLM 对话功能没启用，就从已配置的 provider 里挑一个文本聊天的(排除 embedding/图像)。"""
        try:
            p = self.context.get_using_provider()
            if p:
                return p
        except Exception:  # noqa: BLE001
            pass
        try:
            for p in (self.context.get_all_providers() or []):
                tag = ""
                try:
                    meta = p.meta()
                    tag = f"{getattr(meta, 'id', '')} {getattr(meta, 'model', '')} {getattr(meta, 'type', '')}".lower()
                except Exception:  # noqa: BLE001
                    tag = str(p).lower()
                if "embedding" in tag or "image" in tag or "tts" in tag or "stt" in tag:
                    continue
                if hasattr(p, "text_chat"):
                    return p
        except Exception as e:  # noqa: BLE001
            logger.debug(f"{LOG_PREFIX} 找文本 provider 失败: {e}")
        return None

    async def _translate_cn(self, title: str, text: str) -> str:
        """用 bot 的 LLM 把更新公告译成简洁中文要点；无 LLM/失败返回空串。"""
        try:
            provider = self._any_chat_provider()
            if not provider:
                return ""
            resp = await provider.text_chat(
                prompt=(f"这是游戏《幻兽帕鲁(Palworld)》的官方更新公告，请翻译并整理成简洁的中文要点"
                        f"(用「· 」列点，保留关键改动，不超过350字，开头一句话概括)：\n\n"
                        f"标题：{title}\n\n正文：{text}"),
                system_prompt="你是游戏资讯翻译助手，输出地道流畅的简体中文，只输出译文不要解释。")
            return (resp.completion_text or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} LLM 翻译失败: {e}")
            return ""

    async def _cmd_patchnotes(self, event: AstrMessageEvent):
        """拉取帕鲁最新官方更新公告，LLM 译成中文，连同配图/原文链接发出。"""
        note = await self._fetch_latest_patchnote()
        if not note:
            return event.plain_result("📭 暂时没拉到帕鲁官方更新公告，稍后再试。")
        cn = await self._translate_cn(note["title"], note["text"])
        head = "🎮 帕鲁官方更新公告\n"
        if cn:
            body = head + cn + f"\n\n🔗 原文：{note['url']}"
        else:   # 无 LLM/翻译失败 → 降级发原文摘要
            body = head + f"{note['title']}\n\n{note['text'][:500]}…\n\n🔗 原文：{note['url']}"
        chain = [Comp.Plain(body)]
        if note["img"]:
            chain.append(Comp.Image.fromURL(note["img"]))
        return event.chain_result(chain)

    async def _check_server_update(self) -> None:
        """后台节流：检测帕鲁服务端 Steam 新版本，检测到就发游戏公告 + QQ 群通知。
        实际更新交给镜像自带的每日自动更新(UPDATE_ON_BOOT/AUTO_UPDATE)，本方法只负责通知。"""
        if not self.config.get("notify_server_update", True):
            return
        now = time.time()
        interval = max(int(self.config.get("update_check_hours", 6) or 6), 1) * 3600
        if now - self.state.get("update_checked", 0) < interval:
            return
        self.state["update_checked"] = now
        self._save_state()
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return
        # 1) 查 Steam 最新 manifest(第三方 api.steamcmd.net，快)
        latest = ""
        try:
            session = await self._get_session()
            async with session.get("https://api.steamcmd.net/v1/info/2394010",
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return
                d = await r.json()
            latest = (d.get("data", {}).get("2394010", {}).get("depots", {})
                      .get("2394012", {}).get("manifests", {}).get("public", {}).get("gid", ""))
        except Exception as e:  # noqa: BLE001
            logger.debug(f"{LOG_PREFIX} 查 Steam 版本失败: {e}")
            return
        if not latest:
            return
        # 2) 读当前已装 manifest(appmanifest 第 2 个 manifest 行)
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        try:
            _, out = await self._docker_exec(sock, container, ["/bin/sh", "-c",
                r"awk '/manifest/{c++} c==2{print $2;exit}' /palworld/steamapps/appmanifest_2394010.acf | tr -d '\"'"])
            current = (out or "").strip().split("\n")[-1].strip()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"{LOG_PREFIX} 读当前版本失败: {e}")
            return
        if not current:
            return
        if latest == current:
            self.state.pop("update_notified", None)   # 已是最新，清通知标记(下次新版本可再报)
            self._save_state()
            return
        # 3) 有新版本，且该版本没通知过 -> 游戏公告 + QQ 群通知
        if self.state.get("update_notified") == latest:
            return
        self.state["update_notified"] = latest
        self._save_state()
        await self._api_post("/v1/api/announce",
                             {"message": "New server version available. Auto-update at daily maintenance."})
        rb = str(self.config.get("daily_reboot_time", "") or "05:00")
        await self._broadcast_text(
            f"🔔 检测到帕鲁服务端有新版本\n将在每日维护时间（约 {rb}）自动更新并重启，"
            "用时约几分钟，请提前下线保存进度～")

    async def _find_latest_backup(self, sock: str, container: str) -> Tuple[Optional[str], int]:
        """探测最近一次删档备份：返回 (时间戳, 该批 tar 个数)；无备份返回 (None, 0)。"""
        script = (
            f'BK="{RESET_BACKUP_DIR}"; '
            r'latest=$(ls -1 "$BK" 2>/dev/null | grep -E "_[0-9]{8}_[0-9]{6}\.tar\.gz$" '
            r'| sed -E "s/.*_([0-9]{8}_[0-9]{6})\.tar\.gz$/\1/" | sort | tail -1); '
            'if [ -z "$latest" ]; then echo "TS= N=0"; '
            'else n=$(ls -1 "$BK"/*_"$latest".tar.gz 2>/dev/null | wc -l); '
            'echo "TS=$latest N=$n"; fi'
        )
        try:
            _, out = await self._docker_exec(sock, container, ["/bin/sh", "-c", script])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 探测备份失败: {e}")
            return None, 0
        mt = re.search(r"TS=(\S*)", out or "")
        mn = re.search(r"N=(\d+)", out or "")
        ts = (mt.group(1) if mt else "").strip()
        n = int(mn.group(1)) if mn else 0
        if not ts or n <= 0:
            return None, 0
        return ts, n

    async def _cmd_restore(self, event: AstrMessageEvent, args: list[str]):
        """恢复上一次删档前的存档（仅最近一次）。需二次确认。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return await self._msg_card(
                event, "🚫", "无法恢复存档",
                desc="该操作需要容器挂载 docker.sock。当前未检测到，已中止。",
                color="#E5484D")
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        ts, n = await self._find_latest_backup(sock, container)
        if not ts:
            return await self._msg_card(
                event, "📭", "没有可恢复的存档",
                desc="未找到任何删档备份。\n只有执行过 /帕鲁重置存档 之后才会有可恢复的存档。",
                color="#F5A623")
        self._pending[str(event.get_sender_id())] = {
            "action": "恢复存档", "kind": "restore", "ts": time.time(),
            "backup_ts": ts, "desc": f"还原 {self._pretty_backup_ts(ts)} 的存档",
        }
        nconf = self._confirm_timeout()
        return await self._img(event, self._t("message"), {
            "icon": "↩️", "title": "恢复上一次重置前的存档",
            "head": "⚠️ 覆盖当前世界 · 需二次确认",
            "desc": (f"将用【{self._pretty_backup_ts(ts)}】那次删档前的存档，"
                     "覆盖回服务器。\n\n"
                     "• 当前这个新世界会被丢弃（不再保留）\n"
                     "• 服务器会先停机，约 1 分钟后以还原后的存档重新上线\n"
                     "• 仅能还原最近一次重置的存档\n"
                     "• 角色/背包/帕鲁/据点/等级等服务器数据可完整还原\n"
                     "• 但地图迷雾是各玩家本机数据，无法还原，恢复后需重新探索\n\n"
                     f"确认无误请在 {nconf} 秒内回复「/帕鲁确认」，超时自动作废。"),
            "color": "#E5484D",
        })

    async def _do_restore_save(self, event: AstrMessageEvent, pending: dict):
        """执行恢复存档：停服→清空当前世界→解包最近一次备份→重启。返回结果卡片。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        ts = str(pending.get("backup_ts", "")).strip()
        if not ts:
            return await self._fail_card(event, "未记录要恢复的备份时间戳，请重新发起。")
        sg = self._save_games_base()   # .../SaveGames/0(配置留空时用默认基目录)
        restored = 0
        try:
            self._enter_maint(300)    # 抑制停机期间的掉线/恢复误报
            await self._api_post("/v1/api/announce",
                                 {"message": "Server is restoring a previous save. Shutting down..."})
            await self._api_post("/v1/api/save", {})
            await asyncio.sleep(1.0)
            image = await self._docker_image_of(sock, container)
            await self._docker_container_action(sock, container, "stop", timeout=90)
            script = (
                "set -e; "
                f'SG="{sg}"; BK="{RESET_BACKUP_DIR}"; TS="{ts}"; '
                'ls "$BK"/*_"$TS".tar.gz >/dev/null 2>&1 || { echo "NOBACKUP"; exit 5; }; '
                'for d in "$SG"/*/; do d="${d%/}"; [ -d "$d" ] && rm -rf "$d"; done; '
                'n=0; '
                'for f in "$BK"/*_"$TS".tar.gz; do '
                '  [ -f "$f" ] || continue; '
                '  tar xzf "$f" -C "$SG"; '
                '  n=$((n+1)); '
                'done; '
                'echo "RESTORED=$n"'
            )
            code, out = await self._docker_run_helper(
                sock, image, container, ["/bin/sh", "-c", script], timeout=120)
            m = re.search(r"RESTORED=(\d+)", out or "")
            restored = int(m.group(1)) if m else 0
            if code != 0 or restored <= 0:
                await self._docker_container_action(sock, container, "start", timeout=60)
                self._save.invalidate()
                self._resolved_save_dir = None
                self._log_admin(event, "恢复存档", f"失败 code={code} restored={restored}", False)
                return await self._fail_card(
                    event, f"恢复未成功(code={code})，已自动重启服务器。\n{(out or '')[:120]}")
            await self._docker_container_action(sock, container, "start", timeout=60)
            self._save.invalidate()
            self._resolved_save_dir = None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 恢复存档失败: {e}")
            try:
                await self._docker_container_action(sock, container, "start", timeout=60)
            except Exception:  # noqa: BLE001
                pass
            self._log_admin(event, "恢复存档", str(e)[:60], False)
            return await self._fail_card(event, f"恢复过程中出错：{e}")
        self._log_admin(event, "恢复存档", f"已还原 {self._pretty_backup_ts(ts)} 的存档", True)
        return await self._msg_card(
            event, "↩️", "存档已恢复",
            desc=(f"已还原【{self._pretty_backup_ts(ts)}】那次删档前的存档，"
                  "服务器正在重启。\n约 1 分钟后即可进服。"),
            head="↩️ 存档恢复", color="#30A46C")

    async def _cmd_backups(self, event: AstrMessageEvent, args: list[str]):
        """列出可回档的自动备份(backup/world)。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return await self._msg_card(
                event, "🚫", "无法读取备份",
                desc="该操作需要容器挂载 docker.sock。当前未检测到，已中止。", color="#E5484D")
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        rows = await self._list_backups(sock, container)
        if not rows:
            return await self._msg_card(
                event, "📭", "暂无自动备份",
                desc="还没有找到 backup/world 下的自动备份存档。", color="#F5A623")
        keep = int(self.config.get("backup_keep_max", 0) or 0)
        lines = [f"{i}. {r['pretty']}  · {r['size']}" for i, r in enumerate(rows[:30], 1)]
        tail = f"\n———\n共 {len(rows)} 份（上限 {keep if keep else '不限'}）。回档发：/帕鲁回档 <编号>"
        return await self._msg_card(
            event, "🗂️", "存档备份列表", desc="\n".join(lines) + tail,
            head="🗂️ 备份 · 可回档", color=self._theme())

    async def _cmd_rollback(self, event: AstrMessageEvent, args: list[str]):
        """回档到指定编号的自动备份（admin + 二次确认）。无参=列表。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return await self._msg_card(
                event, "🚫", "无法回档",
                desc="该操作需要容器挂载 docker.sock。当前未检测到，已中止。", color="#E5484D")
        if not args or not args[0].isdigit():
            return await self._cmd_backups(event, args)   # 无编号 -> 直接给列表
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        rows = await self._list_backups(sock, container)
        idx = int(args[0])
        if idx < 1 or idx > len(rows):
            return await self._msg_card(
                event, "❓", "编号不存在",
                desc=f"请发 /帕鲁备份列表 查看有效编号（1~{len(rows)}）。", color="#E5484D")
        sel = rows[idx - 1]
        self._pending[str(event.get_sender_id())] = {
            "action": "回档", "kind": "rollback", "ts": time.time(),
            "backup_fname": sel["fname"], "desc": f"回档到 {sel['pretty']}",
        }
        n = self._confirm_timeout()
        return await self._img(event, self._t("message"), {
            "icon": "⏪", "title": f"回档到 {sel['pretty']}",
            "head": "⚠️ 覆盖当前世界 · 需确认",
            "desc": (f"将用【{sel['pretty']}】的每日备份覆盖当前世界。\n\n"
                     "• 回档前会自动把当前世界另存一份(以防回档错)\n"
                     "• 服务器会先停机，约 1 分钟后以回档存档重新上线\n"
                     "• 地图迷雾是各玩家本机数据，无法还原，回档后需重新探索\n\n"
                     f"确认请在 {n} 秒内回复「/帕鲁确认」，超时作废。"),
            "color": "#E5484D",
        })

    async def _do_rollback(self, event: AstrMessageEvent, pending: dict):
        """执行回档：存档→停服→当前存档另存→清空 SaveGames→解包镜像 tar 备份→启服。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        fname = str(pending.get("backup_fname", "")).strip()
        # 防注入：文件名只允许 备份命名字符
        if not fname or not re.fullmatch(r"palworld-save-[\d_\-]+\.tar\.gz", fname):
            return await self._fail_card(event, "备份文件名异常，请重新发起。")
        try:
            self._enter_maint(300)
            await self._api_post("/v1/api/announce",
                                 {"message": "Server is rolling back a backup. Shutting down..."})
            await self._api_post("/v1/api/save", {})
            await asyncio.sleep(1.0)
            image = await self._docker_image_of(sock, container)
            await self._docker_container_action(sock, container, "stop", timeout=90)
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 镜像 tar 内是 Saved/SaveGames/...，解包到 /palworld/Pal/ 覆盖存档(不动 Config)
            script = (
                "set -e; "
                f'BD="{IMAGE_BACKUP_DIR}"; F="$BD/{fname}"; PAL=/palworld/Pal; '
                f'BK="{RESET_BACKUP_DIR}"; STAMP="{now}"; '
                'if [ ! -f "$F" ]; then echo NOBACKUP; exit 5; fi; '
                # 回档前把当前存档另存(可再回滚)
                'mkdir -p "$BK"; '
                'tar czf "$BK/before_rollback_$STAMP.tar.gz" -C "$PAL" Saved/SaveGames 2>/dev/null || true; '
                # 清当前 SaveGames 再解包(只覆盖存档，不动 Config)
                'rm -rf "$PAL/Saved/SaveGames"; '
                'tar xzf "$F" -C "$PAL" Saved/SaveGames 2>/dev/null || tar xzf "$F" -C "$PAL"; '
                '[ -d "$PAL/Saved/SaveGames" ] && echo ROLLED=1 || echo ROLLED=0'
            )
            code, out = await self._docker_run_helper(
                sock, image, container, ["/bin/sh", "-c", script], timeout=180)
            ok = "ROLLED=1" in (out or "")
            if code != 0 or not ok:
                await self._docker_container_action(sock, container, "start", timeout=60)
                self._save.invalidate()
                self._resolved_save_dir = None
                self._log_admin(event, "回档", f"失败 code={code}", False)
                return await self._fail_card(
                    event, f"回档未成功(code={code})，已自动重启服务器。\n{(out or '')[:120]}")
            await self._docker_container_action(sock, container, "start", timeout=60)
            self._save.invalidate()
            self._resolved_save_dir = None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 回档失败: {e}")
            try:
                await self._docker_container_action(sock, container, "start", timeout=60)
            except Exception:  # noqa: BLE001
                pass
            self._log_admin(event, "回档", str(e)[:60], False)
            return await self._fail_card(event, f"回档过程中出错：{e}")
        pretty = self._pretty_world_ts(fname)
        self._log_admin(event, "回档", f"已回档到 {pretty}", True)
        return await self._msg_card(
            event, "⏪", "回档完成",
            desc=(f"已回档到【{pretty}】的每日备份，服务器正在重启。\n"
                  "约 1 分钟后即可进服。\n回档前的存档已另存，如需可联系管理处理。"),
            head="⏪ 存档回档", color="#30A46C")

    async def _cmd_restart(self, event: AstrMessageEvent, args: list[str]):
        """重启服务器（admin + 二次确认）：存档后 docker restart，约 1 分钟恢复。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return await self._msg_card(
                event, "🚫", "无法重启",
                desc="该操作需要容器挂载 docker.sock。当前未检测到，已中止。",
                color="#E5484D")
        self._pending[str(event.get_sender_id())] = {
            "action": "重启服务器", "kind": "restart", "ts": time.time(),
            "desc": "重启帕鲁服务器",
        }
        n = self._confirm_timeout()
        return await self._img(event, self._t("message"), {
            "icon": "🔄", "title": "重启服务器",
            "head": "⚠️ 危险操作 · 需确认",
            "desc": ("将重启帕鲁服务器（存档不变，只是重新启动）。\n\n"
                     "• 会先存档，再停机重启\n"
                     "• 在线玩家会断线，约 1 分钟后可重新进服\n\n"
                     f"确认请在 {n} 秒内回复「/帕鲁确认」，超时作废。"),
            "color": "#F5A623",
        })

    async def _do_restart_server(self, event: AstrMessageEvent, pending: dict):
        """执行重启：存档 → docker restart → 报告。"""
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        container = await self._resolve_container(sock) or str(self.config.get("docker_container", "palworld-server"))
        try:
            self._enter_maint(180)    # 抑制重启期间的掉线/恢复误报
            await self._api_post("/v1/api/announce",
                                 {"message": "Server is restarting, back in ~1 min..."})
            await self._api_post("/v1/api/save", {})
            await asyncio.sleep(1.0)
            await self._docker_container_action(sock, container, "restart", timeout=120)
            self._save.invalidate()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 重启服务器失败: {e}")
            self._log_admin(event, "重启服务器", str(e)[:60], False)
            return await self._fail_card(event, f"重启过程中出错：{e}")
        self._log_admin(event, "重启服务器", "-", True)
        return await self._msg_card(
            event, "🔄", "服务器正在重启",
            desc="已存档并触发重启，约 1 分钟后恢复。", head="🔄 重启", color="#30A46C")

    # ------------------------------------------------------------------
    # 二次确认
    # ------------------------------------------------------------------
    def _set_pending(self, event, action_name, path, payload, desc):
        self._pending[str(event.get_sender_id())] = {
            "action": action_name, "path": path, "payload": payload,
            "desc": desc, "ts": time.time(),
        }

    async def _confirm_card(self, event, title, desc):
        # title/desc 可能含用户键入的参数(如封禁 userId、关服提示语)，进模板前转义
        n = self._confirm_timeout()
        return await self._img(event, self._t("message"), {
            "icon": "⚠️", "title": _esc(title), "head": "⚠️ 危险操作 · 需确认",
            "desc": f"{_esc(desc)}\n\n请在 {n} 秒内回复「/帕鲁确认」执行，超时作废。",
            "color": "#F5A623",
        })

    async def _cmd_confirm(self, event: AstrMessageEvent):
        sender = str(event.get_sender_id())
        pending = self._pending.pop(sender, None)
        if not pending:
            return await self._msg_card(event, "🤔", "没有待确认的操作",
                                        desc="可能已超时或已执行。", color="#9a9aa8")
        if time.time() - pending["ts"] > self._confirm_timeout():
            return await self._msg_card(event, "⌛", "确认已超时",
                                        desc="危险操作已自动作废，请重新发起。", color="#E5484D")
        # 多步编排类操作（删档重开 / 恢复存档 / 重启）走专用执行器
        if pending.get("kind") == "reset":
            return await self._do_reset_save(event, pending)
        if pending.get("kind") == "restore":
            return await self._do_restore_save(event, pending)
        if pending.get("kind") == "restart":
            return await self._do_restart_server(event, pending)
        if pending.get("kind") == "rollback":
            return await self._do_rollback(event, pending)
        ok, err = await self._api_post(pending["path"], pending["payload"])
        self._log_admin(event, pending["action"], pending["desc"], ok)
        if ok:
            return await self._msg_card(event, "✅", f"{pending['action']} 已执行",
                                        desc=_esc(pending["desc"]), color="#30A46C")
        return await self._fail_card(event, err)

    # ------------------------------------------------------------------
    # 杂项
    # ------------------------------------------------------------------
    async def _fail_card(self, event, err: str):
        return await self._msg_card(event, "❌", "操作失败",
                                    desc=f"服务器返回：{err}", color="#E5484D")

    def _log_admin(self, event, action: str, detail: str, ok: bool):
        logger.info(
            f"{LOG_PREFIX} 管理操作 | 操作者={event.get_sender_id()}"
            f"({event.get_sender_name()}) | 动作={action} | 详情={detail} | "
            f"结果={'成功' if ok else '失败'}"
        )
        # 审计：持久化最近 50 条
        audit = self.state.setdefault("audit", [])
        audit.append({"ts": int(time.time()), "name": event.get_sender_name() or str(event.get_sender_id()),
                      "qq": str(event.get_sender_id()), "action": action, "detail": detail, "ok": ok})
        if len(audit) > 50:
            del audit[:-50]
        self._save_state()

    async def _cmd_audit(self, event: AstrMessageEvent):
        audit = self.state.get("audit", [])[-12:][::-1]
        if not audit:
            return await self._msg_card(event, "📋", "暂无管理操作记录", head="📋 管理审计")
        lines = []
        for r in audit:
            t = datetime.fromtimestamp(r["ts"]).strftime("%m-%d %H:%M")
            st = "✅" if r.get("ok") else "❌"
            d = f" {_esc(r['detail'])}" if r.get("detail") and r["detail"] != "-" else ""
            lines.append(f"{t} {st} {_esc(r.get('name', '?'))}：{r['action']}{d}")
        return await self._msg_card(event, "📋", "最近管理操作",
                                    desc="\n".join(lines), head="📋 管理审计")

    async def _cmd_selfcheck(self, event: AstrMessageEvent):
        """部署自检：逐项体检 docker/连接/存档/依赖/渲染/配置，给可读结论与修复建议。
        给新部署者一键排障，不用来问作者。仅管理员。"""
        lines: list[str] = []
        counts = {"ok": 0, "warn": 0, "err": 0}

        def add(mark: str, label: str, detail: str, fix: str = ""):
            counts["ok" if mark == "✅" else ("warn" if mark == "⚠️" else "err")] += 1
            seg = f"{mark} {label}：{detail}"
            if fix and mark != "✅":
                seg += f"\n↳ {fix}"
            lines.append(seg)

        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))

        # 1) docker.sock 是否挂载
        sock_ok = os.path.exists(sock)
        if sock_ok:
            add("✅", "docker.sock", f"已挂载 {sock}")
        else:
            add("❌", "docker.sock", f"未找到 {sock}",
                "在 astrbot 的 docker-compose 加挂载 "
                "- /var/run/docker.sock:/var/run/docker.sock:ro 后重启容器；"
                "存档/关服/重启/资源监控都依赖它。")

        # 2) 帕鲁服容器(按配置或自动探测)
        container = None
        if sock_ok:
            container = await self._resolve_container(sock)
            info = await docker_api.inspect_container(sock, container)
            found = info is not None
            info = info or {}
            cfg_name = str(self.config.get("docker_container", "palworld-server")).strip()
            if found:
                st = (info.get("State", {}) or {}).get("Status", "?")
                tag = "" if container == cfg_name else "(自动探测)"
                add("✅" if st == "running" else "⚠️", "帕鲁服容器",
                    f"{container}{tag} · {st}",
                    "容器未在运行，请到面板/命令行启动它。" if st != "running" else "")
            else:
                add("❌", "帕鲁服容器", f"未找到「{container}」",
                    "在插件配置 docker_container 填正确的帕鲁服容器名(面板可查)，"
                    "或确认镜像名含 palworld 以便自动探测。")
        else:
            add("⚠️", "帕鲁服容器", "跳过(docker.sock 未挂载)")

        # 3) REST API 可达 + admin_password 是否正确
        ok, data, status = await self._api_get("/v1/api/info")
        if ok and isinstance(data, dict):
            add("✅", "REST API",
                f"可达 · {data.get('servername', '服务器')} v{data.get('version', '—')}")
        elif status in (401, 403):
            add("❌", "REST API 认证", f"密码不正确(HTTP {status})",
                "插件 admin_password 必须等于帕鲁容器的 ADMIN_PASSWORD 环境变量。")
        else:
            add("❌", "REST API",
                f"连不上({'HTTP ' + str(status) if status else '超时/被拒'})",
                f"检查 api_base={self._api_base()} 是否可达、帕鲁服 REST(RESTAPIEnabled=True、"
                "端口 8212)是否开启。")

        # 4) 存档目录能否定位(找到 Level.sav)
        if sock_ok and container:
            save_dir = await self._resolve_save_dir(sock, container)
            has = False
            if save_dir:
                try:
                    code, _ = await self._docker_exec(
                        sock, container, ["/bin/sh", "-c", f'test -f "{save_dir}/Level.sav"'])
                    has = (code == 0)
                except Exception:  # noqa: BLE001
                    has = False
            if has:
                guid = save_dir.rsplit("/", 1)[-1]
                tag = "(自动探测)" if not self._configured_save_dir() else ""
                add("✅", "存档目录", f"…/{guid}{tag}")
            else:
                add("❌", "存档目录", "未找到 Level.sav",
                    f"确认存档在 {self._save_games_base()}/<世界GUID>/ 下；"
                    "或在 save_dir_in_container 手填完整的容器内路径。")
        else:
            add("⚠️", "存档目录", "跳过(依赖 docker.sock/容器)")

        # 5) palworld_save_tools 能否 import
        try:
            import palworld_save_tools  # noqa: F401
            pst_ok = True
            add("✅", "存档解析库", "palworld_save_tools 已安装")
        except Exception:  # noqa: BLE001
            pst_ok = False
            add("❌", "存档解析库", "缺少 palworld_save_tools",
                "在 astrbot 容器执行 pip install palworld-save-tools 后重载插件。")

        # 6) liboo2core.so 能否加载 + 端到端实际解析一次
        so_ok = False
        try:
            import sys as _sys
            here = os.path.dirname(os.path.abspath(__file__))
            pw = os.path.join(here, "palwork")
            if not os.path.isfile(os.path.join(pw, "palsave.py")):
                pw = os.path.abspath(os.path.join(here, "..", "..", "palwork"))
            if pw not in _sys.path:
                _sys.path.insert(0, pw)
            import palsave  # 触发 CDLL 加载 liboo2core.so
            so_ok = getattr(palsave, "_oo", None) is not None
        except Exception as e:  # noqa: BLE001
            add("❌", "Oodle 库", f"liboo2core.so 加载失败：{str(e)[:50]}",
                "确认 palwork/liboo2core.so 已随插件一同安装(自包含)。")
        if so_ok:
            prof = None
            if sock_ok and pst_ok:
                try:
                    prof = await self._fetch_save_data(force_save=False)
                except Exception:  # noqa: BLE001
                    prof = None
            if prof and prof.get("profiles"):
                add("✅", "存档解析", f"实测成功 · {len(prof['profiles'])} 名玩家")
            elif not (sock_ok and pst_ok):
                add("⚠️", "存档解析", "liboo2core.so 就绪(前置未满足，跳过实测)")
            else:
                add("⚠️", "存档解析", "库就绪但暂未解析出数据",
                    "可能空档或刚失败进了负缓存；有人上线存档后重发 /帕鲁我 再看。")

        # 7) 渲染是否可用(能出图)
        try:
            url = await self._render(self._t("message"), {
                "icon": "🧪", "title": "渲染自检", "head": "🩺 自检",
                "desc": "能看到这张图说明渲染正常。", "color": "#30A46C"})
        except Exception:  # noqa: BLE001
            url = None
        if url:
            add("✅", "卡片渲染", "出图正常")
        else:
            add("❌", "卡片渲染", "无法出图",
                "本地渲染(Playwright/Chromium)不可用，检查 astrbot 渲染环境；"
                "可临时关闭 local_render 走远程 t2i。")

        # 8) admin_qq 是否已配置
        admins = self._admins()
        if admins:
            add("✅", "管理员白名单", f"已配置 {len(admins)} 人")
        else:
            add("❌", "管理员白名单", "admin_qq 为空",
                "在插件配置 admin_qq 填管理员 QQ，否则没人能用管理指令(含本自检)。")

        ok_n, warn_n, err_n = counts["ok"], counts["warn"], counts["err"]
        head = f"🩺 部署自检 · {ok_n}✅ {warn_n}⚠️ {err_n}❌"
        if err_n == 0 and warn_n == 0:
            icon, color = "✅", "#30A46C"
        elif err_n == 0:
            icon, color = "⚠️", "#F5A623"
        else:
            icon, color = "❌", "#E5484D"
        return await self._msg_card(event, icon, "帕鲁部署自检",
                                    desc="\n".join(lines), head=head, color=color)

    # ------------------------------------------------------------------
    # Phase 1：后台轮询 + 主动播报(上下线 / 掉线告警)
    # ------------------------------------------------------------------
    async def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            p = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
            if p:
                self._client = p.get_client()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"{LOG_PREFIX} 获取 aiocqhttp 客户端失败: {e}")
        return self._client

    async def _send_group_text(self, gid: str, text: str):
        cli = await self._get_client()
        if not cli:
            return
        try:
            await cli.api.call_action("send_group_msg", group_id=int(gid), message=text)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 群 {gid} 文字播报失败: {e}")

    async def _send_group_image(self, gid: str, url: str):
        cli = await self._get_client()
        if not cli:
            return
        try:
            file_arg = url
            # 本地渲染产出的是本机临时文件路径；NapCat 是另一个容器，按路径取不到文件
            # (retcode=1200 文件处理失败/识别URL失败)。本地路径一律读出转 base64 内嵌发送。
            if url and not url.startswith(("http://", "https://", "base64://")):
                p = url[7:] if url.startswith("file://") else url
                if os.path.exists(p):
                    import base64
                    with open(p, "rb") as f:
                        file_arg = "base64://" + base64.b64encode(f.read()).decode()
            await cli.api.call_action(
                "send_group_msg", group_id=int(gid),
                message=[{"type": "image", "data": {"file": file_arg}}])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 群 {gid} 图片播报失败: {e}")

    async def _broadcast_text(self, text: str):
        for gid in self._broadcast_targets():
            await self._send_group_text(gid, text)

    async def _broadcast_card(self, tmpl: str, data: dict):
        url = await self._render(tmpl, data)   # html_render 默认 return_url=True
        if not url:
            return
        for gid in self._broadcast_targets():
            await self._send_group_image(gid, url)

    async def _poll_loop(self):
        await asyncio.sleep(15)   # 启动后稍等，等平台适配器就绪
        while True:
            try:
                if self._enable_broadcast():
                    async with self._lock:
                        await self._poll_once()
                        await self._check_schedules()   # 定时早晚报 / 周肝帝结算
                        await self._check_backup_prune()  # 备份份数上限清理(每小时节流)
                        await self._check_server_update()  # 检测服务端新版本→QQ通知(节流)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 轮询异常: {e}")
            await asyncio.sleep(self._poll_interval())

    async def _prewarm_loop(self):
        """后台预热：启动后预热浏览器 + 存档缓存(首条指令直接命中)；之后在缓存到期前
        刷新——但仅当 有人在线 / 近期有人用过 存档类指令时，空服不空跑强制存盘。"""
        await asyncio.sleep(8)   # 略等网络就绪(预热不发消息，无需等平台适配器)
        # 预热本地渲染器(省掉首次出图的浏览器启动开销)
        if self.config.get("local_render", False):
            try:
                await self._get_browser()
            except Exception:  # noqa: BLE001
                pass
        sock = str(self.config.get("docker_sock", "/var/run/docker.sock"))
        warmed_once = False
        while True:
            try:
                ttl = max(int(self.config.get("save_cache_ttl", 120)), 20)
                if self.config.get("prewarm_save", True) and os.path.exists(sock):
                    now = time.time()
                    cache = self._save.cache_entry()
                    stale = (not cache) or (now - cache[0] > ttl - 25)
                    active = bool(self.state.get("online")) or (now - getattr(self, "_last_save_use", 0) < 300)
                    # 启动后无条件预热一次，让重启后第一条指令也快
                    if stale and (active or not warmed_once):
                        prof = await self._fetch_save_profiles()
                        if prof is not None:
                            if not warmed_once:
                                logger.info(f"{LOG_PREFIX} 存档缓存已预热（{len(prof)} 个玩家），首条指令可秒出图")
                            warmed_once = True
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning(f"{LOG_PREFIX} 存档预热异常: {e}")
            await asyncio.sleep(max(min(int(self.config.get("save_cache_ttl", 120)) - 25, 100), 30))

    def _enter_maint(self, seconds: float):
        """进入维护静默窗口：期间管理员主动重启/重置/恢复导致的不可达不报掉线/恢复告警。"""
        self._maint_until = time.time() + seconds

    def _in_maint(self) -> bool:
        return time.time() < getattr(self, "_maint_until", 0)

    async def _poll_once(self):
        ok, data, status = await self._api_get("/v1/api/players")

        # —— 不可达：累计失败，仅在 上线→掉线 跳变时告警一次 ——
        if not ok:
            if status in (401, 403):      # 认证错不算掉线
                return
            self.state["fail_count"] = self.state.get("fail_count", 0) + 1
            if self.state["fail_count"] >= self._offline_threshold():
                if (self.state.get("server_up") is True and self._notify_server_down()
                        and not self._in_maint()):
                    await self._broadcast_card(self._t("message"), {
                        "icon": "🔴", "title": "服务器掉线", "head": "🎮 帕鲁服务器告警",
                        "desc": "监测到帕鲁服务器无法连接，可能崩溃或已关闭，请管理员留意。",
                        "color": "#E5484D"})
                self.state["server_up"] = False
            self._save_state()
            return

        # —— 可达：处理恢复 + 在线 diff ——
        recovered = self.state.get("server_up") is False
        self.state["fail_count"] = 0
        self.state["server_up"] = True

        okm, metrics, _ = await self._api_get("/v1/api/metrics")
        days = None
        if okm and isinstance(metrics, dict):
            self.state["maxn"] = metrics.get("maxplayernum", self.state.get("maxn"))
            days = metrics.get("days")
        maxn = self.state.get("maxn")

        # 运维：FPS 告警 + 设置变更监控（可达即检查）
        await self._check_fps(metrics.get("serverfps") if (okm and isinstance(metrics, dict)) else None)
        await self._check_settings_change()

        players = (data or {}).get("players", []) if isinstance(data, dict) else []
        now = int(time.time())
        cur = {str(p.get("userId")): {"name": p.get("name", "未知"), "level": p.get("level", "?")}
               for p in players if p.get("userId") is not None}
        # 记录 userId->playerId(存档键)，供 /帕鲁我·背包·队伍 关联存档；持久化跨离线
        u2p = self.state.setdefault("uid2pid", {})
        for p in players:
            u, pid = p.get("userId"), p.get("playerId")
            if u is not None and pid:
                u2p[str(u)] = pid
        prev = self.state.get("online", {})

        # 首次轮询 或 刚恢复：静默重建在线集合，不刷屏“上线”
        if not self.state.get("initialized") or recovered:
            for uid, info in cur.items():
                info["since"] = prev.get(uid, {}).get("since", now)
            self.state["online"] = cur
            self.state["initialized"] = True
            self.state["last_poll"] = now      # 重置计时基准，避免把停服时段算进时长
            self._save_state()
            if recovered and self._notify_server_down() and not self._in_maint():
                await self._broadcast_card(self._t("message"), {
                    "icon": "🟢", "title": "服务器已恢复", "head": "🎮 帕鲁服务器",
                    "desc": "帕鲁服务器已恢复连接，可以上线啦！", "color": "#30A46C"})
            return

        joins = [uid for uid in cur if uid not in prev]
        lefts = [uid for uid in prev if uid not in cur]
        for uid in cur:    # 继承在线起始时间
            cur[uid]["since"] = prev.get(uid, {}).get("since", now)
        self._accrue_stats(prev, cur, now)     # Phase 2：累计在线时长 + 采样人数
        self.state["online"] = cur
        self._save_state()
        await self._check_milestones(len(cur), days, maxn)   # 里程碑/成就播报

        # Phase 3：订阅@提醒（独立于上下线播报总开关）
        if joins:
            subs = self.state.get("subs", {})
            for uid in joins:
                nm = cur[uid]["name"]
                qqs = subs.get(nm)
                if qqs:
                    at = "".join(f"[CQ:at,qq={q}]" for q in qqs)
                    await self._broadcast_text(f"{at} 你订阅的 🟢 {nm} 上线啦！")

        if (joins or lefts) and self._notify_join_left() and not self._in_quiet():
            lines = []
            for uid in joins:
                info = cur[uid]
                lines.append(f"🟢 {info['name']} 上线了（Lv.{info['level']}）")
            for uid in lefts:
                info = prev[uid]
                dur = self._fmt_uptime(now - info.get("since", now))
                lines.append(f"⚪ {info.get('name', '玩家')} 下线了 · 本次在线 {dur}")
            tail = f"当前在线 {len(cur)}/{maxn}" if maxn else f"当前在线 {len(cur)}"
            await self._broadcast_text("【帕鲁服务器】\n" + "\n".join(lines) + f"\n———\n{tail}")

    # ------------------------------------------------------------------
    # Phase 2：在线统计 + 肝帝榜（数据在轮询中累计）
    # ------------------------------------------------------------------
    @staticmethod
    def _week_id_of(dt) -> str:
        y, w, _ = dt.isocalendar()
        return f"{y}-W{w:02d}"

    def _week_id(self) -> str:
        return self._week_id_of(datetime.now())

    @staticmethod
    def _parse_hhmm(s: str):
        try:
            hh, mm = str(s).strip().split(":")
            return int(hh) * 60 + int(mm)
        except (ValueError, AttributeError):
            return None

    def _today_top(self, top: int = 3) -> list[dict]:
        """今日在线时长排行(今日肝帝)。"""
        today = datetime.now().strftime("%Y-%m-%d")
        rows = []
        for t in self.state.get("totals", {}).values():
            d = t.get("day", 0) if t.get("day_id") == today else 0
            if d > 0:
                rows.append({"name": t.get("name", "玩家"), "sec": int(d)})
        rows.sort(key=lambda x: x["sec"], reverse=True)
        return rows[:top]

    def _last_week_board(self, week_id: str, top: int = 10) -> list[dict]:
        """上周肝帝榜(结算用)：合并未重置的 totals 与已归档 week_archive。"""
        board = {}
        for uid, t in self.state.get("totals", {}).items():
            if t.get("week_id") == week_id and t.get("week", 0) > 0:
                board[uid] = {"uid": uid, "name": t["name"], "sec": int(t["week"])}
        for uid, rec in self.state.get("week_archive", {}).get(week_id, {}).items():
            if rec.get("sec", 0) > 0 and uid not in board:
                board[uid] = {"uid": uid, "name": rec["name"], "sec": int(rec["sec"])}
        return sorted(board.values(), key=lambda x: x["sec"], reverse=True)[:top]

    # ------------------------------------------------------------------
    # Phase 5-④：定时早晚报 + 周肝帝结算
    # ------------------------------------------------------------------
    async def _check_schedules(self):
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        cur_min = now.hour * 60 + now.minute

        def due(time_str, last_key) -> bool:
            m = self._parse_hhmm(time_str)
            if m is None or self.state.get(last_key) == today:
                return False
            return m <= cur_min < m + 60   # 命中后 1 小时窗口内触发一次

        # 每日例行重启(帕鲁镜像 AUTO_REBOOT_CRON 等)感知：到点前 2 分钟发预告 +
        # 进维护静默，避免重启前低帧的 FPS 误报与重启瞬断的掉线/恢复误报。
        rb = self._parse_hhmm(self.config.get("daily_reboot_time", ""))
        if rb is not None and self.state.get("last_reboot_notice") != today:
            if max(rb - 2, 0) <= cur_min < rb + 1:   # 预告窗口：重启前 2 分钟内
                self.state["last_reboot_notice"] = today
                self._save_state()
                self._enter_maint(360)   # 静默覆盖重启全程(预告→重启→恢复，约 6 分钟)
                await self._broadcast_text(
                    "🔄 服务器将进行每日例行重启更新，预计 1 分钟左右完成，请稍候并注意保存进度～")

        if due(self.config.get("morning_report_time", "09:00"), "last_morning"):
            self.state["last_morning"] = today
            self._save_state()
            await self._send_daily_report("morning")
        if due(self.config.get("evening_report_time", "21:00"), "last_evening"):
            self.state["last_evening"] = today
            self._save_state()
            await self._send_daily_report("evening")
        # 周一肝帝结算
        st = self.config.get("weekly_settle_time", "10:00")
        m = self._parse_hhmm(st)
        if now.weekday() == 0 and m is not None and m <= cur_min < m + 60:
            last_wk = self._week_id_of(now - timedelta(days=1))   # 周日 => 上周
            if self.state.get("last_settled") != last_wk:
                self.state["last_settled"] = last_wk
                self._save_state()
                await self._do_settlement(last_wk)

    async def _send_daily_report(self, kind: str):
        okm, metrics, _ = await self._api_get("/v1/api/metrics")
        m = metrics if (okm and isinstance(metrics, dict)) else {}
        daily = self.state.get("stats", {}).get("daily", {})
        today = datetime.now().strftime("%Y-%m-%d")
        yday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        td, yd = daily.get(today, {}), daily.get(yday, {})
        cur = len(self.state.get("online", {}))
        data = {
            "kind": kind,
            "title": "🌅 帕鲁早报" if kind == "morning" else "🌃 帕鲁晚报",
            "greeting": "早安，冒险者～新的一天，帕鲁岛等你开荒！" if kind == "morning"
                        else "今天辛苦啦，来看看今日战报～",
            "online": okm,
            "cur": cur,
            "maxn": m.get("maxplayernum", self.state.get("maxn") or "—"),
            "fps": m.get("serverfps", "—"),
            "days": m.get("days", "—"),
            "today_peak": max(td.get("peak", 0), cur),
            "today_avg": round(td.get("sum", 0) / td["n"], 1) if td.get("n") else cur,
            "yday_peak": yd.get("peak", "—") if yd else "—",
            "show_yday": kind == "morning",
            "record": self.state.get("record_peak", max(td.get("peak", 0), cur)),
            "week_top": [{"name": r["name"], "dur": self._fmt_uptime(r["sec"])}
                         for r in self._rank_list(3)],
            "today_top": [{"name": r["name"], "dur": self._fmt_uptime(r["sec"])}
                          for r in self._today_top(3)],
        }
        await self._broadcast_card(self._t("daily"), data)

    async def _do_settlement(self, last_wk: str):
        board = self._last_week_board(last_wk, 10)
        if not board:
            return   # 上周无在线数据，不结算
        maxsec = board[0]["sec"]
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        online = set(self.state.get("online", {}))
        rows = [{
            "name": r["name"], "online": r["uid"] in online,
            "dur": self._fmt_uptime(r["sec"]),
            "pct": round(r["sec"] / maxsec * 100) if maxsec else 0,
            "medal": medals.get(i, str(i)),
        } for i, r in enumerate(board, 1)]
        await self._broadcast_card(self._t("rank"), {
            "rows": rows, "rank_title": "🏆 上周肝帝结算",
            "rank_sub": f"{last_wk} 周榜 · 恭喜上榜的肝帝们！"})
        # @ 上周肝帝(若绑定了 QQ)
        champ = board[0]
        champ_qq = None
        for qq, b in self.state.get("bindings", {}).items():
            if b.get("userId") == champ["uid"] or b.get("name") == champ["name"]:
                champ_qq = qq
                break
        at = f"[CQ:at,qq={champ_qq}] " if champ_qq else ""
        await self._broadcast_text(
            f"🎉 {at}恭喜「{champ['name']}」荣膺上周肝帝！在线 {self._fmt_uptime(champ['sec'])}，太肝了！")
        # 归档历史 + 清理上周 archive + 归零仍持有上周计时的玩家
        self.state.setdefault("history", {})[last_wk] = [{"name": r["name"], "sec": r["sec"]} for r in board]
        self.state.get("week_archive", {}).pop(last_wk, None)
        for t in self.state.get("totals", {}).values():
            if t.get("week_id") == last_wk:
                t["week"] = 0
                t["week_id"] = self._week_id()
        self._save_state()

    def _accrue_stats(self, prev: dict, cur: dict, now: int):
        """累计每人在线时长(肝帝榜) + 今日在线人数采样(峰值/均值)。"""
        last = self.state.get("last_poll")
        self.state["last_poll"] = now
        totals = self.state.setdefault("totals", {})
        wk = self._week_id()
        today = datetime.now().strftime("%Y-%m-%d")
        if last:
            delta = now - last
            if 0 < delta <= self._poll_interval() * 3:   # 跳过异常大间隔(如停服重启)
                for uid in cur:
                    if uid in prev:    # 本次与上次都在线 => 这段时间计入
                        t = totals.setdefault(uid, {"name": cur[uid]["name"], "total": 0, "week": 0, "week_id": wk})
                        # 周切换：先把上周时长归档(结算用)，再清零
                        if t.get("week_id") != wk:
                            if t.get("week_id") and t.get("week", 0) > 0:
                                self.state.setdefault("week_archive", {}).setdefault(
                                    t["week_id"], {})[uid] = {"name": t["name"], "sec": t["week"]}
                            t["week"] = 0
                            t["week_id"] = wk
                        # 日切换：清零今日(今日肝帝用，无需归档)
                        if t.get("day_id") != today:
                            t["day"] = 0
                            t["day_id"] = today
                        t["name"] = cur[uid]["name"]
                        t["total"] = t.get("total", 0) + delta
                        t["week"] = t.get("week", 0) + delta
                        t["day"] = t.get("day", 0) + delta
        # 夜猫子：凌晨 0-5 点在线过即标记
        if 0 <= datetime.now().hour < 5:
            for uid, info in cur.items():
                t = totals.setdefault(uid, {"name": info["name"], "total": 0, "week": 0, "week_id": wk})
                t["night"] = True
        # 今日在线人数采样
        daily = self.state.setdefault("stats", {}).setdefault("daily", {})
        today = datetime.now().strftime("%Y-%m-%d")
        d = daily.setdefault(today, {"peak": 0, "sum": 0, "n": 0})
        c = len(cur)
        d["peak"] = max(d["peak"], c)
        d["sum"] += c
        d["n"] += 1
        if len(daily) > 14:    # 只留近 14 天
            for k in sorted(daily)[:-14]:
                daily.pop(k, None)
        # 7×24 在线热力埋点：按 星期-小时 累计在线人数 + 采样次数(求平均)
        heat = self.state.setdefault("heat", {})
        hb = heat.setdefault(f"{datetime.now().weekday()}-{datetime.now().hour}", [0, 0])
        hb[0] += c
        hb[1] += 1

    def _rank_list(self, top: int = 10) -> list[dict]:
        """本周在线时长排行(肝帝榜)。"""
        wk = self._week_id()
        online = set(self.state.get("online", {}))
        rows = []
        for uid, t in self.state.get("totals", {}).items():
            wsec = t.get("week", 0) if t.get("week_id") == wk else 0
            if wsec <= 0:
                continue
            rows.append({"name": t.get("name", "玩家"), "sec": int(wsec), "online": uid in online})
        rows.sort(key=lambda x: x["sec"], reverse=True)
        return rows[:top]

    def _stats_data(self) -> dict:
        daily = self.state.get("stats", {}).get("daily", {})
        today = datetime.now().strftime("%Y-%m-%d")
        td = daily.get(today, {})
        cur = len(self.state.get("online", {}))
        peak = max(td.get("peak", 0), cur)
        avg = round(td.get("sum", 0) / td["n"], 1) if td.get("n") else cur
        days = []
        for i in range(6, -1, -1):
            ds = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            days.append({"label": ds[5:], "peak": daily.get(ds, {}).get("peak", 0)})
        maxp = max([x["peak"] for x in days] + [1])
        for x in days:
            x["h"] = round(x["peak"] / maxp * 100) if maxp else 0
        return {"cur": cur, "peak": peak, "avg": avg,
                "maxn": self.state.get("maxn") or "—", "days": days}

    # ------------------------------------------------------------------
    # Phase 5-①：里程碑 / 成就
    # ------------------------------------------------------------------
    async def _check_milestones(self, count: int, days, maxn):
        quiet = self._in_quiet()
        # 在线人数破纪录
        if self.config.get("notify_record", True):
            rec = self.state.get("record_peak", 0)
            if rec > 0 and count > rec and not quiet:    # rec>0 跳过冷启动
                await self._broadcast_text(
                    f"🎉 在线人数破纪录！当前 {count} 人同时在线（上次纪录 {rec}）。")
            if count > rec:
                self.state["record_peak"] = count
                self._save_state()
        # 世界天数里程碑
        if isinstance(days, int):
            # 冷启动：首次见到天数时，把"已经过去的"里程碑静默记下，不补报
            if "day_milestone" not in self.state:
                passed = [m for m in DAY_MILESTONES if m <= days]
                self.state["day_milestone"] = max(passed) if passed else 0
                self._save_state()
            elif self.config.get("notify_milestone", True):
                last = self.state.get("day_milestone", 0)
                crossed = [m for m in DAY_MILESTONES if last < m <= days]
                if crossed:
                    top = max(crossed)
                    self.state["day_milestone"] = top
                    self._save_state()
                    if not quiet:
                        await self._broadcast_text(f"🌍 帕鲁世界已度过 {top} 天！一起见证这段冒险～")

    # ------------------------------------------------------------------
    # Phase 5-②：运维增强（夜间静默 / FPS告警 / 设置变更 / 审计）
    # ------------------------------------------------------------------
    def _in_quiet(self) -> bool:
        """是否处于夜间静默时段(HH-HH)，期间不发非紧急播报。"""
        s = str(self.config.get("quiet_hours", "")).strip()
        if "-" not in s:
            return False
        try:
            a, b = s.split("-", 1)
            a = int(a.split(":")[0])
            b = int(b.split(":")[0])
        except (ValueError, IndexError):
            return False
        if a == b:
            return False
        h = datetime.now().hour
        return a <= h < b if a < b else (h >= a or h < b)   # 支持跨午夜

    async def _check_fps(self, fps):
        thr = int(self.config.get("fps_alert_threshold", 0))
        if thr <= 0 or not isinstance(fps, (int, float)):
            return
        low = fps < thr
        was_low = self.state.get("fps_low", False)
        if low != was_low:
            self.state["fps_low"] = low
            self._save_state()
            if low and not self._in_quiet() and not self._in_maint():
                await self._broadcast_text(
                    f"⚠️ 服务器 FPS 偏低：当前 {fps}（阈值 {thr}），可能卡顿，请管理员留意。")

    async def _check_settings_change(self):
        if not self.config.get("notify_settings_change", False):
            return
        now = time.time()
        if now - self.state.get("settings_checked", 0) < 600:   # 每 10 分钟才查一次
            return
        self.state["settings_checked"] = now
        ok, data, _ = await self._api_get("/v1/api/settings")
        if not ok or not isinstance(data, dict):
            return
        labels = {k: lab for lab, k, _ in SETTINGS_FIELDS}
        labels["bEnablePlayerToPlayerDamage"] = "PVP"
        snap = {k: data.get(k) for k in labels if k in data}
        old = self.state.get("settings_snap")
        self.state["settings_snap"] = snap
        self._save_state()
        if old is None:    # 首次仅记录基线
            return
        changes = [f"{labels.get(k, k)}：{old.get(k)} → {v}" for k, v in snap.items() if old.get(k) != v]
        if changes and not self._in_quiet():
            await self._broadcast_text("⚙️ 服务器设置变更：\n" + "\n".join(changes))

    def _week_top_uid(self) -> Optional[str]:
        wk = self._week_id()
        best, best_sec = None, 0
        for uid, t in self.state.get("totals", {}).items():
            s = t.get("week", 0) if t.get("week_id") == wk else 0
            if s > best_sec:
                best, best_sec = uid, s
        return best

    def _is_elder(self, qq: str) -> bool:
        """开荒元老：最早绑定的玩家。"""
        bs = self.state.get("bindings", {})
        me = bs.get(qq, {})
        if not me.get("ts"):
            return False
        return all(me["ts"] <= b.get("ts", float("inf")) for b in bs.values())

    def _titles_for(self, uid: str, qq: str) -> list[str]:
        titles = []
        if uid and uid == self._week_top_uid():
            titles.append("🔥本周肝帝")
        t = self.state.get("totals", {}).get(uid, {}) if uid else {}
        if t.get("night"):
            titles.append("🦉夜猫子")
        if self._is_elder(qq):
            titles.append("🌱开荒元老")
        return titles

    async def terminate(self):
        if getattr(self, "_poll_task", None):
            self._poll_task.cancel()
        if getattr(self, "_prewarm_task", None):
            self._prewarm_task.cancel()
        if self._session and not self._session.closed:
            await self._session.close()
        # 关闭本地渲染器(Chromium)
        try:
            await self._renderer.close()
        except Exception:  # noqa: BLE001
            pass
        logger.info(f"{LOG_PREFIX} 插件已卸载，轮询已停止，HTTP 会话已关闭")
