#!/usr/bin/env python3
"""生成「插件扩展」线性 SVG 图标(游戏无此语义的功能:服务器/主机/插件运维)。

这些**不是**游戏图标,也**不冒充**游戏图标:统一细线风格,明确属于插件 UI。
用于 ingame 主题里 server.*/plugin.* 语义键(manifest 的 plugin_ext 命名空间)。
输出:data/ingame/svg/<key>.svg。改图标请改本脚本后重跑,保持风格一致。

颜色:stroke 用 currentColor 占位;由 CSS/内联 color 决定(ingame 配色待截图校准前用中性暖线)。
"""
from __future__ import annotations

import os

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ingame", "svg")

# viewBox 0 0 24 24, 统一细线。fill 型个别单独给。
_HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
         'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">')

# key -> 内部 SVG 元素(不含外层 <svg>)
ICONS: dict[str, str] = {
    # ---- server.* / 主机 ----
    "server_online": '<circle cx="12" cy="12" r="8" opacity=".4"/><circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/>',
    "server_offline": '<circle cx="12" cy="12" r="8"/><path d="M6.5 6.5l11 11"/>',
    "players": '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-5 6-5s6 1.7 6 5"/><path d="M16.5 6a3 3 0 0 1 0 6"/><path d="M21 20c0-2.6-1.5-4.2-4-4.9"/>',
    "fps": '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4.5-5"/><circle cx="12" cy="18" r="1.2" fill="currentColor" stroke="none"/>',
    "uptime": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "calendar": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 9.5h16M8.5 3v4M15.5 3v4"/>',
    "gauge": '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l5-3"/><circle cx="12" cy="18" r="1.2" fill="currentColor" stroke="none"/><path d="M12 18v-2M7 14l1 1M17 14l-1 1"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="1"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>',
    "memory": '<rect x="3" y="8" width="18" height="8" rx="1"/><path d="M6.5 16.5v1.5M10 16.5v1.5M14 16.5v1.5M17.5 16.5v1.5"/><path d="M7 11v2M11 11v2M15 11v2"/>',
    # ---- plugin.* / 运维 ----
    "selfcheck": '<path d="M12 3l7 3v5c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6z"/><path d="M9 12l2 2 4-4.5"/>',
    "audit": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    "backup": '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v12c0 1.6 3.1 3 7 3s7-1.4 7-3V6"/><path d="M5 12c0 1.6 3.1 3 7 3s7-1.4 7-3"/>',
    "bell": '<path d="M6 9a6 6 0 0 1 12 0c0 4.5 2 5.5 2 5.5H4S6 13.5 6 9"/><path d="M10 18.5a2 2 0 0 0 4 0"/>',
    "bell_off": '<path d="M6 9a6 6 0 0 1 9.7-4.7M18 11.5c0 3 1.3 3.9 2 3.9H8"/><path d="M10 18.5a2 2 0 0 0 4 0"/><path d="M4 4l16 16"/>',
    "lock": '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "link": '<path d="M9.5 14.5l5-5"/><path d="M10.5 6.5l1-1a4 4 0 0 1 5.7 5.7l-2 2"/><path d="M13.5 17.5l-1 1a4 4 0 0 1-5.7-5.7l2-2"/>',
    "search": '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.3-4.3"/>',
    "edit": '<path d="M14 5l5 5"/><path d="M4 20l1.2-4.2L15.5 5.5l3 3L8.2 18.8z"/>',
    "error": '<circle cx="12" cy="12" r="9"/><path d="M8.5 8.5l7 7M15.5 8.5l-7 7"/>',
    "success": '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5.5-6.5"/>',
}


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    for name, body in ICONS.items():
        svg = _HEAD + body + "</svg>"
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(svg)
    print(f"[done] 生成 {len(ICONS)} 个插件扩展 SVG -> {os.path.normpath(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
