# tools/game_data — 游戏数据提取工具链

把散落在仓库外隐藏目录(`/opt/palworld-khd/...`)的提取流程,逐步收敛成**仓库内可复现**的工具。
目标(CLAUDE.md):数据带 build id / source、不臆造未公开数值、生成失败不覆盖旧数据、能出差异报告。

> **本工具链需要游戏客户端 pak + usmap,只在有游戏文件的机器上跑;插件运行本身不依赖它。**

## 组成

| 脚本 | 作用(阶段) |
|---|---|
| `game_env.py` | 统一配置 + **来源采集**(discover):读 build id、usmap/pak 指纹、egame,写 `provenance.json` |
| `export_datatable.py` | **导出**(export):薄封装 dotnet CUE4Parse 导出器,把资产前缀下的 DataTable → JSON |
| `compare_data.py` | **差异报告**(compare):旧/新 JSON 按主键列增删改,重生成前后核对 |
| `clean_data_text.py` | 文本清洗(去零宽/占位/`<itemName>`),已用于 paldex/items |
| `extract_ingame_icons.py` / `gen_plugin_svgs.py` / `build_ingame_preview.py` | ingame 主题素材/预览 |

## 外部依赖(实测,本机)

- **pak**:`/opt/palworld-khd/extract/Pal-Windows.pak`(约 40GB,客户端 app 1623730)
- **usmap**:`/opt/palworld-khd/Mappings_10.usmap`(2.3MB)。1.0 用 unversioned properties,**必须**匹配版本的 usmap,只能从**运行中的客户端**用 Dumper-7/UE4SS dump(见 `/opt/palworld-khd/给Windows的ClaudeCode-提取Palworld1.0的usmap.md`)。
- **导出器**:`/opt/palworld-khd/work/exporter/`(dotnet 工程,基于 CUE4Parse)。CLI:
  `exporter <pakDir> <usmap> <aes> <outDir> <egame> <prefix1> [prefix2 …]`
- **dotnet**:`/opt/palworld-khd/dotnet/dotnet`(10.0.301)
- **服务端 build id**:`/opt/palworld/palworld/steamapps/appmanifest_2394010.acf` → `buildid = 24088465`

### 验证过的参数(build 24088465)

```
pakDir = /opt/palworld-khd/extract
usmap  = /opt/palworld-khd/Mappings_10.usmap
aes    = 0x0000…0000   (全零 32 字节;Palworld pak 用零密钥)
egame  = GAME_UE5_1
```

自测:`DT_PalMonsterParameter_Common` → 753 行;pak 文件总数 185003。全部路径可用环境变量覆盖
(`PAL_PAK_DIR / PAL_USMAP / PAL_AES / PAL_EGAME / PAL_EXPORTER / PAL_DOTNET / PAL_APPMANIFEST / PAL_EXPORT_OUT`)。

## 流程(重生成某类数据时)

```bash
# 1. discover:记录来源
python tools/game_data/game_env.py                      # -> provenance.json

# 2. 环境自检(缺文件会明确报缺什么,不伪造)
python tools/game_data/export_datatable.py --check

# 3. export:导出需要的 DataTable(前缀是 pak 内路径)
python tools/game_data/export_datatable.py Pal/Content/Pal/DataTable/Quest

# 4. build:用对应 build_*.py 从 exported/ 组装成 data/<x>.json
#    (build 脚本目前仍在 /opt/palworld-khd/work/,随 C/E/F 逐个收进本目录)

# 5. compare:重生成前把旧文件留存为 <x>.old.json,再核对增删改
python tools/game_data/compare_data.py data/missions.old.json data/missions.json

# 6. clean:文本统一清洗(如涉及描述字段)
python tools/game_data/clean_data_text.py --apply
```

**生成失败不覆盖旧数据**:build 脚本先写 `*_new.json`,compare 核对通过再替换 `data/`。

## 尚未收进本目录(逐步迁移)

外部 `/opt/palworld-khd/work/` 里的 `build_missions.py`、`build_breeding.py`、公会解析脚本等,
在对应阶段(C 任务 / E 公会 / F 配种)重生成时随之整理进本目录并配 provenance,不长期依赖仓库外路径。
