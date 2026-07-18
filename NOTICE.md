# NOTICE · 第三方素材与版权声明

本插件（`astrbot_plugin_palworld`）自身的**源代码**以仓库根目录 `LICENSE` 所载协议开源。
但仓库内**包含若干第三方素材/库**，它们各自的版权与授权**不属于本插件的开源协议范围**，
分别适用下列条款。使用、分发、二次开发本仓库时，请一并遵守这些第三方条款。

---

## 1. 游戏素材（Pocketpair, Inc. 版权所有）

- **路径**：`data/images/`（帕鲁/物品/科技/建筑等图标）、`data/ingame/`（游戏 UI 图标/纹理）、
  `data/worldmap.png`、`data/worldmap_hd.jpg`、`data/treemap_hd.jpg`（游戏地图底图）、
  以及 `data/*.json` 中提取自游戏 DataTable 的名称/数值/文本。
- **版权**：《幻兽帕鲁 / Palworld》© Pocketpair, Inc. 保留所有权利。
- **说明**：上述素材与数据提取自游戏客户端，仅用于**非商业的服务器查询/图鉴展示**，
  为玩家提供游戏信息参考。本项目与 Pocketpair 无隶属或授权关系。
  这些素材**不在本插件开源协议授权范围内**，其一切权利归 Pocketpair 所有。
- **合规预案**：若 Pocketpair 或权利人提出异议，将应要求移除相关素材。

## 2. Oodle 压缩库（专有）

- **路径**：`palwork/liboo2core.so`
- **版权**：Oodle Data Compression © Epic Games Tools LLC（原 RAD Game Tools）。专有软件。
- **说明**：解析游戏存档（`.sav`）需要 Oodle 解压。该库为专有组件，**不适用本插件开源协议**，
  仅为本地存档解析功能附带。若权利人要求，将改为由用户从其本地游戏安装目录自备。

## 3. Fusion Pixel Font 缝合像素字体（OFL-1.1）

- **路径**：`data/fonts/fusion-pixel-12px-proportional-zh_hans.subset.woff2`
- **来源**：<https://github.com/TakWolf/fusion-pixel-font>
- **许可**：SIL Open Font License 1.1（见 `data/fonts/OFL.txt`）。允许自由嵌入、子集化、再分发。
- **说明**：pixel 主题的中文像素字体，已按 OFL 允许的方式做子集化并内联，供离线渲染使用。

## 4. palworld-save-tools（Python 依赖）

- **来源**：PyPI / GitHub 上的 `palworld-save-tools`（MIT 许可）。
- **说明**：作为运行时依赖用于存档解析；本插件在运行时对其做了少量兼容性 monkeypatch（见 `palwork/palsave.py`），
  未修改其分发文件本身。

## 5. 卡片背景插画

- **路径**：`bg.jpg`、`bg_*.jpg`
- **说明**：卡片顶部背景插画。**若这些图片为第三方美术作品，其版权归原作者所有**，
  部署者应自行确认使用权利；可用自有图片替换（见 README「背景图」说明）。

---

> 本文件用于开源合规披露。任何权利人如认为本仓库存在侵权内容，
> 请通过仓库 issue 或 `SECURITY.md` 所列方式联系，我们将及时处理（下架/替换）。
