"""词条品阶用游戏内箭头图标(白遮罩 CSS 上色)+ 品阶颜色,三主题共享。

- 词条大全(passlist)/推荐词条(passrec)按 rank/sign 映射游戏 T_icon_skillstatus_rank_arrow_* 图标,
  金色=高阶好词条、红=减益;白遮罩由模板 CSS(-webkit-mask + background)上色。
- 之前只有 ingame 显示箭头,fantasy/pixel 只有 emoji;现三主题统一。
"""
import os

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
import astrbot_plugin_palworld.render.assets as A
from astrbot_plugin_palworld.render.templates import STYLES

_ENV = Environment(autoescape=False, undefined=ChainableUndefined)
_RES = A.AssetResolver(os.path.join(os.path.dirname(A.__file__), ".."))


def test_rank_meta_mapping():
    m = main.PalworldPlugin._passive_rank_meta
    assert m(3, 1)[0] == "rank_up3" and m(3, 1)[1].startswith("#")
    assert m(1, -1)[0] == "rank_down"
    assert m(2, 1)[0] == "rank_up2" and m(1, 1)[0] == "rank_up1"
    assert m(5, 1)[0] == "rank_up3_plus"


def test_passlist_shows_game_arrow_all_themes():
    items = [{"name": "攻击提升", "effect": "攻击+30%", "rank": 3, "sign": 1,
              "rank_key": "rank_up3", "color": "#ffce4a"},
             {"name": "胆小", "effect": "攻击-10%", "rank": 1, "sign": -1,
              "rank_key": "rank_down", "color": "#e0685f"}]
    for st in ("fantasy", "pixel", "ingame"):
        icons = _RES.game_icon_map(st)
        html = _ENV.from_string(STYLES[st]["passlist"]).render(
            cat="攻击类词条", count=2, color="#c9a86a", icon="⚔️", items=items, icons=icons,
            rk=icons.get("passive_rank", {}))
        # 用到了游戏箭头图标(mask 白遮罩 或 ingame img),且图标真实解析成 data URI
        assert ("webkit-mask" in html or "ig-rank" in html), st
        assert "data:image" in html, st
        assert "🟢" not in html and "🔴" not in html    # 不再用 emoji


def test_passrec_shows_game_arrow():
    sec = {"title": "⚔️ 战斗向", "color": "#e8c466",
           "items": [{"name": "攻击提升", "effect": "攻击+30%", "rank": 3, "stars": "★★★",
                      "rank_key": "rank_up3", "color": "#ffce4a"}]}
    for st in ("fantasy", "pixel", "ingame"):
        icons = _RES.game_icon_map(st)
        html = _ENV.from_string(STYLES[st]["passrec"]).render(
            name="X", index="1", icon="", elements=["火属性"], color="#e8c466",
            roles=["战斗"], sections=[sec], icons=icons)
        assert ("webkit-mask" in html or "ig-rank" in html) and "data:image" in html, st
