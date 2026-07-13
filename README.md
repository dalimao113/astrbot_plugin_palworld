<div align="center">

<img src="https://tc.dalimao.me:16666/i/2026/07/06/6a4b3b03a98b8.png" alt="帕鲁服务器管家" width="900">

# 🎮 帕鲁服务器管家 · astrbot_plugin_palworld

**AstrBot × 幻兽帕鲁(Palworld) 服务器管家插件**

让 QQ 群友查服务器状态 / 在线玩家 / 存档档案（队伍·背包·帕鲁箱·据点·公会），<br>
图鉴配种攻略随手查；管理员可公告 / 踢封 / 存档 / 关服。<br>
**所有回复一律输出精美卡片图片**，附一键部署脚本。

![version](https://img.shields.io/badge/version-1.18.0-6366F1?style=flat-square)
![AstrBot](https://img.shields.io/badge/AstrBot-4.25%2B-8B5CF6?style=flat-square)
![OneBot](https://img.shields.io/badge/OneBot-v11-4ade80?style=flat-square)
![NapCat](https://img.shields.io/badge/adapter-NapCat-22c55e?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)

</div>

让 QQ 群友通过指令查询帕鲁(Palworld)服务器状态，管理员可执行管理操作。
**所有回复一律输出精美卡片图片**（基于 AstrBot `html_render`），不发纯文字（仅渲染失败时兜底文字提示）。

- 目标环境：AstrBot **4.25.5+**（兼容 `>=4.25,<5`，4.26.x 实测可用；OneBot v11 / NapCat）
- 帕鲁服务端：`thijsvanloef/palworld-server-docker`，需开启 REST API

> 📖 **新手部署看这里**：完整、逐步、面向零基础的图文教程见 **[docs/DEPLOY.md](docs/DEPLOY.md)**，从买服务器、连服务器、装 Docker 一直手把手讲到机器人出图。

## 📸 功能展示

> 以下均为插件实际渲染的卡片（**奇幻玻璃**风格；另有**像素羊皮纸**风格，可在 WebUI 插件配置 `card_style` 切换）。

<table>
<tr>
<td align="center" width="50%"><b>服务器状态</b> · <code>/帕鲁状态</code><br><img src="docs/screenshots/status.png" width="300"></td>
<td align="center" width="50%"><b>个人档案</b> · <code>/帕鲁我</code><br><img src="docs/screenshots/profile.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>出战队伍</b>（HP/个体值/词条/技能）· <code>/帕鲁队伍</code><br><img src="docs/screenshots/team.png" width="300"></td>
<td align="center"><b>帕鲁箱</b>（编号/翻页/稀有度配色）· <code>/帕鲁箱</code><br><img src="docs/screenshots/palbox.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>物品详情</b>（买卖价格 / 帕鲁球捕获力）· <code>/帕鲁物品 帕鲁球</code><br><img src="docs/screenshots/item.png" width="300"></td>
<td align="center"><b>科技详情</b>（解锁条件）· <code>/帕鲁科技</code><br><img src="docs/screenshots/tech.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>公会信息</b> · <code>/帕鲁公会</code><br><img src="docs/screenshots/guild.png" width="300"></td>
<td align="center"><b>公会肝帝榜</b> · <code>/帕鲁公会榜</code><br><img src="docs/screenshots/guildrank.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>帕鲁图鉴详情</b>（数值/牧场产出/掉落/进食/刷新等级）· <code>/帕鲁图鉴 棉悠悠</code><br><img src="docs/screenshots/paldex.png" width="300"></td>
<td align="center"><b>配种推演</b> · <code>/帕鲁配种 冰棘兽 清雀</code><br><img src="docs/screenshots/breed.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>属性克制图</b>（九系克制关系）· <code>/帕鲁属性克制</code><br><img src="docs/screenshots/element.png" width="300"></td>
<td align="center"><b>帕鲁栖息区域</b>（地图热区色块）· <code>/帕鲁栖息区域 火绒狐</code><br><img src="docs/screenshots/habitat.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>推荐词条</b>（按战斗/生产/搬运角色定制）· <code>/帕鲁推荐词条 火绒狐</code><br><img src="docs/screenshots/passrec.png" width="300"></td>
<td align="center"><b>物品配方</b>（材料+制作台）· <code>/帕鲁物品 火箭发射器</code><br><img src="docs/screenshots/recipe.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>任务攻略</b>（剧情/目标/坐标/奖励）· <code>/帕鲁任务 少女与高塔</code><br><img src="docs/screenshots/mission.png" width="300"></td>
<td align="center"><b>主线任务列表</b>（剧情顺序/翻页）· <code>/帕鲁主线</code><br><img src="docs/screenshots/missionlist.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>物品分类菜单</b> · <code>/帕鲁物品</code><br><img src="docs/screenshots/itemcat.png" width="300"></td>
<td align="center"><b>设施图鉴</b> · <code>/帕鲁设施 木箱</code><br><img src="docs/screenshots/facility.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>在线玩家地图</b>（真实底图标点）· <code>/帕鲁地图</code><br><img src="docs/screenshots/map.png" width="300"></td>
<td align="center"><b>在线统计</b>（7 日趋势）· <code>/帕鲁统计</code><br><img src="docs/screenshots/stats.png" width="300"></td>
</tr>
<tr>
<td align="center"><b>背包明细</b> · <code>/帕鲁背包</code><br><img src="docs/screenshots/bag.png" width="300"></td>
<td align="center"><b>指令帮助</b> · <code>/帕鲁帮助</code><br><img src="docs/screenshots/help.png" width="300"></td>
</tr>
<tr>
<td align="center" colspan="2"><b>部署自检</b>（管理员一键体检环境，装完先发这条）· <code>/帕鲁自检</code><br><img src="docs/screenshots/selfcheck.png" width="300"></td>
</tr>
</table>

## 指令表

> 指令前缀 `/` 可加可不加（`/帕鲁` 或 `帕鲁` 都行）；「帕鲁」与子命令**不要空格**（如 `/帕鲁在线`），带空格（`帕鲁 在线`）也兼容。

### 查询类（所有群友可用，受冷却限制）
| 指令 | 说明 |
|---|---|
| `/帕鲁` 或 `/帕鲁状态` | 在线人数、FPS、游戏天数、运行时长、版本、**在线玩家列表(含在线时长/等级/ping)**、**服务器 CPU/内存负载** |
| `/帕鲁在线` | 在线玩家列表（独立卡，内容同状态卡的玩家区）|
| `/帕鲁设置` | 主要倍率（经验/捕捉/掉落等）与 PVP 开关 |
| `/帕鲁统计` | 今日在线峰值/平均/当前 + 近 7 日峰值趋势 |
| `/帕鲁肝帝榜` | 本周在线时长排行榜（也可 `/帕鲁排行`）|
| `/帕鲁图鉴 [名/字]` | 帕鲁图鉴：详情卡（**基础数值全项/牧场产出/进食量/刷新等级/蛋型/捕获率/售价/体型** + 技能/工作适性/伙伴技能/掉落/描述）；空=全表网格、模糊=列表、可翻页 |
| `/帕鲁配种 <亲A> <亲B>` | 两只帕鲁的配种后代卡（含子代继续配种推荐）|
| `/帕鲁反配种 <子代>` | 反查：要配出某只帕鲁有哪些亲代组合（也可 `/帕鲁反向`）|
| `/帕鲁继承 <词条A｜词条B>` | 词条继承概率计算器：输入双亲词条，算后代同时继承的概率（社区实测模型）|
| `/帕鲁栖息区域 <名>` | 以世界地图为底图，用属性色块涂出该帕鲁的刷新热区 + 主要出没区域（也可 `/帕鲁栖息地`）|
| `/帕鲁推荐词条 <名>` | 按帕鲁角色（战斗/生产/搬运）定制推荐高价值被动词条（也可 `/帕鲁推荐`）|
| `/帕鲁属性克制` | 九系属性克制关系图（也可 `/帕鲁克制`）|
| `/帕鲁主线 [页]` | 按剧情顺序（next 链拓扑）列出全部主线任务（1.0 共 55 个，翻页）|
| `/帕鲁支线 [NPC]` | 支线任务（1.0 共 50 个，可按 农民/学者/佐伊 等 NPC 筛选，翻页）|
| `/帕鲁任务 <任务名>` | 任务详细攻略：剧情 + 目标 + 地图坐标 + 奖励 + 下一环 |
| `/帕鲁塔主 [名]` | 7 大高塔塔主：属性/等级/血量/所在 + 克制提示（也可 `/帕鲁高塔`）|
| `/帕鲁突袭 [名]` | 突袭 Boss（贝菈诺娃等）数据与打法提示（也可 `/帕鲁boss`）|
| `/帕鲁竞技场 [段位]` | 竞技场 6 段位（青铜→大师）对手阵容 + 段位首通/重复奖励；战斗券兑换见 `/帕鲁商人 竞技场商店` |
| `/帕鲁商人 [名]` | 9 大商店卖什么 + 价格/货币（流浪/沙漠/火山/勋章/赏金/竞技场…）|
| `/帕鲁哪里买 <物品>` | 某物品在哪个商店买、多少钱（数据来自客户端 pak 商店表）|
| `/帕鲁技能 <名/属性>` | 主动技能图鉴：威力/冷却/效果 + 是否技能果实可得（`/帕鲁技能 果实` 看全部果实）|
| `/帕鲁钓鱼` | 钓鱼能钓到什么 + 各自概率（高级帕鲁球/设计图/帕鲁之魂等）|
| `/帕鲁工作 <工种>` | 某工种（采矿/搬运/手工/浇水…）最强帕鲁排行（按适性等级）|
| `/帕鲁坐骑` | 可骑乘帕鲁按奔跑速度排行（找快马代步）|
| `/帕鲁对比 <A> <B>` | 两只帕鲁数值并排对比（◀左强 ▶右强 ＝相同）|
| `/帕鲁料理 [效果]` | 有增益的料理一览（攻击/防御/工作速度/SAN/配种…可筛选）|
| `/帕鲁武器 [名]` | 武器攻击力榜 / 某武器的攻击力·解锁科技·弹药 |
| `/帕鲁物品 [类别/名]` | 物品图鉴：空=分类菜单、类别名=该类网格、物品名=详情（描述+**商人价格/帕鲁球捕获力+制作材料+制作台**）|
| `/帕鲁设施 [名/字]` | 建筑设施图鉴：详情（描述+**建造材料+解锁科技**）/网格/翻页（也可 `/帕鲁建筑`）|
| `/帕鲁科技 [名/字]` | 科技图鉴：详情（描述+**解锁条件**：等级/技术点/古代科技点）/网格/翻页（也可 `/帕鲁技术`）|
| `/帕鲁材料路线 <物品> [数量]` | 把配方**递归展开到底**：直接配方 + 需预制的中间产物 + **原料总需求**（拆到采集/掉落原料的合计）+ 全链路制作台；带数量算 N 份（也可 `/帕鲁材料`）|
| `/帕鲁帮助` | 指令帮助卡片（也可 `/帕鲁菜单`）|

### 管理类（仅 `admin_qq` 白名单可用）
| 指令 | 说明 |
|---|---|
| `/帕鲁公告 <内容>` | 服务器内广播公告 |
| `/帕鲁踢 <userId> [理由]` | 踢出玩家 |
| `/帕鲁封 <userId> [理由]` | 封禁玩家（**需二次确认**） |
| `/帕鲁解封 <userId>` | 解除封禁 |
| `/帕鲁批准绑定 [QQ]` | `bind_mode=admin_confirm` 时批准玩家绑定申请（无参列出待批）|
| `/帕鲁拒绝绑定 <QQ>` | 拒绝玩家绑定申请 |
| `/帕鲁存档` | 立即保存世界存档 |
| `/帕鲁关服 <秒数> [提示语]` | 定时关服（**需二次确认**） |
| `/帕鲁重启服务器` | 存档后重启服务器，约 1 分钟恢复、世界不变（**需二次确认**；也可 `/帕鲁重启`） |
| `/帕鲁重置存档` | 删档重开：备份旧档 → 停服 → 清空世界 → 以全新世界重启（**需二次确认**；也可 `/帕鲁删档重开`） |
| `/帕鲁恢复存档` | 还原**最近一次** `/帕鲁重置存档` 前的存档（**需二次确认**；也可 `/帕鲁还原`） |
| `/帕鲁审计` | 查看最近 12 条管理操作记录（也可 `/帕鲁日志`）|
| `/帕鲁自检` | **一键体检**：docker.sock / 帕鲁容器 / REST 密码 / 存档目录 / 存档解析库 / 渲染 / 管理员白名单，逐项 ✅⚠️❌ + 修复指引（也可 `/帕鲁诊断`、`/帕鲁体检`）。**装完/配完先发这条确认环境** |
| `/帕鲁地图` | 在线玩家世界地图：真实底图上标注在线玩家位置/名字/等级/所在区域（仅在线玩家）|
| `/帕鲁确认` | 在超时时间内确认上一条危险操作 |

> **关服 / 重启 / 重置 / 恢复存档**需容器挂载 `docker.sock`（与服务器负载监控同款挂载）；均为危险操作，走管理员白名单 + 二次确认。
> - `/帕鲁重置存档` 会先把旧世界打包备份到容器内 `/palworld/Pal/Saved/manual_resets/<世界GUID>_<时间戳>.tar.gz` 再清空重开；`/帕鲁恢复存档` 只还原**最近一次**那份备份。
> - ⚠️ **地图迷雾无法还原**：角色 / 背包 / 帕鲁 / 据点 / 等级等**服务器数据可完整还原**，但「已探索地图迷雾」是**各玩家客户端本机**数据——重置后地图会变黑、恢复也救不回，需各玩家自行重新探索。

### 玩家自助（所有群友可用）
| 指令 | 说明 |
|---|---|
| `/帕鲁绑定 <游戏名>` | 绑定你的帕鲁角色（**建议在线时绑**，以精确认账号）|
| `/帕鲁我` | 查看个人在线档案（在线状态/本周时长/累计/排名）|
| `/帕鲁我的战力 [页]` | 自己**所有捕捉帕鲁**按综合战力排行（等级/属性/闪光头目标记，分页；管理员可加玩家名查他人）|
| `/帕鲁养成 <帕鲁名> [序号]` | 读你存档里这只帕鲁的**浓缩星级/帕鲁之魂/觉醒/个体值/词条/技能**现状与目标差距（浓缩/魂精确材料数游戏未公开则不虚报，觉醒晶石按属性给）。**同种有多只时会列出让你按序号选**（`/帕鲁养成 达鼠泥 2`）|
| `/帕鲁小队进度` | 按群聚合已绑定队员的**图鉴/传送点/塔主/野外Boss/地牢/遗物/区域**进度 + 各自**下一步任务**（存档只读自动同步，读不到的用手动勾选）|
| `/帕鲁小队勾选 <目标>` | 手动勾选/取消一个探索目标（按群记录是谁完成，如 `/帕鲁小队勾选 世界树探索`）|
| `/帕鲁据点体检 [据点号]` | 据点摘要：工人数/工作中、**工作适性覆盖与关键缺口**、伤病/饥饿/理智低/工作病计数 + 处理建议。一个公会最多 4 个据点，多据点时顶部可切换、`/帕鲁据点体检 2` 看第 2 据点（存档只读，规则见 `data/basecamp_rules.json`）|
| `/帕鲁订阅 <游戏名>` | 该玩家上线时在群里 @ 你 |
| `/帕鲁退订 <游戏名>` | 取消上线提醒 |
| `/帕鲁找人 <游戏名>` | 查某玩家是否在线 |
| `/帕鲁喊话 <内容>` | 把话广播到**游戏内**（带 `[QQ-昵称]` 前缀，有冷却）|
| `/帕鲁喊 <游戏名>` | @ 已绑定该角色的群友，喊 TA 上线 |

> **绑定说明**：内部以帕鲁 `userId`（基于 Steam64 的稳定账号 id）为主键，名字仅作显示、改名也认得。
> `/帕鲁绑定 名字` 会在在线/历史中定位你的 userId；**同名多人**时会列出候选，让你用 `/帕鲁绑定 <userId>` 精确绑。
>
> **适用场景**：角色绑定是面向**熟人私人群**的**信任机制**（同一游戏角色不能被多个 QQ 重复绑定，避免顶替），**不含验证码/审核**。
> **绑定模式** `bind_mode`：默认 `open`（先到先绑，适合熟人小队）；陌生人大群可设 `admin_confirm`，玩家绑定需管理员 `/帕鲁批准绑定 <QQ>` 通过，`trusted_qq` 白名单免批准。
> **广播安全**：`broadcast_whitelist_only=true` 可让上下线/掉线播报只发到 `broadcast_groups` 白名单群，避免误发到机器人被拉进的其它群。

> 非白名单用户触发管理指令 → 回复「无权限」卡片，不执行。
> 危险操作（封禁/关服）需在 `confirm_timeout` 秒内回复 `/帕鲁确认` 才执行，超时作废。

### 存档查询类（需挂载 docker.sock，`palwork/` 已随插件自带）
> 这些指令读取**服务器存档**（强制存盘 → 经 docker.sock 从帕鲁容器拉取 → 解析），数据更详细更真实。
> **隐私**：查自己随意；带玩家名查他人的详细数据**仅管理员**可用。

| 指令 | 说明 |
|---|---|
| `/帕鲁我` | 个人档案：在线状态/时长/排名 + **存档真实等级·技术点·配方数·生命·饱食·状态点加点 + 出战队伍预览 + 背包件数** |
| `/帕鲁背包` | 背包物品明细（中文名 + 游戏图标 + 数量）|
| `/帕鲁队伍` | 出战帕鲁详细面板：生命值/个体值IV/浓缩/性别/属性/闪光/头目 + **词条(带等级配色)** + **技能(属性·威力·描述)** |
| `/帕鲁箱 [页]` | 帕鲁箱全部帕鲁网格：编号/等级/✨闪光/👑头目/★浓缩 + **稀有度底框配色**，可翻页 |
| `/帕鲁可孵化` | 根据你帕鲁箱里**已拥有的帕鲁**，算出两两配种能孵出哪些你还没有的新帕鲁 |
| `/帕鲁据点 [据点号] [页]` | 据点工作帕鲁状态：每只的属性/等级/**工作适性** + **濒死·重伤·饥饿**标记 + 受伤/饥饿汇总。多据点时顶部可切换、`/帕鲁据点 2` 看第 2 据点 |
| `/帕鲁箱查询 <编号>` | 帕鲁箱里某只帕鲁的完整面板（编号取自 `/帕鲁箱` 列表）|
| `/帕鲁公会` | 公会信息卡：成员/会长/规模（也可 `/帕鲁工会`）|
| `/帕鲁公会榜` | 公会肝帝榜：按公会汇总成员在线时长排名 |
| `/帕鲁公会帕鲁 [页]` | 公会终端：汇总本公会**所有成员帕鲁箱**里的帕鲁（分页网格）|

> 管理员可在以上指令后带玩家名查他人，如 `/帕鲁队伍 大狸猫`、`/帕鲁箱查询 大狸猫 5`、`/帕鲁公会 大狸猫`。
> 详细部署见 **[docs/DEPLOY.md](docs/DEPLOY.md)**。

## 配置项（WebUI → 插件配置）
| 键 | 默认 | 说明 |
|---|---|---|
| `api_base` | `http://palworld-server:8212` | 帕鲁 REST API 地址 |
| `admin_password` | （空） | 服务器 `ADMIN_PASSWORD`（Basic Auth 密码，用户名固定 `admin`）|
| `admin_qq` | `[]` | 管理员 QQ 号列表 |
| `query_cooldown` | `10` | 查询冷却秒数（硬下限 5）|
| `confirm_timeout` | `60` | 危险操作二次确认超时秒数 |
| `card_theme_color` | `#6366F1` | 卡片主题色 |
| `request_timeout` | `5` | API 请求超时秒数 |
| `enable_broadcast` | `true` | 后台主动播报总开关 |
| `poll_interval` | `60` | 后台轮询间隔秒数（硬下限 20）|
| `broadcast_groups` | `[]` | 指定播报群号；留空=自动登记用过指令的群 |
| `notify_player_join_left` | `true` | 播报玩家上下线 |
| `notify_server_down` | `true` | 播报服务器掉线/恢复 |
| `offline_alert_threshold` | `2` | 连续几次轮询失败才判掉线告警 |
| `notify_record` | `true` | 播报在线人数破纪录 |
| `notify_milestone` | `true` | 播报世界天数里程碑（7/30/100…天）|
| `quiet_hours` | `""` | 夜间静默时段 `HH-HH`（如 `23-8`），期间不发非紧急播报。掉线告警不受影响 |
| `fps_alert_threshold` | `0` | 服务器 FPS 低于此值告警，`0`=关闭（建议 30~45）|
| `notify_settings_change` | `false` | 播报服务器倍率/PVP 等设置变更（每约 10 分钟检查）|
| `morning_report_time` | `09:00` | 早报推送时间 `HH:MM`，留空=不发 |
| `evening_report_time` | `21:00` | 晚报推送时间 `HH:MM`，留空=不发 |
| `weekly_settle_time` | `10:00` | 周一肝帝结算时间 `HH:MM`，留空=不结算 |
| `enable_shout` | `true` | 启用群→游戏喊话 |
| `shout_cooldown` | `30` | 喊话/喊人冷却秒数（硬下限 5）|
| `enable_host_stats` | `true` | 状态卡显示容器 CPU/内存 |
| `docker_container` | `palworld-server` | 要监控/拉存档的帕鲁容器名；**找不到会自动探测**跑 palworld 的游戏服容器 |
| `docker_sock` | `/var/run/docker.sock` | docker socket 路径 |
| `card_style` | `fantasy` | 卡片风格：`fantasy`(奇幻玻璃) / `pixel`(像素羊皮纸) / `ingame`(游戏原生)。三套主题**共享真实游戏语义图标**(属性/工作适性/货币等),仅背景/面板/边框/排版各自不同 |
| `save_dir_in_container` | （空） | 帕鲁容器内的世界存档目录；**留空自动探测** `SaveGames/0/` 下的世界 GUID（换世界也免改，仅多世界/特殊布局才需手填）|
| `save_cache_ttl` | `120` | 存档解析缓存秒数（每次拉档先强制存盘，建议 ≥60）|
| `local_render` | `false` | **默认关**：出图走 **AstrBot 内置 t2i 渲染服务**（开箱即用、自带中文字体、稳定,推荐）。仅当容器确实装了 Playwright+Chromium+中文字体、想更快出图时才开 `true`（会自动回退 t2i）|
| `prewarm_save` | `true` | 后台预热存档缓存，让首次发存档类指令就秒出图 |

## 主动播报（后台监控）
开启 `enable_broadcast` 后，插件每 `poll_interval` 秒轮询一次服务器，自动：
- **玩家上下线播报**：玩家上线/下线时在播报群提示（下线附带本次在线时长）。
- **掉线/恢复告警**：服务器从在线变为连不上（连续失败达 `offline_alert_threshold` 次）发掉线卡，恢复时发恢复卡。

播报目标群：默认**自动登记**——任何在群里用过 `/帕鲁` 指令的群会自动成为播报群；也可用 `broadcast_groups` 手动指定。
状态持久化在插件数据目录 `state.json`，重载/重启不丢。

## 自然语言查询（LLM）
若机器人本身启用了 LLM 且允许函数调用，群友可直接用自然语言提问，bot 会自动调用工具出卡：
- "现在服务器几个人？" → 状态卡
- "有谁在线？" → 在线玩家卡
- "服务器经验倍率多少？" → 设置卡

注册的 LLM 工具：`palworld_server_status`、`palworld_online_players`、`palworld_server_settings`。
（无需配置，自动随插件注册；机器人没开 LLM 则此功能不生效，不影响 `/帕鲁` 指令。）

## 图鉴 / 配种（数据驱动）
- `/帕鲁图鉴 <帕鲁名>`：查帕鲁中文名/属性/主动技能/工作适性/伙伴技能/描述（支持模糊匹配，查无给建议）。
- `/帕鲁配种 <亲A> <亲B>`：查两只帕鲁的配种后代（精确，含同种与特殊组合）。
- **代码与数据分离**：数据放插件 `data/` 子目录，启动时加载，换数据文件不用改代码。
  - `data/paldex.json`：图鉴主数据（**287 只官方可收集帕鲁**；含变体/剧情 boss 共 **289 个数据实体**，编号 1–204，简体中文全字段）。数据实体与可收集口径差异 2 条为**枯星龙**（世界树剧情最终 boss）与**花叶泥泥**（叶泥泥花变种，与基础共享图鉴位）——已用 `is_collectible` 字段标记、不计入正式可收集数，未删除。来源：**从游戏客户端 pak 直接解析**（含技能/适性/伙伴技能/描述/口径字段）。
  - `data/breeding.json`：配种组合表（**21321 组**，按游戏当前 CombiRank 算法生成，全覆盖）。
  - `data/images/<pal_dev_name>.png`：**帕鲁透明头像**（289 张，128px）。图鉴卡名旁、配种卡每只帕鲁上方自动显示。来源：**从游戏客户端 pak 提取的官方贴图**（含 1.0 新帕鲁/变体）。
  - 游戏更新出新帕鲁后想刷新数据：解析工具链备份在仓库外 `../../../../_palworld_extract_tools/`（repak 解包 + 自研纯 Python UE5.1 DataTable 解析器）；图标可按 `https://cdn.paldb.cc/image/Pal/Texture/PalIcon/Normal/T_<DevName>_icon_normal.webp` 补拉。`.bak` 是上一版数据备份。
  - 想更新/替换：保持同样的字段结构覆盖这两个文件，再「重载插件」即可。

## 定时早晚报 + 周肝帝结算
- **早报/晚报**：每天定点（默认早 09:00 / 晚 21:00）向播报群推一张日报卡——服务器状态、今日峰值/平均、今日肝帝 TOP3、本周肝帝榜 TOP3（早报含昨日峰值，晚报含历史纪录）。
- **周肝帝结算**：每周一定点（默认 10:00）结算上周肝帝榜，发结算卡并 @ 上周肝帝祝贺，随后开启新一周计时（数据归档到 `history`）。
- 任一时间留空即关闭对应推送。

## 在线统计与肝帝榜
后台轮询会顺带采集数据（依赖 `enable_broadcast` 开启）：
- **`/帕鲁统计`**：今日在线峰值/平均/当前 + 近 7 日峰值柱状趋势。
- **`/帕鲁肝帝榜`**：本周每位玩家累计在线时长排行（周一自动归零）。时长按轮询累计，间隔越小越精确。
- 数据存在 `state.json`，只保留近 14 天采样。

## 服务器负载（CPU/内存）
`帕鲁/帕鲁状态` 卡片可显示 **palworld 容器的 CPU% 和内存占用**（除游戏 FPS/人数外）。
- 数据来源：Docker Engine API（读 `docker.sock`），非帕鲁 REST API。
- **前置条件**：把宿主机 docker socket **只读**挂载进 AstrBot 容器，在 `docker-compose.yml` 的 astrbot 服务下加：
  ```yaml
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  ```
  然后重建 astrbot 容器（`docker compose up -d astrbot`）。未挂载时状态卡自动省略负载区，不报错。
- 监控目标容器名由 `docker_container` 配置（默认 `palworld-server`）。

## Docker 网络互通（重要）
插件在 **AstrBot 容器内**通过 Docker 内部网络访问帕鲁容器，因此：

1. AstrBot 容器与帕鲁容器必须在**同一个自定义网络**里。
2. `api_base` 用帕鲁的**容器名**（如 `palworld-server`）而非 `localhost`/宿主机 IP。
3. 帕鲁需开启 REST API（`RCON`/`REST_API_ENABLED=true` 等，详见镜像文档），并设置 `ADMIN_PASSWORD`。
4. **安全红线**：8212 仅供内网调用，**绝不对公网暴露**。

示例（把两个 compose 接到同一外部网络）：
```yaml
networks:
  game-net:
    external: true
# 两个容器都加：
    networks:
      - game-net
```

## 卡片风格切换（皮肤）
插件内置两套卡片风格，可实时切换：
- **🌌 奇幻玻璃（fantasy）**：二次元插画背景 + 深蓝紫磨砂玻璃 + 暗金宝石。**需你提供插画图**（见下）。
- **📜 像素羊皮纸（pixel）**：低像素 + aged 羊皮纸纹理 + 复古墨色（深红/金/暗绿）+ 像素字体。**自包含，无需图片**（羊皮纸纹理 CSS 生成，中文像素字体 Zpix 经 CDN 加载）。

切换方式：在 **WebUI → 插件配置 → `card_style`** 选择 `fantasy`（奇幻玻璃）或 `pixel`（像素羊皮纸），保存后生效（如未即时生效可重载插件）。

## 卡片视觉风格（二次元奇幻）
全部卡片为**整图插画背景 + 深蓝紫磨砂玻璃信息面板 + 暗金复古描边 + 四角发光宝石**的现代手游 UI 风。
- **插画背景由你提供**（命名 `bg.jpg` 或每卡专属 `bg_<卡名>.jpg` 放插件目录）。建议主体偏右下、左上稍暗，玻璃面板压左上文字清晰、右下露出角色。
- 不放图时回退深蓝紫渐变背景，一切正常。
- 暗金/宝石/玻璃为 CSS 绘制（与 `card_theme_color` 无关，是固定奇幻配色）。

## 卡片样式
- 卡片为**整图铺满**的竖版设计，白底 + 内容随长短自适应高度，顶部状态栏底部圆角过渡。
- **顶部状态栏背景图（可每卡专属）**：把帕鲁游戏图放进插件目录即可，顶部栏会显示——右侧清晰露图、左侧模糊 + 主题色渐隐护住文字。
  - `bg.jpg`：**默认图**，所有卡片通用。
  - `bg_<卡名>.jpg`：**该卡专属图**，覆盖默认。卡名取值：
    `status`(状态) `players`(在线) `settings`(设置) `help`(帮助) `stats`(统计) `rank`(肝帝榜) `profile`(个人档案) `message`(通用消息/告警/确认)。
    例：`bg_rank.jpg` 只用于肝帝榜卡。
  - 支持 `.jpg/.jpeg/.png/.webp`；没放专属图就用 `bg.jpg`；都没有则纯色头部。改图后「重载插件」生效。
  - 建议尺寸 ~3:1 宽幅、主体偏右、≤500KB（详见图片建议）。
- **超高清渲染**：CSS `zoom` 超采样（`SUPERSCALE=2`）× `device_scale_factor_level: ultra`，
  输出 **1944px 宽 PNG 无损**（约 2× 普通清晰度），放大也不糊。
  - 想更清晰可把 `constants.py` 里的 `SUPERSCALE` 调到 3（输出 2916px，文件更大）。
- 主题色由配置 `card_theme_color` 控制（默认靛蓝 `#6366F1`，可自定义）。

## 📂 项目结构

| 路径 | 类型 | 说明 |
|---|---|---|
| `main.py` | Python | 插件入口：插件类 + 生命周期 + AstrBot 指令/事件 Handler + 命令分发 + 各 `_cmd_*` 业务逻辑 + 后台轮询/播报 |
| `constants.py` · `config.py` | Python | 常量/映射表；配置默认值(规范来源)+启动校验 |
| `commands/router.py` | Python | 命令注册表（子命令→处理器 的单一事实来源）|
| `services/` · `api/` | Python | 存档拉取/缓存/负缓存编排；Palworld REST + Docker socket 封装(含高危权限注释) |
| `render/` | Python | `templates.py`(卡片 HTML/CSS 模板 + 两套皮肤) + `renderer.py`(渲染引擎) |
| `utils/` | Python | 文本转义 / 输入长度限制(安全) 等工具 |
| `_conf_schema.json` | JSON | AstrBot 插件配置项 schema（WebUI 配置界面据此生成）|
| `metadata.yaml` | YAML | 插件元信息（名称/作者/版本/描述）|
| `requirements.txt` | 文本 | Python 依赖声明 |
| `README.md` · `docs/DEPLOY.md` | Markdown | 说明文档 / 从零部署教程（含服务器全参数参考）|
| `docs/screenshots/` | 图片目录 | README 功能展示用的卡片截图 |
| `bg.jpg` · `bg_*.jpg` | 图片 | 卡片顶部背景插画（`bg.jpg` 默认；`bg_<卡名>.jpg` 专属）|
| `data/paldex.json` | JSON 数据 | 帕鲁图鉴（**287 只可收集**/289 数据实体：属性/技能/工作适性/伙伴技能/描述/口径字段）|
| `data/breeding.json` | JSON 数据 | 配种组合表（21321 组）|
| `data/items.json` | JSON 数据 | 物品图鉴（名称/描述/类型/图标）|
| `data/recipes.json` | JSON 数据 | 物品制作配方（材料 + 制作台）|
| `data/buildings.json` | JSON 数据 | 设施/建筑图鉴 |
| `data/building_recipes.json` | JSON 数据 | 设施建造配方（建造材料 + 解锁科技）|
| `data/tech.json` | JSON 数据 | 科技图鉴（含解锁等级/古代科技标记）|
| `data/passives.json` | JSON 数据 | 帕鲁词条(被动)表（中文名/等级/正负/效果）|
| `data/wazas.json` | JSON 数据 | 帕鲁主动技能枚举 → 中文名 |
| `data/worldmap.png` | 图片 | 世界地图底图（2048² 高清，用于 `/帕鲁地图`）|
| `data/map_*.json` · `regions.json` | JSON 数据 | 地图坐标变换 / 区域 / 传送点锚点 |
| `data/images/` | 图片目录 | 全部图标：帕鲁头像 + `items/`(物品) + `buildings/`(设施) + `tech/`(科技) |
| `palwork/palsave.py` | Python | 存档解析器（破解 PlM/Oodle 存档格式，解析 个人档案/背包/队伍/帕鲁箱/公会）|
| `palwork/liboo2core.so` | 二进制库 | Oodle 解压库（解 PlM 压缩存档需要）|

> `palwork/` 随插件一起装、按相对路径加载，**无需单独移动或改路径**（旧版本要求外移到 `data/palwork/`，现已自包含；若你旧部署把它放在外面，插件仍会回退兼容）。

## 安装

### 🚀 最快：一键脚本（从零到上线，纯小白推荐）
装好 [1Panel](https://1panel.cn/) 后，在它的**终端**里跑一行，自动装好「帕鲁服 + AstrBot + NapCat + 本插件」并补齐所有必需配置（含状态卡 CPU/内存要用的 `docker.sock` 挂载）：

```bash
# 先演练看看(只检测不改动)：
curl -fsSL https://raw.githubusercontent.com/dalimao113/astrbot_plugin_palworld/main/install.sh | bash -s -- --dry-run
# 正式安装：
curl -fsSL https://raw.githubusercontent.com/dalimao113/astrbot_plugin_palworld/main/install.sh | bash
```
已装过 astrbot/napcat/帕鲁服的会**只体检补配置**（改前备份+显示diff+确认，不破坏你的自定义配置）。完整图文教程见 **[docs/DEPLOY.md](docs/DEPLOY.md)** 第 1.5 章。

> 🖼️ **关于出图（t2i 渲染）**：本插件所有回复都是渲染成图片发出的。AstrBot 自带的渲染默认走**官方公共 t2i 端点**，偶发偏慢/502。一键脚本会额外部署一个**本地渲染服务** `astrbot-t2i`（`soulter/astrbot-t2i-service`），并把 AstrBot 的 `t2i_endpoint` 指向它（容器内 `http://astrbot-t2i:8999`），出图更快更稳。若出图很慢或失败，去 AstrBot WebUI「配置 → 其它 → 文转图」确认 `t2i_strategy=remote`、`t2i_endpoint` 已指向本地服务。

> 🔄 **后续更新**：只更新插件 → AstrBot「插件管理 → 更新」或插件目录 `git pull` 后重载。想连 AstrBot/NapCat/t2i/帕鲁镜像一起更 → 重跑脚本加 `--update`：`curl -fsSL .../install.sh | bash -s -- --update`（`git pull` 插件 + 拉各最新镜像并重建，不改配置）。普通重跑不带 `--update` 不会升级镜像。详见 [docs/DEPLOY.md](docs/DEPLOY.md) 第 10.4 节。

### 已有 AstrBot，只想加插件（4 步）
1. **装插件**：AstrBot WebUI「插件管理」填仓库地址 `https://github.com/dalimao113/astrbot_plugin_palworld` 安装；或用文件管理器把本仓库放进 `.../astrbot/data/plugins/astrbot_plugin_palworld/`。`palwork/`、数据、依赖都随插件自带,**无需手动移动文件**。

   > ⚠️ **手动下载 ZIP 安装务必改名**：从 GitHub「Code → Download ZIP」下载解压后，目录名是 `astrbot_plugin_palworld-main`（带分支后缀）。**必须把目录重命名为 `astrbot_plugin_palworld`** 再放进 `data/plugins/`——否则插件包名含非法字符 `-`，会导致插件加载失败（相对导入无法工作）。用 WebUI 填仓库地址安装 / `git clone` / 一键脚本 时目录名本就正确，无需改名。
2. **挂 docker.sock**（存档/负载功能需要,只查状态可跳过）：在 AstrBot 的 `docker-compose.yml` 加 `- /var/run/docker.sock:/var/run/docker.sock:ro`,重建 astrbot 容器。
3. **填两项必配**:WebUI → 插件配置,只需填 `admin_password`（帕鲁服的 `ADMIN_PASSWORD`）+ `admin_qq`（你的 QQ）。其余（容器名 / 存档目录 / API 地址）**能自动探测就自动**,一般不用动。
4. **自检**：发 `/帕鲁自检`（管理员）逐项确认环境 ✅,有 ❌ 按提示修。全绿即可开用。

> 从零到上线的小白教程（买服务器→装 Docker→出图）见 **[docs/DEPLOY.md](docs/DEPLOY.md)**,全程网页点鼠标。
> 1Panel 编排部署时插件目录:宿主机 `/opt/1panel/docker/compose/astrbot/astrbot/data/plugins/astrbot_plugin_palworld/`（对应容器内 `/AstrBot/data/plugins/astrbot_plugin_palworld/`）。
> 改完代码在 WebUI「插件管理 → 重载插件」热重载,无需重启容器。

## 对接的官方 REST API
`GET /v1/api/metrics`、`/players`、`/info`、`/settings`；
`POST /v1/api/announce`、`/kick`、`/ban`、`/unban`、`/save`、`/shutdown`、`/stop`。
全部走 HTTP Basic Auth（`admin` + `ADMIN_PASSWORD`），请求超时默认 5s，异常回离线/错误卡片。

---

## 部署说明（存档解析依赖 palwork）

本仓库**自带** `palwork/` 子目录（`palsave.py` + `liboo2core.so`，Oodle 解压库），供 `/帕鲁我`、`/帕鲁背包`、`/帕鲁队伍`、`/帕鲁箱`、`/帕鲁据点`、`/帕鲁公会` 等**存档解析功能**使用。**它随插件一起装，无需手动移动或改路径**——插件按相对自身目录加载，`.so` 也按 `palsave.py` 同级目录定位，装到哪跑到哪。

**存档功能的前置条件：**
1. **挂载 docker.sock**：AstrBot 容器读帕鲁服容器的存档 + 负载,需把宿主 docker socket 只读挂进 AstrBot 容器（见上文「服务器负载」章的 `volumes` 示例）。
2. **依赖 `palworld-save-tools==0.24.0`**：`requirements.txt` 已声明,AstrBot 装插件时会自动装。若容器重建后丢失（表现为"读不到存档"），在容器终端 `pip install palworld-save-tools==0.24.0` 重装即可（`/帕鲁自检` 会明确指出这一项缺失）。**必须锁 0.24.0**——`palsave.py` 的解析器针对该版本内部结构做了适配，装更新的版本会解析失败。
3. **存档目录 / 容器名：全自动**。`save_dir_in_container` 留空即自动探测 `SaveGames/0/` 下的世界 GUID 目录；`docker_container` 找不到时自动探测跑 palworld 的游戏服容器。一般无需手填。

> 装完发一条 **`/帕鲁自检`**（管理员）即可逐项确认：docker.sock / 帕鲁容器 / REST 密码 / 存档目录 / save-tools / 解析库 / 渲染 / 管理员白名单——每项 ✅⚠️❌ 带修复指引，配置对不对一目了然。

> 不需要存档功能（仅状态/在线/图鉴/配方/地图/竞技场等）时,不挂 docker.sock、不配存档也能用,存档类指令会提示未启用。

## 🔐 安全与权限

完整说明见 [SECURITY.md](SECURITY.md)。要点：

- **管理员白名单 `admin_qq`**：公告/踢/封/解封/存档/关服/重启/回档/重置/恢复/解绑/审计/自检/地图 等仅限白名单 QQ；查询类对所有群友开放。
- **二次确认**：封禁/关服/重启/回档/重置存档/恢复存档 发起后需管理员回复「帕鲁 确认」，超时作废。

### ⚠️ Docker socket 权限风险

> 挂载 `docker.sock` ≈ 赋予该容器近乎宿主机 **root** 的能力。请确保 AstrBot 本身可信、`admin_qq` 白名单配置正确。所有经 socket 的操作集中在 `api/docker_api.py`，高危写操作（关服/重启/删档/回档/exec/helper 容器）有 `[高危]` 注释并受白名单 + 二次确认保护。

### 普通模式 vs 运维模式

| 模式 | docker.sock | 能力 |
|---|---|---|
| **普通模式**（推荐，最小权限） | 不挂载 | 状态/在线/设置/图鉴/配种/公告/踢/封 等（走 REST API）。容器负载、存档解析、关服/重启/回档/删档 **不可用** |
| **运维模式** | 只读 `:ro` 挂载 | 额外启用 容器负载、存档解析（背包/队伍/我/公会）、关服/重启/回档/重置/恢复 |

内网红线：帕鲁 REST 端口（默认 8212）**只在内网**开放，切勿暴露公网。

## 📄 资源版权与授权说明

- **本项目代码**（`main.py` 及 `constants.py`/`config.py`/`commands/`/`services/`/`api/`/`render/`/`utils/`/`palwork/palsave.py` 等）以 **AGPL-3.0-or-later** 授权，见 [LICENSE](LICENSE)。
- **`palwork/liboo2core.so`**：Oodle 数据压缩库（RAD Game Tools / Epic Games 专有），**非本项目开源范围**。随插件提供仅为解析你本地服务器存档之便；版权归原厂商所有，请勿单独分发或作未授权用途。
- **`data/images/`（帕鲁/物品/建筑图标）、`bg*.jpg`**：来源于游戏《幻兽帕鲁 / Palworld》，版权归 **Pocketpair, Inc.**。仅用于非商业的信息展示（图鉴/卡片）。本项目**不主张对这些素材的任何权利，也不以开源协议授权它们**。
- **`data/*.json`（图鉴/配方/掉落等数值）**：整理自游戏数据，相关版权归 Pocketpair, Inc.；此处仅为便于查询的结构化整理。

> 若你是相关权利方并认为某资源不宜随仓库分发，请通过 issue/私信联系，我们会及时处理。以上第三方资源不因随本仓库分发而进入 AGPL 授权范围。
