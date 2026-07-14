"""公会卡增强(每成员等级/帕鲁数 + 帕鲁合计)护栏。

- 每成员 等级/帕鲁数 = 跨 CharacterSaveParameterMap 按 uid(去连字符大写)关联档案 party+palbox。
- 真实 1.0 存档已验证 12/12 成员对齐(uid 归一化后)。
- 无档案的成员(没上线/无 Player sav)安全降级:level=None,不显示,不报错。
"""
import asyncio

import astrbot_plugin_palworld.main as main


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o.state = {"bindings": {"q0": {"userId": "steam_x", "name": "大狸猫"}}, "uid2pid": {}}
    o._last_save_use = 0
    o._fresh_ttl = lambda: 0
    o._is_admin = lambda qq: False
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
    asyncio.new_event_loop().run_until_complete(o._cmd_guild(_E(), args))
    return cap.get("data")


def test_guild_member_level_and_pal_count():
    o = _plugin()
    admin = "475FC982000000000000000000000000"
    guild = {"guild_name": "Unnamed Guild", "admin_uid": admin,
             "members": [{"name": "大狸猫", "uid": admin},
                         {"name": "花枝鼠", "uid": "CC11ECDF000000000000000000000000"},
                         {"name": "没上线的", "uid": "DEADBEEF000000000000000000000000"}]}

    async def _fg(*a, **k):
        return [guild]

    async def _fp(*a, **k):   # 档案 uid 用连字符小写(存档原样),须归一化才对齐
        return {
            "475fc982-0000-0000-0000-000000000000": {"level": 45, "party": [1] * 5, "palbox": [1] * 182},
            "cc11ecdf-0000-0000-0000-000000000000": {"level": 53, "party": [1] * 5, "palbox": [1] * 190},
        }
    o._fetch_guilds, o._fetch_save_profiles = _fg, _fp
    d = _run(o, [])
    by = {m["name"]: m for m in d["members"]}
    assert by["大狸猫"]["level"] == 45 and by["大狸猫"]["pals"] == 187
    assert by["花枝鼠"]["level"] == 53 and by["花枝鼠"]["pals"] == 195
    assert by["没上线的"]["level"] is None          # 无档案安全降级
    assert d["guild_pals"] == 187 + 195             # 帕鲁合计(无档案成员计 0)
