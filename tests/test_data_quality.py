"""数据质量护栏(增量1:1.0 数据准确性)。

- 统一文本清洗 clean_text / is_missing_text 行为。
- 图鉴/物品数据不得再出现:zh-hans text 占位、未解析 <itemName>、零宽字符、名称首尾空格。
- 中文名索引同名时优先可收集本体(叶泥泥),去空格后可查(黑月女王)。
"""
import json
import os

from astrbot_plugin_palworld.utils.text import clean_text, is_missing_text

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ZW = "​‌‍⁠﻿"


def _read(name):
    return open(os.path.join(_ROOT, "data", name), encoding="utf-8").read()


def _load(name):
    return json.loads(_read(name))


# ---------------- clean_text ----------------
def test_clean_text_placeholders_to_empty():
    assert clean_text("zh-hans text") == ""
    assert clean_text("zh_Hans_Text") == ""
    assert clean_text("None") == ""
    assert is_missing_text("zh-hans text") and is_missing_text("None") and is_missing_text("")
    assert not is_missing_text("正常文本")


def test_clean_text_strips_tags_zw_control_keeps_emoji_and_newline():
    assert clean_text("威力<b>强</b>攻击") == "威力强攻击"
    assert clean_text("<itemName id=|SkillUnlock_X|/>解锁") == "解锁"          # 无解析器 -> 去标签
    assert clean_text("a\r\nb\rc") == "a\nb\nc"                              # 换行统一
    assert clean_text("含零宽​字符‌x") == "含零宽字符x"                       # 零宽剔除
    assert clean_text("火焰🔥龙🐉") == "火焰🔥龙🐉"                            # Emoji 保留


def test_clean_text_resolver():
    assert clean_text("<itemName id=|Wood|/>", lambda i: "木材" if i == "Wood" else "") == "木材"


# ---------------- 数据文件无残留 ----------------
def test_data_files_free_of_placeholders_and_junk():
    raw = _read("paldex.json") + _read("items.json")
    assert "zh-hans text" not in raw, "数据仍含 zh-hans text 占位"
    assert "<itemName" not in raw, "数据仍含未解析 <itemName>"
    for z in _ZW:
        assert z not in raw, f"数据仍含零宽字符 U+{ord(z):04X}"


def test_pal_names_no_surrounding_space():
    bad = [p["pal_name"] for p in _load("paldex.json")
           if isinstance(p.get("pal_name"), str) and p["pal_name"] != p["pal_name"].strip()]
    assert not bad, f"pal_name 首尾空格: {bad}"


# ---------------- 名称索引:同名优先可收集本体 ----------------
def test_name_index_prefers_collectible(monkeypatch):
    import astrbot_plugin_palworld.main as main
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    yy = o._pal_by_name.get("叶泥泥")
    assert yy is not None and yy.get("is_collectible"), "叶泥泥应索引到可收集本体(PlantSlime)"
    assert yy.get("pal_dev_name") == "PlantSlime"
    # 去空格后可查
    assert o._pal_by_name.get("黑月女王") is not None, "黑月女王(去尾空格)应可查"
