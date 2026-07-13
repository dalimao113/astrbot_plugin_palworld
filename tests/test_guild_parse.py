"""1.0 公会 RawData 解析回归(阶段E:#12)。

1.0 改了 base_camp 段字节格式(官方 palworld_save_tools 0.24.0 在此崩)。本测试用**脱敏合成**
的公会字节(假 UID/假名字,非真实玩家数据)验证 _parse_guild_1_0:
- 头部解析到 base_camp_level 后,能扫出玩家记录(uid16+last8+name)与公会名。
- 会长(admin_uid)= group_name 字段(owner PlayerUId),与队长成员对应。
- 中文(utf-16)名字与 ASCII(utf-8)名字都能解出。
需 palworld_save_tools(容器内有;本地缺失自动跳过)。真实存档结构已本机验证(不入库)。
"""
import struct

import pytest

pytest.importorskip("palworld_save_tools")
import importlib

palsave = importlib.import_module("astrbot_plugin_palworld.palwork.palsave")


def _uid(u32):
    return struct.pack("<I", u32) + b"\x00" * 12      # Palworld PlayerUId:4 非0 + 12 零


def _fstr(s):
    if any(ord(c) > 127 for c in s):
        d = s.encode("utf-16-le") + b"\x00\x00"
        return struct.pack("<i", -(len(s) + 1)) + d
    d = s.encode("utf-8") + b"\x00"
    return struct.pack("<i", len(d)) + d


def _player(u32, last, name):
    return _uid(u32) + struct.pack("<q", last) + _fstr(name)


def _synth_guild():
    """合成一个 1.0 公会 RawData(脱敏):会长阿狸(AABBCCDD)+ 成员B(11223344),公会名『测试公会』。"""
    b = b""
    b += _uid(0xAABBCCDD)                                  # group_id
    b += _fstr("AABBCCDD000000000000000000000000")        # group_name = 会长 UID hex
    b += struct.pack("<i", 0)                              # individual_character_handle_ids count
    b += b"\x00"                                           # org_type
    b += struct.pack("<i", 0)                              # base_ids count
    b += struct.pack("<i", 1)                              # base_camp_level
    b += bytes(range(1, 17))                               # base_camp_points(格式变了,填充16字节)
    b += _fstr("测试公会")                                   # guild_name(自定义名,utf-16)
    b += _player(0xAABBCCDD, 638000000000000000, "会长阿狸")
    b += _player(0x11223344, 637000000000000000, "MemberB")
    return b


def test_parse_guild_1_0_names_uids_admin():
    g = palsave._parse_guild_1_0(_synth_guild())
    assert g is not None, "1.0 公会应解析成功(非 None)"
    assert g["guild_name"] == "测试公会"
    names = [m["name"] for m in g["members"]]
    assert names == ["会长阿狸", "MemberB"], f"成员名(含中文)应解出: {names}"
    # admin = owner UID,且与队长成员 uid 对应
    assert g["admin_uid"] == "AABBCCDD000000000000000000000000"
    leader = next(m for m in g["members"] if m["uid"] == g["admin_uid"])
    assert leader["name"] == "会长阿狸"
    # last_online 解出
    assert g["members"][0]["last_online"] == 638000000000000000


def test_guild_display_name_prefers_custom_over_default():
    import astrbot_plugin_palworld.main as main
    f = main.PalworldPlugin._guild_display_name
    assert f({"guild_name": "测试公会"}, "阿狸") == "测试公会"
    assert f({"guild_name": "Unnamed Guild"}, "阿狸") == "「阿狸」的公会"   # 游戏默认名回退
    assert f({"guild_name": ""}, "阿狸") == "「阿狸」的公会"
