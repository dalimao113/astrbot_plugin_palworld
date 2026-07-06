"""输入长度限制与清洗（安全增强，任务八 §9）。

目的：防止超长/超多/含控制字符的用户输入被广播到游戏内、进入卡片渲染或正则匹配，
造成刷屏、渲染撑大、正则回溯等自伤式 DoS。正常中文/英文输入远短于这些上限，不受影响。

配合已有防护：HTML 转义(utils.text._esc)、tar 路径穿越(api.docker_api)、解压炸弹上限
(palwork.palsave)、管理员白名单 + 二次确认(commands.router/_dispatch)。
"""
from __future__ import annotations

import re

# 各类自由文本上限（字符数）
MAX_SHOUT = 100        # 群→游戏 喊话内容
MAX_ANNOUNCE = 500     # 管理员公告
MAX_NAME = 64          # 角色名 / 喊人目标名
MAX_REASON = 200       # 踢/封 理由
MAX_USERID = 64        # 玩家 userId
MAX_ARG = 200          # 单个指令参数通用上限
MAX_ARGS = 20          # 参数个数上限

# 控制字符（保留 \t \n）：回车/退格/转义等可用于伪造多行、刷屏、覆盖显示。
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clip(text, limit: int) -> str:
    """去除控制字符并截断到 limit 字符。None→''。用于广播/显示的自由文本。"""
    s = _CTRL_RE.sub("", str(text if text is not None else ""))
    return s[:limit]


def clamp_args(args, per: int = MAX_ARG, maxn: int = MAX_ARGS) -> list:
    """指令参数的全局兜底：最多 maxn 个，每个截断到 per 字符（去控制字符）。

    宽松上限，正常查询参数不受影响；仅拦截异常超长/超多参数。"""
    if not args:
        return []
    return [_CTRL_RE.sub("", str(a))[:per] for a in list(args)[:maxn]]
