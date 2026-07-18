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
from .utils.text import _esc, clean_text, egg_to_cn  # noqa: F401
from .utils import security as _security
from .render.templates import (  # noqa: F401
    STYLES,
    TEMPLATE_KEYS,
    STYLE_NAMES,
    STYLE_ALIAS,
    MISSION_GROUP_CN,   # 支线委托 NPC 分组中文名(此前漏导致 /帕鲁支线 NameError)
)
# 命令注册表：子命令→处理器 的单一事实来源，驱动 _dispatch 与 _SUB_ALIASES。
from .commands.router import ALIAS_MAP as COMMAND_ALIAS_MAP, COMMAND_TOKENS, COMMANDS as COMMAND_SPECS
# 配置默认值(规范来源) + 启动合法性校验。
from . import config as _config
# 存档拉取/缓存/负缓存/强制存盘 编排服务（palsave.py 只管纯解析）。
from .services.save_service import SaveService
# REST 请求 + Docker socket 操作封装（含高危操作权限风险注释）。
from .api import palworld_api, docker_api
# 卡片渲染引擎(Jinja 缓存 + Playwright + html_render 兜底)。
from .render.renderer import Renderer
from .render.assets import AssetResolver


@register(
    "astrbot_plugin_palworld",
    "dalimao113",
    "帕鲁(Palworld)服务器查询与管理插件，所有回复输出精美卡片图片",
    "1.45.0",
    "https://github.com/dalimao113/astrbot_plugin_palworld",
)
class PalworldPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._cooldown: dict[str, float] = {}          # group_id -> 上次查询时间戳
        self._pending: dict[str, dict] = {}            # sender_id -> 待确认操作
        self._cooldown_map: dict[str, float] = {}      # sender_id -> 上次受冷却查询的时间戳(查询冷却)
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
        self._assets = AssetResolver(os.path.dirname(os.path.abspath(__file__)))  # ingame 图标/组件解析器
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
        def fresh() -> dict:   # 每次新建，避免默认 list/dict 被共享引用
            # tracking_started_at：累计总榜的统计起点。全新/重置 state 从今天起算(此前无累计数据)。
            return {"groups": [], "online": {}, "server_up": None, "fail_count": 0,
                    "initialized": False, "state_version": 1,
                    "tracking_started_at": datetime.now().strftime("%Y-%m-%d")}
        try:
            if self._state_path.exists():
                d = json.loads(self._state_path.read_text("utf-8"))
                if isinstance(d, dict):
                    had_track = "tracking_started_at" in d
                    for k, v in fresh().items():   # 向后兼容：补全旧版本缺失的字段
                        d.setdefault(k, v)
                    d["state_version"] = 1
                    # 历史 state:totals 是过去累加的,真实起点未知 → 不臆断日期,标 None(展示为"起点未记录")
                    if not had_track and d.get("totals"):
                        d["tracking_started_at"] = None
                    return d
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 状态文件读取失败，重置(损坏副本已保留供排查): {e}")
            try:   # 保留损坏副本，不直接丢弃(可能含绑定/审计)
                self._state_path.replace(
                    self._state_path.with_name(f"{self._state_path.name}.corrupt.{int(time.time())}"))
            except Exception:  # noqa: BLE001
                pass
        return fresh()

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
        """自动登记用过指令的群为广播目标。broadcast_whitelist_only 开启时不自动登记(仅显式白名单)。"""
        if self.config.get("broadcast_whitelist_only", False):
            return
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
        self._breed_meta: dict = {}      # 配种数据版本/来源元信息(game_version/generated_at/source)
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
            nm = (p.get("pal_name") or "").strip()   # 去首尾空格(如「黑月女王 」),防精确查询/关联失败
            p["pal_name"] = nm                         # 归一后写回内存对象,展示一致
            if not idx or not idx[0].isdigit() or not nm or nm == "zh_Hans_Text":
                continue   # 排除 Boss/人类(-1/-2)与未翻译占位
            ni = self._norm_idx(idx)
            self._pals.append(p)
            self._pal_idx[ni] = p
            # 同名(如「叶泥泥」本体 vs 花变种)：中文名索引优先指向可收集本体，不被变种后写覆盖
            existing = self._pal_by_name.get(nm)
            if existing is None or (p.get("is_collectible", True) and not existing.get("is_collectible", True)):
                self._pal_by_name[nm] = p
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
            self._breed_meta = bd.get("_meta", {})   # 数据版本/来源元信息(game_version/generated_at/source)
            for child, pairs in bd.items():
                if str(child).startswith("_"):   # _meta 等元数据键，非配种数据
                    continue
                c = self._norm_idx(child)
                for pa, pb in pairs:
                    a, b = self._norm_idx(pa), self._norm_idx(pb)
                    self._breed[frozenset((a, b))] = c
                    self._breed_rev.setdefault(c, []).append((a, b))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 配种表 data/breeding.json 加载失败: {e}")
        # 物品图鉴数据
        self._items: list = []
        self._item_by_name: dict = {}   # 中文名 -> 主体物品(同名优先无品阶/NPC 后缀的本体)
        self._items_by_name: dict = {}  # 中文名 -> [同名物品...](重名候选,不静默丢弃品阶/NPC 变体)
        self._item_by_id: dict = {}      # item_id -> item(取中文名/图标)
        self._item_id_ci: dict = {}      # 小写id -> 正确id(存档物品id大小写容错，如 bone->Bone)
        try:
            with open(os.path.join(base, "items.json"), encoding="utf-8") as _f:
                idata = json.loads(_f.read())
            for it in idata:
                nm = it.get("name")
                if it.get("item_id"):
                    self._item_by_id.setdefault(it["item_id"], it)
                    self._item_id_ci.setdefault(it["item_id"].lower(), it["item_id"])
                if nm and nm != "zh_Hans_Text":
                    self._items.append(it)
                    self._items_by_name.setdefault(nm, []).append(it)
            # 名称主键:同名不按文件顺序静默取首个,确定性优先"本体"(item_id 无 _2.._9 品阶、无 _NPC 后缀)
            for nm, group in self._items_by_name.items():
                self._item_by_name[nm] = min(group, key=self._item_variant_rank)
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
        # 研究所(1.0 新增) list + 名字索引 + 分类分组
        self._lab: list = []
        self._lab_by_name: dict = {}
        self._lab_by_cat: dict = {}
        try:
            with open(os.path.join(base, "lab_research.json"), encoding="utf-8") as _f:
                for it in json.loads(_f.read()):
                    nm = it.get("name")
                    if nm:
                        self._lab.append(it)
                        self._lab_by_name.setdefault(nm, it)
                        self._lab_by_cat.setdefault(it.get("category", "通用"), []).append(it)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 研究所数据 data/lab_research.json 加载失败: {e}")
        # 人类/NPC 名字(存档里能抓到人类:盗猎者/士兵/商人等,不在图鉴里)
        self._human_names: dict = {}
        try:
            with open(os.path.join(base, "human_names.json"), encoding="utf-8") as _f:
                self._human_names = (json.loads(_f.read()) or {}).get("names", {})
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 人类名字 data/human_names.json 加载失败: {e}")
        # 词条(被动技能) id -> {name,rank,sign,effect}; 主动技能枚举 -> 中文名
        self._passives: dict = {}
        self._wazas: dict = {}
        try:
            with open(os.path.join(base, "passives.json"), encoding="utf-8") as _f:
                self._passives = json.loads(_f.read())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 词条数据 data/passives.json 加载失败: {e}")
        # 被动技能的基础属性加成(HP/攻/防 %)，用于按游戏公式算准确当前属性
        self._passive_stat: dict = {}
        try:
            with open(os.path.join(base, "passive_stats.json"), encoding="utf-8") as _f:
                self._passive_stat = json.loads(_f.read())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 被动加成 data/passive_stats.json 加载失败: {e}")
        # 植入体(1.0) list + 名字/词条名索引（/帕鲁植入体）
        self._implants: list = []
        self._implant_by_name: dict = {}
        self._implant_by_id: dict = {}
        try:
            with open(os.path.join(base, "implants.json"), encoding="utf-8") as _f:
                self._implants = json.loads(_f.read())
            for im in self._implants:
                self._implant_by_name.setdefault(im["name"], im)   # 完整名唯一(区分耗材/永久)
                if im.get("item_id"):
                    self._implant_by_id.setdefault(im["item_id"], im)
        except Exception:  # noqa: BLE001
            pass
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
        # 头目/塔主固定刷新位置 {dev: {name,is_tower,points:[[l,t]],lv_min,lv_max}}（栖息地叠加显示）
        self._boss_spawns: dict = {}
        try:
            with open(os.path.join(base, "boss_spawns.json"), encoding="utf-8") as _f:
                self._boss_spawns = json.loads(_f.read())
        except Exception:  # noqa: BLE001
            pass
        # 任务(主线/支线) [{id,name,type,desc,objective,coords,exp,rewards,next,next_id,group,order}]（/帕鲁任务）
        self._missions: list = []
        self._mission_by_name: dict = {}       # 名 -> 主任务(重名取确定性主体)
        self._missions_by_name: dict = {}      # 名 -> [同名任务...](重名不静默丢弃,可列候选)
        self._mission_by_id: dict = {}         # id -> 任务(稳定主键)
        try:
            with open(os.path.join(base, "missions.json"), encoding="utf-8") as _f:
                self._missions = json.loads(_f.read())
            for m in self._missions:
                self._missions_by_name.setdefault(m["name"], []).append(m)
                if m.get("id"):
                    self._mission_by_id[m["id"]] = m
            # 名称主键:重名不按列表顺序覆盖,确定性优先主线、再非 _Replay、再 order/id
            for nm, group in self._missions_by_name.items():
                self._mission_by_name[nm] = min(group, key=self._mission_variant_rank)
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
        # 技能果实(1.0) list + 技能名/元素索引（/帕鲁技能果实）
        self._skill_fruits: list = []
        self._sf_by_tech: dict = {}
        self._sf_by_element: dict = {}
        try:
            with open(os.path.join(base, "skill_fruits.json"), encoding="utf-8") as _f:
                self._skill_fruits = json.loads(_f.read())
            for f in self._skill_fruits:
                self._sf_by_tech.setdefault(f["tech"], f)
                self._sf_by_element.setdefault(f["element"], []).append(f)
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
        # 帕鲁数量统一口径：可收集(官方正式图鉴,287) vs 数据实体(含变体/剧情boss,289)
        self._dex_total = len(self._pals)
        self._dex_collectible = sum(1 for p in self._pals if p.get("is_collectible", True))
        logger.info(f"{LOG_PREFIX} 图鉴 {self._dex_collectible} 只可收集(数据实体 {self._dex_total}) / "
                    f"配种 {len(self._breed)} 组合 / 物品 {len(self._items)} / 设施 {len(self._buildings)} / "
                    f"科技 {len(self._tech)} / 词条 {len(self._passives)} / 技能 {len(self._wazas)} 已加载")

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

    _HUMAN_WEAP = r"(_Rifle|_Shotgun|_Handgun|_Bat|_CrossBow|_FlameThrower|_GatlingGun|_GiantClub|_Spear|_MiniOilrig)"

    def _image_keys(self) -> set:
        if getattr(self, "_imgkeys", None) is None:
            d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images")
            try:
                self._imgkeys = {f[:-4] for f in os.listdir(d) if f.endswith(".png")}
            except OSError:
                self._imgkeys = set()
        return self._imgkeys

    def _human_icon(self, char_id: str) -> str:
        """抓到的人类 NPC -> 游戏人物头像(T_<key>_icon_normal 提取到 data/images)。容错武器/区域/编号后缀。"""
        cid = str(char_id or "")
        if not cid:
            return ""
        keys = self._image_keys()
        base_w = re.sub(self._HUMAN_WEAP + r"+$", "", cid)                       # 去武器后缀
        base_region = re.sub(r"(_Volcano|_Wander|_Green|_Snow|_Desert)\d*$", "", cid)
        base_pad = re.sub(r"(\d+)$", lambda m: f"{int(m.group(1)):02d}", cid)    # People2 -> People02
        cands = [cid, "Human_" + cid, base_w, base_region, base_pad,
                 cid + "01", base_w + "01", base_region + "01", re.sub(r"_v\d+$", "", cid)]
        for c in dict.fromkeys(cands):
            if c in keys:
                return self._pal_icon(c)
        for c in (cid, base_w, base_region):        # 前缀兜底(Male_Trader01 -> Male_Trader01_v04)
            m = next((k for k in keys if k.startswith(c)), None)
            if m:
                return self._pal_icon(m)
        return ""

    def _canon_iid(self, iid):
        """存档物品id -> items.json 里的正确大小写id(容错 bone->Bone)。找不到原样返回。"""
        if not iid:
            return iid
        return getattr(self, "_item_id_ci", {}).get(str(iid).lower(), iid)

    def _item_icon(self, item_id: str) -> str:
        """读取 data/images/items/<item_id>.png(游戏物品图标) -> base64 data uri。无图返回空。"""
        if not item_id:
            return ""
        item_id = self._canon_iid(item_id)   # 大小写容错(存档id如 bone -> Bone)
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
        # 习性(全部来自图鉴 DataTable 已有字段,不猜测):种属/遇敌AI/掠食者/夜行
        _GENUS_CN = {"Humanoid": "人形", "Bird": "鸟类", "FourLegged": "四足兽",
                     "Fish": "鱼类", "Dragon": "龙类", "Other": "其它"}
        _AI_CN = {"Friendly": "友好(不主动攻击)", "Escape_to_Battle": "先逃后战",
                  "Escape": "遇敌逃跑", "NotInterested": "无兴趣(不主动)",
                  "Warlike": "好战(主动攻击)", "Warlike_Anyway": "极度好战"}
        traits = []
        _g = _GENUS_CN.get(p.get("genus_category"))
        if _g:
            traits.append({"k": "种属", "v": _g})
        _ai = _AI_CN.get(p.get("ai_response"))
        if _ai:
            traits.append({"k": "遇敌", "v": _ai})
        if p.get("predator"):   # 官方 ENABLE_PREDATOR_BOSS_PAL 对应的掠食者
            traits.append({"k": "掠食者", "v": "夜间袭击"})
        if p.get("nocturnal"):
            traits.append({"k": "作息", "v": "夜行性"})
        # 公母比例(male_probability):偏离 50/50 才展示(默认均衡的不刷屏);配种/牧场参考
        _mp = p.get("male_probability")
        if isinstance(_mp, (int, float)) and 0 <= _mp <= 100 and int(_mp) != 50:
            _mp = int(_mp)
            traits.append({"k": "公母比", "v": f"♂{_mp}% ♀{100 - _mp}%"})
        _pn = p["pal_name"]
        return {
            "name": _pn, "index": p["pal_index"], "elements": p.get("elements", []),
            "traits": traits,
            "related": [f"/帕鲁栖息区域 {_pn}", f"/帕鲁反配种 {_pn}", f"/帕鲁推荐词条 {_pn}"],
            "icon": self._pal_icon(dev),
            "rarity": min(int(p.get("rarity", 0) or 0), 5), "nocturnal": bool(p.get("nocturnal")),
            "is_boss": bool(p.get("is_boss")), "is_tower_boss": bool(p.get("is_tower_boss")),
            "desc": clean_text(p.get("pal_description")),   # 详情页：完整,不截断(模板自动换行)
            "partner_title": p.get("partner_skill_title", ""),
            # 伙伴技能描述：游戏 1.0 未提供中文文本，缺时给诚实占位(不用工作适性瞎编，避免误导)
            "partner_desc": (clean_text(p.get("partner_skill_description"))
                             or ("该伙伴技能游戏内暂未提供中文详细说明" if p.get("partner_skill_title") else "")),
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
                               "k": "pal", "ik": p.get("pal_dev_name", ""),
                               "boss": ("tower" if p.get("is_tower_boss") else ("boss" if p.get("is_boss") else ""))}
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

    # 种属分类(genus_category,图鉴 DataTable 已有字段):无游戏图标 → Emoji 兜底
    _GENUS_MENU = [("人形", "Humanoid", "🧍"), ("四足兽", "FourLegged", "🐾"),
                   ("鸟类", "Bird", "🐦"), ("鱼类", "Fish", "🐟"),
                   ("龙类", "Dragon", "🐉"), ("其它", "Other", "❓")]
    _GENUS_ALIAS = {"人": "Humanoid", "人形": "Humanoid", "四足": "FourLegged", "四足兽": "FourLegged",
                    "兽": "FourLegged", "鸟": "Bird", "鸟类": "Bird", "鱼": "Fish", "鱼类": "Fish",
                    "龙": "Dragon", "龙类": "Dragon", "龙系": "Dragon", "其它": "Other", "其他": "Other"}

    def _genus_map(self) -> dict:
        if getattr(self, "_genus_cache", None) is None:
            self._genus_cache = {p.get("pal_dev_name"): p.get("genus_category") for p in self._pals}
        return self._genus_cache

    async def _cmd_genus(self, event: AstrMessageEvent, args: list[str]):
        if not self._pals:
            return await self._msg_card(event, "📕", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失或损坏。", color="#E5484D")
        query, page = self._parse_page_args(args)
        gmap = self._genus_map()
        if not query:                                # 分类菜单(带各种属数量)
            cnt = {}
            for e in self._ordered_pals():
                cnt[gmap.get(e["ik"])] = cnt.get(gmap.get(e["ik"]), 0) + 1
            lines = [f"{em} {cn} · {cnt.get(key, 0)} 只" for cn, key, em in self._GENUS_MENU if cnt.get(key)]
            return await self._msg_card(event, "🧬", "帕鲁种属分类",
                                        desc="\n".join(lines) + "\n\n发「/帕鲁种属 <种属>」看该类全部帕鲁,如 /帕鲁种属 龙",
                                        head="🧬 种属图鉴", color="#7ab8ff")
        key = self._GENUS_ALIAS.get(query) or next((k for cn, k, _ in self._GENUS_MENU if query in cn), None)
        if not key:
            alln = "、".join(cn for cn, _, _ in self._GENUS_MENU)
            return await self._msg_card(event, "🔍", "没有这个种属",
                                        desc=f"支持的种属：{alln}。\n如 /帕鲁种属 四足兽", color="#F5A623")
        cn, _, em = next(g for g in self._GENUS_MENU if g[1] == key)
        entries = [e for e in self._ordered_pals() if gmap.get(e["ik"]) == key]
        if not entries:
            return await self._msg_card(event, em, f"{cn}帕鲁暂无", desc="该种属下没有帕鲁。", color="#9a8a91")
        return await self._render_grid(event, f"{cn}帕鲁", em, entries, page, "/帕鲁种属", cn)

    @staticmethod
    def _pal_works(p: dict) -> list:
        """帕鲁工作适性 -> [{k:中文工种, lv:等级}]，按等级降序，只留 lv>0。
        中文工种键与模板 icons.work[...] 对齐（真实游戏工作图标，三主题共享）。"""
        return sorted(
            ({"k": WORK_LABELS.get(k, k), "lv": int(v)}
             for k, v in (p.get("work_suitability") or {}).items() if v and int(v) > 0),
            key=lambda w: -w["lv"])

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
                    "icon": self._pal_icon(x.get("pal_dev_name")), "works": self._pal_works(x)}
        # 子代继续配种：C + 亲A、C + 亲B 各能配出什么
        child_breeds = []
        for partner in (pa, pb):
            if partner["pal_name"] == child["pal_name"]:
                continue
            r = self._breed_result(child, partner)
            if r:
                child_breeds.append({"partner": partner["pal_name"], "result": r["pal_name"],
                                     "partner_icon": self._pal_icon(partner.get("pal_dev_name")),
                                     "result_icon": self._pal_icon(r.get("pal_dev_name")),
                                     "result_works": self._pal_works(r)})
        data = {"a": brief(pa), "b": brief(pb),
                "c": {**brief(child), "rarity": min(int(child.get("rarity", 0) or 0), 5)},
                "child_name": child["pal_name"], "child_breeds": child_breeds}
        return await self._img(event, self._t("breed"), data)

    @staticmethod
    def _item_variant_rank(it: dict):
        """同名物品排序键:本体(无 _2.._9 品阶、无 _NPC 后缀)排前;再按 item_id 短。用于确定性选主体。"""
        iid = it.get("item_id", "") or ""
        suffixed = 1 if re.search(r"_(?:[2-9]|NPC)$", iid) else 0
        return (suffixed, len(iid), iid)

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
        # 重量(item_extra.weight,影响负重;NPC 专用道具常为 99999 哨兵值,不展示)
        wt = ex.get("weight")
        try:
            wt = float(wt) if wt not in (None, "") else None
            if wt is not None and (wt <= 0 or wt >= 9999):
                wt = None
            elif wt is not None:
                wt = int(wt) if wt == int(wt) else round(wt, 1)
        except (TypeError, ValueError):
            wt = None
        # 描述:游戏物品表有则用;植入体游戏无物品描述→用其真实词条效果兜底(见 implants.json)
        desc = clean_text(it.get("description"))
        if not desc:
            im = (self._implant_by_id or {}).get(it.get("item_id"))
            if im:
                eff = (im.get("effect") or "").strip()
                psv = (im.get("passive") or "").strip()
                bits = []
                if psv:
                    bits.append(f"为帕鲁植入「{psv}」词条")
                if eff:
                    bits.append(f"效果：{eff}")
                if im.get("consumable"):
                    bits.append("（耗材型，使用后消耗）")
                desc = "。".join(b for b in bits if b)
        return self._img(event, self._t("item"), {
            "name": it["name"], "type": self._item_type_cn(it.get("type")),
            "description": desc,   # 详情:统一清洗,不截断
            "materials": mats, "benches": rec.get("bench", []),
            "price": price, "sphere": sphere, "weight": wt,
            "related": ([f"/帕鲁材料路线 {it['name']}", f"/帕鲁用途 {it['name']}"]
                        + ([f"/帕鲁哪里买 {it['name']}"] if price else [])),
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
        iid = self._canon_iid(query)                 # item_id 直查(大小写容错):精确取重名的某品阶/NPC 变体
        if iid in self._item_by_id:                  # 物品 id 是 ASCII dev 名,与中文名不冲突
            return await self._item_detail(event, self._item_by_id[iid])
        if query in self._item_by_name:              # 精确名 -> 详情(同名取本体)
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

    # 科技树(/帕鲁科技树 [等级]):把 tech.json 按解锁等级归档,做建造/科技进度路线图。
    # 纯已有数据(tech.json 的 level/points/is_boss),配真实游戏科技图标(_sub_icon)。
    def _techtree_index(self) -> dict:
        if getattr(self, "_tt_index", None) is None:
            idx: dict = {}
            for t in self._tech:
                idx.setdefault(int(t.get("level") or 0), []).append(t)
            self._tt_index = idx
        return self._tt_index

    async def _cmd_techtree(self, event: AstrMessageEvent, args: list[str]):
        if not self._tech:
            return await self._msg_card(event, "🔬", "科技数据未加载",
                                        desc="data/tech.json 缺失或损坏。", color="#E5484D")
        a = list(args)
        level = int(a[-1]) if a and a[-1].isdigit() else None
        idx = self._techtree_index()
        ancient_total = sum(1 for t in self._tech if t.get("is_boss"))
        if level is None:                            # 总览:各等级解锁数路线图
            levels = [{"lv": lv, "n": len(idx[lv]),
                       "ancient": sum(1 for x in idx[lv] if x.get("is_boss"))}
                      for lv in sorted(idx) if lv > 0]
            return await self._img(event, self._t("techtree"), {
                "mode": "overview", "levels": levels, "total": len(self._tech),
                "max_level": max((x["lv"] for x in levels), default=0), "ancient_total": ancient_total})
        items = idx.get(level, [])
        if not items:
            return await self._msg_card(event, "🔬", f"Lv.{level} 无新科技",
                                        desc=f"该等级没有解锁的科技。科技分布在 Lv.1~{max((k for k in idx if k>0), default=0)}。",
                                        color="#9a8a91")
        view = [{"name": t["name"], "icon": self._sub_icon("tech", t.get("id")),
                 "points": int(t.get("points") or 0), "ancient": bool(t.get("is_boss"))}
                for t in sorted(items, key=lambda x: (bool(x.get("is_boss")), x.get("name", "")))]
        return await self._img(event, self._t("techtree"), {
            "mode": "level", "level": level, "items": view,
            "points_total": sum(v["points"] for v in view if not v["ancient"]),
            "ancient_count": sum(1 for v in view if v["ancient"])})

    # 牧场产出总览(/帕鲁牧场 [产物]):组合已有数据——牧场适性帕鲁 × 伙伴技能里的产物。
    # 产物从"分派到家畜牧场"那句真实游戏文本里按物品名匹配;挖道具类如实标"随机道具"。
    def _ranch_index(self) -> list:
        if getattr(self, "_ranch_cache", None) is None:
            inames = [nm for nm in self._item_by_name if len(nm) >= 2]
            out = []
            for p in self._pals:
                if not (p.get("work_suitability") or {}).get("monster_farm"):
                    continue
                desc = p.get("partner_skill_description") or ""
                seg = desc.split("家畜牧场", 1)[1] if "家畜牧场" in desc else desc
                found = sorted({nm for nm in inames if nm in seg}, key=len, reverse=True)
                dedup = []
                for nm in found:                      # 去子串重复(留最长,如"帕鲁蛋"盖过"蛋")
                    if not any(nm in d and nm != d for d in dedup):
                        dedup.append(nm)
                if not dedup and "蛋" in seg:          # 皮皮鸡等"产下蛋":蛋非独立词条名
                    dedup = ["蛋"]
                products = [{"name": nm, "icon": self._item_icon((self._item_by_name.get(nm) or {}).get("item_id"))}
                            for nm in dedup]
                out.append({"pal": p["pal_name"], "icon": self._pal_icon(p.get("pal_dev_name", "")),
                            "products": products, "random": not dedup})
            out.sort(key=lambda x: (x["random"], x["pal"]))   # 有具体产物的在前
            self._ranch_cache = out
        return self._ranch_cache

    async def _cmd_ranch(self, event: AstrMessageEvent, args: list[str]):
        if not self._pals:
            return await self._msg_card(event, "🐑", "图鉴数据未加载", desc="data/paldex.json 缺失。", color="#E5484D")
        q = " ".join(args).strip()
        idx = self._ranch_index()
        if q:
            rows = [r for r in idx if any(q in pr["name"] for pr in r["products"])]
            if not rows:
                prods = sorted({pr["name"] for r in idx for pr in r["products"]})
                return await self._msg_card(event, "🔍", f"没有牧场产「{_esc(q)}」的帕鲁",
                                            desc="可产的有：" + "、".join(prods), color="#F5A623")
            title, sub = f"牧场产「{_esc(q)}」", f"共 {len(rows)} 只可产"
        else:
            title, sub = "牧场产出一览", f"共 {len(idx)} 只有牧场适性"
            rows = idx
        return await self._img(event, self._t("ranch"), {"title": title, "sub": sub, "rows": rows})

    _LAB_CAT_EMOJI = {"手工": "🔨", "点火": "🔥", "浇水": "💧", "播种": "🌱", "发电": "⚡",
                      "砍伐": "🪓", "采矿": "⛏️", "冷却": "❄️", "制药": "💊", "通用": "🔬"}
    # 研究所分类=工作适性 → 游戏工作图标 snake 键(三主题共享,经 game_icon 解析)
    _LAB_CAT_WORK = {"手工": "handcraft", "点火": "emit_flame", "浇水": "watering", "播种": "seeding",
                     "发电": "generate_electricity", "砍伐": "deforest", "采矿": "mining",
                     "冷却": "cool", "制药": "product_medicine"}

    def _lab_cat_icon(self, cat: str) -> str:
        """研究所分类的真实游戏工作图标 data URI(三主题共享);无对应/缺失返回空(模板回退 Emoji)。"""
        snake = self._LAB_CAT_WORK.get(cat)
        return self._assets.game_icon(f"work.{snake}") if snake else ""

    def _lab_detail(self, event, it: dict):
        cat = it.get("category", "通用")
        return self._img(event, self._t("lab_detail"), {
            "name": it["name"], "category": cat, "emoji": self._LAB_CAT_EMOJI.get(cat, "🔬"),
            "icon": self._lab_cat_icon(cat),
            "effect": it.get("effect", ""), "materials": it.get("materials", []),
            "prereq": it.get("prereq", ""), "work": it.get("work", 0),
            "essential": bool(it.get("essential"))})

    async def _cmd_lab(self, event: AstrMessageEvent, args: list[str]):
        if not self._lab:
            return await self._msg_card(event, "🔬", "研究所数据未加载",
                                        desc="data/lab_research.json 缺失或损坏。", color="#E5484D")
        query, _page = self._parse_page_args(args)
        if not query:
            cats = [{"name": c, "emoji": self._LAB_CAT_EMOJI.get(c, "🔬"), "icon": self._lab_cat_icon(c),
                     "count": len(v), "essential": sum(1 for x in v if x.get("essential"))}
                    for c, v in self._lab_by_cat.items()]
            return await self._img(event, self._t("lab_overview"), {"cats": cats, "total": len(self._lab)})
        if query in self._lab_by_cat:
            return await self._img(event, self._t("lab_list"),
                                   {"category": query + "研究", "emoji": self._LAB_CAT_EMOJI.get(query, "🔬"),
                                    "icon": self._lab_cat_icon(query),
                                    "items": self._lab_by_cat[query], "cat_short": query})
        mnum = re.match(r"^(.+?)(\d+)$", query)     # 分类+编号，如「手工1」=手工类第1项
        if mnum and mnum.group(1) in self._lab_by_cat:
            pool = self._lab_by_cat[mnum.group(1)]
            idx = int(mnum.group(2))
            if 1 <= idx <= len(pool):
                return await self._lab_detail(event, pool[idx - 1])
            return await self._msg_card(event, "🔢", "编号超出范围",
                                        desc=f"「{mnum.group(1)}」类共 {len(pool)} 项，没有第 {idx} 项。", color="#F5A623")
        if query in self._lab_by_name:
            return await self._lab_detail(event, self._lab_by_name[query])
        matches = [x for x in self._lab if query in x["name"]]
        if len(matches) == 1:
            return await self._lab_detail(event, matches[0])
        if not matches:
            return await self._msg_card(event, "🔍", "查无此研究",
                                        desc=f"没有名字含「{query}」的研究，也不是分类名"
                                             "(手工/点火/浇水/播种/发电/砍伐/采矿/冷却/制药)。", color="#F5A623")
        return await self._img(event, self._t("lab_list"),
                               {"category": f"含「{query}」的研究", "emoji": "🔬", "icon": "", "items": matches,
                                "cat_short": matches[0]["category"] if matches else "手工"})

    def _breed_result(self, pa: dict, pb: dict):
        ci = self._breed.get(frozenset((self._name_idx.get(pa["pal_name"]), self._name_idx.get(pb["pal_name"]))))
        return self._pal_idx.get(ci) if ci else None

    async def _cmd_reverse(self, event: AstrMessageEvent, args: list[str]):
        if not self._breed_rev:
            return await self._msg_card(event, "🔄", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        if not args:
            return await self._msg_card(event, "✏️", "请输入想配出的帕鲁",
                                        desc="用法：/帕鲁反配种 <帕鲁名>\n例：/帕鲁反配种 铠格力斯", color="#E5484D")
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
            "target_works": self._pal_works(p),
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
        # 目标在游戏里无任何配种配方(传说/特殊帕鲁 IgnoreCombi,如空涡龙)——只能捕捉,任何帕鲁都配不出
        if not self._breed_rev.get(target):
            return await self._msg_card(
                event, "🚫", "这只无法通过配种获得",
                desc=f"「{p['pal_name']}」在游戏里没有任何配种配方,属于只能捕捉/特殊获取的帕鲁,"
                     f"用任何帕鲁组合都配不出来。\n请去野外/头目/塔主处捕捉。", color="#F5A623")
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
            pp = self._resolve_owned_pal(str(pal.get("char_id", "")))   # 容错 BOSS_/元素变种前后缀
            if pp:
                owned.add(self._norm_idx(str(pp.get("pal_index", ""))))
        owned.discard("")
        if not owned:
            return await self._msg_card(event, "📦", "你的帕鲁箱是空的",
                                        desc="先去抓几只帕鲁，再来规划配种路线～", color="#9a8a91")
        already_owned = target in owned
        # 排除库存里目标本身:即便已拥有,也用「其他」帕鲁算出再配一只的路线(而非直接提示"已拥有")
        route = self._breed_route(owned - {target}, target)
        if not route:
            miss = "先去抓几只基础帕鲁" if not already_owned else "你现有的其他帕鲁还配不出它，需要更多基础帕鲁"
            return await self._msg_card(
                event, "🤷", "现有帕鲁配不出",
                desc=f"用你帕鲁箱里{'其他' if already_owned else '现在'}的帕鲁，暂时配不出「{p['pal_name']}」（{miss}）。\n"
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
            "target_works": self._pal_works(p),
            "steps": steps, "n_steps": len(steps),
            "sub": (f"你已有此帕鲁 · 用其他帕鲁再配一只 · {len(steps)} 步" if already_owned
                    else f"用你现有帕鲁 · {len(steps)} 步配出")})

    async def _cmd_breed_out(self, event: AstrMessageEvent, args: list[str]):
        """正向亲代展开:某帕鲁作为亲代 × 各搭档 → 能配出的全部后代(按后代稀有度降序,分页)。
        与 /帕鲁反配种(谁能配出它)互补——这里查「它能配出谁」。数据全来自 breeding.json。"""
        if not self._breed:
            return await self._msg_card(event, "🧬", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        q, page = self._parse_page_args(args)   # 末位数字=页码
        if not q:
            return await self._msg_card(event, "✏️", "请输入帕鲁名",
                                        desc="用法：/帕鲁配出谁 <帕鲁名>\n例：/帕鲁配出谁 棉悠悠\n"
                                             "会列出它作为亲代能配出的全部后代。", color="#E5484D")
        p = self._find_pal(q)
        if not p:
            sug = self._suggest_pals(q)
            return await self._msg_card(event, "🔍", "查无此帕鲁",
                                        desc=f"没找到「{q}」。" + ("\n是不是：" + "、".join(sug) if sug else ""),
                                        color="#F5A623")
        xi = self._norm_idx(str(p["pal_index"]))
        # 遍历正向表:X 参与的每个配对 → 后代;同一后代可由多个搭档配出，合并搭档集合
        child_partners: dict = {}
        for fs, child in self._breed.items():
            if xi in fs:
                rest = fs - {xi}
                partner = next(iter(rest)) if rest else xi   # rest 空=自配(X×X)
                child_partners.setdefault(child, set()).add(partner)
        if not child_partners:
            return await self._msg_card(
                event, "🚫", "这只不能作为亲代配种",
                desc=f"「{p['pal_name']}」在游戏里被标记为不可配种(传说/塔主/boss 等,如空涡龙),"
                     f"无法作为亲代配出任何后代。", color="#F5A623")

        def _rar(idx: str) -> int:
            return int((self._pal_idx.get(idx) or {}).get("rarity", 0) or 0)
        # 后代按稀有度降序(玩家最关心配出强的)，同稀有度按图鉴号
        children = sorted(child_partners.keys(),
                          key=lambda c: (-_rar(c), int(c) if str(c).isdigit() else 9999))
        PS = 10
        pages = max(1, (len(children) + PS - 1) // PS)
        page = min(max(1, page), pages)
        rows = []
        for c in children[(page - 1) * PS: page * PS]:
            cp = self._pal_idx.get(c) or {}
            r = _rar(c)
            partners = sorted(child_partners[c], key=lambda z: -_rar(z))
            rows.append({
                "name": cp.get("pal_name", c), "index": str(c),
                "icon": self._pal_icon(cp.get("pal_dev_name", "")),
                "rarity": r, "stars": min(r, 5), "elements": cp.get("elements", []),
                "works": self._pal_works(cp),
                "partners": [{"name": (self._pal_idx.get(z) or {}).get("pal_name", z),
                              "icon": self._pal_icon((self._pal_idx.get(z) or {}).get("pal_dev_name", ""))}
                             for z in partners]})
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁配出谁 {p['pal_name']} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("breedout"), {
            "target": p["pal_name"], "target_index": p["pal_index"],
            "target_icon": self._pal_icon(p.get("pal_dev_name")),
            "total": len(children), "page": page, "pages": pages, "rows": rows, "pager": pager})

    def _as_parent_map(self) -> dict:
        """惰性构建并缓存:亲代图鉴号 -> {能配出的后代号...}(供配种榜/正向展开)。"""
        ap = getattr(self, "_as_parent_cache", None)
        if ap is None:
            ap = {}
            for fs, child in self._breed.items():
                for x in fs:            # 自配 fs={X} 只遍历一次
                    ap.setdefault(x, set()).add(child)
            self._as_parent_cache = ap
        return ap

    async def _cmd_breed_rank(self, event: AstrMessageEvent, args: list[str]):
        """配种榜:每只帕鲁作为亲代能配出的不同后代数量降序排行(数据来自 breeding.json)。"""
        if not self._breed:
            return await self._msg_card(event, "🧬", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        _, page = self._parse_page_args(args)   # 榜无查询词,只取页码
        ap = self._as_parent_map()
        ranked = sorted(ap.items(),
                        key=lambda kv: (-len(kv[1]), int(kv[0]) if str(kv[0]).isdigit() else 9999))
        PS = 15
        pages = max(1, (len(ranked) + PS - 1) // PS)
        page = min(max(1, page), pages)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        rows = []
        base = (page - 1) * PS
        for i, (xi, kids) in enumerate(ranked[base: base + PS], base + 1):
            p = self._pal_idx.get(xi) or {}
            r = int(p.get("rarity", 0) or 0)
            rows.append({"rank": i, "medal": medals.get(i, str(i)),
                         "name": p.get("pal_name", xi), "index": str(xi),
                         "icon": self._pal_icon(p.get("pal_dev_name", "")),
                         "count": len(kids), "stars": min(r, 5),
                         "elements": p.get("elements", [])})
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁配种榜 {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("breedrank"), {
            "total": len(ranked), "page": page, "pages": pages, "rows": rows, "pager": pager})

    def _breed_route_to_set(self, owned: set, targets: set, tie_break=None, require_bred=False):
        """正向 BFS:从 owned 逐步配出更多,求配出 targets 中**任意**物种的最短链。
        返回 (命中物种号, 拓扑序步骤[(父A,父B,子)]) / None。步数最少优先;
        同步数用 tie_break(idx)->可比较值 降序打破(值越大越优,如工作适性等级)。
        require_bred=True:即使 owned 已含目标也强制展开配种,只认「配出来的」目标
        (用于「如何配出」,不把库存已有的那只当答案)。"""
        if not targets:
            return None
        reach = {o: None for o in owned}       # 节点 -> 亲代(a,b) 或 None(=拥有的叶子)
        depth = {o: 0 for o in owned}

        def _bred_hit():                       # 命中目标(require_bred 时只算配出来的)
            return {c for c in (set(reach) & targets)
                    if (not require_bred) or reach.get(c) is not None}
        if require_bred or not _bred_hit():    # owned 里尚无(可用)满足者才展开配种
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
                if _bred_hit() or not changed:
                    break
        cand = _bred_hit()
        if not cand:
            return None
        tb = tie_break or (lambda i: 0)

        def _steps_len(t):                     # 配出 t 的总配种次数(需配的祖先数)
            cnt, seen2, stack = 0, set(), [t]
            while stack:
                n = stack.pop()
                if n in seen2 or reach.get(n) is None:
                    continue
                seen2.add(n)
                cnt += 1
                a, b = reach[n]
                stack += [a, b]
            return cnt
        # 步数(总配种次数)最少优先;同步数 tie_break 大者优(如工作适性等级高)
        best = min(cand, key=lambda c: (_steps_len(c), -tb(c)))
        steps, seen = [], set()

        def expand(n):
            if n in seen or reach.get(n) is None:
                return
            seen.add(n)
            a, b = reach[n]
            expand(a)
            expand(b)
            steps.append((a, b, n))
        expand(best)
        return best, steps

    def _parse_work_target(self, args: list[str]):
        """解析 <工种> [等级] -> (wk_snake, lv, None) 或 (None, None, (emoji,title,desc,color))。"""
        if not args:
            works = "、".join(dict.fromkeys(WORK_LABELS.values()))
            return None, None, ("✏️", "请输入工种和等级",
                                f"用法：<工种> [最低等级]\n例：采矿 3\n支持工种：{works}", "#E5484D")
        wk = WORK_ALIAS.get(args[0]) or (args[0] if args[0] in WORK_LABELS else None)
        if not wk:
            works = "、".join(dict.fromkeys(WORK_LABELS.values()))
            return None, None, ("🔍", "未知工种", f"没有工种「{args[0]}」。\n支持：{works}", "#F5A623")
        lv = 1
        if len(args) >= 2 and str(args[1]).isdigit():
            lv = max(1, int(args[1]))
        return wk, lv, None

    async def _cmd_breed_worksuit(self, event: AstrMessageEvent, args: list[str]):
        """通用查询:列出所有满足「工种≥等级」的帕鲁 + 各自的配种组合(不看库存)。
        工作适性是物种固定值,故先按工种等级降序列出目标帕鲁,再给出配出它的亲代组合。"""
        if not self._breed_rev:
            return await self._msg_card(event, "🧬", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        wk, lv, err = self._parse_work_target(args)
        if err:
            return await self._msg_card(event, err[0], err[1], desc=err[2], color=err[3])
        wk_cn = WORK_LABELS.get(wk, wk)

        def _wlv(idx: str) -> int:
            return int(((self._pal_idx.get(idx) or {}).get("work_suitability") or {}).get(wk, 0) or 0)
        targets = [self._norm_idx(str(p["pal_index"]))
                   for p in self._pals if _wlv(self._norm_idx(str(p["pal_index"]))) >= lv]
        if not targets:
            top = max((_wlv(self._norm_idx(str(p["pal_index"]))) for p in self._pals), default=0)
            return await self._msg_card(
                event, "🤷", "没有这么高适性的帕鲁",
                desc=f"没有帕鲁的「{wk_cn}」适性达到 Lv{lv}(全图鉴最高 Lv{top})。\n换个更低等级再试。",
                color="#F5A623")
        # 工种等级降序,同级按图鉴号；第 3 个数字参数=页码(工种/等级各占前两位)
        targets = sorted(set(targets),
                         key=lambda i: (-_wlv(i), int(i) if str(i).isdigit() else 9999))
        page = 1
        if len(args) >= 3 and str(args[2]).isdigit():
            page = int(args[2])
        PS = 8
        pages = max(1, (len(targets) + PS - 1) // PS)
        page = min(max(1, page), pages)
        rows = []
        for t in targets[(page - 1) * PS: page * PS]:
            tp = self._pal_idx.get(t) or {}
            combos_raw = self._breed_rev.get(t, [])
            combos = []
            for a, b in combos_raw[:3]:
                pa, pb = self._pal_idx.get(a) or {}, self._pal_idx.get(b) or {}
                combos.append({"a": pa.get("pal_name", a), "a_icon": self._pal_icon(pa.get("pal_dev_name", "")),
                               "b": pb.get("pal_name", b), "b_icon": self._pal_icon(pb.get("pal_dev_name", ""))})
            r = int(tp.get("rarity", 0) or 0)
            rows.append({"name": tp.get("pal_name", t), "index": str(t),
                         "icon": self._pal_icon(tp.get("pal_dev_name", "")),
                         "wlv": _wlv(t), "stars": min(r, 5), "elements": tp.get("elements", []),
                         "combos": combos, "more": max(0, len(combos_raw) - 3),
                         "no_recipe": not combos_raw})
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁配工种 {wk_cn} {lv} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("workcombo"), {
            "work": wk_cn, "lv": lv, "total": len(targets),
            "page": page, "pages": pages, "rows": rows, "pager": pager})

    async def _cmd_my_breed_worksuit(self, event: AstrMessageEvent, args: list[str]):
        """用你帕鲁箱现有帕鲁,规划配出满足「工种≥等级」帕鲁的配种链(步数最少)。
        即使库存已有满足者也**继续给配种链**(require_bred);配不出/太长回退通用最短链。"""
        if not self._breed_rev:
            return await self._msg_card(event, "🧬", "配种数据未加载",
                                        desc="data/breeding.json 缺失或损坏。", color="#E5484D")
        wk, lv, err = self._parse_work_target(args)
        if err:
            return await self._msg_card(event, err[0], err[1], desc=err[2], color=err[3])
        wk_cn = WORK_LABELS.get(wk, wk)

        def _wlv(idx: str) -> int:
            return int(((self._pal_idx.get(idx) or {}).get("work_suitability") or {}).get(wk, 0) or 0)
        targets = {self._norm_idx(str(p["pal_index"]))
                   for p in self._pals if _wlv(self._norm_idx(str(p["pal_index"]))) >= lv}
        if not targets:
            top = max((_wlv(self._norm_idx(str(p["pal_index"]))) for p in self._pals), default=0)
            return await self._msg_card(
                event, "🤷", "没有这么高适性的帕鲁",
                desc=f"没有帕鲁的「{wk_cn}」适性达到 Lv{lv}(全图鉴最高 Lv{top})。\n换个更低等级再试。",
                color="#F5A623")
        # 读库存
        owned: set = set()
        self._last_save_use = time.time()
        profiles = await self._fetch_save_profiles(max_age=self._fresh_ttl())
        qq = str(event.get_sender_id())
        sp = self._match_save_profile(self.state.get("bindings", {}).get(qq), profiles) if profiles else None
        if sp is None:
            return await self._msg_card(
                event, "🔗", "读不到你的帕鲁箱",
                desc="请先 /帕鲁绑定 <游戏名> 并上线一次，让我能读到你的帕鲁箱。\n"
                     "（也可发 /帕鲁配工种 " + wk_cn + " " + str(lv) + " 看通用配种组合）", color="#F5A623")
        for pal in sp.get("party", []) + sp.get("palbox", []):
            pp = self._resolve_owned_pal(str(pal.get("char_id", "")))   # 容错 BOSS_/元素变种前后缀
            if pp:
                owned.add(self._norm_idx(str(pp.get("pal_index", ""))))
        owned.discard("")
        if not owned:
            return await self._msg_card(event, "📦", "你的帕鲁箱是空的",
                                        desc="先去抓几只帕鲁，再来规划配种～", color="#9a8a91")
        # 强制配出(即使已有满足者也给配种链);库存配不出或 >8 步回退通用
        MAX_INV_STEPS = 8
        inv = self._breed_route_to_set(owned, targets, _wlv, require_bred=True)
        if inv and len(inv[1]) <= MAX_INV_STEPS:
            best, mode = inv, "库存"
        else:
            nodes: set = set()
            for fs, c in self._breed.items():
                nodes |= set(fs)
                nodes.add(c)
            uni = self._breed_route_to_set(nodes - targets, targets, _wlv)
            if uni:
                best, mode = uni, "通用"
            elif inv:
                best, mode = inv, "库存"
            else:
                best, mode = None, "库存"
        if not best:
            return await self._msg_card(
                event, "🤷", "配不出这个适性",
                desc=f"用你现有的帕鲁暂时配不出「{wk_cn}≥Lv{lv}」的帕鲁。\n"
                     f"可发 /帕鲁配工种 {wk_cn} {lv} 看通用配法，或去野外捕捉。", color="#F5A623")
        tgt, route = best
        tp = self._pal_idx.get(tgt) or {}
        owned_mark = owned if mode == "库存" else set()
        steps = []
        for i, (a, b, c) in enumerate(route, 1):
            pa, pb, pc = self._pal_idx.get(a), self._pal_idx.get(b), self._pal_idx.get(c)
            steps.append({
                "n": i,
                "a": (pa or {}).get("pal_name", a), "a_icon": self._pal_icon((pa or {}).get("pal_dev_name", "")),
                "a_owned": a in owned_mark,
                "b": (pb or {}).get("pal_name", b), "b_icon": self._pal_icon((pb or {}).get("pal_dev_name", "")),
                "b_owned": b in owned_mark,
                "c": (pc or {}).get("pal_name", c), "c_icon": self._pal_icon((pc or {}).get("pal_dev_name", "")),
                "is_target": c == tgt})
        if mode == "库存":
            sub = f"目标 {wk_cn}≥Lv{lv} · 用你现有帕鲁 · {len(steps)} 步配出 {tp.get('pal_name', tgt)}（{wk_cn}Lv{_wlv(tgt)}）"
        else:
            sub = f"目标 {wk_cn}≥Lv{lv} · 通用配法(库存不足,亲代需自行获得) · {len(steps)} 步 → {tp.get('pal_name', tgt)}（{wk_cn}Lv{_wlv(tgt)}）"
        return await self._img(event, self._t("route"), {
            "target": tp.get("pal_name", tgt), "target_icon": self._pal_icon(tp.get("pal_dev_name", "")),
            "target_works": self._pal_works(tp),
            "steps": steps, "n_steps": len(steps), "sub": sub})

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
        # query_cooldown<=0 显式关闭冷却(私人小群可关)；否则不低于硬下限。
        cd = int(self.config.get("query_cooldown", 10))
        return 0 if cd <= 0 else max(cd, HARD_MIN_COOLDOWN)

    def _admins(self) -> list[str]:
        return [str(q).strip() for q in (self.config.get("admin_qq") or []) if str(q).strip()]

    def _is_admin(self, qq: str) -> bool:
        return str(qq) in self._admins()

    def _is_trusted(self, qq: str) -> bool:
        """受信任用户(管理员 或 trusted_qq 白名单):admin_confirm 绑定模式下仍可直接自绑。"""
        if self._is_admin(qq):
            return True
        return str(qq) in {str(q).strip() for q in (self.config.get("trusted_qq") or []) if str(q).strip()}

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
        """播报目标群。配了 broadcast_groups 白名单就只用它;
        broadcast_whitelist_only=True 时**只**认白名单(白名单空则不播报,绝不回退自动登记群,防误发误邀群);
        否则(默认)回退到用过指令自动登记的群。"""
        cfg = [str(g).strip() for g in (self.config.get("broadcast_groups") or []) if str(g).strip()]
        if self.config.get("broadcast_whitelist_only", False):
            return cfg   # 严格白名单:空则不播报
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
            base = configured.rsplit("/", 1)[0]
            # 安全护栏:误配置(如填 "/" 或过浅路径)会让 base 变空/过短,下游
            # 删档/恢复脚本的 rm -rf "$base"/*/ 可能误删容器内顶层目录 → 回退默认基目录。
            if base.startswith("/") and base.count("/") >= 3:
                return base
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
        try:
            progress = palsave.extract_all_progress(save_dir)   # 玩家进度记录(小队进度用)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 进度记录解析失败: {e}")
            progress = {}
        return {"profiles": profiles, "guilds": guilds, "progress": progress}

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
            # 传送点/遗物雕像/地牢入口(从关卡对象提取的真实坐标点集,可选文件)
            def _load_pts(fname):
                try:
                    with open(os.path.join(base, fname), encoding="utf-8") as _f:
                        return [(n, d["X"], d["Y"]) for n, d in json.loads(_f.read()).items()]
                except Exception:  # noqa: BLE001
                    return []
            self._ft_points = _load_pts("map_ft_points.json")
            self._relic_points = _load_pts("map_relics.json")
            self._dungeon_points = _load_pts("map_dungeons.json")
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
            # 世界树独立地图 + 变换(栖息地/boss 在世界树区域时用；缺失则回退主图)
            self._tree_map_img = None
            self._tree_mu = self._tree_mv = None
            tree_hd = os.path.join(base, "treemap_hd.jpg")
            tree_tf = os.path.join(base, "map_transform_tree.json")
            if os.path.exists(tree_hd) and os.path.exists(tree_tf):
                with open(tree_hd, "rb") as _f:
                    self._tree_map_img = "data:image/jpeg;base64," + base64.b64encode(_f.read()).decode("ascii")
                with open(tree_tf, encoding="utf-8") as _f:
                    _tt = json.loads(_f.read())
                self._tree_mu, self._tree_mv = _tt["mu"], _tt["mv"]
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

    # 地图注册表:map_id -> (中文名, 图片属性名, 变换属性 mu, 变换属性 mv)。
    # 主大陆与世界树是**独立坐标系**,按各自仿射把世界坐标归属到所属地图,不 clamp。
    _MAP_REGISTRY = (
        ("main", "主大陆", "_map_img", "_map_mu", "_map_mv"),
        ("tree", "世界树", "_tree_map_img", "_tree_mu", "_tree_mv"),
    )

    def _classify_map(self, wx: float, wy: float):
        """按各地图仿射变换判断世界坐标属于哪张地图。返回 (map_id, left%, top%)。
        都不落在任何已知地图内 -> ('unknown', None, None)。**归类前不 clamp**,越界不压边缘。"""
        lo, hi = -3.0, 103.0   # 允许边缘少量溢出(玩家贴边)
        for mid, _label, _img, mu_attr, mv_attr in self._MAP_REGISTRY:
            mu, mv = getattr(self, mu_attr, None), getattr(self, mv_attr, None)
            if not mu or not mv:
                continue
            left = (mu[0] * wx + mu[1] * wy + mu[2]) * 100.0
            top = (mv[0] * wx + mv[1] * wy + mv[2]) * 100.0
            if lo <= left <= hi and lo <= top <= hi:
                return mid, left, top
        return "unknown", None, None

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
        groups: dict = {}     # map_id -> [player...]
        offmap: list = []     # 无法归类的玩家(不压到主图边缘,单列显示)
        total = 0
        for i, p in enumerate(raw, 1):
            try:
                wx = float(p.get("location_x")); wy = float(p.get("location_y"))
            except (TypeError, ValueError):
                continue
            total += 1
            mid, left, top = self._classify_map(wx, wy)   # 不 clamp
            gx = round((wy - 158000) / 459)   # 世界坐标 -> 游戏内地图坐标(与游戏地图一致)
            gy = round((wx + 123888) / 459)
            region = (self._nearest_region(wx, wy) if mid == "main"
                      else ("世界树" if mid == "tree" else "区域待确认"))
            pd = {"no": i, "name": p.get("name") or "玩家", "level": p.get("level", "?"),
                  "region": region, "coord": f"{gx}, {gy}",
                  "left": round(left, 2) if left is not None else None,
                  "top": round(top, 2) if top is not None else None}
            if mid == "unknown":
                offmap.append(pd)
            else:
                groups.setdefault(mid, []).append(pd)
        if not total:
            return await self._msg_card(event, "🗺️", "当前无人在线",
                                        desc="服务器现在没有在线玩家，地图上没有可标注的位置。", color="#9a8a91")
        # 按注册表顺序组装每张有玩家的地图面板
        maps = []
        for mid, label, img_attr, _mu, _mv in self._MAP_REGISTRY:
            ps = groups.get(mid)
            img = getattr(self, img_attr, None)
            if ps and img:
                maps.append({"map_id": mid, "label": label, "mapimg": img, "players": ps})
        sub = f"{total} 人在线 · {datetime.now().strftime('%H:%M')}"
        return await self._img(event, self._t("map"),
                               {"subtitle": sub, "maps": maps, "offmap": offmap},
                               width=MAP_WIDTH, dsf=1.6)

    # ------------------------------------------------------------------
    # 地图收集/地标标注(/帕鲁地图收集 [类别]):把带世界坐标的地标/传送点标到世界地图上。
    # 说明:游戏文件里没有单个"露娜妹雕像/遗物宝箱"的逐点坐标,故标注的是**命名地标 +
    #      传送点 + 禁猎区**这类有坐标的采集/探索目标点,不臆造不存在的坐标。
    # ------------------------------------------------------------------
    _POI_CATS = (
        ("禁猎区", "🛡️", ("禁猎区", "Sanctuary", "Wildlife")),
        ("遗迹遗址", "🏛️", ("遗址", "遗迹", "教堂", "教会", "祭祀", "要塞", "废弃", "环形门", "高塔", "遇难船")),
        ("聚落村镇", "🏘️", ("聚落", "村", "镇", "城市", "城")),
        ("洞窟秘道", "🕳️", ("洞窟", "密道", "洞")),
        ("孤岛秘境", "🏝️", ("孤岛",)),
        ("其它地标", "📌", ()),   # 兜底:不属于上面任何类的命名地标
    )
    _POI_PAGE = 200   # 收集图是"完整参考图",尽量一页标全(点多才有用)

    def _poi_index(self) -> dict:
        """类别 -> [(name, wx, wy)]。传送点来自 ft_points;其余按名字关键词归入地标类(首个命中)。"""
        if getattr(self, "_poi_cache", None) is None:
            cats = {"传送点": list(getattr(self, "_ft_points", []) or []),
                    "遗物雕像": list(getattr(self, "_relic_points", []) or []),
                    "地牢入口": list(getattr(self, "_dungeon_points", []) or [])}
            for cn, _emoji, _kws in self._POI_CATS:
                cats.setdefault(cn, [])
            for name, wx, wy in (self._map_regions or []):
                placed = False
                for cn, _emoji, kws in self._POI_CATS[:-1]:
                    if any(k in name for k in kws):
                        cats[cn].append((name, wx, wy)); placed = True
                        break
                if not placed:
                    cats["其它地标"].append((name, wx, wy))
            self._poi_cache = {k: v for k, v in cats.items() if v}
        return self._poi_cache

    async def _cmd_poimap(self, event: AstrMessageEvent, args: list[str]):
        if not self._load_map():
            return await self._msg_card(event, "🗺️", "地图素材缺失",
                                        desc="data/worldmap_hd.jpg / map_transform.json 未就绪。", color="#E5484D")
        idx = self._poi_index()
        query, page = self._parse_page_args(args)
        emoji_of = {"传送点": "📍", "遗物雕像": "🗿", "地牢入口": "🕳️", **{cn: em for cn, em, _ in self._POI_CATS}}
        if not query:                                # 类别菜单
            lines = [f"{emoji_of.get(cn, '📌')} {cn} · {len(pts)} 处" for cn, pts in idx.items()]
            return await self._msg_card(event, "🗺️", "地图地标 / 收集点",
                                        desc="\n".join(lines) + "\n\n发「/帕鲁地图收集 <类别>」把该类标到世界地图上,如 /帕鲁地图收集 遗物雕像\n"
                                        "坐标从游戏关卡对象直接提取,名称按就近地标标注(遗物/地牢无官方逐点名)。",
                                        head="🗺️ 地图收集", color="#7ab8ff")
        qn = query.replace("其他", "其它")   # 常见异写归一(其他=其它)
        cat = next((c for c in idx if qn == c or qn in c or c in qn), None)
        if not cat:
            return await self._msg_card(event, "🔍", "没有这个类别",
                                        desc="可选：" + "、".join(idx.keys()) + "\n如 /帕鲁地图收集 遗迹遗址", color="#F5A623")
        # 世界坐标 -> 主图百分比(只标能归到主大陆的点,世界树点跳过)
        pts = []
        for name, wx, wy in idx[cat]:
            mid, left, top = self._classify_map(float(wx), float(wy))
            if mid != "main":
                continue
            gx = round((float(wy) - 158000) / 459)
            gy = round((float(wx) + 123888) / 459)
            pts.append({"name": clean_text(name), "left": round(left, 2), "top": round(top, 2),
                        "coord": f"{gx}, {gy}"})
        if not pts:
            return await self._msg_card(event, "🗺️", f"{cat} 无可标注点", desc="该类地标不在主大陆地图范围内。", color="#9a8a91")
        total = len(pts)
        pages = max(1, (total + self._POI_PAGE - 1) // self._POI_PAGE)
        page = min(max(1, page), pages)
        chunk = pts[(page - 1) * self._POI_PAGE: page * self._POI_PAGE]
        for i, p in enumerate(chunk, 1):
            p["no"] = (page - 1) * self._POI_PAGE + i
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁地图收集 {cat} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("poimap"), {
            "title": f"{emoji_of.get(cat, '📌')} {cat}", "sub": f"共 {total} 处 · 第 {page}/{pages} 页",
            "mapimg": self._map_img, "points": chunk, "pager": pager}, width=MAP_WIDTH, dsf=1.6)

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

    # 属性名归一化(火/火系/火属性/fire → 火属性),供「按属性列帕鲁」用
    _ELEM_ALIAS = {"fire": "火属性", "water": "水属性", "grass": "草属性", "leaf": "草属性",
                   "electric": "雷属性", "thunder": "雷属性", "elec": "雷属性", "dark": "暗属性",
                   "ground": "地属性", "earth": "地属性", "ice": "冰属性", "dragon": "龙属性",
                   "neutral": "无属性", "normal": "无属性", "none": "无属性"}
    for _b in ("无", "草", "水", "火", "雷", "暗", "地", "冰", "龙"):
        for _form in (_b, _b + "系", _b + "属性"):
            _ELEM_ALIAS[_form] = _b + "属性"
    del _b, _form

    def _elem_map(self) -> dict:
        if getattr(self, "_elem_cache", None) is None:
            self._elem_cache = {p.get("pal_dev_name"): (p.get("elements") or []) for p in self._pals}
        return self._elem_cache

    async def _cmd_element(self, event: AstrMessageEvent, args: list[str] | None = None):
        if not self._elements:
            return await self._msg_card(event, "⚔️", "克制数据缺失",
                                        desc="data/elements.json 未就绪。", color="#E5484D")
        query, page = self._parse_page_args(list(args or []))
        if query and query not in ("克制", "克制图", "关系", "图", "克制关系"):
            el = self._ELEM_ALIAS.get(query)
            if not el:
                return await self._msg_card(event, "🔍", "没有这个属性",
                                            desc="支持：草 / 水 / 火 / 雷 / 暗 / 地 / 冰 / 龙 / 无。\n如 /帕鲁属性 火\n(看克制关系发 /帕鲁属性克制)",
                                            color="#F5A623")
            emap = self._elem_map()
            entries = [e for e in self._ordered_pals() if el in emap.get(e["ik"], [])]
            if not entries:
                return await self._msg_card(event, "⚔️", f"{el}帕鲁暂无", desc="该属性下没有帕鲁。", color="#9a8a91")
            return await self._render_grid(event, f"{el}帕鲁", "⚔️", entries, page, "/帕鲁属性", query)
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

    # 栖息特殊点(非野生热区)种类:kind -> (符号, 中文标注, 是否头目档, 排序, 地图标记色)。
    # 地图上用小圆点标记(按此色 + 白边),既小又能按颜色区分种类;符号只用于图例/副标题文字。
    _HAB_KINDS = {
        "tower":   ("🗼", "塔主", True, 0, "#ffcc33"),
        "fboss":   ("👑", "野外头目", True, 1, "#ff4d4d"),
        "dboss":   ("👑", "地牢头目", True, 2, "#c062ff"),
        "prison":  ("⛓️", "关押头目", True, 3, "#ff7a3d"),
        "dungeon": ("🚪", "地牢", False, 4, "#5b9bff"),
    }

    def _habitat_data(self, p: dict) -> dict:
        dev = p.get("pal_dev_name", "")
        sp = (self._pal_spawns or {}).get(dev) or {}
        # 主大陆点(day/night，主图百分比) 与 世界树点(tree_day/tree_night，世界树图百分比)
        # 是**两套独立坐标系**，各自落各自底图，不混用。
        day = sp.get("day") or []
        night = sp.get("night") or []
        tree_day = sp.get("tree_day") or []
        tree_night = sp.get("tree_night") or []
        main_pts = list(day) + list(night)
        tree_pts = list(tree_day) + list(tree_night)
        els = p.get("elements", []) or []
        cn = els[0].replace("属性", "").strip() if els else ""
        color = (self._elements or {}).get(cn, {}).get("color") or "#ff6a3d"
        # 热区要鲜艳:无属性(灰 #9CA3AF)在地图上几乎看不见,提亮成暖橙;其余属性色本身够艳。
        if color.upper() in ("#9CA3AF", "#9CA3AFFF"):
            color = "#FF8C42"
        tree_img = getattr(self, "_tree_map_img", None)
        # 特殊点(地牢/头目)。**野外头目/地牢头目/地牢/关押 一律用权威 spawner 提取的 spots**
        # (坐标+等级都取自 DT_PalSpawnerPlacement/WildSpawner);外部 boss_spawns.json 经核对有
        # 假点/多点(如云海鹿多编一个不存在的头目点),故只保留它独有的**塔主**(高塔不在刷新表)。
        bs = (self._boss_spawns or {}).get(dev) or {}
        raw_spots: list = []          # (region, l, t, kind)
        lv_by_kind: dict = {}         # kind -> [min, max]
        if bs.get("points") and bs.get("is_tower"):
            bs_region = "tree" if bs.get("region") == "tree" else "main"
            for x, y in bs["points"]:
                raw_spots.append((bs_region, x, y, "tower"))
            if bs.get("lv_min"):
                lv_by_kind["tower"] = [bs["lv_min"], bs.get("lv_max", bs["lv_min"])]
        # 地牢刷新是**按地牢随机池**——常见野生帕鲁也会作为地牢(头目)出现在大量地牢里,
        # 对有野外热区的帕鲁这些点是噪声(不是"去哪找它")。故地牢/地牢头目仅在该帕鲁**无野生
        # 热区**(地牢是其主要栖息)时显示;野外头目/关押是固定单点,始终显示。
        has_wild = bool(main_pts or tree_pts)
        spot_lv = sp.get("spot_lv") or {}
        for l, t, kind, region in sp.get("spots", []):
            if kind in ("dungeon", "dboss") and has_wild:
                continue
            if kind in self._HAB_KINDS:
                raw_spots.append((region, l, t, kind))
                if kind in spot_lv:
                    lv_by_kind[kind] = spot_lv[kind]
        # 选底图:主大陆有内容(野生热区 或 头目/塔主/boss 坐标) > 世界树有内容。
        # 头目/塔主/boss 的具体坐标要能显示出来,故其所在区域参与选图(不被跨区野生盖掉)。
        main_content = bool(main_pts) or any(r == "main" for r, _, _, _ in raw_spots)
        tree_content = bool(tree_pts) or any(r == "tree" for r, _, _, _ in raw_spots)
        use_tree = bool((not main_content) and tree_content and tree_img)
        region_sel = "tree" if use_tree else "main"
        pts = tree_pts if use_tree else main_pts
        # 生物群系占比只对主大陆野生有意义(世界树是独立小地图，不按主图群系归属)
        region_count: dict = {}
        if not use_tree:
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
        # 只保留与所选底图同区域的特殊点(避免主图上画世界树坐标、或反之)
        sel = [(l, t, kind) for region, l, t, kind in raw_spots if region == region_sel]
        markers = []
        kind_count: dict = {}
        for l, t, kind in sel:
            sym, label, boss_tier, _o, mcolor = self._HAB_KINDS[kind]
            markers.append({"l": round(l, 2), "t": round(t, 2), "sym": sym, "boss": boss_tier, "c": mcolor})
            kind_count[kind] = kind_count.get(kind, 0) + 1
        # 图例(带数量/等级/颜色) + 副标题类型标签,按种类排序
        legend, kinds = [], []
        if points:
            kinds.append({"sym": "🔥", "label": "野生", "c": color})
        for kind in sorted(kind_count, key=lambda k: self._HAB_KINDS[k][3]):
            sym, label, _b, _o, mcolor = self._HAB_KINDS[kind]
            lr = lv_by_kind.get(kind)
            lvs = ("" if not lr else (f"Lv.{lr[0]}" if lr[0] == lr[1] else f"Lv.{lr[0]}~{lr[1]}"))
            detail = (f"{lvs} · " if lvs else "") + f"{kind_count[kind]}处"
            legend.append({"sym": sym, "label": label, "detail": detail, "c": mcolor})
            kinds.append({"sym": sym, "label": label, "c": mcolor})
        has_day = bool(tree_day if use_tree else day)
        has_night = bool(tree_night if use_tree else night)
        # 地牢刷新规则说明(有地牢/地牢头目标记时展示,解释地图上的点是什么)
        dungeon_note = ""
        if kind_count.get("dungeon") or kind_count.get("dboss"):
            dungeon_note = ("地牢帕鲁按「地牢随机池」刷新:进入地牢后从该地牢的帕鲁池里随机抽取,"
                            "不是每次必刷。图中标的是**该帕鲁可能出现的地牢入口位置**,"
                            "进对应地牢多刷几次即可遇到。")
        return {"name": p["pal_name"], "index": p.get("pal_index", "?"),
                "icon": self._pal_icon(dev), "elements": els, "color": color,
                "mapimg": (self._tree_map_img if use_tree else self._map_img),
                "map_label": ("世界树" if use_tree else ""),
                "points": points, "regions": regions,
                "markers": markers, "legend": legend, "kinds": kinds,
                "dungeon_note": dungeon_note,
                "nocturnal": bool(p.get("nocturnal")), "count": len(pts),
                "has_day": has_day, "has_night": has_night,
                # 兼容旧测试键(templates 已改用 markers/legend/kinds)
                "boss_points": markers}

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
        if not data["points"] and not data["markers"]:
            return await self._msg_card(event, "🗺️", f"{p['pal_name']} 无固定刷新坐标",
                                        desc="游戏刷新表里没有该帕鲁的固定坐标(野外/地牢/头目均无)——通常靠 配种／捕食者游荡刷新／剧情或活动 获取。",
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
            rkey, rcolor = self._passive_rank_meta(rk, int(m.get("sign") or 1))
            return {"name": m.get("name", ""), "effect": m.get("effect", ""),
                    "rank": rk, "stars": "★" * rk, "rank_key": rkey, "color": rcolor}

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
    # 词条大全（/帕鲁词条大全）：全部被动词条按类别查询 + 详情
    # ------------------------------------------------------------------
    _PASSDEX_CATS = ["攻击", "防御", "生命", "工作", "移动", "元素", "生存", "训练师", "其他"]
    _PASSDEX_ICON = {"攻击": "⚔️", "防御": "🛡️", "生命": "❤️", "工作": "🔨",
                     "移动": "💨", "元素": "🔮", "生存": "🍖", "训练师": "🧑", "其他": "✨"}
    # 词条分类 → 游戏内数值图标键(有对应的用真实游戏图标,其余回退 emoji)
    _PASSDEX_STAT = {"攻击": "attack", "防御": "defense", "生命": "hp", "工作": "work_speed",
                     "移动": "speed", "生存": "hunger"}
    _PASSDEX_COLOR = {"攻击": "#e15b5b", "防御": "#5b9ae1", "生命": "#5cc97a", "工作": "#e6942e",
                      "移动": "#2ec8b0", "元素": "#b06ee0", "生存": "#e8c466", "训练师": "#9aa6c0", "其他": "#c9a86a"}

    @staticmethod
    def _passive_category(pid: str, effect: str) -> str:
        p = str(pid).lower(); e = effect or ""
        if p.startswith("trainer"):
            return "训练师"
        if "element" in p or "属性" in e or "抗性" in e:
            return "元素"
        if "attack" in p or "atk" in p or "攻击" in e:
            return "攻击"
        if "deffence" in p or "defense" in p or "防御" in e:
            return "防御"
        if p.startswith("hp") or "_hp" in p or "生命" in e or "体力" in e:
            return "生命"
        if any(w in p for w in ("workspeed", "craftspeed", "mining", "logging", "collection", "handcraft", "farm")) \
                or any(w in e for w in ("工作", "采集", "挖矿", "砍伐", "制作", "农")):
            return "工作"
        if any(w in p for w in ("movespeed", "swimspeed", "ridespeed", "dash", "muteki")) \
                or any(w in e for w in ("移动", "游泳", "骑乘", "冲刺")):
            return "移动"
        if any(w in p for w in ("sanity", "stomach", "stamina")) \
                or any(w in e for w in ("理智", "饱食", "耐力", "SAN")):
            return "生存"
        return "其他"

    @staticmethod
    def _passive_rank_meta(rank: int, sign: int) -> tuple:
        """词条等级/正负 → (游戏箭头图标键, 品阶颜色)。
        游戏真实有 6 档箭头(T_icon_skillstatus_rank_arrow_00~05):
          减益↓ / +1↑ / +2↑↑ / +3↑↑↑ / +4(↑↑↑加号) / +5(↑↑↑钻石,最高档)。
        颜色按档位递进,金色(+3)之上还有紫(+4)/青虹(+5)——即"比金色更好"的彩色高阶词条。"""
        if sign < 0:
            return "rank_down", "#e0685f"          # 减益(↓ 红)
        r = rank or 1
        if r >= 5:
            return "rank_up5", "#35e0d8"           # +5 顶阶(3↑+钻石):青虹(最高,比金更好)
        if r == 4:
            return "rank_up3_plus", "#c58cff"      # +4(3↑+加号):紫(比金更好)
        if r == 3:
            return "rank_up3", "#ffce4a"           # +3(↑↑↑):金
        if r == 2:
            return "rank_up2", "#6fcf7f"           # +2(↑↑):绿
        return "rank_up1", "#cfd6e4"               # +1(↑):银白

    def _passive_item(self, name: str, effect: str, rank: int, sign: int) -> dict:
        key, color = self._passive_rank_meta(rank, sign)
        return {"name": name, "effect": effect, "rank": rank, "sign": sign,
                "rank_key": key, "color": color}

    def _passdex_group(self) -> dict:
        if getattr(self, "_passdex_cache", None) is None:
            from collections import defaultdict
            g = defaultdict(list)
            for pid, v in (self._passives or {}).items():
                cat = self._passive_category(pid, v.get("effect", ""))
                g[cat].append(self._passive_item(v.get("name", pid), v.get("effect", ""),
                                                 int(v.get("rank", 0) or 0), int(v.get("sign", 0) or 0)))
            for c in g:
                g[c].sort(key=lambda x: (-x["rank"], x["name"]))
            self._passdex_cache = dict(g)
        return self._passdex_cache

    async def _cmd_passive_dex(self, event: AstrMessageEvent, args: list):
        if not self._passives:
            return await self._msg_card(event, "📜", "词条数据缺失",
                                        desc="data/passives.json 未就绪。", color="#E5484D")
        g = self._passdex_group()
        q = " ".join(args).strip().rstrip("类")
        if not q:
            cats = [{"name": c, "emoji": self._PASSDEX_ICON.get(c, "✨"),
                     "icon": (self._assets.game_icon(f"stat.{self._PASSDEX_STAT[c]}")
                              if (c in self._PASSDEX_STAT and getattr(self, "_assets", None)) else ""),
                     "color": self._PASSDEX_COLOR.get(c, "#c9a86a"), "count": len(g.get(c, [])),
                     "sample": "、".join(x["name"] for x in g.get(c, [])[:4])}
                    for c in self._PASSDEX_CATS if g.get(c)]
            return await self._img(event, self._t("passdex"),
                                   {"cats": cats, "total": sum(len(v) for v in g.values())})
        if q in self._PASSDEX_CATS:
            items = g.get(q, [])
            return await self._img(event, self._t("passlist"),
                                   {"cat": q + "类词条", "icon": self._PASSDEX_ICON.get(q, "✨"),
                                    "color": self._PASSDEX_COLOR.get(q, "#c9a86a"),
                                    "items": items, "count": len(items)})
        # 词条名模糊查询 → 命中列表
        hits = [{**x, "cat": c} for c, lst in g.items() for x in lst
                if q in x["name"] or x["name"] in q]
        if hits:
            return await self._img(event, self._t("passlist"),
                                   {"cat": f"含「{q}」的词条", "icon": "🔍", "color": "#c9a86a",
                                    "items": hits, "count": len(hits)})
        return await self._msg_card(event, "🔍", "查无此词条",
                                    desc=f"没有名字含「{q}」的词条。\n发「/帕鲁词条大全」看全部分类。", color="#F5A623")

    # 词条查帕鲁(/帕鲁词条查 <词条名>):列出你队伍/帕鲁箱里带某词条的帕鲁,帕鲁多了也能一键定位。
    def _passfind_row(self, pal: dict, matched: set, loc: str):
        pv = [str(x) for x in (pal.get("passives") or [])]
        hit = [pid for pid in pv if pid in matched]
        if not hit:
            return None
        cid = str(pal.get("char_id", ""))
        meta = self._resolve_owned_pal(cid)                # 容错 BOSS_/元素变种前后缀
        hname = None if meta else self._human_name(cid)    # 抓到的人类/头目给中文名
        disp = [self._passive_view(pid) for pid in hit]
        return {
            "name": _esc(meta["pal_name"] if meta else (hname or cid or "未知帕鲁")),
            "icon": self._pal_icon(meta.get("pal_dev_name", "")) if meta else (self._human_icon(cid) if hname else ""),
            "elements": meta.get("elements", []) if meta else [],
            "is_human": bool(hname),
            "nickname": _esc(pal.get("nickname") or ""), "level": pal.get("level", 1), "loc": loc,
            "lucky": bool(pal.get("lucky")), "alpha": bool(pal.get("is_alpha")),
            "matched": [{"name": _esc(m["name"]), "rank_key": m["rank_key"], "hex": m["hex"]} for m in disp],
            "total_passives": len(pv)}

    async def _cmd_passive_find(self, event: AstrMessageEvent, args: list[str]):
        if not self._passives:
            return await self._msg_card(event, "📜", "词条数据未加载", desc="data/passives.json 未就绪。", color="#E5484D")
        a = list(args)
        pick = 0
        if len(a) > 1 and a[-1].isdigit():        # 结果后带编号 -> 看那只详情
            pick = int(a[-1]); a = a[:-1]
        q = " ".join(a).strip()
        if not q:
            return await self._msg_card(event, "✏️", "查你哪只帕鲁带某词条",
                                        desc="用法：/帕鲁词条查 <词条名> [结果编号]\n列出你队伍/帕鲁箱里带这个词条的帕鲁;帕鲁太多也能一键定位。\n再发「/帕鲁词条查 <词条名> <编号>」看列表里第几只的完整详情。\n例：/帕鲁词条查 提升攻击　→　/帕鲁词条查 提升攻击 2",
                                        head="🔎 词条查帕鲁", color="#7ab8ff")
        exact = {pid for pid, v in self._passives.items() if (v.get("name") or "") == q}
        matched = exact or {pid for pid, v in self._passives.items() if q in (v.get("name") or "")}
        if not matched:
            return await self._msg_card(event, "🔍", "没有这个词条",
                                        desc=f"没找到名字含「{_esc(q)}」的词条。\n发「/帕鲁词条大全」看全部词条。", color="#F5A623")
        matched_names = sorted({self._passives[pid].get("name") or pid for pid in matched})
        sp, uname, err = await self._resolve_target_sp(event, [])   # 仅自己(隐私门控)
        if err:
            return err
        matches = []   # [(展示行, 原始 pal dict)]
        for p in (sp.get("party") or []):
            r = self._passfind_row(p, matched, "队伍")
            if r:
                matches.append((r, p))
        for i, p in enumerate(self._palbox_sorted(sp.get("palbox") or []), 1):
            r = self._passfind_row(p, matched, f"箱 #{i}")
            if r:
                matches.append((r, p))
        if not matches:
            return await self._msg_card(event, "📦", f"你没有带「{_esc(q)}」的帕鲁",
                                        desc="队伍/帕鲁箱里没有帕鲁带这个词条。", head="🔎 词条查帕鲁", color="#9a8a91")
        if 1 <= pick <= len(matches):             # 指定编号 -> 那只完整详情(复用队伍卡)
            row, pal_obj = matches[pick - 1]
            pv = self._pal_view(pal_obj)
            return await self._img(event, self._t("team"),
                                   {"title": f"🔎 带「{_esc(q)}」· 第 {pick} 只",
                                    "subtitle": f"{pv['name']}（图鉴 #{pv['index']}） · {row['loc']}",
                                    "pals": [pv]})
        rows = []
        for no, (r, _) in enumerate(matches, 1):
            r["no"] = no
            rows.append(r)
        return await self._img(event, self._t("passfind"), {
            "query": _esc(q), "owner": _esc(uname or ""), "total": len(rows),
            "matched_names": [_esc(n) for n in matched_names], "rows": rows})

    # ------------------------------------------------------------------
    # 任务（/帕鲁任务 /帕鲁主线 /帕鲁支线）
    # ------------------------------------------------------------------
    @staticmethod
    def _mission_variant_rank(m: dict):
        """同名任务排序键:主线优先、非 _Replay 优先、再按 order/id。用于确定性选主体。"""
        mid = m.get("id", "") or ""
        return (m.get("type") != "主线", mid.endswith("_Replay"),
                str(m.get("order") or 9999), mid)

    def _find_mission(self, q: str):
        """按 id / 名 精确定位单个任务;重名(需候选消歧)返回 None。"""
        q = (q or "").strip()
        if not q:
            return None
        if q in self._mission_by_id:                 # id 主键直查(ASCII dev 名,与中文名不冲突)
            return self._mission_by_id[q]
        group = self._missions_by_name.get(q)
        if group:
            return group[0] if len(group) == 1 else None   # 重名 -> None,交由候选列表
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
            "order": (m.get("order") if isinstance(m.get("order"), int) else 0) if is_main else 0,
            "order_total": sum(1 for x in self._missions if x.get("type") == "主线"),
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
        # 重名(同名多条)时用 id 消歧:brief 带 id,提示按 id 精确查,避免其中一条被永久遮蔽
        ambiguous = len(self._missions_by_name.get(q, [])) > 1
        rows = [{"tag": (str(x["order"]) if x["type"] == "主线" else "支"), "name": x["name"],
                 "brief": ((x.get("objective") or (f"经验+{x['exp']}" if x.get("exp") else ""))
                           + (f" · id:{x['id']}" if ambiguous else ""))} for x in hits[:30]]
        hint = f"/帕鲁任务 {hits[0]['id']}" if ambiguous else f"/帕鲁任务 {hits[0]['name']}"
        return await self._img(event, self._t("missionlist"),
                               {"title": f"📜 含「{q}」的任务", "subtitle": f"{len(hits)} 个",
                                "rows": rows, "detailhint": hint, "pagehint": ""})

    @staticmethod
    def _order_int(m: dict) -> int:
        """任务 order 归一成 int(用于排序,兼容 str/空/缺失,不再混类型崩溃)。无有效 order 排最后。"""
        o = m.get("order")
        try:
            return int(o)
        except (TypeError, ValueError):
            return 9999

    async def _cmd_mainquest(self, event: AstrMessageEvent, args: list):
        if not self._missions:
            return await self._msg_card(event, "📜", "任务数据未加载", desc="data/missions.json 缺失。", color="#E5484D")
        mains = sorted([m for m in self._missions if m["type"] == "主线"],
                       key=lambda x: (self._order_int(x), x.get("id", "")))
        page = 1
        if args and args[-1].isdigit():
            page = max(1, int(args[-1]))
        size = 16
        total_pages = max(1, (len(mains) + size - 1) // size)
        page = min(page, total_pages)
        chunk = mains[(page - 1) * size: page * size]
        rows = [{"tag": (str(m["order"]) if str(m.get("order", "")).strip() not in ("", "9999") else "主"),
                 "name": m["name"],
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
        page = max(1, int(args[-1])) if args and args[-1].isdigit() else 1
        size = 20
        total_pages = max(1, (len(subs) + size - 1) // size)
        page = min(page, total_pages)
        chunk = subs[(page - 1) * size: page * size]
        rows = [{"tag": MISSION_GROUP_CN.get(m.get("group", ""), "委托")[:2], "name": m["name"],
                 "brief": (m.get("desc", "")[:22] or m.get("objective", ""))} for m in chunk]
        sub = f"共 {len(subs)} 个 · 第 {page}/{total_pages} 页" + (f" · {q}" if q else " · 8 类 NPC 委托")
        nextpage = f"/帕鲁支线 {q + ' ' if q else ''}{page + 1}"
        pagehint = (f"发「{nextpage}」看下一页" if page < total_pages
                    else ("可加 NPC 名筛选，如 /帕鲁支线 农民" if not q else ""))
        return await self._img(event, self._t("missionlist"),
                               {"title": "📋 支线任务", "subtitle": sub, "rows": rows,
                                "detailhint": f"/帕鲁任务 {chunk[0]['name']}" if chunk else "/帕鲁任务 <名>",
                                "pagehint": pagehint})

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

    @staticmethod
    def _fmt_drop(d) -> str:
        """把掉落项(dict 或字符串)格式化成可读文案：名称 ×数量 · 概率。"""
        if not isinstance(d, dict):
            return str(d)
        name = str(d.get("name") or "").strip()
        if not name:
            return ""
        parts = [name]
        qty = str(d.get("qty") or "").strip()
        if qty and qty not in ("1", "1~1"):
            parts.append(f"×{qty}")
        rate = d.get("rate")
        if isinstance(rate, (int, float)) and rate:
            rate_s = f"{rate:g}%"
            parts.append("必掉" if rate >= 100 else rate_s)
        elif isinstance(rate, str) and rate.strip():
            parts.append(rate.strip())
        return " ".join(parts)

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
        loc = b.get("location") or ""
        if is_tower:
            tip_parts.append("塔主战限时、限带 5 只帕鲁，注意躲技能、备好治疗")
        elif "召唤的祭坛" in loc:
            tip_parts.append(f"需合成「{b.get('pal') or b.get('short') or b['name']}的石板」，再到「召唤的祭坛」召唤挑战")
            tip_parts.append("石板碎片可从掉落/换购获得，集齐合成石板；血厚建议多人速攻")
        elif "掠夺者" in loc:
            tip_parts.append("掠夺者在野外随机出没，等级很高，击败可得「捕食者核心」「究极帕鲁之魂」")
        else:
            tip_parts.append("野外头目血厚，建议多人或满配队伍速攻")
        return {"name": b.get("short") or b["name"], "emoji": "🗼" if is_tower else "👹",
                "catlabel": b.get("category", "Boss"), "color": color,
                "elements": [e + "属性" for e in els], "difficulty": b.get("difficulty", ""),
                "level": b.get("level", ""), "hp": b.get("hp", ""), "location": b.get("location", ""),
                "drops": [s for s in (self._fmt_drop(d) for d in (b.get("drops") or [])) if s],
                "icon": self._pal_icon(b.get("dev", "")),
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
        fpals = (self._fishing or {}).get("fish_pals") or []
        rows = [{"name": c["name"], "sub": (f"×{c['qty']}" if c.get("qty") and c["qty"] != "1" else ""),
                 "right": c.get("rate", "")} for c in catch]
        rows += [{"name": f["name"], "sub": f.get("size", ""), "right": "🐟可钓"} for f in fpals]
        badges = [f"{len(catch)} 种钓获物"]
        if fpals:
            badges.append(f"{len(fpals)} 种可钓帕鲁")
        return await self._img(event, self._t("merchant"),
                               {"emoji": "🎣", "title": "🎣 钓鱼可获得",
                                "badges": badges,
                                "note": "在水边用钓竿钓鱼，有概率钓上以下物品，也能钓到水系帕鲁（标🐟）：",
                                "rows": rows,
                                "foot": "钓点遍布各水域；稀有设计图/钥匙/帕鲁之魂、以及各种水系帕鲁都能钓到。"})

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

    def _skillfruit_detail(self, event, f: dict):
        color = (self._elements or {}).get(f["element"], {}).get("color") or "#e8c466"
        return self._img(event, self._t("skillfruit"), {
            "tech": f["tech"], "fruit_name": f["fruit_name"], "element": f["element"],
            "emoji": ELEM_EMOJI.get(f["element"], "✨"), "color": color,
            "power": f["power"], "cooldown": f["cooldown"], "effect": f.get("effect", ""),
            "desc": f.get("desc", ""), "icon": self._item_icon(f["fruit_id"])})

    async def _cmd_skillfruit(self, event: AstrMessageEvent, args: list):
        if not self._skill_fruits:
            return await self._msg_card(event, "🍐", "技能果实数据未加载",
                                        desc="data/skill_fruits.json 缺失或损坏。", color="#E5484D")
        q, page = self._parse_page_args(args)
        ELS = ("无", "火", "水", "雷", "草", "冰", "地", "暗", "龙")

        def _ent(pool):   # no=序号(供「元素+编号」查询，如 火1)
            return [{"no": str(i + 1), "name": f["tech"], "k": "item", "ik": f["fruit_id"]} for i, f in enumerate(pool)]
        if not q:
            return await self._render_grid(event, "技能果实图鉴", "🍐",
                                           _ent(self._skill_fruits), page, "/帕鲁技能果实", "")
        if q in ELS:
            return await self._render_grid(event, f"{q}属性技能果实", "🍐",
                                           _ent(self._sf_by_element.get(q, [])), page, "/帕鲁技能果实", q)
        mnum = re.match(r"^(.+?)(\d+)$", q)        # 元素+编号，如「火1」=火属性第1个
        if mnum and mnum.group(1) in ELS:
            pool = self._sf_by_element.get(mnum.group(1), [])
            idx = int(mnum.group(2))
            if 1 <= idx <= len(pool):
                return await self._skillfruit_detail(event, pool[idx - 1])
            return await self._msg_card(event, "🔢", "编号超出范围",
                                        desc=f"「{mnum.group(1)}」属性共 {len(pool)} 个技能果实，没有第 {idx} 个。", color="#F5A623")
        if q in self._sf_by_tech:                 # 技能名精确命中
            return await self._skillfruit_detail(event, self._sf_by_tech[q])
        matches = [x for x in self._skill_fruits if q in x["tech"] or q in x["fruit_name"]]
        if len(matches) == 1:
            return await self._skillfruit_detail(event, matches[0])
        if not matches:
            return await self._msg_card(event, "🔍", "查无此技能果实",
                                        desc=f"没有教「{q}」的技能果实。\n可按属性查，如 /帕鲁技能果实 火。", color="#F5A623")
        return await self._render_grid(event, f"含「{q}」的技能果实", "🍐", _ent(matches), page, "/帕鲁技能果实", q)

    def _implant_detail(self, event, im: dict):
        return self._img(event, self._t("implant"), {
            "name": im["name"], "passive": im["passive"], "effect": im.get("effect", ""),
            "rank": im.get("rank", 0), "sign": im.get("sign", 0),
            "consumable": bool(im.get("consumable")), "icon": self._item_icon(im["item_id"])})

    async def _cmd_implant(self, event: AstrMessageEvent, args: list):
        if not self._implants:
            return await self._msg_card(event, "🧬", "植入体数据未加载",
                                        desc="data/implants.json 缺失或损坏。", color="#E5484D")
        q, page = self._parse_page_args(args)
        gidx = {im["item_id"]: i + 1 for i, im in enumerate(self._implants)}   # 全局序号(按稀有度排序)

        def _ent(pool):   # no=全局编号(供纯数字查询)；名字用完整名(区分永久/耗材，避免重名)
            return [{"no": str(gidx[im["item_id"]]), "name": im["name"], "k": "item", "ik": im["item_id"]} for im in pool]
        if not q:                                 # 纯数字被当页码：/帕鲁植入体 1 = 第1页
            return await self._render_grid(event, "植入体图鉴", "🧬", _ent(self._implants), page, "/帕鲁植入体", "")
        exact = self._implant_by_name.get(q)      # 完整名精确命中
        if exact:
            return await self._implant_detail(event, exact)
        matches = [x for x in self._implants if q in x["name"] or q in x["passive"]]
        if len(matches) == 1:
            return await self._implant_detail(event, matches[0])
        if not matches:
            return await self._msg_card(event, "🔍", "查无此植入体",
                                        desc=f"没有名字含「{q}」的植入体或词条。\n按编号查用 /帕鲁植入体查询 <编号>。", color="#F5A623")
        # 命中多个(如「鬼神」有永久/耗材两版) → 列表让用户按完整名精确查
        return await self._render_grid(event, f"含「{q}」的植入体", "🧬", _ent(matches), page, "/帕鲁植入体", q)

    async def _cmd_implant_num(self, event: AstrMessageEvent, args: list):
        """/帕鲁植入体查询 <编号>：按全局序号查第 N 个植入体(与分页解耦)。"""
        if not self._implants:
            return await self._msg_card(event, "🧬", "植入体数据未加载",
                                        desc="data/implants.json 缺失或损坏。", color="#E5484D")
        num = (args[0].strip() if args else "")
        if not num.isdigit():
            return await self._msg_card(event, "🔢", "请给出编号",
                                        desc="用法：/帕鲁植入体查询 1 (查第1个)。\n编号见 /帕鲁植入体 列表左上角。", color="#F5A623")
        idx = int(num)
        if not (1 <= idx <= len(self._implants)):
            return await self._msg_card(event, "🔢", "编号超出范围",
                                        desc=f"植入体共 {len(self._implants)} 种，没有第 {idx} 种。", color="#F5A623")
        return await self._implant_detail(event, self._implants[idx - 1])

    async def _cmd_worldtree(self, event: AstrMessageEvent, args: list):
        """/帕鲁世界树：1.0 世界树 boss 专题。守护者(暮尘蛾/夜蔓爵,可捕获)+ 最终剧情 boss 枯星龙(不可捕获)。
        对应主线 Main_DefeatWorldTreeMiddleBoss / Main_DefeatWorldTreeDragon(苏醒)。"""
        # (dev, 角色标签, 是否剧情最终boss)——按遭遇顺序:先守护者,后最终龙
        plan = [("mothman", "世界树守护者", False),
                ("flowerprince", "世界树守护者", False),
                ("worldtreedragon", "最终 Boss · 剧情", True)]
        bosses = []
        for d, role, final in plan:
            p = self._pal_by_dev.get(d)
            if not p:
                continue
            partner = (p.get("partner_skill_title") or "").strip()
            bosses.append({
                "name": p["pal_name"], "index": p.get("pal_index", ""),
                "role": role, "is_final": final,
                "story_only": bool(p.get("is_story_only")),
                "elements": p.get("elements", []), "rarity": p.get("rarity", 0),
                "partner": partner if partner not in ("", "-") else "",
                "skills": [s["name"] for s in p.get("active_skills", [])],
                "drops": [dd["item_name"] for dd in p.get("item_drops", [])],
                "hp": (p.get("stats", {}) or {}).get("hp", ""),
                "icon": self._pal_icon(p.get("pal_dev_name", ""))})
        if not bosses:
            return await self._msg_card(event, "🌳", "世界树数据未加载",
                                        desc="paldex.json 里缺少世界树 boss。", color="#E5484D")
        return await self._img(event, self._t("worldtree"), {"bosses": bosses})

    async def _cmd_v10(self, event: AstrMessageEvent, args: list):
        """/帕鲁1.0：插件对幻兽帕鲁 1.0 正式版的数据与功能支持总览。"""
        def _n(a):
            return len(getattr(self, a, []) or [])
        stats = {"pals": getattr(self, "_dex_collectible", _n("_pals")),
                 "pals_total": getattr(self, "_dex_total", _n("_pals")),
                 "items": _n("_items"), "skills": _n("_skills"),
                 "tech": _n("_tech"), "buildings": _n("_buildings"), "recipes": _n("_recipes"),
                 "lab": _n("_lab"), "fruits": _n("_skill_fruits"), "implants": _n("_implants")}
        return await self._img(event, self._t("v10"), {"stats": stats})

    # ------------------------------------------------------------------
    # 觉醒系统（/帕鲁觉醒）：1.0 帕鲁觉醒材料与机制百科（DT 未提供具体觉醒数值，只做材料/机制百科）
    # ------------------------------------------------------------------
    _AWAKE_ORDER = [("Fire", "火", "#e15b5b"), ("Water", "水", "#5b9ae1"), ("Grass", "草", "#5cc97a"),
                    ("Electric", "雷", "#e8c466"), ("Ice", "冰", "#7fd3e0"), ("Ground", "地", "#c08a5a"),
                    ("Dark", "暗", "#9b7bc0"), ("Dragon", "龙", "#7b8ce0"), ("Neutral", "无", "#b9a9d6")]

    def _awakening_data(self) -> dict:
        by_id = {x["item_id"]: x for x in (self._items or [])}
        gems = []
        for eid, cn, color in self._AWAKE_ORDER:
            stone = by_id.get(f"PalAwakening_{eid}", {})
            mat = (by_id.get(f"PalAwakening_Material_{eid}", {})
                   or by_id.get(f"PalAwakening_{eid}", {}))
            gems.append({"elem": cn, "color": color,
                         "gem": stone.get("name", f"{cn}之觉醒晶石"),
                         "gem_icon": self._item_icon(f"PalAwakening_{eid}"),
                         "mat": (mat.get("name", "") if "辉石" in str(mat.get("name", "")) else f"{cn}之辉石")})
        return {"gems": gems}

    async def _cmd_awakening(self, event: AstrMessageEvent, args: list):
        if not self._items:
            return await self._msg_card(event, "🌟", "数据未加载", desc="data/items.json 未就绪。", color="#E5484D")
        return await self._img(event, self._t("awakening"), self._awakening_data())

    # ------------------------------------------------------------------
    # 突变系统（/帕鲁突变）：1.0 突变机制 + 特殊蛋糕百科（概率游戏未公开，只标机制）
    # ------------------------------------------------------------------
    def _mutation_data(self) -> dict:
        by_id = {x["item_id"]: x for x in (self._items or [])}

        def clean(s):
            return (s or "").replace("\r\n", " ").replace("\n", " ").strip()
        cakes = []
        for cid in ("Cake", "Cake02", "Cake03", "Cake04", "Cake05"):
            x = by_id.get(cid)
            if x:
                cakes.append({"name": x.get("name", cid), "icon": self._item_icon(cid),
                              "effect": clean(x.get("description", ""))[:70]})
        eggs = []
        for eid in ("PalEgg_MutationPal_01", "PalEgg_MutationPal_03", "PalEgg_MutationPal_05"):
            x = by_id.get(eid)
            if x:
                eggs.append({"name": x.get("name", eid), "icon": self._item_icon(eid)})
        return {"cakes": cakes, "eggs": eggs}

    async def _cmd_mutation(self, event: AstrMessageEvent, args: list):
        if not self._items:
            return await self._msg_card(event, "🧬", "数据未加载", desc="data/items.json 未就绪。", color="#E5484D")
        return await self._img(event, self._t("mutation"), self._mutation_data())

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

    @filter.regex(r"^\s*/?帕鲁(?:\s|$|状态|在线|玩家|设置|统计|热力图|在线热力|热力|热度|heatmap|图鉴编号|编号查询|编号|palid|战力榜|战力排行|战力|最强帕鲁|power|闪光墙|闪光帕鲁|闪光|幸运帕鲁|shiny|lucky|头目墙|alpha墙|alpha|头目收集|排行|肝帝榜|榜|图鉴榜|图鉴排行|收集榜|图鉴收集|dexrank|资产榜|身价榜|财富榜|土豪榜|wealth|公会战力|工会战力|guildpower|更新公告|更新内容|更新日志|补丁说明|patchnotes|更新资讯|1\.0总览|1\.0导览|1\.0内容|1\.0|版本|v10|图鉴|反配种|反向配种|反向|反查|反配|怎么配出|怎么配|如何配|配种路线|配种链|breedroute|配种榜|配种排行榜|配种排行|能配榜|breedrank|我可以配工种|我能配工种|我配工种|我可以配|mybreedwork|配工种|配工作帕鲁|按工种配|工种配种|worksuitbreed|配出谁|能配出谁|能配谁|当亲代|作为亲代|正向配种|breedout|配种|继承|词条继承|继承计算|词条遗传|遗传|继承率|inherit|哪里掉|哪里爆|掉落|爆什么|掉什么|爆率|drop|竞技场|竞技|斗技场|arena|物品|道具|设施|建筑|科技|技术|研究所|研究|实验室|lab|材料路线|材料|配方展开|总材料|matroute|种属|分类图鉴|种族分类|genus|科技树|科技路线|解锁路线|techtree|牧场产出|牧场|放牧|家畜牧场|ranch|材料用途|用途|能做什么|matuse|属性克制|克制图|克制|属性|element|栖息区域|栖息地|栖息|分布|habitat|推荐词条|推荐|词条查|查词条|词条帕鲁|谁带词条|passfind|词条|passive|植入体|改造|implant|任务攻略|任务|主线任务|主线|支线任务|支线|quest|mission|塔主|高塔|tower|突袭boss|突袭|raid|世界树boss|世界树|最终boss|worldtree|养成|培养|养成进度|养成路线|growth|觉醒|帕鲁觉醒|觉醒系统|awakening|突变配种|突变系统|突变|特殊蛋糕|mutation|boss|BOSS|头目|首领|商人|商店|merchant|shop|哪里买|哪买|在哪买|哪里有卖|技能|主动技能|技能果实|skill|钓鱼|fishing|钓|工作适性|工作|适性|work|坐骑|骑乘|mount|对比|比较|compare|vs|料理|食物|做菜|cuisine|武器|weapon|帮助|菜单|绑定|我的战力|个人战力|我的最强帕鲁|我的帕鲁战力|mypower|小队进度|小队勾选|小队重置|小队|勾选|squad|我|档案|背包|物品栏|队伍|出战|帕鲁箱|箱子|箱|仓库|可孵化|可配种|可配|能配出|孵化|hatchable|查帕鲁|据点体检|基地体检|据点健康|基地健康|basehealth|据点|基地|据点帕鲁|基地帕鲁|工作帕鲁|basecamp|base|症状|伤病|治疗|怎么治|cure|symptom|公会榜|公会肝帝榜|公会帕鲁箱|公会帕鲁|公会终端|工会帕鲁|公会|工会|guild|订阅|退订|取消订阅|找人|查人|喊话|喊人|喊|审计|日志|自检|诊断|健康检查|自检诊断|体检|selfcheck|healthcheck|地图收集|地图地标|收集地图|地标|poimap|地图|map|公告|踢|封|解封|解绑|unbind|批准绑定|批准|approvebind|拒绝绑定|拒绝|rejectbind|重置存档|删档重开|删档|重开|重置世界|resetworld|reset|恢复存档|还原存档|恢复|还原|回档|回滚|rollback|备份列表|备份管理|备份|backups|backup|restore|重启服务器|重启服务|重启|restart|reboot|存档|关服|确认)")
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
            # 记录本群小队成员(已绑定的发指令者)——供 /帕鲁小队进度 按群隔离名单
            _sqq = str(event.get_sender_id() or "")
            if _sqq and _sqq in (self.state.get("bindings", {}) or {}):
                gm = self.state.setdefault("group_members", {}).setdefault(str(gid), {})
                if _sqq not in gm:
                    gm[_sqq] = int(time.time())
                    self._save_state()

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

    @staticmethod
    def _edit_dist(a: str, b: str) -> int:
        """Levenshtein 编辑距离(指令纠错用,字符串短、开销小)。"""
        if a == b:
            return 0
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[len(b)]

    def _suggest_commands(self, sub: str, n: int = 3) -> list:
        """给未知子命令找最接近的已知指令 canonical 列表(子串命中优先,再按归一化编辑距离)。"""
        sub = (sub or "").strip()
        if len(sub) < 1:
            return []
        scored = []
        for tok in COMMAND_TOKENS:
            if len(tok) < 2:               # 跳过单字别名(噪声大)
                continue
            if sub in tok or tok in sub:
                d = 0.2
            else:
                d = self._edit_dist(sub, tok) / max(len(sub), len(tok))
            scored.append((d, COMMAND_ALIAS_MAP[tok].canonical))
        scored.sort(key=lambda x: x[0])
        out = []
        for d, canon in scored:
            if d > 0.55:                   # 太不像就不猜
                break
            if canon not in out:
                out.append(canon)
            if len(out) >= n:
                break
        return out

    async def _unknown_card(self, event: AstrMessageEvent, sub: str):
        """未知子命令:先看是不是帕鲁/物品名(引导对应查询),再猜最接近指令;都没头绪才给帮助。只提示不代执行。"""
        sub = (sub or "").strip()
        blocks = []
        if sub:
            content = []
            if self._pals and self._find_pal(sub):
                content.append(f"/帕鲁图鉴 {_esc(sub)}")
            elif self._items and self._find_item(sub):
                content.append(f"/帕鲁物品 {_esc(sub)}")
            if content:
                blocks.append("查这个内容:\n" + "\n".join("· " + c for c in content))
        cmds = self._suggest_commands(sub)
        if cmds:
            blocks.append("你是不是想找:\n" + "\n".join(f"· /帕鲁{c}" for c in cmds))
        if not blocks:
            return await self._cmd_help(event)   # 完全没头绪 → 全量帮助
        return await self._msg_card(
            event, "🤔", f"没有「{_esc(sub)}」这条指令",
            desc="\n\n".join(blocks) + "\n\n看全部指令发「/帕鲁帮助」。",
            head="🔍 你可能想找", color="#7ab8ff")

    async def _dispatch(self, event: AstrMessageEvent, sub: str, args: list[str]):
        # 注册表驱动分发（commands/router.py 的 CommandSpec）。行为与旧 if 链严格一致：
        # 未知→帮助；先管理员鉴权(必要时写警告日志)，再冷却门，最后按 pass_args/extra 调 handler。
        sender = str(event.get_sender_id())
        spec = COMMAND_ALIAS_MAP.get(sub)
        if spec is None:
            yield await self._unknown_card(event, sub)
            return
        if spec.admin and not self._is_admin(sender):
            if spec.log_denied:
                logger.warning(f"{LOG_PREFIX} 非白名单用户 {sender} 尝试执行「{spec.canonical}」")
            yield await self._no_perm_card(event)
            return
        if spec.cooldown and not self._pass_cooldown(event, spec.canonical):
            return
        handler = getattr(self, spec.handler)
        if spec.pass_args:
            yield await handler(event, args, *spec.extra)
        else:
            yield await handler(event, *spec.extra)

    # ------------------------------------------------------------------
    # 冷却
    # ------------------------------------------------------------------
    def _pass_cooldown(self, event: AstrMessageEvent, sub: str = "") -> bool:
        """查询冷却:**按(用户, 指令)分别计时**——同一用户重复发**同一条**指令 < query_cooldown 秒才拦截;
        **不同指令互不冷却**,可同时发多条并各自出图(如 /帕鲁主线 + /帕鲁商人 一起发都会处理)。
        query_cooldown<=0 关闭(私人小群可关);管理/绑定等 cooldown=False 的指令不经过这里。
        目的:只挡"同一个人狂刷同一张图",不挡正常并发不同查询。"""
        cd = self._effective_cooldown()
        if cd <= 0:
            return True
        key = f"{event.get_sender_id() or ''}:{sub}"
        now = time.time()
        if now - self._cooldown_map.get(key, 0.0) < cd:
            return False
        self._cooldown_map[key] = now
        if len(self._cooldown_map) > 500:   # 防内存无界增长,清理过期项
            self._cooldown_map = {k: v for k, v in self._cooldown_map.items() if now - v < cd}
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
        # 布尔开关：字段缺失时不显示，绝不把"API 未返回"误判成"关闭"
        for label, key in SETTINGS_BOOL:
            if key in s and s[key] is not None:
                items.append({"k": label, "v": "开启" if s[key] else "关闭"})
        # 服务端版本/Build(来自 /v1/api/info)
        server_version = ""
        ok_i, info, _ = await self._api_get("/v1/api/info")
        if ok_i and isinstance(info, dict):
            server_version = str(info.get("version") or "")
        if not items and not server_version:
            return await self._msg_card(
                event, "⚙️", "暂无可显示的设置",
                desc="服务器未返回可识别的设置字段。", head="⚙️ 服务器设置")
        return await self._img(event, self._t("settings"),
                               {"items": items, "server_version": server_version})

    async def _cmd_stats(self, event: AstrMessageEvent):
        return await self._img(event, self._t("stats"), self._stats_data())

    @staticmethod
    def _combat_stats(bhp: int, batk: int, bdef: int, level: int,
                      iv_hp: int = 0, iv_atk: int = 0, iv_def: int = 0, rank: int = 1,
                      alpha: bool = False, bonus_hp: float = 0.0,
                      bonus_atk: float = 0.0, bonus_def: float = 0.0):
        """按游戏公式算当前属性(HP/攻击/防御)。经存档 + 游戏面板实测验证(炽焰牛/云海鹿精确命中)：
          头目(Alpha)帕鲁 HP 种族值 ×1.2(DT 的 BOSS_ 条目确认)；
          HP  = (500 + 5×Lv + 种族HP  × 0.5   × Lv × (1 + 0.3×天赋HP/100)) × (1+被动HP%)
          攻击 = (100        + 种族攻击 × 0.075 × Lv × (1 + 0.3×天赋攻/100)) × (1+被动攻%)
          防御 = (50         + 种族防御 × 0.075 × Lv × (1 + 0.3×天赋防/100)) × (1+被动防%)
        被动如 Rare 攻/防 +15%、Deffence +20%；浓缩(Rank)每级约 +5%。"""
        if alpha:
            bhp = round(bhp * 1.2)
        hp = int((500 + 5 * level + bhp * 0.5 * level * (1 + 0.3 * iv_hp / 100)) * (1 + bonus_hp / 100))
        atk = int((100 + 0.075 * batk * level * (1 + 0.3 * iv_atk / 100)) * (1 + bonus_atk / 100))
        dfn = int((50 + 0.075 * bdef * level * (1 + 0.3 * iv_def / 100)) * (1 + bonus_def / 100))
        if rank > 1:
            m = 1 + (rank - 1) * 0.05
            hp, atk, dfn = int(hp * m), int(atk * m), int(dfn * m)
        return hp, atk, dfn

    def _passive_bonus(self, passives) -> dict:
        """一组被动技能的基础属性加成合计 {hp%, atk%, def%}(存档 id 带 rank 后缀时去尾匹配)。"""
        tot = {"hp": 0.0, "atk": 0.0, "def": 0.0}
        ps = self._passive_stat or {}
        for pid in (passives or []):
            b = ps.get(pid) or ps.get(re.sub(r"_\d+$", "", str(pid))) or {}
            for k in tot:
                tot[k] += b.get(k, 0.0)
        return tot

    def _pal_power(self, brief: dict) -> int:
        """玩家帕鲁综合战力：游戏公式算真实 HP/攻/防(头目HP×1.2 + 等级+天赋+浓缩 + 被动加成)。"""
        p = self._resolve_owned_pal(str(brief.get("char_id", "")))   # 容错 BOSS_/元素变种前后缀
        st = (p or {}).get("stats") or {}
        bhp = int(st.get("hp", 0) or 0) or 100
        batk = max(int(st.get("melee_attack", 0) or 0), int(st.get("shot_attack", 0) or 0)) or 100
        bdef = int(st.get("defense", 0) or 0) or 50
        pb = self._passive_bonus(brief.get("passives", []))
        hp, atk, dfn = self._combat_stats(
            bhp, batk, bdef, int(brief.get("level", 1) or 1),
            int(brief.get("iv_hp", 0) or 0), int(brief.get("iv_atk", 0) or 0),
            int(brief.get("iv_def", 0) or 0), int(brief.get("rank", 1) or 1),
            bool(brief.get("is_alpha")), pb["hp"], pb["atk"], pb["def"])
        hp = max(int(brief.get("hp", 0) or 0), hp)   # 生命值优先用存档真实值(满血含灵魂/状态点)
        return int(hp * 0.5 + atk + dfn)

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
            cid = str(pal.get("char_id", ""))
            p = self._resolve_owned_pal(cid)
            hname = None if p else self._human_name(cid)   # 抓到的人类给中文名
            name = pal.get("nickname") or (p or {}).get("pal_name") or hname or cid or "?"
            rows.append({
                "rank": i, "name": _esc(name), "owner": _esc(owner),
                "level": pal.get("level", 1), "power": pw, "pct": int(pw / mxp * 100),
                "icon": self._pal_icon((p or {}).get("pal_dev_name", "")) or (self._human_icon(cid) if hname else ""),
                "is_human": bool(hname),
                "lucky": bool(pal.get("lucky")), "alpha": bool(pal.get("is_alpha")),
                "medal": ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)})
        return await self._img(event, self._t("power"),
                               {"rows": rows, "sub": f"全服最强帕鲁 Top{len(rows)} · 共 {len(allpals)} 只"})

    async def _cmd_my_power(self, event: AstrMessageEvent, args: list[str]):
        """个人帕鲁战力排行:自己(管理员可查他人)所有捕捉帕鲁按综合战力排序,分页。
        末位数字=页码;非数字(管理员)=目标玩家名。不含公会共享据点帕鲁。"""
        a = list(args)
        page = 1
        if a and a[-1].isdigit():
            page = max(1, int(a[-1])); a = a[:-1]
        sp, name, err = await self._resolve_target_sp(event, a)   # 复用:自己/管理员查他人 + 隐私门控
        if err:
            return err
        pals = [(self._pal_power(p), p) for p, _ in self._iter_prof_pals(sp, set(), include_shared=False)]
        if not pals:
            return await self._msg_card(event, "📦", "还没有可统计的帕鲁",
                                        desc=f"「{_esc(name)}」的队伍/帕鲁箱里还没有帕鲁。", color="#9a8a91")
        pals.sort(key=lambda x: -x[0])
        total, mxp = len(pals), (pals[0][0] or 1)
        size = 15
        pages = max(1, (total + size - 1) // size)
        page = min(page, pages)
        rows = []
        for i, (pw, pal) in enumerate(pals[(page - 1) * size: page * size], (page - 1) * size + 1):
            cid = str(pal.get("char_id", ""))
            p = self._resolve_owned_pal(cid)
            hname = None if p else self._human_name(cid)
            pnm = pal.get("nickname") or (p or {}).get("pal_name") or hname or cid or "?"
            els = (p or {}).get("elements") or []
            rows.append({
                "rank": i, "name": _esc(pnm), "owner": "", "is_human": bool(hname),
                "element": "".join(e.replace("属性", "") for e in els[:2]),
                "level": pal.get("level", 1), "power": pw, "pct": int(pw / mxp * 100),
                "icon": self._pal_icon((p or {}).get("pal_dev_name", "")) or (self._human_icon(cid) if hname else ""),
                "lucky": bool(pal.get("lucky")), "alpha": bool(pal.get("is_alpha")),
                "medal": ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)})
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            tgt = " ".join(a)
            pager = f"发「/帕鲁我的战力{(' ' + tgt) if tgt else ''} {nxt}」翻到第 {nxt}/{pages} 页"
        return await self._img(event, self._t("power"),
                               {"title": f"🏆 {name} 的战力榜", "rows": rows, "pager": pager,
                                "sub": f"共 {total} 只捕捉帕鲁 · 第 {page}/{pages} 页 · 按综合战力排序"})

    # ------------------------------------------------------------------
    # 首选3：养成(/帕鲁养成 <帕鲁名>)——基于玩家实际拥有的该帕鲁,展示浓缩/帕鲁之魂/觉醒/个体值/词条/技能
    #        现状与目标差距。全部存档只读;浓缩/魂精确材料数游戏未提取则不虚报。
    # ------------------------------------------------------------------
    def _growth_data(self, pal: dict, p: dict, count: int) -> dict:
        rank = int(pal.get("rank", 1) or 1)          # 存档 Rank 1~5
        stars = max(0, min(4, rank - 1))             # 0~4★
        souls = pal.get("souls") or {}
        awakened = bool(pal.get("awakened"))
        els = p.get("elements") or []
        elem_cn = els[0].replace("属性", "").strip() if els else ""
        gem = ""
        if not awakened and elem_cn:
            gm = next((g for g in (self._awakening_data().get("gems") or []) if g.get("elem") == elem_cn), None)
            gem = gm["gem"] if gm else f"{elem_cn}之觉醒晶石"
        passv = [(self._passives.get(pid, {}) or {}).get("name") or pid for pid in pal.get("passives", [])]
        waza = [self._wazas.get(w, w) for w in pal.get("equip_waza", [])]
        notes = []
        notes.append("浓缩已满 4★。" if stars >= 4
                     else "浓缩：用同种帕鲁在浓缩台提升,满 4★;精确所需数量游戏未从 DataTable 提取,故不虚报。")
        if souls:
            notes.append("帕鲁之魂：数值取自你存档实测;用「帕鲁之魂(小/中/大)」道具在魂坛继续强化。")
        if els:
            notes.append("已觉醒。" if awakened else f"未觉醒：需「{gem}」等 9 系晶石觉醒(机制见 /帕鲁觉醒)。")
        notes.append("个体值(天赋)捕捉时固定,不可后天更改。")
        return {
            "name": p["pal_name"], "icon": self._pal_icon(p.get("pal_dev_name", "")),
            "elements": els, "level": pal.get("level", 1), "nickname": _esc(pal.get("nickname") or ""),
            "count": count, "lucky": bool(pal.get("lucky")), "alpha": bool(pal.get("is_alpha")),
            "condense": stars, "condense_max": 4,
            "souls": [{"k": k, "lv": v} for k, v in souls.items() if v],
            "awakened": awakened, "gem": _esc(gem), "element_cn": elem_cn,
            "iv_hp": pal.get("iv_hp", 0), "iv_atk": pal.get("iv_atk", 0), "iv_def": pal.get("iv_def", 0),
            "passives": [_esc(x) for x in passv], "wazas": [_esc(x) for x in waza],
            "notes": [n for n in notes if n],
            "source": "现状全部来自你的存档(只读,不改档);浓缩/魂精确材料数游戏未公开则不虚报",
        }

    async def _cmd_growth(self, event: AstrMessageEvent, args: list[str]):
        if not self._pals:
            return await self._msg_card(event, "🧬", "图鉴数据未加载", desc="data/paldex.json 缺失。", color="#E5484D")
        a = list(args)
        idx = 0
        if len(a) > 1 and a[-1].isdigit():   # 名字后带序号:选具体某只(同种多只时)
            idx = int(a[-1]); a = a[:-1]
        q = " ".join(a).strip()
        if not q:
            return await self._msg_card(event, "✏️", "查你某只帕鲁的养成",
                                        desc="用法：/帕鲁养成 <帕鲁名> [序号]\n会读你存档里这只帕鲁的浓缩/帕鲁之魂/觉醒/个体值/词条/技能现状；同种有多只时会列出让你选序号。",
                                        head="🧬 养成", color="#7ab8ff")
        p = self._find_pal(q)
        if not p:
            sug = self._suggest_pals(q)
            return await self._msg_card(event, "🔍", "查无此帕鲁",
                                        desc=f"没找到「{_esc(q)}」。" + ("\n是不是：" + "、".join(sug) if sug else ""), color="#F5A623")
        sp, name, err = await self._resolve_target_sp(event, [])   # 自己的存档档案(隐私门控)
        if err:
            return err
        dev = str(p.get("pal_dev_name", "")).lower()
        mine = [pal for pal, _ in self._iter_prof_pals(sp, set(), include_shared=False)
                if str((self._resolve_owned_pal(str(pal.get("char_id", ""))) or {})
                       .get("pal_dev_name", "")).lower() == dev]   # 容错 BOSS_/元素变种,头目也算本种
        if not mine:
            return await self._msg_card(event, "📦", f"你还没有「{_esc(p['pal_name'])}」",
                                        desc="养成卡只统计你自己捕捉的这只帕鲁。先去抓一只,再来看养成进度~", color="#9a8a91")
        # 稳定排序(浓缩>等级>iid)——保证序号跨查询一致,best 在前
        mine.sort(key=lambda x: (-int(x.get("rank", 1) or 1), -int(x.get("level", 1) or 1), str(x.get("iid", ""))))
        # 只有一只 或 指定了有效序号 -> 直接出养成卡
        if len(mine) == 1 or 1 <= idx <= len(mine):
            chosen = mine[idx - 1] if idx else mine[0]
            d = self._growth_data(chosen, p, len(mine))
            d["pick"] = idx or 1
            return await self._img(event, self._t("growth"), d)
        # 同种多只、未指定序号 -> 列出让用户选(每只带昵称/等级/浓缩/个体值区分)
        lines = []
        for i, pal in enumerate(mine, 1):
            stars = "★" * max(0, int(pal.get("rank", 1) or 1) - 1) or "0★"
            nick = pal.get("nickname") or "(无昵称)"
            badge = ("✨" if pal.get("lucky") else "") + ("👑" if pal.get("is_alpha") else "")
            lines.append(f"{i}. {badge}「{_esc(nick)}」Lv{pal.get('level', 1)} · 浓缩{stars} · "
                         f"个体{pal.get('iv_hp', 0)}/{pal.get('iv_atk', 0)}/{pal.get('iv_def', 0)}")
        return await self._msg_card(
            event, "🧬", f"你有 {len(mine)} 只「{_esc(p['pal_name'])}」",
            desc="\n".join(lines) + f"\n\n发「/帕鲁养成 {_esc(p['pal_name'])} <序号>」看具体某只的养成。",
            head="🧬 选一只看养成", color="#7ab8ff")

    # ------------------------------------------------------------------
    # 材料路线(/帕鲁材料路线 <物品> [数量]):把可制作物品的配方递归展开到底,
    # 给几人小服算清"总共要采集哪些原料 + 要预制哪些中间产物 + 用到哪些制作台"。
    # 数据来自客户端 pak 配方表(data/recipes.json),不猜测;采集/掉落原料为递归叶子。
    # ------------------------------------------------------------------
    def _recipe_for(self, name: str) -> dict:
        meta = self._item_by_name.get(name)
        return (self._recipes or {}).get(meta.get("item_id")) if meta else None

    def _matroute_expand(self, name, qty, path, base, inter, benches, depth):
        meta = self._item_by_name.get(name)
        iid = meta.get("item_id") if meta else None
        rec = (self._recipes or {}).get(iid) if iid else None
        if not rec or not rec.get("mats") or depth > 8 or (iid and iid in path):
            base[name] = base.get(name, 0) + qty      # 采集/掉落原料 = 递归叶子
            return
        inter[name] = inter.get(name, 0) + qty        # 可制作中间产物
        for b in rec.get("bench", []):
            if b not in benches:
                benches.append(b)
        for m in rec["mats"]:
            self._matroute_expand(m.get("name"), int(m.get("count", 0) or 0) * qty,
                                  path | {iid}, base, inter, benches, depth + 1)

    def _matroute_data(self, it: dict, mult: int) -> dict | None:
        iid = it.get("item_id")
        rec = (self._recipes or {}).get(iid) or {}
        if not rec.get("mats"):
            return None                               # 该物品不可制作(采集/掉落获得)
        base, inter, benches = {}, {}, []
        for b in rec.get("bench", []):
            if b not in benches:
                benches.append(b)
        direct = []
        for m in rec["mats"]:
            nm = m.get("name")
            cnt = int(m.get("count", 0) or 0) * mult
            meta = self._item_by_name.get(nm)
            craft = bool(meta and ((self._recipes or {}).get(meta.get("item_id")) or {}).get("mats"))
            direct.append({"name": nm, "count": cnt, "craftable": craft,
                           "icon": self._item_icon(meta.get("item_id")) if meta else ""})
            self._matroute_expand(nm, cnt, {iid}, base, inter, benches, 1)

        def _rows(d):
            out = []
            for nm, c in sorted(d.items(), key=lambda kv: (-kv[1], kv[0])):
                meta = self._item_by_name.get(nm)
                out.append({"name": nm, "count": c,
                            "icon": self._item_icon(meta.get("item_id")) if meta else ""})
            return out

        return {"name": it["name"], "mult": mult, "icon": self._item_icon(iid),
                "direct": direct, "benches": benches,
                "inter": _rows(inter), "base": _rows(base),
                "source": "配方来自客户端 pak 配方表,递归展开到底;采集/掉落类原料为叶子,不再拆分"}

    async def _cmd_matroute(self, event: AstrMessageEvent, args: list[str]):
        if not self._recipes:
            return await self._msg_card(event, "🧾", "配方数据未加载", desc="data/recipes.json 缺失或损坏。", color="#E5484D")
        a = list(args)
        mult = 1
        if len(a) > 1 and a[-1].isdigit():            # 名字后带数量:算 N 份
            mult = max(1, min(999, int(a[-1])))
            a = a[:-1]
        q = " ".join(a).strip()
        if not q:
            return await self._msg_card(event, "✏️", "算某物品的总材料",
                                        desc="用法：/帕鲁材料路线 <物品名> [数量]\n把配方递归展开到底,算清总共要采多少原料、预制哪些中间产物、用哪些制作台。\n例：/帕鲁材料路线 火箭发射器",
                                        head="🧾 材料路线", color="#7ab8ff")
        it = self._find_item(q)
        if not it:
            return await self._msg_card(event, "🔍", "查无此物品",
                                        desc=f"没找到「{_esc(q)}」。\n可发「/帕鲁物品」看分类菜单。", color="#F5A623")
        d = self._matroute_data(it, mult)
        if not d:
            return await self._msg_card(event, "🧾", f"「{_esc(it['name'])}」无法制作",
                                        desc="该物品没有制作配方(多为采集/掉落/商人购买获得),没有材料路线可展开。", color="#9a8a91")
        return await self._img(event, self._t("matroute"), d)

    # 材料用途反查(/帕鲁用途 <材料> [页]):材料路线的逆——"这材料能做什么"。
    # 反向索引 recipes + building_recipes:同名不同品阶去重,保留最小需求量,分页。
    def _matuse_index(self) -> dict:
        if getattr(self, "_mu_index", None) is None:
            bname = {b.get("id"): b.get("name") for b in (self._buildings or [])}
            idx: dict = {}
            for iid, r in (self._recipes or {}).items():
                pname = (self._item_by_id.get(iid) or {}).get("name") or iid
                for m in r.get("mats", []):
                    idx.setdefault(m.get("name"), []).append(
                        {"name": pname, "count": int(m.get("count", 0) or 0), "kind": "物品",
                         "icon": self._item_icon(iid)})
            for bid, r in (self._build_recipes or {}).items():
                pname = bname.get(bid) or bid
                for m in r.get("mats", []):
                    idx.setdefault(m.get("name"), []).append(
                        {"name": pname, "count": int(m.get("count", 0) or 0), "kind": "建筑",
                         "icon": self._sub_icon("buildings", bid)})
            self._mu_index = idx
        return self._mu_index

    _MATUSE_PAGE = 24

    async def _cmd_matuse(self, event: AstrMessageEvent, args: list[str]):
        if not self._recipes:
            return await self._msg_card(event, "🧾", "配方数据未加载", desc="data/recipes.json 缺失或损坏。", color="#E5484D")
        a = list(args)
        page = int(a[-1]) if len(a) > 1 and a[-1].isdigit() else 1
        if len(a) > 1 and a[-1].isdigit():
            a = a[:-1]
        q = " ".join(a).strip()
        if not q:
            return await self._msg_card(event, "✏️", "查某材料能做什么",
                                        desc="用法：/帕鲁用途 <材料名> [页]\n反查这个材料是哪些物品/建筑的配方原料(材料路线的反向)。\n例：/帕鲁用途 石炭",
                                        head="🧾 材料用途", color="#7ab8ff")
        it = self._find_item(q)
        name = it["name"] if it else q                # 用规范名匹配索引
        uses = self._matuse_index().get(name)
        if not uses:
            return await self._msg_card(event, "🧾", f"「{_esc(name)}」暂无已知用途",
                                        desc="没查到用它当原料的配方(可能是最终产物/仅出售/仅料理食材)。", color="#9a8a91")
        seen, rows = {}, []                           # 同名不同品阶去重:留最小需求量
        for u in sorted(uses, key=lambda x: (x["kind"] != "物品", x["name"])):
            key = (u["name"], u["kind"])
            if key in seen:
                if u["count"] < seen[key]["count"]:
                    seen[key]["count"] = u["count"]
                continue
            row = dict(u)
            seen[key] = row
            rows.append(row)
        total = len(rows)
        pages = max(1, (total + self._MATUSE_PAGE - 1) // self._MATUSE_PAGE)
        page = min(max(1, page), pages)
        chunk = rows[(page - 1) * self._MATUSE_PAGE: page * self._MATUSE_PAGE]
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁用途 {_esc(name)} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("matuse"), {
            "name": _esc(name), "icon": self._item_icon(it.get("item_id")) if it else "",
            "rows": chunk, "total": total, "page": page, "pages": pages, "pager": pager})

    # ------------------------------------------------------------------
    # 帕鲁战力等级排行（/帕鲁战力榜）：基于图鉴种族值的战力，全帕鲁排名，翻页+详细
    # ------------------------------------------------------------------
    _POWER_REF_LV = 50   # 帕鲁战力榜基准等级(满级战力，无天赋/浓缩)

    def _species_power(self, p: dict) -> int:
        """帕鲁战力等级：以满级 Lv50、无天赋/浓缩为基准，用游戏公式算 HP/攻/防综合(仅横向对比)。"""
        st = p.get("stats") or {}
        batk = max(int(st.get("melee_attack", 0) or 0), int(st.get("shot_attack", 0) or 0))
        hp, atk, dfn = self._combat_stats(int(st.get("hp", 0) or 0), batk,
                                          int(st.get("defense", 0) or 0), self._POWER_REF_LV)
        return round(hp * 0.5 + atk + dfn)

    def _power_ranked(self) -> list:
        """全图鉴按种族战力降序缓存 [(power, pal), ...]。"""
        if getattr(self, "_pp_ranked", None) is None:
            lst = [(self._species_power(p), p) for p in self._pals if (p.get("stats") or {}).get("hp")]
            lst.sort(key=lambda x: (-x[0], x[1].get("pal_name", "")))
            self._pp_ranked = lst
        return self._pp_ranked

    async def _cmd_paldex_power(self, event: AstrMessageEvent, args: list):
        if not self._pals:
            return await self._msg_card(event, "🏆", "图鉴数据未加载",
                                        desc="data/paldex.json 缺失或损坏。", color="#E5484D")
        ranked = self._power_ranked()
        query, page = self._parse_page_args(args)
        # 详细查询：/帕鲁战力榜 <帕鲁名或编号>
        if query:
            p = self._find_pal(query)
            if not p:
                return await self._msg_card(event, "🔍", "查无此帕鲁",
                                            desc=f"没有名字/编号含「{query}」的帕鲁。", color="#F5A623")
            pw = self._species_power(p)
            rank = next((i for i, (_, pp) in enumerate(ranked, 1) if pp is p), "?")
            st = p.get("stats") or {}
            bhp = int(st.get("hp", 0) or 0)
            bme = int(st.get("melee_attack", 0) or 0)
            bsh = int(st.get("shot_attack", 0) or 0)
            bdf = int(st.get("defense", 0) or 0)
            hp50, atk50, def50 = self._combat_stats(bhp, max(bme, bsh), bdf, self._POWER_REF_LV)
            mx = max(hp50, atk50, def50, 1)
            data = {
                "name": _esc(p.get("pal_name", "?")), "icon": self._pal_icon(p.get("pal_dev_name", "")),
                "elements": p.get("elements", []), "rarity": int(p.get("rarity", 0) or 0),
                "power": pw, "rank": rank, "total": len(ranked), "reflv": self._POWER_REF_LV,
                "partner": _esc(p.get("partner_skill_title", "") or ""),
                "base": {"hp": bhp, "melee": bme, "shot": bsh, "df": bdf},
                "stats": [
                    {"k": "生命 HP", "v": hp50, "pct": int(hp50 / mx * 100)},
                    {"k": "攻击", "v": atk50, "pct": int(atk50 / mx * 100)},
                    {"k": "防御", "v": def50, "pct": int(def50 / mx * 100)},
                ]}
            return await self._img(event, self._t("palpowerdetail"), data)
        # 排行翻页：每页 14
        per = 14
        total_pages = max(1, (len(ranked) + per - 1) // per)
        page = max(1, min(page, total_pages))
        mxp = ranked[0][0] if ranked else 1
        chunk = ranked[(page - 1) * per: page * per]
        rows = []
        for off, (pw, p) in enumerate(chunk):
            i = (page - 1) * per + off + 1
            els = p.get("elements", []) or []
            rows.append({
                "rank": i, "name": _esc(p.get("pal_name", "?")),
                "icon": self._pal_icon(p.get("pal_dev_name", "")),
                "element": (els[0].replace("属性", "") if els else "—"),
                "rarity": int(p.get("rarity", 0) or 0),
                "boss": ("tower" if p.get("is_tower_boss") else ("boss" if p.get("is_boss") else "")),
                "power": pw, "pct": int(pw / (mxp or 1) * 100),
                "medal": ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)})
        sub = f"已知帕鲁战力排行 · 第 {page}/{total_pages} 页 · 共 {len(ranked)} 只"
        return await self._img(event, self._t("palpower"),
                               {"rows": rows, "sub": sub, "page": page, "total_pages": total_pages})

    async def _collection_wall(self, event, field, title, badge, label, empty, badge_kind=""):
        """收藏墙通用：遍历全服帕鲁筛 field(lucky/is_alpha) 为真的，网格展示。
        badge_kind: 语义键(lucky/alpha),模板据此取三主题共享的游戏图标,缺失回退 badge Emoji。"""
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
                    cid = str(pal.get("char_id", ""))
                    p = self._resolve_owned_pal(cid)            # 容错 BOSS_/元素变种前后缀
                    hname = None if p else self._human_name(cid)   # 抓到的人类/头目给中文名
                    name = pal.get("nickname") or (p or {}).get("pal_name") or hname or cid or "?"
                    items.append({"name": _esc(name), "owner": _esc(owner), "badge": badge,
                                  "is_human": bool(hname),
                                  "icon": self._pal_icon((p or {}).get("pal_dev_name", ""))
                                          or (self._human_icon(cid) if hname else "")})
                    owner_cnt[owner] = owner_cnt.get(owner, 0) + 1
        if not items:
            return await self._msg_card(event, badge, f"全服还没有{label}帕鲁",
                                        desc=empty, color="#9a8a91")
        items.sort(key=lambda x: x["owner"])     # 同主人聚一起
        owners = sorted(owner_cnt.items(), key=lambda x: -x[1])
        top = " ".join(f"{_esc(o)}×{c}" for o, c in owners[:3])
        return await self._img(event, self._t("shiny"), {
            "title": title, "badge": badge, "badge_kind": badge_kind, "rows": items[:30],
            "sub": f"共 {len(items)} 只{label} · {len(owner_cnt)} 位训练师", "top_owners": top})

    async def _cmd_shiny(self, event: AstrMessageEvent):
        return await self._collection_wall(
            event, "lucky", "✨ 全服闪光墙", "✨", "闪光",
            "闪光(幸运)帕鲁非常稀有～多抓多孵，第一只闪光说不定就是你的！", badge_kind="lucky")

    async def _cmd_alpha(self, event: AstrMessageEvent):
        return await self._collection_wall(
            event, "is_alpha", "👑 全服头目墙", "👑", "头目",
            "头目(Alpha)是地图上的强力 BOSS 帕鲁，捕获它们填满这面墙吧！", badge_kind="alpha")

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

    # 肝帝榜口径关键词 -> scope(本周为默认)
    _RANK_SCOPES = {
        "今日": "today", "日榜": "today", "今天": "today", "today": "today", "day": "today",
        "总": "total", "总榜": "total", "累计": "total", "累积": "total", "历史": "total",
        "总排行": "total", "total": "total", "all": "total",
        "本周": "week", "周榜": "week", "本周榜": "week", "week": "week",
    }

    def _rank_scope(self, args: list[str]):
        """解析排行口径。返回 (scope, rank_title, rank_sub);week 用模板默认标题(返回 None)。"""
        key = args[0].strip().lower() if args else ""   # 中文不受 lower 影响,英文归一化
        scope = self._RANK_SCOPES.get(key, "week")
        if scope == "today":
            return "today", "🏆 今日肝帝榜", "今日在线时长排行 · 看今天谁最肝～"
        if scope == "total":
            start = self.state.get("tracking_started_at")
            since = f"自 {start} 起" if start else "自插件开始统计起（起点未记录）"
            return "total", "🏆 累计肝帝榜", f"{since}累计在线时长排行 · 历史总肝王～"
        return "week", None, None   # None -> 模板默认(本周)

    async def _cmd_rank(self, event: AstrMessageEvent, args: list[str]):
        scope, title, sub = self._rank_scope(args)
        raw = self._rank_list(10, scope)
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
        data = {"rows": rows, "note": "按玩家本周(周一0点起)累计在线时长排序;时长由机器人定时轮询在线状态累加,离线不计。"}
        if title:   # week 用模板默认标题
            data["rank_title"], data["rank_sub"] = title, sub
        return await self._img(event, self._t("rank"), data)

    async def _cmd_dex_rank(self, event: AstrMessageEvent):
        """图鉴收集榜：全服玩家按拥有的不同帕鲁种类数排行(复用 rank 模板)。"""
        self._last_save_use = time.time()
        profiles = await self._fetch_save_profiles()
        if not profiles:
            return await self._msg_card(
                event, "🛰️", "暂时读不到存档",
                desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        total = getattr(self, "_dex_collectible", 0) or len(self._pals) or 1   # 收集度以官方可收集287为满
        board = []
        seen_shared = set()
        for prof in profiles.values():
            species = set()
            for pal, owner in self._iter_prof_pals(prof, seen_shared, include_shared=False):
                p = self._resolve_owned_pal(str(pal.get("char_id", "")))   # 容错 BOSS_/元素变种前后缀
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
            "rank_sub": f"全服图鉴收集进度 · 共 {total} 种 · {len(board)} 位训练师",
            "note": f"按玩家拥有的不同帕鲁种类数排序(队伍+帕鲁箱去重,不含公会共享据点);满值={total}(官方可收集数)。"})

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
                p = self._resolve_owned_pal(str(pal.get("char_id", "")))   # 容错 BOSS_/元素变种前后缀
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
            "rank_sub": f"全服帕鲁总身价排行(金币) · {len(board)} 位训练师",
            "note": "把玩家所有帕鲁的图鉴售价(卖给商人的金币)累加;个体值/浓缩/词条不计入,仅按种族基础售价。"})

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
            "rank_sub": f"各公会成员帕鲁战力总和 · {len(board)} 个公会",
            "note": "各公会全体成员帕鲁的综合战力(等级/种族/天赋/浓缩/被动)求和;共享据点帕鲁全局去重,只计一次。"})

    # 帮助卡分区(类别 -> 中文标题),数据驱动:直接读命令注册表,永远与实际指令同步。
    _HELP_CATS = (("server", "🖥️ 服务器"), ("rank", "🏆 排行榜"),
                  ("paldex", "📚 图鉴 / 攻略查询"), ("player", "🧑 玩家自助(建议先绑定)"),
                  ("guild", "👥 公会"), ("admin", "🔧 管理(仅 admin_qq)"))

    def _help_sections(self, query: str = "") -> list:
        """按类别分区的指令清单;query 非空则只留名字/别名/说明含关键词的(搜索)。"""
        q = (query or "").strip()
        secs = []
        for cat, title in self._HELP_CATS:
            cmds = []
            for s in COMMAND_SPECS:
                if s.category != cat or s.canonical == "帮助":
                    continue
                if q:
                    hay = s.canonical + " " + " ".join(s.aliases) + " " + (s.description or "")
                    if q.lower() not in hay.lower():
                        continue
                cmds.append({"cmd": "/帕鲁" + s.canonical, "desc": s.description or ""})
            if cmds:
                secs.append({"title": title, "cmds": cmds})
        return secs

    async def _cmd_help(self, event: AstrMessageEvent, args: list[str] | None = None):
        q = " ".join(args or []).strip()
        secs = self._help_sections(q)
        if q and not secs:
            cmds = self._suggest_commands(q)
            return await self._msg_card(
                event, "🔍", f"没搜到含「{_esc(q)}」的指令",
                desc=("你是不是想找:\n" + "\n".join(f"· /帕鲁{c}" for c in cmds) if cmds else "")
                + "\n\n发不带关键词的「/帕鲁帮助」看全部指令。", color="#F5A623")
        data = {"sections": secs}
        if q:
            n = sum(len(s["cmds"]) for s in secs)
            data["help_title"] = f"🔍 含「{_esc(q)}」的指令 · {n} 条"
            data["help_sub"] = "发不带关键词的「/帕鲁帮助」看全部"
        return await self._img(event, self._t("help"), data)

    # ------------------------------------------------------------------
    # 首选1：小队进度(/帕鲁小队进度)——按群聚合已绑定成员的探索/收集/塔主等进度(存档只读自动同步)
    #        + 群级手动勾选目标(读不到的探索节点由群成员自己记，不伪造自动完成)
    # ------------------------------------------------------------------
    @staticmethod
    def _norm_uid(u) -> str:
        return str(u or "").replace("-", "").upper()

    def _squad_roster_qq(self, gid: str) -> list:
        """本群小队名单:已绑定 且 在本群用过指令的 QQ;群成员记录为空时回退到全部已绑定(私人小队)。"""
        bindings = self.state.get("bindings", {}) or {}
        gm = (self.state.get("group_members", {}) or {}).get(str(gid), {}) or {}
        qqs = [q for q in bindings if str(q) in gm] if gm else list(bindings)
        return qqs

    async def _squad_progress_data(self, gid: str) -> Optional[dict]:
        """聚合本群小队进度。返回渲染 data 或 None(读不到存档)。存档只读,不改。"""
        self._last_save_use = time.time()
        data = await self._fetch_save_data(force_save=False)
        if not data:
            return None
        profiles = data.get("profiles") or {}
        progress = data.get("progress") or {}
        bindings = self.state.get("bindings", {}) or {}
        members = []
        for qq in self._squad_roster_qq(gid):
            b = bindings.get(qq) or {}
            prof = self._match_save_profile(b, profiles)   # 绑定 userId→playerId(uid2pid)或昵称兜底
            if not prof:
                continue
            pr = progress.get(prof.get("player_id"))       # 进度按存档 playerId 键
            if not pr:
                continue
            # 当前进行中的任务 -> 中文名(下一步建议);去掉隐藏/展示台内部任务
            nexts = []
            for qid in pr.get("active_quests", []):
                if qid.startswith(("Hidden_", "Test_", "Sub_PalDisplay")):
                    continue
                m = self._mission_by_id.get(qid)
                nexts.append(m["name"] if m else qid)
            members.append({
                "name": _esc(b.get("name", "玩家")),
                "paldeck": pr.get("paldeck", 0),
                "fasttravel": pr.get("fasttravel", 0),
                "towers": len(pr.get("tower_bosses", [])),
                "field_bosses": pr.get("field_bosses", 0),
                "dungeon": pr.get("dungeon_normal", 0) + pr.get("dungeon_fixed", 0),
                "relics": pr.get("relics", 0),
                "areas": pr.get("areas_found", 0),
                "next": nexts[:3],
            })
        members.sort(key=lambda m: (-m["towers"], -m["paldeck"]))
        # 群级手动勾选目标
        squad = (self.state.get("squad", {}) or {}).get(str(gid), {}) or {}
        checklist = []
        for item, whos in (squad.get("checklist") or {}).items():
            names = [self.state.get("bindings", {}).get(q, {}).get("name") or f"QQ{q}" for q in whos]
            checklist.append({"item": _esc(item), "done_by": [_esc(n) for n in names], "count": len(whos)})
        dex_total = getattr(self, "_dex_collectible", 287) or 287
        return {"members": members, "count": len(members),
                "dex_total": dex_total, "checklist": checklist,
                "hint": "存档自动同步:图鉴/传送点/塔主/野外boss/地牢/遗物/区域/当前任务;手动目标用 /帕鲁小队勾选 <目标>"}

    async def _cmd_squad(self, event: AstrMessageEvent):
        gid = str(event.get_group_id() or "")
        if not gid:
            return await self._msg_card(event, "👥", "请在群里用", desc="小队进度按群聚合，请在群聊里发 /帕鲁小队进度。", color="#F5A623")
        d = await self._squad_progress_data(gid)
        if d is None:
            return await self._msg_card(event, "🛰️", "暂时读不到存档",
                                        desc="未挂载 docker.sock 或存档读取失败，稍后再试。手动目标仍可用 /帕鲁小队勾选。", color="#F5A623")
        if not d["members"] and not d["checklist"]:
            return await self._msg_card(event, "👥", "小队还没有进度",
                                        desc="让群友先 /帕鲁绑定 <游戏名> 并上线一次；或用 /帕鲁小队勾选 <目标> 手动记录探索目标。", color="#9a8a91")
        return await self._img(event, self._t("squad"), d)

    async def _cmd_squad_check(self, event: AstrMessageEvent, args: list[str]):
        """群成员手动勾选/取消一个探索目标(记录是谁完成):/帕鲁小队勾选 <目标>。再发一次=取消自己。"""
        gid = str(event.get_group_id() or "")
        qq = str(event.get_sender_id())
        if not gid:
            return await self._msg_card(event, "✏️", "请在群里用", desc="请在群聊里发 /帕鲁小队勾选 <目标>。", color="#F5A623")
        item = " ".join(args).strip()
        if not item:
            return await self._msg_card(event, "✏️", "请提供目标",
                                        desc="用法：/帕鲁小队勾选 <目标>\n例：/帕鲁小队勾选 世界树探索\n再发一次取消你自己的勾选。", color="#E5484D")
        squad = self.state.setdefault("squad", {}).setdefault(gid, {}).setdefault("checklist", {})
        whos = squad.setdefault(item, [])
        if qq in whos:
            whos.remove(qq)
            act = "取消勾选"
            if not whos:
                squad.pop(item, None)
        else:
            whos.append(qq)
            act = "已勾选"
        self._save_state()
        return await self._msg_card(event, "✅", f"{act}「{_esc(item)}」",
                                    desc=f"发 /帕鲁小队进度 查看小队总览。", color="#30A46C")

    async def _cmd_squad_reset(self, event: AstrMessageEvent, args: list[str]):
        """管理员重置本群手动勾选清单:/帕鲁小队重置。"""
        gid = str(event.get_group_id() or "")
        if gid and gid in (self.state.get("squad", {}) or {}):
            self.state["squad"].pop(gid, None)
            self._save_state()
        return await self._msg_card(event, "🧹", "已重置本群小队清单", desc="本群的手动勾选目标已清空(存档自动同步部分不受影响)。", color="#30A46C")

    # ------------------------------------------------------------------
    # 首选2：据点体检(/帕鲁据点体检)——聚合小队(公会共享)据点工作帕鲁,给工人/适性缺口/伤病摘要。只读,不改存档。
    # ------------------------------------------------------------------
    def _load_basecamp_rules(self) -> dict:
        if getattr(self, "_bc_rules", None) is None:
            try:
                base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "basecamp_rules.json")
                with open(base, encoding="utf-8") as f:
                    self._bc_rules = json.load(f)
            except Exception:  # noqa: BLE001
                self._bc_rules = {"work_types": [], "health_thresholds": {}}
        return self._bc_rules

    async def _basecamp_health_data(self, gid: str) -> Optional[dict]:
        """聚合本群小队据点工作帕鲁的体检数据(公会共享,按 iid 去重)。存档只读。读不到→None。"""
        self._last_save_use = time.time()
        data = await self._fetch_save_data(force_save=False)
        if not data:
            return None
        profiles = data.get("profiles") or {}
        bindings = self.state.get("bindings", {}) or {}
        workers = {}   # iid -> pal(据点共享帕鲁在每个成员档案里各有一份,去重)
        for qq in self._squad_roster_qq(gid):
            prof = self._match_save_profile(bindings.get(qq), profiles)   # 绑定→存档档案(uid2pid/昵称)
            for pal in (prof or {}).get("basecamp", []):
                workers.setdefault(pal.get("iid") or id(pal), pal)
        # 每只算一次 view,保留所属据点(base_cid);一个公会最多 4 个据点
        views = []
        for pal in workers.values():
            try:
                v = self._basecamp_view(pal)
            except Exception:  # noqa: BLE001
                continue
            v["base_cid"] = pal.get("base_cid") or ""
            views.append(v)
        return views

    def _group_bases(self, views: list) -> list:
        """把 views 按 base_cid 分组,按 cid 排序分配稳定据点号。返回 [{no, cid, views}]。"""
        by: dict = {}
        for v in views:
            by.setdefault(v.get("base_cid") or "", []).append(v)
        return [{"no": i, "cid": cid, "views": by[cid]} for i, cid in enumerate(sorted(by), 1)]

    def _base_health_metrics(self, views: list) -> dict:
        """一组据点工作帕鲁的体检指标:工作适性覆盖/缺口 + 伤病/饥饿/理智/工作病计数 + 建议。"""
        rules = self._load_basecamp_rules()
        th = rules.get("health_thresholds", {})
        hp_low, stom_low = th.get("hp_low_pct", 50), th.get("stomach_low_pct", 30)
        coverage = []
        for wt in rules.get("work_types", []):
            cn = wt["cn"]
            cnt = sum(1 for v in views if any(w["k"] == cn for w in v.get("works", [])))
            maxlv = max([w["lv"] for v in views for w in v.get("works", []) if w["k"] == cn] or [0])
            coverage.append({"cn": cn, "count": cnt, "maxlv": maxlv,
                             "essential": bool(wt.get("essential")), "gap": cnt == 0})
        gaps = [c["cn"] for c in coverage if c["gap"] and c["essential"]]
        hurt = sum(1 for v in views if v.get("hp_pct") and v["hp_pct"] < hp_low)
        hungry = sum(1 for v in views if v.get("hungry"))
        low_san = sum(1 for v in views if v.get("low_san"))
        sick = sum(1 for v in views if v.get("sick"))
        low_stom = sum(1 for v in views if v.get("stomach") and v["stomach"] < stom_low)
        advices = []
        if gaps:
            advices.append(f"缺关键工作适性：{('、').join(gaps)} —— 抓/放对应适性帕鲁进据点补齐。")
        if hungry or low_stom:
            advices.append(f"有 {max(hungry, low_stom)} 只饥饿/低饱食 —— 检查喂食箱食物是否断供、补种农场。")
        if sick:
            advices.append(f"有 {sick} 只工作病(扭伤/虚弱/消沉) —— 放进帕鲁床/温泉/药品设施休养。")
        if low_san:
            advices.append(f"有 {low_san} 只理智低 —— 减负、加温泉/娱乐设施,避免暴走。")
        if hurt:
            advices.append(f"有 {hurt} 只残血(<{hp_low}%) —— 撤下休养或喂治疗药。")
        if not advices and views:
            advices.append("据点状态良好：关键适性齐全,无明显伤病/饥饿。")
        return {"workers": len(views), "working": sum(1 for v in views if v.get("working")),
                "coverage": coverage, "gaps": gaps, "hurt": hurt, "hungry": hungry,
                "low_san": low_san, "sick": sick, "low_stom": low_stom, "advices": advices}

    async def _cmd_basecamp_health(self, event: AstrMessageEvent, args: list[str]):
        gid = str(event.get_group_id() or "")
        if not gid:
            return await self._msg_card(event, "🏰", "请在群里用", desc="据点体检按群小队聚合，请在群聊里发 /帕鲁据点体检。", color="#F5A623")
        views = await self._basecamp_health_data(gid)
        if views is None:
            return await self._msg_card(event, "🛰️", "暂时读不到存档",
                                        desc="未挂载 docker.sock 或存档读取失败，稍后再试。", color="#F5A623")
        if not views:
            return await self._msg_card(event, "🏰", "据点里还没有工作帕鲁",
                                        desc="让群友先 /帕鲁绑定 并上线一次；或把帕鲁从帕鲁箱放到据点工作后再体检。", color="#9a8a91")
        bases = self._group_bases(views)
        sel = int(args[0]) if args and args[0].isdigit() else 0     # 0=全部;N=第N据点
        sel = sel if 1 <= sel <= len(bases) else 0
        scope = next((b["views"] for b in bases if b["no"] == sel), views) if sel else views
        d = self._base_health_metrics(scope)
        d["bases"] = [{"no": b["no"], "count": len(b["views"])} for b in bases]
        d["selected"] = sel
        d["sel_label"] = f"据点{sel}" if sel else ("全部据点" if len(bases) > 1 else "据点")
        d["multi"] = len(bases) > 1
        d["source"] = "工作适性来自客户端 DataTable;体检只读,不改存档。多据点可发 /帕鲁据点体检 <据点号>"
        return await self._img(event, self._t("basehealth"), d)

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
        """带归属校验的绑定：该角色已被别的 QQ 绑定则拒绝；admin_confirm 模式下非受信用户挂起待批；否则落库回成功卡。"""
        if self._bind_owner(uid, qq):
            return await self._msg_card(
                event, "🔒", "该角色已被绑定",
                desc="这个游戏角色已被其他 QQ 绑定，无法重复绑定。\n"
                     "如需换绑，请联系管理员用 /帕鲁解绑 <QQ或角色名> 先解绑。",
                color="#E5484D")
        # admin_confirm 模式:非受信用户(非管理/非 trusted_qq)不直接绑,挂起等管理员批准(防冒绑他人角色偷看隐私)
        if self.config.get("bind_mode", "open") == "admin_confirm" and not self._is_trusted(qq):
            pend = self.state.setdefault("bind_pending", {})
            pend[str(qq)] = {"userId": uid, "name": name, "ts": int(time.time())}
            self._save_state()
            return await self._msg_card(
                event, "⏳", "绑定待管理员批准",
                desc=f"已提交绑定到角色「{_esc(name)}」的申请。\n"
                     f"当前为「需管理员批准」模式，请管理员发 /帕鲁批准绑定 {qq} 通过。",
                color="#F5A623")
        self._do_bind(qq, uid, name)
        self.state.get("bind_pending", {}).pop(str(qq), None)   # 清掉可能的旧挂起
        return await self._msg_card(event, "🔗", "绑定成功", desc=_esc(ok_desc), color="#30A46C")

    async def _cmd_bind_approve(self, event: AstrMessageEvent, args: list[str]):
        """管理员批准/查看挂起绑定：/帕鲁批准绑定 [QQ]。无参列出待批。"""
        pend = self.state.get("bind_pending", {}) or {}
        if not args:
            if not pend:
                return await self._msg_card(event, "✅", "没有待批准的绑定", desc="当前没有挂起的绑定申请。", color="#30A46C")
            lines = [f"• QQ {q} → 角色「{_esc(r.get('name', '?'))}」" for q, r in pend.items()]
            return await self._msg_card(event, "⏳", f"待批准绑定 {len(pend)} 条",
                                        desc="\n".join(lines) + "\n\n批准发：/帕鲁批准绑定 <QQ>；拒绝发：/帕鲁拒绝绑定 <QQ>",
                                        color="#F5A623")
        qq = args[0].strip()
        req = pend.get(qq)
        if not req:
            return await self._msg_card(event, "🔍", "没有该 QQ 的待批绑定", desc=f"QQ {qq} 没有挂起的绑定申请。", color="#F5A623")
        if self._bind_owner(req["userId"], qq):   # 期间可能被别人绑了
            pend.pop(qq, None); self._save_state()
            return await self._msg_card(event, "🔒", "申请作废", desc=f"角色「{_esc(req.get('name', '?'))}」已被别的 QQ 绑定，此申请已删除。", color="#E5484D")
        self._do_bind(qq, req["userId"], req["name"])
        pend.pop(qq, None); self._save_state()
        return await self._msg_card(event, "🔗", "已批准绑定", desc=f"QQ {qq} 已绑定到角色「{_esc(req.get('name', '?'))}」。", color="#30A46C")

    async def _cmd_bind_reject(self, event: AstrMessageEvent, args: list[str]):
        """管理员拒绝挂起绑定：/帕鲁拒绝绑定 <QQ>。"""
        if not args:
            return await self._msg_card(event, "✏️", "请提供要拒绝的 QQ", desc="用法：/帕鲁拒绝绑定 <QQ>", color="#E5484D")
        qq = args[0].strip()
        pend = self.state.get("bind_pending", {}) or {}
        if pend.pop(qq, None) is None:
            return await self._msg_card(event, "🔍", "没有该 QQ 的待批绑定", desc=f"QQ {qq} 没有挂起的绑定申请。", color="#F5A623")
        self._save_state()
        return await self._msg_card(event, "🚫", "已拒绝绑定", desc=f"已删除 QQ {qq} 的绑定申请。", color="#9a8a91")

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
        rkey, rhex = self._passive_rank_meta(rank, sign)   # 游戏箭头图标键 + 品阶金/红色
        return {"name": meta.get("name") or pid, "rank": rank, "sign": sign,
                "effect": meta.get("effect", ""), "color": color,
                "rank_key": rkey, "hex": rhex,
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

    _HUMAN_TYPE = (("hunter", "盗猎者"), ("believer", "信徒"), ("firecult", "火祭教团"),
                   ("police", "警察"), ("salesperson", "流浪商人"), ("trader", "商人"),
                   ("soldier", "士兵"), ("guard", "守卫"), ("scientist", "研究员"),
                   ("desertpeople", "沙漠居民"), ("snowpeople", "雪地居民"),
                   ("people", "平民"), ("male_", "居民"), ("female_", "居民"), ("boss", "头目"))

    def _human_name(self, char_id: str):
        """存档 char_id 是抓到的人类时给中文名(先查名表,再按类型兜底);非人类返回 None。"""
        cid = str(char_id or "").lower()
        hn = (getattr(self, "_human_names", None) or {}).get(cid)
        if hn:
            return hn
        return next((cn for key, cn in self._HUMAN_TYPE if key in cid), None)

    def _resolve_owned_pal(self, char_id: str):
        """存档 char_id -> 图鉴 pal(容错 boss/元素变种前后缀);查不到返回 None。"""
        cid = str(char_id or "").lower()
        p = self._pal_by_dev.get(cid)
        if p:
            return p
        base = re.sub(r"^(boss_|gym_|raid_|predator_)", "", cid)
        base = re.sub(r"(_otomo|_\d+|_water|_fire|_ground|_dark|_ice|_leaf|_electric|_dragon)$", "", base)
        return self._pal_by_dev.get(base)

    def _pal_view(self, pal: dict) -> dict:
        """_pal_brief 原始字段 -> 卡片展示字段(中文名/图标/属性/词条/技能)。"""
        cid = str(pal.get("char_id", ""))
        p = self._resolve_owned_pal(cid)
        hname = None if p else self._human_name(cid)   # 抓到的人类给中文名
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
                   "desc": ((p.get("partner_skill_description") or
                             ("该伙伴技能游戏内暂未提供中文详细说明" if p.get("partner_skill_title") else "")) if p else "")}
        # 当前真实 HP/攻/防：游戏公式(头目HP种族×1.2 + 等级+天赋+浓缩) × 被动加成，经实测校准。
        _batk = max(int(stats.get("shot_attack") or 0), int(stats.get("melee_attack") or 0)) or 100
        _pb = self._passive_bonus(pal.get("passives", []))
        _hp_f, _cur_atk, _cur_def = self._combat_stats(
            int(stats.get("hp") or 0) or 100, _batk, int(stats.get("defense") or 0) or 50,
            int(pal.get("level", 1) or 1), int(pal.get("iv_hp", 0) or 0),
            int(pal.get("iv_atk", 0) or 0), int(pal.get("iv_def", 0) or 0),
            int(pal.get("rank", 1) or 1), bool(pal.get("is_alpha")),
            _pb["hp"], _pb["atk"], _pb["def"])
        # 生命值：满血含灵魂/状态点时存档更准、受伤时公式 MaxHP 更准 → 取较大者
        _hp_display = max(int(pal.get("hp", 0) or 0), _hp_f)
        return {
            "name": (p["pal_name"] if p else (hname or "未知")),
            "index": str(p.get("pal_index", "")) if p else "",
            "icon": self._pal_icon(p.get("pal_dev_name")) if p else (self._human_icon(cid) if hname else ""),
            "is_human": bool(hname), "elements": p.get("elements", []) if p else [],
            "level": pal.get("level", 1), "gender": self._gender_cn(pal.get("gender", "")),
            "alpha": bool(pal.get("is_alpha")), "lucky": bool(pal.get("lucky")),
            "nickname": _esc(pal.get("nickname", "")), "hp": _hp_display,
            "health": self._health_view(pal.get("health", "")),
            "condense": condense, "rarity": rarity, "rtier": self._rarity_tier(rarity),
            "iv_hp": pal.get("iv_hp", 0), "iv_atk": pal.get("iv_atk", 0), "iv_def": pal.get("iv_def", 0),
            "passives": [self._passive_view(x) for x in pal.get("passives", [])],
            "wazas": [self._waza_view(x) for x in pal.get("equip_waza", [])],
            "base_atk": int(stats.get("shot_attack") or stats.get("melee_attack") or 0),
            "base_def": int(stats.get("defense") or 0),
            "cur_atk": _cur_atk, "cur_def": _cur_def,
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
                iid = self._canon_iid(it.get("id"))
                meta = self._item_by_id.get(iid)
                cells.append({"name": meta["name"] if meta else it.get("id", "?"),
                              "icon": self._item_icon(iid),
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
        # ingame 主题为手机竖屏统一单列窄卡(540)
        multi = len(pals) > 1
        ingame = self._style() == "ingame"
        width = CARD_WIDTH if ingame else (920 if multi else CARD_WIDTH)
        return await self._img(event, self._t("team"),
                               {"title": f"🐾 {name} 的出战队伍",
                                "subtitle": f"共 {len(pals)} 只帕鲁 · 数据来自存档",
                                "pals": pals, "team_cols": 1 if ingame else (2 if multi else 1)},
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
        p = self._resolve_owned_pal(str(pal.get("char_id", "")))   # 容错 BOSS_/元素变种前后缀
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
        """据点工作帕鲁状态。一个公会最多 4 个据点:第1个数字=据点号,第2个数字=页码;非数字(管理员)=目标玩家名。"""
        a = list(args)
        digits = [x for x in a if x.isdigit()]
        a = [x for x in a if not x.isdigit()]
        base_no = int(digits[0]) if digits else 0        # 0=未指定(多据点默认第1个)
        page = int(digits[1]) if len(digits) > 1 else 1
        sp, name, err = await self._resolve_target_sp(event, a)
        if err:
            return err
        # 按 base_cid 分组成各据点(稳定编号)
        allbase = sorted(sp.get("basecamp", []),
                         key=lambda p: (not p.get("lucky"), not p.get("is_alpha"), -(p.get("level") or 0)))
        groups: dict = {}
        for p in allbase:
            groups.setdefault(p.get("base_cid") or "", []).append(p)
        base_order = sorted(groups)                       # cid 排序 -> 稳定据点号
        bases = [{"no": i, "count": len(groups[cid])} for i, cid in enumerate(base_order, 1)]
        multi = len(base_order) > 1
        base_no = base_no if 1 <= base_no <= len(base_order) else (1 if multi else 0)
        sel_pals = groups[base_order[base_no - 1]] if base_no else allbase
        cells = self._safe_views(self._basecamp_view, sel_pals, "据点")
        hurt = sum(1 for c in cells if c["health"]["hurt"])
        hungry = sum(1 for c in cells if c["starving"])
        low_san = sum(1 for c in cells if c["low_san"])
        total = len(cells)
        pages = max(1, (total + BASECAMP_PAGE_SIZE - 1) // BASECAMP_PAGE_SIZE)
        page = min(max(1, page), pages)
        shown = cells[(page - 1) * BASECAMP_PAGE_SIZE: page * BASECAMP_PAGE_SIZE]
        tgt = " ".join(a)
        tgt_part = (" " + tgt) if tgt else ""
        b_part = f" {base_no}" if base_no else ""
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁据点{tgt_part}{b_part} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("basecamp"),
                               {"name": name, "total": total, "hurt": hurt,
                                "hungry": hungry, "low_san": low_san, "cells": shown,
                                "page": page, "pages": pages, "pager": pager,
                                "bases": bases, "selected": base_no, "multi": multi,
                                "sel_label": (f"据点{base_no}" if base_no else "据点")})

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
            pl = self._resolve_owned_pal(str(p.get("char_id", "")))   # 容错 BOSS_/元素变种前后缀
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

    @staticmethod
    def _guild_display_name(g: dict, leader: str) -> str:
        """公会展示名:玩家自定义了公会名就用真名,否则(游戏默认 Unnamed Guild/空)用「队长」的公会。"""
        gn = (g.get("guild_name") or "").strip()
        if gn and gn.lower() != "unnamed guild":
            return gn
        return f"「{leader}」的公会"

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
        # 每成员 等级/帕鲁数：跨 CharacterSaveParameterMap 按 uid 关联(存档只读,真实存档 12/12 验证)
        profiles = await self._fetch_save_profiles(max_age=self._fresh_ttl()) or {}
        prof_by_norm = {self._norm_uid(k): v for k, v in profiles.items()}

        def _mstat(m):
            pf = prof_by_norm.get(self._norm_uid(m["uid"]))
            if not pf:
                return None, None
            return int(pf.get("level") or 0), len(pf.get("party", [])) + len(pf.get("palbox", []))
        guild_pals = sum((_mstat(m)[1] or 0) for m in members)
        pages = max(1, (total + GUILD_PAGE_SIZE - 1) // GUILD_PAGE_SIZE)
        page = min(page, pages)
        start = (page - 1) * GUILD_PAGE_SIZE
        shown = members[start:start + GUILD_PAGE_SIZE]
        view = []
        for i, m in enumerate(shown):
            lvl, pals = _mstat(m)
            view.append({"name": _esc(m["name"]), "is_leader": m["uid"] == g.get("admin_uid"),
                         "no": start + i + 1, "level": lvl, "pals": pals})
        tgt_part = (" " + name) if name else ""
        pager = ""
        if pages > 1:
            nxt = page + 1 if page < pages else 1
            pager = f"发「/帕鲁公会{tgt_part} {nxt}」翻到第 {nxt} 页（共 {pages} 页）"
        return await self._img(event, self._t("guild"),
                               {"gname": _esc(self._guild_display_name(g, leader)), "leader": leader, "total": total,
                                "rank": rank, "members": view, "guild_pals": guild_pals,
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
                # 护栏:SG 必须是足够深的绝对路径(至少 3 段),否则 "$SG"/*/ 可能误删顶层目录。
                'case "$SG" in /*/*/*) ;; *) echo "BADSG"; exit 6;; esac; '
                'ls "$BK"/*_"$TS".tar.gz >/dev/null 2>&1 || { echo "NOBACKUP"; exit 5; }; '
                # 只清含 Level.sav 的真实世界目录(与删档一致),不碰其它目录;untar 会重建世界内容。
                'for d in "$SG"/*/; do d="${d%/}"; [ -f "$d/Level.sav" ] && rm -rf "$d"; done; '
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
            # 公会解析(1.0 base_camp 新格式)诊断
            if prof and prof.get("profiles"):
                gs = prof.get("guilds") or []
                if gs:
                    tot = sum(len(x.get("members", [])) for x in gs)
                    named = sum(1 for x in gs if (x.get("guild_name") or "").strip()
                                and x["guild_name"].strip().lower() != "unnamed guild")
                    add("✅", "公会解析", f"{len(gs)} 个公会 · {tot} 名成员"
                        + (f" · {named} 个自定义名" if named else " · 均游戏默认名"))
                else:
                    add("⚠️", "公会解析", "未解析到公会",
                        "存档里可能确实没有公会；若游戏内有公会却读不到，可能 1.0 格式又变，请反馈。")

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

    def _rank_list(self, top: int = 10, scope: str = "week") -> list[dict]:
        """在线时长排行(肝帝榜)。scope: week 本周 / today 今日 / total 累计总榜。"""
        wk = self._week_id()
        today = datetime.now().strftime("%Y-%m-%d")
        online = set(self.state.get("online", {}))
        rows = []
        for uid, t in self.state.get("totals", {}).items():
            if scope == "total":
                sec = t.get("total", 0)
            elif scope == "today":
                sec = t.get("day", 0) if t.get("day_id") == today else 0
            else:
                sec = t.get("week", 0) if t.get("week_id") == wk else 0
            if sec <= 0:
                continue
            rows.append({"name": t.get("name", "玩家"), "sec": int(sec), "online": uid in online})
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
        # 先取消后台任务并 await 到真正退出(否则重载后旧轮询残留、重复播报/拉档)。
        for _attr in ("_poll_task", "_prewarm_task"):
            t = getattr(self, _attr, None)
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"{LOG_PREFIX} 后台任务 {_attr} 退出异常(忽略): {e}")
        # 任务停稳后再关网络/渲染资源
        if self._session and not self._session.closed:
            await self._session.close()
        try:
            await self._renderer.close()   # 关闭本地渲染器(Chromium)
        except Exception:  # noqa: BLE001
            pass
        logger.info(f"{LOG_PREFIX} 插件已卸载：后台任务已结束，HTTP 会话与渲染器已关闭")
