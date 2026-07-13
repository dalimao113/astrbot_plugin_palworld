# data/ingame/parts — 游戏原生 UI 组件纹理

从《幻兽帕鲁》1.0 客户端 pak 提取的**真实 UI 面板/边框/槽/标签/按钮/进度条纹理**,
供 ingame 主题的通用组件(阶段C)用 `border-image` 九宫格 / `background` 拼装,
**不是**截图、**不是** AI 生成。复现见 `tools/game_data/extract_ingame_icons.py`。

> 多数为**白色/单色遮罩**,游戏内由材质着色 → CSS 里用 `filter`/半透明叠色重着为主题色,
> 描边/主色待游戏截图校准(与插件扩展 SVG 的 `PLUGIN_INK` 同批校准)。

| 文件 | 尺寸 | 游戏来源 | 角色 | 用法建议 |
|---|---|---|---|---|
| panel_glow_h | 1024×4 | T_prt_menu_bggrd | 面板顶/底柔光条 | `background` 横向拉伸 |
| panel_glow_v | 4×1024 | T_prt_menu_bggrd_v | 面板侧柔光条 | 纵向拉伸 |
| panel_blur | 72×72 | T_prt_base_blur | 柔边面板底 | `border-image` slice≈24 |
| panel_info | 688×308 | T_prt_palinfo_base | 帕鲁信息大面板底 | 固定底图 `background` |
| title_flare | 336×64 | T_prt_text_base_flare | 区块标题辉光/下划 | `background` no-repeat |
| frame_thin | 32×32 | T_prt_frame_2px | 2px 细边框 | `border-image` slice≈4 |
| frame_corner | 112×56 | T_prt_FrameCorner | ∧ 角饰 | 角标 `background` |
| operating_frame | 64×64 | …/OperatingTable/T_prt_Operating_Frame | 操作面板框 | `border-image` slice≈20 |
| **slot_item** | 128×128 | T_prt_item_base | **物品槽(切角方)** | `border-image` slice≈24 — GameItemSlot |
| slot_select | 52×52 | T_prt_itemslot_select_check_0 | 选中环 | 叠加 `background` |
| slot_pal | 96×80 | T_prt_pal_base_frame | 帕鲁卡框 | `border-image` slice≈24 — GamePalSlot |
| slot_pal_detail | 76×76 | T_prt_PalBoxDetailFrame | 帕鲁箱详情框 | `border-image` slice≈20 |
| slot_pal_icon | 68×68 | T_prt_pal_icon_base_s | 帕鲁头像方槽底 | `background` |
| slot_pal_circle | 64×64 | T_prt_pal_get_icon_frame | 帕鲁头像圆框 | `background` |
| **node_gold** | 128×128 | …/Research/T_prt_Research_IconBase_1_On | **金色八角节点框(招牌)** | GameRarityFrame/节点 `background` |
| node_dark | 128×128 | …_Off | 暗八角节点框(未激活) | 同上 |
| node_selected | 128×128 | …_Selected | 青色八角节点框(选中) | 选中态 |
| tab_base | 76×36 | T_prt_inventory_tab_base | 标签底 | `border-image` 横向 slice≈10 — GameTabs |
| tab_main | 212×36 | T_prt_maintab_base | 主标签条 | `background` |
| button | 32×32 | …/T_prt_DropDownButton_Normal | 按钮底 | `border-image` slice≈8 — GameButton |
| button_flare | 48×48 | T_prt_button_frame_flare | 按钮辉光 | 叠加 |
| **bar_hp** | 250×20 | T_gauge_HP_base | **HP/进度条底** | `border-image` 横向 — GameStatBar |
| bar_frame | 20×20 | Common/T_prt_common_gauge_frame | 进度条外框 | `border-image` slice≈6 |

**招牌组件**:`node_gold`(金色八角框)+ `slot_item`(切角槽)+ `bar_hp` 是最能体现帕鲁 UI 观感的三件,阶段C 优先用。
`slice` 值为**初估**,阶段C 建 CSS 时对照渲染微调。
