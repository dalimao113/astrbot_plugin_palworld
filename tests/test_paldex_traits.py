"""图鉴详情「习性」增强护栏。

- 全部字段来自 paldex DataTable 已有值:种属(genus_category)/遇敌AI(ai_response)/
  掠食者(predator,对应官方 ENABLE_PREDATOR_BOSS_PAL)/夜行(nocturnal),不猜测。
- 未知/不确定含义的字段(biological_grade/noose_trap)不展示,避免误导。
- 三主题详情卡均能渲染习性;英文枚举一律映射中文。
"""
from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


def test_traits_built_from_real_fields():
    o = _plugin()
    # 造一只:好战 + 掠食者 + 夜行 + 四足
    p = dict(next(iter(o._pals)))
    p.update(genus_category="FourLegged", ai_response="Warlike", predator=True, nocturnal=True)
    d = o._pal_card_data(p)
    kv = {t["k"]: t["v"] for t in d["traits"]}
    assert kv["种属"] == "四足兽"
    assert "好战" in kv["遇敌"]
    assert "掠食者" in kv and "作息" in kv         # predator + nocturnal 都进
    # 全中文:习性里不得残留英文枚举
    blob = "".join(t["k"] + t["v"] for t in d["traits"])
    assert not any(c.isascii() and c.isalpha() for c in blob)


def test_traits_absent_when_no_data():
    o = _plugin()
    p = dict(next(iter(o._pals)))
    p.update(genus_category=None, ai_response=None, predator=False, nocturnal=False)
    assert o._pal_card_data(p)["traits"] == []


def test_traits_gender_ratio_only_when_skewed():
    o = _plugin()
    base = dict(next(iter(o._pals)))
    base.update(genus_category=None, ai_response=None, predator=False, nocturnal=False)
    # 50/50 均衡:不展示公母比,避免刷屏
    p50 = dict(base); p50["male_probability"] = 50
    assert all(t["k"] != "公母比" for t in o._pal_card_data(p50)["traits"])
    # 偏公:展示 ♂90% ♀10%
    p90 = dict(base); p90["male_probability"] = 90
    kv = {t["k"]: t["v"] for t in o._pal_card_data(p90)["traits"]}
    assert kv.get("公母比") == "♂90% ♀10%"


def test_traits_render_all_three_themes():
    o = _plugin()
    p = dict(next(iter(o._pals)))
    p.update(genus_category="Dragon", ai_response="Friendly", predator=False, nocturnal=True)
    d = o._pal_card_data(p)
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["paldex"]).render(**d)
        assert "习性" in html and "龙类" in html and "友好" in html
