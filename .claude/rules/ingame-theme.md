---
paths:
  - "render/**/*"
  - "data/ingame/**/*"
  - "tools/game_data/**/*"
  - "constants.py"
  - "config.py"
  - "_conf_schema.json"
  - "main.py"
  - "tests/**/*theme*"
  - "tests/**/*render*"
---

# ingame 游戏原生主题规则

编辑上述路径(渲染/主题/素材/配置)时,遵守以下规则。总纲见根目录 `CLAUDE.md`。

## 主题独立性
- ingame 是**独立第三主题**,禁止覆盖 fantasy / pixel。
- 三套主题**共用业务数据**;主题只管模板/CSS/组件/图片/纹理/图标。
- 三套主题的**模板键集合必须一致**;以 `TEMPLATE_KEYS` / STYLES 实际注册表为权威来源审计,不能凭记忆。
- 未知 `card_style` 值安全回退到 fantasy;ingame 素材缺失时安全回退,不得让指令异常。
- 改 ingame 不得改变 fantasy/pixel 现有视觉表现。

## 素材获取
- ingame **必须**通过统一的 **Asset Manifest + 图标解析器**取图(如 `asset("work.mining")`)。
- **禁止**在各 Handler / 模板里到处硬编码素材文件路径。
- 游戏存在真实图标 → 用真实图标;游戏不存在对应语义 → 用统一插件扩展 SVG,**不得乱用**语义错误的游戏图标。
- 不得用 AI 生成图标冒充游戏原始图标;未取得真实素材必须明确标记缺失。

## Emoji 审计
- **禁止只替换部分常用页面**的 Emoji。
- 必须**同时审计**:模板里的静态 Emoji + Python 代码动态注入的 Emoji。
- 用户自己输入的 Emoji(昵称/公告/聊天)不得删除。

## 原生 UI 组件(复用,不为每卡复制 CSS)
- `GameWindow` / `GameHeader` / `GameTabs` / `GamePanel` / `GameSidebar`
- `GameItemGrid` / `GameItemSlot` / `GamePalSlot` / `GameStatBar` / `GamePropertyRow`
- `GameWorkIcon` / `GameElementBadge` / `GameRarityFrame` / `GameTooltip` / `GameKeyHint` / `GameProgressBar` / `GameSectionTitle`
- CSS 用统一变量(`--pal-bg`/`--pal-panel`/`--pal-accent` 等),颜色以游戏截图/素材校准,不盲抄示例值。
- 游戏边框/面板纹理优先 **border-image / 九宫格拉伸**,避免小图直接拉伸变形。

## 手机适配与验收
- 手机竖屏允许重排(横向双栏→竖向卡),但保留游戏视觉语言;文字必须清晰。
- **每批卡片完成后必须输出预览图**对照游戏截图检查。
- 缺少截图时,**列出需要用户提供的页面清单**,不得凭想象声称高度还原。
