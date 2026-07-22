"""命令注册表（单一事实来源）。

把原 main.py `_dispatch` 巨型 if 链、`_SUB_ALIASES` 两处重复的“子命令→处理器”
映射，收敛成一张声明式表。`_dispatch` 与 `_SUB_ALIASES` 都从这里派生，避免三处
手工维护漂移。

⚠️ 行为不变约束（重构第一阶段）：
- 触发正则 `@filter.regex(...)` **不**从本表自动生成。正则只枚举“可无空格粘连触发”
  的兼容子集；本表还含 status/no/me/vs/box 等英文或短别名。
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
    CommandSpec("状态", "_cmd_status", ("status",), cooldown=True, description="服务器在线人数/版本/运行时长/延迟", category="server"),
    CommandSpec("在线", "_cmd_players", ("玩家", "players"), cooldown=True, description="当前在线玩家及其等级列表", category="server"),
    CommandSpec("设置", "_cmd_settings", ("settings",), cooldown=True, description="世界规则/经验掉落等服务器倍率配置", category="server"),
    CommandSpec("统计", "_cmd_stats", ("stats",), cooldown=True, description="在线人数当前/峰值/近7天趋势", category="server"),
    CommandSpec("热力", "_cmd_heatmap", ("热力图", "在线热力", "热度", "heatmap"), cooldown=True, description="一天各时段在线热度,看几点人多", category="server"),
    CommandSpec("玩家战力榜", "_cmd_power_rank", ("玩家帕鲁战力榜", "玩家帕鲁战力", "玩家最强帕鲁", "全服战力榜", "服务器战力榜"), cooldown=True, description="全服玩家按自己帕鲁总战力排名", category="rank"),
    CommandSpec("战力榜", "_cmd_paldex_power", ("战力", "战力排行", "帕鲁战力", "帕鲁战力榜", "帕鲁战力排行", "最强帕鲁", "power"), cooldown=True, pass_args=True, description="全图鉴帕鲁按满级战力强弱排名", category="rank"),
    CommandSpec("闪光墙", "_cmd_shiny", ("闪光", "闪光帕鲁", "幸运帕鲁", "shiny", "lucky"), cooldown=True, description="本服已捕获的闪光(幸运)帕鲁墙", category="rank"),
    CommandSpec("头目墙", "_cmd_alpha", ("头目帕鲁", "alpha", "alpha墙", "头目收集"), cooldown=True, description="本服已捕获的头目(Alpha)帕鲁墙", category="rank"),
    CommandSpec("图鉴榜", "_cmd_dex_rank", ("图鉴排行", "收集榜", "图鉴收集", "图鉴收集榜", "dexrank"), cooldown=True, description="全服玩家按图鉴收集数量排名", category="rank"),
    CommandSpec("资产榜", "_cmd_wealth", ("身价榜", "财富榜", "土豪榜", "wealth"), cooldown=True, description="全服玩家按金钱/身价排名", category="rank"),
    CommandSpec("公会战力", "_cmd_guild_power", ("公会战力榜", "工会战力", "公会榜战力", "guildpower"), cooldown=True, description="各公会按成员帕鲁总战力排名", category="rank"),
    CommandSpec("更新公告", "_cmd_patchnotes", ("更新内容", "更新日志", "补丁说明", "patchnotes", "更新资讯"), cooldown=True, description="服务器最近一次更新/补丁内容", category="server"),
    CommandSpec("排行", "_cmd_rank", ("肝帝榜", "榜", "排行榜", "rank"), cooldown=True, pass_args=True, description="群友在线时长榜(本周/今日/总榜)", category="rank"),
    CommandSpec("帮助", "_cmd_help", ("help", "菜单"), pass_args=True, description="全部指令清单,加关键词可搜指令", category="misc"),

    # ---------------- 图鉴 / 配种 ----------------
    CommandSpec("图鉴", "_cmd_paldex", ("paldex",), cooldown=True, pass_args=True, description="查某帕鲁属性/技能/掉落/栖息地(加名字)", category="paldex"),
    CommandSpec("编号", "_cmd_pal_index", ("图鉴编号", "编号查询", "palid", "no"), cooldown=True, pass_args=True, description="按图鉴编号查对应帕鲁(加编号)", category="paldex"),
    CommandSpec("属性克制", "_cmd_element", ("克制", "属性", "克制图", "element"), cooldown=True, pass_args=True, description="属性相克关系图/按属性列出帕鲁", category="paldex"),
    CommandSpec("栖息区域", "_cmd_habitat", ("栖息地", "栖息", "分布", "habitat"), cooldown=True, pass_args=True, description="某帕鲁在地图上的野生出没点(加名字)", category="paldex"),
    CommandSpec("推荐词条", "_cmd_passrec", ("词条", "推荐", "passive"), cooldown=True, pass_args=True, description="某帕鲁值得保留的被动词条推荐(加名字)", category="paldex"),
    CommandSpec("词条查", "_cmd_passive_find", ("查词条", "词条帕鲁", "谁带词条", "passfind"), cooldown=True, pass_args=True, description="查你现有帕鲁里谁带某词条(加词条名)", category="player"),
    CommandSpec("词条大全", "_cmd_passive_dex", ("词条分类", "词条图鉴", "全部词条", "词条查询", "词条百科", "passivedex"), cooldown=True, pass_args=True, description="全部被动词条效果分类查询", category="paldex"),
    CommandSpec("觉醒", "_cmd_awakening", ("帕鲁觉醒", "觉醒系统", "awakening"), cooldown=True, pass_args=True, description="1.0觉醒系统:所需材料与强化机制", category="paldex"),
    CommandSpec("突变", "_cmd_mutation", ("突变配种", "突变系统", "特殊蛋糕", "mutation"), cooldown=True, pass_args=True, description="1.0突变配种机制与特殊蛋糕做法", category="paldex"),
    CommandSpec("主线", "_cmd_mainquest", ("主线任务", "mainquest"), cooldown=True, pass_args=True, description="主线任务流程与攻略", category="paldex"),
    CommandSpec("支线", "_cmd_subquest", ("支线任务", "subquest"), cooldown=True, pass_args=True, description="支线任务流程与攻略", category="paldex"),
    CommandSpec("任务", "_cmd_mission", ("任务攻略", "quest", "mission"), cooldown=True, pass_args=True, description="按名字查任务目标与攻略(加任务名)", category="paldex"),
    CommandSpec("塔主", "_cmd_boss", ("高塔", "tower"), cooldown=True, pass_args=True, extra=("塔主",), description="八大高塔塔主打法与推荐配队(加名字)", category="paldex"),
    CommandSpec("突袭", "_cmd_boss", ("突袭boss", "raid"), cooldown=True, pass_args=True, extra=("突袭",), description="突袭(Raid)BOSS打法与掉落(加名字)", category="paldex"),
    CommandSpec("竞技场", "_cmd_arena", ("竞技", "斗技场", "arena"), cooldown=True, pass_args=True, description="PVP竞技场规则与奖励", category="paldex"),
    CommandSpec("boss", "_cmd_boss", ("BOSS", "头目", "首领"), cooldown=True, pass_args=True, extra=("",), description="各类BOSS(头目/塔主/突袭)攻略入口", category="paldex"),
    CommandSpec("商人", "_cmd_merchant", ("商店", "merchant", "shop"), cooldown=True, pass_args=True, description="各类商人卖什么/在哪(加商人名)", category="paldex"),
    CommandSpec("哪里买", "_cmd_wheretobuy", ("哪买", "在哪买", "哪里有卖", "wheretobuy"), cooldown=True, pass_args=True, description="反查某物品能在哪个商人买到(加物品名)", category="paldex"),
    CommandSpec("技能果实", "_cmd_skillfruit", ("果实图鉴", "skillfruit"), cooldown=True, pass_args=True, description="1.0技能果实一览:各能学的主动技能", category="paldex"),
    CommandSpec("植入体查询", "_cmd_implant_num", ("植入体编号",), cooldown=True, pass_args=True, description="按编号查植入体(1.0,加编号)", category="paldex"),
    CommandSpec("植入体", "_cmd_implant", ("改造", "implant"), cooldown=True, pass_args=True, description="1.0植入体图鉴:改造效果与解锁(加名字)", category="paldex"),
    CommandSpec("世界树", "_cmd_worldtree", ("世界树boss", "最终boss", "worldtree"), cooldown=True, pass_args=True, description="1.0世界树最终BOSS专题攻略", category="paldex"),
    CommandSpec("1.0", "_cmd_v10", ("版本", "v10", "1.0内容", "1.0导览", "1.0总览"), cooldown=True, pass_args=True, description="1.0正式版新增内容与支持功能总览", category="paldex"),
    CommandSpec("技能", "_cmd_skill", ("主动技能", "skill"), cooldown=True, pass_args=True, description="主动技能数据:威力/属性/冷却(加技能名)", category="paldex"),
    CommandSpec("钓鱼", "_cmd_fishing", ("fishing", "钓"), cooldown=True, pass_args=True, description="钓鱼点位与能钓到的帕鲁/物品", category="paldex"),
    CommandSpec("工作", "_cmd_work", ("工作适性", "适性", "work"), cooldown=True, pass_args=True, description="按工作适性(采矿/搬运等)排帕鲁强弱", category="paldex"),
    CommandSpec("坐骑", "_cmd_mount", ("骑乘", "mount"), cooldown=True, pass_args=True, description="可骑乘帕鲁一览:地面/飞行/水上", category="paldex"),
    CommandSpec("对比", "_cmd_compare", ("比较", "compare", "vs"), cooldown=True, pass_args=True, description="两只帕鲁属性/工作/战力并排对比(加两名)", category="paldex"),
    CommandSpec("料理", "_cmd_cuisine", ("食物", "做菜", "cuisine", "food"), cooldown=True, pass_args=True, description="料理食谱:材料/效果/加成(加菜名)", category="paldex"),
    CommandSpec("武器", "_cmd_weapon", ("weapon",), cooldown=True, pass_args=True, description="武器数据:伤害/解锁科技/材料(加名字)", category="paldex"),
    CommandSpec("配种", "_cmd_breed", ("breed",), cooldown=True, pass_args=True, description="查两只帕鲁能配出什么后代(加两名)", category="paldex"),
    CommandSpec("反配种", "_cmd_reverse", ("反向配种", "反查配种", "反配", "反向", "reverse"), cooldown=True, pass_args=True, description="查某帕鲁由哪些亲代组合配出(加名字)", category="paldex"),
    CommandSpec("怎么配", "_cmd_breed_route", ("如何配", "配种路线", "配种链", "怎么配出", "route", "breedroute"), cooldown=True, pass_args=True, description="从常见帕鲁到目标帕鲁的配种路线(加名字)", category="paldex"),
    CommandSpec("配出谁", "_cmd_breed_out", ("能配谁", "能配出谁", "当亲代", "作为亲代", "正向配种", "breedout"), cooldown=True, pass_args=True, description="某帕鲁当亲代能配出的全部后代(加名字)", category="paldex"),
    CommandSpec("配种榜", "_cmd_breed_rank", ("配种排行榜", "配种排行", "能配榜", "breedrank"), cooldown=True, pass_args=True, description="能配出后代种类最多的帕鲁排名", category="paldex"),
    CommandSpec("配工种", "_cmd_breed_worksuit", ("配工作帕鲁", "按工种配", "工种配种", "worksuitbreed"), cooldown=True, pass_args=True, description="满足某工作适性等级的帕鲁及配法(加工作)", category="paldex"),
    CommandSpec("我可以配工种", "_cmd_my_breed_worksuit", ("我能配工种", "我配工种", "我可以配", "mybreedwork"), cooldown=True, pass_args=True, description="用你现有帕鲁规划配出某工种帕鲁(加工作)", category="player"),
    CommandSpec("继承", "_cmd_inherit", ("词条继承", "继承计算", "词条遗传", "遗传", "继承率", "inherit"), cooldown=True, pass_args=True, description="配种时词条(被动)遗传概率说明", category="paldex"),
    CommandSpec("哪里掉", "_cmd_drop", ("哪里爆", "掉落", "爆什么", "掉什么", "爆率", "drop"), cooldown=True, pass_args=True, description="某帕鲁/BOSS掉落什么及爆率(加名字)", category="paldex"),
    CommandSpec("获取", "_cmd_obtain", ("来源", "怎么获得", "获取方式", "特殊物品"), cooldown=True, pass_args=True, description="汇总物品的采集地图/掉落/制作/商店等全部来源", category="paldex"),
    CommandSpec("矿点", "_cmd_oremap", ("矿石地图", "矿点图", "矿脉", "矿石地点"), cooldown=True, pass_args=True, description="把矿石和特殊采集物的真实点位标到游戏地图", category="paldex"),
    CommandSpec("解剖", "_cmd_butcher", ("解体", "肢解", "解剖查询"), cooldown=True, pass_args=True, description="按帕鲁或物品反查解剖掉落", category="paldex"),
    CommandSpec("物品", "_cmd_item", ("道具", "item"), cooldown=True, pass_args=True, description="物品图鉴:用途/获取/合成(加物品名)", category="paldex"),
    CommandSpec("设施", "_cmd_facility", ("建筑", "facility", "building"), cooldown=True, pass_args=True, description="据点设施:功能/材料/解锁科技(加名字)", category="paldex"),
    CommandSpec("科技", "_cmd_tech", ("技术", "tech"), cooldown=True, pass_args=True, description="科技图鉴:解锁物/所需点数(加名字)", category="paldex"),
    CommandSpec("研究所", "_cmd_lab", ("研究", "实验室", "lab"), cooldown=True, pass_args=True, description="1.0研究所:研究项目与产出", category="paldex"),
    CommandSpec("材料路线", "_cmd_matroute", ("材料", "配方展开", "总材料", "matroute"), cooldown=True, pass_args=True, description="把配方递归展开成总原料清单(加物品名)", category="paldex"),
    CommandSpec("种属", "_cmd_genus", ("分类图鉴", "种族分类", "genus"), cooldown=True, pass_args=True, description="按种属(人形/鸟/四足/龙/鱼)分类浏览图鉴", category="paldex"),
    CommandSpec("科技树", "_cmd_techtree", ("科技路线", "解锁路线", "techtree"), cooldown=True, pass_args=True, description="按等级看科技/建造解锁顺序", category="paldex"),
    CommandSpec("牧场", "_cmd_ranch", ("牧场产出", "放牧", "家畜牧场", "ranch"), cooldown=True, pass_args=True, description="牧场帕鲁产出一览/按产物反查帕鲁", category="paldex"),
    CommandSpec("用途", "_cmd_matuse", ("材料用途", "能做什么", "matuse"), cooldown=True, pass_args=True, description="反查某材料能做哪些配方(加材料名)", category="paldex"),
    CommandSpec("地图收集", "_cmd_poimap", ("地图地标", "收集地图", "地标", "poimap"), cooldown=True, pass_args=True, description="把地标/传送点/禁猎区标到世界地图", category="paldex"),

    # ---------------- 玩家自助 ----------------
    CommandSpec("绑定", "_cmd_bind", ("bind",), pass_args=True, description="绑定你的游戏角色,才能查个人数据", category="player"),
    CommandSpec("我的战力", "_cmd_my_power", ("个人战力", "我的最强帕鲁", "我的帕鲁战力", "mypower"), cooldown=True, pass_args=True, description="你捕获的全部帕鲁按战力排名", category="player"),
    CommandSpec("养成", "_cmd_growth", ("培养", "养成进度", "养成路线", "growth"), cooldown=True, pass_args=True, description="你某只帕鲁的浓缩/魂/觉醒/词条差距(加名字)", category="player"),
    CommandSpec("小队进度", "_cmd_squad", ("小队", "squad", "team_progress"), cooldown=True, description="群内小队探索/收集的当前、总量与剩余进度", category="player"),
    CommandSpec("据点体检", "_cmd_basecamp_health", ("基地体检", "据点健康", "基地健康", "basehealth"), cooldown=True, pass_args=True, description="据点工人/适性缺口/伤病汇总(可加据点号)", category="player"),
    CommandSpec("小队勾选", "_cmd_squad_check", ("勾选", "squadcheck"), pass_args=True, description="手动勾选/记录一个小队探索目标", category="player"),
    CommandSpec("小队重置", "_cmd_squad_reset", ("squadreset",), admin=True, pass_args=True, log_denied=True, description="清空本群小队手动勾选清单(管理)", category="admin"),
    CommandSpec("我", "_cmd_profile", ("档案", "me"), cooldown=True, description="你的个人档案:等级/公会/帕鲁数等", category="player"),
    CommandSpec("背包", "_cmd_bag", ("物品栏", "bag", "inventory"), cooldown=True, pass_args=True, description="你角色背包里的物品清单", category="player"),
    CommandSpec("队伍", "_cmd_team", ("出战", "team", "party"), cooldown=True, pass_args=True, description="你当前携带出战的帕鲁队伍", category="player"),
    CommandSpec("箱查询", "_cmd_palbox_query", ("帕鲁箱查询", "箱子查询", "查帕鲁", "boxinfo"), cooldown=True, pass_args=True, description="在你帕鲁箱里按名字搜某只帕鲁(加名字)", category="player"),
    CommandSpec("箱", "_cmd_palbox", ("帕鲁箱", "箱子", "仓库", "palbox", "box"), cooldown=True, pass_args=True, description="你帕鲁箱里保存的全部帕鲁", category="player"),
    CommandSpec("可孵化", "_cmd_hatchable", ("可配种", "可配", "能配出", "孵化", "hatchable"), cooldown=True, pass_args=True, description="你现有帕鲁能两两配出的新种", category="player"),
    CommandSpec("据点", "_cmd_basecamp", ("基地", "据点帕鲁", "基地帕鲁", "工作帕鲁", "basecamp", "base"), cooldown=True, pass_args=True, description="你据点里干活的工作帕鲁一览", category="player"),
    CommandSpec("症状", "_cmd_symptom", ("伤病", "治疗", "怎么治", "cure", "symptom"), pass_args=True, description="帕鲁伤病(骨折/感冒等)怎么治(加症状)", category="player"),
    CommandSpec("公会榜", "_cmd_guild_rank", ("公会肝帝榜", "工会榜", "公会排行", "guildrank"), cooldown=True, description="本服各公会在线时长/活跃排名", category="guild"),
    CommandSpec("公会帕鲁", "_cmd_guild_pals", ("公会终端", "工会帕鲁", "公会帕鲁箱", "guildpals"), cooldown=True, pass_args=True, description="查某公会共享帕鲁箱(加公会名)", category="guild"),
    CommandSpec("公会", "_cmd_guild", ("工会", "guild"), cooldown=True, pass_args=True, description="公会信息:成员/据点/战力(加公会名)", category="guild"),
    CommandSpec("订阅", "_cmd_sub", ("sub",), pass_args=True, description="订阅玩家上下线播报到本群", category="player"),
    CommandSpec("退订", "_cmd_unsub", ("取消订阅", "unsub"), pass_args=True, description="取消上下线播报订阅", category="player"),
    CommandSpec("找人", "_cmd_find", ("查人", "find"), pass_args=True, description="查某玩家是否在线/上次在线(加名字)", category="player"),

    # ---------------- 互动 ----------------
    CommandSpec("喊话", "_cmd_shout", ("shout",), pass_args=True, description="以服务器名义向游戏内广播(加内容)", category="misc"),
    CommandSpec("喊", "_cmd_call", ("喊人", "call"), pass_args=True, description="在游戏里喊某玩家上线(加名字)", category="misc"),

    # ---------------- 二次确认 ----------------
    CommandSpec("确认", "_cmd_confirm", admin=True, log_denied=True,
                description="确认执行上一步高危操作", category="admin"),

    # ---------------- 管理审计 / 自检 / 地图（白名单，各自内联鉴权，拒绝不写警告日志） ----------------
    CommandSpec("审计", "_cmd_audit", ("日志", "audit"), admin=True, description="查看管理操作审计日志(管理)", category="admin"),
    CommandSpec("自检", "_cmd_selfcheck", ("诊断", "健康检查", "体检", "selfcheck", "healthcheck"), admin=True, description="插件部署/连接自检诊断(管理)", category="admin"),
    CommandSpec("地图", "_cmd_map", ("map",), admin=True, cooldown=True, description="在世界地图上标出在线玩家位置(管理)", category="admin"),

    # ---------------- 管理类（白名单，拒绝写警告日志） ----------------
    CommandSpec("重置存档", "_cmd_reset", ("删档重开", "删档", "重开", "重置世界", "resetworld", "reset"), admin=True, pass_args=True, confirm=True, log_denied=True, description="删档重开:清空世界存档(管理,需确认)", category="admin"),
    CommandSpec("恢复存档", "_cmd_restore", ("还原存档", "恢复", "还原", "restore"), admin=True, pass_args=True, confirm=True, log_denied=True, description="从备份恢复世界存档(管理,需确认)", category="admin"),
    CommandSpec("重启服务器", "_cmd_restart", ("重启服务", "重启", "restart", "reboot"), admin=True, pass_args=True, confirm=True, log_denied=True, description="重启游戏服务器(管理,需确认)", category="admin"),
    CommandSpec("备份列表", "_cmd_backups", ("备份", "备份管理", "backups", "backup"), admin=True, pass_args=True, log_denied=True, description="查看世界存档备份列表(管理)", category="admin"),
    CommandSpec("回档", "_cmd_rollback", ("回滚", "rollback"), admin=True, pass_args=True, confirm=True, log_denied=True, description="回滚到指定备份存档(管理,需确认)", category="admin"),
    CommandSpec("解绑", "_cmd_unbind", ("unbind",), admin=True, pass_args=True, log_denied=True, description="解除某玩家的角色绑定(管理)", category="admin"),
    CommandSpec("批准绑定", "_cmd_bind_approve", ("批准", "approvebind"), admin=True, pass_args=True, log_denied=True, description="批准挂起的角色绑定申请(管理)", category="admin"),
    CommandSpec("拒绝绑定", "_cmd_bind_reject", ("拒绝", "rejectbind"), admin=True, pass_args=True, log_denied=True, description="拒绝挂起的角色绑定申请(管理)", category="admin"),
    CommandSpec("公告", "_cmd_announce", admin=True, pass_args=True, log_denied=True, description="在游戏内发布服务器公告(管理,加内容)", category="admin"),
    CommandSpec("踢", "_cmd_kick", admin=True, pass_args=True, log_denied=True, description="把某玩家踢下线(管理,加名字)", category="admin"),
    CommandSpec("封", "_cmd_ban", admin=True, pass_args=True, log_denied=True, description="封禁某玩家(管理,加名字)", category="admin"),
    CommandSpec("解封", "_cmd_unban", admin=True, pass_args=True, log_denied=True, description="解除某玩家封禁(管理,加名字)", category="admin"),
    CommandSpec("存档", "_cmd_save", admin=True, pass_args=True, log_denied=True, description="立即强制保存世界存档(管理)", category="admin"),
    CommandSpec("关服", "_cmd_shutdown", admin=True, pass_args=True, log_denied=True, description="关闭游戏服务器(管理)", category="admin"),
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
