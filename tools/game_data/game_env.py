#!/usr/bin/env python3
"""游戏数据提取工具链的统一配置 + 来源采集(discover)。

把散在仓库外隐藏目录(`/opt/palworld-khd/...`)的路径收敛到一处、可用环境变量覆盖,
并提供 provenance(build id / usmap 指纹 / pak 指纹 / egame)采集,写进 `provenance.json`,
让每次数据重生成都带可核对的来源(CLAUDE.md:数据须记录 build id / source)。

所有路径均可用环境变量覆盖,便于换机器/换游戏版本:
  PAL_PAK_DIR   含 Pal-Windows.pak 的目录(DefaultFileProvider 的 pakDir)
  PAL_USMAP     Mappings usmap(1.0 需从运行中客户端 dump,见 README)
  PAL_AES       pak AES 密钥(Palworld 为全零 32 字节)
  PAL_EGAME     CUE4Parse EGame 枚举(实测 GAME_UE5_1)
  PAL_EXPORTER  dotnet 导出器工程目录(exporter.csproj 所在)
  PAL_DOTNET    dotnet 可执行文件
  PAL_APPMANIFEST  服务端 appmanifest_2394010.acf(取 buildid)
  PAL_EXPORT_OUT   DataTable 导出 JSON 的输出目录
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone

# 仓库根(本文件在 tools/game_data/ 下)
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PLUGIN_ROOT, "data")

# 外部游戏工具链默认路径(本机实测),均可用环境变量覆盖
PAK_DIR = os.environ.get("PAL_PAK_DIR", "/opt/palworld-khd/extract")
USMAP = os.environ.get("PAL_USMAP", "/opt/palworld-khd/Mappings_10.usmap")
AES = os.environ.get("PAL_AES", "0x" + "0" * 64)   # Palworld pak 用全零 32 字节密钥
EGAME = os.environ.get("PAL_EGAME", "GAME_UE5_1")   # 实测可解 1.0 DataTable
EXPORTER = os.environ.get("PAL_EXPORTER", "/opt/palworld-khd/work/exporter")
DOTNET = os.environ.get("PAL_DOTNET", "/opt/palworld-khd/dotnet/dotnet")
APPMANIFEST = os.environ.get("PAL_APPMANIFEST", "/opt/palworld/palworld/steamapps/appmanifest_2394010.acf")
EXPORT_OUT = os.environ.get("PAL_EXPORT_OUT", "/opt/palworld-khd/work/exported")

PROVENANCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "provenance.json")


def _acf_field(text: str, key: str) -> str:
    m = re.search(rf'"{key}"\s+"([^"]+)"', text)
    return m.group(1) if m else ""


def read_build_id() -> str:
    """从服务端 appmanifest 读 buildid(如 24088465)。读不到返回空串。"""
    try:
        with open(APPMANIFEST, encoding="utf-8", errors="ignore") as f:
            return _acf_field(f.read(), "buildid")
    except OSError:
        return ""


def _fingerprint(path: str) -> dict:
    """文件指纹:存在性 / 大小 / mtime / sha256(大文件如 pak 只按大小+mtime,不整读)。"""
    if not os.path.exists(path):
        return {"path": path, "exists": False}
    st = os.stat(path)
    info = {"path": path, "exists": True, "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()}
    if st.st_size <= 64 * 1024 * 1024:   # usmap 等中小文件算 sha256;pak(40GB)跳过
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        info["sha256"] = h.hexdigest()
    return info


def _dotnet_version() -> str:
    try:
        return subprocess.run([DOTNET, "--version"], capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def collect_provenance() -> dict:
    """采集当前提取环境的来源信息(不做导出,仅记录)。"""
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "steam_build_id": read_build_id(),
        "app_id": "2394010",
        "egame": EGAME,
        "aes_zero_key": AES == "0x" + "0" * 64,
        "dotnet_version": _dotnet_version(),
        "pak_dir": PAK_DIR,
        "usmap": _fingerprint(USMAP),
        "pak": _fingerprint(os.path.join(PAK_DIR, "Pal-Windows.pak")),
        "exporter_present": os.path.exists(os.path.join(EXPORTER, "exporter.csproj")),
    }


def main() -> int:
    prov = collect_provenance()
    with open(PROVENANCE_PATH, "w", encoding="utf-8") as f:
        json.dump(prov, f, ensure_ascii=False, indent=2)
    print(f"[provenance] build_id={prov['steam_build_id']} egame={prov['egame']} "
          f"usmap={'ok' if prov['usmap']['exists'] else 'MISSING'} "
          f"pak={'ok' if prov['pak']['exists'] else 'MISSING'} -> {PROVENANCE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
