"""材料用途反查(/帕鲁用途 <材料>)护栏——材料路线的逆。

- 反向索引 recipes + building_recipes;同名不同品阶去重,保留最小需求量。
- 用途多的材料(金属锭 400+)分页;查不到用途给友好提示;三主题可渲染。
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
        cap.update(kind="img", data=data)
        return "I"

    async def _msg(event, icon, title, **k):
        cap.update(kind="msg", title=title, desc=k.get("desc", ""))
        return "M"
    o._img, o._t, o._msg_card = _img, (lambda k: k), _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_matuse(_E(), args))
    return cap


def test_matuse_lists_products_dedup():
    o = _plugin()
    cap = _run(o, ["石炭"])
    assert cap["kind"] == "img"
    d = cap["data"]
    assert d["total"] >= 4 and d["rows"]
    # 去重:同名不重复出现
    names = [r["name"] for r in d["rows"]]
    assert len(names) == len(set(names))
    assert all(r["kind"] in ("物品", "建筑") and r["count"] > 0 for r in d["rows"])


def test_matuse_paginates_common_material():
    o = _plugin()
    d = _run(o, ["金属锭"])["data"]
    assert d["pages"] > 1 and len(d["rows"]) <= o._MATUSE_PAGE and d["pager"]
    # 翻到第 2 页返回不同内容
    d2 = _run(o, ["金属锭", "2"])["data"]
    assert d2["page"] == 2 and d2["rows"] != d["rows"]


def test_matuse_unknown_material():
    o = _plugin()
    cap = _run(o, ["纯装饰不可制作xyz"])
    assert cap["kind"] == "msg" and "暂无已知用途" in cap["title"]


def test_matuse_renders_all_themes():
    o = _plugin()
    d = _run(o, ["石炭"])["data"]
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["matuse"]).render(**d)
        assert "用途" in html and "被" in html
