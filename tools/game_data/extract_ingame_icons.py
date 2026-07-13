#!/usr/bin/env python3
"""从 Palworld 客户端 pak 提取 ingame 主题所需的真实 UI 图标。

用法(本机):
    python tools/game_data/extract_ingame_icons.py \
        --pak-dir /opt/palworld-khd/extract \
        --usmap   /opt/palworld-khd/work/Mappings.usmap \
        --texexport /opt/palworld-khd/work/texexport/bin/Release/net10.0/texexport.dll \
        --dotnet  /opt/palworld-khd/dotnet/dotnet \
        --out     data/ingame     # 内含 icons/ 与 parts/

说明:
- 底层用已编译的 texexport(CUE4Parse) 把 UTexture2D 解码成透明 PNG。
- 客户端 pak 实测无需真实 AES(全 0 即可)。
- ICONS 表是「语义相对路径 -> 游戏资产路径(去 .uasset，/Pal/Content 写成 /Game)」。
- 元素纹理顺序为**视觉实测**顺序(00无01火02水03雷04草05暗06龙07地08冰)，非枚举序。
- 工作纹理按**图标内容**绑定(08=制药 09=采油，与枚举相反)，勿用索引算术。
- 与 data/ingame/manifest.json 的 game_source 字段一一对应；改这里需同步 manifest。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

UI = "/Game/Pal/Texture/UI/InGame"
MM = "/Game/Pal/Texture/UI/Main_Menu"
SE = "/Game/Pal/Texture/UI/Common/StatusEffect"
IM = "/Game/Pal/Texture/UI/IngameMenu"
INV = "/Game/Others/InventoryItemIcon/Texture"

# 语义相对路径(输出 <out>/<左>.png)  ->  游戏资产路径(无扩展名)
ICONS: dict[str, str] = {}

# 属性 9（视觉实测序）
for _k, _i in {"neutral": "00", "fire": "01", "water": "02", "electric": "03",
               "grass": "04", "dark": "05", "dragon": "06", "ground": "07", "ice": "08"}.items():
    ICONS[f"element/{_k}"] = f"{UI}/T_Icon_element_s_{_i}"

# 工作适性 13（按图标内容绑定）
for _k, _i in {"kindling": "00", "watering": "01", "planting": "02", "electricity": "03",
               "handiwork": "04", "gathering": "05", "lumbering": "06", "mining": "07",
               "medicine": "08", "oil": "09", "cooling": "10", "transport": "11",
               "farming": "12"}.items():
    ICONS[f"work/{_k}"] = f"{UI}/T_icon_palwork_{_i}"

# 元素系状态异常
for _e in ("Fire", "Water", "Ice", "Electric", "Grass", "Ground", "Dark", "Poison", "Stun"):
    ICONS[f"status/{_e}"] = f"{SE}/T_icon_StatusEffect_{_e}"

# 通用 UI
ICONS["ui/rarity"] = f"{UI}/T_icon_pal_rare"
ICONS["ui/gender_male"] = f"{MM}/T_Icon_PanGender_Male"
ICONS["ui/gender_female"] = f"{MM}/T_Icon_PanGender_Female"
ICONS["ui/money"] = f"{MM}/T_icon_money"
ICONS["ui/tech_point"] = f"{MM}/T_icon_tech_point_0"
ICONS["ui/ancient_tech_point"] = f"{MM}/T_icon_tech_point_1"
ICONS["ui/dog_coin"] = f"{INV}/T_itemicon_Material_DogCoin"
ICONS["ui/bounty"] = f"{INV}/T_icon_item_Jewelry_BountyProof_1"

# 帕鲁标记(视觉确认):头目=罗盘 boss 头 / 突变=Mutant / 浓缩=condense
ICONS["pal/alpha"] = f"{UI}/T_icon_compass_boss"
ICONS["pal/mutation"] = f"{UI}/T_icon_enemy_Mutant"
ICONS["pal/condensation"] = f"{IM}/T_icon_condense"

# 面板数值图标(视觉确认:00心=HP 03盾=防御 04秤=重量;饱食 hunger)
ICONS["stat/hp"] = f"{MM}/T_icon_status_00"
ICONS["stat/defense"] = f"{MM}/T_icon_status_03"
ICONS["stat/weight"] = f"{MM}/T_icon_status_04"
ICONS["stat/hunger"] = f"{UI}/T_icon_hunger"

# 被动/技能 等级箭头(白色遮罩,CSS 重着色):00↓减益 01↑+1 02↑↑+2 03↑↑↑+3 04↑↑↑+顶阶
ICONS["passive/rank_down"] = f"{MM}/T_icon_skillstatus_rank_arrow_00"
ICONS["passive/rank_up1"] = f"{MM}/T_icon_skillstatus_rank_arrow_01"
ICONS["passive/rank_up2"] = f"{MM}/T_icon_skillstatus_rank_arrow_02"
ICONS["passive/rank_up3"] = f"{MM}/T_icon_skillstatus_rank_arrow_03"
ICONS["passive/rank_up3_plus"] = f"{MM}/T_icon_skillstatus_rank_arrow_04"

# --------- UI 组件纹理(面板/边框/槽/标签/按钮/进度条,多为白色遮罩可 CSS 重着色)---------
# 输出到 data/ingame/parts/,供 ingame 通用组件 CSS 用(border-image 九宫格 / background)。
# 子目录已逐个核实(跨 InGame/Main_Menu/IngameMenu/Common)。
CM = "/Game/Pal/Texture/UI/Common"
PARTS: dict[str, str] = {
    "parts/panel_glow_h":    f"{MM}/T_prt_menu_bggrd",
    "parts/panel_glow_v":    f"{MM}/T_prt_menu_bggrd_v",
    "parts/panel_blur":      f"{UI}/T_prt_base_blur",
    "parts/panel_info":      f"{UI}/T_prt_palinfo_base",
    "parts/title_flare":     f"{MM}/T_prt_text_base_flare",
    "parts/frame_thin":      f"{UI}/T_prt_frame_2px",
    "parts/frame_corner":    f"{UI}/T_prt_FrameCorner",
    "parts/operating_frame": f"{IM}/OperatingTable/T_prt_Operating_Frame",
    "parts/slot_item":       f"{UI}/T_prt_item_base",
    "parts/slot_select":     f"{MM}/T_prt_itemslot_select_check_0",
    "parts/slot_pal":        f"{MM}/T_prt_pal_base_frame",
    "parts/slot_pal_detail": f"{IM}/T_prt_PalBoxDetailFrame",
    "parts/slot_pal_icon":   f"{UI}/T_prt_pal_icon_base_s",
    "parts/slot_pal_circle": f"{UI}/T_prt_pal_get_icon_frame",
    "parts/node_gold":       f"{IM}/Research/T_prt_Research_IconBase_1_On",
    "parts/node_dark":       f"{IM}/Research/T_prt_Research_IconBase_1_Off",
    "parts/node_selected":   f"{IM}/Research/T_prt_Research_IconBase_1_Selected",
    "parts/tab_base":        f"{MM}/T_prt_inventory_tab_base",
    "parts/tab_main":        f"{MM}/T_prt_maintab_base",
    "parts/button":          f"{IM}/T_prt_DropDownButton_Normal",
    "parts/button_flare":    f"{MM}/T_prt_button_frame_flare",
    "parts/bar_hp":          f"{UI}/T_gauge_HP_base",
    "parts/bar_frame":       f"{CM}/T_prt_common_gauge_frame",
}

ZERO_AES = "0x" + "0" * 64


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pak-dir", required=True)
    ap.add_argument("--usmap", required=True)
    ap.add_argument("--texexport", required=True, help="texexport.dll 路径")
    ap.add_argument("--dotnet", default="dotnet")
    ap.add_argument("--out", default="data/ingame", help="ingame 素材根(内含 icons/ 与 parts/)")
    ap.add_argument("--aes", default=ZERO_AES)
    args = ap.parse_args()

    # icons 键(element/…)统一挂到 icons/ 下;parts 键已自带 parts/ 前缀。
    all_map = {f"icons/{k}": v for k, v in ICONS.items()}
    all_map.update(PARTS)

    os.makedirs(args.out, exist_ok=True)
    # texexport 单目录输出 <dev>.png，dev 允许带子目录，先建好子目录
    for rel in all_map:
        os.makedirs(os.path.join(args.out, os.path.dirname(rel)), exist_ok=True)

    map_file = os.path.join(args.out, "_extract_map.tsv")
    with open(map_file, "w", encoding="utf-8") as f:
        for rel, path in all_map.items():
            f.write(f"{rel}\t{path}\n")

    env = dict(os.environ, DOTNET_ROOT=os.path.dirname(args.dotnet))
    cmd = [args.dotnet, args.texexport, args.pak_dir, args.usmap, args.aes, args.out, map_file]
    print("[i] 运行:", " ".join(cmd))
    subprocess.run(cmd, env=env)
    os.remove(map_file)

    got = sum(1 for rel in all_map if os.path.exists(os.path.join(args.out, rel + ".png")))
    print(f"[done] 期望 {len(all_map)} 张(icons {len(ICONS)} + parts {len(PARTS)})，落地 {got} 张 -> {args.out}")
    return 0 if got == len(all_map) else 1


if __name__ == "__main__":
    sys.exit(main())
