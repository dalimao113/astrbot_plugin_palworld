# 安全说明

本插件可读写你的帕鲁服务器与宿主机 Docker，请务必阅读本文件。

## 报告安全问题

发现安全漏洞请**不要公开提 issue**，请私下联系仓库作者（GitHub 主页邮箱 / 私信）描述问题与复现方式。我们会尽快修复后再公开。

## 权限模型

- **管理员白名单（`admin_qq`）**：只有白名单内的 QQ 能执行 公告/踢/封/解封/存档/关服/重启/回档/重置/恢复/解绑/审计/自检/地图 等写操作或敏感操作。非白名单用户触发会被拒绝并记警告日志。
- **二次确认**：封禁/关服/重启/回档/重置存档/恢复存档 等高危操作发起后，需管理员在超时时间内回复「/帕鲁确认」才执行，超时作废。
- 查询类指令（状态/在线/图鉴/背包等）对所有群友开放。

## Docker socket 权限风险（务必了解）

部分功能（容器 CPU/内存、拉存档解析、关服/重启、删档重开/回档/恢复、备份清理）依赖把宿主机 `docker.sock` 挂进 AstrBot 容器：

```yaml
# astrbot 的 docker-compose
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

> ⚠️ **挂载 `docker.sock` ≈ 赋予该容器近乎宿主机 root 的能力。** 任何能在 AstrBot 容器内执行代码的人都可借此控制宿主 Docker。请确保 AstrBot 本身可信、且插件的 `admin_qq` 白名单配置正确。
>
> ⚠️ **`:ro` 不是安全边界。** 它只让 socket **文件节点**只读，**完全不限制 Docker API 的写操作**——挂了 `:ro` 的 socket 依旧能 `stop/exec/create/run`（本插件的关服/删档/恢复正是靠它工作）。因此 `:ro` 与 `rw` 在能力上**等价于宿主机 root**，没有区别。唯一真正的安全边界是**是否挂载 socket** + **`admin_qq` 白名单**,请勿把 `:ro` 当成"最小权限"。

所有经 `docker.sock` 的操作都集中在 `api/docker_api.py`，其中 `container_action(stop/start/restart)`、`docker_exec`、`run_helper` 为高危写操作，代码中已用 `[高危]` 注释标注，并由上层管理员白名单 + 二次确认保护。

### 普通模式 vs 运维模式

- **普通模式（推荐，最小权限）**：**不挂** `docker.sock`。可用全部查询/图鉴/配种/公告/踢/封等（走 REST API）。容器负载、存档解析（背包/队伍/我/公会）、关服/重启/回档/删档等**不可用**，插件会静默跳过或提示。
- **运维模式**：挂载 `docker.sock`（示例用 `:ro`，但如上所述 `:ro` **不降低**其宿主 root 级能力，仅是习惯写法）。启用容器负载显示、存档解析、以及关服/重启/回档/重置/恢复等运维能力。**仅在你完全信任该运行环境时启用。**

## 已实施的防护

| 面向 | 措施 | 位置 |
|---|---|---|
| REST 凭据 | `admin_password` 仅经 HTTP Basic Auth 头传递，**不写入日志**（失败日志只记路径与异常） | `api/palworld_api.py` |
| 存档解压 | Oodle/zlib 解压尺寸上限 512 MiB，防解压炸弹 | `palwork/palsave.py` |
| tar 解包 | `filter="data"`（Py3.12+）/ 手动拒绝绝对路径、`..` 穿越、symlink/hardlink | `api/docker_api.py` |
| XSS | 玩家可控字段（昵称/公会名/喊话/公告等）放入卡片前一律 `_esc` HTML 转义（Jinja autoescape 关闭是有意的，转义由调用方负责） | `utils/text.py` + 各 handler |
| 输入长度 | 喊话/公告/理由/角色名等限长 + 清洗控制字符；指令参数全局限个数/长度 | `utils/security.py` |
| 临时文件 | 拉取的存档临时目录用后即删；本地渲染的临时 JPEG 定期清理 | `services/save_service.py`、`render/renderer.py` |
| 配置校验 | 启动校验 QQ/群号/路径/容器名/api_base/时间格式，问题写清晰日志（不阻断加载） | `config.py` |

## 敏感配置

- `admin_password` 对应帕鲁容器的 `ADMIN_PASSWORD`。请勿泄露、勿提交到公开仓库。
- 建议帕鲁 REST 端口（默认 8212）**只在内网**开放，切勿暴露公网。
