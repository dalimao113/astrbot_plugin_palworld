---
paths:
  - "data/**/*.json"
  - "palwork/**/*"
  - "tools/game_data/**/*"
  - "services/save_service.py"
  - "tests/**/*data*"
  - "tests/**/*save*"
---

# Palworld 数据与存档规则

编辑上述路径(数据/存档解析/数据工具)时,遵守以下规则。总纲见根目录 `CLAUDE.md`。

## 数据口径与版本
- 数据必须标注 `game_version` / `steam_build_id` / `generated_at` / `source`(如 breeding.json 的 `_meta`)。
- **不得把 DataTable 行数/数据实体数冒充官方图鉴数**。
  - 现口径:**287 官方可收集 / 289 数据实体**(差 2 = `WorldTreeDragon` 枯星龙剧情最终 boss + `PlantSlime_Flower` 花叶泥泥变种,DT `ZukanIndex`/`IsPal` 权威定位),已用 `is_collectible`/`is_variant`/`is_story_only` 等字段标记,**不删除**。
- 官方未公开的数值/概率(如浓缩需求数、突变概率)**不得伪造**,标注"游戏未公开"或"仅说明机制"。

## 引用与校验
- 所有外键引用(配种父母/子代编号、掉落物品、技能、栖息 dev 等)必须校验有效。
- 配种更新时检查:父母/子代编号有效、A+B=B+A 对称、无重复组合、特殊组合正确、旧版结果已失效。
- 数据生成失败**不得覆盖**上一版可用数据;每次数据更新应能生成差异报告。

## 存档解析(palwork/palsave.py)
- 1.0 存档 worldSaveData 顶层有 `SetProperty`(InLockerCharacterInstanceIDArray),须由跳过器识别(读 inner 类型名+可选 GUID 后按 `size` 整块 skip),否则整份存档解析崩溃。此兼容有 `tests/test_palsave.py` 回归护栏。
- 遇 `Unknown type: XxxProperty` 一律同法:按 `size` 跳过、对齐到下一属性;**不得为避免报错而静默吞掉关键数据**,对不支持的新结构输出明确日志。
- **修改存档解析必须用真实或脱敏样本验证**;无真实 1.0 存档验证时,不得声称"已兼容"。
- 调试存档:拉只读副本 → 容器内 `palsave.extract_profiles` → **用完 rm -rf,绝不提交**(玩家隐私)。
- 觉醒状态:存档帕鲁 SaveParameter **无觉醒字段**(`Rank_HP/Attack/Defence` 是浓缩非觉醒),当前**不支持读取觉醒状态**,只做百科查询。

## 工具化
- 数据/素材提取工具逐步收进 `tools/game_data/`,不长期依赖仓库外隐藏目录(如 `/opt/palworld-khd/work`)。
