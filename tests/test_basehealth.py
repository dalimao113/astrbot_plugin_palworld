"""据点体检(首选2)+ 多据点选择护栏。

- 规则来源在数据文件 data/basecamp_rules.json(可追溯 1.0),含 essential 工作适性 + 阈值。
- _base_health_metrics:聚合工作适性覆盖/缺口、伤病/饥饿/理智低/工作病计数,给建议。只读,不改存档。
- _group_bases:按 base_cid 分组、稳定据点号(一个公会最多 4 个据点)。
真实存档验证:2 据点(15+14 工人)。
"""
import json
import os

import astrbot_plugin_palworld.main as main

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bare():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._bc_rules = None
    return o


def _view(works, hp_pct=100, hungry=False, low_san=False, sick=False, stomach=100, working=True, base_cid="B1"):
    return {"works": [{"k": k, "lv": lv} for k, lv in works], "hp_pct": hp_pct, "hungry": hungry,
            "low_san": low_san, "sick": sick, "stomach": stomach, "working": working, "base_cid": base_cid}


def test_rules_file_traceable():
    with open(os.path.join(_ROOT, "data", "basecamp_rules.json"), encoding="utf-8") as f:
        r = json.load(f)
    assert r["_meta"].get("steam_build_id") and "DataTable" in r["_meta"].get("source", "")
    assert any(w.get("essential") for w in r["work_types"])
    assert {"hp_low_pct", "sanity_low"} <= set(r["health_thresholds"])


def test_metrics_detects_gaps_and_health():
    views = [_view([("手工", 3), ("采矿", 4)]), _view([("采矿", 2)], hungry=True, sick=True)]
    d = _bare()._base_health_metrics(views)
    assert d["workers"] == 2
    assert "砍伐" in d["gaps"] and "搬运" in d["gaps"] and "手工" not in d["gaps"]
    assert d["hungry"] == 1 and d["sick"] == 1
    cov = {c["cn"]: c for c in d["coverage"]}
    assert cov["采矿"]["count"] == 2 and cov["采矿"]["maxlv"] == 4 and not cov["采矿"]["gap"]
    assert any("缺关键工作适性" in a for a in d["advices"])


def test_metrics_all_good():
    rules = json.load(open(os.path.join(_ROOT, "data", "basecamp_rules.json"), encoding="utf-8"))
    allworks = [(w["cn"], 5) for w in rules["work_types"]]
    d = _bare()._base_health_metrics([_view(allworks)])
    assert not d["gaps"] and d["hungry"] == 0 and any("状态良好" in a for a in d["advices"])


def test_group_bases_by_base_cid_stable_numbering():
    o = _bare()
    views = [_view([("手工", 1)], base_cid="Z"), _view([("采矿", 1)], base_cid="A"),
             _view([("砍伐", 1)], base_cid="A")]
    bases = o._group_bases(views)
    assert [b["no"] for b in bases] == [1, 2]
    assert bases[0]["cid"] == "A" and len(bases[0]["views"]) == 2    # cid 排序 -> A=据点1
    assert bases[1]["cid"] == "Z" and len(bases[1]["views"]) == 1
