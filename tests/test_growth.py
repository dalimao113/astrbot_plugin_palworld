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


def test_growth_multi_same_species_select():
    """同种多只:不带序号列出候选(msg);带有效序号出养成卡(img)。序号稳定(浓缩>等级>iid)。"""
    import asyncio
    o = _plugin()
    p = list(o._pal_by_name.values())[0]
    dev = p["pal_dev_name"]
    prof = {"nickname": "阿狸", "party": [], "basecamp": [],
            "palbox": [{"char_id": dev, "level": 20, "rank": 1, "iid": "b", "iv_hp": 5, "iv_atk": 5, "iv_def": 5,
                        "souls": {}, "passives": [], "equip_waza": []},
                       {"char_id": dev, "level": 40, "rank": 3, "iid": "a", "iv_hp": 9, "iv_atk": 9, "iv_def": 9,
                        "souls": {}, "passives": [], "equip_waza": []}]}

    async def _rt(event, a):
        return prof, "阿狸", None

    o._resolve_target_sp = _rt
    cap = {}

    async def _img(event, tmpl, data, **kw):
        cap["kind"] = ("img", data)
        return "I"

    async def _msg(event, icon, title, **k):
        cap["kind"] = ("msg", title, k.get("desc", ""))
        return "M"

    o._img, o._t, o._msg_card = _img, (lambda k: k), _msg

    class E:
        def get_sender_id(self):
            return "q0"

        def get_group_id(self):
            return "g1"

    def run(a):
        asyncio.new_event_loop().run_until_complete(o._cmd_growth(E(), a))
        return cap["kind"]

    k = run([p["pal_name"]])                       # 无序号 -> 列表
    assert k[0] == "msg" and "2 只" in k[1] and "1." in k[2] and "2." in k[2]
    k = run([p["pal_name"], "1"])                  # 序号1 -> 养成卡,取排序后第1(rank3那只)
    assert k[0] == "img" and k[1]["pick"] == 1 and k[1]["condense"] == 2   # rank3 -> 2★
