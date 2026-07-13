# data/ingame/icons — 游戏原生 UI 图标

这些 PNG 是从《幻兽帕鲁》1.0 **客户端 pak 提取的真实游戏图标**(透明底),
供 ingame 主题使用。**不是 AI 生成、不是 Emoji 截图**。

- 来源:`Pal-Windows.pak` → texexport(CUE4Parse) 解码 UTexture2D。
- 复现:`python tools/game_data/extract_ingame_icons.py`(参数见脚本头)。
- 语义键 ↔ 游戏资产 ↔ 状态:见 `data/ingame/manifest.json`。

## 目录
- `element/` — 属性 9(视觉实测序:无火水雷草暗龙地冰)。
- `work/` — 工作适性 13(按图标内容绑定:medicine=药瓶, oil=油桶)。
- `status/` — 元素系状态异常 9。
- `pal/` — 头目(alpha)/ 突变(mutation)/ 浓缩(condensation)。
- `stat/` — HP(心)/ 防御(盾)/ 重量(秤)/ 饱食(刀叉)。
- `ui/` — 性别 / 稀有度 / 货币(金币·狗币·赏金)/ 科技点。

## 尚缺 / 待核实(见 manifest 状态字段)
- **待截图核实语义**:面板图标 `T_icon_status_01/02/05/07`(脉冲/爆发/锤/帕鲁头)疑为 SAN/攻击/工作速度,未确认前不绑。
- **pending-extract**:非元素症状(骨折/扭伤/虚弱/精神萎靡)。
- **游戏无扁平图标(text-keep)**:闪光(仅粒子特效)、觉醒(未见专属纹理)。保留 Emoji fallback。
- `server.*`/`plugin.*`(CPU/内存/自检/审计/备份…)游戏无此语义 → 用插件扩展 SVG,不放此目录。
