"""三主题语义图标渲染烟测(共享图标层落地验证)。

对属性克制图 / 帕鲁详情 / 闪光墙:fantasy、pixel、ingame **都必须渲染出真实游戏图标**(data:image/png),
且不抛异常。守护「游戏图标三主题共享」不被回退成 Emoji。需 jinja2(缺失自动跳过)。
"""
import os

import pytest

pytest.importorskip("jinja2")
import jinja2  # noqa: E402

from astrbot_plugin_palworld.render.assets import AssetResolver  # noqa: E402
from astrbot_plugin_palworld.render.templates import STYLES  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV = jinja2.Environment(autoescape=False)


def _render(key, ctx):
    res = AssetResolver(_ROOT)
    out = {}
    for theme in ("fantasy", "pixel", "ingame"):
        c = dict(ctx)
        c["icons"] = res.game_icon_map(theme)
        if theme == "ingame":
            c["parts"] = res.component_uris()
        out[theme] = _ENV.from_string(STYLES[theme][key]).render(**c)
    return out


_PAL = dict(
    name="皮皮鸡", index="001", elements=["火", "龙"], rarity=3, nocturnal=True,
    is_boss=False, is_tower_boss=False, desc="测试", partner_title="", partner_desc="",
    skills=[{"name": "火焰弹", "power": 50, "cd": 5, "elem": "火"}],
    works=[{"k": "点火", "lv": 3}, {"k": "采矿", "lv": 2}], drops=[], ranch=[],
    hp=100, atk=80, defense=70, shot=60, stamina=50, walk=40, run=90, ride=100,
    transport=80, food=50, size="M", egg="火焰蛋", lv="10-15", price=1000, cap=1.0,
)
_ELEM = {"elems": [{"cn": "火", "emoji": "🔥", "color": "#ff7043",
                    "strong": [{"cn": "草", "emoji": "🌿"}], "weak": [{"cn": "水", "emoji": "💧"}]}]}
_SHINY = {"title": "全服闪光墙", "sub": "共 1 只", "badge": "✨", "badge_kind": "lucky",
          "rows": [{"name": "皮皮鸡", "owner": "阿狸", "icon": ""}], "top_owners": "阿狸×1"}


@pytest.mark.parametrize("key,ctx,need_png", [
    ("element", _ELEM, True),
    ("paldex", _PAL, True),
    ("shiny", _SHINY, True),
])
def test_semantic_icons_render_in_all_three_themes(key, ctx, need_png):
    out = _render(key, ctx)
    for theme, html in out.items():
        assert html, f"{key}@{theme} 渲染为空"
        if need_png:
            assert "data:image/png" in html, f"{key}@{theme} 未渲染出真实游戏图标(回退了 Emoji?)"


def test_element_chart_no_emoji_fallback_when_icon_present():
    """9 系属性图标齐全 → 三主题都不该再出现 🔥 等属性 Emoji。"""
    out = _render("element", _ELEM)
    for theme, html in out.items():
        assert "🔥" not in html, f"{theme} 属性图仍回退 Emoji 🔥"
