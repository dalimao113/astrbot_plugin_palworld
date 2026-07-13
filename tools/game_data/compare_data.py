#!/usr/bin/env python3
"""数据差异报告(可复现)。对比两份 JSON(旧/新),按稳定主键列出新增/删除/字段变更。

CLAUDE.md:数据生成失败不得覆盖上一版可用数据;每次数据更新应能生成差异报告。
重生成前先把现有 data/<x>.json 备份为 <x>.old.json,重生成后跑本工具核对增删改,确认无误再替换。

用法:
  python tools/game_data/compare_data.py <old.json> <new.json> [--key item_id]
主键(--key)省略时自动探测常见主键(item_id / pal_dev_name / id / mission_id / RowName)。
支持 list[dict]、dict[str,dict]、以及顶层 [ {..., "Rows": {...}} ] 的 DataTable 导出结构。
"""
from __future__ import annotations

import json
import sys

_KEY_CANDIDATES = ("item_id", "pal_dev_name", "mission_id", "id", "RowName", "name")


def _rows(obj):
    """把多种结构归一成 {key: record}。"""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "Rows" in obj[0]:
        return obj[0]["Rows"]          # DataTable 导出:[{...,"Rows":{...}}]
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        return obj                     # list[dict] -> 后续按主键取
    return {}


def _index(obj, key):
    rows = _rows(obj)
    if isinstance(rows, dict):
        return {str(k): v for k, v in rows.items()}
    out = {}
    for i, r in enumerate(rows):
        k = str(r.get(key, i)) if isinstance(r, dict) else str(i)
        out[k] = r
    return out


def _detect_key(obj):
    rows = _rows(obj)
    sample = next(iter(rows.values())) if isinstance(rows, dict) else (rows[0] if rows else {})
    if isinstance(sample, dict):
        for k in _KEY_CANDIDATES:
            if k in sample:
                return k
    return "id"


def diff(old_obj, new_obj, key=None):
    key = key or _detect_key(new_obj)
    a, b = _index(old_obj, key), _index(new_obj, key)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = []
    for k in sorted(set(a) & set(b)):
        if isinstance(a[k], dict) and isinstance(b[k], dict):
            fields = sorted({f for f in set(a[k]) | set(b[k]) if a[k].get(f) != b[k].get(f)})
            if fields:
                changed.append((k, fields))
        elif a[k] != b[k]:
            changed.append((k, ["<value>"]))
    return {"key": key, "old_count": len(a), "new_count": len(b),
            "added": added, "removed": removed, "changed": changed}


def report(d) -> str:
    lines = [f"主键={d['key']}  旧={d['old_count']} 新={d['new_count']} "
             f"(+{len(d['added'])} / -{len(d['removed'])} / ~{len(d['changed'])})"]
    if d["added"]:
        lines.append(f"新增({len(d['added'])}): " + ", ".join(d["added"][:40])
                     + (" …" if len(d["added"]) > 40 else ""))
    if d["removed"]:
        lines.append(f"删除({len(d['removed'])}): " + ", ".join(d["removed"][:40])
                     + (" …" if len(d["removed"]) > 40 else ""))
    if d["changed"]:
        lines.append(f"变更({len(d['changed'])}):")
        for k, fields in d["changed"][:40]:
            lines.append(f"  {k}: {', '.join(fields[:8])}" + (" …" if len(fields) > 8 else ""))
        if len(d["changed"]) > 40:
            lines.append(f"  … 另 {len(d['changed']) - 40} 项")
    return "\n".join(lines)


def main(argv) -> int:
    args = [a for a in argv if not a.startswith("--")]
    key = None
    if "--key" in argv:
        i = argv.index("--key")
        key = argv[i + 1] if i + 1 < len(argv) else None
        args = [a for a in args if a != key]
    if len(args) < 2:
        print(__doc__)
        return 1
    old = json.load(open(args[0], encoding="utf-8"))
    new = json.load(open(args[1], encoding="utf-8"))
    print(report(diff(old, new, key)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
