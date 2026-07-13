"""材料路线(次选:/帕鲁材料路线 <物品> [数量])护栏。

- 配方递归展开到底:采集/掉落类原料为叶子,可制作物品继续拆。
- 数量按份线性放大;不可制作物品(采集/掉落)返回 None(命令给友好提示)。
- 数据只来自 data/recipes.json(客户端 pak 配方表),不猜测。
"""
from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()          # 载入 items.json + recipes.json
    return o


def test_matroute_recursive_expand():
    o = _plugin()
    it = o._item_by_name.get("火箭发射器")
    assert it, "样例物品应存在"
    d = o._matroute_data(it, 1)
    assert d and d["direct"] and d["base"]
    # 直接配方里,可制作的中间产物应标记 craftable
    assert any(m["craftable"] for m in d["direct"])
    # 原料总需求全部是叶子(在 recipes 里没有配方,或采集掉落)
    for m in d["base"]:
        rec = o._recipe_for(m["name"])
        assert not (rec and rec.get("mats")), f"{m['name']} 不应再有配方(应已展开)"
    # 用到的制作台非空
    assert d["benches"]


def test_matroute_multiplier_scales():
    o = _plugin()
    it = o._item_by_name.get("火箭发射器")
    a = {m["name"]: m["count"] for m in o._matroute_data(it, 1)["base"]}
    b = {m["name"]: m["count"] for m in o._matroute_data(it, 3)["base"]}
    assert a and all(b[k] == v * 3 for k, v in a.items())     # N 份线性放大


def test_matroute_uncraftable_returns_none():
    o = _plugin()
    # 找一个没有配方的采集类原料
    raw = next((it for it in o._items
                if not ((o._recipes or {}).get(it.get("item_id")) or {}).get("mats")), None)
    assert raw and o._matroute_data(raw, 1) is None


def test_matroute_renders_all_three_themes():
    o = _plugin()
    d = o._matroute_data(o._item_by_name["火箭发射器"], 2)
    env = Environment(autoescape=False, undefined=ChainableUndefined)  # 共享页脚 parts.* 缺省容忍
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["matroute"]).render(**d)
        assert "火箭发射器" in html and "原料总需求" in html and "制作 ×2" in html
