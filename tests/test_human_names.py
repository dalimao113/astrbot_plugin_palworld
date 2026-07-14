"""帕鲁箱里抓到的人类 NPC 显示中文名(而非英文 char_id)。

- 存档里可抓人类(盗猎者/士兵/商人等),不在图鉴 → 之前显示英文名 + 无图。
- 先查 human_names 名表(通缉犯真名),再按类型兜底(Hunter→盗猎者…),boss 兜底头目;人类标 is_human。
- pal 变种前后缀(BOSS_/_otomo/_Fire)容错回退到本体图鉴。
"""
import astrbot_plugin_palworld.main as main


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


def test_human_names_loaded():
    o = _plugin()
    assert o._human_names and len(o._human_names) > 50


def test_named_wanted_criminal():
    o = _plugin()
    assert o._human_name("Hunter_Rifle")          # 名表命中(通缉犯真名)
    assert "英文" not in (o._human_name("Hunter_Rifle") or "")


def test_type_fallback():
    o = _plugin()
    assert o._human_name("SalesPerson_Wander") == "流浪商人"
    assert o._human_name("Female_Soldier999") == "士兵"
    assert o._human_name("YakushimaBoss001") == "头目"
    assert o._human_name("SheepBall") is None     # 真帕鲁不是人类


def test_pal_view_human_gets_cn_name():
    o = _plugin()
    v = o._pal_view({"char_id": "Hunter_Rifle", "level": 30, "passives": [], "equip_waza": []})
    assert v["is_human"] and v["name"] and v["name"] != "Hunter_Rifle"


def test_variant_suffix_resolves_to_paldex():
    o = _plugin()
    dev = list(o._pal_by_name.values())[0]["pal_dev_name"]
    v = o._pal_view({"char_id": f"BOSS_{dev}", "level": 30, "passives": [], "equip_waza": []})
    assert not v["is_human"] and v["name"] != f"BOSS_{dev}"   # 回退到本体图鉴名


def test_human_icon_from_game_asset():
    o = _plugin()
    # 具名人类应取到游戏头像(已提取到 data/images)
    for cid in ("Hunter_Rifle", "Believer_CrossBow", "GrassBoss", "Female_Soldier03", "SalesPerson_Wander", "Male_Soldier"):
        assert o._human_icon(cid), f"{cid} 应有游戏人物头像"


def test_pal_view_human_has_icon():
    o = _plugin()
    v = o._pal_view({"char_id": "Hunter_Rifle", "level": 30, "passives": [], "equip_waza": []})
    assert v["is_human"] and v["icon"] and v["icon"].startswith("data:image")
