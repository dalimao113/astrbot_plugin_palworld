# 贡献指南

欢迎 PR / issue。本插件运行于 AstrBot（`>=4.25,<5`），Python 3.10+。

## 项目结构（分层）

```
main.py          轻入口：插件类 + 生命周期(__init__/terminate) + AstrBot Handler +
                 命令分发 _dispatch + 业务 _cmd_* + 对各模块的薄包装调用
constants.py     常量 / 静态映射表
config.py        配置默认值(规范单一来源，与 _conf_schema.json 对齐) + 校验
commands/router.py  命令注册表(CommandSpec/COMMANDS)：子命令→处理器 的单一事实来源
services/        save_service.py  存档拉取/缓存/负缓存/强制存盘编排
api/             palworld_api.py(REST)  +  docker_api.py(docker.sock，含高危权限注释)
render/          templates.py(HTML/CSS 模板 + 皮肤)  +  renderer.py(渲染引擎)
utils/           text.py(HTML 转义等)  +  security.py(输入长度限制)
palwork/         palsave.py  纯解析(GVAS/Oodle) + liboo2core.so
```

约定：
- **AstrBot 入口永远留在 `main.py`**（插件类、`@register`、`@filter.*` Handler、`_dispatch`）。业务逻辑拆到外部模块，由 `main.py` 调用。
- 新增/修改命令：改 `commands/router.py` 的 `COMMANDS` 表；**触发正则 `@filter.regex` 是有意手维护**（只枚举可无空格粘连触发的子集），勿改成从全表自动生成（会新增误触发）。
- 所有玩家可控字段进卡片前必须 `_esc` 转义。经 `docker.sock` 的新操作放 `api/docker_api.py` 并加权限注释。
- 配置默认值改动要同时改 `config.py` 的 `DEFAULTS` 与 `_conf_schema.json`（测试会断言两者一致）。
- 发版时版本号两处同步：`metadata.yaml` 的 `version` 与 `main.py` 的 `@register(...)`。

## 本地开发与测试

宿主机通常无 astrbot 运行时；测试用内联 stub（见 `tests/conftest.py`），无需真实 astrbot。

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install pytest ruff jinja2

# 提交前请全部跑通（与 CI 一致）：
python -m py_compile main.py palwork/palsave.py
python -m json.tool _conf_schema.json > /dev/null
find data -name "*.json" -print0 | xargs -0 -I{} python -m json.tool "{}" > /dev/null
ruff check .
pytest
```

## 在 AstrBot 中验证

在 AstrBot WebUI「插件管理」重载本插件，然后在群里发 `帕鲁 状态` / `帕鲁 帮助` 等确认出图正常、日志出现 `[帕鲁管家] 插件已加载`、`配置校验通过`。

## 授权

提交即表示你同意你的贡献以本项目的 LICENSE（AGPL-3.0-or-later）发布。注意：`palwork/liboo2core.so` 与 `data/images/`、`bg*.jpg` 等第三方/游戏资源**不在**本项目开源授权范围内，见 README「资源版权与授权说明」。
