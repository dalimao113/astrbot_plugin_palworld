"""个人帕鲁战力排行(/帕鲁我的战力)护栏。

- 只统计玩家自己捕捉的帕鲁(队伍+帕鲁箱+自有据点),**排除公会共享据点帕鲁**。
- 按综合战力降序;分页;top3 奖牌。
真实存档验证:195 只、13 页。
"""
import asyncio

import astrbot_plugin_palworld.main as main


class _Ev:
    def get_sender_id(self):
        return "q0"

    def get_group_id(self):
        return "g1"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _plugin(prof):
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._pal_power = lambda pal: int(pal.get("level", 1)) * 100          # 简化战力=等级×100
    o._pal_by_dev = {}
    o._pal_icon = lambda d: ""
    o._last_save_use = 0

    async def _rt(event, a):
        return prof, prof.get("nickname"), None

    o._resolve_target_sp = _rt
    cap = {}

    async def _img(event, tmpl, data, **kw):
        cap["d"] = data
        return "IMG"

    async def _msg(event, *a, **k):
        cap["msg"] = a
        return "MSG"

    o._img, o._t, o._msg_card = _img, (lambda k: k), _msg
    o._cap = cap
    return o


def test_my_power_ranks_own_excludes_shared():
    prof = {"nickname": "阿狸",
            "party": [{"char_id": "A", "level": 50, "nickname": "强将"}],
            "palbox": [{"char_id": "B", "level": 10}, {"char_id": "C", "level": 30}],
            "basecamp": [{"char_id": "D", "level": 99, "shared": True, "iid": "x1"}]}   # 共享 -> 排除
    o = _plugin(prof)
    _run(o._cmd_my_power(_Ev(), []))
    rows = o._cap["d"]["rows"]
    powers = [r["power"] for r in rows]
    assert powers == sorted(powers, reverse=True)                     # 降序
    assert 9900 not in powers                                         # 共享(lv99)不计入个人
    assert rows[0]["power"] == 5000 and rows[0]["medal"] == "🥇"      # 队伍 lv50 居首
    assert o._cap["d"]["title"] == "🏆 阿狸 的战力榜"
    assert "共 3 只" in o._cap["d"]["sub"]


def test_my_power_empty():
    o = _plugin({"nickname": "空", "party": [], "palbox": [], "basecamp": []})
    _run(o._cmd_my_power(_Ev(), []))
    assert "还没有" in o._cap.get("msg", ("",))[1]
