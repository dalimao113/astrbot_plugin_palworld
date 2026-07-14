"""队伍/帕鲁箱/据点帕鲁的工作适性 + 词条分类用游戏图标(而非 emoji)。

- 队伍卡(team,箱查询/据点共用)的工作适性从 emoji 改为真实游戏工作图标 icons.work[name]。
- 词条分类总览(passdex)分类图标:攻击/防御/生命/工作/生存 用真实游戏数值图标(新提取 attack/work_speed/san),
  无图标的(移动等)回退 emoji;修掉原来 emoji/icon 键不一致导致不显示的 bug。
"""
import os

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.render.assets as A
from astrbot_plugin_palworld.render.templates import STYLES

_ENV = Environment(autoescape=False, undefined=ChainableUndefined)
_RES = A.AssetResolver(os.path.join(os.path.dirname(A.__file__), ".."))


def test_newly_extracted_stat_icons_present():
    for k in ("attack", "work_speed", "san"):
        assert _RES.game_icon(f"stat.{k}"), f"stat.{k} 应已提取为游戏图标"


def test_team_work_uses_game_icon_not_emoji():
    pal = {"name": "电兽", "index": "1", "icon": "", "elements": ["雷属性"], "level": 30, "gender": "公",
           "alpha": False, "lucky": False, "nickname": "", "hp": 1500, "health": {}, "condense": 0,
           "rarity": 3, "rtier": "", "iv_hp": 80, "iv_atk": 70, "iv_def": 60, "passives": [], "wazas": [],
           "base_atk": 100, "base_def": 80, "cur_atk": 100, "cur_def": 80, "craft_speed": 100,
           "works": [{"name": "发电", "icon": "⚡", "level": 3}], "partner": {"title": "", "desc": ""}}
    for st in ("fantasy", "pixel", "ingame"):
        icons = _RES.game_icon_map(st)
        html = _ENV.from_string(STYLES[st]["team"]).render(pals=[pal], name="X", count=1, icons=icons)
        wk = icons["work"].get("发电", "")
        assert wk and wk[:24] in html, f"{st}: 队伍工作适性应用游戏图标"


def test_passdex_category_prefers_game_icon_else_emoji():
    cats = [{"name": "攻击", "emoji": "⚔️", "icon": _RES.game_icon("stat.attack"), "color": "#e15b5b",
             "count": 50, "sample": "x"},
            {"name": "元素", "emoji": "🔮", "icon": "", "color": "#b06ee0", "count": 10, "sample": "y"}]
    for st in ("fantasy", "pixel", "ingame"):
        html = _ENV.from_string(STYLES[st]["passdex"]).render(cats=cats, total=60, icons=_RES.game_icon_map(st))
        assert cats[0]["icon"][:20] in html    # 攻击用游戏图标
        assert "🔮" in html                     # 元素回退 emoji
