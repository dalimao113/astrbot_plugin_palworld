"""按属性列帕鲁(/帕鲁属性 <系>)护栏——与 /帕鲁属性克制 同处理器,按参数分流。

- 无参 / "克制" → 克制图(img element);属性名(火/火系/火属性/fire)→ 该属性帕鲁网格。
- 未知属性给友好提示,不误当克制图。网格条目确实都属于该属性。
"""
import asyncio

import astrbot_plugin_palworld.main as main


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    o._elements = o._elements or {"火属性": {}}   # 克制数据存在即可
    return o


class _E:
    def get_sender_id(self):
        return "q0"

    def get_group_id(self):
        return "g1"


def test_element_noarg_shows_chart():
    o = _plugin()
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(tmpl=tmpl)
        return "I"
    o._img, o._t, o._element_data = _img, (lambda k: k), (lambda: {"x": 1})
    asyncio.new_event_loop().run_until_complete(o._cmd_element(_E(), []))
    assert cap["tmpl"] == "element"          # 克制图


def test_element_by_name_grid():
    o = _plugin()
    cap = {}

    async def _grid(event, title, emoji, entries, page, base_cmd, query):
        cap.update(title=title, entries=entries)
        return "G"
    o._render_grid = _grid
    for alias in ("火", "火系", "火属性", "fire"):
        cap.clear()
        asyncio.new_event_loop().run_until_complete(o._cmd_element(_E(), [alias]))
        assert cap["title"] == "火属性帕鲁" and cap["entries"]
    emap = o._elem_map()
    assert all("火属性" in emap.get(e["ik"], []) for e in cap["entries"])


def test_element_unknown_hint():
    o = _plugin()
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(title=title)
        return "M"
    o._msg_card = _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_element(_E(), ["不存在的系xyz"]))
    assert "没有这个属性" in cap["title"]
