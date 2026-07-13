#!/usr/bin/env python3
"""DataTable / 资产 -> JSON 导出器封装(可复现)。

薄封装 dotnet CUE4Parse 导出器(`exporter.csproj`,见 README「导出器」),用 game_env 的
统一参数调用,把指定资产前缀下的 DataTable 导出为 JSON 到 EXPORT_OUT。C/E/F 阶段的
任务/公会/配种数据重生成都从这里取源,不再依赖记忆里的隐藏命令。

实测参数(本机,build 24088465):
  pakDir=/opt/palworld-khd/extract  usmap=Mappings_10.usmap  aes=全零32字节  egame=GAME_UE5_1
  DT_PalMonsterParameter_Common -> 753 行。

用法:
  python tools/game_data/export_datatable.py <前缀1> [前缀2 ...]
  # 前缀是 pak 内路径前缀,如 Pal/Content/Pal/DataTable/Quest
  python tools/game_data/export_datatable.py --check    # 只检查环境齐备,不导出
前缀省略时导出常用 DataTable 目录(Pal/Content/Pal/DataTable)。
"""
from __future__ import annotations

import os
import subprocess
import sys

from game_env import (AES, DOTNET, EGAME, EXPORT_OUT, EXPORTER, PAK_DIR, USMAP,
                      collect_provenance)

DEFAULT_PREFIXES = ["Pal/Content/Pal/DataTable"]


def check_env() -> list[str]:
    """返回缺失项清单(空=齐备)。不臆造:缺什么明确报什么。"""
    missing = []
    if not os.path.isdir(PAK_DIR) or not os.path.exists(os.path.join(PAK_DIR, "Pal-Windows.pak")):
        missing.append(f"pak: {os.path.join(PAK_DIR, 'Pal-Windows.pak')}")
    if not os.path.exists(USMAP):
        missing.append(f"usmap: {USMAP}(1.0 需从运行中客户端 dump,见 README)")
    if not os.path.exists(os.path.join(EXPORTER, "exporter.csproj")):
        missing.append(f"exporter: {EXPORTER}/exporter.csproj")
    if not os.path.exists(DOTNET):
        missing.append(f"dotnet: {DOTNET}")
    return missing


def export(prefixes: list[str]) -> int:
    missing = check_env()
    if missing:
        print("[abort] 提取环境缺失,无法导出(不伪造数据):")
        for m in missing:
            print("  -", m)
        return 2
    os.makedirs(EXPORT_OUT, exist_ok=True)
    cmd = [DOTNET, "run", "--project", EXPORTER, "-c", "Release", "--",
           PAK_DIR, USMAP, AES, EXPORT_OUT, EGAME, *prefixes]
    print("[export]", " ".join(cmd))
    r = subprocess.run(cmd, cwd=EXPORTER)
    return r.returncode


def main(argv: list[str]) -> int:
    if "--check" in argv:
        prov = collect_provenance()
        missing = check_env()
        print(f"[env] build_id={prov['steam_build_id']} egame={EGAME} "
              f"out={EXPORT_OUT}")
        print("[env] 齐备 ✓" if not missing else "[env] 缺失: " + "; ".join(missing))
        return 0 if not missing else 2
    prefixes = [a for a in argv if not a.startswith("--")] or DEFAULT_PREFIXES
    return export(prefixes)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
