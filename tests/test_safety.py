"""小队安全护栏(P0):绑定模式 + 广播白名单。

- bind_mode=open(默认):任何人自绑未占用角色(兼容现有私人小队)。
- bind_mode=admin_confirm:非受信用户挂起待批,管理员/trusted_qq 直接绑;批准后落库。
- broadcast_whitelist_only:只向 broadcast_groups 播报,空则不播报,绝不回退自动登记群;自动登记被禁。
"""
import asyncio

import astrbot_plugin_palworld.main as main


def _plugin(config):
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o.state = {"bindings": {}, "bind_pending": {}, "groups": [],
               "online": {"UID1": {"name": "阿狸", "level": 10}}, "totals": {}}
    o.config = config
    o._save_state = lambda: None
    cap = {}

    async def _msg(event, icon, title, **k):
        cap["title"] = title
        return "MSG"

    o._msg_card = _msg
    o._cap = cap
    return o


class _Ev:
    def __init__(self, q):
        self.q = q

    def get_sender_id(self):
        return self.q

    def get_group_id(self):
        return "g"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_bind_open_binds_directly():
    o = _plugin({"bind_mode": "open", "admin_qq": ["999"], "trusted_qq": []})
    _run(o._cmd_bind(_Ev("100"), ["阿狸"]))
    assert o.state["bindings"].get("100", {}).get("userId") == "UID1"


def test_bind_admin_confirm_pends_then_approves():
    o = _plugin({"bind_mode": "admin_confirm", "admin_qq": ["999"], "trusted_qq": []})
    _run(o._cmd_bind(_Ev("100"), ["阿狸"]))
    assert "100" in o.state["bind_pending"] and o.state["bindings"] == {}   # 挂起,未绑
    _run(o._cmd_bind_approve(_Ev("999"), ["100"]))
    assert o.state["bindings"].get("100", {}).get("userId") == "UID1"
    assert "100" not in o.state["bind_pending"]


def test_bind_trusted_bypasses_confirm():
    o = _plugin({"bind_mode": "admin_confirm", "admin_qq": ["999"], "trusted_qq": ["200"]})
    _run(o._cmd_bind(_Ev("200"), ["阿狸"]))
    assert o.state["bindings"].get("200", {}).get("userId") == "UID1"   # trusted 直接绑


def test_bind_reject_clears_pending():
    o = _plugin({"bind_mode": "admin_confirm", "admin_qq": ["999"], "trusted_qq": []})
    _run(o._cmd_bind(_Ev("100"), ["阿狸"]))
    _run(o._cmd_bind_reject(_Ev("999"), ["100"]))
    assert "100" not in o.state["bind_pending"] and o.state["bindings"] == {}


def test_broadcast_whitelist_only():
    o = _plugin({"broadcast_whitelist_only": True, "broadcast_groups": ["allow1"]})
    o.state["groups"] = ["auto2", "auto3"]
    assert o._broadcast_targets() == ["allow1"]              # 只白名单
    o.config["broadcast_groups"] = []
    assert o._broadcast_targets() == []                      # 空白名单 -> 不播报(不回退自动群)
    o._register_group("newg")
    assert "newg" not in o.state["groups"]                   # 自动登记被禁


def test_broadcast_default_falls_back_to_auto():
    o = _plugin({"broadcast_whitelist_only": False, "broadcast_groups": []})
    o.state["groups"] = ["auto2", "auto3"]
    assert o._broadcast_targets() == ["auto2", "auto3"]
