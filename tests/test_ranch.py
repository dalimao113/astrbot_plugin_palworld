"""牧场产出总览(/帕鲁牧场 [产物])护栏。

- 组合已有数据:牧场适性帕鲁 × 伙伴技能「分派到家畜牧场」真实描述里的产物。
- 挖掘类(玉藻狐等)无具体产物时如实标 random,不编造。
- 按产物反查(如 羊毛)只返回真的产该物的帕鲁;三主题可渲染。
"""
import asyncio

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


class _E:
    def get_sender_id(self):
        return "q0"

    def get_group_id(self):
        return "g1"


def _run(o, args):
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(data=data)
        return "I"
    o._img, o._t = _img, (lambda k: k)
    asyncio.new_event_loop().run_until_complete(o._cmd_ranch(_E(), args))
    return cap.get("data")


def test_ranch_overview_has_products_and_random():
    o = _plugin()
    d = _run(o, [])
    assert d["rows"] and len(d["rows"]) >= 25
    # 至少有一只有具体产物、且有具体产物的排在前面
    assert any(r["products"] for r in d["rows"])
    assert d["rows"][0]["products"]                 # 有产物的在前
    # 挖掘类如实标 random(无产物)
    assert any(r["random"] and not r["products"] for r in d["rows"])


def test_ranch_query_wool():
    o = _plugin()
    d = _run(o, ["羊毛"])
    assert d["rows"] and all(any("羊毛" in pr["name"] for pr in r["products"]) for r in d["rows"])
    names = {r["pal"] for r in d["rows"]}
    assert "棉悠悠" in names          # 真实存在的产羊毛帕鲁


def test_ranch_query_unknown_lists_products():
    o = _plugin()
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(title=title, desc=k.get("desc", ""))
        return "M"
    o._msg_card = _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_ranch(_E(), ["不存在的产物xyz"]))
    assert "没有牧场产" in cap["title"] and "可产的有" in cap["desc"]


def test_ranch_renders_all_themes():
    o = _plugin()
    d = _run(o, [])
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["ranch"]).render(**d)
        assert "牧场产出一览" in html and "棉悠悠" in html
