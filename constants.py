"""集中管理的常量与静态映射表（从 main.py 原样迁出，值未改）。
重构第一阶段：仅搬家，不改动任何数值/键名。"""
from __future__ import annotations


# ----------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------
LOG_PREFIX = "[帕鲁管家]"
# 删档重开时旧存档的备份目录(容器内)；/帕鲁恢复存档 从这里取最近一次备份还原
RESET_BACKUP_DIR = "/palworld/Pal/Saved/manual_resets"
# 镜像每天3点的备份(回档/份数上限对接这个)：/palworld/backups/palworld-save-2026-06-29_03-00-00.tar.gz
# 内含整个 Saved/(排除 backup 子目录)。稳定每天一份。
IMAGE_BACKUP_DIR = "/palworld/backups"
# 游戏引擎自带的高频内部快照(可选清理，避免占空间)：<世界GUID>/backup/world/<时间戳>/
BACKUP_WORLD_SUBDIR = "backup/world"
HARD_MIN_COOLDOWN = 5          # 查询冷却硬下限(秒)，§6 规定不低于 5s
DEFAULT_THEME = "#6366F1"      # 默认主题色(靛蓝紫)
DAY_MILESTONES = [7, 30, 50, 100, 150, 200, 300, 365, 500, 730, 1000]  # 世界天数里程碑

# 技能 element_type(英文) -> 中文(图鉴 elements 字段本身已是中文)
ELEM_CN = {"None": "无", "Normal": "无", "Fire": "火", "Water": "水", "Leaf": "草", "Grass": "草",
           "Electric": "雷", "Electricity": "雷", "Ice": "冰", "Earth": "地", "Ground": "地",
           "Dark": "暗", "Dragon": "龙"}
# 属性 -> emoji 图标(属性克制图/图鉴用)
ELEM_EMOJI = {"无": "⚪", "火": "🔥", "水": "💧", "草": "🌿", "雷": "⚡",
              "冰": "❄️", "地": "⛰️", "暗": "🌑", "龙": "🐉"}
# 工作适性键 -> 中文
WORK_LABELS = {"emit_flame": "点火", "watering": "浇水", "seeding": "播种", "generate_electricity": "发电",
               "handcraft": "手工", "collection": "采集", "deforest": "砍伐", "mining": "采矿",
               "oil_extraction": "采油", "product_medicine": "制药", "cool": "制冷",
               "transport": "搬运", "monster_farm": "牧场", "farming": "农活"}
# 工种中文/别名 -> work_suitability 键（/帕鲁工作 排行用）
WORK_ALIAS = {"采矿": "mining", "挖矿": "mining", "搬运": "transport", "运输": "transport",
              "手工": "handcraft", "制作": "handcraft", "手工制作": "handcraft", "采集": "collection",
              "砍伐": "deforest", "伐木": "deforest", "浇水": "watering", "灌溉": "watering",
              "发电": "generate_electricity", "制药": "product_medicine", "医疗": "product_medicine",
              "制冷": "cool", "牧场": "monster_farm", "农活": "farming", "种植": "seeding",
              "播种": "seeding", "采油": "oil_extraction", "点火": "emit_flame", "生火": "emit_flame"}
# 工作适性键 -> emoji 图标（帕鲁详情卡「工作适性」区用；近似游戏工种图标）
WORK_ICON = {"emit_flame": "🔥", "watering": "💧", "seeding": "🌱", "generate_electricity": "⚡",
             "handcraft": "🔨", "collection": "🧺", "deforest": "🪓", "mining": "⛏️",
             "oil_extraction": "🛢️", "product_medicine": "💊", "cool": "❄️",
             "transport": "📦", "monster_farm": "🐄", "farming": "🌾"}

# 生产类工作适性键(用于 /帕鲁推荐词条 判定「生产型」角色)
PROD_WORK_KEYS = {"emit_flame", "watering", "seeding", "generate_electricity", "handcraft",
                  "collection", "deforest", "mining", "oil_extraction", "product_medicine",
                  "cool", "farming", "monster_farm"}
# /帕鲁推荐词条：按角色推荐的高价值被动词条(取 passives.json 的 key)
PASS_UNIVERSAL = ["Legend", "PAL_ALLAttack_up3", "Vampire", "Deffence_up3"]
PASS_COMBAT = ["Legend", "PAL_ALLAttack_up3", "PAL_ALLAttack_up2", "Vampire"]
PASS_PRODUCE = ["CraftSpeed_up3", "CraftSpeed_up2", "Vampire", "PAL_Sanity_Down_3", "PAL_FullStomach_Down_3"]
PASS_TRANSPORT = ["MoveSpeed_up_3", "MoveSpeed_up_2", "Legend", "Vampire"]
# 元素 -> 该系最强增伤词条(战斗向首选)
PASS_ELEM_BOOST = {"火": "EternalFlame", "雷": "EternalFlame", "水": "Nushi", "冰": "Witch",
                   "暗": "Witch", "龙": "Invader", "草": "Salvation", "无": "Salvation",
                   "地": "ElementBoost_Earth_2_PAL"}
# 主要生物群系中心(世界坐标)，仅用于 /帕鲁栖息区域 的「出没区域」文字统计。
# 用精选大区而非 map_regions 的 117 个传送/地牢锚点(那些密集且偏小，就近统计会偏)。
MAJOR_BIOMES = {
    "初始台地": (-358785, 267940), "风起之丘": (-348495, 209450), "草巨兽山陵": (-342035, 236885),
    "飞鱼海岸": (-372422, 228769), "渡岛海岸": (-265980, 268690), "翠竹溪谷": (-267060, 52948),
    "草熊猫之森": (-177771, 265009), "彩蝶之森": (-248771, 126205), "弦月湖畔": (-219582, 155464),
    "新绿清流": (-129908, 253374), "日暮沙地": (-169806, 101247), "荒漠沙丘": (49259, 374264),
    "沙丘入口": (-50301, 287392), "沙丘深处": (117624, 400134), "黑曜火山": (-345832, -111428),
    "火山山脚": (-349536, -4036), "白银灵峰": (57835, 72692), "霜冻雪山": (-97566, 249169),
    "永冻湖": (8000, 111770), "寒水之滨": (-119038, 138340), "绝对零度之域": (102159, 48527),
    "樱花岛·南部砂原": (-86710, -140442), "樱花岛·蘑菇湿地": (-63521, -55006), "樱花岛·北部矿场": (32787, -81421),
    "潮风群岛": (-416795, 71680), "常夏孤岛": (-496120, -36566), "极冻孤岛": (-558411, 121112),
    "古代文明遗址": (-414447, -24604), "黄土平原": (-792350, -251110), "锈灰高原": (-591120, -484261),
    "余烬熔岩台": (-671902, -172408),
}
# 物品类型 -> 中文(物品图鉴用，未列的回退原值)
ITEM_TYPE_CN = {"Money": "货币", "Material": "材料", "Food": "食物", "Ingredient": "食材",
                "Weapon": "武器", "Armor": "防具", "Accessory": "饰品", "Consume": "消耗品",
                "Ammo": "弹药", "Glider": "滑翔翼", "PalSphere": "帕鲁球", "SphereModule": "球强化",
                "Medicine": "药品", "Seed": "种子", "Blueprint": "图纸", "Essential": "重要物品",
                "Egg": "蛋", "Ore": "矿石", "Ingot": "锭", "Gem": "宝石", "Cloth": "布料",
                "Drug": "药品", "Coin": "货币", "ExpItem": "经验道具", "Technology": "科技书"}
# 物品大类(菜单顺序 + 图标)。归类逻辑见 _item_category。
ITEM_CAT_META = [("武器", "🗡️"), ("防具", "🛡️"), ("饰品", "💍"), ("帕鲁装备", "🎽"),
                 ("食物", "🍖"), ("材料", "🧱"), ("消耗品", "🧪"), ("捕获球", "⚪"),
                 ("蓝图", "📐"), ("重要物品", "✨"), ("其它", "📦")]
CARD_WIDTH = 540              # 卡片逻辑设计宽度(px)，手机竖版
TEAM_WIDTH = 920              # 队伍卡加宽：2 列布局降低高宽比，避免高图被 QQ 缩窄留边
MAP_WIDTH = 760              # 地图卡加宽 + 高 dsf，用 8192² 游戏原图出高清地图（仅 /帕鲁地图）
SUPERSCALE = 2               # 超采样倍率：CSS zoom 把整版面放大 N 倍再渲染，文字按更大尺寸
GRID_COLS = 5                # 图鉴/物品/设施/科技 网格列表每行格子数
GRID_PAGE_SIZE = 30          # 网格列表每页格子数(5×6)，超出自动分页
PALBOX_PAGE_SIZE = 28        # 帕鲁箱每页格子数(4×7)，超出翻页
BAG_PAGE_SIZE = 32           # 背包每页格子数(4×8)，超出翻页，避免囤货玩家超长图
BASECAMP_PAGE_SIZE = 10      # 据点每页帕鲁数(详情行较高)，超出翻页
GUILD_PAGE_SIZE = 20         # 公会成员每页人数(单行)，超出翻页
                             # 重新栅格化 → 放大也清晰。最终像素 = 540×N×ultra(1.8)。N=2→1944px宽。

# html_render 选项：
# - viewport_width = 540×SUPERSCALE，与模板里的 zoom 同步放大，避免缩左上角/留白。
#   必须同时提供 viewport_height，否则自建 t2i 服务不设自定义视口宽度(退回默认 1280，
#   导致卡片右侧露出底图)。
# - full_page 让高度按内容延伸。
# - device_scale_factor_level=ultra(本机上限,1.8x)叠加 zoom，进一步提清晰度。
# - type=png 无损，避免 jpeg 压缩把文字边缘压糊(这是“放大就糊”的主因之一)。
# 本机 AstrBot 官方 t2i 端点已验证支持这些键(参考 group_activity 插件)。
RENDER_OPTIONS = {
    "full_page": True,
    "type": "png",
    "scale": "device",
    "device_scale_factor_level": "ultra",
    "viewport_width": CARD_WIDTH * SUPERSCALE,
    # 自建 t2i 服务要求 viewport 宽高都给才会设自定义视口(只给宽会退回默认1280宽→
    # 卡片1080露右侧底图)。高度只为触发设视口，成图高度仍由 full_page 撑开。
    "viewport_height": 720,
}


# 设置卡要展示的字段：(中文标签, settings 键, 单位/后缀)
SETTINGS_FIELDS = [
    ("难度", "Difficulty", ""),
    ("经验倍率", "ExpRate", "x"),
    ("捕捉倍率", "PalCaptureRate", "x"),
    ("帕鲁出现率", "PalSpawnNumRate", "x"),
    ("掉落数量", "DropItemMaxNum", ""),
    ("采集倍率", "CollectionDropRate", "x"),
    ("玩家攻击", "PlayerDamageRateAttack", "x"),
    ("玩家受伤", "PlayerDamageRateDefense", "x"),
    ("帕鲁攻击", "PalDamageRateAttack", "x"),
    ("工作速度", "WorkSpeedRate", "x"),
    ("白天速度", "DayTimeSpeedRate", "x"),
    ("夜晚速度", "NightTimeSpeedRate", "x"),
    ("死亡惩罚", "DeathPenalty", ""),
]
