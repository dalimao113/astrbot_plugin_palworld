# 从零开始的完整部署教程（小白向 · 1Panel 图形面板版）

这份教程假设你**几乎没碰过电脑、完全没接触过服务器**。别怕——你**不需要懂编程、也几乎不用敲命令**。我们全程借助一个免费的图形化管理面板 **1Panel**，绝大多数操作都是「在网页里点鼠标 + 复制粘贴一小段配置」。我会把每一步该做什么、做完会看到什么、出错了怎么办，都讲清楚。

整件事说白了就 6 步：**准备一台服务器 → 装好 1Panel 面板 → 在面板里开起 3 个程序（游戏服 + 机器人 + QQ 连接器）→ 装本插件 → 配置 → 在 QQ 群里用**。慢慢来，跟着做就行。

> 💡 **遇到任何一步卡住、或看到看不懂的红字报错**：把那几行字**原样复制**下来，发给懂行的朋友、或丢给 AI（如 ChatGPT）问「这是什么意思、怎么办」。报错信息本身就是答案的线索，不要慌。

---

## 🔰 为什么用 1Panel？（新手必读）

**1Panel** 是一款开源免费的 Linux 服务器**图形化管理面板**。对小白来说，它把原本要在黑乎乎的命令行里敲的活，全变成了网页上点点点。本教程选它，是因为它有这些实打实的好处：

- **几乎不用命令行**：装容器、改配置、看日志、重启、更新、备份，全在网页界面点鼠标完成。
- **自动装好 Docker**：安装 1Panel 时会**自动帮你装好 Docker 和 Docker Compose**，省去一堆环境配置。
- **可视化「容器 / 编排」管理**：我们的游戏服、机器人都用「编排（Compose）」一键拉起，启停/重启/更新都是按钮。
- **在线文件管理器 + 代码编辑器**：建配置文件（`.env`）、上传插件、找存档目录，像在电脑上用文件夹一样直观，还能直接在线编辑文本。
- **可视化放行端口**：自带防火墙面板，开端口点一下就行，不用记命令。
- **计划任务 / 监控 / 应用商店**：定时备份、资源监控、一键装常用软件都内置。

> 一句话：**1Panel = 服务器版的「控制面板」**。下面只有「安装 1Panel」这一步需要在终端敲一行命令，之后基本告别命令行。

### 关于「终端」那一行命令

安装 1Panel 时要在服务器的**终端**（黑色命令行窗口）里粘贴一行命令。连接服务器终端的方式：

- **云服务器**：厂商控制台一般有「远程连接 / Workbench / VNC」按钮，点开就是网页版终端，最省事。
- **Windows 电脑**：可下载免费的 **[MobaXterm](https://mobaxterm.mobatek.net/download.html)**，新建 SSH 会话填服务器 IP + 用户名 `root` + 密码即可。
- **Mac 电脑**：用自带「终端」App，输入 `ssh root@你的服务器IP` 回车，再输密码。

> ⚠️ 输密码时**屏幕不显示任何字符（连 `*` 都没有）是正常的**，打完直接回车。装好 1Panel 后，这个黑窗口基本就用不到了。

---

## 目录

- [第 0 章 · 你需要准备什么（硬件 + 系统）](#第-0-章你需要准备什么硬件--系统)
- [第 1 章 · 安装 1Panel 管理面板](#第-1-章安装-1panel-管理面板)
- [⭐ 第 1.5 章 · 一键脚本安装（推荐，最省事）](#-第-15-章一键脚本安装推荐最省事)
- 👇 下面第 2~8 章是**手动逐步版**（想弄懂每一步、或脚本某步失败时看）
- [第 2 章 · 在 1Panel 里放行端口](#第-2-章在-1panel-里放行端口)
- [第 3 章 · 创建共享网络](#第-3-章创建共享网络)
- [第 4 章 · 用「编排」部署幻兽帕鲁服务器](#第-4-章用编排部署幻兽帕鲁服务器)
- [第 5 章 · 用「编排」部署 AstrBot + NapCat](#第-5-章用编排部署-astrbot--napcat)
- [第 6 章 · 让 QQ 机器人上线](#第-6-章让-qq-机器人上线)
- [第 7 章 · 安装本插件](#第-7-章安装本插件)
- [第 8 章 · 配置插件](#第-8-章配置插件)
- [第 9 章 · 验证功能](#第-9-章验证功能)
- [第 10 章 · 日常运维（启动/重启/更新/备份/找存档，全图形化）](#第-10-章日常运维全在-1panel-图形界面)
- [第 11 章 · 服务器参数完整参考（全部可改参数 + 中文注释）](#第-11-章服务器参数完整参考)
- [第 12 章 · 常见问题](#第-12-章常见问题)
- [第 13 章 · 安全提醒](#第-13-章安全提醒)

---

<a id="第-0-章你需要准备什么硬件--系统"></a>
## 第 0 章 · 你需要准备什么（硬件 + 系统）

### 0.1 一台服务器

可以是**云服务器**（阿里云 / 腾讯云 / AWS / 各种 VPS）、家里的**小主机 / NAS**、或一台闲置电脑。要求：

- 有**公网 IP**（朋友才能从外网连进来玩）。云服务器自带公网 IP；家用宽带需要公网 IP + 端口转发，没有公网 IP 的可以用内网穿透（frp 等）。
- 能 7×24 小时开机（服务器关机=游戏服务器下线）。

### 0.2 推荐配置

幻兽帕鲁专用服务器比较吃**内存**和**CPU 单核性能**。下面按"同时在线人数"给推荐：

| 同时在线 | CPU | 内存 | 硬盘 | 说明 |
|---|---|---|---|---|
| 2~4 人（小圈子） | 2 核 | 8 GB | 30 GB SSD | 最低能跑 |
| 8~16 人 | 4 核 | 16 GB | 50 GB SSD | **推荐起步** |
| 32 人（满员公开服） | 8 核 | 32 GB | 80 GB SSD | 流畅满员 |

补充说明：

- **内存最重要**。帕鲁服务器随着世界变大、基地变多会越吃越多，内存不够会卡顿甚至崩档。宁可多给。
- **硬盘一定要用 SSD（固态）**。存档读写频繁，机械硬盘会拖慢自动存盘、加重卡顿。
- 上面的内存已经包含了机器人（AstrBot）、QQ 协议端（NapCat）和 1Panel 面板本身的开销，它们加起来约占 1.5~2 GB。
- **带宽**：每个在线玩家约占用 100~300 Kbps 上行，32 人公开服建议上行 ≥ 10 Mbps。

### 0.3 装什么系统

推荐 **Ubuntu Server 22.04 LTS**（或更新的 24.04 LTS）：

- 对新手最友好，1Panel 官方也优先支持。
- LTS = 长期支持，5 年内不用折腾升级。
- 1Panel 同样支持 Debian、CentOS、RockyLinux 等主流系统。

> 云服务器在购买/控制台界面直接选"Ubuntu Server 22.04 64 位"镜像即可，系统会装好。家用主机/NAS 自行安装 Ubuntu Server。

---

<a id="第-1-章安装-1panel-管理面板"></a>
## 第 1 章 · 安装 1Panel 管理面板

这是**唯一需要敲命令的一步**，装完之后就进入图形化操作了。

### 1.1 连上服务器终端

用上面〔关于「终端」那一行命令〕说的任意方式连上服务器（云控制台远程连接 / MobaXterm / Mac 终端），看到形如 `root@xxx:~#` 的提示符就说明连上了。

### 1.2 一键安装 1Panel

把下面这行**复制、粘贴进终端、按回车**（1Panel 官方 **V2 最新版** 安装脚本，会自动安装 Docker）：

```bash
curl -sSL https://resource.fit2cloud.com/1panel/package/v2/quick_start.sh -o quick_start.sh && bash quick_start.sh
```

安装过程中它会问你几个问题，按提示操作：

- **面板端口**：直接回车用随机端口（更安全），或自己设一个（如 `8090`）。**记下这个端口号**。
- **安全入口 / 面板访问目录**：随机一段字符串，相当于面板网址的"暗号"，**记下来**。
- **面板用户名 / 密码**：设一个你自己的管理员账号密码，**记牢**。

装完后，终端会打印一段**面板登录信息**，类似：

```
面板地址: http://你的服务器IP:端口/安全入口
用户名:   xxxx
密码:     xxxx
```

### 1.3 登录 1Panel

> ⚠️ 先确保**云厂商安全组放行了上一步的面板端口**（TCP），否则网页打不开。云服务器到控制台「安全组」加一条对应端口的放行规则；本机防火墙 1Panel 安装时一般已自动处理。

电脑浏览器打开上面那个**面板地址**，用刚设的用户名密码登录。看到 1Panel 的仪表盘（显示 CPU/内存/磁盘等），就装好了 🎉。

> 💡 之后所有操作基本都在这个网页面板里完成。建议把面板地址收藏起来。

---

<a id="-第-15-章一键脚本安装推荐最省事"></a>
## ⭐ 第 1.5 章 · 一键脚本安装（推荐，最省事）

装好 1Panel 后，**大部分人到这里用一键脚本就够了**——它会自动帮你装好「幻兽帕鲁服务器 + AstrBot + NapCat + 本插件」，还会自动补上各种必需配置（比如状态卡显示 CPU/内存要用的 `docker.sock` 挂载）。

> 🆚 **两种安装方式，二选一**：
> - **想省事** → 用本章一键脚本，跑完直接跳到 [第 6 章](#第-6-章让-qq-机器人上线) 扫码登录 QQ 即可。
> - **想弄懂每一步 / 脚本某步失败** → 跳过本章，从 [第 2 章](#第-2-章在-1panel-里放行端口) 开始手动逐步来。

### 1.5.1 打开 1Panel 的终端

1Panel 左侧菜单 **主机 → 终端**（或 **网站 → 终端**，不同版本位置略有差异），会打开一个网页版的命令行窗口——就是在这里粘命令。

### 1.5.2 先「试运行」看看（不改动任何东西，强烈建议先跑这个）

把下面这行**整行复制**，粘进终端按回车。它是**演练模式**，只检测环境、打印"将要做什么"，**不会真安装、不会改任何文件**：

```bash
curl -fsSL https://raw.githubusercontent.com/dalimao113/astrbot_plugin_palworld/main/install.sh | bash -s -- --dry-run
```

看它把 8 个阶段都跑一遍、没有报红色错误，就说明环境 OK，可以正式装了。

### 1.5.3 正式一键安装

去掉 `--dry-run` 再跑一次，这次会真正安装：

```bash
curl -fsSL https://raw.githubusercontent.com/dalimao113/astrbot_plugin_palworld/main/install.sh | bash
```

过程中它会：
- 检测并安装系统依赖、Docker、`yq` 等工具；
- **已经装过帕鲁服 / AstrBot / NapCat 的**：不会重装，只体检配置，**缺什么补什么**（每次改配置前都会**备份原文件 + 显示改动对比 + 停下来问你 y/N**，不会破坏你已有的自定义配置）；
- **没装过的**：用内置模板帮你创建好；
- 中途会**让你输入**：帕鲁服管理密码（`ADMIN_PASSWORD`，留空会自动生成并显示）、你的管理员 QQ 号；
- 最后把插件装好、配置预填好。

> ✅ 脚本跑完后，**接着做 [第 6 章](#第-6-章让-qq-机器人上线) 的 3 步**（NapCat 扫码登录 QQ、接上反向 WebSocket、确认 admin_qq），然后在群里发 `/帕鲁自检` 验收即可。
>
> ⚠️ 脚本可**重复跑**（幂等），跑坏了再跑一次也安全；每次改配置都有备份（`xxx.bak.时间戳`）。

---

<a id="第-2-章在-1panel-里放行端口"></a>
## 第 2 章 · 在 1Panel 里放行端口

游戏和机器人需要这些端口能被访问。**先在云厂商安全组放行，再在 1Panel 防火墙放行**（两层都要）。

| 端口 | 协议 | 用途 | 是否对公网开放 |
|---|---|---|---|
| 8211 | UDP | 游戏端口（玩家连这个进服） | ✅ 必须开放 |
| 27015 | UDP | 社区列表查询端口 | ✅ 公开服必须开放 |
| 6185 | TCP | AstrBot 管理网页后台 | ⚠️ 建议只对自己 IP 开放 |
| 6099 | TCP | NapCat 扫码登录网页 | ⚠️ 临时用，配置完可关 |
| 8212 | TCP | 帕鲁 REST API | ❌ **绝不要对公网开放**（仅容器内部用，编排里已只绑本机）|

**在 1Panel 里放行**：左侧菜单 **主机 → 防火墙 → 端口规则 → 创建规则**，分别添加 `8211/udp`、`27015/udp`、`6185/tcp`（6099 临时用可暂放）。

**云服务器**还要去厂商控制台的「安全组 / 防火墙」加同样的放行规则——这一层最容易漏，打不开网页/进不去服多半是它没放行。

---

<a id="第-3-章创建共享网络"></a>
## 第 3 章 · 创建共享网络

帕鲁服务器和机器人要在**同一个 Docker 网络**里，机器人才能用「容器名」直接访问帕鲁服务器。在 1Panel 里建这个网络：

左侧 **容器 → 网络 → 创建网络**：

- **名称**填 `astrbot_default`
- 其余保持默认，点确认。

> 也可以在终端执行 `docker network create astrbot_default`，效果一样。后面两个编排都会接到这个网络。

---

<a id="第-4-章用编排部署幻兽帕鲁服务器"></a>
## 第 4 章 · 用「编排」部署幻兽帕鲁服务器

用社区维护的镜像 [`thijsvanloef/palworld-server-docker`](https://github.com/thijsvanloef/palworld-server-docker)。在 1Panel 里，部署一组容器叫「**编排（Compose）**」。

### 4.1 新建编排

左侧 **容器 → 编排 → 创建编排**：

- **名称**填 `palworld`（这会决定文件存放目录 `/opt/1panel/docker/compose/palworld/`）。
- **来源**选「编辑 compose 文件」/「手动输入」。
- 在编辑框里**粘贴下面这段** compose 内容：

```yaml
services:
  palworld:
    image: thijsvanloef/palworld-server-docker:latest
    restart: unless-stopped
    container_name: palworld-server
    stop_grace_period: 30s        # 关服前留 30 秒存盘，防丢档
    env_file:
      - ./.env                    # 全部服务器参数从 .env 读（见第 11 章）
    ports:
      - "8211:8211/udp"           # 游戏端口，必须放行
      - "27015:27015/udp"         # 查询端口，公开服必须放行，否则社区列表搜不到
      - "127.0.0.1:8212:8212/tcp" # REST API：只绑本机 127.0.0.1，绝不对外
    volumes:
      - ./palworld:/palworld/     # 存档目录挂到本地 ./palworld
    networks:
      - default

# 接到第 3 章建的共享网络，机器人才能用容器名 palworld-server:8212 访问
networks:
  default:
    name: astrbot_default
    external: true
```

> 注意 `127.0.0.1:8212:8212` 这种写法：它让 REST API 端口**只绑在本机回环**，外网完全访问不到，安全。**先别急着点确认启动**，下一步要先把 `.env` 参数文件建好（compose 里 `env_file` 指向它），否则会因为找不到 `.env` 报错。

部分 1Panel 版本会让你**先保存编排**再去放文件；如果它坚持要先启动，可先把 `env_file` 那两行临时删掉保存，建好 `.env` 后再加回来。

<a id="42-用文件管理器建参数文件-env"></a>
### 4.2 用文件管理器建参数文件 .env

帕鲁服务器**所有能调的参数**（经验倍率、捕获率、PVP、备份…）都集中在一个叫 `.env` 的文件里，要放在编排目录 `/opt/1panel/docker/compose/palworld/` 下。

1. 左侧 **主机 → 文件**（文件管理器），地址栏进入 `/opt/1panel/docker/compose/palworld/`。
2. 点 **创建文件**，文件名填 `.env`，确认。
3. 在文件列表里**右键 `.env` → 编辑**（或点编辑图标），打开在线编辑器。
4. 把 **[第 11 章 · 服务器参数完整参考](#第-11-章服务器参数完整参考)** 里那一整段参数内容**全部复制粘贴**进去，**保存**。

**建好后，至少要改这 2 行**（其余先用默认，以后想调再说）：

```ini
# 管理密码：机器人靠它管理服务器，必须改成你自己的、别人猜不到的强密码（字母+数字，10 位以上）
ADMIN_PASSWORD=改成你自己的强密码
# 服务器名（显示在游戏社区列表里，随便起）
SERVER_NAME=我的帕鲁服务器
```

> ⚠️ **千万注意**：`.env` 里**值和注释不能写在同一行**。比如密码要写成两行——上一行是 `# 注释`，下一行才是 `ADMIN_PASSWORD=xxxx`。否则注释会被当成密码的一部分，导致进不去服。在线编辑器里改完记得点**保存**。

<a id="43-启动并验证"></a>
### 4.3 启动并验证

回到 **容器 → 编排 → palworld**，点 **启动**（或重新部署）。首次启动会下载游戏文件（约几 GB，耐心等几分钟）。

- **看日志**：编排或容器列表里找到 `palworld-server`，点 **日志**。看到类似 `Running Palworld dedicated server` 且不再刷错误，就启动好了。
- **验证 REST API**：左侧 **容器 → 容器**，找到 `palworld-server` → 点 **终端**，在弹出的容器终端里执行（把密码换成你 `.env` 里的 `ADMIN_PASSWORD`）：

  ```bash
  curl -s -u admin:你的ADMIN_PASSWORD http://127.0.0.1:8212/v1/api/info
  ```

  能返回一段带服务器名、版本的 JSON，就说明帕鲁服务器 + REST API 都正常了。

### 4.4 记下世界存档 GUID（存档查询功能要用）

还是在 `palworld-server` 的**容器终端**里执行：

```bash
ls /palworld/Pal/Saved/SaveGames/0/
```

会输出一串大写十六进制目录名，例如 `D0623B70BAE54CB68C68DF8AD8857729`。把它记下来，你的世界存档完整路径就是：

```
/palworld/Pal/Saved/SaveGames/0/<上面那串GUID>
```

第 8 章配置插件时，`save_dir_in_container` **留空即可自动探测**这个 GUID 目录，一般不用手填；只有多世界/特殊布局才需要把它填进去（记下来备用）。

> 也可以用 1Panel 文件管理器进入 `/opt/1panel/docker/compose/palworld/palworld/Pal/Saved/SaveGames/0/`，直接看到那个 GUID 文件夹名。

---

<a id="第-5-章用编排部署-astrbot--napcat"></a>
## 第 5 章 · 用「编排」部署 AstrBot + NapCat

AstrBot 是机器人核心（跑本插件），NapCat 是连接 QQ 的协议端。两个一起编排。

左侧 **容器 → 编排 → 创建编排**：

- **名称**填 `astrbot`（目录将是 `/opt/1panel/docker/compose/astrbot/`）。
- 粘贴下面这段 compose 内容，保存并启动：

```yaml
services:
  # ========== 1. NapCat：QQ 协议端 ==========
  napcat:
    image: mlikiowa/napcat-docker:latest
    container_name: napcat
    restart: always
    environment:
      - ACCOUNT=                 # 留空，启动后去网页扫码登录
      - WS_ENABLE=true
      - HTTP_ENABLE=true
      - WEB_UI_ENABLE=true
      - WEB_UI_PORT=6099
      - TZ=Asia/Shanghai
    ports:
      - "6099:6099"              # 扫码登录网页
      - "3001:3001"
      - "6001:6001"
    volumes:
      - ./napcat/config:/app/napcat/config
      - ./napcat/qq:/app/.config/QQ
      - ./astrbot/data:/AstrBot/data
    networks:
      - default

  # ========== 2. AstrBot：机器人核心 + 本插件 ==========
  astrbot:
    image: soulter/astrbot:latest
    container_name: astrbot
    restart: always
    # 启动时自动装插件的存档解析依赖(palworld-save-tools==0.24.0)，再启动 AstrBot。
    # 容器重建/更新后这个 pip 包会丢失，放这里保证每次启动自愈，否则 /帕鲁队伍
    # 等存档类指令会报「读不到存档」。必须锁 0.24.0：解析器针对该版本适配，更新版会解析失败。
    command: ["sh","-c","pip install --no-cache-dir palworld-save-tools==0.24.0 -i https://pypi.tuna.tsinghua.edu.cn/simple || true; exec python main.py"]
    depends_on:
      - napcat
    environment:
      - NAPCAT_HOST=napcat
      - NAPCAT_PORT=3001
      - TZ=Asia/Shanghai
    ports:
      - "6185:6185"              # 管理网页后台
    volumes:
      - ./astrbot/data:/AstrBot/data
      # ★ 只读挂载 docker socket：本插件靠它读帕鲁容器存档 + 状态卡的 CPU/内存监控。
      #   不挂这一行，状态卡就不显示服务器负载、存档类指令也用不了。:ro=只读更安全。
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - default

networks:
  default:
    name: astrbot_default        # 和帕鲁服务器同一个网络
    external: true
```

> **为什么要挂 docker.sock**：本插件用它从帕鲁容器里拉存档（`/帕鲁我`、背包、队伍、帕鲁箱、据点、公会等功能）和读容器 CPU/内存。不挂也能用基础功能，但这些会自动关闭。`:ro` 表示只读，降低风险。
>
> 启动后，机器人相关文件就在 `/opt/1panel/docker/compose/astrbot/` 下：插件目录是 `astrbot/data/plugins/`（第 7 章把插件放这里；存档解析依赖 `palwork/` 已随插件自带，无需单独处理）。

### （可选）加本地 t2i 渲染服务（加速出图）

本插件所有回复都渲染成图片。AstrBot 自带渲染默认走**官方公共 t2i 端点**，偶发偏慢/502。想出图更快更稳，在上面 astrbot 编排的 `services:` 下**再加一个本地渲染服务**（一键脚本装的就是它）：

```yaml
  # t2i：文/HTML 转图片渲染服务，插件卡片出图走它（与 astrbot 同网络，用容器名访问）
  t2i:
    image: soulter/astrbot-t2i-service:latest
    container_name: astrbot-t2i
    restart: always
    ports:
      - "8999:8999"
    networks:
      - default
```

保存并「重新部署」astrbot 编排后，去 AstrBot 后台（6185）**配置 → 其它 → 文转图**，把 **策略(`t2i_strategy`)** 设为 `remote`、**端点(`t2i_endpoint`)** 设为 `http://astrbot-t2i:8999`，保存后重启 AstrBot 生效。（用一键脚本安装的已自动配好，无需手动设。）

---

<a id="第-6-章让-qq-机器人上线"></a>
## 第 6 章 · 让 QQ 机器人上线

### 6.1 登录 NapCat WebUI（先拿 token → 再扫码登录 QQ）

浏览器打开 `http://你的服务器IP:6099`（NapCat 网页），它会先要你输入 **token（WebUI 登录密钥）**。

**怎么找 token —— 三种方式任选其一：**

1. **① 1Panel 文件管理器（最直观，推荐）**：1Panel 左侧 **主机 → 文件**（或 **容器 → 编排 → astrbot → 目录**），进入编排目录
   `/opt/1panel/docker/compose/astrbot/napcat/config/`，找到并打开 **`webui.json`**，里面这一行引号内的就是登录密钥：
   ```json
   "token": "xxxxxxxxxxxx",
   ```
2. **② 看容器日志**：1Panel **容器 → 容器 → napcat → 日志**，找带 `WebUi`、`token=` 或 `panel` 字样的那行，里面带着 token。
3. **③ 容器终端**：1Panel **容器 → napcat → 终端**，执行 `cat /app/napcat/config/webui.json`，看 `token` 字段。

> ⚠️ **token 就是你 NapCat 后台的密码**（一串随机字符，例如 `a1b2c3d4e5f6` 这种），**别外泄**。想改：直接编辑 `webui.json` 的 `token` 值 → 保存 → 重启 napcat 容器即可。

**拿到 token 登录后 → 扫码登录机器人 QQ：**
进入 NapCat WebUI，在「**登录 / 扫码登录**」页，用**手机 QQ 扫屏幕上的二维码**，登录你要当机器人的那个 QQ 号（**强烈建议用小号**，主号有被风控风险）。页面显示「已登录 / 在线」即成功。之后 6099 网页平时用不到，可在防火墙里把 6099 关掉更安全。

### 6.2 确认 NapCat ↔ AstrBot 已互通（反向 WebSocket）

本教程编排里，NapCat 和 AstrBot 通过**反向 WebSocket** 连接：**NapCat 主动连 AstrBot**（地址 `ws://astrbot:6199/ws`），AstrBot 用 `aiocqhttp` 适配器在 **6199** 端口接收。

> ⚠️ **这一步需要你手动配一次**：一键脚本只负责部署容器 + 配好出图(t2i)，**不会**自动配 NapCat↔AstrBot 的连接。按下面 **A、B 两端各配一次**即可，配好后长期生效。

**A、B 两端都要配：**

**A. AstrBot 端**（后台 `http://IP:6185` → 首次设管理员账号密码 → 左侧「平台适配器 / 消息平台」）
1. **添加** → 选 **`aiocqhttp`（OneBot v11）**。
2. 关键参数（用**反向 WS**）：
   - 连接模式：**反向 WebSocket**
   - 监听地址 `ws_reverse_host`：`0.0.0.0`
   - 监听端口 `ws_reverse_port`：`6199`
   - 校验 `ws_reverse_token`：**留空**（若要填，A/B 两端必须一致）
3. 保存并**启用**。

**B. NapCat 端**（WebUI `http://IP:6099` → 左侧「网络配置 / 网络设置」）
1. **新建** → 选 **WebSocket 客户端（websocketClient）**。
2. 关键参数：
   - 名称：`astrbot`（随意）
   - URL：`ws://astrbot:6199/ws` —— **用容器名 `astrbot`**（两容器同一 docker 网络时）；若不同网络，改成 AstrBot 宿主机 `IP:6199`
   - 消息格式 `messagePostFormat`：`array`
   - Token：**留空**（与 A 端一致）
3. 启用 / 保存。

**确认已连通：**
- NapCat WebUI 网络配置里，那条 `astrbot` 客户端显示 **已连接 / 绿色**；
- AstrBot 后台「平台适配器」显示适配器 **在线**（或 astrbot 容器日志有 aiocqhttp 连接成功）；
- 到 QQ 群 @机器人 或发条消息，有反应即通。

> **端口速记**：`6099`=NapCat 登录网页、`6199`=AstrBot 接收 NapCat 反向 WS、`6185`=AstrBot 后台。（编排里映射的 `3001` 是 NapCat 的正向 WS 端口，本方案用反向 WS，一般用不到。）

---

<a id="第-7-章安装本插件"></a>
## 第 7 章 · 安装本插件

把插件代码放进 AstrBot 的插件目录：`/opt/1panel/docker/compose/astrbot/astrbot/data/plugins/`。

### 7.1 放插件代码

本仓库**已公开**，匿名即可下载，无需 GitHub 令牌。下面任选一种：

**方式 A · 在 1Panel 文件管理器里上传（最直观，推荐新手）**

1. 电脑浏览器登录 GitHub，进本仓库 → 绿色 **Code** 按钮 → **Download ZIP**，下载到电脑并解压，得到 `astrbot_plugin_palworld` 文件夹。
2. 1Panel 左侧 **主机 → 文件**，进入 `/opt/1panel/docker/compose/astrbot/astrbot/data/plugins/`。
3. 点 **上传**，把整个 `astrbot_plugin_palworld` 文件夹（或它的 zip）传上去；传 zip 的话上传后**右键 → 解压**到当前目录。

**方式 B · 用 Git 下载（仓库已公开，无需令牌）**

在 1Panel 打开 `astrbot` 容器的**终端**（或宿主机终端），执行：

   ```bash
   cd /opt/1panel/docker/compose/astrbot/astrbot/data/plugins
   git clone https://github.com/dalimao113/astrbot_plugin_palworld.git
   ```

**方式 C · AstrBot 插件市场从 URL 安装（最省事）**

AstrBot WebUI「插件管理 → 安装插件 → 从 URL/仓库地址」填 `https://github.com/dalimao113/astrbot_plugin_palworld` 直接装。

> ✅ **成功标志**：文件管理器里 `.../plugins/astrbot_plugin_palworld/` 下能看到 `main.py` 等文件。

### 7.2 存档解析依赖 palwork（已随插件自带，无需操作）

存档解析用的 `palwork/`（`palsave.py` + `liboo2core.so`）**已随插件一起装、按相对路径加载**，装到哪跑到哪，**不用再移动或改路径**（旧版本要求剪切到 `data/palwork/`，现已自包含）。

### 7.3 装运行依赖

存档解析依赖 Python 包 `palworld-save-tools==0.24.0`。本编排的 astrbot 服务**启动命令里已自动安装**（容器每次启动自愈，重建也不怕），一般**无需手动装**。若 `/帕鲁自检` 提示该项缺失，再在 1Panel **容器 → astrbot → 终端** 执行（**必须锁 0.24.0**，解析器针对该版本适配，更新版会解析失败）：

```bash
pip install palworld-save-tools==0.24.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> 🖼️ **出图渲染**：AstrBot 自带渲染默认走**官方公共 t2i 端点**（偶发偏慢/502）。想快而稳，可另起一个本地渲染服务 `astrbot-t2i`（一键脚本会自动装好并配置；手动部署见第 5 章末尾「(可选) 加本地 t2i 渲染服务」）。

---

<a id="第-8-章配置插件"></a>
## 第 8 章 · 配置插件

> 💡 用了 [第 1.5 章一键脚本](#-第-15-章一键脚本安装推荐最省事) 的话，这几项脚本已帮你预填好，本章可只做核对。

AstrBot 后台（6185）→「插件管理」→ 找到 `astrbot_plugin_palworld` →「插件配置」。**真正必填只有两项**：

| 配置项 | 填什么 | 必填？ |
|---|---|---|
| `admin_password` | 第 4 章设的 `ADMIN_PASSWORD`（帕鲁服管理密码）| ✅ 必填 |
| `admin_qq` | 你的 QQ 号（管理员，可填多个）| ✅ 必填 |
| `api_base` | 默认 `http://palworld-server:8212`（用**容器名**不是 IP）；容器名没改就不用动 | 默认即可 |
| `docker_container` | 帕鲁容器名；**留空/填错会自动探测** | 一般不用填 |
| `save_dir_in_container` | 世界存档目录；**留空自动探测**（第 4.4 步记的 GUID 现在也不用手填了）| 一般不用填 |

其余保持默认即可。保存后回「插件管理」点**重载插件**。

> 出图走 AstrBot 渲染（`local_render` 默认关，自带中文字体）。想快而稳建议用一键脚本部署的本地 t2i 服务 `astrbot-t2i`（AstrBot 默认公共端点偶发偏慢/502）。
> 配完发 `/帕鲁自检`（管理员）体检一下最稳。

---

<a id="第-9-章验证功能"></a>
## 第 9 章 · 验证功能

在机器人所在的 QQ 群里发：

| 发什么 | 期望 |
|---|---|
| `/帕鲁自检` ⭐（管理员） | **一键体检卡**：docker.sock / 帕鲁容器 / REST 密码 / 存档目录 / 存档解析库 / 渲染 / 管理员白名单，逐项 ✅⚠️❌ + 修复指引。**配完先发这条，哪里没弄好一目了然** |
| `/帕鲁状态` | 出服务器状态卡（在线人数 / FPS / 负载…）|
| `/帕鲁图鉴 棉悠悠` | 出帕鲁图鉴卡（不依赖存档 / REST）|
| `/帕鲁竞技场` | 出竞技场段位/对手卡（纯数据，不依赖存档）|
| `/帕鲁绑定 <你的游戏角色名>` | 绑定成功卡（建议你在线时绑）|
| `/帕鲁我` | 出个人档案卡（含存档真实数据）→ 说明 docker.sock + palwork + save_dir 都对了 |
| `/帕鲁队伍`、`/帕鲁箱`、`/帕鲁据点`、`/帕鲁公会` | 出对应存档卡 |

> 💡 出图走 AstrBot 的 t2i 渲染，自带中文字体、无需装浏览器。AstrBot 默认公共端点偶发偏慢/502，一键脚本已部署本地 `astrbot-t2i` 服务规避。
> 存档类指令首次可能稍慢（要拉取+解析存档），之后有缓存会快。

---

<a id="第-10-章日常运维全在-1panel-图形界面"></a>
## 第 10 章 · 日常运维（全在 1Panel 图形界面）

有了 1Panel，启停/重启/更新/看日志全是**点按钮**，不用记命令。

### 10.1 容器与编排（容器 → 编排 / 容器）

进入 1Panel **容器 → 编排**，对 `palworld` 或 `astrbot` 编排，右侧操作菜单即可：

| 想做的事 | 在 1Panel 怎么点 |
|---|---|
| **启动 / 停止 / 重启** | 编排或容器行的「启动 / 停止 / 重启」按钮 |
| **改了编排内容后重建** | 编排 →「编辑」改完 →「重新部署 / 重建」 |
| **改了 `.env` 后生效** | 编排 →「重新部署」（光重启不会重新读 `.env`）|
| **更新游戏 / 机器人版本** | 容器 →「镜像」拉取最新 → 编排「重新部署」；或编排里直接「更新」|
| **看实时日志** | 容器 → 对应容器 →「日志」|
| **进容器内部** | 容器 → 对应容器 →「终端」|

> 本教程的 `.env` 默认开了 `UPDATE_ON_BOOT=true` 和 `AUTO_UPDATE_ENABLED=true`，**帕鲁游戏会自动更新**，一般不用手动拉。

### 10.2 改服务器参数（玩法手感）

文件管理器进入 `/opt/1panel/docker/compose/palworld/`，**编辑 `.env`**，改完保存，再到 **容器 → 编排 → palworld →「重新部署」**。常用调参见第 11 章「[常用调参速查](#常用调参速查)」。

### 10.3 备份 / 找存档

- **存档位置**：文件管理器 `/opt/1panel/docker/compose/palworld/palworld/Pal/Saved/SaveGames/0/<GUID>/`。
- **自动备份**：`.env` 默认每天凌晨 3 点自动备份（见第 11 章 `BACKUP_*`），文件在 `.../palworld/backups/`。
- **手动 / 定时备份（1Panel 计划任务）**：左侧 **计划任务 → 创建任务**，类型选「备份 / 目录」，把 `/opt/1panel/docker/compose/palworld/palworld/` 设为备份源，设定周期即可。1Panel 还能把备份直接传到对象存储（OSS/COS 等）。

### 10.4 更新（插件 / 镜像 / 游戏）

按你想更新的范围，选一种：

#### A. 只更新插件（最常见、最省事）
AstrBot 后台「插件管理 → 更新」按钮；或在插件目录 `git pull` 后点**重载插件**。**不用重启容器**。

#### B. 一条命令全更新（插件 + AstrBot / NapCat / t2i / 帕鲁镜像）
在 1Panel「**主机 → 终端**」(root) 里，重跑一键脚本、**加 `--update`**：

```bash
curl -fsSL https://raw.githubusercontent.com/dalimao113/astrbot_plugin_palworld/main/install.sh | bash -s -- --update
```

> ⚠️ 中间的 **`-s --` 不能省**——`curl | bash` 时要靠它才能把 `--update` 传进脚本；少了它 `--update` 会被丢掉、退化成普通重跑（不升级镜像）。

它会做三件事：`git pull` 更新插件 → `docker compose pull` 拉各最新镜像 → **用新镜像重建容器**。全程**不改你的配置、不重新问密码/QQ、不动存档**。

想**先看会做什么但不动手**，末尾再加 `--dry-run` 演练一遍（只打印计划、不执行）：

```bash
curl -fsSL https://raw.githubusercontent.com/dalimao113/astrbot_plugin_palworld/main/install.sh | bash -s -- --update --dry-run
```

> 跑完后，**插件代码更新要到「插件管理 → 重载插件」再点一下才生效**（镜像更新随重建已生效）。
> 首次说明：`--update` 是较新版本才加入的功能；若你现在的插件还没有它，先用上面 **A** 方式把插件更新一次即可获得，之后 `--update` 就一直能用。

#### C. 游戏本体
`.env` 里 `UPDATE_ON_BOOT=true` / `AUTO_UPDATE_ENABLED=true` 时，帕鲁容器重启就自动更到最新游戏版本，一般无需手动；也可在 1Panel「编排 → palworld → 重新部署」触发。

> ⚠️ **普通重跑脚本（不带 `--update`）只体检配置 + 更新插件，不会自动升级镜像**——这是有意为之，避免 AstrBot 跨大版本意外破坏环境。想升级镜像时才显式用 `--update`。

---

<a id="第-11-章服务器参数完整参考"></a>
## 第 11 章 · 服务器参数完整参考

下面是帕鲁服务器 `.env` 的**完整内容**，包含**所有可修改的参数**，每一项上面都有一行中文注释。

> 🤖 **用了一键脚本的，这份 `.env` 会自动帮你生成好，通常不用手动粘贴：**
> - **全新安装**（机器上还没有 `/opt/palworld`）→ 脚本会**自动写出下面这份完整参数 `.env`**（含逐行注释），并把你安装时引导输入的**服务器名、最大人数、管理员密码**填进对应位置。装完直接在 `/opt/palworld/.env` 改任意参数、再「重新部署」即可。
> - **手动部署**（本教程第 4 章那条路）→ 才需要按 [第 4.2 步](#42-用文件管理器建参数文件-env) 把下面这整段**复制粘贴**进 `.env`。
> - **已有旧 `.env`（重跑脚本 / 老机器）→ 脚本不会覆盖你的 `.env`**（怕冲掉你调好的参数），只会补几个关键缺失键（REST API、管理密码、离线存档保留 `EXIST_PLAYER_AFTER_LOGOUT`）。
>   **想让老机器也换成这份完整参数版**：删掉旧的 compose 和 `.env`（**保留游戏目录 `/opt/palworld/palworld`，存档在里面别删**），再重跑一键脚本走"全新生成"即可：
>   ```bash
>   rm -f /opt/palworld/compose.yaml /opt/palworld/.env
>   curl -fsSL https://raw.githubusercontent.com/dalimao113/astrbot_plugin_palworld/main/install.sh | bash
>   ```

**重要规则：**

1. **注释必须单独成行**（`#` 开头），**绝对不能和参数写在同一行**。例如写成 `SERVER_PASSWORD=  # 密码` 会把 `# 密码` 当成密码的一部分，导致进不去服！
2. 改完任何参数，必须到 **1Panel 容器 → 编排 → palworld → 重新部署** 才生效（光「重启」不会重新读 `.env`）。
3. 标 `★` 的是**玩法倍率类**，决定服务器手感（经验/掉落/伤害等）。**下面给的全部是 Palworld 官方默认值**（原汁原味的普通体验），照抄即可；想调成"轻肝休闲"之类的手感，参考文末「[常用调参速查](#常用调参速查)」自行改。
   > ⚠️ 例外：`EXIST_PLAYER_AFTER_LOGOUT` 官方默认是 `False`，本教程改成了 `True`——这样玩家离线后角色/帕鲁/背包仍保留在存档里，机器人的 `/帕鲁我`、`/帕鲁队伍`、`/帕鲁箱`、`/帕鲁据点` 等离线查档功能才能用。不需要这些功能可改回 `False`。

**怎么用**：按 [第 4.2 步](#42-用文件管理器建参数文件-env) 在 1Panel 文件管理器里新建 `/opt/1panel/docker/compose/palworld/.env`，把下面这整段内容**复制粘贴进在线编辑器并保存**，再改掉 `ADMIN_PASSWORD` 和 `SERVER_NAME` 两行：

```ini
# Palworld 服务器配置 (.env) — 每项单独一行中文注释，改值后重新部署生效
# ⚠️ 注释必须单独成行，不能和值写同一行

# ════════ 容器 / 基础 ════════
# 时区
TZ=Asia/Shanghai
# 容器运行用户ID
PUID=1000
# 容器运行用户组ID
PGID=1000
# 游戏端口(UDP)
PORT=8211
# 查询端口(社区列表用UDP)
QUERY_PORT=27015
# 公开服拉满，官方上限就是 32
PLAYERS=32
# 多线程(提升性能)
MULTITHREADING=true

# ════════ 服务器信息 ════════
# 服务器名(显示在社区列表)
SERVER_NAME=我的帕鲁服务器
# 服务器简介
SERVER_DESCRIPTION=欢迎来玩~

# ════════ 公开 / 密码 / 网络 ════════
# 显示在游戏内"社区服务器"列表
COMMUNITY=true
# 留空=完全开放，任何人直接进。注意：值和注释不能写在同一行，否则注释会被当成密码
SERVER_PASSWORD=
# 管理用，必须设且改掉，别留默认
ADMIN_PASSWORD=改成你自己的强密码
# REST API / 玩家列表 / 认证
# 是否启用REST API(机器人管理需要)
REST_API_ENABLED=true
# REST API端口(只绑本机)
REST_API_PORT=8212
# 是否公开在线玩家列表
SHOW_PLAYER_LIST=true
# 是否记录玩家进出日志
ENABLE_PLAYER_LOGGING=true
# 是否启用账号认证
USEAUTH=true

# ════════ 跨平台 ════════
# 允许的跨平台(Steam/Xbox/PS5/Mac)
CROSSPLAY_PLATFORMS=(Steam,Xbox,PS5,Mac)

# ════════ 自动更新 ════════
# 开机时检查并更新游戏
UPDATE_ON_BOOT=true
# 公开服建议开，跟上客户端版本
AUTO_UPDATE_ENABLED=true
# 每天凌晨 5 点检查更新
AUTO_UPDATE_CRON_EXPRESSION=0 5 * * *
# 更新前提前几分钟通知
AUTO_UPDATE_WARN_MINUTES=30

# ════════ 自动重启 ════════
# 是否定时自动重启
AUTO_REBOOT_ENABLED=true
# 有人在线时不强制重启
AUTO_REBOOT_EVEN_IF_PLAYERS_ONLINE=false
# 重启前提前几分钟通知
AUTO_REBOOT_WARN_MINUTES=5
# 自动重启时间(cron表达式)
AUTO_REBOOT_CRON_EXPRESSION=0 5 * * *

# ════════ 备份 / 存档 ════════
# 是否自动备份存档
BACKUP_ENABLED=true
# 备份时间(cron表达式)
BACKUP_CRON_EXPRESSION=0 3 * * *
# 是否删除旧备份
DELETE_OLD_BACKUPS=true
# 备份保留天数
OLD_BACKUP_DAYS=30
# 自动存盘间隔(分钟)
AUTO_SAVE_SPAN=30.000000
# 玩家离线后角色/帕鲁/背包保留在存档，机器人才能离线查档案
EXIST_PLAYER_AFTER_LOGOUT=True

# ════════ ★ 经验 / 捕获 / 帕鲁数量 ════════
# 经验获取倍率(越大升级越快)
EXP_RATE=1.000000
# 帕鲁捕获成功率倍率
PAL_CAPTURE_RATE=1.000000
# 野生帕鲁刷新数量倍率
PAL_SPAWN_NUM_RATE=1.000000

# ════════ ★ 伤害倍率 ════════
# 帕鲁造成伤害倍率
PAL_DAMAGE_RATE_ATTACK=1.000000
# 帕鲁受到伤害倍率(越大越脆)
PAL_DAMAGE_RATE_DEFENSE=1.000000
# 玩家造成伤害倍率
PLAYER_DAMAGE_RATE_ATTACK=1.000000
# 玩家受到伤害倍率(越大越脆)
PLAYER_DAMAGE_RATE_DEFENSE=1.000000

# ════════ ★ 生命自动回复 ════════
# 玩家生命自动回复倍率
PLAYER_AUTO_HP_REGEN_RATE=1.000000
# 玩家睡觉时生命回复倍率
PLAYER_AUTO_HP_REGEN_RATE_IN_SLEEP=1.000000
# 帕鲁生命自动回复倍率
PAL_AUTO_HP_REGEN_RATE=1.000000
# 帕鲁在帕鲁箱中生命回复倍率
PAL_AUTO_HP_REGEN_RATE_IN_SLEEP=1.000000

# ════════ ★ 消耗 / 负重 / 耐久 ════════
# 玩家饱食度下降速度(越小越耐饿)
PLAYER_STOMACH_DECREASE_RATE=1.000000
# 玩家耐力下降速度
PLAYER_STAMINA_DECREASE_RATE=1.000000
# 帕鲁饱食度下降速度
PAL_STOMACH_DECREASE_RATE=1.000000
# 帕鲁耐力下降速度
PAL_STAMINA_DECREASE_RATE=1.000000
# 物品重量倍率(越小越能背)
ITEM_WEIGHT_RATE=1.000000
# 装备耐久损耗倍率
EQUIPMENT_DURABILITY_DAMAGE_RATE=1.000000

# ════════ ★ 时间 / 速度 / 孵蛋 ════════
# 白天时间流速倍率
DAYTIME_SPEEDRATE=1.000000
# 夜晚时间流速倍率
NIGHTTIME_SPEEDRATE=1.000000
# 帕鲁工作&建造速度倍率
WORK_SPEED_RATE=1.000000
# 帕鲁蛋孵化时间(小时, 越小越快, 想秒孵设0)
PAL_EGG_DEFAULT_HATCHING_TIME=72.000000

# ════════ ★ 掉落 ════════
# 采集物(树/矿等)掉落数量倍率
COLLECTION_DROP_RATE=1.000000
# 击杀敌人掉落数量倍率
ENEMY_DROP_ITEM_RATE=1.000000
# 地面掉落物数量上限
DROP_ITEM_MAX_NUM=3000
# 掉落物存在小时数
DROP_ITEM_ALIVE_MAX_HOURS=1.000000
# 地面便便数量上限
DROP_ITEM_MAX_NUM_UNKO=100

# ════════ ★ 采集物 ════════
# 采集物耐久倍率(越小越好砍)
COLLECTION_OBJECT_HP_RATE=1.000000
# 采集物再生速度倍率
COLLECTION_OBJECT_RESPAWN_SPEED_RATE=1.000000

# ════════ ★ 建筑 / 基地 ════════
# 建筑耐久倍率
BUILD_OBJECT_HP_RATE=1.000000
# 建筑受攻击伤害倍率
BUILD_OBJECT_DAMAGE_RATE=1.000000
# 建筑自然劣化速度(0=不劣化, 不用喂材料)
BUILD_OBJECT_DETERIORATION_DAMAGE_RATE=1.000000
# 全服基地数量上限
BASE_CAMP_MAX_NUM=128
# 单个基地工作帕鲁上限
BASE_CAMP_WORKER_MAX_NUM=15
# 每个公会基地数量上限
BASE_CAMP_MAX_NUM_IN_GUILD=4
# 单基地建筑数量上限(0=无限)
MAX_BUILDING_LIMIT_NUM=0
# 是否开启建造区域限制
BUILD_AREA_LIMIT=False

# ════════ 公会 ════════
# 公会最大人数
GUILD_PLAYER_MAX_NUM=20
# 公会全员离线时自动解散
AUTO_RESET_GUILD_NO_ONLINE_PLAYERS=False
# 自动解散的离线小时数
AUTO_RESET_GUILD_TIME_NO_ONLINE_PLAYERS=72.000000

# ════════ PvP / 公会对抗 ════════
# 是否开启PvP
IS_PVP=False
# 公开服防恶意 PK，先关玩家互伤
ENABLE_PLAYER_TO_PLAYER_DAMAGE=False
# 是否开启友军误伤
ENABLE_FRIENDLY_FIRE=False
# 是否允许进攻其他公会基地
ENABLE_DEFENSE_OTHER_GUILD_PLAYER=False
# 能否捡其他公会死亡掉落
CAN_PICKUP_OTHER_GUILD_DEATH_PENALTY_DROP=False
# 隐藏其他公会基地范围特效
INVISIBLE_OTHER_GUILD_BASE_CAMP_AREA_FX=False

# ════════ 难度 / 死亡惩罚 / 硬核 ════════
# 难度(None/Casual/Normal/Hard…)
DIFFICULTY=None
# 死亡惩罚(None不掉/Item掉物品/ItemAndEquipment掉物品装备/All全掉含帕鲁)
DEATH_PENALTY=All
# 硬核模式(死亡永久失去)
HARDCORE=False
# 硬核死亡后是否重建角色
CHARACTER_RECREATE_IN_HARDCORE=False
# 硬核下帕鲁是否也永久失去
PAL_LOST=False
# 长期不登录是否惩罚
ENABLE_NON_LOGIN_PENALTY=True

# ════════ 世界 / 探索 ════════
# 是否允许快速旅行(传送)
ENABLE_FAST_TRAVEL=True
# 是否地图选择出生点
IS_START_LOCATION_SELECT_BY_MAP=True
# 是否出现入侵者(突袭)
ENABLE_INVADER_ENEMY=True
# 是否出现掠食者头目帕鲁
ENABLE_PREDATOR_BOSS_PAL=True

# ════════ 帕鲁箱跨服传输 ════════
# 是否允许把帕鲁导出到全局帕鲁箱
ALLOW_GLOBAL_PALBOX_EXPORT=True
# 是否允许从全局帕鲁箱导入
ALLOW_GLOBAL_PALBOX_IMPORT=False

# ════════ 随机器 Randomizer ════════
# 随机器类型(None=关)
RANDOMIZER_TYPE=None
# 随机器种子
RANDOMIZER_SEED=""
# 随机器帕鲁等级是否随机
IS_RANDOMIZER_PAL_LEVEL_RANDOM=False

# ════════ 其它 / 杂项 ════════
# 空投补给间隔(分钟)
SUPPLY_DROP_SPAN=180
# 每分钟聊天发言上限
CHAT_POST_LIMIT_PER_MINUTE=10
# 是否启用便便(UNKO)
ACTIVE_UNKO=False
# 手柄瞄准辅助
ENABLE_AIM_ASSIST_PAD=True
# 键盘瞄准辅助
ENABLE_AIM_ASSIST_KEYBOARD=False
# 容器强制保存间隔(秒)
ITEM_CONTAINER_FORCE_MARK_DIRTY_INTERVAL=1.000000
# 物品腐败速度倍率
ITEM_CORRUPTION_MULTIPLIER=1.000000
# 实体同步距离(性能相关)
SERVER_REPLICATE_PAWN_CULL_DISTANCE=15000.000000
```

> ✅ 保存后回到 [4.3 启动并验证](#43-启动并验证) 继续。

<a id="常用调参速查"></a>
### 常用调参速查

| 想达到的效果 | 改哪个参数 |
|---|---|
| 升级更快 | `EXP_RATE` 调大（如 100=百倍）|
| 更好抓帕鲁 | `PAL_CAPTURE_RATE` 调大 |
| 野外帕鲁更多 | `PAL_SPAWN_NUM_RATE` 调大 |
| 砍树挖矿出更多 | `COLLECTION_DROP_RATE` 调大 |
| 背包不超重 | `ITEM_WEIGHT_RATE` 调小（如 0.1）|
| 秒孵蛋 | `PAL_EGG_DEFAULT_HATCHING_TIME=0` |
| 死亡不掉东西 | `DEATH_PENALTY=None` |
| 开 PvP | `IS_PVP=True` 且 `ENABLE_PLAYER_TO_PLAYER_DAMAGE=True` |
| 建筑不用喂材料维护 | `BUILD_OBJECT_DETERIORATION_DAMAGE_RATE=0` |

---

<a id="第-12-章常见问题"></a>
## 第 12 章 · 常见问题

- **`/帕鲁状态` 报离线 / 认证失败**：检查 `api_base` 是否用容器名 `palworld-server`、两个编排是否在同一网络 `astrbot_default`、`admin_password` 是否等于服务器 `.env` 的 `ADMIN_PASSWORD`、`.env` 里 `REST_API_ENABLED=true`。
- **`/帕鲁我` 提示"读不到存档"**：是否挂了 docker.sock、astrbot 容器内是否装了 `palworld-save-tools==0.24.0`、`save_dir_in_container` 留空能否自动探测到世界目录。（`palwork/` 已随插件自带、按相对路径加载，**无需再放到 `data/palwork/`**。）
- **`/帕鲁自检` 里存档解析显示"库就绪但暂未解析出数据·可能空档"**：这是**全新/空世界**的正常现象——世界还没有任何玩家角色时，存档里没有角色数据。等有人上线玩一会儿、服务器自动存档后，再发存档类指令即可正常读到。
- **离线玩家查不到队伍 / 背包 / 据点**：`.env` 要 `EXIST_PLAYER_AFTER_LOGOUT=True` 并到 1Panel 把 palworld 编排「重新部署」。
- **改了 .env 没生效**：必须在 1Panel **编排 → 重新部署**，光「重启」不会重新读 `.env`。
- **进不去服 / 密码错误**：八成是某行参数把注释写在了同一行（见第 11 章规则 1），检查 `SERVER_PASSWORD`、`ADMIN_PASSWORD` 那几行。
- **社区列表搜不到我的服**：`COMMUNITY=true` 是否开、27015 端口是否在 1Panel 防火墙**和**云安全组都放行了。
- **网页面板/后台打不开**：对应端口是否在云厂商安全组放行（1Panel 面板端口、6185、6099）。
- **首条存档指令慢（约 5 秒）**：正常，首次要启动浏览器 + 拉档，之后有缓存就快了。

---

<a id="第-13-章安全提醒"></a>
## 第 13 章 · 安全提醒

- 帕鲁 **8212 REST 端口绝不要映射到公网**（编排里用 `127.0.0.1:8212:8212` 只绑本机）。
- `ADMIN_PASSWORD` 用强密码并改掉默认值。
- **1Panel 面板本身**：用随机端口 + 安全入口，面板登录密码设强一些；有条件只对自己 IP 开放面板端口。
- AstrBot 后台（6185）和 NapCat（6099）尽量只对自己的 IP 开放，配置完 NapCat 可以不再暴露 6099。
- 插件配置里的 `admin_qq` 只填可信管理员——管理类指令（踢人 / 封禁 / 关服 / 查他人存档）只有白名单 QQ 能用。
- docker.sock 用 `:ro` 只读挂载，降低风险。
