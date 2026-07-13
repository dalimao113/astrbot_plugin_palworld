"""养成(首选3)护栏。

- 浓缩星级 = 存档 Rank-1(0~4★);帕鲁之魂/觉醒/个体值/词条/技能取自存档只读。
- **不虚报**:浓缩/魂精确材料数游戏未从 DataTable 提取,建议里明确说明,不编造数字。
- 觉醒材料按帕鲁主属性引用 /帕鲁觉醒 的 9 系晶石(真实数据)。
真实存档验证:青天如墨的鬼刃武士 浓缩 3/4★、词条 稀有/灵活、技能 真空刃等。
"""
import astrbot_plugin_palworld.main as main


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


def test_growth_condense_stars_from_rank():
    o = _plugin()
    p = o._pal_by_name.get("皮皮鸡") or list(o._pal_by_name.values())[0]
    pal = {"char_id": p["pal_dev_name"], "level": 30, "rank": 4,        # rank4 -> 3★
           "iv_hp": 70, "iv_atk": 80, "iv_def": 60, "awakened": False,
           "souls": {"最大HP": 3}, "passives": [], "equip_waza": []}
    d = o._growth_data(pal, p, 1)
    assert d["condense"] == 3 and d["condense_max"] == 4
    assert d["souls"] == [{"k": "最大HP", "lv": 3}]
    assert d["iv_atk"] == 80
    # 不虚报:浓缩建议里说明未提取精确数量
    assert any("未从 DataTable 提取" in n for n in d["notes"])


def test_growth_awakening_gem_by_element():
    o = _plugin()
    fire = next((p for p in o._pals if "火属性" in (p.get("elements") or [])), None)
    if not fire:
        return
    pal = {"char_id": fire["pal_dev_name"], "rank": 1, "awakened": False,
           "souls": {}, "passives": [], "equip_waza": []}
    d = o._growth_data(pal, fire, 1)
    assert d["awakened"] is False
    assert "火" in d["gem"] or "觉醒晶石" in d["gem"]          # 按主属性给觉醒晶石
    assert any("未觉醒" in n for n in d["notes"])


def test_growth_awakened_no_gem_prompt():
    o = _plugin()
    p = list(o._pal_by_name.values())[0]
    pal = {"char_id": p["pal_dev_name"], "rank": 5, "awakened": True,
           "souls": {}, "passives": [], "equip_waza": []}
    d = o._growth_data(pal, p, 1)
    assert d["condense"] == 4 and d["awakened"] is True
    assert any("已觉醒" in n for n in d["notes"])
