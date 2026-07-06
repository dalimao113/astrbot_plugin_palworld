# 更新日志

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [1.2.1] - 2026-07-06

### 文档 / 发布一致性
- 统一版本号：`pyproject.toml` 补齐到与 metadata.yaml / `main.py @register` / README 一致；新增 `tests/test_version.py` 防止三处版本再次漂移。
- 依赖声明：`jinja2` 判定为仅本地渲染用，移入 pyproject `optional-dependencies.local-render`，使主依赖与 requirements.txt 一致。
- README 修正：`/帕鲁风格`（不存在的命令）改为"WebUI 配置 card_style 切换"；项目结构表更新为模块化后的实际结构；补充"手动下载 ZIP 安装须把目录改名为 astrbot_plugin_palworld"的说明（避免包名含非法字符导致加载失败）。
- 部署教程（docs/DEPLOY.md）第 6 章重写：NapCat WebUI token 的三种查法（含 1Panel 文件管理器打开 `napcat/config/webui.json`）；NapCat↔AstrBot 改为准确的**反向 WebSocket**（`ws://astrbot:6199/ws`）说明与 aiocqhttp 适配器关键参数。
- 一键脚本 `install.sh` 收尾提醒增强：token 查找方式、反向 WS、`admin_qq` 必填 更醒目。

### 帕鲁详情卡增强（队伍 / 帕鲁箱查询）
- 每只帕鲁新增显示：**攻击 / 防御**（种族基础值）、**工作速度**、**工作适性**（带工种图标 + 等级）、**伙伴技能**（名称 + 详细解释）；数据均来自图鉴，准确无误差。
- `生命IV / 攻击IV / 防御IV` 改名为直观的 **生命天赋 / 攻击天赋 / 防御天赋**（即游戏内"天赋"，个体值 0–100）。
- 补全 `data/passives.json` 词条数据：**负面词条**（胆小/弱不禁风/笨手笨脚等）标记为红色并补上效果数值（如"攻击 -10%"），**正面词条**标金/彩，**牧场产出/特性**类标中性灰——好词条、坏词条一眼可分，且每个词条都有效果解释。

## [1.2.0] - 2026-07-06

### 工程重构（无功能变化）
- 将 9200+ 行的单文件 `main.py` 分层拆分为 `constants.py` / `config.py` / `commands/` / `services/` / `api/` / `render/` / `utils/`，`main.py` 降至约 5400 行（仅保留插件入口、生命周期、Handler、命令分发与薄包装）。AstrBot 加载入口不变。
- 命令分发改为注册表模式（`commands/router.py` 的 `CommandSpec`/`COMMANDS`），`_dispatch` 与 `_SUB_ALIASES` 由单一事实来源派生；全部中文/英文别名、管理员权限、二次确认、冷却语义保持不变。
- REST 请求与 Docker socket 操作拆到 `api/palworld_api.py`、`api/docker_api.py`（高危操作加权限风险注释）。
- 存档拉取/缓存/负缓存/强制存盘编排拆到 `services/save_service.py`，`palwork/palsave.py` 专注纯解析。
- 卡片模板与渲染引擎拆到 `render/templates.py`、`render/renderer.py`；卡片样式与图片输出不变。

### 体验改进
- 个人自助查询（`/帕鲁我`·`背包`·`队伍`·`帕鲁箱`·`据点`·`公会`·`配种路线`）改用较短的缓存有效期（与强制存盘节流 `force_save_min_interval` 对齐，默认 15 秒），玩家在游戏内刚获取的物品/帕鲁/天赋点能尽快查到最新，而非等满 `save_cache_ttl`（默认 120 秒）。榜单类聚合查询（战力榜/资产榜/图鉴榜/公会榜等）沿用长缓存，不增加服务器负载。

### 安全增强
- 新增用户输入长度限制与控制字符清洗（`utils/security.py`）：喊话/公告/理由/角色名限长，指令参数全局限个数与长度。
- 集中并加固 Docker socket 高危操作的权限注释；tar 解包路径穿越防护、存档解压炸弹上限、HTML 转义、API 凭据不入日志等已就地保留说明。

### 配置
- 修正两处代码默认值与 `_conf_schema.json` 不一致：`local_render`（应默认关闭）、`backup_keep_max`（应默认 0=交给镜像清理）。
- schema 补齐此前代码在用但未暴露的 `force_save_min_interval`、`save_neg_ttl`。
- 新增启动配置校验（QQ/群号/路径/容器名/api_base/时间格式），问题写入日志且不阻断加载。

### 工程规范
- 新增 `pyproject.toml`、`tests/`（pytest，含配置一致性、命令别名、路由、存档缓存、渲染、安全等测试）、`.github/workflows/ci.yml`（py_compile + JSON 校验 + ruff + pytest）。
- 新增 `LICENSE`(AGPL-3.0)、`SECURITY.md`、`CONTRIBUTING.md`、`CHANGELOG.md`、`.gitignore`。
- 清理仓库中无用的 `data/*.json.bak*` 编辑残留，停止追踪编译产物 `__pycache__`。
