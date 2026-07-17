#!/usr/bin/env python3
"""帕鲁野外刷新点提取 -> data/pal_spawns.json。

背景:旧 data/pal_spawns.json(137 只)覆盖严重不全 —— 每个刷新点(spawner)其实同时
刷**多只**帕鲁,旧提取每组只取到 1~2 只,导致同坐标的其余帕鲁全丢(如「捣蛋猫/勾魂鱿/
鬼刃武士」等在图鉴查得到,却 /帕鲁栖息 显示查不到)。本工具从两张权威 DataTable 正确
JOIN,展开每个 spawner 组的**全部** Pal_1/2/3,覆盖 225 只。

## 数据源(两张表 JOIN)

- `DT_PalSpawnerPlacement`:刷新点**放置**,给世界坐标 `Location{X,Y}` + `SpawnerName` +
  `PlacementType`(Field/FieldBoss/Dungeon…)+ `WorldName`。
- `DT_PalWildSpawner`:刷新**组**,按 `SpawnerName` 分组,每行 `Pal_1/2/3` + `OnlyTime`
  (Day/Night/Undefined=日夜均刷)+ `Weight` + `LvMin/Max`。

JOIN:placement.SpawnerName == wildspawner 行的 SpawnerName 字段。世界坐标经仿射换算到
地图百分比。按 PlacementType 分类:
  - Field 非头目  -> 野外常规刷新热区(day/night/tree_day/tree_night)
  - Field 头目 / FieldBoss     -> 野外头目(spots kind=fboss)
  - Dungeon 非头目             -> 地牢(spots kind=dungeon)
  - Dungeon 头目 / DungeonBoss -> 地牢头目(spots kind=dboss)
  - ImprisonmentBoss           -> 关押头目(spots kind=prison)
(头目 = spawner 组里帕鲁名带 BOSS_ 前缀。) 这样地牢限定/头目限定帕鲁(如 炽巫猫=樱花岛
地牢)也有坐标可显示,不再"查不到";栖息卡按种类标注类型。塔主(tower)不在这两张表里
(高塔是独立 boss 竞技场),仍由 boss_spawns.json 提供。

## 双区域(主大陆 / 世界树)

`worldtree*` 开头的 spawner 属**世界树独立区域**,用 data/map_transform_tree.json 换算、
落世界树独立底图;其余用 data/map_transform.json 落主大陆。实测:非 worldtree 放置全部
落主图 0~100%,worldtree 放置全部落世界树图 0~100%,前缀区分干净、无交叉。

输出 schema(按图鉴序):
  { dev_name: {"day":[[l,t]], "night":[[l,t]], "tree_day":[[l,t]], "tree_night":[[l,t]],
               "spots":[[l,t,kind,region], ...]}, ... }
空桶省略;野外热区主图点在 day/night、世界树点在 tree_day/tree_night;特殊点(地牢/头目)
在 spots(kind=fboss/dungeon/dboss/prison,region=main/tree)。同点按 0.5% 栅格去重、
热区每桶最多 CAP 个、spots 每(种类,区域)最多 SPOT_CAP 个均匀采样(避免糊卡/文件过大)。

用法:
  python tools/game_data/build_pal_spawns.py
  # 或指定导出目录:PAL_EXPORT_OUT=/path python tools/game_data/build_pal_spawns.py
覆盖:直接写回 data/pal_spawns.json(生成失败不覆盖旧数据)。
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA = os.path.join(_ROOT, "data")
_EXPORT_OUT = os.environ.get("PAL_EXPORT_OUT", "/opt/palworld-khd/work/exported")
_SPAWNER_DIR = os.path.join(_EXPORT_OUT, "Pal/Content/Pal/DataTable/Spawner")

CAP = 70   # 野生热区每桶(day/night/tree_day/tree_night)最多保留的刷新点数
SPOT_CAP = 40   # 特殊点(地牢/头目)每(种类,区域)最多保留数

# 放置类型 -> 特殊点种类(野外常规刷新走 day/night 热区,不进 spots)。
# is_boss = 该 spawner 组里帕鲁名带 BOSS_ 前缀(头目形态)。
def _spot_kind(placement_type: str, is_boss: bool) -> str:
    pt = placement_type.split("::")[-1]
    if pt == "FieldBoss" or (pt == "Field" and is_boss):
        return "fboss"        # 野外头目
    if pt == "DungeonBoss" or (pt == "Dungeon" and is_boss):
        return "dboss"        # 地牢头目
    if pt == "Dungeon":
        return "dungeon"      # 地牢(普通)
    if pt == "ImprisonmentBoss":
        return "prison"       # 关押头目
    return ""                 # Field 非头目 -> 野生热区,不在此处理


def _rows(obj):
    """CUE4Parse 导出的 DataTable:可能是 {..,'Rows':{}} 或 [{'Rows':{}}]。"""
    if isinstance(obj, dict) and "Rows" in obj:
        return obj["Rows"]
    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, dict) and "Rows" in x:
                return x["Rows"]
    return obj


def _load(name: str):
    with open(os.path.join(_SPAWNER_DIR, name), encoding="utf-8") as f:
        return _rows(json.load(f))


def _affine(tf):
    mu, mv = tf["mu"], tf["mv"]
    return lambda x, y: (round((mu[0] * x + mu[1] * y + mu[2]) * 100, 1),
                         round((mv[0] * x + mv[1] * y + mv[2]) * 100, 1))


def _dedupe_cap(pts: set) -> list:
    """0.5% 栅格去重 -> 超 CAP 则均匀采样,保留地理分布。"""
    grid = {}
    for l, t in pts:
        grid.setdefault((round(l * 2) / 2, round(t * 2) / 2), (l, t))
    uniq = sorted(grid.values())
    if len(uniq) <= CAP:
        return [[l, t] for l, t in uniq]
    step = len(uniq) / CAP
    return [[uniq[int(i * step)][0], uniq[int(i * step)][1]] for i in range(CAP)]


def build() -> dict:
    ws = _load("DT_PalWildSpawner.json")
    pl = _load("DT_PalSpawnerPlacement.json")
    main = _affine(json.load(open(os.path.join(_DATA, "map_transform.json"), encoding="utf-8")))
    tree = _affine(json.load(open(os.path.join(_DATA, "map_transform_tree.json"), encoding="utf-8")))

    # spawner 组 -> {pal_dev: {'day','night'}}(Undefined 记为日夜均刷)
    ws_by = defaultdict(list)
    for row in ws.values():
        ws_by[row.get("SpawnerName", "")].append(row)

    def group_pals(sn: str):
        """spawner 组内每只帕鲁 -> {'times':时段集合, 'lv':[min,max]}。名字含 BOSS_ 前缀保留。"""
        out: dict = {}
        for row in ws_by.get(sn, []):
            t = row.get("OnlyTime", "")
            night = t == "EPalOneDayTimeType::Night"
            day = t == "EPalOneDayTimeType::Day"
            for i in (1, 2, 3):
                pal = row.get(f"Pal_{i}", "None")
                if not pal or pal == "None":
                    continue
                e = out.setdefault(pal, {"times": set(), "lv": [10 ** 9, -1]})
                if night:
                    e["times"].add("night")
                elif day:
                    e["times"].add("day")
                else:
                    e["times"].update(("day", "night"))
                lo, hi = row.get(f"LvMin_{i}"), row.get(f"LvMax_{i}")
                if isinstance(lo, int) and lo > 0:
                    e["lv"][0] = min(e["lv"][0], lo)
                if isinstance(hi, int) and hi > 0:
                    e["lv"][1] = max(e["lv"][1], hi)
        return out

    def to_map(x, y, is_tree_name):
        """世界坐标 -> (map%, region)。worldtree spawner 用世界树变换,否则主图;都不落图内返回 None。"""
        if is_tree_name:
            l, t = tree(x, y)
            return ((l, t), "tree") if 0 <= l <= 100 and 0 <= t <= 100 else None
        l, t = main(x, y)
        if 0 <= l <= 100 and 0 <= t <= 100:
            return (l, t), "main"
        l, t = tree(x, y)                  # 少数非 worldtree 命名但实处世界树的兜底
        return ((l, t), "tree") if 0 <= l <= 100 and 0 <= t <= 100 else None

    base = lambda n: n[5:] if n.startswith("BOSS_") else n   # noqa: E731

    # 野生热区:pal -> {day,night,tree_day,tree_night} 点集
    wild = defaultdict(lambda: {"day": set(), "night": set(), "tree_day": set(), "tree_night": set()})
    # 特殊点(地牢/头目):pal -> {(kind, region): set(点)}
    spots = defaultdict(lambda: defaultdict(set))
    # 特殊点等级:pal -> {kind: [min, max]}(用于图例显示头目等级,取自权威 spawner 表)
    spot_lv = defaultdict(dict)

    for v in pl.values():
        pt = v.get("PlacementType", "") or ""
        loc = v.get("Location") or {}
        x, y = loc.get("X"), loc.get("Y")
        if x is None or y is None:
            continue
        sn = v.get("SpawnerName", "") or ""
        mapped = to_map(x, y, sn.lower().startswith("worldtree"))
        if mapped is None:
            continue
        (l, t), region = mapped
        pref = "tree_" if region == "tree" else ""
        for pal, info in group_pals(sn).items():
            dev = base(pal)
            is_boss = pal.startswith("BOSS_")
            if pt == "EPalSpawnerPlacementType::Field" and not is_boss:
                for tm in info["times"]:    # 野外常规刷新 -> 热区
                    wild[dev][pref + tm].add((l, t))
            else:
                kind = _spot_kind(pt, is_boss)
                if kind:
                    spots[dev][(kind, region)].add((l, t))
                    lo, hi = info["lv"]
                    if hi >= lo >= 0:
                        cur = spot_lv[dev].get(kind)
                        spot_lv[dev][kind] = [min(cur[0], lo), max(cur[1], hi)] if cur else [lo, hi]

    # 只保留图鉴内的 dev 名(RowName/None 等垃圾键排除);按图鉴序输出
    pals = json.load(open(os.path.join(_DATA, "paldex.json"), encoding="utf-8"))
    order = {str(p.get("pal_dev_name", "")): i for i, p in enumerate(pals)}
    devset = set(order)

    out: dict = {}
    for dev in set(wild) | set(spots):
        if dev not in devset:
            continue
        entry = {}
        for key in ("day", "night", "tree_day", "tree_night"):
            pts = _dedupe_cap(wild[dev][key])
            if pts:
                entry[key] = pts
        # spots: [[l,t,kind,region], ...]。同一坐标同时是地牢+地牢头目(同一地牢入口)时,
        # 只保留高优先种类(关押>地牢头目>野外头目>地牢),避免同点两个标记、并缩小体积。
        _PRIO = {"prison": 4, "dboss": 3, "fboss": 2, "dungeon": 1}
        best: dict = {}   # (region, grid_l, grid_t) -> (kind, l, t)
        for (kind, region), pset in spots[dev].items():
            for l, t in pset:
                gk = (region, round(l * 2) / 2, round(t * 2) / 2)
                cur = best.get(gk)
                if cur is None or _PRIO[kind] > _PRIO[cur[0]]:
                    best[gk] = (kind, l, t)
        # 每(种类,区域)限量,保留地理分布
        by_kr = defaultdict(list)
        for (region, _gl, _gt), (kind, l, t) in best.items():
            by_kr[(kind, region)].append((l, t))
        spot_list = []
        kept_kinds = set()
        for (kind, region), pts in sorted(by_kr.items()):
            for l, t in sorted(pts)[:SPOT_CAP]:
                spot_list.append([l, t, kind, region])
                kept_kinds.add(kind)
        if spot_list:
            entry["spots"] = spot_list
            lv = {k: spot_lv[dev][k] for k in kept_kinds if k in spot_lv.get(dev, {})}
            if lv:
                entry["spot_lv"] = lv
        if entry:
            out[dev] = entry
    return dict(sorted(out.items(), key=lambda kv: order.get(kv[0], 99999)))


def main():
    try:
        data = build()
    except Exception as e:  # noqa: BLE001
        print(f"[build_pal_spawns] 生成失败,保留旧数据: {e}", file=sys.stderr)
        return 1
    if len(data) < 137:   # 旧版覆盖 137,少于此视为异常,拒绝覆盖
        print(f"[build_pal_spawns] 覆盖数 {len(data)} < 137,疑似源数据异常,拒绝写入", file=sys.stderr)
        return 1
    # provenance 元信息(CLAUDE.md:数据须记录来源)。dev 名不会等于 _meta,不影响按名查询。
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from game_env import read_build_id  # type: ignore
        build_id = read_build_id()
    except Exception:  # noqa: BLE001
        build_id = ""
    data["_meta"] = {
        "source": "DT_PalSpawnerPlacement × DT_PalWildSpawner (Field 热区 + 地牢/头目 spots)",
        "steam_build_id": build_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pal_count": len(data),
    }
    out_path = os.path.join(_DATA, "pal_spawns.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[build_pal_spawns] 写入 {out_path}:{len(data) - 1} 只帕鲁,{os.path.getsize(out_path)} 字节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
