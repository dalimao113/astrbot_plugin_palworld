#!/usr/bin/env python3
"""数据文本清洗(可复现)。修复审计确认的文本类问题,不手工改最终 JSON。

处理:
- 所有字符串值:去零宽字符(U+200B/C/D、BOM)。
- paldex.json:pal_name / partner_skill_title 去首尾空格(修「黑月女王 」);
  描述类字段(pal_description / partner_skill_description / related_technology.description)
  过 clean_text:解析 <itemName id=|X|/>(用本仓库 items/tech/paldex 名称表),占位「zh-hans text」→ 空。
- items.json:去零宽字符 + 描述过 clean_text。

流程:载入 -> 处理 -> 校验(JSON 可解析 + 无零宽/无 <itemName>/无占位/无名称首尾空格)-> 原子替换。
校验不过不落盘。用法:python tools/game_data/clean_data_text.py [--apply]
不带 --apply 只做 dry-run 报告。
"""
from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(_ROOT))
from astrbot_plugin_palworld.utils.text import clean_text, is_missing_text  # noqa: E402

_DATA = os.path.join(_ROOT, "data")
_ZW = "​‌‍⁠﻿"
_DESC_FIELDS = {"pal_description", "partner_skill_description", "description", "technology_name"}
_NAME_FIELDS = {"pal_name", "partner_skill_title", "name"}


def _load(name):
    with open(os.path.join(_DATA, name), encoding="utf-8") as f:
        return json.load(f)


def _build_resolver():
    """id/dev_name -> 中文名,用于解析 <itemName id=|X|/>。来源:仓库现有数据。"""
    m = {}
    try:
        for it in _iter_items(_load("items.json")):
            for k in ("id", "item_id", "dev_name", "name_en"):
                if it.get(k):
                    m.setdefault(str(it[k]), it.get("name"))
    except Exception:  # noqa: BLE001
        pass
    try:
        for p in _load("paldex.json"):
            if p.get("pal_dev_name"):
                m.setdefault(str(p["pal_dev_name"]), p.get("pal_name"))
    except Exception:  # noqa: BLE001
        pass
    return lambda rid: m.get(rid) or m.get(rid.replace("SkillUnlock_", "")) or ""


def _iter_items(items):
    return items if isinstance(items, list) else list(items.values())


def _strip_zw(s):
    return "".join(c for c in s if c not in _ZW) if isinstance(s, str) else s


def _walk_clean(obj, resolve, stats):
    """递归:去零宽;描述字段过 clean_text;名称字段去首尾空格。"""
    if isinstance(obj, dict):
        return {k: _walk_field(k, v, resolve, stats) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_clean(v, resolve, stats) for v in obj]
    return obj


def _walk_field(key, val, resolve, stats):
    if isinstance(val, (dict, list)):
        return _walk_clean(val, resolve, stats)
    if not isinstance(val, str):
        return val
    orig = val
    if key in _NAME_FIELDS:
        val = _strip_zw(val).strip()
    elif key in _DESC_FIELDS:
        val = clean_text(_strip_zw(val), resolve)
    else:
        val = _strip_zw(val)
    if val != orig:
        stats["changed"] += 1
    return val


def _validate(obj_paldex, obj_items):
    """校验:无零宽 / 无 <itemName / 无 zh-hans text 占位描述 / pal_name 无首尾空格。返回问题列表。"""
    probs = []
    raw = json.dumps([obj_paldex, obj_items], ensure_ascii=False)
    for zw in _ZW:
        if zw in raw:
            probs.append(f"仍含零宽字符 U+{ord(zw):04X}")
    if "<itemName" in raw:
        probs.append("仍含未解析 <itemName>")
    for p in obj_paldex:
        n = p.get("pal_name")
        if isinstance(n, str) and n != n.strip():
            probs.append(f"pal_name 首尾空格: {n!r}")
        rt = p.get("related_technology")
        if isinstance(rt, dict) and is_missing_text(rt.get("description")) and rt.get("description"):
            probs.append(f"related_technology.description 占位未清: {p.get('pal_name')}")
    return probs


def main() -> int:
    apply = "--apply" in sys.argv
    # <itemName id=|X|/> 的正确名称需游戏本地化表(尚未提取);按「不得猜测」原则,
    # 暂不用仓库名称表反查(可能对应技能/物品而非帕鲁名),无法解析则去除标签。
    resolve = None
    paldex = _load("paldex.json")
    items = _load("items.json")
    st = {"changed": 0}
    paldex2 = _walk_clean(paldex, resolve, st)
    items2 = _walk_clean(items, resolve, st)
    probs = _validate(paldex2, items2)
    print(f"[clean] 变更字段数: {st['changed']}")
    print(f"[validate] 残留问题: {probs or '无 ✓'}")
    if probs:
        print("[abort] 校验未过,不落盘。")
        return 1
    if not apply:
        print("[dry-run] 未加 --apply,不写文件。加 --apply 落盘。")
        return 0
    for name, obj in (("paldex.json", paldex2), ("items.json", items2)):
        dst = os.path.join(_DATA, name)
        tmp = dst + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)  # 紧凑格式,匹配源文件(默认 separators)
        json.load(open(tmp, encoding="utf-8"))  # 二次确认可解析
        os.replace(tmp, dst)
        print(f"[write] {name} 已原子替换")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
