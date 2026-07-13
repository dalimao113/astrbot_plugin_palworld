"""小队进度(首选1)护栏。

- 聚合按群名单(group_members)隔离;已绑定成员的进度自动同步(存档只读),active_quests→中文名"下一步"。
- 手动勾选按群隔离、记录是谁、再勾选取消;管理员可重置。
- 不伪造:读不到进度的成员不计入自动同步,只走手动勾选。
真实存档结构已本机验证(extract_player_progress,不入库)。
"""
import asyncio

import astrbot_plugin_palworld.main as main


class _Ev:
    def __init__(self, q, g="g1"):
        self.q, self.g = q, g

    def get_sender_id(self):
        return self.q

    def get_group_id(self):
        return self.g


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    # 绑定 userId(REST) → 存档 playerId(uid2pid);profiles/progress 以 playerId 为键(与生产一致)
    o.state = {"bindings": {"q0": {"userId": "UID_A", "name": "阿狸"},
                            "q1": {"userId": "UID_B", "name": "小明"}},
               "uid2pid": {"UID_A": "PID_A", "UID_B": "PID_B"},
               "group_members": {}, "squad": {}}
    o._save_state = lambda: None
    o._last_save_use = 0
    profiles = {"PID_A": {"player_id": "PID_A", "nickname": "阿狸"},
                "PID_B": {"player_id": "PID_B", "nickname": "小明"}}   # PID_B 无进度 -> 应被跳过,不伪造
    prog = {"PID_A": {"paldeck": 91, "fasttravel": 55, "tower_bosses": ["GrassBoss", "ForestBoss"],
                      "field_bosses": 22, "dungeon_normal": 1, "dungeon_fixed": 8, "relics": 2,
                      "areas_found": 47, "active_quests": ["Main_CollectKeySpheres", "Hidden_X"]}}

    async def _fetch(**k):
        return {"profiles": profiles, "guilds": [], "progress": prog}

    o._fetch_save_data = _fetch
    cap = {}

    async def _img(event, tmpl, data, **kw):
        cap["data"] = data
        return "IMG"

    async def _msg(event, *a, **k):
        cap["msg"] = (a, k)
        return "MSG"

    o._img, o._t, o._msg_card = _img, (lambda k: k), _msg
    o._cap = cap
    return o


def test_squad_aggregates_bound_members_with_next_step():
    o = _plugin()
    d = _run(o._squad_progress_data("g1"))
    assert d["count"] == 1                       # 只有 AAAA0000 有进度(BBBB0000 无 -> 不计入,不伪造)
    m = d["members"][0]
    assert m["paldeck"] == 91 and m["towers"] == 2 and m["dungeon"] == 9
    assert "收集密钥球" in m["next"]              # active_quests -> 中文名"下一步"
    assert not any("Hidden" in x for x in m["next"])   # 隐藏任务过滤


def test_squad_check_toggle_per_group_records_who():
    o = _plugin()
    _run(o._cmd_squad_check(_Ev("q0"), ["世界树探索"]))
    assert o.state["squad"]["g1"]["checklist"]["世界树探索"] == ["q0"]
    _run(o._cmd_squad_check(_Ev("q1"), ["世界树探索"]))
    assert set(o.state["squad"]["g1"]["checklist"]["世界树探索"]) == {"q0", "q1"}
    _run(o._cmd_squad_check(_Ev("q0"), ["世界树探索"]))   # 再勾一次=取消自己
    assert o.state["squad"]["g1"]["checklist"]["世界树探索"] == ["q1"]
    # 群隔离:g2 不受影响
    _run(o._cmd_squad_check(_Ev("q0", "g2"), ["世界树探索"]))
    assert "g2" in o.state["squad"] and o.state["squad"]["g1"] != o.state["squad"]["g2"]


def test_squad_reset_clears_group_manual_only():
    o = _plugin()
    _run(o._cmd_squad_check(_Ev("q0"), ["目标A"]))
    _run(o._cmd_squad_reset(_Ev("q0"), []))
    assert "g1" not in o.state.get("squad", {})


def test_squad_roster_group_isolated():
    o = _plugin()
    o.state["group_members"] = {"g1": {"q0": 1}}    # 只有 q0 在 g1
    assert o._squad_roster_qq("g1") == ["q0"]
    assert set(o._squad_roster_qq("gX")) == {"q0", "q1"}   # 无记录 -> 回退全部已绑定(私人小队)
