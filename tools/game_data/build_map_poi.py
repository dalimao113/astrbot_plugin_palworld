#!/usr/bin/env python3
"""地图 POI(传送点 / 遗物雕像 / 地牢入口)坐标提取 -> data/map_*.json。

背景:旧 data/map_ft_points.json(82 点)是早期手工收集、不完整(v1.1.3 起,无提取脚本)。
本工具从**游戏关卡对象**直接提取全量点位,坐标来源可核对、不臆造。

## 提取管线(两步)

1) 关卡对象扫描(dotnet CUE4Parse 导出器的 __LEVELSCAN__ 模式,见 exporter/Program.cs):
   遍历 `Pal/Content/Pal/Maps/MainWorld_5/` 下全部 .umap(约 9978 个 world-partition
   streaming cell),按 actor 的 ExportType 关键字过滤,取 RootComponent.RelativeLocation
   作为世界坐标,输出 JSON 列表 [{type,name,cell,x,y,z,has_loc}]。

   传送点:  keyword=FastTravel      -> BP_LevelObject_TowerFastTravelPoint_C(152 个)
   遗物雕像: keyword=Relic           -> BP_LevelObject_Relic_C(155 个)
   地牢入口: keyword=Dungeon...      -> BP_DungeonPortalMarker_<Biome>_C

   示例命令(本机,build 24088465,egame=GAME_UE5_1):
     dotnet exporter.dll <pakDir> <usmap> <aes> ft_scan.json  GAME_UE5_1 \
        __LEVELSCAN__ Pal/Content/Pal/Maps/MainWorld_5/ FastTravel
     dotnet exporter.dll <pakDir> <usmap> <aes> poi_scan.json GAME_UE5_1 \
        __LEVELSCAN__ Pal/Content/Pal/Maps/MainWorld_5/ Relic,Dungeon,...

2) 本脚本:读扫描 JSON,世界坐标经 data/map_transform.json 的仿射换算到主图百分比,
   只保留落在主大陆地图内的点,近点去重;名称按**就近命名地标**(map_regions)标注
   (遗物/地牢/多数传送点游戏内无官方逐点名),同名加序号保证唯一。

用法:
  python tools/game_data/build_map_poi.py <ft_scan.json> <poi_scan.json>
覆盖:直接写回 data/map_ft_points.json / map_relics.json / map_dungeons.json。
"""
from __future__ import annotations

import json
import math
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA = os.path.join(_ROOT, "data")

BIOME = {"Desert": "沙漠", "Forest": "森林", "Grass": "草原", "Snow": "雪山",
         "Volcano": "火山", "Sakura": "樱花岛", "Skyland": "天空岛",
         "Viking": "维京", "Yakushima": "屋久岛"}


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main(ft_scan: str, poi_scan: str) -> None:
    t = _load(os.path.join(_DATA, "map_transform.json"))
    mu, mv = t["mu"], t["mv"]
    regs = [(n, v["X"], v["Y"]) for n, v in _load(os.path.join(_DATA, "map_regions.json")).items()]
    old_ft = _load(os.path.join(_DATA, "map_ft_points.json"))

    def pct(x, y):
        return (mu[0] * x + mu[1] * y + mu[2]) * 100, (mv[0] * x + mv[1] * y + mv[2]) * 100

    def onmain(x, y):
        u, v = pct(x, y)
        return -2 <= u <= 102 and -2 <= v <= 102

    def nreg(x, y):
        return min(regs, key=lambda r: (x - r[1]) ** 2 + (y - r[2]) ** 2)[0]

    def dedup(pts, thr):
        u = []
        for x, y in pts:
            if not any(math.hypot(x - a, y - b) < thr for a, b in u):
                u.append((x, y))
        return u

    def build(pts, label):
        out, cnt = {}, {}
        for x, y in sorted(pts, key=lambda p: pct(p[0], p[1])):
            base = label(x, y)
            cnt[base] = cnt.get(base, 0) + 1
            nm = base if cnt[base] == 1 else f"{base}·{cnt[base]}"
            k, i = nm, 2
            while k in out:
                k = f"{nm}({i})"; i += 1
            out[k] = {"X": round(x, 1), "Y": round(y, 1)}
        return out

    def old_ft_name(x, y):
        c = [(nm, math.hypot(x - d["X"], y - d["Y"])) for nm, d in old_ft.items()]
        nm, dist = min(c, key=lambda z: z[1])
        return nm if dist < 100 else None

    ft = _load(ft_scan)
    ftp = dedup([(a["x"], a["y"]) for a in ft if a["has_loc"] and onmain(a["x"], a["y"])], 50)
    ft_out = build(ftp, lambda x, y: old_ft_name(x, y) or nreg(x, y))

    poi = _load(poi_scan)
    relic = dedup([(a["x"], a["y"]) for a in poi
                   if a["type"] == "BP_LevelObject_Relic_C" and a["has_loc"] and onmain(a["x"], a["y"])], 200)
    relic_out = build(relic, nreg)

    dpts = []
    for a in poi:
        if "DungeonPortalMarker" in a["type"] and a["has_loc"] and onmain(a["x"], a["y"]):
            bi = next((v for k, v in BIOME.items() if k in a["type"]), "地牢")
            dpts.append((a["x"], a["y"], bi))
    u = []
    for x, y, bi in dpts:
        if not any(math.hypot(x - a, y - b) < 500 for a, b, _ in u):
            u.append((x, y, bi))
    bmap = {(x, y): bi for x, y, bi in u}
    dun_out = build([(x, y) for x, y, _ in u], lambda x, y: bmap.get((x, y), "地牢") + "地牢")

    for fname, data in (("map_ft_points.json", ft_out), ("map_relics.json", relic_out),
                        ("map_dungeons.json", dun_out)):
        with open(os.path.join(_DATA, fname), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=0)
        print(f"{fname}: {len(data)} 点(主图)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
