"""输错指令智能纠错护栏。

- 未知子命令不再甩全量帮助:是帕鲁/物品名→引导对应查询;拼错→按编辑距离猜最接近指令(只提示不代执行)。
- 完全没头绪才回退帮助卡。
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


def _run(o, sub):
    cap = {}

    async def _msg(event, icon, title, **k):
        cap.update(kind="msg", title=title, desc=k.get("desc", ""))
        return "M"

    async def _help(event):
        cap.update(kind="help")
        return "H"
    o._msg_card, o._cmd_help = _msg, _help
    asyncio.new_event_loop().run_until_complete(o._unknown_card(_E(), sub))
    return cap


def test_typo_suggests_closest_command():
    o = _plugin()
    cap = _run(o, "战力排行v")           # 接近 战力榜
    assert cap["kind"] == "msg" and "你是不是想找" in cap["desc"]
    assert "战力" in cap["desc"]


def test_pal_name_suggests_paldex():
    o = _plugin()
    name = next(iter(o._pal_by_name))    # 真实帕鲁名
    cap = _run(o, name)
    assert cap["kind"] == "msg" and f"/帕鲁图鉴 {name}" in cap["desc"]


def test_gibberish_falls_back_to_help():
    o = _plugin()
    cap = _run(o, "zzzxqwv不存在的东西")
    assert cap["kind"] == "help"


def test_suggest_commands_ranking():
    o = _plugin()
    # "养城" 拼错 养成
    sug = o._suggest_commands("养城")
    assert "养成" in sug
