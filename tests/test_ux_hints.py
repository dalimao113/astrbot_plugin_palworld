"""好用性:详情卡相关指令引导 + 榜单口径说明。

- 图鉴/物品详情卡带 related(相关指令),引导串联使用;三主题渲染。
- 排行榜(rank 模板)带 note 口径说明,减少"这榜怎么算"疑问。
"""
import asyncio

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES

_ENV = Environment(autoescape=False, undefined=ChainableUndefined)


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


def test_paldex_has_related():
    o = _plugin()
    p = next(iter(o._pal_by_name.values()))
    d = o._pal_card_data(p)
    assert d["related"] and any("栖息区域" in c for c in d["related"])
    assert all(p["pal_name"] in c for c in d["related"])   # 都带这只帕鲁名


def test_item_related_and_render():
    o = _plugin()
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(data=data)
        return "I"
    o._img, o._t = _img, (lambda k: k)
    it = o._item_by_name.get("帕鲁球") or next(iter(o._item_by_name.values()))
    asyncio.new_event_loop().run_until_complete(o._item_detail(None, it))
    d = cap["data"]
    assert d["related"] and any("材料路线" in c for c in d["related"])
    for st in ("fantasy", "pixel", "ingame"):
        html = _ENV.from_string(STYLES[st]["item"]).render(**d)
        assert "相关指令" in html


def test_rank_note_renders_all_themes():
    d = {"rows": [{"name": "A", "online": False, "dur": "5种", "pct": 50, "medal": "🥇"}],
         "rank_title": "📖 图鉴收集榜", "rank_sub": "x", "note": "按拥有的不同帕鲁种类数排序。"}
    for st in ("fantasy", "pixel", "ingame"):
        html = _ENV.from_string(STYLES[st]["rank"]).render(**d)
        assert "口径" in html and "种类数" in html
