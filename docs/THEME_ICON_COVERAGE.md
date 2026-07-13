# 三主题图标覆盖表

> 真实游戏语义图标为 **fantasy / pixel / ingame 三主题共享素材层**(v1.10.0 起)。
> 主题只决定展示方式;图标来源统一走 `data/ingame/manifest.json` + `render/assets.py`。
> UI 组件纹理(游戏窗口/切角面板/物品槽边框)仍**仅 ingame**,与语义图标区分。

## 一、架构(根因修复)

旧:`AssetResolver.img()` 里 `if style != "ingame": return ""` → 真图只在 ingame 生效,fantasy/pixel 永远回退 Emoji。
新:
- `game_icon(key)` — 主题无关,返回真实游戏图标(无原图/文件缺失 → 空串)。
- `img(key, style)` — 游戏有原图:三主题都返回真图;无原图:ingame 用中性 SVG,fantasy/pixel 返回空(模板回退 Emoji)。
- `game_icon_map(style)` — 三主题共享的语义图标映射(`ingame_icon_map()` 保留为别名);renderer **对三主题都注入** `{{ icons.* }}`。
- manifest 资产字段兼容 `game`(新)/`ingame`(旧);图标文件只一份。

## 二、语义图标(游戏有原图 → 三主题共享)

| 命名空间 | 键 | 游戏原图 | 资产路径(manifest) | 三主题解析 | 回退 |
|---|---|---|---|---|---|
| element | 无/火/水/草/雷/冰/地/暗/龙(9) | ✅ 9/9 | `icons/element/*.png` | ✅ 共享 | Emoji |
| work | 点火/浇水/播种/发电/手工/采集/伐木/采矿/制药/冷却/搬运/牧场(+1) | ✅ 13 | `icons/work/*.png` | ✅ 共享 | Emoji |
| currency | gold/tech_point/ancient_tech_point/dog_coin/bounty | ✅ 5/5 | `icons/ui/*.png` | ✅ 共享 | 💰 等 |
| pal | 闪光/头目/塔主(alpha)/突变/浓缩/性别×2/稀有度 | ✅ 7 | `icons/pal/*.png`,`icons/ui/*.png` | ✅ 共享 | Emoji |
| passive_rank | rank_down/up1/up2/up3/up3_plus | ✅ 5/5 | `icons/ui/*.png` | ✅ 共享 | 箭头 |
| stat | hp/defense/weight/hunger | ✅ 4 | `icons/ui/*.png` | ✅ 共享 | Emoji |
| stat | attack/san/work_speed/stamina/speed | 🔶 待提取 | — | 回退 Emoji | 明确标缺失 |

> 解析层三主题共享**已全部生效**(`test_game_icon_shared_across_all_themes` 守护:上述键 fantasy/pixel/ingame 都返回真图)。

## 三、模板接线状态(fantasy/pixel 用上真图的卡)

| 卡 | 元素 | 工作适性 | 货币 | 状态 |
|---|---|---|---|---|
| 属性克制图(element) | ✅ | — | — | ✅ 三主题真图 |
| 帕鲁详情(paldex) | ✅ | ✅ | ✅(贩卖价) | ✅ |
| 栖息区域 / boss / 竞技场(元素徽章) | ✅ | — | — | ✅(共享 pill 徽章) |
| 据点帕鲁(basecamp,工作适性) | — | ✅ | — | ✅ |
| 物品详情 / 词条大全(price) | — | — | ✅ | ✅ |
| 对比页 小徽章(font-size:10px 元素) | 🔶 | — | — | 待接(密集小徽章,评估可读性) |
| 稀有度 ★ / 头目·塔主徽章 | — | — | — | 结构符号(★/箭头)保留,头目·塔主待接 pal.alpha |
| message/排行/任务/地图/帮助 的装饰性/section-header emoji | — | — | — | 装饰性,非逐项语义图标,保留 |

## 四、插件扩展概念(游戏无图 → 各主题自有)

QQ / AstrBot / Docker / CPU / 内存 / REST / 网络延迟 / 服务器在线离线 / 备份 / 审计 / 自检 / 管理员 / 搜索 / 成功失败 / 通知
- fantasy:Emoji/奇幻图标;pixel:像素图标;ingame:中性线性 SVG(`server.*` / `plugin.*`)。
- **不得**为"统一"给这些套语义错误的游戏图标(`test_plugin_ext_still_per_theme` 守护)。

## 五、回退规则

1. 游戏有原图 → 三主题必须用游戏图标。
2. 游戏无原图 → 用当前主题的合理扩展图标(Emoji/像素/SVG)。
3. 素材文件意外缺失 → 不得整卡渲染失败;fantasy/pixel 回退 Emoji、ingame 回退中性占位;记录警告 + 缺失语义键。
4. 不得用 AI 生成图片冒充游戏原图。

## 六、仍缺 / 待办

- 游戏原图待提取:`stat.attack/san/work_speed/stamina/speed`(数值图标),提取前明确回退 Emoji。
- 模板接线待补:对比页密集小元素徽章、头目/塔主状态徽章(改用 `pal.alpha`)、部分帕鲁蛋/植入体/觉醒材料/蛋糕的图鉴详情图标(数据侧图标已在 `_item_icon`,主要是三主题一致展示)。
- 上述待办不影响已接卡:解析层三主题共享已全生效,新卡接入 `icons.*` 即自动三主题共享。
