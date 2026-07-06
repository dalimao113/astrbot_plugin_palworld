"""配置默认值 + 类型化取值 + 合法性校验（集中管理）。

设计原则（重构第一阶段）：
- `DEFAULTS` 是所有配置项默认值的**规范单一来源**，必须与 `_conf_schema.json` 的
  default 逐项相等（由 tests 守护，防止两边漂移）。
- 本模块**不**改变 main.py 现有取值表达式的语义（那些散落的 `config.get(key, 字面量)`
  行为各有细节，逐一替换风险大）；它提供规范默认值、类型化 getter（供新代码/测试用）、
  以及启动时的合法性校验，输出清晰的中文提示，绝不因校验失败阻断插件加载。
- `HARD_MIN` 记录各项的硬下限（与 main.py 里已有的 max(...) clamp 一致），集中留档。
"""
from __future__ import annotations

import re

# 配置项默认值：规范单一来源，与 _conf_schema.json 的 default 必须一致。
DEFAULTS: dict = {
    # --- 连接 / 认证 ---
    "api_base": "http://palworld-server:8212",
    "admin_password": "",
    "admin_qq": [],
    "request_timeout": 5,
    # --- 交互 / 冷却 / 外观 ---
    "query_cooldown": 10,
    "confirm_timeout": 60,
    "card_theme_color": "#6366F1",
    "card_style": "fantasy",
    # --- 后台播报 ---
    "enable_broadcast": True,
    "poll_interval": 60,
    "broadcast_groups": [],
    "notify_player_join_left": True,
    "notify_server_down": True,
    "offline_alert_threshold": 2,
    "notify_record": True,
    "notify_milestone": True,
    "quiet_hours": "",
    "fps_alert_threshold": 0,
    "notify_settings_change": False,
    "daily_reboot_time": "",
    "notify_server_update": True,
    "update_check_hours": 6,
    # --- 备份 ---
    "backup_keep_max": 0,        # 修正：旧代码兜底误为 20，与 schema/hint(0=交给镜像) 不符
    "engine_backup_keep": 30,
    # --- 定时报告 ---
    "morning_report_time": "09:00",
    "evening_report_time": "21:00",
    "weekly_settle_time": "10:00",
    # --- 喊话 ---
    "enable_shout": True,
    "shout_cooldown": 30,
    # --- 容器 / 存档 ---
    "enable_host_stats": True,
    "docker_container": "palworld-server",
    "docker_sock": "/var/run/docker.sock",
    "save_dir_in_container": "",
    "save_cache_ttl": 120,
    "local_render": False,       # 修正：旧代码兜底误为 True，与 schema/hint(默认关闭) 不符
    "prewarm_save": True,
    # --- 内部性能参数（补入 schema，让用户可调） ---
    "force_save_min_interval": 15,
    "save_neg_ttl": 45,
}

# 硬下限：与 main.py 里已有的 max(...) clamp 保持一致，集中留档。
HARD_MIN: dict = {
    "query_cooldown": 5,
    "poll_interval": 20,
    "offline_alert_threshold": 1,
    "shout_cooldown": 5,
    "save_cache_ttl": 20,
    "save_neg_ttl": 10,
    "force_save_min_interval": 0,
}


# ---------------------------------------------------------------------------
# 类型化取值（供新代码/测试使用；不强制替换 main.py 现有表达式）
# ---------------------------------------------------------------------------
def get_int(cfg, key: str) -> int:
    """按 DEFAULTS 兜底取整数，并套用 HARD_MIN 下限（若有）。取值异常回退默认。"""
    default = DEFAULTS.get(key, 0)
    try:
        val = int(cfg.get(key, default))
    except (TypeError, ValueError):
        val = int(default)
    lo = HARD_MIN.get(key)
    return max(val, lo) if lo is not None else val


def get_bool(cfg, key: str) -> bool:
    return bool(cfg.get(key, DEFAULTS.get(key, False)))


def get_str(cfg, key: str) -> str:
    val = cfg.get(key, DEFAULTS.get(key, ""))
    return "" if val is None else str(val)


def get_list(cfg, key: str) -> list:
    """取字符串列表，逐项 strip 去空（QQ/群号白名单常用）。"""
    raw = cfg.get(key, DEFAULTS.get(key, [])) or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(x).strip() for x in raw if str(x).strip()]


# ---------------------------------------------------------------------------
# 合法性校验：返回中文提示列表（level, message）。level: "错误" / "警告" / "提示"。
# 只提示、不抛异常，避免因配置问题导致插件加载失败。
# ---------------------------------------------------------------------------
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")          # HH:MM
_QUIET_RE = re.compile(r"^([01]?\d|2[0-3])-([01]?\d|2[0-3])$")  # HH-HH
_CONTAINER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")     # docker 容器名规则


def validate_config(cfg) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def g(key):
        return cfg.get(key, DEFAULTS.get(key))

    # 认证 / 管理员
    if not get_str(cfg, "admin_password"):
        out.append(("警告", "未配置 admin_password：REST API 认证会失败，"
                            "状态/在线/公告/踢封等都无法工作。"))
    admins = get_list(cfg, "admin_qq")
    if not admins:
        out.append(("警告", "未配置 admin_qq 白名单：公告/踢/封/解封/存档/关服/重启/回档 "
                            "等管理指令将无人可用。"))
    for q in admins:
        if not q.isdigit():
            out.append(("警告", f"admin_qq 含非纯数字项「{q}」，QQ 号应为纯数字。"))
    for gid in get_list(cfg, "broadcast_groups"):
        if not gid.isdigit():
            out.append(("警告", f"broadcast_groups 含非纯数字项「{gid}」，群号应为纯数字。"))

    # api_base
    api = get_str(cfg, "api_base")
    if not re.match(r"^https?://", api):
        out.append(("错误", f"api_base「{api}」格式不对，必须以 http:// 或 https:// 开头。"))

    # docker
    container = get_str(cfg, "docker_container")
    if container and not _CONTAINER_RE.match(container):
        out.append(("警告", f"docker_container「{container}」不像合法容器名"
                            "（应为字母数字开头，仅含 字母数字 _ . -）。"))
    sock = get_str(cfg, "docker_sock")
    if sock and not sock.startswith("/"):
        out.append(("警告", f"docker_sock「{sock}」应为绝对路径（以 / 开头）。"))
    save_dir = get_str(cfg, "save_dir_in_container")
    if save_dir and not save_dir.startswith("/"):
        out.append(("警告", f"save_dir_in_container「{save_dir}」应为容器内绝对路径（以 / 开头），"
                            "留空可自动探测。"))

    # 时间格式
    for key in ("morning_report_time", "evening_report_time",
                "weekly_settle_time", "daily_reboot_time"):
        val = get_str(cfg, key)
        if val and not _TIME_RE.match(val):
            out.append(("警告", f"{key}「{val}」格式应为 HH:MM（如 09:00），留空=关闭。"))
    quiet = get_str(cfg, "quiet_hours")
    if quiet and not _QUIET_RE.match(quiet):
        out.append(("警告", f"quiet_hours「{quiet}」格式应为 HH-HH（如 23-8），留空=不启用。"))

    # card_style
    style = get_str(cfg, "card_style")
    if style and style not in ("fantasy", "pixel"):
        out.append(("提示", f"card_style「{style}」未知，将回退 fantasy。"))

    # 被 clamp 的项，提示实际生效值
    for key, lo in HARD_MIN.items():
        try:
            raw = int(cfg.get(key, DEFAULTS[key]))
        except (TypeError, ValueError):
            continue
        if raw < lo:
            out.append(("提示", f"{key}={raw} 低于硬下限 {lo}，将按 {lo} 生效。"))

    return out
