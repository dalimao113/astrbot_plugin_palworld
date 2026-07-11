"""命令注册表（单一事实来源）。

把原 main.py `_dispatch` 巨型 if 链、`_SUB_ALIASES` 两处重复的“子命令→处理器”
映射，收敛成一张声明式表。`_dispatch` 与 `_SUB_ALIASES` 都从这里派生，避免三处
手工维护漂移。

⚠️ 行为不变约束（重构第一阶段）：
- 触发正则 `@filter.regex(...)` **不**从本表自动生成。正则只枚举“可无空格粘连触发”
  的子集（247 项）；本表含全部别名（含 status/no/me/vs/box 等英文/短别名，共 292 项）。
  若用全表重建正则，会让 `帕鲁status`、`帕鲁note`(→编号 no) 等新触发，属行为变更且易误触发。
  故正则保持字面量。见 main.py 中 `palworld` 处理器上方注释。
- 冷却语义：原 `_pass_cooldown` 恒 True（等于不限流），此处仅忠实保留“是否调用冷却门”。
- 二次确认(confirm)：原实现由各 handler 内部 `_pending` 处理，本表 confirm 仅作元信息，
  不改变分发行为。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandSpec:
    canonical: str                       # 规范名（拒绝日志/帮助展示用）
    handler: str                         # PalworldPlugin 上的方法名
    aliases: tuple = ()                  # 其余别名（含中文/英文）
    admin: bool = False                  # 需白名单管理员
    cooldown: bool = False               # 是否经过 _pass_cooldown 门
    pass_args: bool = False              # handler 是否接收 args 位置参数
    extra: tuple = ()                    # args 之后的额外定位参数（如 boss 的分类）
    confirm: bool = False                # 仅元信息：handler 内部有二次确认
    log_denied: bool = False             # 非管理员被拒时是否 logger.warning（原 admin_subs 组会）
    description: str = ""                # 帮助/文档用（未来可驱动帮助卡）
    category: str = ""

    @property
    def tokens(self) -> tuple:
        return (self.canonical, *self.aliases)


# 顺序仅影响帮助/文档展示，不影响分发（分发走别名 map）。
COMMANDS: list[CommandSpec] = [
    # ---------------- 查询类（全员，受冷却） ----------------
    CommandSpec("状态", "_cmd_status", ("status",), cooldown=True, description="查看服务器状态", category="server"),
    CommandSpec("在线", "_cmd_players", ("玩家", "players"), cooldown=True, description="查看在线玩家", category="server"),
    CommandSpec("设置", "_cmd_settings", ("settings",), cooldown=True, description="查看服务器设置", category="server"),
    CommandSpec("统计", "_cmd_stats", ("stats",), cooldown=True, description="查看统计", category="server"),
    CommandSpec("热力", "_cmd_heatmap", ("热力图", "在线热力", "热度", "heatmap"), cooldown=True, description="在线热力图", category="server"),
    CommandSpec("战力榜", "_cmd_power_rank", ("战力", "最强帕鲁", "战力排行", "power"), cooldown=True, description="战力排行", category="rank"),
    CommandSpec("闪光墙", "_cmd_shiny", ("闪光", "闪光帕鲁", "幸运帕鲁", "shiny", "lucky"), cooldown=True, description="闪光帕鲁墙", category="rank"),
    CommandSpec("头目墙", "_cmd_alpha", ("头目帕鲁", "alpha", "alpha墙", "头目收集"), cooldown=True, description="头目收集墙", category="rank"),
    CommandSpec("图鉴榜", "_cmd_dex_rank", ("图鉴排行", "收集榜", "图鉴收集", "图鉴收集榜", "dexrank"), cooldown=True, description="图鉴收集榜", category="rank"),
    CommandSpec("资产榜", "_cmd_wealth", ("身价榜", "财富榜", "土豪榜", "wealth"), cooldown=True, description="资产排行", category="rank"),
    CommandSpec("公会战力", "_cmd_guild_power", ("公会战力榜", "工会战力", "公会榜战力", "guildpower"), cooldown=True, description="公会战力榜", category="rank"),
    CommandSpec("更新公告", "_cmd_patchnotes", ("更新内容", "更新日志", "补丁说明", "patchnotes", "更新资讯"), cooldown=True, description="服务器更新公告", category="server"),
    CommandSpec("排行", "_cmd_rank", ("肝帝榜", "榜", "排行榜", "rank"), cooldown=True, description="肝帝榜", category="rank"),
    CommandSpec("帮助", "_cmd_help", ("help", "菜单"), description="帮助菜单", category="misc"),

    # ---------------- 图鉴 / 配种 ----------------
    CommandSpec("图鉴", "_cmd_paldex", ("paldex",), cooldown=True, pass_args=True, description="帕鲁图鉴", category="paldex"),
    CommandSpec("编号", "_cmd_pal_index", ("图鉴编号", "编号查询", "palid", "no"), cooldown=True, pass_args=True, description="按图鉴编号查询", category="paldex"),
    CommandSpec("属性克制", "_cmd_element", ("克制", "属性", "克制图", "element"), cooldown=True, description="属性克制图", category="paldex"),
    CommandSpec("栖息区域", "_cmd_habitat", ("栖息地", "栖息", "分布", "habitat"), cooldown=True, pass_args=True, description="帕鲁栖息区域", category="paldex"),
    CommandSpec("推荐词条", "_cmd_passrec", ("词条", "推荐", "passive"), cooldown=True, pass_args=True, description="推荐被动词条", category="paldex"),
    CommandSpec("主线", "_cmd_mainquest", ("主线任务", "mainquest"), cooldown=True, pass_args=True, description="主线任务攻略", category="paldex"),
    CommandSpec("支线", "_cmd_subquest", ("支线任务", "subquest"), cooldown=True, pass_args=True, description="支线任务攻略", category="paldex"),
    CommandSpec("任务", "_cmd_mission", ("任务攻略", "quest", "mission"), cooldown=True, pass_args=True, description="任务攻略", category="paldex"),
    CommandSpec("塔主", "_cmd_boss", ("高塔", "tower"), cooldown=True, pass_args=True, extra=("塔主",), description="塔主攻略", category="paldex"),
    CommandSpec("突袭", "_cmd_boss", ("突袭boss", "raid"), cooldown=True, pass_args=True, extra=("突袭",), description="突袭 BOSS 攻略", category="paldex"),
    CommandSpec("竞技场", "_cmd_arena", ("竞技", "斗技场", "arena"), cooldown=True, pass_args=True, description="竞技场", category="paldex"),
    CommandSpec("boss", "_cmd_boss", ("BOSS", "头目", "首领"), cooldown=True, pass_args=True, extra=("",), description="BOSS 攻略", category="paldex"),
    CommandSpec("商人", "_cmd_merchant", ("商店", "merchant", "shop"), cooldown=True, pass_args=True, description="商人", category="paldex"),
    CommandSpec("哪里买", "_cmd_wheretobuy", ("哪买", "在哪买", "哪里有卖", "wheretobuy"), cooldown=True, pass_args=True, description="哪里购买物品", category="paldex"),
    CommandSpec("技能果实", "_cmd_skillfruit", ("果实图鉴", "skillfruit"), cooldown=True, pass_args=True, description="技能果实图鉴(1.0)", category="paldex"),
    CommandSpec("技能", "_cmd_skill", ("主动技能", "skill"), cooldown=True, pass_args=True, description="主动技能", category="paldex"),
    CommandSpec("钓鱼", "_cmd_fishing", ("fishing", "钓"), cooldown=True, pass_args=True, description="钓鱼", category="paldex"),
    CommandSpec("工作", "_cmd_work", ("工作适性", "适性", "work"), cooldown=True, pass_args=True, description="工作适性排行", category="paldex"),
    CommandSpec("坐骑", "_cmd_mount", ("骑乘", "mount"), cooldown=True, pass_args=True, description="坐骑", category="paldex"),
    CommandSpec("对比", "_cmd_compare", ("比较", "compare", "vs"), cooldown=True, pass_args=True, description="帕鲁对比", category="paldex"),
    CommandSpec("料理", "_cmd_cuisine", ("食物", "做菜", "cuisine", "food"), cooldown=True, pass_args=True, description="料理", category="paldex"),
    CommandSpec("武器", "_cmd_weapon", ("weapon",), cooldown=True, pass_args=True, description="武器", category="paldex"),
    CommandSpec("配种", "_cmd_breed", ("breed",), cooldown=True, pass_args=True, description="配种", category="paldex"),
    CommandSpec("反配种", "_cmd_reverse", ("反向配种", "反查配种", "反配", "反向", "reverse"), cooldown=True, pass_args=True, description="反向配种", category="paldex"),
    CommandSpec("怎么配", "_cmd_breed_route", ("如何配", "配种路线", "配种链", "怎么配出", "route", "breedroute"), cooldown=True, pass_args=True, description="配种路线", category="paldex"),
    CommandSpec("继承", "_cmd_inherit", ("词条继承", "继承计算", "词条遗传", "遗传", "继承率", "inherit"), cooldown=True, pass_args=True, description="词条继承率", category="paldex"),
    CommandSpec("哪里掉", "_cmd_drop", ("哪里爆", "掉落", "爆什么", "掉什么", "爆率", "drop"), cooldown=True, pass_args=True, description="掉落查询", category="paldex"),
    CommandSpec("物品", "_cmd_item", ("道具", "item"), cooldown=True, pass_args=True, description="物品图鉴", category="paldex"),
    CommandSpec("设施", "_cmd_facility", ("建筑", "facility", "building"), cooldown=True, pass_args=True, description="设施图鉴", category="paldex"),
    CommandSpec("科技", "_cmd_tech", ("技术", "tech"), cooldown=True, pass_args=True, description="科技图鉴", category="paldex"),
    CommandSpec("研究所", "_cmd_lab", ("研究", "实验室", "lab"), cooldown=True, pass_args=True, description="研究所图鉴(1.0)", category="paldex"),

    # ---------------- 玩家自助 ----------------
    CommandSpec("绑定", "_cmd_bind", ("bind",), pass_args=True, description="绑定游戏角色", category="player"),
    CommandSpec("我", "_cmd_profile", ("档案", "me"), cooldown=True, description="我的档案", category="player"),
    CommandSpec("背包", "_cmd_bag", ("物品栏", "bag", "inventory"), cooldown=True, pass_args=True, description="我的背包", category="player"),
    CommandSpec("队伍", "_cmd_team", ("出战", "team", "party"), cooldown=True, pass_args=True, description="我的出战队伍", category="player"),
    CommandSpec("箱查询", "_cmd_palbox_query", ("帕鲁箱查询", "箱子查询", "查帕鲁", "boxinfo"), cooldown=True, pass_args=True, description="帕鲁箱查询", category="player"),
    CommandSpec("箱", "_cmd_palbox", ("帕鲁箱", "箱子", "仓库", "palbox", "box"), cooldown=True, pass_args=True, description="我的帕鲁箱", category="player"),
    CommandSpec("可孵化", "_cmd_hatchable", ("可配种", "可配", "能配出", "孵化", "hatchable"), cooldown=True, pass_args=True, description="可孵化配种", category="player"),
    CommandSpec("据点", "_cmd_basecamp", ("基地", "据点帕鲁", "基地帕鲁", "工作帕鲁", "basecamp", "base"), cooldown=True, pass_args=True, description="据点工作帕鲁", category="player"),
    CommandSpec("症状", "_cmd_symptom", ("伤病", "治疗", "怎么治", "cure", "symptom"), pass_args=True, description="伤病治疗", category="player"),
    CommandSpec("公会榜", "_cmd_guild_rank", ("公会肝帝榜", "工会榜", "公会排行", "guildrank"), cooldown=True, description="公会肝帝榜", category="guild"),
    CommandSpec("公会帕鲁", "_cmd_guild_pals", ("公会终端", "工会帕鲁", "公会帕鲁箱", "guildpals"), cooldown=True, pass_args=True, description="公会帕鲁箱", category="guild"),
    CommandSpec("公会", "_cmd_guild", ("工会", "guild"), cooldown=True, pass_args=True, description="公会信息", category="guild"),
    CommandSpec("订阅", "_cmd_sub", ("sub",), pass_args=True, description="订阅上下线播报", category="player"),
    CommandSpec("退订", "_cmd_unsub", ("取消订阅", "unsub"), pass_args=True, description="退订播报", category="player"),
    CommandSpec("找人", "_cmd_find", ("查人", "find"), pass_args=True, description="找人", category="player"),

    # ---------------- 互动 ----------------
    CommandSpec("喊话", "_cmd_shout", ("shout",), pass_args=True, description="向服务器喊话", category="misc"),
    CommandSpec("喊", "_cmd_call", ("喊人", "call"), pass_args=True, description="喊人上线", category="misc"),

    # ---------------- 二次确认 ----------------
    CommandSpec("确认", "_cmd_confirm", description="确认高危操作", category="admin"),

    # ---------------- 管理审计 / 自检 / 地图（白名单，各自内联鉴权，拒绝不写警告日志） ----------------
    CommandSpec("审计", "_cmd_audit", ("日志", "audit"), admin=True, description="管理操作审计", category="admin"),
    CommandSpec("自检", "_cmd_selfcheck", ("诊断", "健康检查", "体检", "selfcheck", "healthcheck"), admin=True, description="部署自检诊断", category="admin"),
    CommandSpec("地图", "_cmd_map", ("map",), admin=True, cooldown=True, description="在线玩家地图", category="admin"),

    # ---------------- 管理类（白名单，拒绝写警告日志） ----------------
    CommandSpec("重置存档", "_cmd_reset", ("删档重开", "删档", "重开", "重置世界", "resetworld", "reset"), admin=True, pass_args=True, confirm=True, log_denied=True, description="删档重开", category="admin"),
    CommandSpec("恢复存档", "_cmd_restore", ("还原存档", "恢复", "还原", "restore"), admin=True, pass_args=True, confirm=True, log_denied=True, description="恢复存档", category="admin"),
    CommandSpec("重启服务器", "_cmd_restart", ("重启服务", "重启", "restart", "reboot"), admin=True, pass_args=True, confirm=True, log_denied=True, description="重启服务器", category="admin"),
    CommandSpec("备份列表", "_cmd_backups", ("备份", "备份管理", "backups", "backup"), admin=True, pass_args=True, log_denied=True, description="备份列表", category="admin"),
    CommandSpec("回档", "_cmd_rollback", ("回滚", "rollback"), admin=True, pass_args=True, confirm=True, log_denied=True, description="回档到备份", category="admin"),
    CommandSpec("解绑", "_cmd_unbind", ("unbind",), admin=True, pass_args=True, log_denied=True, description="解绑角色", category="admin"),
    CommandSpec("公告", "_cmd_announce", admin=True, pass_args=True, log_denied=True, description="发服务器公告", category="admin"),
    CommandSpec("踢", "_cmd_kick", admin=True, pass_args=True, log_denied=True, description="踢出玩家", category="admin"),
    CommandSpec("封", "_cmd_ban", admin=True, pass_args=True, log_denied=True, description="封禁玩家", category="admin"),
    CommandSpec("解封", "_cmd_unban", admin=True, pass_args=True, log_denied=True, description="解封玩家", category="admin"),
    CommandSpec("存档", "_cmd_save", admin=True, pass_args=True, log_denied=True, description="强制存档", category="admin"),
    CommandSpec("关服", "_cmd_shutdown", admin=True, pass_args=True, log_denied=True, description="关闭服务器", category="admin"),
]


def build_alias_map(commands: list[CommandSpec]) -> dict:
    """token -> CommandSpec。重复别名直接抛错（满足“别名表不重复”要求）。"""
    amap: dict = {}
    for spec in commands:
        for tok in spec.tokens:
            if tok in amap:
                raise ValueError(
                    f"命令别名重复: {tok!r} 同时属于 {amap[tok].canonical!r} 和 {spec.canonical!r}")
            amap[tok] = spec
    return amap


ALIAS_MAP: dict = build_alias_map(COMMANDS)
COMMAND_TOKENS: frozenset = frozenset(ALIAS_MAP)
