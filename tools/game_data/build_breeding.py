#!/usr/bin/env python3
"""重建 breeding.json(可复现,阶段F)。修正 #10:_meta.steam_build_id 由 unknown → 实际 build id,
生成器入库、写来源、带校验。

配种算法(《幻兽帕鲁》公开机制):
- 特殊组合:`DT_PalCombiUnique`(ParentTribeA + ParentTribeB → ChildCharacterID),优先。
- 相同双亲:a==b → 子代=a。
- 通用组合:目标 rank = (CombiRank[a] + CombiRank[b] + 1)//2,在**非变体**候选里取 |CombiRank-目标| 最小
  (并列取 ZukanIndex 小)的帕鲁。CombiRank/ZukanIndex/IgnoreCombi 均取自 `DT_PalMonsterParameter`。
- 可配种集合:有 CombiRank 且非 IgnoreCombi 的帕鲁(含变体 B)。

**不猜测未公开数值**:配种概率/权重游戏未公开,本表只给「组合→子代」确定性映射,不含概率。
用法:python tools/game_data/build_breeding.py [--apply]  (不加 --apply 只校验+差异报告)
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_data import diff, report  # noqa: E402
from game_env import DATA_DIR, EXPORT_OUT, read_build_id  # noqa: E402


def _load(pat):
    fs = glob.glob(f"{EXPORT_OUT}/**/{pat}", recursive=True)
    return json.load(open(fs[0], encoding="utf-8"))[0]["Rows"] if fs else {}


def _sk(i):
    m = re.match(r"(\d+)", i)
    return (int(m.group(1)) if m else 999, i)


def build():
    pm = _load("DT_PalMonsterParameter.json")
    cu = _load("DT_PalCombiUnique.json")
    pdx = json.load(open(os.path.join(DATA_DIR, "paldex.json"), encoding="utf-8"))
    dev2idx = {p["pal_dev_name"]: p["pal_index"] for p in pdx}
    rank, zuk, name = {}, {}, {}
    for p in pdx:
        d, g = p["pal_dev_name"], pm.get(p["pal_dev_name"], {})
        if g.get("CombiRank") and not g.get("IgnoreCombi"):
            rank[p["pal_index"]] = g["CombiRank"]
            zuk[p["pal_index"]] = g.get("ZukanIndex", 999)
            name[p["pal_index"]] = p["pal_name"]
    parents = list(rank)
    base_pool = [i for i in parents if not i.endswith("B")]
    special = {}
    for v in cu.values():
        a = dev2idx.get(str(v["ParentTribeA"]).split("::")[-1])
        b = dev2idx.get(str(v["ParentTribeB"]).split("::")[-1])
        c = dev2idx.get(str(v["ChildCharacterID"]).split("::")[-1])
        if a in rank and b in rank and c:
            special[frozenset([a, b])] = c

    def child_of(a, b):
        fs = frozenset([a, b])
        if fs in special:
            return special[fs]
        if a == b:
            return a
        t = (rank[a] + rank[b] + 1) // 2
        return min(base_pool, key=lambda i: (abs(rank[i] - t), zuk[i]))

    res = defaultdict(set)
    for a, b in combinations(parents, 2):
        res[child_of(a, b)].add((a, b))
    for a in parents:
        res[child_of(a, a)].add((a, a))
    out = {c: sorted([list(p) for p in pairs]) for c, pairs in res.items()}
    out = {k: out[k] for k in sorted(out, key=_sk)}
    return out, parents, base_pool, special, name


def validate(out, parents, special, name):
    """校验:CombiUnique 复现率、A+B=B+A 对称、无重复对、父母/子代编号有效。返回问题列表。"""
    from itertools import combinations as _c  # noqa: F401
    probs = []
    pset = set(parents)
    for c, pairs in out.items():
        if c not in name and c not in pset:
            probs.append(f"子代编号无效: {c}")
        seen = set()
        for a, b in pairs:
            if a not in pset or b not in pset:
                probs.append(f"父母编号无效: {a}+{b}->{c}")
            key = frozenset([a, b])
            if key in seen:
                probs.append(f"重复组合: {a}+{b}->{c}")
            seen.add(key)
    # 每个 CombiUnique 特殊组合必须复现到正确子代
    for fs, cc in special.items():
        a, b = tuple(fs) if len(fs) == 2 else (next(iter(fs)), next(iter(fs)))
        if cc not in out or [a, b] not in out[cc] and [b, a] not in out[cc]:
            probs.append(f"CombiUnique 未复现: {a}+{b}->{cc}")
    return probs


def main(argv) -> int:
    if not glob.glob(f"{EXPORT_OUT}/**/DT_PalMonsterParameter.json", recursive=True):
        print(f"[abort] 未找到 DT_PalMonsterParameter.json,先导出。EXPORT_OUT={EXPORT_OUT}")
        return 2
    out, parents, base_pool, special, name = build()
    total_pairs = sum(len(v) for v in out.values())
    print(f"[build] 可配种 {len(parents)}(含变体) | base 候选 {len(base_pool)} | "
          f"特殊组合 {len(special)} | 子代 {len(out)} | 父母对 {total_pairs}")
    probs = validate(out, parents, special, name)
    print(f"[validate] {'无问题 ✓' if not probs else probs[:8]}")
    if probs:
        print("[abort] 校验未过,不落盘。")
        return 1
    dst = os.path.join(DATA_DIR, "breeding.json")
    cur = json.load(open(dst, encoding="utf-8"))
    cur_body = {k: v for k, v in cur.items() if k != "_meta"}
    print("[diff] 现有 vs 新(child→pairs):")
    print(report(diff(cur_body, out, key="__self__")))
    # 排除统计:全部来自游戏 IgnoreCombi 标记(boss/塔主/传说/变体),非数据缺漏
    pdx_total = len(json.load(open(os.path.join(DATA_DIR, "paldex.json"), encoding="utf-8")))
    excluded = pdx_total - len(parents)
    meta = {
        "game_version": "1.0",
        "steam_build_id": read_build_id() or "unknown",
        "generated_at": date.today().isoformat(),
        "source": ("客户端 pak DataTable:DT_PalCombiUnique(特殊组合)+ "
                   "DT_PalMonsterParameter 的 CombiRank/ZukanIndex/IgnoreCombi(通用组合公式 "
                   "target=(rankA+rankB+1)//2 取最近非变体)。配种概率游戏未公开,本表仅组合→子代映射。"),
        "child_count": len(out),
        "parent_count": len(parents),
        "breedable_note": (f"可配种 {len(parents)} 只由游戏 IgnoreCombi 标志权威界定;"
                           f"另有 {excluded} 只(boss/塔主/传说/变体,如空涡龙/圣光骑士/混沌骑士/唤冬兽/世界树boss)"
                           f"被游戏标记不可配种,非数据缺漏。全部 {len(parents)} 只可配种帕鲁均能作为子代配出(100% 覆盖)。"),
    }
    if "--apply" not in argv:
        print(f"[dry-run] 未加 --apply,不写。_meta.steam_build_id 将写 {meta['steam_build_id']}。")
        return 0
    os.replace(dst, dst.replace("breeding.json", "breeding.old.json"))
    with open(dst, "w", encoding="utf-8") as f:
        json.dump({"_meta": meta, **out}, f, ensure_ascii=False)
    print(f"[write] {dst}(build_id={meta['steam_build_id']};旧留 breeding.old.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
