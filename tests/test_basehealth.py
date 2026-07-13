"""据点体检(首选2)护栏。

- 规则来源在数据文件 data/basecamp_rules.json(可追溯 1.0),含 essential 工作适性 + 阈值。
- 聚合工作适性覆盖/缺口、伤病/饥饿/理智低/工作病计数,给建议。只读,不改存档。
真实存档(29 工人)已本机验证。
"""
import asyncio
import json
import os

import astrbot_plugin_palworld.main as main

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_rules_file_traceable():
    with open(os.path.join(_ROOT, "data", "basecamp_rules.json"), encoding="utf-8") as f:
        r = json.load(f)
    assert r["_meta"].get("steam_build_id") and "DataTable" in r["_meta"].get("source", "")
    assert any(w.get("essential") for w in r["work_types"])           # 有关键适性
    assert {"hp_low_pct", "sanity_low"} <= set(r["health_thresholds"])


def _plugin_with_views(views):
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o.state = {"bindings": {"q0": {"userId": "UID_A", "name": "阿狸"}},
               "uid2pid": {"UID_A": "PID_A"}, "group_members": {}}
    o._last_save_use = 0
    o._bc_rules = None

    async def _fetch(**k):
        return {"profiles": {"PID_A": {"player_id": "PID_A",
                                       "basecamp": [{"iid": f"i{i}"} for i in range(len(views))]}}}

    o._fetch_save_data = _fetch
    o._safe_views = lambda fn, pals, tag: views            # 直接喂受控 view,绕过复杂 _basecamp_view
    return o


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _view(works, hp_pct=100, hungry=False, low_san=False, sick=False, stomach=100, working=True):
    return {"works": [{"k": k, "lv": lv} for k, lv in works], "hp_pct": hp_pct, "hungry": hungry,
            "low_san": low_san, "sick": sick, "stomach": stomach, "working": working}


def test_basehealth_detects_gaps_and_health():
    # 只有 手工/采矿 有人;缺 砍伐/采集/搬运(essential)-> gaps
    views = [_view([("手工", 3), ("采矿", 4)]), _view([("采矿", 2)], hungry=True, sick=True)]
    o = _plugin_with_views(views)
    d = _run(o._basecamp_health_data("g1"))
    assert d["workers"] == 2
    assert "砍伐" in d["gaps"] and "搬运" in d["gaps"] and "手工" not in d["gaps"]
    assert d["hungry"] == 1 and d["sick"] == 1
    cov = {c["cn"]: c for c in d["coverage"]}
    assert cov["采矿"]["count"] == 2 and cov["采矿"]["maxlv"] == 4 and not cov["采矿"]["gap"]
    assert any("缺关键工作适性" in a for a in d["advices"])


def test_basehealth_all_good():
    rules = json.load(open(os.path.join(_ROOT, "data", "basecamp_rules.json"), encoding="utf-8"))
    allworks = [(w["cn"], 5) for w in rules["work_types"]]
    o = _plugin_with_views([_view(allworks)])
    d = _run(o._basecamp_health_data("g1"))
    assert not d["gaps"] and d["hungry"] == 0
    assert any("状态良好" in a for a in d["advices"])
