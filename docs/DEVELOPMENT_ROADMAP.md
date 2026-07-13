# 开发路线图 · DEVELOPMENT_ROADMAP

> 状态基于**当前代码 + git 历史验证**,不按描述盲填。最后核对版本:**1.8.10**。
> 状态标记:`未开始` / `进行中` / `已完成` / `已阻塞`。

## 总体方向

| # | 方向 | 状态 |
|---|---|---|
| 1 | 实用型功能优化 | ✅ 已完成(阶段2,v1.8.5) |
| 2 | Palworld 1.0 数据适配 | ✅ 已完成(阶段3,v1.8.6–1.8.10) |
| 3 | 独立 ingame 游戏原生主题 | 🟢 主体完成(56/56 卡已转,待截图做视觉精校) |
| 4 | 全页面游戏图标替换 | 🟢 主体完成(真实游戏图标全覆盖 + 插件扩展 SVG;剩动态标题/message icon 去 Emoji) |
| 5 | 游戏数据与素材自动生成工具 | 🟡 部分(提取脚本在仓库外 `/opt/palworld-khd/work`,未收进 `tools/game_data/`) |

---

## 已完成(代码已验证)

### 方向1 · 实用型优化(v1.8.5)
- `query_cooldown` 生效:`_pass_cooldown` 用户级冷却,配 0 可关(此前恒 True)。
- `terminate` 生命周期:cancel 后 await 任务退出,再关 aiohttp/Playwright。
- `state.json`:加 `state_version` + 缺失字段补全 + 损坏副本保留(仍原子写,未迁移数据库)。
- 版本 5 处统一 + CHANGELOG 补齐 1.3.0–1.8.4;`test_version` 扩展检查 README 徽章 + CHANGELOG。
- README 补角色绑定"熟人私人群信任机制"说明。

### 方向2 · 1.0 数据适配(v1.8.6–1.8.10)
- **帕鲁口径**:DT `ZukanIndex`/`IsPal` 权威定位 **287 可收集 / 289 实体**,差 2(枯星龙+花叶泥泥)标记不删,派生 `is_collectible`/`is_variant`/`is_boss_only`/`is_story_only`/`is_internal`/`available_version`,双口径统一(`/帕鲁1.0`/README/收集度)。
- **配种**:261 子代全有效/无重复/A+B=B+A 一致,加 `_meta`(版本/来源)。
- **数值规则**:核查确认**无旧值硬编码**(不需改),工作适性 0–8,浓缩/捕获机制数游戏未公开→不猜测。
- **觉醒/突变**:`/帕鲁觉醒`(9 系晶石+机制)、`/帕鲁突变`(机制+5 特殊蛋糕);觉醒状态不读存档、突变概率不猜测,均如实标注。
- **世界树独立地图**:`DT_WorldMapUIData` 的 Tree 区块(独立坐标系),提取 `T_TreeMap`(8192²)+7 boss 坐标,栖息地查世界树帕鲁自动切底图。
- **服务器设置**:补 1.0 字段(孵蛋/补给箱/据点工人/公会人数)+布尔开关(PvP/语音/快速旅行/硬核/入侵,缺失不误判关闭)+服务端版本。
- **存档兼容**:SetProperty 跳过安全验证;玩家/背包/队伍/帕鲁箱/据点解析正常;新增 `tests/test_palsave.py` 回归测试。
- (更早 v1.3.0–1.8.4:14 张 1.0 数据表 + 研究所/技能果实/植入体/世界树/1.0总览/战力榜/词条大全/boss塔主地图 等,见 CHANGELOG。)

---

## 部分完成

### 方向5 · 数据/素材生成工具 🟡
- **现状**:提取脚本(`build_*.py`、`bp_dump`、`texexport`、`exporter`)在仓库外 `/opt/palworld-khd/work/`,能提取 DataTable/本地化/图标/UI 纹理,但**未规范收进 `tools/game_data/`**。
- **待办**:迁入 `tools/game_data/`(discover/extract/build/validate/compare/build_all),`build_all.py --game-dir --output`,自动识版本+差异报告+失败不覆盖。

---

## 未开始 · ingame 游戏原生主题(方向3+4)

**尚未开始**(验证:STYLES 只有 fantasy/pixel;`data/ingame/` 不存在;`_conf_schema.json` card_style 无 ingame 选项)。

拆分阶段:

| 阶段 | 内容 | 状态 |
|---|---|---|
| A | UI 与 Emoji 完整审计(以 TEMPLATE_KEYS 为准,静态+动态两类) | ✅ 已完成(`docs/INGAME_ICON_COVERAGE.md` + `docs/INGAME_UI_REFERENCE.md`;791 处/166 Emoji;fantasy 56 键 / pixel 43 键不一致已记录) |
| B | 素材 Manifest + 图标解析器(`asset()`,禁硬编码路径) | ✅ 已完成(`data/ingame/manifest.json`+37真实图标+`tools/game_data/extract_ingame_icons.py`;解析器 `render/assets.py`;card_style 注册 ingame;pixel 补齐13键→**三套56键一致**;`tests/test_theme.py`。剩余=继续提取待定图标 + 逐卡接线) |
| C | 游戏原生通用 UI 组件(GameWindow/Panel/ItemSlot/StatBar/…) | ✅ 已完成(`render/templates.py` 的 `_INGAME_CSS`/`_IH`/`_IF`:窗口/面板/区块标题/八角节点/切角物品槽/帕鲁卡/进度条/属性徽章/工作芯片/排行行/网格/斜切属性牌/等级箭头 等,用真实纹理 border-image + `{{ parts.* }}` 注入);冷调石板灰配色(用户定)。**配色/间距/slice 临时值,待截图精校** |
| D | 重点卡片(状态/档案/帕鲁详情/队伍/帕鲁箱/背包) | ✅ 全部完成(status/players/paldex/palbox/bag/profile/team) |
| E | 其余全部卡片 | ✅ **56/56 全部转 ingame**(fantasy 全集)。渲染层注入 `icons`(element/work/stat/passive_rank/server/pal/currency);手机竖屏单列;真实游戏图标(属性/工作/数值/闪光/头目/货币/等级箭头)+ 插件扩展 SVG(server/plugin 概念)。fantasy/pixel 零改动。team handler 按 ingame 走 540 单列 |
| F | 全覆盖测试 + 视觉验收 | 🟡 自动化:三主题 56 键一致 / 全模板 Jinja 编译 / 56 卡渲染无错 / 静态无未替换 Emoji ✅。**动态 Emoji 已在渲染层清理**(ingame:标题去开头 Emoji、message icon 的 Emoji→插件 SVG,未映射不显示;fantasy/pixel 不受影响)。配色金/青已采自 pak 真值。**仅剩视觉验收**(面板底色/间距/字号/slice 精校)待用户游戏截图或 dump 控件蓝图 |

---

## 素材层现状(阶段 A/B 产物)

**素材层已基本齐备**:46 张真实游戏图标(element/work/status/pal/stat/ui)+ **23 个真实游戏 UI 组件纹理**(面板/边框/槽/标签/按钮/进度条,`data/ingame/parts/`)+ 20 个插件扩展 SVG(server/plugin)。
状态分布:**verified 71(48 图标+23 组件)· plugin-ext 20 · text-keep 8 · pending-extract 3**。
- text-keep 8(游戏权威核实确无图):伤病(骨折/扭伤/虚弱/精神,`DT_BaseCampWorkerSickDataTable` 无 icon)、闪光(仅粒子)、觉醒(无专属纹理)、耐力/速度。
- **pending-extract 仅 3 个,全部依赖游戏截图**:SAN/攻击/工作速度(候选 `T_icon_status_01/02/05`,需截图确认语义再绑)。

## 当前阻塞

- 🚫 **阶段 C(通用 UI 组件)/ D(重点卡片)缺游戏 UI 截图** —— 布局/间距/字号/**配色**(含插件扩展 SVG 描边色 `PLUGIN_INK` 校准)/信息层级/选中状态的参考,**挖不出来,必须用户提供**。素材层不再阻塞。

## 需要用户提供(截图,最后做)

- **游戏 UI 截图**(手机或 PC):帕鲁详情、帕鲁箱、背包、世界设置(核心优先);科技树、建造菜单、世界地图、任务日志、商店、公会、觉醒/突变/配种页。
- 顺带能确认 `T_icon_status_01/02/05/07` 语义(SAN/攻击/工作速度/帕鲁头)的**帕鲁详情面板**截图即可解掉最后 3 个 pending。

## 下一步

1. (不依赖截图)阶段 C 基建:`_INGAME_CSS` 变量 token + 通用组件骨架(占位配色,标注待校准),或先把 `tools/game_data/` 其余提取脚本规范化。
2. 用户发核心 UI 截图 → 阶段 C 配色校准 + 阶段 D 重点卡片 `asset()` 接线 + ingame 专属布局。
