"""种属图鉴(/帕鲁种属)护栏。

- 分类来自 paldex genus_category(已有字段);无参给分类菜单,带种属出网格(真实立绘)。
- 中文/别名(龙/龙类/四足/鱼…)都能解析;未知种属给友好提示。
"""
import asyncio

import astrbot_plugin_palworld.main as main


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


class _E:
    def get_sender_id(self):
        return "q0"

    def get_group_id(self):
        return "g1"


def test_genus_menu_lists_counts():
    o = _plugin()
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(title=title, desc=k.get("desc", ""))
        return "M"
    o._msg_card = _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_genus(_E(), []))
    assert "种属" in cap["title"] and "龙类" in cap["desc"]


def test_genus_grid_by_alias():
    o = _plugin()
    cap = {}

    async def _grid(event, title, emoji, entries, page, base_cmd, query):
        cap.update(title=title, n=len(entries), entries=entries)
        return "G"
    o._render_grid = _grid
    asyncio.new_event_loop().run_until_complete(o._cmd_genus(_E(), ["龙"]))
    assert "龙类" in cap["title"] and cap["n"] > 0
    # 网格条目都确实是龙类
    gmap = o._genus_map()
    assert all(gmap.get(e["ik"]) == "Dragon" for e in cap["entries"])


def test_genus_unknown_friendly():
    o = _plugin()
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(title=title)
        return "M"
    o._msg_card = _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_genus(_E(), ["不存在的种属xyz"]))
    assert "没有这个种属" in cap["title"]
