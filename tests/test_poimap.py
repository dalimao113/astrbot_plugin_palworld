"""地图收集/地标标注(/帕鲁地图收集 [类别])护栏。

- 只标**有真实世界坐标**的命名地标/传送点/禁猎区(map_regions + map_ft_points);
  游戏文件无单个雕像/遗物宝箱逐点坐标,不臆造。
- 世界坐标经真实仿射变换 -> 主图百分比;越界(非主大陆)的点跳过。
- 无参给类别菜单;未知类别给提示;三主题可渲染。
"""
import asyncio
import json
import os

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    t = json.load(open(os.path.join(_DATA, "map_transform.json"), encoding="utf-8"))
    reg = json.load(open(os.path.join(_DATA, "map_regions.json"), encoding="utf-8"))
    ft = json.load(open(os.path.join(_DATA, "map_ft_points.json"), encoding="utf-8"))
    o._map_mu, o._map_mv = t["mu"], t["mv"]
    o._tree_mu = o._tree_mv = None
    o._map_regions = [(n, d["X"], d["Y"]) for n, d in reg.items()]
    o._ft_points = [(n, d["X"], d["Y"]) for n, d in ft.items()]

    def _opt(fn):
        p = os.path.join(_DATA, fn)
        return [(n, d["X"], d["Y"]) for n, d in json.load(open(p, encoding="utf-8")).items()] if os.path.exists(p) else []
    o._relic_points = _opt("map_relics.json")
    o._dungeon_points = _opt("map_dungeons.json")
    o._map_img = "data:image/jpeg;base64,AAAA"
    o._map_ready = True                        # 跳过大图加载
    return o


class _E:
    def get_sender_id(self):
        return "q0"

    def get_group_id(self):
        return "g1"


def test_poimap_menu_lists_categories():
    o = _plugin()
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(title=title, desc=k.get("desc", ""))
        return "M"
    o._msg_card = _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_poimap(_E(), []))
    assert "地标" in cap["title"] and "禁猎区" in cap["desc"] and "传送点" in cap["desc"]
    assert "遗物雕像" in cap["desc"] and "地牢入口" in cap["desc"]


def test_poimap_relics_and_dungeons_have_points():
    o = _plugin()
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(cat=data["title"], n=len(data["points"]))
        return "I"
    o._img, o._t = _img, (lambda k: k)
    loop = asyncio.new_event_loop()
    for cat in ("遗物雕像", "地牢入口", "传送点"):
        loop.run_until_complete(o._cmd_poimap(_E(), [cat]))
        assert cap["n"] >= 100, f"{cat} 只有 {cap['n']} 点(数据应已补全)"


def test_poimap_category_markers_on_main():
    o = _plugin()
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(data=data)
        return "I"
    o._img, o._t = _img, (lambda k: k)
    asyncio.new_event_loop().run_until_complete(o._cmd_poimap(_E(), ["传送点"]))
    d = cap["data"]
    assert d["points"] and d["mapimg"]
    for p in d["points"]:                       # 百分比在合理范围、编号连续
        assert -3 <= p["left"] <= 103 and -3 <= p["top"] <= 103 and p["no"] >= 1


def test_poimap_unknown_category():
    o = _plugin()
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(title=title)
        return "M"
    o._msg_card = _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_poimap(_E(), ["不存在类别xyz"]))
    assert "没有这个类别" in cap["title"]


def test_poimap_renders_all_themes():
    o = _plugin()
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(data=data)
        return "I"
    o._img, o._t = _img, (lambda k: k)
    asyncio.new_event_loop().run_until_complete(o._cmd_poimap(_E(), ["遗迹遗址"]))
    d = cap["data"]
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["poimap"]).render(**d)
        assert "遗迹遗址" in html
