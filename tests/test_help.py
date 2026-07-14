"""帮助卡:数据驱动分类 + 关键词搜索。

- 帮助卡从命令注册表生成,永远与实际指令同步(含新指令);按类别(服务器/排行/图鉴/玩家/公会/管理)分区。
- /帕鲁帮助 <关键词> 只列名字/别名/说明含关键词的指令;搜不到给纠错提示。
"""
import asyncio

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


def test_help_sections_categorized_and_synced():
    o = _plugin()
    secs = o._help_sections()
    titles = [s["title"] for s in secs]
    assert any("图鉴" in t for t in titles) and any("管理" in t for t in titles)
    all_cmds = {c["cmd"] for s in secs for c in s["cmds"]}
    # 新指令必须在(数据驱动 → 自动同步)
    for c in ("/帕鲁地图收集", "/帕鲁用途", "/帕鲁种属", "/帕鲁牧场"):
        assert c in all_cmds, f"{c} 不在帮助里(应自动同步)"


def test_help_search_filters():
    o = _plugin()
    hit = o._help_sections("地图")
    cmds = [c["cmd"] for s in hit for c in s["cmds"]]
    assert "/帕鲁地图收集" in cmds
    assert "/帕鲁配种" not in cmds        # 不相关的不出现


def test_help_renders_all_themes_with_new_cmds():
    o = _plugin()
    secs = o._help_sections()
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["help"]).render(sections=secs)
        assert "/帕鲁用途" in html and "/帕鲁地图收集" in html


def test_help_search_miss_suggests():
    o = _plugin()
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(title=title, desc=k.get("desc", ""))
        return "M"
    o._msg_card = _msg
    o._suggest_commands = lambda q, n=3: ["配种"]

    class E:
        def get_sender_id(self):
            return "q"

        def get_group_id(self):
            return "g"
    asyncio.new_event_loop().run_until_complete(o._cmd_help(E(), ["完全不存在xyz"]))
    assert "没搜到" in cap["title"]
