"""命令注册表驱动的 _dispatch 路由行为（需 astrbot stub）。"""
import asyncio

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.commands import router

P = main.PalworldPlugin


class Ev:
    def get_sender_id(self):
        return "1"


def _mk(admin=False):
    o = P.__new__(P)
    log = []
    for name in {s.handler for s in router.COMMANDS} | {"_cmd_help", "_no_perm_card"}:
        async def f(*a, _n=name, **k):
            log.append((_n, a[1:]))
            return _n
        object.__setattr__(o, name, f)
    object.__setattr__(o, "_is_admin", lambda q: admin)
    object.__setattr__(o, "_pass_cooldown", lambda e: True)
    return o, log


def _run(o, sub, args=None):
    async def go():
        return [r async for r in o._dispatch(Ev(), sub, args or [])]
    return asyncio.run(go())


def test_query_route_no_args():
    o, log = _mk()
    _run(o, "状态")
    assert log == [("_cmd_status", ())]


def test_query_route_with_args():
    o, log = _mk()
    _run(o, "图鉴", ["皮皮鸡"])
    assert log == [("_cmd_paldex", (["皮皮鸡"],))]


def test_boss_extra_category():
    o, log = _mk()
    _run(o, "塔主", ["x"])
    assert log == [("_cmd_boss", (["x"], "塔主"))]


def test_unknown_falls_to_help():
    o, log = _mk()
    _run(o, "乱码不存在xyz")
    assert log == [("_cmd_help", ())]


def test_admin_denied_for_non_admin():
    o, log = _mk(admin=False)
    _run(o, "关服", ["x"])
    assert log[0][0] == "_no_perm_card"


def test_admin_allowed_for_admin():
    o, log = _mk(admin=True)
    _run(o, "关服", ["x"])
    assert log[0] == ("_cmd_shutdown", (["x"],))


def test_english_alias_routes_same():
    o, log = _mk()
    _run(o, "status")
    assert log == [("_cmd_status", ())]
