"""存档解析回归测试：确保 1.0 SetProperty 兼容 patch 不被意外移除、关键解析函数存在。

不含真实存档（玩家隐私 + 体积），只验证解析器的兼容机制与接口完整性。
需 palworld_save_tools（容器内有；本地缺失时自动跳过）。
"""
import importlib
import pytest

pytest.importorskip("palworld_save_tools")


def test_palsave_public_functions():
    m = importlib.import_module("astrbot_plugin_palworld.palwork.palsave")
    for fn in ("load_sav", "extract_profiles", "extract_guilds",
               "decompress_sav", "_parse_item_slot", "_pal_brief"):
        assert hasattr(m, fn), f"palsave 缺少关键函数 {fn}"


def test_setproperty_patch_registered():
    """1.0 存档 worldSaveData 顶层的 SetProperty(InLockerCharacterInstanceIDArray)
    需被跳过器识别，否则整份存档解析崩溃、玩家信息全查不到。"""
    importlib.import_module("astrbot_plugin_palworld.palwork.palsave")  # 触发幂等 patch
    from palworld_save_tools import archive
    assert getattr(archive.FArchiveReader, "_pal_setprop_patched", False), \
        "SetProperty 兼容 patch 未注册（1.0 存档会解析崩溃）"


def test_setproperty_handler_skips_by_size():
    """SetProperty 处理器应读掉 inner 类型名+可选 GUID 后，用 size 整块跳过、对齐到下一属性。"""
    importlib.import_module("astrbot_plugin_palworld.palwork.palsave")
    from palworld_save_tools import archive

    class FakeReader:
        def __init__(self):
            self.skipped = 0
            self._props = archive.FArchiveReader.property  # patched

        def fstring(self):
            return "StructProperty"

        def optional_guid(self):
            return None

        def skip(self, n):
            self.skipped += n

    r = FakeReader()
    out = archive.FArchiveReader.property(r, "SetProperty", 4826, ".x")
    assert r.skipped == 4826, "SetProperty 应按 size 跳过整块"
    assert out.get("skipped_set") is True
