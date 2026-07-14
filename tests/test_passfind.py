"""词条查帕鲁(/帕鲁词条查 <词条名>)护栏。

- 从自己存档(队伍+帕鲁箱)里找带某词条的帕鲁,一键定位;箱编号与 /帕鲁箱 一致(闪光/头目/高等级在前)。
- 词条名模糊匹配;带的具体档位(rank)用游戏箭头图标+品阶色显示;没有则友好提示。
"""
import asyncio

from jinja2 import ChainableUndefined, Environment

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.templates import STYLES


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


class _E:
    def get_sender_id(self):
        return "q0"

    def get_group_id(self):
        return "g1"


def _run(o, args):
    cap = {}

    async def _img(event, tmpl, data, **k):
        cap.update(kind="img", data=data)
        return "I"

    async def _msg(event, icon, title, **k):
        cap.update(kind="msg", title=title, desc=k.get("desc", ""))
        return "M"
    o._img, o._t, o._msg_card = _img, (lambda k: k), _msg
    asyncio.new_event_loop().run_until_complete(o._cmd_passive_find(_E(), args))
    return cap


def _stub_sp(o, party, palbox):
    async def _rt(event, a):
        return {"party": party, "palbox": palbox}, "阿狸", None
    o._resolve_target_sp = _rt


def test_passfind_lists_owning_pals():
    o = _plugin()
    # 取一个真实词条 id + 名
    pid = next(k for k, v in o._passives.items() if v.get("name"))
    pname = o._passives[pid]["name"]
    dev = list(o._pal_by_name.values())[0]["pal_dev_name"]
    party = [{"char_id": dev, "level": 40, "nickname": "带的", "passives": [pid], "lucky": False, "is_alpha": False}]
    palbox = [{"char_id": dev, "level": 10, "passives": ["无关词条ID"], "lucky": False, "is_alpha": False},
              {"char_id": dev, "level": 50, "nickname": "箱里也带", "passives": [pid], "lucky": True, "is_alpha": False}]
    o._palbox_sorted = staticmethod(main.PalworldPlugin._palbox_sorted).__func__
    _stub_sp(o, party, palbox)
    cap = _run(o, [pname])
    assert cap["kind"] == "img"
    d = cap["data"]
    assert d["total"] == 2                       # 队伍1 + 箱1(不含无关那只)
    locs = {r["loc"] for r in d["rows"]}
    assert "队伍" in locs and any(l.startswith("箱 #") for l in locs)
    # 匹配词条带 rank 图标键 + 结果编号连续
    assert all(r["matched"] and r["matched"][0]["rank_key"].startswith("rank_") for r in d["rows"])
    assert [r["no"] for r in d["rows"]] == [1, 2]


def test_passfind_pick_shows_detail():
    o = _plugin()
    pid = next(k for k, v in o._passives.items() if v.get("name"))
    pname = o._passives[pid]["name"]
    dev = list(o._pal_by_name.values())[0]["pal_dev_name"]
    party = [{"char_id": dev, "level": 40, "nickname": "第一只", "passives": [pid],
              "iv_hp": 5, "iv_atk": 5, "iv_def": 5, "rank": 1, "equip_waza": [], "lucky": False, "is_alpha": False}]
    palbox = [{"char_id": dev, "level": 50, "nickname": "第二只", "passives": [pid],
               "iv_hp": 5, "iv_atk": 5, "iv_def": 5, "rank": 1, "equip_waza": [], "lucky": False, "is_alpha": False}]
    o._palbox_sorted = staticmethod(main.PalworldPlugin._palbox_sorted).__func__
    _stub_sp(o, party, palbox)
    cap = _run(o, [pname, "2"])          # 看第 2 只详情
    assert cap["kind"] == "img"
    assert "第 2 只" in cap["data"]["title"] and cap["data"]["pals"]   # 走队伍详情卡


def test_passfind_none_owned():
    o = _plugin()
    pid = next(k for k, v in o._passives.items() if v.get("name"))
    pname = o._passives[pid]["name"]
    dev = list(o._pal_by_name.values())[0]["pal_dev_name"]
    o._palbox_sorted = staticmethod(main.PalworldPlugin._palbox_sorted).__func__
    _stub_sp(o, [{"char_id": dev, "level": 5, "passives": ["别的"], "lucky": False, "is_alpha": False}], [])
    cap = _run(o, [pname])
    assert cap["kind"] == "msg" and "没有带" in cap["title"]


def test_passfind_unknown_passive():
    o = _plugin()
    _stub_sp(o, [], [])
    cap = _run(o, ["根本不存在的词条xyz"])
    assert cap["kind"] == "msg" and "没有这个词条" in cap["title"]


def test_passfind_renders_all_themes():
    o = _plugin()
    d = {"query": "提升攻击", "owner": "阿狸", "total": 1,
         "matched_names": ["提升攻击Lv3"],
         "rows": [{"no": 1, "name": "火绒狐", "icon": "", "elements": ["火属性"], "nickname": "小火",
                   "level": 45, "loc": "箱 #2", "lucky": True, "alpha": False,
                   "matched": [{"name": "提升攻击Lv3", "rank_key": "rank_up3", "hex": "#ffce4a"}],
                   "total_passives": 4}]}
    env = Environment(autoescape=False, undefined=ChainableUndefined)
    for st in ("fantasy", "pixel", "ingame"):
        html = env.from_string(STYLES[st]["passfind"]).render(**d)
        assert "提升攻击" in html and "箱 #2" in html and "火绒狐" in html
