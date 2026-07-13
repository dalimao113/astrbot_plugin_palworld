# INGAME 主题 · Emoji / 图标全量审计与覆盖矩阵

> 阶段 A 产物。以**实际代码扫描**为准(非记忆):`render/templates.py`、`main.py`、`constants.py`。
> 扫描脚本见 `tools/`(临时脚本在会话 scratchpad)。本文件是后续 Asset Manifest + 图标解析器 + 批量替换的**唯一权威清单**。
> 状态标记:`原图已有` / `待提取` / `游戏无此语义` / `插件扩展SVG` / `待用户截图` / `已替换` / `已验证`。
> 当前全表状态:**审计完成,实现未开始**(除已存在的帕鲁/物品/建筑/科技立绘)。

---

## 0. 扫描量化结果(客观数据)

| 文件 | 严格 Emoji 出现次数 |
|---|---|
| `main.py` | 408 |
| `render/templates.py` | 341 |
| `constants.py` | 34 |
| `api/docker_api.py` | 4 |
| 其它(test/router/renderer) | 4 |
| **合计** | **~791 处,166 个不同 Emoji** |

- `render/templates.py`:模板内**静态** Emoji(区块标题、空态、装饰)。
- `main.py`:**动态注入** Emoji —— 其中 `_msg_card()` 共 **192 个调用点**,每个把一个 Emoji 当 `icon` 数据传进 `message` 模板(错误/空态/确认/无数据卡)。
- `constants.py`:`ELEM_EMOJI`(9)、`WORK_ICON`(14)、`ITEM_CAT_META`(11)等映射表,被 main 注入模板。
- **CSS `content:` 无 Emoji;模板内无 `<script>`/JS。**(已验证,排除这两类隐藏来源)

---

## 1. 模板键注册表(TEMPLATE_KEYS 权威)

**关键发现:fantasy 与 pixel 的模板键集合当前并不一致,违反 CLAUDE.md「三套主题模板键集合必须一致」。**

- `STYLES["fantasy"]` = **56** 个键。
- `STYLES["pixel"]` = **43** 个键。
- `_t(key)` 逻辑:`STYLES[style].get(key, STYLES["fantasy"][key])` —— pixel 缺失的 13 个键**已在悄悄回退 fantasy**(正是 CLAUDE.md 禁止 ingame 出现的行为,pixel 已存在)。

**pixel 缺失、仅 fantasy 有的 13 个键**(ingame 必须全部实现,pixel 是否补齐另议):

```
palpower  palpowerdetail  lab_overview  lab_list  lab_detail
passdex   passlist        awakening     mutation  skillfruit
implant   worldtree       v10
```

➡ **ingame 目标 = fantasy 全集 56 键**(pixel ⊂ fantasy,故并集=fantasy)。`_conf_schema.json` 的 `card_style.options` 当前只有 `["fantasy","pixel"]`,需加 `ingame`;`STYLE_NAMES`/`STYLE_ALIAS` 需加 ingame 条目。

### 用户列的 ~90 个「页面」→ 56 个模板键映射

多数页面**共用**同一模板(参数化),不是 90 个独立模板:

| 模板键 | 承载的用户页面 |
|---|---|
| `message` | 错误/离线/认证失败/无权限/二次确认/操作成功/操作失败/**所有空数据状态**/审计/自检提示(**192 个 icon**) |
| `rank` | 玩家/图鉴/战力/财富/公会 排行榜(参数化) |
| `daily` | 早报/晚报/周结算/更新公告 |
| `paldex`/`grid` | 帕鲁图鉴 / 图鉴编号 / 坐骑 / 武器(网格筛选) |
| `power`/`palpower`/`palpowerdetail` | 战力榜 / 工作适性排行 / 公会帕鲁 |
| `item`/`itemcat` | 物品 / 物品分类 / 料理 / 配方 |
| `boss` | 塔主 / 突袭Boss |
| `passdex`/`passlist`/`passrec` | 被动词条图鉴 / 推荐词条 |
| `lab_*` | 研究所(总览/列表/详情) |
| `mission`/`missionlist` | 任务 / 主线 / 支线 |
| `arena`/`arena_tier` | 竞技场 |

其余为 1:1(status/players/settings/profile/bag/team/palbox/basecamp/guild/breed/reverse/route/inherit/element/habitat/shiny/heatmap/stats/skill/skillfruit/implant/worldtree/awakening/mutation/v10/map/compare/hatch/drop/droplist/facility/tech/symptom/merchant/help)。

---

> **进度更新(阶段B已完成基建)**:素材来源=游戏目录已打通(见记忆 ingame-icon-extraction-pipeline)。
> **已提取并落地 46 个真实游戏图标** → `data/ingame/icons/`,已建 `data/ingame/manifest.json`(79 语义键,**48 verified**,0 断链)+ 提取脚本 `tools/game_data/extract_ingame_icons.py`。
> 补提第二批(已 verified):头目/突变/浓缩、狗币/赏金、HP/防御/重量/饱食(+饥饿症状)。
> **插件扩展 SVG 已建 20 个**(`data/ingame/svg/`,`tools/game_data/gen_plugin_svgs.py`):server.*/plugin.*(CPU/内存/FPS/在线/自检/审计/备份/铃铛/锁/搜索…),解析器 `img()` 已支持 `plugin_svg`(描边色 `AssetResolver.PLUGIN_INK` 待截图校准)。
> **仅剩 3 个真 pending**(全部依赖游戏截图):SAN/攻击/工作速度(候选 `T_icon_status_01/02/05`)。
> **text-keep(游戏确无图,权威核实)**:伤病(骨折/扭伤/虚弱/精神,`DT_BaseCampWorkerSickDataTable` 无 icon 字段)、闪光(仅粒子特效)、觉醒(无专属纹理)。
> **UI 组件纹理已深挖提取 23 个**(真实游戏面板/边框/槽/标签/按钮/进度条)→ `data/ingame/parts/`,manifest 新增 `component` 命名空间,详见 `data/ingame/parts/README.md`。招牌件:金色八角节点框 `node_gold`、切角物品槽 `slot_item`、HP 条 `bar_hp`。多为白色遮罩,CSS 可重着色;`slice` 值初估,阶段C 建 CSS 时对照微调。
> 当前状态分布:**verified 71(48 图标+23 组件)· plugin-ext 20 · text-keep 8 · pending-extract 3**。
> **解析器 `render/assets.py`**(`asset(key,style)`:ingame→base64 图标/缺失→统一占位;fantasy·pixel→fallback;支持插件内部键别名)。
> **card_style 已注册 ingame**(schema/STYLE_NAMES/STYLE_ALIAS/STYLES;ingame 现为 fantasy **临时回退**模板,逐卡替换)。
> **pixel 已补齐 13 键 → 三套主题 56 键完全一致**。测试 `tests/test_theme.py`(键一致/模板可编译/manifest 素材存在/解析器行为)。
> **阶段C 已做**:`_INGAME_CSS` 组件系统(窗口/面板/八角节点/切角槽/进度条/属性徽章/工作芯片/标签/按钮),真实纹理 border-image;`component_uris()` + 渲染层注入 `{{ parts.* }}`。
> **阶段D 起步**:**帕鲁详情 `paldex` 已接为 ingame 真卡**(`PALDEX_ING`)——同一 Handler 数据,ingame 布局 + 元素/工作/数值走真实游戏图标(渲染层注入 `icons` 中文键映射)。预览:`docs/ingame_paldex_preview.html`。
> **未做**:其余 55 张卡逐张改造、配色/间距/slice 截图精校、最后 3 个 stat 图标语义确认。
> 下表 element.*/work.*/status(元素系)/gender/rarity/货币(金币·科技点) 状态实际已为 **verified**;pal.lucky/alpha/condensation/awakening/mutation、非元素症状、狗币/赏金、多数 stat.* 仍 **pending-extract**;server.*/plugin.* 为 **plugin-ext-pending**(待 SVG)。以 manifest 为准。

## 2. 统一语义资源键(Asset Manifest 草案 → 已落地 manifest.json)

> 业务层尽量传**语义键**(如 `element.fire`),不再把 Emoji 当业务数据。
> 每个键三态:`ingame_asset`(游戏原图) / `fallback_text`(fantasy·pixel 原 Emoji,保持不变) / `plugin_asset`(游戏无此概念时的插件扩展 SVG)。
> 解析器:`asset(key, style)` → ingame 取原图,缺失回退统一「缺失图标」;fantasy/pixel 取 `fallback_text`。

### 2.1 属性 element.*(游戏有原图 → 待提取)

| 语义键 | 现 Emoji | 游戏有? | 来源 | 状态 |
|---|---|---|---|---|
| element.neutral(无) | ⚪ | ✅ | `ELEM_EMOJI`、paldex/element/skill | 待提取 |
| element.fire(火) | 🔥 | ✅ | 同上 | 待提取 |
| element.water(水) | 💧 | ✅ | | 待提取 |
| element.grass(草) | 🌿 | ✅ | | 待提取 |
| element.electric(雷) | ⚡ | ✅ | | 待提取 |
| element.ice(冰) | ❄️ | ✅ | | 待提取 |
| element.ground(地) | ⛰️ | ✅ | | 待提取 |
| element.dark(暗) | 🌑 | ✅ | | 待提取 |
| element.dragon(龙) | 🐉 | ✅ | | 待提取 |

### 2.2 工作适性 work.*(游戏有原图 → 待提取)

`constants.WORK_ICON` 14 项 + 兜底 `⚙️`(main.py:3732):

| 语义键 | 现 Emoji | 游戏有? | 状态 |
|---|---|---|---|
| work.kindling(点火 emit_flame) | 🔥 | ✅ | 待提取 |
| work.watering(浇水) | 💧 | ✅ | 待提取 |
| work.planting(播种 seeding) | 🌱 | ✅ | 待提取 |
| work.electricity(发电) | ⚡ | ✅ | 待提取 |
| work.handiwork(手工 handcraft) | 🔨 | ✅ | 待提取 |
| work.gathering(采集 collection) | 🧺 | ✅ | 待提取 |
| work.lumbering(砍伐 deforest) | 🪓 | ✅ | 待提取 |
| work.mining(采矿) | ⛏️ | ✅ | 待提取 |
| work.oil(采油 oil_extraction) | 🛢️ | ✅ | 待提取 |
| work.medicine(制药) | 💊 | ✅ | 待提取 |
| work.cooling(制冷 cool) | ❄️ | ✅ | 待提取 |
| work.transport(搬运) | 📦 | ✅ | 待提取 |
| work.farming(牧场 monster_farm) | 🐄 | ✅ | 待提取 |
| work.farm_crop(农活 farming) | 🌾 | ✅ | 待提取 |
| work.__fallback | ⚙️ | — | 用统一「缺失图标」 |

### 2.3 基础数值 stat.*(游戏部分有 → 待核实)

来源:profile/paldex/compare/team。当前多为文字标签(生命/近战攻击…),少量 Emoji:

| 语义键 | 现 | 游戏有? | 状态 |
|---|---|---|---|
| stat.hp(生命) | ❤ | ✅ 游戏有心形 HP | 待提取 |
| stat.attack(近战/远程攻击) | ⚔ / 文字 | ⚠ 待核实 | 待核实 |
| stat.defense(防御力) | 🛡 / 文字 | ⚠ 待核实 | 待核实 |
| stat.stamina(耐力) | 文字 | ⚠ 待核实 | 待核实 |
| stat.san(理智/SAN) | 🧠 | ✅ 游戏有 SAN 图标 | 待提取 |
| stat.hunger(进食量/饱食) | 🍖 | ✅ | 待提取 |
| stat.weight(体型/重量) | 📏 | ⚠ 体型是文字 XS–XL | 保留文字 |
| stat.speed(移动/骑乘速度) | 🚀/🐎 | ⚠ 待核实 | 待核实 |
| stat.work_speed(工作速度) | 文字 | ⚠ 待核实 | 待核实 |

### 2.4 货币 currency.*(游戏有原图 → 待提取)

| 语义键 | 现 | 游戏有? | 状态 |
|---|---|---|---|
| currency.gold(金币) | 💰 | ✅ | 待提取 |
| currency.dog_coin(狗币) | 💰 | ✅ | 待提取 |
| currency.bounty(赏金) | 💰 | ⚠ 待核实 | 待核实 |
| currency.tech_point(科技点) | 💠/⭐ | ✅(科技树) | 待提取 |
| currency.ancient_tech_point(古代科技点) | 💠 | ✅ | 待提取 |

### 2.5 帕鲁标记 pal.*(游戏有原图 → 待提取)

| 语义键 | 现 | 游戏有? | 状态 |
|---|---|---|---|
| pal.gender_male(♂) | ♂ | ✅ | 待提取 |
| pal.gender_female(♀) | ♀ | ✅ | 待提取 |
| pal.lucky(闪光) | ✨ | ✅ 游戏有闪光标 | 待提取 |
| pal.alpha(头目/BOSS) | 👑/👹 | ✅ | 待提取 |
| pal.condensation(浓缩星级) | ★/⭐ | ✅ | 待提取 |
| pal.awakening(觉醒) | 🌟 | ⚠ 1.0 有觉醒页,图标待核实 | 待核实 |
| pal.mutation(突变) | 🧬 | ⚠ 待核实是否有专属图标 | 待核实 |
| pal.rarity_frame(稀有度边框) | 文字★ | ✅ 游戏用边框色+星 | 待提取 |

### 2.6 状态/症状 status.*(游戏有原图 → 待提取)

来源:`symptom`、`basecamp`(💊🩹🧠):

| 语义键 | 现 | 游戏有? | 状态 |
|---|---|---|---|
| status.burn(灼烧) | 🔥 | ✅ | 待提取 |
| status.poison(中毒) | 💊 | ✅ | 待提取 |
| status.frozen(冰冻) | ❄️ | ✅ | 待提取 |
| status.fracture(骨折) | 🩹 | ✅ | 待提取 |
| status.hungry(饥饿) | 🍖 | ✅ | 待提取 |
| status.starvation(极度饥饿) | 🍖 | ✅ | 待提取 |
| status.sprain(扭伤) | 🩹 | ✅ | 待提取 |
| status.weakness(虚弱) | 💤 | ✅ | 待提取 |
| status.depression(精神萎靡/低 SAN) | 🧠 | ✅ | 待提取 |
| status.cold/heat(失温/中暑) | 🩹 | ✅ | 待提取 |

### 2.7 服务器/插件功能(游戏无此语义 → 插件扩展 SVG)

**游戏里没有这些概念,严禁套用语义错误的游戏图标,一律统一线性 SVG,明确标为「插件扩展图标」:**

| 语义键 | 现 Emoji | 类别 | 状态 |
|---|---|---|---|
| server.online(在线) | 🟢/● | 服务器状态 | 插件扩展SVG |
| server.offline(离线) | 🔴 | | 插件扩展SVG |
| server.player_count(在线人数) | 👥 | | 插件扩展SVG |
| server.fps(服务器FPS) | ⚡ | | 插件扩展SVG(勿用雷属性) |
| server.uptime(运行时长) | ⏱ | | 插件扩展SVG |
| server.world_day(游戏天数) | 📅 | 半概念 | 插件扩展SVG |
| server.cpu | (文字) | 主机 | 插件扩展SVG |
| server.memory | (文字) | 主机 | 插件扩展SVG |
| server.load(服务器负载) | ◆ | | 插件扩展SVG |
| plugin.selfcheck(自检) | 🔬/🛠 | 插件 | 插件扩展SVG |
| plugin.audit(审计) | 📋 | 插件 | 插件扩展SVG |
| plugin.backup(备份/恢复) | 💾/⏪ | 插件 | 插件扩展SVG |
| plugin.notify(播报开关) | 🔔/🔕 | 插件 | 插件扩展SVG |
| plugin.docker/rest/qq/render | 🐳/🛰/💬 | 基础设施 | 插件扩展SVG |
| plugin.admin(管理员权限) | 🔒/🔓/🚫 | 权限 | 插件扩展SVG |
| plugin.link(绑定/关联) | 🔗 | 插件 | 插件扩展SVG |
| plugin.search/edit/help(查询/编辑/帮助占位) | 🔍/✏️/🙋 | 空态/提示 | 插件扩展SVG |

### 2.8 UI 区块标题 & 通用装饰(逐条判定)

模板里的区块标题 Emoji(📊基础数值 / ⚔主动技能 / 🎁掉落物品 / 🐑牧场产出 / 🔨工作适性 / 📖更多指令 …):
- **有对应游戏语义的**(技能/掉落/工作/属性/科技/物品)→ 用对应游戏图标或游戏面板小标题样式。
- **纯栏目名无对应物**(基础数值/更多指令/说明)→ 用游戏面板 `GameSectionTitle` 组件(游戏风格线条标题),不塞 Emoji。
- 装饰性(🐾脚印、💡提示、⚠警告、→ 箭头、★ 星):归入 UI 组件层统一处理,ingame 用游戏风格分隔/提示条。

---

## 3. 各模板 Emoji 明细(静态,来自 templates.py 扫描)

> 每行 = 一个模板常量出现的 Emoji×次数。ingame 需逐模板替换。fantasy/pixel **保持不变**。

```
STATUS_TMPL         ⏱×2 🦊×1 🏷×1 ●×1 ⚡×1 📅×1 👥×1 ◆×1
PLAYERS_TMPL        👥×1 🏝×1 ⭐×1
SETTINGS_TMPL       ⚙×1
HELP_TMPL           🆕×5 📖×1 🔍×1 🙋×1 🛠×1
STATS_TMPL          📊×1 📈×1
RANK_TMPL           🏆×1 😴×1
PROFILE_TMPL        🐾×2 👤 🧑 🚀 😴 ● 📜 ❤ ⚡ 🏋 💪 ✨ 👑 🎒 📦
PALDEX_TMPL         ★×2 📈×2 💰×2 📏×2 📕 🗼 👑 🌙 🥚 🎯 → 📊 🐑 ⚔ 🔨 🎁 🤝
BREED_TMPL          ★×2 🧬 🐣 →
BAG_TMPL            🎒 📦 📖
PALBOX_TMPL         📦 ✨ 👑 🐾 ★ 📖
BASECAMP_TMPL       💊×3 🏕×2 🍖×2 🧠×2 🐾 ✨ 👑 ⚠ ⛏ 💤 ❤ 📖
GUILD_TMPL          👥 👑 📖
TEAM_TMPL           ✨×2 👑×2 🐾 ★ ⚠
REVERSE_TMPL        🔄 📖
SHINY_TMPL          🐾 🧑 🏆
SYMPTOM_TMPL        💊×5 🩹×2
ROUTE_TMPL          ✓×3 →×2 🧬
POWER_TMPL          🏆 🐾 ✨ 👑 🧑
PALPOWER_TMPL       ⚔ 🐾 🗼 👑
PALPOWERDETAIL_TMPL ⚔ 🐾 🤝
HEATMAP_TMPL        🔥 📈
DROPLIST_TMPL       🎁×2
DROP_TMPL           🎁 🐾 📖
ITEM_TMPL           📦×2 🎒 💰 🎯 ⭐ 🔨 🛠
ITEMCAT_TMPL        🎒 📖
FACILITY_TMPL       🏗 🧱 🔨 📦
TECH_TMPL           🔬 ⭐ 🔓 💠
LAB_OVERVIEW_TMPL   🔬
LAB_DETAIL_TMPL     ✔ ⏳ 🔗
SKILLFRUIT_TMPL     🍐×2 ⚔ ⏱
IMPLANT_TMPL        🧬×2 ★ 🔥 ♻
WORLDTREE_TMPL      🌳×2 🛡
V10_TMPL            🎉 🐾 🎒 ✨ 🔬 🏛 🛠 🧪 🍐 🧬
GRID_TMPL           🗼 👑 ❔ 📖
MAP_TMPL            🗺 📍
ELEMENT_TMPL        ⚔ 💡
HABITAT_TMPL        🗺×2 🌙 🗼 👑 📍 💡
PASSREC_TMPL        📜 💡 ★
PASSDEX_TMPL        📜 🔍
PASSLIST_TMPL       🟢×2 🔴×2 ⚪×2
MISSION_TMPL        🎯 📍 🏅 ➡
MISSIONLIST_TMPL    💡
BOSS_TMPL           📍 🎁 ⚔
COMPARE_TMPL        📕×2 ▲×2 🔨
HATCH_TMPL          🥚×2 ← 📖
INHERIT_TMPL        🧬 👨 👩 🎲 📊 ⭐ ⚠ 📌
ARENA_TMPL          🏟 🏅 📖
ARENA_TIER_TMPL     🏅 🔁 ⚔ 💡 →
SKILL_TMPL          🍐×2 📖
MERCHANT_TMPL       🛒 …(见扫描)
AWAKENING_TMPL      🌟 💎 → 💡 ⚠
MUTATION_TMPL       🧬 🍰 💡 ⚠ 🌌 📜
```

*(pixel 变体 `_PIX` 用几何字符 ▰▣▤▦▥☷☖☗ 等作装饰,属 pixel 风格,ingame 不涉及、保持不变。)*

---

## 4. 动态 Emoji 来源(main.py 注入)—— 静态扫模板会漏,必须单独处理

| 来源 | 数量/说明 | ingame 处理 |
|---|---|---|
| `_msg_card(event, "<emoji>", …)` | **192 调用点**,把 icon 传进 `message` 模板 | icon 参数改传**语义键**,`message` 模板经 `asset()` 解析;错误类(🔴🔑🚫)→ 插件扩展 SVG |
| `constants.ELEM_EMOJI`(9) | main.py:1841-1843、2546、2555 注入 element/skill/paldex | 改为 `element.*` 语义键 |
| `constants.WORK_ICON`(14)+兜底`⚙️` | main.py:3732 注入 profile/paldex/basecamp | 改为 `work.*` 语义键 |
| `constants.ITEM_CAT_META`(11) | main.py:884-889 注入 itemcat,兜底`🎒` | 物品大类图标 → 游戏物品分类图标或扩展 SVG |
| 元素兜底 `"✨"` | main.py:2546/2555 | → `element.neutral` |
| 各处 `head=`/`icon=` 字面 Emoji | ~22 处 dict 内联 | 逐处改语义键 |

**最高杠杆点:`message` 模板 + 192 个 icon。** 只要 `message` 模板与 `_msg_card` 的 icon 通道改成语义键解析,一次覆盖近半数动态 Emoji 卡。

---

## 5. 现有素材盘点(data/images)

| 目录 | 数量 | 内容 | 对 ingame 图标的意义 |
|---|---|---|---|
| `data/images/` | 300 | 帕鲁立绘 | ✅ 已可用(帕鲁头像) |
| `data/images/items/` | 2420 | 物品图标 | ✅ 已可用 |
| `data/images/buildings/` | 497 | 建筑/设施图标 | ✅ 已可用(facility) |
| `data/images/tech/` | 598 | 科技图标 | ✅ 已可用(tech) |
| `data/images/misc/` | 1 | merchant.png | 几乎为空 |

**结论:立绘/物品/建筑/科技图标齐全;但属性、工作适性、状态、货币、性别、稀有度、数值、地图标记等 UI 图标一张都没提取,现在全靠 Emoji 顶替 —— 这是本轮最大缺口,需要从游戏文件批量提取(阶段 B 的提取管线)。**

---

## 6. 三类缺口汇总

**A. 待从游戏文件提取(游戏有原图):**
element.*(9)、work.*(14)、status.*(≈10)、currency.*(5)、pal.gender/lucky/alpha/condensation(≈6)、稀有度边框、地图标记/BOSS/快速旅行点、部分 stat.*、UI 面板/边框九宫格纹理、区块标题装饰。

**B. 待游戏文件核实(是否有专属图标):**
stat.attack/defense/stamina/speed/work_speed、pal.awakening、pal.mutation、currency.bounty。

**C. 游戏无此语义 → 插件扩展线性 SVG(不得用游戏图标冒充):**
server.online/offline/fps/uptime/player_count/world_day/cpu/memory/load、plugin.selfcheck/audit/backup/notify/docker/rest/qq/render/admin/link、以及 🔍查询/✏️编辑/🙋帮助 等纯提示占位。

---

## 7. 分批实施计划(阶段 B–F)

- **B. 基础设施**:`data/ingame/manifest.json`(语义键→ingame_asset/fallback_text/plugin_asset)+ `asset(key,style)` 解析器 + 统一「缺失图标」回退 + `card_style` 注册 ingame(schema/STYLE_NAMES/STYLE_ALIAS/STYLES)+ 自动测试(键唯一、模板键三套一致、素材引用存在、ingame 静态无未白名单 Emoji)。
- **C. 通用组件**:GameWindow/Header/Panel/SectionTitle/StatBar/PropertyRow/WorkIcon/ElementBadge/RarityFrame/ItemSlot/PalSlot(共用,不逐卡复制 CSS)。
- **D. 重点 6 卡**:status、profile、paldex、team、palbox、bag(先出预览对照游戏截图)。
- **E. 其余 50 键**全部覆盖(含 message + 192 icon、rank/daily/grid 参数化家族)。
- **F. 全量预览 + Emoji 扫描测试**,更新本表状态列至 `已验证`,确保无「只替换部分页面」。

**阻塞:** 阶段 D 起需要真实游戏 UI 截图与提取的真实图标,否则不得声称「高度还原」。缺口见 `docs/INGAME_UI_REFERENCE.md`。
