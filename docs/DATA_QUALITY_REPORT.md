# Palworld 1.0 数据质量与纠错报告

> 「1.0 功能纠错与数据补全」审计 + 增量记录。状态基于**当前代码/数据实测**,不按描述盲填。
> 最后核对:2026-07-13。

## 0. 环境与来源(阶段 A)

| 项 | 值/路径 | 备注 |
|---|---|---|
| Dedicated Server build id | **24088465**(`appmanifest_2394010.acf`,LastUpdated 1783820519) | 服务端构建号,可记录 |
| 客户端 pak | `/opt/palworld-khd/extract/Pal-Windows.pak`(40GB) | 可提取 DataTable/纹理/本地化 |
| 服务端 pak | `/opt/palworld/palworld/Pal/Content/Paks/Pal-LinuxServer.pak` | |
| 提取器 | `/opt/palworld-khd/dotnet/dotnet` + `.../work/exporter`(DataTable→JSON)+ `.../work/texexport`(纹理→PNG) | **需收进 `tools/game_data/`(待办)** |
| 实时 REST API | 宿主机 **`http://127.0.0.1:8212`**(容器 `palworld-server` 端口映射;`palworld-server:8212` 是 docker 内网名,仅容器间可用) | ✅ **可达**。版本 **`v1.0.0.100427`**、worldguid `3C5CF320...` |
| `/v1/api/game-data` | — | 🔴 **本构建 404**(不存在!)→ 公会/地图**不能依赖 `/game-data`**,须走 `/players` + 存档 |
| `/v1/api/players` | — | ✅ 有 `location_x/y`(**世界坐标**)、level、ping、playerId、userId(steam_…);**无 GuildID/GuildName** |
| 真实 1.0 存档 | `/opt/palworld/palworld/Pal/Saved/SaveGames/0/3C5CF320.../Level.sav` | ✅ 可读(**只读副本调试,用完删,绝不改服务端存档**) |

> ⚠️ 客户端(app 1623730)自身的 build id 无 appmanifest 可查;记录服务端 24088465 + 客户端 pak 路径。
> `breeding.json._meta.steam_build_id` 当前为 `unknown`,重生成后应写 24088465(或客户端实际构建号)。

## 1. 审计:已确认属实的问题(实测数字)

| # | 问题 | 实测 | 状态 |
|---|---|---|---|
| 1 | 图鉴 `related_technology.description == "zh-hans text"` | **80** 条 | ✅ 已修 |
| 2 | 未解析 `<itemName id=|...|/>`(`technology_name`) | **2**(薇莉塔/黑月女王) | ✅ 已去除(正确名需本地化表) |
| 3 | items.json 零宽字符 | U+200B×2, U+200C×1 | ✅ 已修 |
| 4 | `黑月女王 ` 尾空格 | 1 条 | ✅ 已修(数据+索引去空格) |
| 5 | `叶泥泥` 同名(本体+花变种)`_pal_by_name` 后写覆盖 | PlantSlime(可收集)/PlantSlime_Flower(变种) | ✅ 已修(优先可收集) |
| 6 | items.json 中文重名组 | **150** 组(655 项,武器品阶 _2.._5 + _NPC) | ✅ 已修(增量D:名称主键确定性取本体、变体保留于 `_items_by_name`、可按 item_id 直查) |
| 7 | 任务 107 条:3 组同名、`_mission_by_name` 覆盖、next=None×53、next 内部ID×54、`Main_BuildWorkBench` 只有 `_Old`、`subs[:30]` | 全属实 | ✅ 已修(阶段C:DataTable 重生成 105 active,next→本地化名,_Old 分离,重名候选+id直查,支线分页) |
| 8 | `_world_to_mappct` 把世界树坐标 clamp 到 0–100 | line 1822 | ✅ 已修(增量2:map registry + `_classify_map` 去 clamp + 多地图面板) |
| 9 | `_rank_list` 只读 week;`排行` 无 `pass_args` | 确认 | ✅ 已修(增量G:scope 本周/今日/总榜 + pass_args + 统计起点) |
| 10 | `breeding._meta.steam_build_id == unknown` + 生成器未入库 | 确认 | ✅ 已修(阶段F:生成器入库、重生成写 build 24088465、校验通过、数据体与旧完全一致) |
| 11 | 详情硬截断 `[:120][:90][:34]…` | 多处 | ✅ 已修(增量D:帕鲁详情 desc/partner_desc、物品 desc 去截断走 clean_text;列表页摘要保留) |
| 12 | 公会名丢弃、成员段字节猜测、`extract_guilds` 静默吞异常 | ✅ 实测:真实存档 1 个 Guild + 7 Org,`extract_guilds` 返回 **0**(确坏);**1.0 公会 RawData 格式已变**,连官方 `palworld_save_tools 0.24.0` 的 `group.decode_bytes` 也崩在 `map_object_instance_ids_base_camp_points`(`could not read 16 bytes for uuid`) | ✅ 已修(阶段E:逆向 1.0 格式,`_parse_guild_1_0` 真实存档验证——1 公会/12 成员/会长/公会名全解出) |

## 2. 本次已修复并验证(增量 1:数据准确性,不依赖 API/存档)

- **统一文本清洗** `utils/text.clean_text()` / `is_missing_text()`:解析 `<itemName id=|X|/>`(可选 resolver)、去 UE 样式标签、统一 CRLF/CR→LF、去零宽/控制字符、占位("zh-hans text"/"None")→空、**保留 Emoji**。
- **可复现数据清洗** `tools/game_data/clean_data_text.py`(临时→校验→原子替换,不手工改 JSON):
  - paldex/items 去零宽;pal_name/technology_name 去空格;描述占位→空;`<itemName>` 去除。
  - 结果:`<itemName>` 0 / `zh-hans text` 0 / 零宽 0 / pal_name 首尾空格 0(4289 字段归一)。
- **名称索引** `main._load_paldex`:pal_name 去首尾空格写回;同名优先可收集本体(叶泥泥→PlantSlime);黑月女王去空格后可查。
- **测试** `tests/test_data_quality.py`(6 项,全过):clean_text 行为 / 数据无占位·标签·零宽 / 名称无空格 / 索引优先可收集。

**验证命令**:`python tools/game_data/clean_data_text.py`(dry-run 报「残留问题:无」)。

## 2b. 本次已修复并验证(增量 2:在线地图去 clamp + 多地图分类)

- **地图注册表** `main._MAP_REGISTRY`:`main`(主大陆)/`tree`(世界树)各自独立仿射变换,可扩展。
- **世界坐标归类** `main._classify_map(wx,wy)`:按各地图仿射把世界坐标算成图片百分比,**落在 [−3,103]²(容边)才归该图,不 clamp**;都不落 → `unknown`。
  - 消除旧 `max(0,min(100,·))` 把世界树玩家压到主图边缘的错标。
- **多地图渲染** `_cmd_map`:按地图分组,每张有玩家的地图独立面板(底图+定位点+名单);无法归类的玩家进「位置待确认」单列,不伪造主图位置。三套主题 `map` 模板同步改为 `maps:[{label,mapimg,players}]` + `offmap`,契约一致。
- **未验证标签纠正**:habitat 里世界树底图标签 `世界树 · Sunreach` → `世界树`(Sunreach 归属未经游戏文件确认,不臆断合并)。
- **测试** `tests/test_map_classify.py`(4 项,全过):实测在线玩家(青天如墨,世界坐标 −347243/263804)归主图(68%/48%);世界树变换中心归 tree;远越界 → unknown 不压边;主/树区间不重叠。坐标取自真实 `/players`。

**验证命令**:`python -m pytest tests/test_map_classify.py -q`。多地图预览见 `docs/ingame_预览/map_multi_*.html`(本地生成,未入库)。

## 2c. 本次已修复并验证(增量 G:累计排行榜 本周/今日/总榜)

- **三口径排行** `_rank_list(top, scope)`:`week` 本周 / `today` 今日 / `total` 累计总榜,分别读 `totals[uid]` 的 `week`/`day`/`total`(过期周·日不计入)。默认 `week`,旧调用(早晚报/结算)行为不变。
- **`/帕鲁排行` 支持参数** `_cmd_rank(event, args)` + `_rank_scope`:`/帕鲁排行 今日`、`/帕鲁排行 总榜`(别名 累计/历史/total…);裸 `/帕鲁排行` 仍为本周。router spec 加 `pass_args=True`。
- **统计起点** `tracking_started_at`:全新/重置 state 从当天起算;**历史 state(已有 totals 却无起点)标 `None`,展示为「起点未记录」,不臆断日期**(总榜副标题据此显示「自 YYYY-MM-DD 起」或「未记录」)。
- 三套主题帮助卡 `/帕鲁肝帝榜` 行同步标注 `[今日/总榜]`。
- **测试** `tests/test_rank_scope.py`(5 项,全过):三口径读对字段·过期周排除·总榜累计反超·关键词解析·起点未知不臆断。

**验证命令**:`python -m pytest tests/test_rank_scope.py -q`。排行预览见 `docs/ingame_预览/rank_{week,today,total}_*.html`。

## 2d. 本次已修复并验证(增量 D 纯代码部分:详情去截断 + items ID 主键)

- **详情去硬截断**:`_pal_card_data` 的 `pal_description`(此前 `[:120]`,实测最长 93,截断为死代码)、`partner_skill_description`(此前 `[:90]`,**实际截掉了凉晶鲸/桃晶鲸/拉比耶尔/海皇鲸 4 只鲸鱼的 91–94 字描述**)改为完整;物品详情 `description` 同样去截断。全部改走统一 `clean_text`,不再各 handler 各自 `replace`。模板本就 `white-space:pre-line;word-break:break-word` 自动换行。
  - 列表页摘要(任务/技能 brief 的 `[:22]/[:14]`、突变 5 蛋糕网格 `[:70]`)按规则保留,不属详情。
- **items 名称主键**:150 组中文重名(655 项,武器 `_2.._5` 品阶 + `_NPC`)此前 `setdefault` 按文件顺序静默取首个。改为:
  - `_items_by_name` 保留同名全部变体(不丢弃);
  - `_item_by_name` 以 `_item_variant_rank` **确定性取本体**(item_id 无 `_2.._9` 品阶、无 `_NPC` 后缀,再按 id 短);
  - `/帕鲁物品 <item_id>` 可精确直查任一品阶/NPC 变体(ASCII id 与中文名不冲突)。
- **测试** `tests/test_item_index.py`(3 项,全过):变体排序取本体、加特林机枪/太刀/激光步枪名称主键取 base、变体不丢弃且可 id 直查。

## 2e. 本次已落地(阶段 A:提取工具链入库,C/E/F 的公共前置)

把仓库外隐藏目录的提取流程收敛成**仓库内可复现**工具(`tools/game_data/`):
- `game_env.py`:统一配置(路径全可环境变量覆盖)+ **来源采集**,写 `provenance.json`——build id `24088465`、usmap sha256、pak 指纹、egame `GAME_UE5_1`、dotnet `10.0.301`。
- `export_datatable.py`:薄封装 dotnet CUE4Parse 导出器(`exporter <pakDir> <usmap> <aes> <outDir> <egame> <prefix…>`)。**实测参数**:pakDir=`/opt/palworld-khd/extract`、usmap=`Mappings_10.usmap`、aes=全零 32 字节、egame=`GAME_UE5_1` → `DT_PalMonsterParameter_Common` 753 行、pak 文件 185003。`--check` 缺文件明确报缺,不伪造。
- `compare_data.py`:旧/新 JSON 按主键出增删改差异报告(支持 list[dict] 与 DataTable 导出结构),满足「数据更新须能出差异报告、失败不覆盖旧数据」。
- `README.md`:外部依赖、验证参数、discover→export→build→compare→clean 流程、逐步迁移计划。
- 其余 `build_*.py`(任务/配种/公会)仍在外部,随 C/E/F 重生成时迁入并配 provenance。

**验证命令**:`python tools/game_data/game_env.py`、`python tools/game_data/export_datatable.py --check`、`python -m pytest tests/test_game_data_tools.py -q`。

## 2f. 本次已修复并验证(阶段 C:1.0 任务重建)

数据从 DataTable 重生成(**不手工改最终 JSON**),`tools/game_data/build_missions.py`(已迁入):
- 源:`DT_PalQuestData`(120 行)+ `DT_PalQuestLocationData` + BP CDO(`bp_out`)+ zh-Hans 本地化(`DT_UI/NpcTalk/MapObjectName`)。
- **区分 active/_Old**:`_Old` 不进 active(105 条 = 主线55/支线50)。`Main_BuildWorkBench` 只有 `_Old`、1.0 无 active → 指向它的 next 判悬挂丢弃;真 active 是大小写不同的 `Main_BuildWorkbench`(旧数据 next 大小写写错才显"悬挂")。
- **next→本地化名**:`AutoOrderQuests[0]`(内部 dev id)解析成目标 active 任务中文名,存 `next`;有效才留 `next_id`。**不再出现字面 "None"、不再泄露内部 id、无悬挂**(丢弃 2 条)。
- 保留人工整理的 `group`/`order`(DataTable 无此语义,按 id 从旧数据继承)。旧文件留 `data/missions.old.json`(gitignore)。重生成带 `compare_data` 差异报告:仅删 2 条 `_Old`、其余为 next/next_id 字段更新。
- **消费端修复**:`_mission_by_name` 不再 last-wins 覆盖 → 主键取确定性主体(主线优先、非 `_Replay`、order/id),`_missions_by_name` 留全部候选,`_mission_by_id` 支持 **id 直查**;精确重名查返回候选列表(brief 带 id 可精确追);`/帕鲁支线` **补分页**(此前 `subs[:30]` 截断)。
- **测试** `tests/test_missions.py`(4 项)+ `tests/test_game_data_tools`:无 `_Old`、next 无悬挂/None、重名主键确定性+候选保留+id 可查。

## 2g. 本次已修复并验证(阶段 F:配种重生成 + 继承来源标注)

- **生成器入库** `tools/game_data/build_breeding.py`:源 `DT_PalCombiUnique`(特殊组合)+ `DT_PalMonsterParameter`(CombiRank/ZukanIndex/IgnoreCombi)。算法=特殊组合优先→同双亲→通用公式 `target=(rankA+rankB+1)//2` 取最近非变体。
- **重生成校验**:261 可配种、150 特殊组合、261 子代、34191 父母对;校验 CombiUnique 100% 复现、A+B=B+A 对称、无重复对、编号有效。`compare_data` 对比:**新数据体与旧完全一致(+0/-0/~0)**——说明数据本就正确,只是 `_meta` 陈旧。
- **#10 修复**:`_meta.steam_build_id` `unknown` → **24088465**,补 `source`(标注算法+「配种概率游戏未公开,仅组合→子代映射」)、`parent_count`。旧文件留 `data/breeding.old.json`(gitignore)。
- **继承模型标注来源**:`/帕鲁继承` 的 40/30/20/10 词条继承分布是**社区实测模型、非游戏官方公开数值**,三套主题卡片脚注已明确标注「社区实测模型,游戏未公开官方数值,仅供参考」(此前只写"模型"未说明来源)。突变卡此前已标「概率游戏未公开,仅说明机制」。
- **测试** `tests/test_breeding.py`(3 项):_meta 真实 build id、编号有效+对称无重复、child_count 一致。

**验证命令**:`python tools/game_data/build_breeding.py`(dry-run 报校验通过 + 差异 0)、`python -m pytest tests/test_breeding.py -q`。

### 配种覆盖深挖(回应「只有261只吗/新帕鲁」)

- **261 是游戏权威口径**:paldex 289 实体中,可配种 261 只由游戏 `DT_PalMonsterParameter.IgnoreCombi` 标志界定;其余 28 只全部是游戏**主动标记不可配种**的 boss/塔主/传说/变体(旺财、空涡龙 Jetragon、圣光骑士 Paladius、混沌骑士 Necromus、唤冬兽 Frostallion、海皇鲸、奥沧鲸、世界树 boss 暮尘蛾/夜蔓爵、女王/龙人系塔主及其暗/水变体等),**非数据缺漏**。0 只有 CombiRank 却被漏、0 只不在 DataTable。
- **传说无"漏配"**:`DT_PalCombiUnique` 里凡以传说为子代的特殊组合,父母必含一只 IgnoreCombi 传说(自交 X+X→X 或需传说当亲代),现实不可达 → 传说确实不可配出,只能捕捉。
- **100% 子代覆盖 + 图闭合**:261 只可配种帕鲁**全部**能作为子代配出;出现为父母的集合 == 子代集合(闭合图)。新帕鲁若可配种必同时进父母/子代两侧,`test_breeding_graph_closed_full_coverage` 守护。
- **多代配种可用**:`/帕鲁怎么配 <目标>` 是正向 BFS(上限 60 步,**任意代数**,不止三代),从玩家帕鲁箱现有帕鲁算最短链;`/帕鲁反配种 <目标>` 给直接亲代对(分页)。修正 `反配种` 帮助例(空涡龙不可配种)→ 铠格力斯(Anubis,可配种经典目标)。
- `_meta.breedable_note` 已写入上述口径,避免"为什么不是287"的重复疑问。

## 2h. 本次已修复并验证(阶段 E:1.0 公会格式逆向 #12)

真实存档只读副本逆向(用完即删,绝不改服务端存档):
- **定位 1.0 变化点**:公会 RawData 头部 `group_id + group_name + individual_character_handle_ids + org_type + base_ids + base_camp_level` **未变**(可解析到 base_camp_level);其后的 `base_camp_points` 段字节格式**变了**(官方 0.24.0 在此 `could not read 16 bytes for uuid` 崩)。
- **关键发现**:段内**玩家记录结构没变**——`PlayerUId(16:前4字节非0+后12字节零) + last_online(i64) + name(fstring, utf-8/utf-16)`;`group_name` 字段就是**会长的 PlayerUId**。
- **`_parse_guild_1_0`**(`palwork/palsave.py`):解析到 base_camp_level 后扫描字符串,凡前置 24 字节符合 PlayerUId+时间戳的即成员记录,首个不符合的即 `guild_name`。`extract_guilds` 改为 1.0 优先、旧格式回退。
- **真实存档验证**:1 个 Guild → `guild_name="Unnamed Guild"`、**12 名成员**(uid+last_online+名,含中文名)、**会长=大狸猫**(与 owner UID 对应)。此前 `extract_guilds` 返回 0(功能全死)。
- **展示**:`_guild_display_name` 玩家自定义了公会名就用真名,游戏默认名(Unnamed Guild)/空则回退「队长」的公会。`/帕鲁自检` 新增"公会解析"诊断行(公会数/成员数/是否自定义名)。
- **测试** `tests/test_guild_parse.py`(2 项,**脱敏合成**字节,非真实玩家数据):中文/ASCII 名+uid+会长解析、默认名回退展示。真实存档结构本机验证、不入库。

## 3. 仍无法从游戏文件确认 / 需后续提取的字段

- `<itemName id=|SkillUnlock_VioletFairy|/>`、`SkillUnlock_LilyQueen_Dark` 的**正确中文名**:需从客户端本地化表(`SkillUnlock_*` → 名称)提取,当前按「不猜测」去除。
- 任务顺序/前后置/发布 NPC/目标数组、世界树 vs Sunreach 归属、boss 所属地图、breeding 权重、突变概率:均需游戏 DataTable/本地化重生成,未提取前不显示猜测值。

## 4. 后续阶段计划(需游戏文件/存档/实时 API)

| 阶段 | 依赖 | 计划 |
|---|---|---|
| A 提取器入库 | 客户端 pak(有) | ✅ 已落地骨架:`tools/game_data/{game_env,export_datatable,compare_data}.py` + README + `provenance.json`(build 24088465)。build_*.py 随 C/E/F 逐步迁入 |
| B 多地图 + 在线地图 | `DT_WorldMapUIData` + `/game-data`(不可达) | map registry(map_id/transform/bounds)、spawn 存世界坐标、去 clamp、多面板;`/game-data` 实测 Stage 语义后再定分类 |
| C 任务重建 | 任务 DataTable + 本地化 | ID 主键、区分 active/_Old、消歧、next→本地化名、分页、图校验 |
| D 图标/本地化 | 纹理 + `icon_asset`/SoftObjectPath + 本地化 | icon manifest(业务ID→资产→输出→状态)、补 1物品/10科技/3设施、`<itemName>` 真解析 |
| E 公会 | 真实 1.0 存档 + `/game-data` | `GroupSaveDataMap` 结构重解、真实 group_name、匿名 fixture、诊断入自检 |
| F 配种/继承/突变 | 客户端 DataTable/Curve | breeding 重生成(build id)、继承模型标注来源、突变仅显可确认值 |
| G 累计排行榜 | 无(state.json) | `pass_args`、`_rank_list(top, scope)`、总榜标注「自插件统计起」、旧 state 迁移 |
