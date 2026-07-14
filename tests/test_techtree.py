"""科技树(/帕鲁科技树 [等级])护栏。

- 纯 tech.json 已有字段(level/points/is_boss),按解锁等级归档;无参给路线总览,带等级列该级全部解锁。
- 古代科技(is_boss)单独标注「古代科技点」,不与普通技术点混算。
- 三主题两种模式(overview/level)均能渲染。
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
    asyncio.new_event_loop().run_until_complete(o._cmd_techtree(_E(), args))
    return cap["data"]


def test_techtree_overview():
    o = _plugin()
    d = _run(o, [])
    assert d["mode"] == "overview" and d["levels"] and d["total"] == len(o._tech)
    assert all(x["lv"] > 0 and x["n"] > 0 for x in d["levels"])


def test_techtree_level_detail():
    o = _plugin()
    d = _run(o, ["1"])
    assert d["mode"] == "level" and d["level"] == 1 and d["items"]
    # 古代科技单独计数,不进普通技术点合计
    assert d["ancient_count"] == sum(1 for i in d["items"] if i["ancient"])


def test_techtree_renders_both_modes_all_themes():
    o = _plugin()
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for args, needle in (([], "各等级解锁路线"), (["10"], "科技树 · Lv.10")):
        d = _run(o, args)
        for st in ("fantasy", "pixel", "ingame"):
            html = env.from_string(STYLES[st]["techtree"]).render(**d)
            assert needle in html or needle.replace(" · ", " · ") in html
