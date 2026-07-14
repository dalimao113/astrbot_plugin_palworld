"""物品详情「重量」护栏(item_extra.weight,原本已加载但未展示)。

- 有效重量(0 < w < 9999)展示;NPC 哨兵值(99999)和 0/缺失不展示,避免误导。
- 三主题物品卡都能渲染重量。
"""
import asyncio

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()   # 载入 items.json + item_extra.json + recipes.json
    return o


def _detail(o, item):
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(data=data)
        return "I"
    o._img, o._t = _img, (lambda k: k)
    asyncio.new_event_loop().run_until_complete(o._item_detail(None, item))
    return cap["data"]


def test_weight_shown_for_real_items():
    o = _plugin()
    # 找一个 item_extra 里 weight 在合理区间的物品
    iid = next((k for k, v in o._item_extra.items()
                if isinstance(v.get("weight"), (int, float)) and 0 < v["weight"] < 9999), None)
    assert iid and iid in o._item_by_id
    d = _detail(o, o._item_by_id[iid])
    assert d["weight"] and float(d["weight"]) > 0


def test_weight_sentinel_hidden():
    o = _plugin()
    # 99999 哨兵值不展示
    iid = next((k for k, v in o._item_extra.items() if v.get("weight") == 99999.0), None)
    if iid and iid in o._item_by_id:
        assert _detail(o, o._item_by_id[iid])["weight"] is None


def test_weight_renders_all_themes():
    o = _plugin()
    iid = next(k for k, v in o._item_extra.items()
               if isinstance(v.get("weight"), (int, float)) and 0 < v["weight"] < 9999)
    d = _detail(o, o._item_by_id[iid])
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["item"]).render(**d)
        assert "重量" in html
