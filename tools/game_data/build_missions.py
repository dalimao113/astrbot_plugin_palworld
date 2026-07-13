#!/usr/bin/env python3
"""重建 missions.json(可复现,阶段C)。源:导出的 DataTable + BP CDO + zh-Hans 本地化。

修正问题 #7:
- **ID 主键**:以 quest dev id 为主键。
- **区分 active / _Old**:`_Old`(1.0 已废弃/被替换)不进 active 列表;若无 active 替代(如
  `Main_BuildWorkBench` 只有 `_Old`)则该任务在 1.0 不存在,任何指向它的 next 视为悬挂。
- **next → 本地化名**:`AutoOrderQuests[0]` 是内部 dev id,解析成目标 active 任务的中文名;
  目标缺失/为 _Old 则置空,**不再泄露内部 id、不再出现字符串 "None"**。
- 无标题 / 标题含未解析 `<…>` 的行跳过。
- 保留人工整理的 `group`/`order`(1.0 DataTable 无此语义),按 id 从旧 missions.json 继承。

依赖导出产物(见 README):
  EXPORT_OUT/**/DT_PalQuestData.json、DT_PalQuestLocationData.json
  EXPORT_OUT/**/L10N/zh-Hans/**/DT_UI_Common_Text*.json、DT_NpcTalkText_Common.json、DT_MapObjectNameText_Common.json
  PAL_BP_OUT/**(Blueprint CDO dump,默认 /opt/palworld-khd/work/bp_out)
用法:python tools/game_data/build_missions.py [--apply]  (不加 --apply 只出差异报告)
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_data import diff, report  # noqa: E402
from game_env import DATA_DIR, EXPORT_OUT  # noqa: E402

BP_OUT = os.environ.get("PAL_BP_OUT", "/opt/palworld-khd/work/bp_out")


def _load_rows(pat):
    fs = glob.glob(f"{EXPORT_OUT}/**/{pat}", recursive=True)
    return json.load(open(fs[0], encoding="utf-8"))[0]["Rows"] if fs else {}


def _load_zh(name):
    fs = glob.glob(f"{EXPORT_OUT}/**/L10N/zh-Hans/**/{name}", recursive=True)
    return json.load(open(fs[0], encoding="utf-8"))[0]["Rows"] if fs else {}


def _loc(rows):
    return {k: (v.get("TextData", {}) or {}).get("LocalizedString", "") or "" for k, v in rows.items()}


def _bp_cdo(assetpath):
    pkg = assetpath.split(".")[0].replace("/Game/", "Pal/Content/")
    f = f"{BP_OUT}/{pkg}.json"
    if not os.path.exists(f):
        return {}
    d = json.load(open(f, encoding="utf-8"))
    cdo = next((e for e in d if e.get("Name", "").startswith("Default__")), None)
    return cdo.get("Properties", {}) if cdo else {}


def build():
    ui = {**_loc(_load_zh("DT_UI_Common_Text.json")), **_loc(_load_zh("DT_UI_Common_Text_Common.json"))}
    npc = _loc(_load_zh("DT_NpcTalkText_Common.json"))
    mn = _loc(_load_zh("DT_MapObjectNameText_Common.json"))
    mn_l = {k.lower(): v for k, v in mn.items()}
    items = {x["item_id"]: x["name"] for x in json.load(open(os.path.join(DATA_DIR, "items.json"), encoding="utf-8"))
             if x.get("item_id")}
    pcn = {p["pal_dev_name"]: p["pal_name"] for p in json.load(open(os.path.join(DATA_DIR, "paldex.json"), encoding="utf-8"))
           if p.get("pal_dev_name")}
    q = _load_rows("DT_PalQuestData.json")
    locd = _load_rows("DT_PalQuestLocationData.json")
    old = {m["id"]: m for m in json.load(open(os.path.join(DATA_DIR, "missions.json"), encoding="utf-8"))}

    def txt(k):
        return ui.get(k) or npc.get(k) or ""

    def clean(s):
        if not s:
            return ""
        s = re.sub(r"<characterName id=\|(\w+)\|[^>]*>", lambda m: pcn.get(m.group(1), m.group(1)), s)
        s = re.sub(r"<mapObjectName id=\|(\w+)\|[^>]*>",
                   lambda m: mn_l.get("mapobject_name_" + m.group(1).lower(), m.group(1)), s)
        s = re.sub(r"<itemName id=\|(\w+)\|[^>]*>", lambda m: items.get(m.group(1), m.group(1)), s)
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"\{[^}]+\}", "", s)
        return re.sub(r"[\r\n]+", "\n", s).strip()

    recs = {}      # id -> record(含原始 next_id)
    for qid, row in q.items():
        if qid.endswith("_Old"):
            continue   # 废弃版不进 active 列表
        cdo = _bp_cdo((row.get("QuestData", {}) or {}).get("AssetPathName", ""))
        if not cdo:
            continue
        tm = cdo.get("QuestTitleMsgId", "")
        name = clean(txt(tm))
        if not name or "<" in name:
            continue
        typ = "主线" if "Main" in str(row.get("QuestType", "")) else "支线"
        o = old.get(qid, {})
        obj = ""
        for ok in (re.sub(r"(?i)title", "OBJECTIVE", tm), re.sub(r"(?i)title", "Objective", tm)):
            obj = clean(txt(ok))
            if obj:
                break
        coords = ""
        fla = ((cdo.get("LocationSettingData") or {}).get("FixedLocationPointArray") or [])
        if fla:
            pos = ((locd.get(fla[0].get("RowName", ""), {}) or {}).get("Position") or {})
            if pos.get("X") is not None:
                coords = f"{round((pos['Y'] - 158000) / 459)},{round((pos['X'] + 123888) / 459)}"
        coords = coords or o.get("coords", "")
        crd = (cdo.get("CommonRewardData", {}) or {})
        rewards = []
        for it in (crd.get("Items", []) or []):
            iid = (it.get("Key", {}) or {}).get("Key", "")
            if iid:
                rewards.append({"name": items.get(iid, iid), "qty": str(it.get("Value", ""))})
        nxt_raw = (cdo.get("AutoOrderQuests", [None]) or [None])[0] or ""
        recs[qid] = {
            "id": qid, "name": name, "type": typ,
            "desc": clean(txt(cdo.get("QuestDescriptionMsgId", ""))) or o.get("desc", ""),
            "objective": obj or o.get("objective", "") or name,
            "coords": coords, "exp": crd.get("Exp", "") or o.get("exp", ""),
            "rewards": rewards, "_next_id": nxt_raw,
            "group": o.get("group", ""), "order": o.get("order", ""),
        }

    # 二次:next_id -> 目标 active 任务中文名;目标不在 active 集合则置空(丢弃悬挂,不泄露 id/None)
    id2name = {i: r["name"] for i, r in recs.items()}
    out = []
    dangling = 0
    for r in recs.values():
        nid = r.pop("_next_id")
        nm = id2name.get(nid, "")
        if nid and not nm:
            dangling += 1
        r["next"] = nm            # 存"目标任务中文名"(消费端直接展示,不再解析 id)
        r["next_id"] = nid if nm else ""   # 有效才保留内部 id,便于追链
        out.append(r)
    # 主线顺序:按 next_id 链拓扑重排(1.0 主线有分支,多条链;链内顺序=游戏推进序)。
    # 旧数据 order 是 155-only EA 残留/字符串,不可靠 → 用链派生干净整数序覆盖。支线不排序(按 NPC 分组)。
    mains = {m["id"]: m for m in out if m["type"] == "主线"}
    nexts = {i: m.get("next_id", "") for i, m in mains.items()}
    pointed = {v for v in nexts.values() if v in mains}
    # 链头按旧 order(能转 int 的)再按 id 稳定排,尽量把"冒险的开始"类靠前
    def _old_ord(i):
        try:
            return int(mains[i].get("order") or 9999)
        except (TypeError, ValueError):
            return 9999
    heads = sorted((i for i in mains if i not in pointed), key=lambda i: (_old_ord(i), i))
    seen, seq = set(), []
    for h in heads:
        c = h
        while c in mains and c not in seen:
            seen.add(c); seq.append(c); c = nexts.get(c, "")
    for i in mains:                      # 环内/未覆盖的补末尾
        if i not in seen:
            seq.append(i)
    for idx, i in enumerate(seq, 1):
        mains[i]["order"] = idx          # 干净整数序
    for m in out:
        if m["type"] == "支线":
            m["order"] = ""              # 支线按 NPC 分组展示,无线性顺序
    out.sort(key=lambda m: (m["type"] != "主线", m["order"] if isinstance(m["order"], int) else 9999, m["id"]))
    print(f"[build] active 任务 {len(out)}(跳过 _Old);悬挂 next 已丢弃 {dangling} 条;"
          f"主线 {sum(1 for m in out if m['type'] == '主线')}/支线 {sum(1 for m in out if m['type'] == '支线')}")
    return out


def main(argv) -> int:
    if not glob.glob(f"{EXPORT_OUT}/**/DT_PalQuestData.json", recursive=True):
        print(f"[abort] 未找到导出的 DT_PalQuestData.json(先 export_datatable.py Pal/Content/Pal/DataTable/Quest)。"
              f"EXPORT_OUT={EXPORT_OUT}")
        return 2
    out = build()
    dst = os.path.join(DATA_DIR, "missions.json")
    old = json.load(open(dst, encoding="utf-8"))
    print("[diff] 旧 vs 新:")
    print(report(diff(old, out, key="id")))
    # 悬挂/None 自检
    ids = {m["id"] for m in out}
    bad = [m["id"] for m in out if m.get("next") in ("None", None) or (m.get("next_id") and m["next_id"] not in ids)]
    assert not bad, f"仍有悬挂/None next: {bad}"
    if "--apply" not in argv:
        print("[dry-run] 未加 --apply,不写。加 --apply 落盘(旧文件留 missions.old.json)。")
        return 0
    os.replace(dst, dst.replace("missions.json", "missions.old.json"))
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[write] {dst}(旧留 missions.old.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
