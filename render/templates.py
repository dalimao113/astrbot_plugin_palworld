"""卡片 HTML/CSS 模板与皮肤表（从 main.py 原样迁出，字符不改）。
两套皮肤 fantasy/pixel 的全部 Jinja 模板 + STYLES/TEMPLATE_KEYS。
注意：Jinja autoescape 关闭，模板内含大量刻意内嵌 HTML；
不可信字段必须由调用方用 utils.text._esc 逐字段转义后再注入。"""
from __future__ import annotations

# 少数网格模板在构造时内嵌列数常量（str(GRID_COLS) 拼接），需从父包常量表取值。
from ..constants import GRID_COLS


# ----------------------------------------------------------------------
# 卡片模板(Jinja2 + 内联 CSS)。html_render(tmpl, data) -> 图片 url。
# 主题色通过 data 的 theme 注入。CSS 单括号在 Jinja 中是安全的。
# ----------------------------------------------------------------------
# 公共样式：二次元奇幻风。整图插画背景 + 深蓝紫磨砂玻璃面板 + 暗金描边 + 宝石点缀。
# 插画由用户提供(bg.jpg / bg_<卡名>.jpg)；无图时回退深蓝紫渐变。
_BASE_CSS = """
  * { box-sizing:border-box; margin:0; padding:0;
      font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif; }
  html { zoom: {{ zoom }}; } html, body { width:{{ cw|default(540) }}px; }
  body { position:relative; color:#e9e0f5; display:flex; flex-direction:column;
    {% if bg %}background:url('{{ bg }}') center/cover no-repeat, #161030;
    {% else %}background:radial-gradient(circle at 72% 16%, #3c2a74 0%, #1b1442 55%, #110b2c 100%);{% endif %} }
  body::before { content:""; position:absolute; inset:0; z-index:0;
    background:
      linear-gradient(115deg, rgba(18,12,46,0.94) 0%, rgba(26,18,62,0.82) 42%, rgba(30,22,72,0.32) 70%, rgba(45,32,95,0.05) 100%),
      linear-gradient(0deg, rgba(12,8,34,0.96) 0%, rgba(12,8,34,0.30) 32%, rgba(12,8,34,0) 56%); }
  .page { position:relative; z-index:2; min-height:300px; flex:1 1 auto; display:flex; flex-direction:column; justify-content:flex-start; padding:30px 20px 22px; }
  /* 内容偏少时让主面板撑满 .page 剩余高度，避免主题框下方露出空背景(footer 被顶到底部) */
  .page > .glass:last-of-type { flex:1 1 auto; }
  .head { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:16px; gap:12px; }
  .title { color:#f3ecd2; font-size:23px; font-weight:800; line-height:1.25;
    text-shadow:0 2px 8px rgba(0,0,0,.75); display:flex; align-items:center; gap:9px; }
  .title .nm { max-width:330px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .subtitle { color:#c6b6e2; font-size:13px; margin-top:6px; text-shadow:0 1px 4px rgba(0,0,0,.6);
    display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .badge { flex-shrink:0; font-size:13px; font-weight:800; padding:6px 14px; border-radius:999px;
    box-shadow:0 3px 12px rgba(0,0,0,.35); }
  .badge.on { color:#0f2a1a; background:linear-gradient(135deg,#7ef0a8,#3fd07a); }
  .badge.off { color:#3a0f15; background:linear-gradient(135deg,#ff9aa6,#e5556a); }
  .badge.gold { color:#2a1d05; background:linear-gradient(135deg,#ffe9a8,#e8c466); }
  .glass { position:relative; background:rgba(34,24,78,0.52); border-radius:22px;
    border:1.5px solid rgba(232,198,106,0.42);
    box-shadow:0 10px 34px rgba(0,0,0,.5), inset 0 0 40px rgba(130,95,210,.16);
    padding:20px; margin-bottom:13px; }
  .glass::before { content:""; position:absolute; inset:6px; border-radius:16px;
    border:1px solid rgba(232,198,106,0.20); pointer-events:none; }
  .gem { position:absolute; width:13px; height:13px; transform:rotate(45deg); z-index:3; border-radius:2px;
    background:linear-gradient(135deg,#fff0bd,#e8c466,#9c7619);
    box-shadow:0 0 10px rgba(232,198,106,.9), inset 0 0 3px #fff6da; }
  .gem.tl{top:-7px;left:24px} .gem.tr{top:-7px;right:24px} .gem.bl{bottom:-7px;left:24px} .gem.br{bottom:-7px;right:24px}
  .sec-t { color:#e8c466; font-size:14px; font-weight:800; letter-spacing:1px; margin:2px 0 12px;
    display:flex; align-items:center; gap:7px; }
  .gold { color:#e8c466; }
  .m3 { display:grid; grid-template-columns:repeat(3,1fr); gap:11px; }
  .m2 { display:grid; grid-template-columns:1fr 1fr; gap:11px; }
  .tile { background:rgba(18,12,48,0.55); border:1px solid rgba(232,198,106,0.22); border-radius:14px; }
  .tc { text-align:center; padding:15px 6px; }
  .tc .i { font-size:20px; margin-bottom:6px; }
  .tc .v { color:#f3e6c2; font-size:22px; font-weight:800; line-height:1.1; word-break:break-all; }
  .tc .k { color:#9c8fc0; font-size:12px; margin-top:4px; }
  .row { display:flex; align-items:center; padding:12px 14px; border-radius:14px; margin-bottom:9px;
    background:rgba(18,12,48,0.5); border:1px solid rgba(232,198,106,0.16); }
  .pill { display:inline-block; font-size:13px; font-weight:700; padding:3px 11px; border-radius:999px; color:#fff; }
  .pill.gold { color:#2a1d05; background:linear-gradient(135deg,#ffe9a8,#e8c466); }
  .pill.soft { color:#e8c466; background:rgba(232,198,106,0.14); border:1px solid rgba(232,198,106,.3); }
  .num-gold { font-weight:900; background:linear-gradient(180deg,#fff3cc,#e8c466,#c79a2e);
    -webkit-background-clip:text; background-clip:text; color:transparent; }
  .bar { height:9px; border-radius:999px; background:rgba(8,5,26,0.6); overflow:hidden; border:1px solid rgba(232,198,106,.18); }
  .barf { height:100%; border-radius:999px; background:linear-gradient(90deg,#8a6ff0,#b98bf0); box-shadow:0 0 8px rgba(160,120,240,.6); }
  .barf.hot { background:linear-gradient(90deg,#f5a623,#e5484d); }
  .footer { text-align:center; color:#9486b6; font-size:12px; padding-top:16px; margin-top:auto; }
  .footer span { color:#e8c466; font-weight:700; }
  .empty { flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center;
    padding:50px 24px; text-align:center; }
  .empty .ee { font-size:64px; margin-bottom:14px; filter:drop-shadow(0 4px 10px rgba(0,0,0,.5)); }
  .empty .et { font-size:20px; font-weight:800; color:#f3ecd2; }
  .empty .ed { font-size:14px; color:#b9a9d6; margin-top:9px; }
"""

_HEAD = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>""" + _BASE_CSS
_GEMS = '<span class="gem tl"></span><span class="gem tr"></span><span class="gem bl"></span><span class="gem br"></span>'
_FOOT = '<footer class="footer">🕓 {{ now }} · <span>🐱 大狸猫 · 帕鲁服务器管家</span></footer>'


STATUS_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head">
    <div>
      <div class="title">🦊 <span class="nm">{{ servername }}</span></div>
      <div class="subtitle">🏷 {{ version }}</div>
    </div>
    <span class="badge {{ 'on' if online else 'off' }}">● {{ '在线' if online else '离线' }}</span>
  </div>
  <div class="glass">""" + _GEMS + """
    <div style="text-align:center">
      <div style="color:#b9a9d6;font-size:13px;font-weight:600;letter-spacing:2px">当前在线人数</div>
      <div style="line-height:1;margin-top:3px">
        <span class="num-gold" style="font-size:74px;letter-spacing:-2px;text-shadow:0 4px 16px rgba(232,198,106,.3)">{{ cur }}</span>
        <span style="font-size:34px;font-weight:700;color:#9888bd">/{{ maxn }}</span>
        <span style="font-size:15px;color:#9888bd;margin-left:4px">人</span>
      </div>
    </div>
    <div class="m3" style="margin-top:18px">
      <div class="tile tc"><div class="i">⚡</div><div class="v">{{ fps }}</div><div class="k">服务器FPS</div></div>
      <div class="tile tc"><div class="i">📅</div><div class="v">{{ days }}</div><div class="k">游戏天数</div></div>
      <div class="tile tc"><div class="i">⏱</div><div class="v">{{ uptime }}</div><div class="k">运行时长</div></div>
    </div>
    {% if players %}
    <div class="sec-t" style="margin-top:18px">👥 在线玩家</div>
    <div style="display:flex;align-items:center;padding:0 12px 5px;font-size:10.5px;color:#9a93b8;letter-spacing:.5px">
      <span style="flex:1">玩家名</span>
      <span style="width:54px;text-align:center">等级</span>
      <span style="width:62px;text-align:center">在线时长</span>
      <span style="width:58px;text-align:center">延迟</span>
    </div>
    {% for p in players %}
    <div class="row" style="padding:9px 12px">
      <div style="flex:1;min-width:0;font-size:15px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ p.name }}</div>
      <span style="width:54px;text-align:center"><span class="pill soft" style="font-size:11px">Lv.{{ p.level }}</span></span>
      <span style="width:62px;text-align:center;font-size:12px;color:#c2b2dd">{% if p.dur %}⏱{{ p.dur }}{% else %}—{% endif %}</span>
      <span style="width:58px;text-align:center"><span class="pill" style="background:{{ p.ping_color }};color:#fff;font-size:11px">{{ p.ping }}ms</span></span>
    </div>
    {% endfor %}
    {% endif %}
    {% if load %}
    <div style="margin-top:18px">
      <div class="sec-t">◆ 服务器负载</div>
      <div style="margin-bottom:11px"><div style="display:flex;justify-content:space-between;color:#cfc1ea;font-size:12.5px;font-weight:700;margin-bottom:6px"><span>CPU</span><span class="gold">{{ load.cpu }}%</span></div><div class="bar"><div class="barf {{ 'hot' if load.cpu_bar>=80 else '' }}" style="width:{{ load.cpu_bar }}%"></div></div></div>
      <div><div style="display:flex;justify-content:space-between;color:#cfc1ea;font-size:12.5px;font-weight:700;margin-bottom:6px"><span>内存</span><span class="gold">{{ load.mem_text }} · {{ load.mem_pct }}%</span></div><div class="bar"><div class="barf {{ 'hot' if load.mem_bar>=80 else '' }}" style="width:{{ load.mem_bar }}%"></div></div></div>
    </div>
    {% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


PLAYERS_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head">
    <div>
      <div class="title">👥 在线玩家</div>
      <div class="subtitle">实时帕鲁岛冒险者名单</div>
    </div>
    <span class="badge gold">{{ count }} 人在线</span>
  </div>
  {% if not players %}
  <div class="glass" style="flex:1;display:flex">""" + _GEMS + """
    <div class="empty"><div class="ee">🏝️</div><div class="et">暂无玩家在线</div><div class="ed">帕鲁岛静悄悄～ 快喊小伙伴上线冒险吧！</div></div>
  </div>
  {% else %}
  <div class="glass">""" + _GEMS + """
    {% for p in players %}
    <div class="row">
      <div style="width:28px;height:28px;flex-shrink:0;border-radius:50%;background:rgba(232,198,106,.16);color:#e8c466;font-size:13px;font-weight:800;display:flex;align-items:center;justify-content:center;margin-right:13px">{{ loop.index }}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:17px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:250px">{{ p.name }}</div>
        <span class="pill soft" style="margin-top:5px;font-size:12px">⭐ Lv.{{ p.level }}</span>
      </div>
      <span class="pill" style="background:{{ p.ping_color }};min-width:62px;text-align:center">{{ p.ping }}ms</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  """ + _FOOT + """
</div></body></html>"""


SETTINGS_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head">
    <div>
      <div class="title">⚙️ 服务器设置</div>
      <div class="subtitle">当前帕鲁世界规则与倍率配置</div>
    </div>
  </div>
  <div class="glass">""" + _GEMS + """
    <div class="m2">
      {% for it in items %}
      <div class="tile" style="padding:13px 15px;border-left:3px solid #e8c466">
        <div style="font-size:12.5px;color:#9c8fc0;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ it.k }}</div>
        <div style="font-size:18px;font-weight:800;color:#f3e6c2;margin-top:4px;word-break:break-word">{{ it.v }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


HELP_TMPL = _HEAD + """
  .cmd { display:inline-block; width:49%; box-sizing:border-box; vertical-align:top; padding:7px 4px; }
  .cmd .c { display:block; font-size:14px; font-weight:800; color:#f3ecd2; }
  .cmd .c b { color:#2a1d05; background:linear-gradient(135deg,#ffe9a8,#e8c466); padding:2px 8px; border-radius:6px; }
  .cmd .d { display:block; font-size:12px; color:#b9a9d6; margin-top:3px; }
</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">📖 帕鲁指令帮助</div>
    <div class="subtitle">指令一行一条，看清楚再发哦～</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">🔍 查询（所有人可用）</div>
    <div class="cmd"><div class="c"><b>/帕鲁</b></div><div class="d">查看服务器状态</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁状态</b></div><div class="d">同上，服务器状态总览</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁在线</b></div><div class="d">查看在线玩家列表</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁设置</b></div><div class="d">查看服务器倍率与规则</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁统计</b></div><div class="d">今日峰值/平均 + 近7日趋势</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁热力</b></div><div class="d">7×24 在线热力图·看高峰时段</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁战力榜</b></div><div class="d">全服最强帕鲁排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁闪光墙</b></div><div class="d">全服闪光帕鲁收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁头目墙</b></div><div class="d">全服头目(Alpha)收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁图鉴榜</b></div><div class="d">全服图鉴收集进度排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁资产榜</b></div><div class="d">全服帕鲁身价排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会战力</b></div><div class="d">各公会战力总和排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁更新公告</b></div><div class="d">官方最新更新公告(中文)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁肝帝榜</b></div><div class="d">本周在线时长排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁图鉴</b> [名/字]</div><div class="d">详情或模糊列表·空=全部·翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁编号</b> 13B</div><div class="d">按图鉴编号查(支持变种)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁配种</b> 亲A 亲B</div><div class="d">查后代 + 子代继续配</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁反配种</b> 帕鲁名</div><div class="d">列出能配成它的组合</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁怎么配</b> 帕鲁名</div><div class="d">用你现有帕鲁算配种路线</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁继承</b> 词条A｜词条B</div><div class="d">算后代继承词条的概率</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁哪里掉</b> 物品</div><div class="d">查哪些帕鲁掉落该物品</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁物品</b> [名/类]</div><div class="d">详情/分类浏览/翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁设施</b> [名/字]</div><div class="d">详情或模糊列表·空=全部·翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁科技</b> [名/字]</div><div class="d">详情或模糊列表·空=全部·翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁研究所</b> [类/名]</div><div class="d">🆕 全局增益研究·9大适性·材料/前置</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁栖息区域</b> 帕鲁名</div><div class="d">地图上涂出它的刷新热区</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁推荐词条</b> 帕鲁名</div><div class="d">按角色推荐高价值词条</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁属性克制</b></div><div class="d">九系属性克制关系图</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁主线</b> [页]</div><div class="d">按剧情顺序列出主线任务</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁支线</b> [NPC]</div><div class="d">支线任务（可按 NPC 筛选）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁任务</b> 任务名</div><div class="d">任务详细攻略：目标/坐标/奖励</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁塔主</b> [名]</div><div class="d">高塔塔主：属性/等级/血量/攻略</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁突袭</b> [名]</div><div class="d">突袭 Boss 数据与打法提示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁竞技场</b> [段位]</div><div class="d">竞技场对手阵容/段位奖励</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁商人</b> [名]</div><div class="d">各商店卖什么 + 价格/货币</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁哪里买</b> 物品</div><div class="d">某物品在哪个商店买、多少钱</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁技能</b> 名/属性</div><div class="d">主动技能威力/冷却/效果</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁技能果实</b> [属性/名]</div><div class="d">🆕 92种果实图鉴·带图标·教什么技能</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁植入体</b> [名]</div><div class="d">🆕 68种植入体·改造帕鲁词条·效果/用法</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁钓鱼</b></div><div class="d">钓鱼能钓到什么 + 概率</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁工作</b> 工种</div><div class="d">某工种(采矿/搬运…)最强帕鲁排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁坐骑</b></div><div class="d">可骑乘帕鲁按奔跑速度排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁对比</b> A B</div><div class="d">两只帕鲁数值并排对比</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁料理</b> [效果]</div><div class="d">有增益的料理(攻击/工作速度/配种…)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁武器</b> [名]</div><div class="d">武器攻击力/解锁科技/弹药</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁帮助</b></div><div class="d">显示本帮助卡片</div></div>
  </div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">🙋 玩家自助（所有人可用）</div>
    <div class="cmd"><div class="c"><b>/帕鲁绑定</b> 游戏名</div><div class="d">绑定你的帕鲁角色</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁我</b></div><div class="d">个人档案·等级/技术点/队伍/背包</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁背包</b></div><div class="d">查看自己的背包物品明细</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁队伍</b></div><div class="d">查看自己出战帕鲁的面板</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁箱</b> [页]</div><div class="d">帕鲁箱全部帕鲁·翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁可孵化</b></div><div class="d">用你箱里的帕鲁能配出哪些新帕鲁</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁据点</b></div><div class="d">据点帕鲁：工作/适性/血量/SAN/伤病</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁症状</b> [状态]</div><div class="d">伤病治疗速查(骨折/濒死/低SAN…)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会帕鲁</b> [页]</div><div class="d">公会终端：全公会成员帕鲁汇总</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁箱查询</b> 编号</div><div class="d">看帕鲁箱某只的详细面板</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会</b></div><div class="d">查看自己公会的成员/会长</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会榜</b></div><div class="d">公会在线时长排行榜</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁订阅</b> 游戏名</div><div class="d">某玩家上线时 @ 你</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁退订</b> 游戏名</div><div class="d">取消上线提醒</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁找人</b> 游戏名</div><div class="d">查某玩家是否在线</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁喊话</b> 内容</div><div class="d">把话广播到游戏内</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁喊</b> 游戏名</div><div class="d">@绑定的玩家喊TA上线</div></div>
  </div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">🛠️ 管理（仅管理员）</div>
    <div class="cmd"><div class="c"><b>/帕鲁公告</b> 内容</div><div class="d">向服务器广播公告</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁踢</b> ID [理由]</div><div class="d">踢出指定玩家</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁封</b> ID [理由]</div><div class="d">封禁玩家（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁解封</b> ID</div><div class="d">解除封禁</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁存档</b></div><div class="d">立即保存世界存档</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁关服</b> 秒 [提示]</div><div class="d">定时关服（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁重启服务器</b></div><div class="d">存档后重启服务器（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁备份列表</b></div><div class="d">查看所有自动备份存档</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁回档</b> 编号</div><div class="d">回档到指定备份（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁重置存档</b></div><div class="d">删档重开·全新世界（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁恢复存档</b></div><div class="d">还原上一次重置前的存档（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁审计</b></div><div class="d">查看最近管理操作记录</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁自检</b></div><div class="d">一键体检配置/连接/存档/渲染</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁地图</b></div><div class="d">在线玩家世界地图分布</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁确认</b></div><div class="d">确认上一条危险操作</div></div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


MSG_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div><div class="title">{{ head }}</div></div></div>
  <div class="glass" style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:40px 28px">""" + _GEMS + """
    <div style="font-size:74px;line-height:1;margin-bottom:20px;filter:drop-shadow(0 6px 14px rgba(0,0,0,.5))">{{ icon }}</div>
    <div style="font-size:26px;font-weight:900;color:{{ color }};line-height:1.35;word-break:break-word">{{ title }}</div>
    {% if desc %}<div style="margin-top:18px;font-size:15px;line-height:1.7;color:#cfc1ea;white-space:pre-line;word-break:break-word;background:rgba(18,12,48,0.5);border:1px solid rgba(232,198,106,0.2);border-radius:14px;padding:15px 18px;text-align:left;max-width:400px">{{ desc }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


STATS_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">📊 在线统计</div>
    <div class="subtitle">今日数据与近 7 日在线峰值</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div class="m3">
      <div class="tile tc"><div class="v gold">{{ peak }}</div><div class="k">今日峰值</div></div>
      <div class="tile tc"><div class="v gold">{{ avg }}</div><div class="k">今日平均</div></div>
      <div class="tile tc"><div class="v gold">{{ cur }}</div><div class="k">当前在线</div></div>
    </div>
    <div class="sec-t" style="margin-top:18px">📈 近 7 日在线峰值</div>
    <div style="display:flex;align-items:flex-end;gap:9px;height:170px;padding:6px 2px 0">
      {% for d in days %}
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%">
        <div style="font-size:12px;font-weight:700;color:#e8c466;margin-bottom:4px">{{ d.peak }}</div>
        <div style="width:72%;min-height:4px;height:{{ d.h }}%;border-radius:7px 7px 3px 3px;background:linear-gradient(180deg,#b98bf0,#8a6ff0);box-shadow:0 0 8px rgba(160,120,240,.5)"></div>
        <div style="font-size:10.5px;color:#9c8fc0;margin-top:7px">{{ d.label }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


RANK_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ rank_title | default('🏆 本周肝帝榜') }}</div>
    <div class="subtitle">{{ rank_sub | default('本周在线时长排行 · 看谁最肝～') }}</div>
  </div></div>
  {% if not rows %}
  <div class="glass" style="flex:1;display:flex">""" + _GEMS + """
    <div class="empty"><div class="ee">😴</div><div class="et">本周还没有在线记录</div><div class="ed">玩起来！在线时长会自动统计上榜～</div></div>
  </div>
  {% else %}
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" {% if loop.index <= 3 %}style="background:linear-gradient(100deg,rgba(232,198,106,0.16),rgba(18,12,48,0.5) 60%);border-color:rgba(232,198,106,0.4)"{% endif %}>
      <div style="width:34px;flex-shrink:0;text-align:center;font-size:20px;font-weight:900;color:#e8c466;margin-right:10px">{{ r.medal }}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:16px;font-weight:700;color:#f3ecd2;display:flex;align-items:center;gap:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.online %}<span style="width:8px;height:8px;border-radius:50%;background:#3fd07a;box-shadow:0 0 6px #3fd07a;flex-shrink:0"></span>{% endif %}</div>
        <div class="bar" style="margin-top:7px"><div class="barf" style="width:{{ r.pct }}%"></div></div>
      </div>
      <div style="flex-shrink:0;margin-left:12px;font-size:16px;font-weight:800;color:#e8c466">{{ r.dur }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  """ + _FOOT + """
</div></body></html>"""


PROFILE_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">👤 我的帕鲁档案</div>
    <div class="subtitle">绑定角色的在线数据</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="text-align:center;padding:6px 0 14px">
      {% if avatar %}<div style="width:96px;height:96px;margin:0 auto;border-radius:50%;padding:3px;background:linear-gradient(135deg,#ffe9a8,#e8a93a);box-shadow:0 4px 14px rgba(0,0,0,.5)"><img src="{{ avatar }}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;display:block"></div>
      {% else %}<div style="font-size:60px;line-height:1;filter:drop-shadow(0 4px 10px rgba(0,0,0,.5))">{% if online %}🧑‍🚀{% else %}😴{% endif %}</div>{% endif %}
      <div style="font-size:26px;font-weight:900;color:#f3ecd2;margin-top:8px;word-break:break-word">{{ name }}</div>
      <span class="badge {{ 'on' if online else 'off' }}" style="margin-top:12px;display:inline-block">● {% if online %}在线 · Lv.{{ level }}{% else %}离线中{% endif %}</span>
      {% if titles %}<div style="margin-top:13px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center">{% for t in titles %}<span class="pill soft">{{ t }}</span>{% endfor %}</div>{% endif %}
    </div>
    <div class="m3">
      <div class="tile tc"><div class="v gold">{{ week_dur }}</div><div class="k">本周在线</div></div>
      <div class="tile tc"><div class="v gold">{{ total_dur }}</div><div class="k">累计在线</div></div>
      <div class="tile tc"><div class="v gold">{{ rank }}</div><div class="k">本周排名</div></div>
    </div>
    {% if has_save %}
    <div class="sec-t" style="margin-top:18px">📜 存档实况</div>
    <div class="m3">
      <div class="tile tc"><div class="v gold">Lv.{{ s_level }}</div><div class="k">角色等级</div></div>
      <div class="tile tc"><div class="v gold">{{ tech }}</div><div class="k">技术点</div></div>
      <div class="tile tc"><div class="v gold">{{ recipes }}</div><div class="k">解锁配方</div></div>
    </div>
    <div class="m3" style="margin-top:11px">
      <div class="tile tc"><div class="v gold" style="color:#ff8a8a">❤ {{ max_hp }}</div><div class="k">最大生命</div></div>
      <div class="tile tc"><div class="v gold" style="color:#7fd4e0">⚡ {{ max_sp }}</div><div class="k">最大耐力</div></div>
      <div class="tile tc"><div class="v gold" style="color:#e6c98a">🏋 {{ weight }}</div><div class="k">负重上限</div></div>
    </div>
    <div class="m3" style="margin-top:11px">
      <div class="tile tc"><div class="v gold" style="color:#7fe0a0">{{ hp|int }}</div><div class="k">当前生命</div></div>
      <div class="tile tc"><div class="v gold">{{ shield|int }}</div><div class="k">护盾值</div></div>
      <div class="tile tc"><div class="v gold">{{ stomach|int }}</div><div class="k">饱食度</div></div>
    </div>
    <div class="m3" style="margin-top:11px">
      <div class="tile tc"><div class="v gold">{{ pal_total }}</div><div class="k">帕鲁总数</div></div>
      <div class="tile tc"><div class="v gold">{{ dex_owned }}<span style="font-size:13px;color:#9c8fc0">/{{ dex_total }}</span></div><div class="k">图鉴收集</div></div>
      <div class="tile tc"><div class="v gold" style="{% if hurt_n %}color:#ff7a7a{% endif %}">{{ hurt_n }}</div><div class="k">受伤帕鲁</div></div>
    </div>
    {% if status %}
    <div class="sec-t" style="margin-top:16px">💪 状态点强化</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:9px">
      {% for s in status %}
      <div style="display:flex;justify-content:space-between;align-items:baseline;background:rgba(18,12,48,.5);border:1px solid rgba(232,198,106,.18);border-radius:11px;padding:8px 11px">
        <span style="font-size:12.5px;color:#cfc1ea">{{ s.name }}</span>
        <span style="font-size:15px;font-weight:900;color:{% if s.points %}#e8c466{% else %}#6b6080{% endif %}">+{{ s.points }}</span>
      </div>
      {% endfor %}
    </div>
    {% endif %}
    {% if party %}
    <div class="sec-t" style="margin-top:16px">🐾 出战队伍 · {{ party_n }} 只</div>
    <div style="display:flex;flex-wrap:wrap;gap:10px;justify-content:center">
      {% for p in party %}
      <div style="display:flex;flex-direction:column;align-items:center;width:80px">
        <div style="position:relative;width:64px;height:64px;background:rgba(18,12,48,.5);border:1px solid rgba(232,198,106,.3);border-radius:13px;display:flex;align-items:center;justify-content:center">
          {% if p.icon %}<img src="{{ p.icon }}" style="width:54px;height:54px;object-fit:contain">{% else %}<span style="font-size:30px">🐾</span>{% endif %}
          {% if p.lucky %}<span style="position:absolute;top:-7px;right:-7px;font-size:16px">✨</span>{% elif p.alpha %}<span style="position:absolute;top:-7px;right:-7px;font-size:15px">👑</span>{% endif %}
        </div>
        <div style="font-size:12px;color:#f3ecd2;margin-top:5px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:80px">{{ p.name }}</div>
        <div style="font-size:11px;color:#e8c466">Lv.{{ p.level }}</div>
      </div>
      {% endfor %}
    </div>
    {% endif %}
    <div style="margin-top:15px;font-size:13px;color:#cfc1ea;line-height:1.7">🎒 背包 <b style="color:#e8c466">{{ bag_n }}</b> 种物品，发 <b>/帕鲁背包</b> 看明细；📦 帕鲁箱 <b style="color:#e8c466">{{ palbox_n }}</b> 只，发 <b>/帕鲁箱</b> 浏览{% if party %}；发 <b>/帕鲁队伍</b> 看出战面板{% endif %}</div>
    {% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


DAILY_TMPL = _HEAD + """
  .lp { display:flex; align-items:center; padding:7px 0; border-bottom:1px solid rgba(232,198,106,0.1); }
  .lp:last-child { border-bottom:none; }
  .lp .rk { width:24px; font-weight:900; color:#e8c466; }
  .lp .nm { flex:1; font-size:15px; font-weight:700; color:#f3ecd2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .lp .du { font-size:14px; font-weight:800; color:#e8c466; }
  .none { color:#9c8fc0; font-size:14px; padding:4px 0 6px; }
</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ title }}</div>
    <div class="subtitle">{{ now }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="color:#cfc1ea;font-size:14px;line-height:1.6;margin-bottom:14px">{{ greeting }}</div>
    <div style="display:flex;align-items:center;gap:10px;padding:12px 16px;border-radius:14px;background:rgba(18,12,48,0.55);border:1px solid rgba(232,198,106,0.2);font-size:15px;font-weight:700;color:#f3ecd2">
      <span class="badge {{ 'on' if online else 'off' }}" style="font-size:12px">{% if online %}在线{% else %}离线{% endif %}</span>
      {% if online %}当前 {{ cur }}/{{ maxn }} 人 · FPS {{ fps }} · 世界第 {{ days }} 天{% else %}服务器当前连不上{% endif %}
    </div>
    <div class="m3" style="margin-top:13px">
      <div class="tile tc"><div class="v gold">{{ today_peak }}</div><div class="k">今日峰值</div></div>
      <div class="tile tc"><div class="v gold">{{ today_avg }}</div><div class="k">今日平均</div></div>
      {% if show_yday %}<div class="tile tc"><div class="v gold">{{ yday_peak }}</div><div class="k">昨日峰值</div></div>
      {% else %}<div class="tile tc"><div class="v gold">{{ record }}</div><div class="k">历史纪录</div></div>{% endif %}
    </div>
  </div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">🔥 今日肝帝 TOP3</div>
    {% if today_top %}{% for p in today_top %}<div class="lp"><div class="rk">{{ loop.index }}</div><div class="nm">{{ p.name }}</div><div class="du">{{ p.dur }}</div></div>{% endfor %}{% else %}<div class="none">今天还没有人上线哦～</div>{% endif %}
    <div class="sec-t" style="margin-top:16px">🏆 本周肝帝榜 TOP3</div>
    {% if week_top %}{% for p in week_top %}<div class="lp"><div class="rk">{{ loop.index }}</div><div class="nm">{{ p.name }}</div><div class="du">{{ p.dur }}</div></div>{% endfor %}{% else %}<div class="none">本周还没有在线记录～</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


PALDEX_TMPL = _HEAD + """
  .sk { display:flex; align-items:center; padding:8px 0; border-bottom:1px solid rgba(232,198,106,0.1); }
  .sk:last-child { border-bottom:none; }
  .sk .se { font-size:12px; font-weight:700; color:#2a1d05; background:linear-gradient(135deg,#ffe9a8,#e8c466); border-radius:6px; padding:2px 7px; margin-right:9px; }
  .sk .sn { flex:1; font-size:15px; font-weight:700; color:#f3ecd2; }
  .sk .sp { font-size:13px; color:#b9a9d6; font-weight:700; min-width:100px; text-align:right; }
</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    {% if icon %}<div style="flex:none;width:108px;height:108px;border-radius:20px;background:radial-gradient(circle at 50% 38%,rgba(232,198,106,.30),rgba(18,12,48,.55) 72%);border:2px solid rgba(232,198,106,.62);box-shadow:0 3px 15px rgba(0,0,0,.5),inset 0 0 18px rgba(232,198,106,.18);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:92px;height:92px;object-fit:contain;filter:drop-shadow(0 3px 8px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:72px">📕</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        <span class="pill soft">图鉴 #{{ index }}</span>
        {% for e in elements %}<span class="pill soft">{{ e }}</span>{% endfor %}
        <span class="pill soft">{{ "★" * (rarity if rarity <= 5 else 5) if rarity else "★" }}</span>
        {% if nocturnal %}<span class="pill soft">🌙 夜行</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% if desc %}<div style="font-size:13.5px;color:#b9a9d6;line-height:1.6;margin-bottom:14px">{{ desc }}</div>{% endif %}
    {% if egg or lv or price or cap %}<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">
      {% if egg %}<span class="pill soft">🥚 {{ egg }}</span>{% endif %}
      {% if lv %}<span class="pill soft">📈 刷新 {{ lv }}</span>{% endif %}
      {% if cap %}<span class="pill soft">🎯 捕获率 ×{{ cap }}</span>{% endif %}
      {% if price %}<span class="pill soft">💰 贩卖价 {{ price }}金币</span>{% endif %}
      {% if size %}<span class="pill soft">📏 体型 {{ size }}</span>{% endif %}
    </div>
    <div style="font-size:11px;color:#8a82a8;line-height:1.6;margin-bottom:12px">💰贩卖价＝把这只帕鲁卖给商人/帕鲁贩子得到的金币（非道具购买价，故「/帕鲁哪里买」查不到）　📈刷新＝野外出现的等级参考范围　📏体型＝帕鲁个头（XS最小 → XL最大，越大越占地、骑乘体感越壮）</div>{% endif %}
    <div class="sec-t">📊 基础数值</div>
    <div class="m3">
      <div class="tile tc"><div class="v gold">{{ hp }}</div><div class="k">生命</div></div>
      <div class="tile tc"><div class="v gold">{{ atk }}</div><div class="k">近战攻击</div></div>
      <div class="tile tc"><div class="v gold">{{ shot }}</div><div class="k">远程攻击</div></div>
    </div>
    <div class="m3" style="margin-top:8px">
      <div class="tile tc"><div class="v gold">{{ defense }}</div><div class="k">防御力</div></div>
      <div class="tile tc"><div class="v gold">{{ stamina }}</div><div class="k">耐力</div></div>
      <div class="tile tc"><div class="v gold">{{ food }}</div><div class="k">进食量</div></div>
    </div>
    <div class="m3" style="margin-top:8px">
      <div class="tile tc"><div class="v gold">{{ walk }}</div><div class="k">走路速度</div></div>
      <div class="tile tc"><div class="v gold">{{ run }}</div><div class="k">奔跑速度</div></div>
      <div class="tile tc"><div class="v gold">{{ ride }}</div><div class="k">骑乘速度</div></div>
    </div>
    {% if ranch %}<div class="sec-t" style="margin-top:16px">🐑 牧场产出</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px">{% for r in ranch %}<span class="pill soft" style="display:inline-flex;align-items:center;gap:6px">{% if r.icon %}<img src="{{ r.icon }}" style="width:22px;height:22px;object-fit:contain">{% endif %}{{ r.name }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:16px">⚔️ 主动技能</div>
    {% for s in skills %}<div class="sk">{% if s.elem %}<span class="se">{{ s.elem }}</span>{% endif %}<span class="sn">{{ s.name }}</span><span class="sp">威力 {{ s.power }} · CD {{ s.cd }}s</span></div>{% endfor %}
    {% if works %}<div class="sec-t" style="margin-top:16px">🔨 工作适性</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px">{% for w in works %}<span class="pill soft">{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}</div>{% endif %}
    {% if drops %}<div class="sec-t" style="margin-top:16px">🎁 掉落物品</div>
    {% for d in drops %}<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(232,198,106,0.1)">
      <span style="display:flex;align-items:center;gap:7px;font-size:14px;color:#f3ecd2">{% if d.icon %}<img src="{{ d.icon }}" style="width:26px;height:26px;object-fit:contain">{% endif %}{{ d.name }}</span>
      <span style="font-size:13px;color:#b9a9d6">{% if d.qty %}×{{ d.qty }} · {% endif %}{{ d.rate }}%</span></div>{% endfor %}{% endif %}
    {% if partner_title %}<div class="sec-t" style="margin-top:16px">🤝 伙伴技能</div>
    <div style="background:rgba(18,12,48,0.5);border:1px solid rgba(232,198,106,0.2);border-radius:14px;padding:12px 15px">
      <div style="font-size:15px;font-weight:800;color:#e8c466">{{ partner_title }}</div>
      <div style="font-size:13.5px;color:#b9a9d6;line-height:1.6;margin-top:5px">{{ partner_desc }}</div>
    </div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


BREED_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🧬 帕鲁配种</div>
    <div class="subtitle">亲代组合的后代</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:flex;align-items:center;justify-content:center;gap:10px;padding:6px 0 14px">
      <div class="tile" style="flex:1;max-width:150px;text-align:center;padding:15px 8px">
        {% if a.icon %}<img src="{{ a.icon }}" style="width:52px;height:52px;object-fit:contain;display:block;margin:0 auto 6px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.5))">{% endif %}
        <div style="font-size:18px;font-weight:800;color:#f3ecd2;word-break:break-word">{{ a.name }}</div>
        <div style="font-size:12px;color:#9c8fc0;margin-top:3px">#{{ a.index }}</div>
        <div style="margin-top:8px;display:flex;gap:5px;justify-content:center;flex-wrap:wrap">{% for e in a.elements %}<span class="pill soft" style="font-size:11px;padding:2px 9px">{{ e }}</span>{% endfor %}</div>
      </div>
      <div style="font-size:30px;font-weight:900;color:#e8c466;flex-shrink:0">＋</div>
      <div class="tile" style="flex:1;max-width:150px;text-align:center;padding:15px 8px">
        {% if b.icon %}<img src="{{ b.icon }}" style="width:52px;height:52px;object-fit:contain;display:block;margin:0 auto 6px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.5))">{% endif %}
        <div style="font-size:18px;font-weight:800;color:#f3ecd2;word-break:break-word">{{ b.name }}</div>
        <div style="font-size:12px;color:#9c8fc0;margin-top:3px">#{{ b.index }}</div>
        <div style="margin-top:8px;display:flex;gap:5px;justify-content:center;flex-wrap:wrap">{% for e in b.elements %}<span class="pill soft" style="font-size:11px;padding:2px 9px">{{ e }}</span>{% endfor %}</div>
      </div>
    </div>
    <div style="text-align:center;font-size:14px;color:#e8c466;font-weight:800;margin:4px 0 2px">═══ 后代 ═══</div>
    <div style="text-align:center;padding:8px 0 6px">
      {% if c.icon %}<img src="{{ c.icon }}" style="width:72px;height:72px;object-fit:contain;display:block;margin:0 auto 4px;filter:drop-shadow(0 3px 6px rgba(0,0,0,.55))">{% endif %}
      <div class="num-gold" style="font-size:30px">{{ c.name }}</div>
      <div style="font-size:13px;color:#9c8fc0;margin-top:4px">图鉴 #{{ c.index }} · {{ "★" * (c.rarity if c.rarity <= 5 else 5) if c.rarity else "★" }}</div>
      <div style="display:flex;gap:6px;justify-content:center;margin-top:10px">{% for e in c.elements %}<span class="pill gold" style="font-size:13px;padding:4px 13px">{{ e }}</span>{% endfor %}</div>
    </div>
    {% if child_breeds %}
    <div style="margin-top:12px;border-top:1px solid rgba(232,198,106,0.25);padding-top:12px">
      <div class="sec-t">🐣 用 {{ child_name }} 继续配</div>
      {% for cb in child_breeds %}
      <div style="display:flex;align-items:center;gap:7px;padding:6px 2px;font-size:14px">
        <span style="color:#c2b2dd;flex:1;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ child_name }} ＋ {{ cb.partner }}</span>
        <span style="color:#e8c466;flex-shrink:0">→</span>
        {% if cb.result_icon %}<img src="{{ cb.result_icon }}" style="width:30px;height:30px;object-fit:contain;flex-shrink:0">{% endif %}
        <b style="color:#f3ecd2;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ cb.result }}</b>
      </div>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


# ====================================================================
# 像素羊皮纸风格模板集(STYLES['pixel'])。低像素 + aged 羊皮纸 + 复古墨色。
# 中文像素字体 Zpix 经 CDN @font-face 加载(已验证渲染服务可加载)。
# 不使用插画 bg，羊皮纸纹理由 CSS+SVG 噪点生成，自包含。
# ====================================================================
_PIX_CSS = """
  @font-face { font-family:'Zpix'; src:url('https://cdn.jsdelivr.net/gh/SolidZORO/zpix-pixel-font/dist/Zpix.ttf') format('truetype'); }
  * { margin:0; padding:0; box-sizing:border-box;
      font-family:'Zpix','Microsoft YaHei','monospace'; }
  html { zoom:{{ zoom }}; } html,body { width:{{ cw|default(540) }}px; }
  body { display:flex; flex-direction:column; position:relative; color:#382207; image-rendering:pixelated;
    background-color:#cdae74;
    background-image:
      radial-gradient(ellipse at 24% 16%, rgba(120,80,30,0.16), transparent 52%),
      radial-gradient(ellipse at 80% 74%, rgba(80,50,18,0.22), transparent 55%),
      radial-gradient(circle at 62% 38%, rgba(70,45,16,0.10), transparent 38%),
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='150'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.09'/%3E%3C/svg%3E"),
      linear-gradient(160deg,#dcc089,#c9a866 55%,#b6924f); }
  body::after { content:""; position:absolute; inset:0; pointer-events:none; z-index:1;
    box-shadow: inset 0 0 64px 16px rgba(60,35,12,0.34), inset 0 0 16px 4px rgba(28,16,5,0.38); }
  .page { position:relative; z-index:2; min-height:300px; flex:1 1 auto; display:flex; flex-direction:column; justify-content:flex-start; padding:28px 20px 22px; }
  /* 内容偏少时让主面板撑满 .page 剩余高度，避免主题框下方露出空背景(footer 被顶到底部) */
  .page > .frame:last-of-type, .page > .glass:last-of-type { flex:1 1 auto; }
  .head { margin-bottom:14px; display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
  .title { color:#46200a; font-size:21px; letter-spacing:1px; line-height:1.3;
    text-shadow:1px 1px 0 rgba(224,200,145,0.85); display:flex; align-items:center; gap:8px; }
  .title .nm { max-width:320px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .subtitle { color:#523f10; font-size:13px; margin-top:6px; display:flex; gap:7px; flex-wrap:wrap; align-items:center; }
  .badge { flex-shrink:0; font-size:13px; padding:5px 12px; color:#3a2410;
    background:#caa860; border:2px solid #5a3a1e; box-shadow:2px 2px 0 rgba(50,30,12,0.4); }
  .badge.on { background:#7c8a46; color:#fff3d0; }
  .badge.off { background:#9a5a4a; color:#fff0e0; }
  .frame { position:relative; margin-bottom:13px; padding:18px;
    background:rgba(236,214,164,0.62);
    border:3px solid #5a3a1e;
    box-shadow: inset 0 0 0 2px #b6843a, inset 0 0 0 5px rgba(90,58,30,0.35), 3px 4px 0 rgba(48,28,10,0.45); }
  .sec-t { color:#7a3604; font-size:14px; letter-spacing:1px; margin:2px 0 11px;
    border-bottom:2px solid rgba(90,58,30,0.4); padding-bottom:6px; }
  .gold { color:#9c6b1a; }
  .ink { color:#8f1212; }
  .m3 { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
  .m2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .tile { background:rgba(221,198,149,0.58); border:2px solid #6a4524; box-shadow:inset 0 0 0 1px rgba(199,154,78,0.5); }
  .tc { text-align:center; padding:13px 5px; }
  .tc .i { font-size:19px; margin-bottom:5px; }
  .tc .v { color:#8f1212; font-size:23px; line-height:1.1; word-break:break-all; text-shadow:1px 1px 0 rgba(224,200,145,0.6); }
  .tc .k { color:#574012; font-size:12px; margin-top:4px; }
  .row { display:flex; align-items:center; padding:10px 11px; margin-bottom:8px;
    background:rgba(223,200,151,0.52); border:2px solid #6a4524; }
  .pill { display:inline-block; font-size:12px; padding:2px 9px; color:#3a2410;
    background:#caa860; border:2px solid #6a4524; }
  .pill.red { background:#9a4636; color:#fff0e0; }
  .num-big { color:#8f1212; line-height:1; text-shadow:2px 2px 0 rgba(199,154,78,0.55); }
  .bar { height:13px; background:rgba(60,40,15,0.34); border:2px solid #5a3a1e; overflow:hidden; }
  .barf { height:100%; background:#7c8a46; }
  .barf.hot { background:#9a3a2a; }
  .footer { text-align:center; color:#6a5230; font-size:12px; padding-top:14px;
    border-top:2px solid rgba(90,58,30,0.35); margin-top:auto; }
  .footer span { color:#8f1212; }
  .empty { flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center; padding:46px 24px; text-align:center; }
  .empty .ee { font-size:60px; margin-bottom:12px; }
  .empty .et { font-size:19px; color:#46200a; }
  .empty .ed { font-size:13px; color:#523f10; margin-top:8px; }
"""

_PH = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>""" + _PIX_CSS
_PF = '<footer class="footer">[ {{ now }} · <span>大狸猫 · 帕鲁服务器管家</span> ]</footer>'


STATUS_PIX = _PH + """</style></head><body><div class="page">
  <div class="head">
    <div>
      <div class="title">▰ <span class="nm">{{ servername }}</span></div>
      <div class="subtitle">v {{ version }}</div>
    </div>
    <span class="badge {{ 'on' if online else 'off' }}">{{ '● 在线' if online else '○ 离线' }}</span>
  </div>
  <div class="frame">
    <div style="text-align:center">
      <div style="color:#523f10;font-size:13px;letter-spacing:2px">- 当前在线人数 -</div>
      <div style="margin-top:6px"><span class="num-big" style="font-size:62px">{{ cur }}</span><span style="font-size:30px;color:#8a6a3a"> / {{ maxn }}</span><span style="font-size:14px;color:#8a6a3a"> 人</span></div>
    </div>
    <div class="m3" style="margin-top:16px">
      <div class="tile tc"><div class="i">⚡</div><div class="v">{{ fps }}</div><div class="k">服务器FPS</div></div>
      <div class="tile tc"><div class="i">📅</div><div class="v">{{ days }}</div><div class="k">游戏天数</div></div>
      <div class="tile tc"><div class="i">⏳</div><div class="v">{{ uptime }}</div><div class="k">运行时长</div></div>
    </div>
    {% if players %}
    <div class="sec-t" style="margin-top:15px">在线玩家</div>
    {% for p in players %}
    <div class="row" style="padding:8px 10px">
      <div style="flex:1;min-width:0;font-size:14px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ p.name }}</div>
      <span class="pill" style="font-size:10px;margin:0 6px">Lv.{{ p.level }}</span>
      {% if p.dur %}<span style="font-size:11px;color:#523f10;margin-right:6px">{{ p.dur }}</span>{% endif %}
      <span class="pill" style="background:{{ p.ping_color }};color:#fff;font-size:10px">{{ p.ping }}ms</span>
    </div>
    {% endfor %}
    {% endif %}
    {% if load %}
    <div style="margin-top:16px">
      <div class="sec-t">◆ 服务器负载</div>
      <div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;color:#574012;font-size:13px;margin-bottom:5px"><span>CPU</span><span class="ink">{{ load.cpu }}%</span></div><div class="bar"><div class="barf {{ 'hot' if load.cpu_bar>=80 else '' }}" style="width:{{ load.cpu_bar }}%"></div></div></div>
      <div><div style="display:flex;justify-content:space-between;color:#574012;font-size:13px;margin-bottom:5px"><span>内存</span><span class="ink">{{ load.mem_text }} · {{ load.mem_pct }}%</span></div><div class="bar"><div class="barf {{ 'hot' if load.mem_bar>=80 else '' }}" style="width:{{ load.mem_bar }}%"></div></div></div>
    </div>
    {% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


PLAYERS_PIX = _PH + """</style></head><body><div class="page">
  <div class="head">
    <div><div class="title">▣ 在线玩家</div><div class="subtitle">实时帕鲁岛冒险者名单</div></div>
    <span class="badge">{{ count }} 人在线</span>
  </div>
  {% if not players %}
  <div class="frame" style="flex:1;display:flex"><div class="empty"><div class="ee">🏝</div><div class="et">暂无玩家在线</div><div class="ed">帕鲁岛静悄悄～快喊小伙伴上线！</div></div></div>
  {% else %}
  <div class="frame">
    {% for p in players %}
    <div class="row">
      <div style="width:26px;height:26px;flex-shrink:0;background:#caa860;border:2px solid #6a4524;color:#46200a;font-size:13px;display:flex;align-items:center;justify-content:center;margin-right:11px">{{ loop.index }}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:16px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:250px">{{ p.name }}</div>
        <span class="pill" style="margin-top:5px;font-size:11px">Lv.{{ p.level }}</span>
      </div>
      <span class="pill" style="background:{{ p.ping_color }};color:#fff;min-width:58px;text-align:center">{{ p.ping }}ms</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  """ + _PF + """
</div></body></html>"""


SETTINGS_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div><div class="title">⚙ 服务器设置</div><div class="subtitle">当前帕鲁世界规则与倍率</div></div></div>
  <div class="frame">
    <div class="m2">
      {% for it in items %}
      <div class="tile" style="padding:12px 14px">
        <div style="font-size:12px;color:#523f10;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ it.k }}</div>
        <div style="font-size:18px;color:#8f1212;margin-top:4px;word-break:break-word">{{ it.v }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  """ + _PF + """
</div></body></html>"""


HELP_PIX = _PH + """
  .cmd { display:inline-block; width:49%; box-sizing:border-box; vertical-align:top; padding:6px 4px; }
  .cmd .c { display:block; font-size:13px; color:#46200a; }
  .cmd .c b { color:#fff3d0; background:#7a3604; padding:2px 7px; border:2px solid #5a3a1e; }
  .cmd .d { display:block; font-size:11px; color:#523f10; margin-top:3px; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">▤ 帕鲁指令帮助</div><div class="subtitle">指令一行一条，看清楚再发</div></div></div>
  <div class="frame">
    <div class="sec-t">查询（所有人可用）</div>
    <div class="cmd"><div class="c"><b>/帕鲁</b></div><div class="d">查看服务器状态</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁在线</b></div><div class="d">查看在线玩家列表</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁设置</b></div><div class="d">查看服务器倍率与规则</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁统计</b></div><div class="d">今日峰值/平均 + 近7日趋势</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁热力</b></div><div class="d">7×24 在线热力图·看高峰时段</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁战力榜</b></div><div class="d">全服最强帕鲁排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁闪光墙</b></div><div class="d">全服闪光帕鲁收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁头目墙</b></div><div class="d">全服头目(Alpha)收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁图鉴榜</b></div><div class="d">全服图鉴收集进度排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁资产榜</b></div><div class="d">全服帕鲁身价排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会战力</b></div><div class="d">各公会战力总和排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁更新公告</b></div><div class="d">官方最新更新公告(中文)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁肝帝榜</b></div><div class="d">本周在线时长排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁图鉴</b> [名/字]</div><div class="d">详情/模糊列表/翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁编号</b> 13B</div><div class="d">按编号查(支持变种)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁配种</b> 亲A 亲B</div><div class="d">查后代+子代继续配</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁反配种</b> 名</div><div class="d">能配成它的组合</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁怎么配</b> 名</div><div class="d">用现有帕鲁算配种路线</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁继承</b> 词条A｜词条B</div><div class="d">算后代继承词条概率</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁哪里掉</b> 物品</div><div class="d">查哪些帕鲁掉该物品</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁物品</b> [名/类]</div><div class="d">详情/分类/翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁设施</b> [名/字]</div><div class="d">详情/模糊列表/翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁科技</b> [名/字]</div><div class="d">详情/模糊列表/翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁研究所</b> [类/名]</div><div class="d">🆕 全局增益研究/9适性/材料</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁栖息区域</b> 帕鲁名</div><div class="d">地图上涂出刷新热区</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁推荐词条</b> 帕鲁名</div><div class="d">按角色推荐词条</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁属性克制</b></div><div class="d">九系属性克制图</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁主线</b> [页]</div><div class="d">主线任务列表(剧情序)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁支线</b> [NPC]</div><div class="d">支线任务(可筛选NPC)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁任务</b> 任务名</div><div class="d">任务详细攻略</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁塔主</b> [名]</div><div class="d">高塔塔主数据/攻略</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁突袭</b> [名]</div><div class="d">突袭Boss数据/打法</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁竞技场</b> [段位]</div><div class="d">对手阵容/段位奖励</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁商人</b> [名]</div><div class="d">商店卖什么+价格</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁哪里买</b> 物品</div><div class="d">物品在哪买/多少钱</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁技能</b> 名/属性</div><div class="d">技能威力/冷却/效果</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁技能果实</b> [属性/名]</div><div class="d">🆕 92种果实图鉴/带图标</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁植入体</b> [名]</div><div class="d">🆕 68种·改造帕鲁词条</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁钓鱼</b></div><div class="d">钓鱼可获得物+概率</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁工作</b> 工种</div><div class="d">工种最强帕鲁排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁坐骑</b></div><div class="d">坐骑奔跑速度榜</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁对比</b> A B</div><div class="d">两帕鲁数值对比</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁料理</b> [效果]</div><div class="d">增益料理一览</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁武器</b> [名]</div><div class="d">武器攻击力/科技/弹药</div></div>
  </div>
  <div class="frame">
    <div class="sec-t">玩家自助（所有人可用）</div>
    <div class="cmd"><div class="c"><b>/帕鲁绑定</b> 游戏名</div><div class="d">绑定你的帕鲁角色</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁我</b></div><div class="d">个人档案·等级/技术点/队伍/背包</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁背包</b></div><div class="d">查看自己的背包物品明细</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁队伍</b></div><div class="d">查看自己出战帕鲁的面板</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁箱</b> [页]</div><div class="d">帕鲁箱全部帕鲁·翻页</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁可孵化</b></div><div class="d">用你箱里的帕鲁能配出哪些新帕鲁</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁据点</b></div><div class="d">据点帕鲁：工作/适性/血量/SAN/伤病</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁症状</b> [状态]</div><div class="d">伤病治疗速查(骨折/濒死/低SAN…)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会帕鲁</b> [页]</div><div class="d">公会终端：全公会成员帕鲁汇总</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁箱查询</b> 编号</div><div class="d">看帕鲁箱某只的详细面板</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会</b></div><div class="d">查看自己公会的成员/会长</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会榜</b></div><div class="d">公会在线时长排行榜</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁订阅</b> 游戏名</div><div class="d">某玩家上线时 @ 你</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁找人</b> 游戏名</div><div class="d">查某玩家是否在线</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁喊话</b> 内容</div><div class="d">把话广播到游戏内</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁喊</b> 游戏名</div><div class="d">@绑定玩家喊TA上线</div></div>
  </div>
  <div class="frame">
    <div class="sec-t">管理（仅管理员）</div>
    <div class="cmd"><div class="c"><b>/帕鲁公告</b> 内容</div><div class="d">向服务器广播公告</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁踢/封/解封</b></div><div class="d">踢出/封禁/解封玩家</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁存档</b></div><div class="d">立即保存世界存档</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁关服</b> 秒</div><div class="d">定时关服（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁重启服务器</b></div><div class="d">存档后重启（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁备份列表</b></div><div class="d">查看所有自动备份</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁回档</b> 编号</div><div class="d">回档到指定备份（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁重置存档</b></div><div class="d">删档重开（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁恢复存档</b></div><div class="d">还原上一次重置（需确认）</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁审计</b></div><div class="d">最近管理操作记录</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁自检</b></div><div class="d">一键体检配置/连接/存档/渲染</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁地图</b></div><div class="d">在线玩家世界地图</div></div>
  </div>
  """ + _PF + """
</div></body></html>"""


MSG_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div><div class="title">{{ head }}</div></div></div>
  <div class="frame" style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:36px 26px">
    <div style="font-size:66px;line-height:1;margin-bottom:16px">{{ icon }}</div>
    <div style="font-size:25px;color:{{ color }};line-height:1.35;word-break:break-word">{{ title }}</div>
    {% if desc %}<div style="margin-top:16px;font-size:15px;line-height:1.7;color:#574012;white-space:pre-line;word-break:break-word;background:rgba(221,198,149,0.58);border:2px solid #6a4524;padding:14px 16px;text-align:left;max-width:400px">{{ desc }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


STATS_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div><div class="title">▦ 在线统计</div><div class="subtitle">今日数据与近 7 日在线峰值</div></div></div>
  <div class="frame">
    <div class="m3">
      <div class="tile tc"><div class="v">{{ peak }}</div><div class="k">今日峰值</div></div>
      <div class="tile tc"><div class="v">{{ avg }}</div><div class="k">今日平均</div></div>
      <div class="tile tc"><div class="v">{{ cur }}</div><div class="k">当前在线</div></div>
    </div>
    <div class="sec-t" style="margin-top:16px">近 7 日在线峰值</div>
    <div style="display:flex;align-items:flex-end;gap:8px;height:165px;padding:4px 2px 0">
      {% for d in days %}
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%">
        <div style="font-size:12px;color:#8f1212;margin-bottom:4px">{{ d.peak }}</div>
        <div style="width:78%;min-height:4px;height:{{ d.h }}%;background:#7c8a46;border:2px solid #5a3a1e"></div>
        <div style="font-size:10px;color:#523f10;margin-top:6px">{{ d.label }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  """ + _PF + """
</div></body></html>"""


RANK_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div><div class="title">♛ {{ (rank_title | default('本周肝帝榜')).replace('🏆 ','').replace('🏆','') }}</div><div class="subtitle">{{ rank_sub | default('本周在线时长排行 · 看谁最肝') }}</div></div></div>
  {% if not rows %}
  <div class="frame" style="flex:1;display:flex"><div class="empty"><div class="ee">💤</div><div class="et">本周还没有在线记录</div><div class="ed">玩起来！时长会自动统计上榜</div></div></div>
  {% else %}
  <div class="frame">
    {% for r in rows %}
    <div class="row" {% if loop.index <= 3 %}style="background:rgba(199,154,78,0.32);border-color:#8a5a1e"{% endif %}>
      <div style="width:30px;flex-shrink:0;text-align:center;font-size:17px;color:#8f1212;margin-right:9px">{{ loop.index }}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.online %} <span style="color:#5a7a2a">[在线]</span>{% endif %}</div>
        <div class="bar" style="margin-top:6px;height:10px"><div class="barf" style="width:{{ r.pct }}%"></div></div>
      </div>
      <div style="flex-shrink:0;margin-left:11px;font-size:15px;color:#8f1212">{{ r.dur }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  """ + _PF + """
</div></body></html>"""


PROFILE_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div><div class="title">☻ 我的帕鲁档案</div><div class="subtitle">绑定角色的在线数据</div></div></div>
  <div class="frame">
    <div style="text-align:center;padding:4px 0 14px">
      {% if avatar %}<div style="width:90px;height:90px;margin:0 auto;border:3px solid #6a4524;background:#caa860;padding:3px"><img src="{{ avatar }}" style="width:100%;height:100%;object-fit:cover;display:block;image-rendering:auto"></div>
      {% else %}<div style="font-size:54px;line-height:1">{% if online %}🧑{% else %}💤{% endif %}</div>{% endif %}
      <div style="font-size:24px;color:#46200a;margin-top:8px;word-break:break-word">{{ name }}</div>
      <span class="badge {{ 'on' if online else 'off' }}" style="margin-top:11px;display:inline-block">{% if online %}● 在线 Lv.{{ level }}{% else %}○ 离线{% endif %}</span>
      {% if titles %}<div style="margin-top:12px;display:flex;flex-wrap:wrap;gap:7px;justify-content:center">{% for t in titles %}<span class="pill">{{ t }}</span>{% endfor %}</div>{% endif %}
    </div>
    <div class="m3">
      <div class="tile tc"><div class="v">{{ week_dur }}</div><div class="k">本周在线</div></div>
      <div class="tile tc"><div class="v">{{ total_dur }}</div><div class="k">累计在线</div></div>
      <div class="tile tc"><div class="v">{{ rank }}</div><div class="k">本周排名</div></div>
    </div>
    {% if has_save %}
    <div class="sec-t" style="margin-top:16px">存档实况</div>
    <div class="m3">
      <div class="tile tc"><div class="v">Lv.{{ s_level }}</div><div class="k">角色等级</div></div>
      <div class="tile tc"><div class="v">{{ tech }}</div><div class="k">技术点</div></div>
      <div class="tile tc"><div class="v">{{ recipes }}</div><div class="k">解锁配方</div></div>
    </div>
    <div class="m3" style="margin-top:10px">
      <div class="tile tc"><div class="v" style="color:#8f1212">{{ max_hp }}</div><div class="k">最大生命</div></div>
      <div class="tile tc"><div class="v" style="color:#1f5f7a">{{ max_sp }}</div><div class="k">最大耐力</div></div>
      <div class="tile tc"><div class="v" style="color:#7a5a1a">{{ weight }}</div><div class="k">负重上限</div></div>
    </div>
    <div class="m3" style="margin-top:10px">
      <div class="tile tc"><div class="v" style="color:#2f7a3a">{{ hp|int }}</div><div class="k">当前生命</div></div>
      <div class="tile tc"><div class="v">{{ shield|int }}</div><div class="k">护盾值</div></div>
      <div class="tile tc"><div class="v">{{ stomach|int }}</div><div class="k">饱食度</div></div>
    </div>
    <div class="m3" style="margin-top:10px">
      <div class="tile tc"><div class="v">{{ pal_total }}</div><div class="k">帕鲁总数</div></div>
      <div class="tile tc"><div class="v">{{ dex_owned }}<span style="font-size:13px;color:#9a8a6a">/{{ dex_total }}</span></div><div class="k">图鉴收集</div></div>
      <div class="tile tc"><div class="v" style="{% if hurt_n %}color:#c0291f{% endif %}">{{ hurt_n }}</div><div class="k">受伤帕鲁</div></div>
    </div>
    {% if status %}
    <div class="sec-t" style="margin-top:15px">状态点强化</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
      {% for s in status %}
      <div style="display:flex;justify-content:space-between;align-items:baseline;background:rgba(221,198,149,0.58);border:2px solid #6a4524;padding:6px 9px">
        <span style="font-size:12px;color:#574012">{{ s.name }}</span>
        <span style="font-size:14px;color:{% if s.points %}#8f1212{% else %}#9a8a6a{% endif %}">+{{ s.points }}</span>
      </div>
      {% endfor %}
    </div>
    {% endif %}
    {% if party %}
    <div class="sec-t" style="margin-top:15px">出战队伍 · {{ party_n }} 只</div>
    <div style="display:flex;flex-wrap:wrap;gap:9px;justify-content:center">
      {% for p in party %}
      <div style="display:flex;flex-direction:column;align-items:center;width:78px">
        <div style="position:relative;width:62px;height:62px;background:rgba(214,184,124,.3);border:2px solid #6b4a24;display:flex;align-items:center;justify-content:center">
          {% if p.icon %}<img src="{{ p.icon }}" style="width:52px;height:52px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:28px">▥</span>{% endif %}
          {% if p.lucky %}<span style="position:absolute;top:-7px;right:-5px;font-size:15px">✨</span>{% elif p.alpha %}<span style="position:absolute;top:-7px;right:-5px;font-size:14px">♛</span>{% endif %}
        </div>
        <div style="font-size:12px;color:#46200a;margin-top:4px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:78px">{{ p.name }}</div>
        <div style="font-size:11px;color:#8f1212">Lv.{{ p.level }}</div>
      </div>
      {% endfor %}
    </div>
    {% endif %}
    <div style="margin-top:13px;font-size:13px;color:#574012;line-height:1.7">背包 {{ bag_n }} 种物品，发 /帕鲁背包 看明细；帕鲁箱 {{ palbox_n }} 只，发 /帕鲁箱 浏览{% if party %}；发 /帕鲁队伍 看出战面板{% endif %}</div>
    {% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


BAG_TMPL = _HEAD + """
  .bgrid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
  .bcell { background:rgba(18,12,48,.5); border:1px solid rgba(232,198,106,.2); border-radius:13px; padding:11px 6px 9px; text-align:center; position:relative; }
  .bcell img { width:46px; height:46px; object-fit:contain; }
  .bcell .ph { font-size:26px; line-height:46px; }
  .bcell .bn { font-size:12px; color:#cfc1ea; margin-top:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bcell .bc { position:absolute; top:5px; right:6px; font-size:12px; font-weight:900; color:#2a1d05; background:linear-gradient(135deg,#ffe9a8,#e8c466); border-radius:8px; padding:1px 6px; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">🎒 {{ name }} 的背包</div><div class="subtitle">共 {{ total }} 种物品{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 背包/装备/饰品栏</div></div></div>
  <div class="glass">""" + _GEMS + """
    {% if cells %}<div class="bgrid">
    {% for c in cells %}<div class="bcell"><span class="bc">×{{ c.count }}</span>{% if c.icon %}<img src="{{ c.icon }}">{% else %}<div class="ph">📦</div>{% endif %}<div class="bn">{{ c.name }}</div></div>{% endfor %}
    </div>{% else %}<div style="color:#9c8fc0;text-align:center;padding:24px">背包空空如也～</div>{% endif %}
    {% if pager %}<div style="margin-top:14px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

BAG_PIX = _PH + """
  .bgrid { display:grid; grid-template-columns:repeat(4,1fr); gap:9px; }
  .bcell { background:rgba(214,184,124,.3); border:2px solid #6b4a24; padding:10px 5px 8px; text-align:center; position:relative; }
  .bcell img { width:44px; height:44px; object-fit:contain; image-rendering:pixelated; }
  .bcell .ph { font-size:24px; line-height:44px; }
  .bcell .bn { font-size:12px; color:#46200a; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bcell .bc { position:absolute; top:2px; right:3px; font-size:11px; color:#3a2410; background:#caa860; border:2px solid #6a4524; padding:0 5px; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">☷ {{ name }} 的背包</div><div class="subtitle">共 {{ total }} 种物品{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 背包/装备/饰品栏</div></div></div>
  <div class="frame">
    {% if cells %}<div class="bgrid">
    {% for c in cells %}<div class="bcell"><span class="bc">×{{ c.count }}</span>{% if c.icon %}<img src="{{ c.icon }}">{% else %}<div class="ph">▦</div>{% endif %}<div class="bn">{{ c.name }}</div></div>{% endfor %}
    </div>{% else %}<div style="color:#523f10;text-align:center;padding:24px">背包空空如也～</div>{% endif %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:13px;color:#46200a;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:8px 11px">▶ {{ pager }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""

PALBOX_TMPL = _HEAD + """
  .pbgrid { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
  .pbc { position:relative; border:1.5px solid rgba(232,198,106,.2); border-radius:13px; padding:9px 4px 7px; text-align:center; }
  .pbc img { width:54px; height:54px; object-fit:contain; }
  .pbc .ph { font-size:30px; line-height:54px; }
  .pbc .pn { font-size:12px; color:#ece3f7; margin-top:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .pbc .pl { font-size:11px; color:#e8c466; font-weight:700; }
  .pbc .bdg { position:absolute; top:-6px; right:-4px; font-size:15px; }
  .pbc .num { position:absolute; top:4px; left:5px; font-size:10px; font-weight:800; color:#0d0820; background:linear-gradient(135deg,#f3d98a,#e8c66a); border-radius:6px; padding:0 5px; z-index:2; }
  .pbc .hb { display:inline-block; margin-top:3px; font-size:10px; font-weight:800; border-radius:6px; padding:0 6px; line-height:15px; }
  .hb-bad { background:linear-gradient(135deg,#ff6a6a,#d42c2c); color:#fff; }
  .hb-warn { background:linear-gradient(135deg,#ffb24a,#e07a1a); color:#3a1d00; }
  .pbc.hurt { box-shadow:0 0 0 2px #ff5a5a inset, 0 0 10px rgba(255,80,80,.4); }
  .pbc { border-width:2px; }
  .rt-common { background:rgba(92,104,130,.62); border-color:rgba(158,170,196,.85); }
  .rt-uncommon { background:rgba(36,116,228,.60); border-color:rgba(110,188,255,.95); }
  .rt-rare { background:rgba(150,66,238,.58); border-color:rgba(204,150,255,.95); }
  .rt-epic { background:linear-gradient(160deg,rgba(242,182,48,.62),rgba(176,114,18,.44)); border-color:rgba(255,218,110,1); box-shadow:0 0 12px rgba(242,184,60,.55); }
  .rt-legend { background:linear-gradient(160deg,rgba(250,66,66,.62),rgba(218,44,152,.46)); border-color:rgba(255,124,124,1); box-shadow:0 0 13px rgba(250,66,66,.55); }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">📦 {{ name }} 的帕鲁箱</div><div class="subtitle">共 {{ total }} 只 · 第 {{ page }}/{{ pages }} 页 · 发「/帕鲁箱查询 编号」看详情</div></div></div>
  <div class="glass">""" + _GEMS + """
    {% if cells %}<div class="pbgrid">
    {% for c in cells %}<div class="pbc rt-{{ c.rtier }}{% if c.health.hurt %} hurt{% endif %}">
      <span class="num">{{ c.no }}</span>
      {% if c.lucky %}<span class="bdg">✨</span>{% elif c.alpha %}<span class="bdg">👑</span>{% endif %}
      {% if c.icon %}<img src="{{ c.icon }}">{% else %}<div class="ph">🐾</div>{% endif %}
      <div class="pn">{{ c.name }}</div><div class="pl">Lv.{{ c.level }}{% if c.condense %} <span style="color:#ffd34d">{{ "★"*c.condense }}</span>{% endif %}</div>
      {% if c.health.hurt %}<div class="hb hb-{{ c.health.tone }}">{{ c.health.label }}</div>{% endif %}
    </div>{% endfor %}
    </div>{% else %}<div style="color:#9c8fc0;text-align:center;padding:24px">帕鲁箱空空如也～</div>{% endif %}
    {% if pager %}<div style="margin-top:14px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

PALBOX_PIX = _PH + """
  .pbgrid { display:grid; grid-template-columns:repeat(4,1fr); gap:9px; }
  .pbc { position:relative; border:2px solid #6b4a24; padding:8px 4px 6px; text-align:center; }
  .pbc img { width:52px; height:52px; object-fit:contain; image-rendering:pixelated; }
  .pbc .ph { font-size:28px; line-height:52px; }
  .pbc .pn { font-size:12px; color:#46200a; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .pbc .pl { font-size:11px; color:#8f1212; }
  .pbc .bdg { position:absolute; top:-7px; right:-3px; font-size:14px; }
  .pbc .num { position:absolute; top:2px; left:3px; font-size:10px; color:#3a2410; background:#e8c66a; border:2px solid #6a4524; padding:0 4px; z-index:2; }
  .pbc .hb { display:inline-block; margin-top:2px; font-size:10px; color:#fff; border:2px solid #6a4524; padding:0 5px; line-height:14px; }
  .hb-bad { background:#d42c2c; }
  .hb-warn { background:#e07a1a; color:#3a1d00; }
  .pbc.hurt { outline:2px solid #d42c2c; outline-offset:-4px; }
  .rt-common { background:rgba(150,158,176,.72); border-color:#566078; }
  .rt-uncommon { background:rgba(84,158,234,.75); border-color:#234f86; }
  .rt-rare { background:rgba(176,112,228,.72); border-color:#52257e; }
  .rt-epic { background:rgba(242,196,76,.82); border-color:#8a6212; }
  .rt-legend { background:rgba(238,88,88,.78); border-color:#7e2222; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">☷ {{ name }} 的帕鲁箱</div><div class="subtitle">共 {{ total }} 只 · 第 {{ page }}/{{ pages }} 页 · 发「/帕鲁箱查询 编号」看详情</div></div></div>
  <div class="frame">
    {% if cells %}<div class="pbgrid">
    {% for c in cells %}<div class="pbc rt-{{ c.rtier }}{% if c.health.hurt %} hurt{% endif %}">
      <span class="num">{{ c.no }}</span>
      {% if c.lucky %}<span class="bdg">✨</span>{% elif c.alpha %}<span class="bdg">♛</span>{% endif %}
      {% if c.icon %}<img src="{{ c.icon }}">{% else %}<div class="ph">▥</div>{% endif %}
      <div class="pn">{{ c.name }}</div><div class="pl">Lv.{{ c.level }}{% if c.condense %} <span style="color:#b06a00">{{ "★"*c.condense }}</span>{% endif %}</div>
      {% if c.health.hurt %}<div class="hb hb-{{ c.health.tone }}">{{ c.health.label }}</div>{% endif %}
    </div>{% endfor %}
    </div>{% else %}<div style="color:#523f10;text-align:center;padding:24px">帕鲁箱空空如也～</div>{% endif %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:13px;color:#46200a;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:8px 11px">▶ {{ pager }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""

# ---------------- 据点工作帕鲁（/帕鲁据点） ----------------
BASECAMP_TMPL = _HEAD + """
  .wk { display:flex; align-items:center; gap:11px; padding:9px 2px; border-bottom:1px solid rgba(232,198,106,.1); }
  .wk:last-child { border-bottom:none; }
  .wk .wpic { flex:none; width:50px; height:50px; border-radius:12px; background:rgba(18,12,48,.5); border:1px solid rgba(232,198,106,.28); display:flex; align-items:center; justify-content:center; position:relative; }
  .wk .wpic img { width:42px; height:42px; object-fit:contain; }
  .wtag { font-size:11px; color:#2a1d05; background:linear-gradient(135deg,#bfe9c0,#7fd089); border-radius:6px; padding:1px 7px; }
  .hpill { font-size:11px; font-weight:800; border-radius:6px; padding:1px 7px; }
  .cure { margin-top:8px; border-left:3px solid rgba(232,198,106,.55); background:rgba(99,102,241,.12); border-radius:0 10px 10px 0; padding:8px 11px; display:flex; flex-direction:column; gap:8px; }
  .cure .ct { display:flex; flex-direction:column; gap:4px; }
  .cure .cs { font-size:12.5px; font-weight:800; color:#ffce6b; letter-spacing:.3px; }
  .cure .cd { font-size:11.5px; color:#cfc1ea; line-height:1.55; }
  .cure .cwrap { display:flex; flex-wrap:wrap; gap:8px; margin-top:2px; }
  .cure .citem { display:flex; align-items:center; gap:5px; background:rgba(18,12,48,.42); border:1px solid rgba(232,198,106,.26); border-radius:9px; padding:2px 9px 2px 3px; }
  .cure .citem img { width:34px; height:34px; object-fit:contain; }
  .cure .citem .cph { width:34px; height:34px; display:flex; align-items:center; justify-content:center; font-size:20px; }
  .cure .citem span { font-size:11px; color:#f3ecd2; font-weight:600; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">🏕️ {{ name }} 的据点帕鲁</div><div class="subtitle">据点工作帕鲁状态{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 数据来自存档</div></div></div>
  <div class="glass">""" + _GEMS + """
    <div class="m3" style="margin-bottom:14px">
      <div class="tile tc"><div class="v gold">{{ total }}</div><div class="k">工作帕鲁</div></div>
      <div class="tile tc"><div class="v gold" style="{% if hurt %}color:#ff7a7a{% endif %}">{{ hurt }}</div><div class="k">受伤</div></div>
      <div class="tile tc"><div class="v gold" style="{% if hungry %}color:#ffce6b{% endif %}">{{ hungry }}</div><div class="k">饥饿</div></div>
    </div>
    {% if cells %}
    {% for c in cells %}
    <div class="wk">
      <div class="wpic">{% if c.icon %}<img src="{{ c.icon }}">{% else %}<span style="font-size:26px">🐾</span>{% endif %}
        {% if c.lucky %}<span style="position:absolute;top:-6px;right:-5px;font-size:14px">✨</span>{% elif c.alpha %}<span style="position:absolute;top:-6px;right:-5px;font-size:13px">👑</span>{% endif %}</div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">
          <span style="font-size:15px;font-weight:800;color:#f3ecd2">{{ c.name }}</span>
          <span style="font-size:12px;color:#e8c466;font-weight:700">Lv.{{ c.level }}</span>
          {% for e in c.elements %}<span style="font-size:10.5px;color:#cfc1ea;background:rgba(99,102,241,.18);border-radius:5px;padding:0 6px">{{ e }}</span>{% endfor %}
          {% if c.health.hurt %}<span class="hpill" style="background:{% if c.health.tone=='bad' %}#d42c2c{% else %}#e07a1a{% endif %};color:#fff">⚠{{ c.health.label }}</span>{% endif %}
          {% if c.starving %}<span class="hpill" style="background:#e0a01a;color:#3a1d00">🍖饥饿</span>{% endif %}
          {% if c.low_san %}<span class="hpill" style="background:#c05bd0;color:#fff">🧠理智低</span>{% endif %}
        </div>
        <div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:11px;font-size:12px;color:#cfc1ea">
          <span>{% if c.working %}⛏️ 正在{{ c.current_work }}{% else %}💤 {{ c.current_work }}{% endif %}</span>
          <span style="{% if c.max_hp and c.hp_pct < 40 %}color:#ff9a9a{% endif %}">❤ {{ c.hp }}{% if c.max_hp %}/{{ c.max_hp }}{% endif %}</span>
          <span style="{% if c.starving %}color:#ffce6b{% endif %}">🍖 {{ c.stomach }}%</span>
          <span style="{% if c.low_san %}color:#ff9a9a{% endif %}">🧠 SAN {{ c.sanity }}</span>
        </div>
        <div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px;align-items:center">
          {% if c.works %}{% for w in c.works %}<span class="wtag">{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}{% else %}<span style="font-size:11px;color:#9c8fc0">无基地工作适性</span>{% endif %}
        </div>
        {% if c.cure_tips %}
        <div class="cure">
          {% for t in c.cure_tips %}
          <div class="ct">
            <div class="cs">💊 {{ t.symptom }}</div>
            <div class="cd">{{ t.desc }}</div>
            {% if t.drugs %}<div class="cwrap">
              {% for it in t.drugs %}<div class="citem">{% if it.icon %}<img src="{{ it.icon }}">{% else %}<span class="cph">💊</span>{% endif %}<span>{{ it.name }}</span></div>{% endfor %}
            </div>{% endif %}
          </div>
          {% endfor %}
        </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
    {% if hurt or hungry or low_san %}<div style="margin-top:10px;font-size:12px;color:#cfc1ea;background:rgba(99,102,241,.14);border:1px solid rgba(232,198,106,.2);border-radius:11px;padding:9px 12px">💊 有帕鲁受伤/理智低？发 <b style="color:#e8c466">/帕鲁症状 &lt;状态&gt;</b>（如 /帕鲁症状 骨折）查治疗方法</div>{% endif %}
    {% if pager %}<div style="margin-top:10px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
    {% else %}
    <div style="text-align:center;padding:22px 10px;color:#b9a9d6;line-height:1.8">
      <div style="font-size:40px">🏕️</div>
      <div style="margin-top:8px;font-size:14px">据点里暂时没有部署帕鲁</div>
      <div style="font-size:12.5px;color:#9c8fc0">在游戏里把帕鲁从帕鲁箱放到据点工作后，这里就会显示它们的状态（属性 / 工作适性 / 受伤·饥饿）。</div>
    </div>
    {% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

BASECAMP_PIX = _PH + """
  .wk { display:flex; align-items:center; gap:10px; padding:8px 2px; border-bottom:2px dotted rgba(90,58,30,.25); }
  .wk:last-child { border-bottom:none; }
  .wk .wpic { flex:none; width:48px; height:48px; background:rgba(214,184,124,.3); border:2px solid #6b4a24; display:flex; align-items:center; justify-content:center; position:relative; }
  .wk .wpic img { width:40px; height:40px; object-fit:contain; image-rendering:pixelated; }
  .wtag { font-size:11px; color:#234f23; background:#a9d8a0; border:2px solid #4e7a44; padding:0 6px; }
  .hpill { font-size:11px; color:#fff; border:2px solid #6a4524; padding:0 6px; }
  .cure { margin-top:7px; border-left:4px solid #8f1212; background:rgba(221,198,149,.5); padding:7px 10px; display:flex; flex-direction:column; gap:7px; }
  .cure .ct { display:flex; flex-direction:column; gap:4px; }
  .cure .cs { font-size:12.5px; color:#8f1212; }
  .cure .cd { font-size:11.5px; color:#574012; line-height:1.55; }
  .cure .cwrap { display:flex; flex-wrap:wrap; gap:7px; margin-top:2px; }
  .cure .citem { display:flex; align-items:center; gap:4px; background:rgba(214,184,124,.55); border:2px solid #6b4a24; padding:1px 8px 1px 2px; }
  .cure .citem img { width:32px; height:32px; object-fit:contain; image-rendering:pixelated; }
  .cure .citem .cph { width:32px; height:32px; display:flex; align-items:center; justify-content:center; font-size:18px; }
  .cure .citem span { font-size:11px; color:#46200a; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">☖ {{ name }} 的据点帕鲁</div><div class="subtitle">据点工作帕鲁状态{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 数据来自存档</div></div></div>
  <div class="frame">
    <div class="m3" style="margin-bottom:13px">
      <div class="tile tc"><div class="v">{{ total }}</div><div class="k">工作帕鲁</div></div>
      <div class="tile tc"><div class="v" style="{% if hurt %}color:#c0291f{% endif %}">{{ hurt }}</div><div class="k">受伤</div></div>
      <div class="tile tc"><div class="v" style="{% if hungry %}color:#a06a10{% endif %}">{{ hungry }}</div><div class="k">饥饿</div></div>
    </div>
    {% if cells %}
    {% for c in cells %}
    <div class="wk">
      <div class="wpic">{% if c.icon %}<img src="{{ c.icon }}">{% else %}<span style="font-size:24px">▥</span>{% endif %}
        {% if c.lucky %}<span style="position:absolute;top:-6px;right:-4px;font-size:13px">✨</span>{% elif c.alpha %}<span style="position:absolute;top:-6px;right:-4px;font-size:12px">♛</span>{% endif %}</div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">
          <span style="font-size:15px;color:#46200a">{{ c.name }}</span>
          <span style="font-size:12px;color:#8f1212">Lv.{{ c.level }}</span>
          {% for e in c.elements %}<span style="font-size:10.5px;color:#574012;background:rgba(156,107,26,.18);padding:0 5px">{{ e }}</span>{% endfor %}
          {% if c.health.hurt %}<span class="hpill" style="background:{% if c.health.tone=='bad' %}#d42c2c{% else %}#e07a1a{% endif %}">⚠{{ c.health.label }}</span>{% endif %}
          {% if c.starving %}<span class="hpill" style="background:#c98a10">🍖饥饿</span>{% endif %}
          {% if c.low_san %}<span class="hpill" style="background:#9c4baa">🧠理智低</span>{% endif %}
        </div>
        <div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:10px;font-size:12px;color:#574012">
          <span>{% if c.working %}⛏️ 正在{{ c.current_work }}{% else %}💤 {{ c.current_work }}{% endif %}</span>
          <span style="{% if c.max_hp and c.hp_pct < 40 %}color:#c0291f{% endif %}">❤ {{ c.hp }}{% if c.max_hp %}/{{ c.max_hp }}{% endif %}</span>
          <span style="{% if c.starving %}color:#a06a10{% endif %}">🍖 {{ c.stomach }}%</span>
          <span style="{% if c.low_san %}color:#c0291f{% endif %}">🧠 SAN {{ c.sanity }}</span>
        </div>
        <div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px">
          {% if c.works %}{% for w in c.works %}<span class="wtag">{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}{% else %}<span style="font-size:11px;color:#7a5a2a">无基地工作适性</span>{% endif %}
        </div>
        {% if c.cure_tips %}
        <div class="cure">
          {% for t in c.cure_tips %}
          <div class="ct">
            <div class="cs">💊 {{ t.symptom }}</div>
            <div class="cd">{{ t.desc }}</div>
            {% if t.drugs %}<div class="cwrap">
              {% for it in t.drugs %}<div class="citem">{% if it.icon %}<img src="{{ it.icon }}">{% else %}<span class="cph">💊</span>{% endif %}<span>{{ it.name }}</span></div>{% endfor %}
            </div>{% endif %}
          </div>
          {% endfor %}
        </div>
        {% endif %}
      </div>
    </div>
    {% endfor %}
    {% if hurt or hungry or low_san %}<div style="margin-top:10px;font-size:12px;color:#46200a;background:rgba(221,198,149,.55);border:2px solid #6a4524;padding:8px 11px">💊 有帕鲁受伤/理智低？发 <b>/帕鲁症状 &lt;状态&gt;</b> 查治疗方法</div>{% endif %}
    {% if pager %}<div style="margin-top:10px;text-align:center;font-size:13px;color:#46200a;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:8px 11px">▶ {{ pager }}</div>{% endif %}
    {% else %}
    <div style="text-align:center;padding:22px 10px;color:#574012;line-height:1.8">
      <div style="font-size:40px">☖</div>
      <div style="margin-top:8px;font-size:14px">据点里暂时没有部署帕鲁</div>
      <div style="font-size:12.5px;color:#7a5a2a">把帕鲁从帕鲁箱放到据点工作后，这里会显示它们的状态。</div>
    </div>
    {% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""

GUILD_TMPL = _HEAD + """
  .grow { display:flex; align-items:center; gap:11px; padding:9px 2px; border-bottom:1px solid rgba(232,198,106,.1); }
  .grow:last-child { border-bottom:none; }
  .grow .gi { width:30px; height:30px; flex:none; border-radius:50%; background:rgba(232,198,106,.16); color:#e8c466; font-weight:800; display:flex; align-items:center; justify-content:center; font-size:14px; }
  .grow .gn { flex:1; font-size:15px; font-weight:700; color:#f3ecd2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .grow .gt { font-size:12px; color:#ffd34d; font-weight:700; flex:none; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">👥 {{ gname }}</div><div class="subtitle">公会成员 · 共 {{ total }} 人{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %}</div></div></div>
  <div class="glass">""" + _GEMS + """
    <div class="m3" style="margin-bottom:14px">
      <div class="tile tc"><div class="v gold">{{ total }}</div><div class="k">成员数</div></div>
      <div class="tile tc"><div class="v gold" style="font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ leader }}</div><div class="k">会长</div></div>
      <div class="tile tc"><div class="v gold">{{ rank }}</div><div class="k">成员规模</div></div>
    </div>
    {% for m in members %}
    <div class="grow"><div class="gi">{{ m.no }}</div><div class="gn">{{ m.name }}</div>{% if m.is_leader %}<div class="gt">👑 会长</div>{% endif %}</div>
    {% endfor %}
    {% if pager %}<div style="margin-top:14px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

GUILD_PIX = _PH + """
  .grow { display:flex; align-items:center; gap:10px; padding:8px 2px; border-bottom:2px dotted rgba(90,58,30,.28); }
  .grow:last-child { border-bottom:none; }
  .grow .gi { width:28px; height:28px; flex:none; background:#caa860; border:2px solid #6a4524; color:#3a2410; font-size:13px; display:flex; align-items:center; justify-content:center; }
  .grow .gn { flex:1; font-size:15px; color:#382207; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .grow .gt { font-size:12px; color:#8f1212; flex:none; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">☗ {{ gname }}</div><div class="subtitle">公会成员 · 共 {{ total }} 人{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %}</div></div></div>
  <div class="frame">
    <div class="m3" style="margin-bottom:13px">
      <div class="tile tc"><div class="v">{{ total }}</div><div class="k">成员数</div></div>
      <div class="tile tc"><div class="v" style="font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ leader }}</div><div class="k">会长</div></div>
      <div class="tile tc"><div class="v">{{ rank }}</div><div class="k">成员规模</div></div>
    </div>
    {% for m in members %}
    <div class="grow"><div class="gi">{{ m.no }}</div><div class="gn">{{ m.name }}</div>{% if m.is_leader %}<div class="gt">♛ 会长</div>{% endif %}</div>
    {% endfor %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:13px;color:#46200a;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:8px 11px">▶ {{ pager }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""

_PCHIP = """
  .prow { display:flex; align-items:center; gap:9px; padding:4px 0; }
  .pname { flex:none; display:inline-flex; align-items:center; gap:5px; font-size:13px; font-weight:800; padding:3px 11px; border-radius:9px; line-height:1.15; }
  .pname .ar { font-size:11px; letter-spacing:-1px; opacity:.95; }
  .pdesc { flex:1; min-width:0; font-size:12px; color:#cfc1ea; line-height:1.35; }
  .srow { display:flex; align-items:baseline; flex-wrap:wrap; gap:7px; padding:5px 0; border-bottom:1px solid rgba(232,198,106,.1); }
  .srow:last-child { border-bottom:none; }
  .sname { font-size:13.5px; font-weight:800; color:#f3ecd2; }
  .selem { font-size:11px; font-weight:700; color:#2a1d05; background:linear-gradient(135deg,#ffe9a8,#e8c466); border-radius:6px; padding:1px 7px; }
  .spow { font-size:11.5px; font-weight:700; color:#e8c466; }
  .sdesc { flex-basis:100%; font-size:11.5px; color:#9c8fc0; line-height:1.3; }
  .pl-legend { background:linear-gradient(135deg,#ffe9a8,#e8a93a); color:#3a2600; box-shadow:0 0 9px rgba(232,169,58,.45); }
  .pl-epic { background:linear-gradient(135deg,#caa0ff,#8a5cf0); color:#fff; }
  .pl-rare { background:linear-gradient(135deg,#8fd0ff,#3a86e0); color:#06243f; }
  .pl-common { background:rgba(150,170,200,.32); color:#e6eeff; }
  .pl-bad { background:linear-gradient(135deg,#ff9a8f,#df3a2e); color:#fff; }
  .pl-neutral { background:rgba(150,140,175,.28); color:#ded6ee; }
"""
_PCHIP_PIX = """
  .prow { display:flex; align-items:center; gap:8px; padding:4px 0; }
  .pname { flex:none; display:inline-flex; align-items:center; gap:4px; font-size:12.5px; padding:2px 9px; border:2px solid #6a4524; line-height:1.2; }
  .pname .ar { font-size:10px; letter-spacing:-1px; }
  .pdesc { flex:1; min-width:0; font-size:11.5px; color:#574012; line-height:1.35; }
  .srow { display:flex; align-items:baseline; flex-wrap:wrap; gap:7px; padding:5px 0; border-bottom:2px dotted rgba(90,58,30,.25); }
  .srow:last-child { border-bottom:none; }
  .sname { font-size:13px; color:#46200a; }
  .selem { font-size:11px; color:#3a2410; background:#caa860; border:2px solid #6a4524; padding:0 6px; }
  .spow { font-size:11px; color:#8f1212; }
  .sdesc { flex-basis:100%; font-size:11px; color:#7a5a2a; line-height:1.3; }
  .pl-legend { background:#f0c860; color:#3a2600; }
  .pl-epic { background:#c4a0e8; color:#2a1640; }
  .pl-rare { background:#9fc8ec; color:#06243f; }
  .pl-common { background:#cdbf9b; color:#3a2410; }
  .pl-bad { background:#e0998f; color:#3a0a06; }
  .pl-neutral { background:#c8bfae; color:#3a2410; }
"""
_TEAM_STAT_F = """
  .team-grid { display:grid; grid-template-columns:repeat({{ team_cols|default(1) }},1fr); gap:14px; align-items:start; }
  .team-grid > .glass { margin:0; }
  .pcard { display:flex; gap:13px; }
  .pcard .pic { flex:none; width:88px; height:88px; background:rgba(232,198,106,.08); border:1px solid rgba(232,198,106,.3); border-radius:14px; display:flex; align-items:center; justify-content:center; position:relative; }
  .pcard .pic img { width:76px; height:76px; object-fit:contain; }
  .ivr { display:flex; gap:6px; margin-top:9px; }
  .ivr .ivb { flex:1; background:rgba(0,0,0,.25); border-radius:8px; padding:5px 6px; text-align:center; }
  .ivr .ivb .ivk { font-size:11px; color:#9c8fc0; }
  .ivr .ivb .ivv { font-size:16px; font-weight:800; color:#e8c466; }
  .ivr .ivb.hpb .ivv { color:#7fe0a0; }
  .ivr .ivb.talent .ivv { color:#ff9a8f; }
  .ivr.trow { margin-top:6px; }
"""
TEAM_TMPL = _HEAD + _PCHIP + _TEAM_STAT_F + """
</style></head><body><div class="page">
  <div class="head"><div><div class="title">{{ title }}</div><div class="subtitle">{{ subtitle }}</div></div></div>
  <div class="team-grid">
  {% for p in pals %}
  <div class="glass">""" + _GEMS + """<div class="pcard">
    <div class="pic">{% if p.icon %}<img src="{{ p.icon }}">{% else %}<span style="font-size:42px">🐾</span>{% endif %}
      {% if p.lucky %}<span style="position:absolute;top:-8px;right:-8px;font-size:18px">✨</span>{% elif p.alpha %}<span style="position:absolute;top:-8px;right:-8px;font-size:16px">👑</span>{% endif %}</div>
    <div style="flex:1;min-width:0">
      <div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
        <span style="font-size:20px;font-weight:900;color:#f3ecd2">{{ p.name }}</span>
        {% if p.nickname %}<span style="font-size:13px;color:#cfc1ea;display:inline-block;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom">「{{ p.nickname }}」</span>{% endif %}
        {% if p.condense %}<span style="font-size:13px;color:#ffd34d;letter-spacing:1px">{{ "★" * p.condense }}</span>{% endif %}
      </div>
      <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px">
        <span class="pill soft">Lv.{{ p.level }}</span>
        {% if p.gender %}<span class="pill soft">{{ p.gender }}</span>{% endif %}
        {% for e in p.elements %}<span class="pill soft">{{ e }}</span>{% endfor %}
        {% if p.lucky %}<span class="pill soft">✨ 闪光</span>{% elif p.alpha %}<span class="pill soft">👑 头目</span>{% endif %}
        {% if p.health.hurt %}<span class="pill" style="background:linear-gradient(135deg,{% if p.health.tone=='bad' %}#ff6a6a,#d42c2c{% else %}#ffb24a,#e07a1a{% endif %});color:#fff;font-weight:800">⚠ {{ p.health.label }}{% if p.health.tone=='bad' %}·放终端可恢复{% endif %}</span>{% endif %}
      </div>
      <div class="ivr">
        <div class="ivb hpb"><div class="ivk">生命值</div><div class="ivv">{{ p.hp }}</div></div>
        <div class="ivb"><div class="ivk">攻击</div><div class="ivv">{{ p.base_atk }}</div></div>
        <div class="ivb"><div class="ivk">防御</div><div class="ivv">{{ p.base_def }}</div></div>
        <div class="ivb"><div class="ivk">工作速度</div><div class="ivv">{{ p.craft_speed }}</div></div>
      </div>
      <div class="ivr trow">
        <div class="ivb talent"><div class="ivk">生命天赋</div><div class="ivv">{{ p.iv_hp }}</div></div>
        <div class="ivb talent"><div class="ivk">攻击天赋</div><div class="ivv">{{ p.iv_atk }}</div></div>
        <div class="ivb talent"><div class="ivk">防御天赋</div><div class="ivv">{{ p.iv_def }}</div></div>
      </div>
      {% if p.works %}<div class="sec-t" style="margin-top:12px">工作适性</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">{% for w in p.works %}<span class="pill">{{ w.icon }} {{ w.name }} Lv{{ w.level }}</span>{% endfor %}</div>{% endif %}
      {% if p.partner.title %}<div class="sec-t" style="margin-top:12px">伙伴技能</div>
      <div class="prow"><span class="pname pl-legend">{{ p.partner.title }}</span>{% if p.partner.desc %}<span class="pdesc">{{ p.partner.desc }}</span>{% endif %}</div>{% endif %}
      {% if p.passives %}<div class="sec-t" style="margin-top:12px">词条</div>
      {% for s in p.passives %}<div class="prow"><span class="pname pl-{{ s.color }}"><span class="ar">{{ s.arrows }}</span>{{ s.name }}</span>{% if s.effect %}<span class="pdesc">{{ s.effect }}</span>{% endif %}</div>{% endfor %}{% endif %}
      {% if p.wazas %}<div class="sec-t" style="margin-top:12px">技能</div>
      {% for w in p.wazas %}<div class="srow"><span class="sname">{{ w.name }}</span>{% if w.elem %}<span class="selem">{{ w.elem }}</span>{% endif %}{% if w.power %}<span class="spow">威力 {{ w.power }}</span>{% endif %}{% if w.desc %}<span class="sdesc">{{ w.desc }}</span>{% endif %}</div>{% endfor %}{% endif %}
    </div>
  </div></div>
  {% endfor %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

_TEAM_STAT_P = """
  .team-grid { display:grid; grid-template-columns:repeat({{ team_cols|default(1) }},1fr); gap:13px; align-items:start; }
  .team-grid > .frame { margin:0; }
  .pcard { display:flex; gap:12px; }
  .pcard .pic { flex:none; width:84px; height:84px; background:rgba(214,184,124,.3); border:2px solid #6b4a24; display:flex; align-items:center; justify-content:center; position:relative; }
  .pcard .pic img { width:72px; height:72px; object-fit:contain; image-rendering:pixelated; }
  .ivr { display:flex; gap:6px; margin-top:9px; }
  .ivr .ivb { flex:1; background:rgba(221,198,149,0.58); border:2px solid #6a4524; padding:5px 6px; text-align:center; }
  .ivr .ivb .ivk { font-size:11px; color:#574012; }
  .ivr .ivb .ivv { font-size:16px; color:#8f1212; }
  .ivr .ivb.hpb .ivv { color:#2f7a3a; }
  .ivr .ivb.talent .ivv { color:#b06a00; }
  .ivr.trow { margin-top:6px; }
"""
TEAM_PIX = _PH + _PCHIP_PIX + _TEAM_STAT_P + """
</style></head><body><div class="page">
  <div class="head"><div><div class="title">{{ title }}</div><div class="subtitle">{{ subtitle }}</div></div></div>
  <div class="team-grid">
  {% for p in pals %}
  <div class="frame"><div class="pcard">
    <div class="pic">{% if p.icon %}<img src="{{ p.icon }}">{% else %}<span style="font-size:40px">▥</span>{% endif %}
      {% if p.lucky %}<span style="position:absolute;top:-8px;right:-6px;font-size:17px">✨</span>{% elif p.alpha %}<span style="position:absolute;top:-8px;right:-6px;font-size:15px">♛</span>{% endif %}</div>
    <div style="flex:1;min-width:0">
      <div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
        <span style="font-size:18px;color:#46200a">{{ p.name }}</span>
        {% if p.nickname %}<span style="font-size:13px;color:#574012;display:inline-block;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom">「{{ p.nickname }}」</span>{% endif %}
        {% if p.condense %}<span style="font-size:13px;color:#b06a00">{{ "★" * p.condense }}</span>{% endif %}
      </div>
      <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px">
        <span class="pill">Lv.{{ p.level }}</span>
        {% if p.gender %}<span class="pill">{{ p.gender }}</span>{% endif %}
        {% for e in p.elements %}<span class="pill">{{ e }}</span>{% endfor %}
        {% if p.lucky %}<span class="pill">✨闪光</span>{% elif p.alpha %}<span class="pill">♛头目</span>{% endif %}
        {% if p.health.hurt %}<span class="pill" style="background:{% if p.health.tone=='bad' %}#d42c2c{% else %}#e07a1a{% endif %};color:#fff">⚠{{ p.health.label }}{% if p.health.tone=='bad' %}·放终端可恢复{% endif %}</span>{% endif %}
      </div>
      <div class="ivr">
        <div class="ivb hpb"><div class="ivk">生命值</div><div class="ivv">{{ p.hp }}</div></div>
        <div class="ivb"><div class="ivk">攻击</div><div class="ivv">{{ p.base_atk }}</div></div>
        <div class="ivb"><div class="ivk">防御</div><div class="ivv">{{ p.base_def }}</div></div>
        <div class="ivb"><div class="ivk">工作速度</div><div class="ivv">{{ p.craft_speed }}</div></div>
      </div>
      <div class="ivr trow">
        <div class="ivb talent"><div class="ivk">生命天赋</div><div class="ivv">{{ p.iv_hp }}</div></div>
        <div class="ivb talent"><div class="ivk">攻击天赋</div><div class="ivv">{{ p.iv_atk }}</div></div>
        <div class="ivb talent"><div class="ivk">防御天赋</div><div class="ivv">{{ p.iv_def }}</div></div>
      </div>
      {% if p.works %}<div class="sec-t" style="margin-top:12px">工作适性</div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">{% for w in p.works %}<span class="pill">{{ w.icon }} {{ w.name }} Lv{{ w.level }}</span>{% endfor %}</div>{% endif %}
      {% if p.partner.title %}<div class="sec-t" style="margin-top:12px">伙伴技能</div>
      <div class="prow"><span class="pname pl-legend">{{ p.partner.title }}</span>{% if p.partner.desc %}<span class="pdesc">{{ p.partner.desc }}</span>{% endif %}</div>{% endif %}
      {% if p.passives %}<div class="sec-t" style="margin-top:12px">词条</div>
      {% for s in p.passives %}<div class="prow"><span class="pname pl-{{ s.color }}"><span class="ar">{{ s.arrows }}</span>{{ s.name }}</span>{% if s.effect %}<span class="pdesc">{{ s.effect }}</span>{% endif %}</div>{% endfor %}{% endif %}
      {% if p.wazas %}<div class="sec-t" style="margin-top:12px">技能</div>
      {% for w in p.wazas %}<div class="srow"><span class="sname">{{ w.name }}</span>{% if w.elem %}<span class="selem">{{ w.elem }}</span>{% endif %}{% if w.power %}<span class="spow">威力 {{ w.power }}</span>{% endif %}{% if w.desc %}<span class="sdesc">{{ w.desc }}</span>{% endif %}</div>{% endfor %}{% endif %}
    </div>
  </div></div>
  {% endfor %}
  </div>
  """ + _PF + """
</div></body></html>"""


DAILY_PIX = _PH + """
  .lp { display:flex; align-items:center; padding:7px 0; border-bottom:2px dotted rgba(90,58,30,0.28); }
  .lp:last-child { border-bottom:none; }
  .lp .rk { width:22px; color:#8f1212; }
  .lp .nm { flex:1; font-size:14px; color:#382207; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .lp .du { font-size:14px; color:#8f1212; }
  .none { color:#523f10; font-size:13px; padding:4px 0 6px; }
</style></head><body><div class="page">
  <div class="head"><div><div class="title">{{ title }}</div><div class="subtitle">{{ now }}</div></div></div>
  <div class="frame">
    <div style="color:#574012;font-size:14px;line-height:1.6;margin-bottom:13px">{{ greeting }}</div>
    <div style="display:flex;align-items:center;gap:9px;padding:11px 14px;background:rgba(221,198,149,0.58);border:2px solid #6a4524;font-size:14px;color:#382207">
      <span class="badge {{ 'on' if online else 'off' }}" style="font-size:11px">{% if online %}在线{% else %}离线{% endif %}</span>
      {% if online %}{{ cur }}/{{ maxn }}人 · FPS{{ fps }} · 第{{ days }}天{% else %}服务器连不上{% endif %}
    </div>
    <div class="m3" style="margin-top:12px">
      <div class="tile tc"><div class="v">{{ today_peak }}</div><div class="k">今日峰值</div></div>
      <div class="tile tc"><div class="v">{{ today_avg }}</div><div class="k">今日平均</div></div>
      {% if show_yday %}<div class="tile tc"><div class="v">{{ yday_peak }}</div><div class="k">昨日峰值</div></div>{% else %}<div class="tile tc"><div class="v">{{ record }}</div><div class="k">历史纪录</div></div>{% endif %}
    </div>
  </div>
  <div class="frame">
    <div class="sec-t">今日肝帝 TOP3</div>
    {% if today_top %}{% for p in today_top %}<div class="lp"><div class="rk">{{ loop.index }}</div><div class="nm">{{ p.name }}</div><div class="du">{{ p.dur }}</div></div>{% endfor %}{% else %}<div class="none">今天还没有人上线哦～</div>{% endif %}
    <div class="sec-t" style="margin-top:14px">本周肝帝榜 TOP3</div>
    {% if week_top %}{% for p in week_top %}<div class="lp"><div class="rk">{{ loop.index }}</div><div class="nm">{{ p.name }}</div><div class="du">{{ p.dur }}</div></div>{% endfor %}{% else %}<div class="none">本周还没有在线记录～</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


PALDEX_PIX = _PH + """
  .sk { display:flex; align-items:center; padding:8px 0; border-bottom:2px dotted rgba(90,58,30,0.28); }
  .sk:last-child { border-bottom:none; }
  .sk .se { font-size:11px; color:#3a2410; background:#caa860; border:2px solid #6a4524; padding:1px 6px; margin-right:8px; }
  .sk .sn { flex:1; font-size:14px; color:#382207; }
  .sk .sp { font-size:12px; color:#523f10; min-width:100px; text-align:right; }
</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:104px;height:104px;background:rgba(214,184,124,.3);border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:86px;height:86px;object-fit:contain;image-rendering:pixelated"></div>{% else %}<div style="flex:none;font-size:64px">▥</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill">#{{ index }}</span>{% for e in elements %}<span class="pill">{{ e }}</span>{% endfor %}<span class="pill">{{ "★"*(rarity if rarity <= 5 else 5) if rarity else "★" }}</span>{% if nocturnal %}<span class="pill">夜行</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="frame">
    {% if desc %}<div style="font-size:13px;color:#574012;line-height:1.6;margin-bottom:13px">{{ desc }}</div>{% endif %}
    {% if egg or lv or price or cap %}<div style="display:flex;flex-wrap:wrap;gap:7px;margin-bottom:7px">
      {% if egg %}<span class="pill">蛋 {{ egg }}</span>{% endif %}
      {% if lv %}<span class="pill">刷新 {{ lv }}</span>{% endif %}
      {% if cap %}<span class="pill">捕获率x{{ cap }}</span>{% endif %}
      {% if price %}<span class="pill">贩卖价 {{ price }}金币</span>{% endif %}
      {% if size %}<span class="pill">体型 {{ size }}</span>{% endif %}
    </div>
    <div style="font-size:11px;color:#7a6a4a;line-height:1.6;margin-bottom:11px">贩卖价＝卖给商人/帕鲁贩子得的金币(非购买价,「哪里买」查不到)　刷新＝野外出现等级参考　体型＝个头大小(XS最小→XL最大)</div>{% endif %}
    <div class="sec-t">基础数值</div>
    <div class="m3">
      <div class="tile tc"><div class="v">{{ hp }}</div><div class="k">生命</div></div>
      <div class="tile tc"><div class="v">{{ atk }}</div><div class="k">近战攻击</div></div>
      <div class="tile tc"><div class="v">{{ shot }}</div><div class="k">远程攻击</div></div>
    </div>
    <div class="m3" style="margin-top:7px">
      <div class="tile tc"><div class="v">{{ defense }}</div><div class="k">防御力</div></div>
      <div class="tile tc"><div class="v">{{ stamina }}</div><div class="k">耐力</div></div>
      <div class="tile tc"><div class="v">{{ food }}</div><div class="k">进食量</div></div>
    </div>
    <div class="m3" style="margin-top:7px">
      <div class="tile tc"><div class="v">{{ walk }}</div><div class="k">走路速度</div></div>
      <div class="tile tc"><div class="v">{{ run }}</div><div class="k">奔跑速度</div></div>
      <div class="tile tc"><div class="v">{{ ride }}</div><div class="k">骑乘速度</div></div>
    </div>
    {% if ranch %}<div class="sec-t" style="margin-top:15px">牧场产出</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for r in ranch %}<span class="pill" style="display:inline-flex;align-items:center;gap:5px">{% if r.icon %}<img src="{{ r.icon }}" style="width:20px;height:20px;object-fit:contain;image-rendering:pixelated">{% endif %}{{ r.name }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:15px">主动技能</div>
    {% for s in skills %}<div class="sk">{% if s.elem %}<span class="se">{{ s.elem }}</span>{% endif %}<span class="sn">{{ s.name }}</span><span class="sp">威力{{ s.power }} CD{{ s.cd }}s</span></div>{% endfor %}
    {% if works %}<div class="sec-t" style="margin-top:15px">工作适性</div><div style="display:flex;flex-wrap:wrap;gap:7px">{% for w in works %}<span class="pill">{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}</div>{% endif %}
    {% if drops %}<div class="sec-t" style="margin-top:15px">掉落物品</div>
    {% for d in drops %}<div style="display:flex;align-items:center;justify-content:space-between;padding:5px 0;border-bottom:2px dotted rgba(90,58,30,0.28)">
      <span style="display:flex;align-items:center;gap:6px;font-size:14px;color:#382207">{% if d.icon %}<img src="{{ d.icon }}" style="width:24px;height:24px;object-fit:contain;image-rendering:pixelated">{% endif %}{{ d.name }}</span>
      <span style="font-size:12px;color:#574012">{% if d.qty %}x{{ d.qty }} · {% endif %}{{ d.rate }}%</span></div>{% endfor %}{% endif %}
    {% if partner_title %}<div class="sec-t" style="margin-top:15px">伙伴技能</div>
    <div style="background:rgba(221,198,149,0.58);border:2px solid #6a4524;padding:11px 14px">
      <div style="font-size:14px;color:#7a3604">{{ partner_title }}</div>
      <div style="font-size:13px;color:#574012;line-height:1.6;margin-top:5px">{{ partner_desc }}</div>
    </div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


BREED_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div><div class="title">⚗ 帕鲁配种</div><div class="subtitle">亲代组合的后代</div></div></div>
  <div class="frame">
    <div style="display:flex;align-items:center;justify-content:center;gap:9px;padding:4px 0 12px">
      <div class="tile" style="flex:1;max-width:150px;text-align:center;padding:13px 8px">
        {% if a.icon %}<img src="{{ a.icon }}" style="width:48px;height:48px;object-fit:contain;display:block;margin:0 auto 5px;image-rendering:pixelated">{% endif %}
        <div style="font-size:17px;color:#46200a;word-break:break-word">{{ a.name }}</div>
        <div style="font-size:11px;color:#523f10;margin-top:3px">#{{ a.index }}</div>
        <div style="margin-top:7px;display:flex;gap:4px;justify-content:center;flex-wrap:wrap">{% for e in a.elements %}<span class="pill" style="font-size:10px">{{ e }}</span>{% endfor %}</div>
      </div>
      <div style="font-size:26px;color:#8f1212;flex-shrink:0">+</div>
      <div class="tile" style="flex:1;max-width:150px;text-align:center;padding:13px 8px">
        {% if b.icon %}<img src="{{ b.icon }}" style="width:48px;height:48px;object-fit:contain;display:block;margin:0 auto 5px;image-rendering:pixelated">{% endif %}
        <div style="font-size:17px;color:#46200a;word-break:break-word">{{ b.name }}</div>
        <div style="font-size:11px;color:#523f10;margin-top:3px">#{{ b.index }}</div>
        <div style="margin-top:7px;display:flex;gap:4px;justify-content:center;flex-wrap:wrap">{% for e in b.elements %}<span class="pill" style="font-size:10px">{{ e }}</span>{% endfor %}</div>
      </div>
    </div>
    <div style="text-align:center;font-size:14px;color:#7a3604;margin:2px 0">==== 后代 ====</div>
    <div style="text-align:center;padding:8px 0 4px">
      {% if c.icon %}<img src="{{ c.icon }}" style="width:64px;height:64px;object-fit:contain;display:block;margin:0 auto 4px;image-rendering:pixelated">{% endif %}
      <div class="num-big" style="font-size:28px">{{ c.name }}</div>
      <div style="font-size:12px;color:#523f10;margin-top:4px">图鉴 #{{ c.index }} · {{ "★"*(c.rarity if c.rarity <= 5 else 5) if c.rarity else "★" }}</div>
      <div style="display:flex;gap:5px;justify-content:center;margin-top:9px">{% for e in c.elements %}<span class="pill red" style="font-size:13px;padding:3px 12px">{{ e }}</span>{% endfor %}</div>
    </div>
    {% if child_breeds %}
    <div style="margin-top:10px;border-top:2px dotted rgba(90,58,30,0.35);padding-top:10px">
      <div class="sec-t">用 {{ child_name }} 继续配</div>
      {% for cb in child_breeds %}
      <div style="display:flex;align-items:center;gap:6px;padding:5px 2px;font-size:13px">
        <span style="color:#523f10;flex:1;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ child_name }} + {{ cb.partner }}</span>
        <span style="color:#7a1f1f;flex-shrink:0">→</span>
        {% if cb.result_icon %}<img src="{{ cb.result_icon }}" style="width:28px;height:28px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
        <b style="color:#382207;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ cb.result }}</b>
      </div>
      {% endfor %}
    </div>
    {% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


REVERSE_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🔄 反配种</div>
    <div class="subtitle">配出「{{ target }}」#{{ target_index }} 的亲代组合 · 共 {{ total }} 组 · 第 {{ page }}/{{ pages }} 页</div>
  </div>{% if target_icon %}<img src="{{ target_icon }}" style="width:54px;height:54px;object-fit:contain;filter:drop-shadow(0 2px 5px rgba(0,0,0,.5))">{% endif %}</div>
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" style="padding:8px 12px;gap:8px">
      <div style="flex:1;display:flex;align-items:center;gap:7px;justify-content:flex-end;min-width:0">
        <span style="font-size:14px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.a }}</span>
        {% if r.a_icon %}<img src="{{ r.a_icon }}" style="width:34px;height:34px;object-fit:contain;flex-shrink:0">{% endif %}
      </div>
      <span style="color:#e8c466;font-weight:800;flex-shrink:0">＋</span>
      <div style="flex:1;display:flex;align-items:center;gap:7px;min-width:0">
        {% if r.b_icon %}<img src="{{ r.b_icon }}" style="width:34px;height:34px;object-fit:contain;flex-shrink:0">{% endif %}
        <span style="font-size:14px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.b }}</span>
      </div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


REVERSE_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🔄 反配种</div>
    <div class="subtitle">配出「{{ target }}」#{{ target_index }} · 共 {{ total }} 组 · 第 {{ page }}/{{ pages }} 页</div>
  </div>{% if target_icon %}<img src="{{ target_icon }}" style="width:48px;height:48px;object-fit:contain;image-rendering:pixelated">{% endif %}</div>
  <div class="frame">
    {% for r in rows %}
    <div class="row" style="padding:7px 10px;gap:7px">
      <div style="flex:1;display:flex;align-items:center;gap:6px;justify-content:flex-end;min-width:0">
        <span style="font-size:14px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.a }}</span>
        {% if r.a_icon %}<img src="{{ r.a_icon }}" style="width:30px;height:30px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
      </div>
      <span style="color:#7a1f1f;flex-shrink:0">+</span>
      <div style="flex:1;display:flex;align-items:center;gap:6px;min-width:0">
        {% if r.b_icon %}<img src="{{ r.b_icon }}" style="width:30px;height:30px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
        <span style="font-size:14px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.b }}</span>
      </div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:12px;text-align:center;font-size:13px;color:#46200a;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:8px 11px">▶ {{ pager }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


SHINY_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ title }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px">
    {% for r in rows %}
      <div style="display:flex;flex-direction:column;align-items:center;background:linear-gradient(160deg,rgba(232,198,106,.16),rgba(18,12,48,.5));border:1px solid rgba(232,198,106,.35);border-radius:13px;padding:10px 6px;position:relative">
        <span style="position:absolute;top:4px;right:6px;font-size:13px">{{ badge }}</span>
        {% if r.icon %}<img src="{{ r.icon }}" style="width:52px;height:52px;object-fit:contain">{% else %}<span style="font-size:32px">🐾</span>{% endif %}
        <div style="font-size:13px;font-weight:700;color:#f3ecd2;margin-top:5px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%">{{ r.name }}</div>
        <div style="font-size:11px;color:#9c8fc0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%">🧑{{ r.owner }}</div>
      </div>
    {% endfor %}
    </div>
    {% if top_owners %}<div style="margin-top:13px;text-align:center;font-size:12.5px;color:#cfc1ea">🏆 收藏家：{{ top_owners }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


SHINY_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ title }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="frame">
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
    {% for r in rows %}
      <div style="display:flex;flex-direction:column;align-items:center;background:rgba(221,198,149,.5);border:2px solid #9c6b1a;padding:9px 5px;position:relative">
        <span style="position:absolute;top:3px;right:5px;font-size:12px">{{ badge }}</span>
        {% if r.icon %}<img src="{{ r.icon }}" style="width:48px;height:48px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:30px">🐾</span>{% endif %}
        <div style="font-size:13px;color:#382207;margin-top:5px;text-align:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%">{{ r.name }}</div>
        <div style="font-size:11px;color:#7a5a1a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%">{{ r.owner }}</div>
      </div>
    {% endfor %}
    </div>
    {% if top_owners %}<div style="margin-top:13px;text-align:center;font-size:12.5px;color:#46200a">收藏家：{{ top_owners }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


SYMPTOM_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">💊 帕鲁伤病治疗</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
{% if single %}
  <div class="glass" style="text-align:center;padding:20px 24px">""" + _GEMS + """
    <div style="font-size:30px;font-weight:900;color:#ffd86b;letter-spacing:2px;text-shadow:0 2px 10px rgba(0,0,0,.55)">🩹 {{ name }}</div>
    <div style="margin:14px auto 0;max-width:420px;font-size:15px;color:#e9e0f5;line-height:1.95;white-space:pre-line;word-break:break-word;text-align:left;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.16);border-radius:14px;padding:12px 16px">{{ desc }}</div>
  </div>
  {% if items %}
  <div class="glass" style="margin-top:11px">""" + _GEMS + """
    <div class="sec-t">💊 治疗道具</div>
    <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:14px;margin-top:6px">
    {% for it in items %}
      <div style="display:flex;flex-direction:column;align-items:center;width:118px">
        <div style="width:104px;height:104px;border-radius:20px;background:radial-gradient(circle at 50% 38%,rgba(232,198,106,.30),rgba(18,12,48,.55) 72%);border:2px solid rgba(232,198,106,.62);box-shadow:0 3px 15px rgba(0,0,0,.5),inset 0 0 18px rgba(232,198,106,.18);display:flex;align-items:center;justify-content:center">
          {% if it.icon %}<img src="{{ it.icon }}" style="width:88px;height:88px;object-fit:contain;filter:drop-shadow(0 3px 8px rgba(0,0,0,.6))">{% else %}<span style="font-size:60px">💊</span>{% endif %}
        </div>
        <div style="margin-top:8px;font-size:14px;font-weight:700;color:#f3ecd2;text-align:center;line-height:1.35;word-break:break-word">{{ it.name }}</div>
      </div>
    {% endfor %}
    </div>
  </div>
  {% endif %}
{% else %}
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" style="padding:9px 12px;gap:11px;align-items:center{% if not loop.first %};margin-top:8px{% endif %}">
      <div style="flex:none;display:flex;gap:6px">
        {% for it in r.items %}
        <div style="width:46px;height:46px;border-radius:12px;background:radial-gradient(circle at 50% 40%,rgba(232,198,106,.26),rgba(18,12,48,.5) 74%);border:1px solid rgba(232,198,106,.5);display:flex;align-items:center;justify-content:center">
          {% if it.icon %}<img src="{{ it.icon }}" style="width:38px;height:38px;object-fit:contain">{% else %}<span style="font-size:24px">💊</span>{% endif %}
        </div>
        {% endfor %}
        {% if not r.items %}<div style="font-size:30px">💊</div>{% endif %}
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-size:16px;font-weight:800;color:#ffd86b">🩹 {{ r.name }}</div>
        <div style="font-size:13px;color:#cfc1ea;line-height:1.55;margin-top:2px">{{ r.desc }}</div>
      </div>
    </div>
    {% endfor %}
  </div>
{% endif %}
  """ + _FOOT + """
</div></body></html>"""


SYMPTOM_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">💊 帕鲁伤病治疗</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
{% if single %}
  <div class="frame" style="text-align:center;padding:18px 20px">
    <div style="font-size:28px;color:#7a1f1f;letter-spacing:2px">🩹 {{ name }}</div>
    <div style="margin:13px auto 0;max-width:420px;font-size:15px;color:#382207;line-height:1.95;white-space:pre-line;word-break:break-word;text-align:left;background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:11px 15px">{{ desc }}</div>
  </div>
  {% if items %}
  <div class="frame" style="margin-top:10px">
    <div class="sec-t">治疗道具</div>
    <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:13px;margin-top:6px">
    {% for it in items %}
      <div style="display:flex;flex-direction:column;align-items:center;width:114px">
        <div style="width:100px;height:100px;background:rgba(214,184,124,.3);border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center">
          {% if it.icon %}<img src="{{ it.icon }}" style="width:84px;height:84px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:58px">💊</span>{% endif %}
        </div>
        <div style="margin-top:8px;font-size:14px;color:#382207;text-align:center;line-height:1.35;word-break:break-word">{{ it.name }}</div>
      </div>
    {% endfor %}
    </div>
  </div>
  {% endif %}
{% else %}
  <div class="frame">
    {% for r in rows %}
    <div class="row" style="padding:8px 10px;gap:10px;align-items:center{% if not loop.first %};margin-top:7px{% endif %}">
      <div style="flex:none;display:flex;gap:5px">
        {% for it in r.items %}
        <div style="width:42px;height:42px;background:rgba(214,184,124,.32);border:2px solid #6b4a24;display:flex;align-items:center;justify-content:center">
          {% if it.icon %}<img src="{{ it.icon }}" style="width:34px;height:34px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:22px">💊</span>{% endif %}
        </div>
        {% endfor %}
        {% if not r.items %}<div style="font-size:28px">💊</div>{% endif %}
      </div>
      <div style="flex:1;min-width:0">
        <div style="font-size:16px;color:#7a1f1f">🩹 {{ r.name }}</div>
        <div style="font-size:13px;color:#46200a;line-height:1.55;margin-top:2px">{{ r.desc }}</div>
      </div>
    </div>
    {% endfor %}
  </div>
{% endif %}
  """ + _PF + """
</div></body></html>"""


ROUTE_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🧬 配种路线 → {{ target }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div>{% if target_icon %}<img src="{{ target_icon }}" style="width:50px;height:50px;object-fit:contain;filter:drop-shadow(0 2px 5px rgba(0,0,0,.5))">{% endif %}</div>
  <div class="glass">""" + _GEMS + """
    {% for s in steps %}
    <div class="row" {% if s.is_target %}style="padding:8px 9px;gap:5px;align-items:center;background:linear-gradient(100deg,rgba(232,198,106,0.16),rgba(18,12,48,0.5) 60%);border-color:rgba(232,198,106,0.4)"{% else %}style="padding:8px 9px;gap:5px;align-items:center"{% endif %}>
      <span style="width:18px;flex-shrink:0;color:#e8c466;font-weight:800;font-size:13px">{{ s.n }}</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;justify-content:flex-end;min-width:0">
        <span style="font-size:12.5px;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.a }}{% if s.a_owned %}<span style="color:#7fe0a0">✓</span>{% endif %}</span>
        {% if s.a_icon %}<img src="{{ s.a_icon }}" style="width:30px;height:30px;object-fit:contain;flex-shrink:0">{% endif %}
      </div>
      <span style="color:#9c8fc0;flex-shrink:0;font-size:12px">＋</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0">
        {% if s.b_icon %}<img src="{{ s.b_icon }}" style="width:30px;height:30px;object-fit:contain;flex-shrink:0">{% endif %}
        <span style="font-size:12.5px;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.b }}{% if s.b_owned %}<span style="color:#7fe0a0">✓</span>{% endif %}</span>
      </div>
      <span style="color:#e8c466;flex-shrink:0;font-weight:800">→</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0">
        {% if s.c_icon %}<img src="{{ s.c_icon }}" style="width:32px;height:32px;object-fit:contain;flex-shrink:0">{% endif %}
        <span style="font-size:13px;font-weight:700;color:{% if s.is_target %}#e8c466{% else %}#f3ecd2{% endif %};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.c }}</span>
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:11px;text-align:center;font-size:11.5px;color:#9c8fc0">✓=你已拥有 · 按顺序配，每步产物用于下一步</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


ROUTE_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🧬 配种路线 → {{ target }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div>{% if target_icon %}<img src="{{ target_icon }}" style="width:46px;height:46px;object-fit:contain;image-rendering:pixelated">{% endif %}</div>
  <div class="frame">
    {% for s in steps %}
    <div class="row" style="padding:7px 8px;gap:5px;align-items:center">
      <span style="width:18px;flex-shrink:0;color:#7a1f1f;font-size:13px">{{ s.n }}</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;justify-content:flex-end;min-width:0">
        <span style="font-size:12.5px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.a }}{% if s.a_owned %}<span style="color:#2f7a3a">✓</span>{% endif %}</span>
        {% if s.a_icon %}<img src="{{ s.a_icon }}" style="width:28px;height:28px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
      </div>
      <span style="color:#7a5a1a;flex-shrink:0;font-size:12px">+</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0">
        {% if s.b_icon %}<img src="{{ s.b_icon }}" style="width:28px;height:28px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
        <span style="font-size:12.5px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.b }}{% if s.b_owned %}<span style="color:#2f7a3a">✓</span>{% endif %}</span>
      </div>
      <span style="color:#7a1f1f;flex-shrink:0">→</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0">
        {% if s.c_icon %}<img src="{{ s.c_icon }}" style="width:30px;height:30px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
        <span style="font-size:13px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.c }}</span>
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:11px;text-align:center;font-size:11.5px;color:#7a5a1a">✓=你已拥有 · 按顺序配</div>
  </div>
  """ + _PF + """
</div></body></html>"""


POWER_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🏆 全服战力榜</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" {% if r.rank <= 3 %}style="padding:9px 12px;gap:9px;align-items:center;background:linear-gradient(100deg,rgba(232,198,106,0.16),rgba(18,12,48,0.5) 60%);border-color:rgba(232,198,106,0.4)"{% else %}style="padding:9px 12px;gap:9px;align-items:center"{% endif %}>
      <div style="width:30px;flex-shrink:0;text-align:center;font-size:17px;font-weight:900;color:#e8c466">{{ r.medal }}</div>
      {% if r.icon %}<img src="{{ r.icon }}" style="width:42px;height:42px;object-fit:contain;flex-shrink:0">{% else %}<span style="font-size:24px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.lucky %} ✨{% elif r.alpha %} 👑{% endif %}</div>
        <div style="font-size:12px;color:#9c8fc0">Lv.{{ r.level }} · 🧑{{ r.owner }}</div>
      </div>
      <div style="flex-shrink:0;text-align:right;min-width:62px">
        <div style="font-size:16px;font-weight:800;color:#e8c466">{{ r.power }}</div>
        <div class="bar" style="margin-top:4px;width:56px"><div class="barf" style="width:{{ r.pct }}%"></div></div>
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:11px;text-align:center;font-size:11.5px;color:#9c8fc0">战力为综合评分(等级/种族/天赋/浓缩/被动),仅供横向对比</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


POWER_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🏆 全服战力榜</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="frame">
    {% for r in rows %}
    <div class="row" style="padding:8px 11px;gap:8px;align-items:center">
      <div style="width:28px;flex-shrink:0;text-align:center;font-size:16px;color:#7a1f1f">{{ r.medal }}</div>
      {% if r.icon %}<img src="{{ r.icon }}" style="width:38px;height:38px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:22px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.lucky %} ✨{% elif r.alpha %} 👑{% endif %}</div>
        <div style="font-size:12px;color:#7a5a1a">Lv.{{ r.level }} · {{ r.owner }}</div>
      </div>
      <div style="flex-shrink:0;font-size:16px;color:#7a1f1f">{{ r.power }}</div>
    </div>
    {% endfor %}
    <div style="margin-top:11px;text-align:center;font-size:11.5px;color:#7a5a1a">战力为综合评分,仅供横向对比</div>
  </div>
  """ + _PF + """
</div></body></html>"""


HEATMAP_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🔥 在线热力图</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% set colors = ['rgba(40,30,70,.55)','rgba(99,102,241,.32)','rgba(99,102,241,.6)','rgba(232,198,106,.55)','#e8c466'] %}
    <div style="display:flex;gap:2px;padding-left:32px;margin-bottom:3px">
      {% for h in range(24) %}<div style="flex:1;font-size:8px;color:#9c8fc0;text-align:center">{{ h }}</div>{% endfor %}
    </div>
    {% for r in rows %}
    <div style="display:flex;align-items:center;gap:2px;margin-bottom:2px">
      <div style="width:30px;font-size:11px;color:#cfc1ea;flex-shrink:0">{{ r.label }}</div>
      {% for c in r.cells %}<div style="flex:1;height:17px;border-radius:3px;background:{{ colors[c] }}"></div>{% endfor %}
    </div>
    {% endfor %}
    <div style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:12px;font-size:11px;color:#cfc1ea">
      <span>少</span>
      {% for c in colors %}<div style="width:18px;height:11px;border-radius:2px;background:{{ c }}"></div>{% endfor %}
      <span>多</span>
    </div>
    {% if hint %}<div style="margin-top:11px;text-align:center;font-size:13px;color:#f3ecd2;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📈 {{ hint }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


HEATMAP_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🔥 在线热力图</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="frame">
    {% set colors = ['rgba(120,100,70,.4)','rgba(124,138,70,.5)','rgba(154,107,26,.7)','rgba(122,31,31,.7)','#7a1f1f'] %}
    <div style="display:flex;gap:2px;padding-left:32px;margin-bottom:3px">
      {% for h in range(24) %}<div style="flex:1;font-size:8px;color:#7a5a1a;text-align:center">{{ h }}</div>{% endfor %}
    </div>
    {% for r in rows %}
    <div style="display:flex;align-items:center;gap:2px;margin-bottom:2px">
      <div style="width:30px;font-size:11px;color:#382207;flex-shrink:0">{{ r.label }}</div>
      {% for c in r.cells %}<div style="flex:1;height:17px;background:{{ colors[c] }};border:1px solid #6a4524">{{ "" }}</div>{% endfor %}
    </div>
    {% endfor %}
    <div style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:12px;font-size:11px;color:#46200a">
      <span>少</span>
      {% for c in colors %}<div style="width:18px;height:11px;background:{{ c }};border:1px solid #6a4524"></div>{% endfor %}
      <span>多</span>
    </div>
    {% if hint %}<div style="margin-top:11px;text-align:center;font-size:13px;color:#46200a;background:rgba(221,198,149,.55);border:2px solid #6a4524;padding:8px 11px">📈 {{ hint }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


DROPLIST_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🎁 掉落物品目录</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    {% for r in rows %}
      <div style="display:flex;align-items:center;gap:8px;background:rgba(18,12,48,.5);border:1px solid rgba(232,198,106,.18);border-radius:11px;padding:7px 10px;min-width:0">
        {% if r.icon %}<img src="{{ r.icon }}" style="width:32px;height:32px;object-fit:contain;flex-shrink:0">{% else %}<span style="font-size:20px">🎁</span>{% endif %}
        <div style="flex:1;min-width:0">
          <div style="font-size:13.5px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</div>
          <div style="font-size:11px;color:#9c8fc0">{{ r.count }} 只掉</div>
        </div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:13px;text-align:center;font-size:12.5px;color:#cfc1ea">发 <b style="color:#e8c466">/帕鲁哪里掉 物品名</b> 查掉落的帕鲁{% if pager %} ·  {{ pager }}{% endif %}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


DROPLIST_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🎁 掉落物品目录</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="frame">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px">
    {% for r in rows %}
      <div style="display:flex;align-items:center;gap:7px;background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:6px 9px;min-width:0">
        {% if r.icon %}<img src="{{ r.icon }}" style="width:30px;height:30px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:18px">🎁</span>{% endif %}
        <div style="flex:1;min-width:0">
          <div style="font-size:13px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</div>
          <div style="font-size:11px;color:#7a5a1a">{{ r.count }} 只掉</div>
        </div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:12px;text-align:center;font-size:12.5px;color:#46200a">发 <b>/帕鲁哪里掉 物品名</b> 查掉落的帕鲁{% if pager %} · {{ pager }}{% endif %}</div>
  </div>
  """ + _PF + """
</div></body></html>"""


DROP_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🎁 掉落查询</div>
    <div class="subtitle">掉落「{{ item }}」的帕鲁 · 共 {{ total }} 种{% if pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %}</div>
  </div>{% if item_icon %}<img src="{{ item_icon }}" style="width:50px;height:50px;object-fit:contain;filter:drop-shadow(0 2px 5px rgba(0,0,0,.5))">{% endif %}</div>
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" style="padding:8px 12px;gap:9px;align-items:center">
      {% if r.icon %}<img src="{{ r.icon }}" style="width:40px;height:40px;object-fit:contain;flex-shrink:0">{% else %}<span style="font-size:24px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.pal }}</div>
        <div style="font-size:12px;color:#9c8fc0">No.{{ r.index }}</div>
      </div>
      <div style="flex-shrink:0;text-align:right">
        <div style="font-size:15px;font-weight:800;color:#e8c466">{{ r.rate }}%</div>
        {% if r.qty %}<div style="font-size:12px;color:#cfc1ea">×{{ r.qty }}</div>{% endif %}
      </div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


DROP_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🎁 掉落查询</div>
    <div class="subtitle">掉落「{{ item }}」的帕鲁 · 共 {{ total }} 种{% if pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %}</div>
  </div>{% if item_icon %}<img src="{{ item_icon }}" style="width:46px;height:46px;object-fit:contain;image-rendering:pixelated">{% endif %}</div>
  <div class="frame">
    {% for r in rows %}
    <div class="row" style="padding:7px 10px;gap:8px;align-items:center">
      {% if r.icon %}<img src="{{ r.icon }}" style="width:34px;height:34px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:22px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.pal }}</div>
        <div style="font-size:12px;color:#7a5a1a">No.{{ r.index }}</div>
      </div>
      <div style="flex-shrink:0;text-align:right">
        <div style="font-size:15px;color:#7a1f1f">{{ r.rate }}%</div>
        {% if r.qty %}<div style="font-size:12px;color:#46200a">x{{ r.qty }}</div>{% endif %}
      </div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:12px;text-align:center;font-size:13px;color:#46200a;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:8px 11px">▶ {{ pager }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


ITEM_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    {% if icon %}<div style="flex:none;width:108px;height:108px;border-radius:20px;background:radial-gradient(circle at 50% 38%,rgba(232,198,106,.30),rgba(18,12,48,.55) 72%);border:2px solid rgba(232,198,106,.62);box-shadow:0 3px 15px rgba(0,0,0,.5),inset 0 0 18px rgba(232,198,106,.18);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:92px;height:92px;object-fit:contain;filter:drop-shadow(0 3px 8px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:72px">🎒</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill soft">📦 {{ type }}</span></div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="font-size:15px;color:#e9e0f5;line-height:1.9;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div>
    {% if price or sphere %}<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:13px">
      {% if price %}<span style="display:inline-flex;align-items:center;gap:5px;background:linear-gradient(135deg,rgba(232,198,106,.24),rgba(232,198,106,.07));border:1px solid rgba(232,198,106,.5);border-radius:11px;padding:5px 12px;font-size:14px;color:#f3e3b0">💰 商人价 <b style="color:#ffd86b">{{ price }}</b> 金币</span>{% endif %}
      {% if sphere %}<span style="display:inline-flex;align-items:center;gap:5px;background:linear-gradient(135deg,rgba(124,252,154,.2),rgba(124,252,154,.06));border:1px solid rgba(124,252,154,.45);border-radius:11px;padding:5px 12px;font-size:14px;color:#bff7cc">🎯 捕获力 <b style="color:#9effb6">×{{ sphere.cap }}</b></span>
      <span style="display:inline-flex;align-items:center;gap:5px;background:linear-gradient(135deg,rgba(160,140,255,.2),rgba(160,140,255,.06));border:1px solid rgba(160,140,255,.45);border-radius:11px;padding:5px 12px;font-size:14px;color:#cfc4ff">⭐ 品阶 <b style="color:#c9bbff">{{ sphere.rank }}</b></span>{% endif %}
    </div>{% endif %}
    {% if materials %}<div class="sec-t" style="margin-top:15px">🔨 制作材料</div>
    <div style="display:flex;flex-direction:column;gap:8px">
      {% for m in materials %}
      <div style="display:flex;align-items:center;gap:10px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.16);border-radius:12px;padding:7px 12px">
        {% if m.icon %}<img src="{{ m.icon }}" style="width:34px;height:34px;object-fit:contain">{% else %}<span style="font-size:22px">📦</span>{% endif %}
        <span style="flex:1;font-size:14px;color:#ece3f7">{{ m.name }}</span>
        <span style="font-size:15px;font-weight:800;color:#e8c466">×{{ m.count }}</span>
      </div>
      {% endfor %}
    </div>{% endif %}
    {% if benches %}<div class="sec-t" style="margin-top:14px">🛠️ 制作台</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for b in benches %}<span class="pill soft">{{ b }}</span>{% endfor %}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


ITEM_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:104px;height:104px;background:rgba(214,184,124,.3);border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:86px;height:86px;object-fit:contain;image-rendering:pixelated"></div>{% else %}<div style="flex:none;font-size:64px">▤</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill">{{ type }}</span></div>
    </div>
  </div></div>
  <div class="frame">
    <div style="font-size:15px;color:#382207;line-height:1.9;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div>
    {% if price or sphere %}<div style="display:flex;flex-wrap:wrap;gap:7px;margin-top:12px">
      {% if price %}<span style="background:rgba(156,107,26,.22);border:2px solid #6a4524;padding:4px 10px;font-size:13px;color:#46200a">💰 商人价 {{ price }} 金币</span>{% endif %}
      {% if sphere %}<span style="background:rgba(31,122,54,.18);border:2px solid #6a4524;padding:4px 10px;font-size:13px;color:#1d5a2a">🎯 捕获力 ×{{ sphere.cap }}</span>
      <span style="background:rgba(122,74,160,.18);border:2px solid #6a4524;padding:4px 10px;font-size:13px;color:#4a2a6a">⭐ 品阶 {{ sphere.rank }}</span>{% endif %}
    </div>{% endif %}
    {% if materials %}<div class="sec-t" style="margin-top:14px">制作材料</div>
    <div style="display:flex;flex-direction:column;gap:7px">
      {% for m in materials %}
      <div style="display:flex;align-items:center;gap:9px;background:rgba(221,198,149,0.5);border:2px solid #6a4524;padding:6px 11px">
        {% if m.icon %}<img src="{{ m.icon }}" style="width:32px;height:32px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:20px">▦</span>{% endif %}
        <span style="flex:1;font-size:14px;color:#382207">{{ m.name }}</span>
        <span style="font-size:14px;color:#8f1212">×{{ m.count }}</span>
      </div>
      {% endfor %}
    </div>{% endif %}
    {% if benches %}<div class="sec-t" style="margin-top:13px">制作台</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for b in benches %}<span class="pill">{{ b }}</span>{% endfor %}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 物品分类菜单 ----------------
ITEMCAT_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🎒 物品图鉴</div>
    <div class="subtitle">共 {{ total }} 件 · 选择分类浏览</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:9px">
      {% for c in cats %}
      <div style="display:flex;align-items:center;gap:10px;padding:11px 13px;border-radius:13px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.18)">
        <span style="font-size:23px">{{ c.emoji }}</span>
        <span style="font-size:15px;font-weight:700;color:#f3ecd2">{{ c.name }}</span>
        <span style="margin-left:auto;font-size:13px;color:#c9bfe6;font-weight:700">{{ c.count }}</span>
      </div>
      {% endfor %}
    </div>
    <div style="margin-top:14px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 发送「/帕鲁物品 武器」浏览某类 · 「/帕鲁物品 羊毛」查详情</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


ITEMCAT_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">▤ 物品图鉴</div>
    <div class="subtitle">共 {{ total }} 件 · 选择分类浏览</div>
  </div></div>
  <div class="frame">
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">
      {% for c in cats %}
      <div style="display:flex;align-items:center;gap:9px;padding:10px 11px;background:rgba(214,184,124,.22);border:2px solid #6b4a24">
        <span style="font-size:22px">{{ c.emoji }}</span>
        <span style="font-size:15px;font-weight:700;color:#2c1a0a">{{ c.name }}</span>
        <span style="margin-left:auto;font-size:13px;color:#574012;font-weight:700">{{ c.count }}</span>
      </div>
      {% endfor %}
    </div>
    <div style="margin-top:13px;text-align:center;font-size:13px;color:#2c1a0a;background:rgba(255,247,224,.55);border:2px solid #6b4a24;padding:8px 12px">▶ 发送「/帕鲁物品 武器」浏览某类 · 「/帕鲁物品 羊毛」查详情</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 设施图鉴 ----------------
FACILITY_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    {% if icon %}<div style="flex:none;width:108px;height:108px;border-radius:20px;background:radial-gradient(circle at 50% 38%,rgba(232,198,106,.30),rgba(18,12,48,.55) 72%);border:2px solid rgba(232,198,106,.62);box-shadow:0 3px 15px rgba(0,0,0,.5),inset 0 0 18px rgba(232,198,106,.18);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:92px;height:92px;object-fit:contain;filter:drop-shadow(0 3px 8px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:72px">🏗️</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">{% if category %}<span class="pill soft">🧱 {{ category }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="font-size:15px;color:#e9e0f5;line-height:1.9;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div>
    {% if materials %}<div class="sec-t" style="margin-top:15px">🔨 建造材料</div>
    <div style="display:flex;flex-direction:column;gap:8px">
      {% for m in materials %}
      <div style="display:flex;align-items:center;gap:10px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.16);border-radius:12px;padding:7px 12px">
        {% if m.icon %}<img src="{{ m.icon }}" style="width:34px;height:34px;object-fit:contain">{% else %}<span style="font-size:22px">📦</span>{% endif %}
        <span style="flex:1;font-size:14px;color:#ece3f7">{{ m.name }}</span>
        <span style="font-size:15px;font-weight:800;color:#e8c466">×{{ m.count }}</span>
      </div>
      {% endfor %}
    </div>
    {% if build %}<div style="margin-top:11px;font-size:13px;color:#cfc1ea;line-height:1.6;background:rgba(99,102,241,.14);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:10px 13px">{{ build }}</div>{% endif %}{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


FACILITY_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:104px;height:104px;background:rgba(214,184,124,.3);border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:86px;height:86px;object-fit:contain;image-rendering:pixelated"></div>{% else %}<div style="flex:none;font-size:64px">▣</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">{% if category %}<span class="pill">{{ category }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="frame">
    <div style="font-size:15px;color:#382207;line-height:1.9;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div>
    {% if materials %}<div class="sec-t" style="margin-top:14px">建造材料</div>
    <div style="display:flex;flex-direction:column;gap:7px">
      {% for m in materials %}
      <div style="display:flex;align-items:center;gap:9px;background:rgba(221,198,149,0.5);border:2px solid #6a4524;padding:6px 11px">
        {% if m.icon %}<img src="{{ m.icon }}" style="width:32px;height:32px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:20px">▦</span>{% endif %}
        <span style="flex:1;font-size:14px;color:#382207">{{ m.name }}</span>
        <span style="font-size:14px;color:#8f1212">×{{ m.count }}</span>
      </div>
      {% endfor %}
    </div>
    {% if build %}<div style="margin-top:10px;font-size:13px;color:#574012;line-height:1.6;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:9px 12px">{{ build }}</div>{% endif %}{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 科技图鉴 ----------------
TECH_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    {% if icon %}<div style="flex:none;width:108px;height:108px;border-radius:20px;background:radial-gradient(circle at 50% 38%,rgba(232,198,106,.30),rgba(18,12,48,.55) 72%);border:2px solid rgba(232,198,106,.62);box-shadow:0 3px 15px rgba(0,0,0,.5),inset 0 0 18px rgba(232,198,106,.18);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:92px;height:92px;object-fit:contain;filter:drop-shadow(0 3px 8px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:72px">🔬</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        {% if is_boss %}<span class="pill" style="background:rgba(180,90,230,.28);border-color:rgba(200,140,255,.5)">⭐ 古代科技</span>{% endif %}
        {% if level %}<span class="pill soft">🔓 解锁 Lv.{{ level }}</span>{% endif %}
        {% if points %}<span class="pill soft">💠 {{ points }} 技术点</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="font-size:15px;color:#e9e0f5;line-height:1.9;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div>
    {% if unlock %}<div class="sec-t" style="margin-top:15px">解锁条件</div>
    <div style="font-size:14px;color:#cfc1ea;line-height:1.75;white-space:pre-line;background:rgba(99,102,241,.14);border:1px solid rgba(232,198,106,.22);border-radius:13px;padding:12px 15px">{{ unlock }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


TECH_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:104px;height:104px;background:rgba(214,184,124,.3);border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:86px;height:86px;object-fit:contain;image-rendering:pixelated"></div>{% else %}<div style="flex:none;font-size:64px">⚙</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        {% if is_boss %}<span class="pill">⭐ 古代科技</span>{% endif %}
        {% if level %}<span class="pill">🔓 Lv.{{ level }}</span>{% endif %}
        {% if points %}<span class="pill">💠 {{ points }} 点</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="frame">
    <div style="font-size:15px;color:#382207;line-height:1.9;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div>
    {% if unlock %}<div class="sec-t" style="margin-top:14px">解锁条件</div>
    <div style="font-size:14px;color:#574012;line-height:1.75;white-space:pre-line;background:rgba(221,198,149,0.55);border:2px solid #6a4524;padding:11px 14px">{{ unlock }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 研究所(1.0 新增) ----------------
LAB_OVERVIEW_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🔬 帕鲁研究所</div>
    <div class="subtitle"><span class="pill soft">共 {{ total }} 项研究</span><span class="pill soft">9 大工作适性</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="font-size:14px;color:#cfc1ea;line-height:1.75;margin-bottom:14px">在据点建造「研究所」后，投入材料与帕鲁工时研究各类工作适性的<b style="color:#e8c466">全局增益</b>(工作速度 / 据点战力 / 孵化 / 远征 等)，效果对全服帕鲁生效。</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:11px">
      {% for c in cats %}
      <div style="display:flex;flex-direction:column;align-items:center;padding:14px 6px 11px;border-radius:14px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.2)">
        <div style="font-size:38px;line-height:1">{{ c.emoji }}</div>
        <div style="margin-top:7px;font-size:15px;font-weight:800;color:#ece3f7">{{ c.name }}</div>
        <div style="margin-top:4px;font-size:12px;color:#b9a9d6">{{ c.count }} 项 · <span style="color:#7cfc9a">{{ c.essential }} 必需</span></div>
      </div>{% endfor %}
    </div>
    <div style="margin-top:15px;font-size:13px;color:#9c8fc0;line-height:1.7">发 <b style="color:#e8c466">/帕鲁研究所 手工</b> 看某类全部研究；发 <b style="color:#e8c466">/帕鲁研究所 &lt;研究名&gt;</b> 看单项材料/前置。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

LAB_LIST_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ emoji }} {{ category }}</div>
    <div class="subtitle"><span class="pill soft">{{ items|length }} 项研究</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:flex;flex-direction:column;gap:8px">
      {% for it in items %}
      <div style="display:flex;align-items:center;gap:10px;padding:10px 13px;border-radius:12px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.16)">
        {% if it.essential %}<span style="flex:none;font-size:11px;font-weight:800;color:#0d0820;background:#7cfc9a;border-radius:6px;padding:2px 6px">必需</span>{% endif %}
        <div style="flex:1;min-width:0">
          <div style="font-size:15px;font-weight:700;color:#ece3f7">{{ it.name }}</div>
          {% if it.effect %}<div style="font-size:12.5px;color:#9effb6;margin-top:2px">{{ it.effect }}</div>{% endif %}
        </div>
      </div>{% endfor %}
    </div>
    <div style="margin-top:13px;font-size:13px;color:#9c8fc0">发 <b style="color:#e8c466">/帕鲁研究所 &lt;研究名&gt;</b> 看材料与前置。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

LAB_DETAIL_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    <div style="flex:none;font-size:72px">{{ emoji }}</div>
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        <span class="pill soft">{{ emoji }} {{ category }}</span>
        {% if essential %}<span class="pill" style="background:rgba(124,252,154,.22);border-color:rgba(124,252,154,.5)">✔ 必需研究</span>{% endif %}
        {% if work %}<span class="pill soft">⏳ {{ work }} 工时</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% if effect %}<div class="sec-t">研究效果</div>
    <div style="font-size:16px;color:#9effb6;font-weight:700;background:rgba(124,252,154,.1);border:1px solid rgba(124,252,154,.3);border-radius:12px;padding:11px 15px">{{ effect }}</div>{% endif %}
    {% if materials %}<div class="sec-t" style="margin-top:15px">所需材料</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px">
      {% for m in materials %}<span style="display:inline-flex;align-items:center;gap:6px;background:rgba(12,8,38,.5);border:1px solid rgba(232,198,106,.22);border-radius:11px;padding:6px 12px;font-size:14px;color:#ece3f7">{{ m.name }} <b style="color:#e8c466">×{{ m.count }}</b></span>{% endfor %}
    </div>{% endif %}
    {% if prereq %}<div class="sec-t" style="margin-top:15px">前置研究</div>
    <div style="font-size:14px;color:#cfc1ea;background:rgba(99,102,241,.14);border:1px solid rgba(232,198,106,.22);border-radius:12px;padding:10px 15px">🔗 需先完成「{{ prereq }}」</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


# ---------------- 技能果实详情(1.0) ----------------
SKILLFRUIT_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    {% if icon %}<div style="flex:none;width:108px;height:108px;border-radius:20px;background:radial-gradient(circle at 50% 38%,{{ color }}44,rgba(18,12,48,.55) 72%);border:2px solid {{ color }}99;box-shadow:0 3px 15px rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:90px;height:90px;object-fit:contain;filter:drop-shadow(0 3px 8px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:72px">🍐</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ fruit_name }}</div>
      <div class="subtitle">
        <span class="pill" style="background:{{ color }}33;border-color:{{ color }}88">{{ emoji }} {{ element }}属性</span>
        {% if power and power != "0" %}<span class="pill soft">⚔ 威力 {{ power }}</span>{% endif %}
        {% if cooldown %}<span class="pill soft">⏱ 冷却 {{ cooldown }}s</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% if effect %}<span class="pill" style="background:rgba(124,252,154,.16);border-color:rgba(124,252,154,.4);color:#9effb6;margin-bottom:11px">{{ effect }}</span>{% endif %}
    <div style="font-size:15px;color:#e9e0f5;line-height:1.9;white-space:pre-line;word-break:break-word">{{ desc or "（暂无描述）" }}</div>
    <div class="sec-t" style="margin-top:15px">用法</div>
    <div style="font-size:14px;color:#cfc1ea;line-height:1.75;background:rgba(99,102,241,.14);border:1px solid rgba(232,198,106,.22);border-radius:13px;padding:12px 15px">🍐 将此技能果实喂给帕鲁，即可让它学会主动技能<b style="color:#e8c466">「{{ tech }}」</b>。技能果实可在世界各地的<b>宝箱</b>等处获得。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# ---------------- 植入体详情(1.0) ----------------
IMPLANT_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    {% if icon %}<div style="flex:none;width:108px;height:108px;border-radius:20px;background:radial-gradient(circle at 50% 38%,rgba(180,90,230,.30),rgba(18,12,48,.55) 72%);border:2px solid rgba(200,140,255,.6);box-shadow:0 3px 15px rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:90px;height:90px;object-fit:contain;filter:drop-shadow(0 3px 8px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:72px">🧬</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        {% if rank %}<span class="pill" style="background:rgba(232,198,106,.24)">{{ "★" * (rank if rank <= 5 else 5) }} Rank{{ rank }}</span>{% endif %}
        {% if consumable %}<span class="pill" style="background:rgba(245,166,35,.22);border-color:rgba(245,166,35,.5)">🔥 耗材·一次性</span>{% else %}<span class="pill soft">♻ 可反复植入</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">赋予词条</div>
    <div style="display:flex;align-items:center;gap:10px;background:rgba(180,90,230,.12);border:1px solid rgba(200,140,255,.3);border-radius:13px;padding:12px 15px">
      <span style="font-size:17px;font-weight:800;color:#d8b0ff">「{{ passive }}」</span>
      {% if effect %}<span style="font-size:14px;color:{% if sign < 0 %}#ff9b9b{% else %}#9effb6{% endif %}">{{ effect }}</span>{% endif %}
    </div>
    <div class="sec-t" style="margin-top:15px">用法</div>
    <div style="font-size:14px;color:#cfc1ea;line-height:1.75;background:rgba(99,102,241,.14);border:1px solid rgba(232,198,106,.22);border-radius:13px;padding:12px 15px">🧬 在据点的<b>帕鲁改造设备</b>上，用此植入体为帕鲁植入被动词条<b style="color:#e8c466">「{{ passive }}」</b>。{% if consumable %}耗材型植入体使用后消耗，效果通常更强力。{% else %}可反复植入或替换词条。{% endif %}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# ---------------- 网格列表(模糊搜索/全表浏览，分页) ----------------
GRID_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ emoji }} {{ title }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:repeat(""" + str(GRID_COLS) + """,1fr);gap:9px">
      {% for c in cells %}
      <div style="position:relative;display:flex;flex-direction:column;align-items:center;padding:11px 3px 8px;border-radius:13px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.16)">
        <div style="position:absolute;top:4px;left:4px;font-size:10px;font-weight:800;color:#0d0820;background:linear-gradient(135deg,#f3d98a,#e8c66a);border-radius:6px;padding:1px 5px;box-shadow:0 1px 3px rgba(0,0,0,.4)">{{ c.no }}</div>
        {% if c.icon %}<img src="{{ c.icon }}" style="width:60px;height:60px;object-fit:contain;filter:drop-shadow(0 2px 5px rgba(0,0,0,.5))">{% else %}<div style="width:60px;height:60px;display:flex;align-items:center;justify-content:center;font-size:30px">❔</div>{% endif %}
        <div style="margin-top:6px;font-size:11.5px;color:#ece3f7;text-align:center;line-height:1.25;height:2.5em;overflow:hidden;word-break:break-all">{{ c.name }}</div>
      </div>
      {% endfor %}
    </div>
    {% if pager %}<div style="margin-top:15px;text-align:center;font-size:13px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


GRID_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ emoji }} {{ title }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="frame">
    <div style="display:grid;grid-template-columns:repeat(""" + str(GRID_COLS) + """,1fr);gap:8px">
      {% for c in cells %}
      <div style="position:relative;display:flex;flex-direction:column;align-items:center;padding:10px 3px 7px;background:rgba(214,184,124,.22);border:2px solid #6b4a24">
        <div style="position:absolute;top:2px;left:2px;font-size:10px;font-weight:700;color:#fff7e0;background:#6b4a24;padding:0 4px">{{ c.no }}</div>
        {% if c.icon %}<img src="{{ c.icon }}" style="width:58px;height:58px;object-fit:contain;image-rendering:pixelated">{% else %}<div style="width:58px;height:58px;display:flex;align-items:center;justify-content:center;font-size:28px">▢</div>{% endif %}
        <div style="margin-top:5px;font-size:11.5px;color:#382207;text-align:center;line-height:1.25;height:2.5em;overflow:hidden;word-break:break-all">{{ c.name }}</div>
      </div>
      {% endfor %}
    </div>
    {% if pager %}<div style="margin-top:14px;text-align:center;font-size:13px;color:#2c1a0a;background:rgba(255,247,224,.55);border:2px solid #6b4a24;padding:8px 12px">▶ {{ pager }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 在线玩家地图 ----------------
MAP_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🗺️ 在线玩家分布</div>
    <div class="subtitle">{{ subtitle }}</div>
  </div></div>
  <div style="position:relative;width:100%;border-radius:16px;overflow:hidden;border:1px solid rgba(232,198,106,.3);box-shadow:0 4px 16px rgba(0,0,0,.45)">
    <img src="{{ mapimg }}" style="display:block;width:100%">
    {% for p in players %}
    <div style="position:absolute;left:{{ p.left }}%;top:{{ p.top }}%;transform:translate(-50%,-100%);width:24px;height:31px;z-index:5">
      <div style="position:absolute;top:0;left:0;width:24px;height:24px;border-radius:50%;background:radial-gradient(circle at 55% 40%,#ff9a9a,#d12f2f);border:2px solid #fff;box-shadow:0 2px 5px rgba(0,0,0,.65)"></div>
      <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:9px solid #d12f2f"></div>
      <div style="position:absolute;top:0;left:0;width:24px;height:24px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:800;text-shadow:0 1px 2px rgba(0,0,0,.5)">{{ p.no }}</div>
    </div>
    {% endfor %}
  </div>
  <div class="glass" style="margin-top:12px">""" + _GEMS + """
    {% for p in players %}
    <div style="display:flex;align-items:center;gap:9px;padding:7px 2px;{% if not loop.last %}border-bottom:1px solid rgba(232,198,106,.12){% endif %}">
      <span style="flex:none;width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#f3d98a,#e8c66a);color:#0d0820;font-size:13px;font-weight:800;text-align:center;line-height:24px">{{ p.no }}</span>
      <span style="font-size:15px;font-weight:700;color:#f3ecd2">{{ p.name }}</span>
      <span class="pill soft">Lv.{{ p.level }}</span>
      <span style="margin-left:auto;text-align:right">
        <span style="font-size:13.5px;color:#c9bfe6">📍 {{ p.region }}</span>
        <span style="display:block;font-size:11.5px;color:#9a93b8">坐标 {{ p.coord }}</span>
      </span>
    </div>
    {% endfor %}
  </div>
  """ + _FOOT + """
</div></body></html>"""


MAP_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">▦ 在线玩家分布</div>
    <div class="subtitle">{{ subtitle }}</div>
  </div></div>
  <div style="position:relative;width:100%;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.4)">
    <img src="{{ mapimg }}" style="display:block;width:100%;image-rendering:auto">
    {% for p in players %}
    <div style="position:absolute;left:{{ p.left }}%;top:{{ p.top }}%;transform:translate(-50%,-100%);width:24px;height:29px;z-index:5">
      <div style="position:absolute;top:0;left:0;width:24px;height:21px;background:#d12f2f;border:2px solid #fff7e0"></div>
      <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:8px solid #d12f2f"></div>
      <div style="position:absolute;top:0;left:0;width:24px;height:21px;display:flex;align-items:center;justify-content:center;color:#fff7e0;font-size:12px;font-weight:700">{{ p.no }}</div>
    </div>
    {% endfor %}
  </div>
  <div class="frame" style="margin-top:12px">
    {% for p in players %}
    <div style="display:flex;align-items:center;gap:9px;padding:6px 2px;{% if not loop.last %}border-bottom:2px solid rgba(107,74,36,.3){% endif %}">
      <span style="flex:none;width:24px;height:24px;background:#6b4a24;color:#fff7e0;font-size:13px;font-weight:700;text-align:center;line-height:24px">{{ p.no }}</span>
      <span style="font-size:15px;font-weight:700;color:#2c1a0a">{{ p.name }}</span>
      <span class="pill">Lv.{{ p.level }}</span>
      <span style="margin-left:auto;text-align:right">
        <span style="font-size:13.5px;color:#574012">▸ {{ p.region }}</span>
        <span style="display:block;font-size:11.5px;color:#7a6a4a">坐标 {{ p.coord }}</span>
      </span>
    </div>
    {% endfor %}
  </div>
  """ + _PF + """
</div></body></html>"""


ELEMENT_TMPL = _HEAD + """
  .ecard { border-radius:16px; padding:12px 13px; border:1px solid rgba(255,255,255,.12); }
  .erow { display:flex; align-items:center; gap:6px; flex-wrap:wrap; font-size:13px; color:#f3ecd2; margin-top:6px; }
  .etag { display:inline-flex; align-items:center; gap:3px; padding:2px 8px; border-radius:9px; font-size:13px; font-weight:700; }
</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">⚔️ 帕鲁属性克制图</div>
    <div class="subtitle"><span class="pill soft">9 系属性</span><span class="pill soft">克制方造成 ×1.5 伤害</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    {% for e in elems %}
      <div class="ecard" style="background:linear-gradient(135deg,{{ e.color }}33,{{ e.color }}11);border-color:{{ e.color }}88">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:24px">{{ e.emoji }}</span>
          <span style="font-size:18px;font-weight:800;color:{{ e.color }}">{{ e.cn }}属性</span>
        </div>
        <div class="erow">
          <span style="color:#7CFC9A;font-weight:700;min-width:38px">克制</span>
          {% if e.strong %}{% for s in e.strong %}<span class="etag" style="background:#7CFC9A22;color:#9effb6">{{ s.emoji }} {{ s.cn }}</span>{% endfor %}{% else %}<span style="color:#9a93b8">无</span>{% endif %}
        </div>
        <div class="erow">
          <span style="color:#ff8a8a;font-weight:700;min-width:38px">被克</span>
          {% if e.weak %}{% for w in e.weak %}<span class="etag" style="background:#ff6b6b22;color:#ffb0b0">{{ w.emoji }} {{ w.cn }}</span>{% endfor %}{% else %}<span style="color:#9a93b8">无</span>{% endif %}
        </div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:14px;font-size:12.5px;color:#b9a9d6;line-height:1.7">💡 用克制属性的帕鲁/技能攻击，伤害提升约 50%；被克制时己方更脆。捕捉强力帕鲁时，带克制属性更省球。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

ELEMENT_PIX = _PH + """
  .ecard { padding:11px 12px; border:2px solid #6b4a24; }
  .erow { display:flex; align-items:center; gap:5px; flex-wrap:wrap; font-size:13px; color:#382207; margin-top:5px; }
  .etag { display:inline-flex; align-items:center; gap:3px; padding:1px 7px; border:2px solid #6a4524; font-size:12px; }
</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">⚔ 帕鲁属性克制图</div>
    <div class="subtitle"><span class="pill">9 系属性</span><span class="pill">克制方 x1.5 伤害</span></div>
  </div></div>
  <div class="frame">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:9px">
    {% for e in elems %}
      <div class="ecard" style="background:{{ e.color }}22">
        <div style="display:flex;align-items:center;gap:7px">
          <span style="font-size:22px">{{ e.emoji }}</span>
          <span style="font-size:17px;color:#46200a">{{ e.cn }}属性</span>
        </div>
        <div class="erow"><span style="color:#1d7a36;min-width:34px">克制</span>{% if e.strong %}{% for s in e.strong %}<span class="etag" style="background:#bdf0c8">{{ s.emoji }}{{ s.cn }}</span>{% endfor %}{% else %}<span style="color:#7a6a4a">无</span>{% endif %}</div>
        <div class="erow"><span style="color:#8f1212;min-width:34px">被克</span>{% if e.weak %}{% for w in e.weak %}<span class="etag" style="background:#f3c4c4">{{ w.emoji }}{{ w.cn }}</span>{% endfor %}{% else %}<span style="color:#7a6a4a">无</span>{% endif %}</div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:13px;font-size:12.5px;color:#574012;line-height:1.7">用克制属性攻击伤害+约50%；捕捉强帕鲁带克制属性更省球。</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 栖息区域（/帕鲁栖息区域） ----------------
HABITAT_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:84px;height:84px;border-radius:18px;background:radial-gradient(circle at 50% 38%,{{color}}44,rgba(18,12,48,.5) 72%);border:2px solid {{color}}aa;display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:72px;height:72px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))"></div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">🗺️ {{ name }} · 栖息分布</div>
      <div class="subtitle"><span class="pill soft">No.{{ index }}</span>{% for e in elements %}<span class="pill soft">{{ e }}</span>{% endfor %}{% if nocturnal %}<span class="pill soft">🌙 夜行</span>{% endif %}</div>
    </div>
  </div></div>
  <div style="position:relative;width:100%;border-radius:16px;overflow:hidden;border:1px solid {{color}}66;box-shadow:0 4px 16px rgba(0,0,0,.45)">
    <img src="{{ mapimg }}" style="display:block;width:100%">
    <div style="position:absolute;inset:0;mix-blend-mode:screen">
      {% for pt in points %}<div style="position:absolute;left:{{pt.l}}%;top:{{pt.t}}%;width:26px;height:26px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,{{color}}d0,{{color}}00 62%)"></div>{% endfor %}
    </div>
  </div>
  <div class="glass" style="margin-top:12px">""" + _GEMS + """
    <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:13.5px;color:#e9e0f5">
      <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:13px;height:13px;border-radius:50%;background:{{color}};display:inline-block;box-shadow:0 0 7px {{color}}"></span>栖息热区</span>
      <span class="pill soft">{{ count }} 个刷新点</span>
      {% if has_day and has_night %}<span class="pill soft">日夜均刷</span>{% elif nocturnal %}<span class="pill soft">夜间为主</span>{% endif %}
    </div>
    {% if regions %}<div class="sec-t" style="margin-top:13px">📍 主要出没区域</div>
    <div style="display:flex;flex-direction:column;gap:7px">
      {% for r in regions %}
      <div style="display:flex;align-items:center;gap:9px">
        <span style="flex:none;width:96px;font-size:13px;color:#ece3f7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</span>
        <span style="flex:1;height:11px;border-radius:6px;background:rgba(12,8,38,.5);overflow:hidden"><span style="display:block;height:100%;width:{{ r.pct }}%;background:linear-gradient(90deg,{{color}}88,{{color}})"></span></span>
        <span style="flex:none;width:38px;text-align:right;font-size:12.5px;color:#c9bfe6">{{ r.pct }}%</span>
      </div>
      {% endfor %}
    </div>{% endif %}
    <div style="margin-top:13px;font-size:12px;color:#b9a9d6;line-height:1.7">💡 色块越亮表示该处刷新越密集；区域占比按刷新点落点就近估算，仅供参考。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

HABITAT_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    {% if icon %}<div style="flex:none;width:80px;height:80px;background:{{color}}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:66px;height:66px;object-fit:contain;image-rendering:pixelated"></div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">▦ {{ name }} · 栖息分布</div>
      <div class="subtitle"><span class="pill">No.{{ index }}</span>{% for e in elements %}<span class="pill">{{ e }}</span>{% endfor %}{% if nocturnal %}<span class="pill">夜行</span>{% endif %}</div>
    </div>
  </div></div>
  <div style="position:relative;width:100%;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.4)">
    <img src="{{ mapimg }}" style="display:block;width:100%">
    <div style="position:absolute;inset:0;mix-blend-mode:screen">
      {% for pt in points %}<div style="position:absolute;left:{{pt.l}}%;top:{{pt.t}}%;width:26px;height:26px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,{{color}}d0,{{color}}00 62%)"></div>{% endfor %}
    </div>
  </div>
  <div class="frame" style="margin-top:12px">
    <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:13.5px;color:#382207">
      <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:12px;height:12px;background:{{color}};display:inline-block;border:1px solid #2c1a0a"></span>栖息热区</span>
      <span class="pill">{{ count }} 个刷新点</span>
      {% if has_day and has_night %}<span class="pill">日夜均刷</span>{% elif nocturnal %}<span class="pill">夜间为主</span>{% endif %}
    </div>
    {% if regions %}<div class="sec-t" style="margin-top:12px">主要出没区域</div>
    <div style="display:flex;flex-direction:column;gap:6px">
      {% for r in regions %}
      <div style="display:flex;align-items:center;gap:8px">
        <span style="flex:none;width:96px;font-size:13px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</span>
        <span style="flex:1;height:11px;background:rgba(74,47,22,.25);border:1px solid #6a4524;overflow:hidden"><span style="display:block;height:100%;width:{{ r.pct }}%;background:{{color}}"></span></span>
        <span style="flex:none;width:36px;text-align:right;font-size:12.5px;color:#574012">{{ r.pct }}%</span>
      </div>
      {% endfor %}
    </div>{% endif %}
    <div style="margin-top:12px;font-size:12px;color:#574012;line-height:1.7">色块越亮表示刷新越密集；区域占比按刷新点就近估算，仅供参考。</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 推荐词条（/帕鲁推荐词条） ----------------
PASSREC_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:84px;height:84px;border-radius:18px;background:radial-gradient(circle at 50% 38%,{{color}}44,rgba(18,12,48,.5) 72%);border:2px solid {{color}}aa;display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:72px;height:72px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))"></div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">📜 {{ name }} · 推荐词条</div>
      <div class="subtitle"><span class="pill soft">No.{{ index }}</span>{% for e in elements %}<span class="pill soft">{{ e }}</span>{% endfor %}{% for r in roles %}<span class="pill soft">{{ r }}型</span>{% endfor %}</div>
    </div>
  </div></div>
  {% for sec in sections %}
  <div class="glass" style="margin-top:{% if loop.first %}0{% else %}11px{% endif %}">""" + _GEMS + """
    <div class="sec-t" style="color:{{ sec.color }}">{{ sec.title }}</div>
    <div style="display:flex;flex-direction:column;gap:8px">
      {% for it in sec['items'] %}
      <div style="display:flex;align-items:center;gap:10px;background:rgba(12,8,38,.42);border:1px solid {{ sec.color }}44;border-radius:12px;padding:8px 12px">
        <span style="flex:none;font-size:14px;font-weight:800;color:{{ sec.color }};min-width:74px">{{ it.name }}</span>
        <span style="flex:1;font-size:12.5px;color:#e9e0f5;line-height:1.45">{{ it.effect }}</span>
        <span style="flex:none;font-size:12px;color:#ffd86b;letter-spacing:1px">{{ it.stars }}</span>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
  <div class="glass" style="margin-top:11px">""" + _GEMS + """
    <div style="font-size:12px;color:#b9a9d6;line-height:1.75">💡 词条 ★ 越多越稀有。战斗帕鲁优先攻击/元素增伤，基地帕鲁优先工作速度，搬运/骑乘优先移速；「吸血鬼」让帕鲁夜间不睡持续干活。词条可在配种时遗传或用书本洗练。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

PASSREC_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    {% if icon %}<div style="flex:none;width:80px;height:80px;background:{{color}}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:66px;height:66px;object-fit:contain;image-rendering:pixelated"></div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">▣ {{ name }} · 推荐词条</div>
      <div class="subtitle"><span class="pill">No.{{ index }}</span>{% for e in elements %}<span class="pill">{{ e }}</span>{% endfor %}{% for r in roles %}<span class="pill">{{ r }}型</span>{% endfor %}</div>
    </div>
  </div></div>
  {% for sec in sections %}
  <div class="frame" style="margin-top:{% if loop.first %}0{% else %}10px{% endif %}">
    <div class="sec-t">{{ sec.title }}</div>
    <div style="display:flex;flex-direction:column;gap:7px">
      {% for it in sec['items'] %}
      <div style="display:flex;align-items:center;gap:9px;background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:6px 11px">
        <span style="flex:none;font-size:14px;color:#46200a;min-width:70px">{{ it.name }}</span>
        <span style="flex:1;font-size:12px;color:#382207;line-height:1.45">{{ it.effect }}</span>
        <span style="flex:none;font-size:12px;color:#8f1212;letter-spacing:1px">{{ it.stars }}</span>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
  <div class="frame" style="margin-top:10px">
    <div style="font-size:12px;color:#574012;line-height:1.75">词条 ★ 越多越稀有。战斗优先攻击/元素增伤，基地优先工作速度，搬运/骑乘优先移速；「吸血鬼」夜间不睡持续干活。</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# 支线任务 NPC 分组键 -> 中文
MISSION_GROUP_CN = {"Zoe": "佐伊", "Farmer": "农民", "Scholar": "学者", "Breeder": "驯养员",
                    "Ranger": "护林员", "Nomad": "淘金客", "Angler": "钓手",
                    "Kigurumi": "玩偶装", "": "其它委托"}


# ---------------- 任务详情（/帕鲁任务 <名>） ----------------
MISSION_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    <div style="flex:none;width:74px;height:74px;border-radius:18px;background:radial-gradient(circle at 50% 38%,{{tcolor}}44,rgba(18,12,48,.5) 72%);border:2px solid {{tcolor}}aa;display:flex;align-items:center;justify-content:center;font-size:38px">{{ emoji }}</div>
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill soft" style="color:{{tcolor}}">{{ tlabel }}</span>{% if order %}<span class="pill soft">主线 第 {{ order }}/32</span>{% endif %}{% if group %}<span class="pill soft">{{ group }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% if desc %}<div style="font-size:14.5px;color:#e9e0f5;line-height:1.85;white-space:pre-line">{{ desc }}</div>{% endif %}
    <div class="sec-t" style="margin-top:14px">🎯 目标</div>
    <div style="font-size:14px;color:#ece3f7;line-height:1.7">{{ objective or "按上方任务说明完成即可" }}{% if coords %}<br><span style="display:inline-flex;align-items:center;gap:5px;margin-top:6px;background:rgba(12,8,38,.5);border:1px solid rgba(232,198,106,.3);border-radius:10px;padding:4px 11px;font-size:13.5px;color:#f3e3b0">📍 地图坐标 <b style="color:#ffd86b">{{ coords }}</b></span>{% endif %}</div>
    {% if exp or rewards %}<div class="sec-t" style="margin-top:14px">🏅 任务奖励</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">
      {% if exp %}<span class="pill" style="background:linear-gradient(135deg,#f3d98a,#e8c66a);color:#2a1d05;font-weight:800">经验 +{{ exp }}</span>{% endif %}
      {% for r in rewards %}<span class="pill soft">{{ r.name }} ×{{ r.qty }}</span>{% endfor %}
    </div>{% endif %}
    {% if nextname %}<div class="sec-t" style="margin-top:14px">➡️ 下一环</div>
    <div style="font-size:14px;color:#c9bfe6">{{ nextname }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

MISSION_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    <div style="flex:none;width:70px;height:70px;background:{{tcolor}}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center;font-size:34px">{{ emoji }}</div>
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill">{{ tlabel }}</span>{% if order %}<span class="pill">主线 {{ order }}/32</span>{% endif %}{% if group %}<span class="pill">{{ group }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="frame">
    {% if desc %}<div style="font-size:14.5px;color:#382207;line-height:1.85;white-space:pre-line">{{ desc }}</div>{% endif %}
    <div class="sec-t" style="margin-top:13px">🎯 目标</div>
    <div style="font-size:14px;color:#46200a;line-height:1.7">{{ objective or "按上方任务说明完成即可" }}{% if coords %}<br><span style="display:inline-block;margin-top:6px;background:rgba(156,107,26,.2);border:2px solid #6a4524;padding:3px 10px;font-size:13px;color:#46200a">📍 坐标 {{ coords }}</span>{% endif %}</div>
    {% if exp or rewards %}<div class="sec-t" style="margin-top:13px">任务奖励</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">
      {% if exp %}<span class="pill" style="background:#e8c66a;color:#2a1d05">经验 +{{ exp }}</span>{% endif %}
      {% for r in rewards %}<span class="pill">{{ r.name }} x{{ r.qty }}</span>{% endfor %}
    </div>{% endif %}
    {% if nextname %}<div class="sec-t" style="margin-top:13px">下一环</div>
    <div style="font-size:14px;color:#574012">{{ nextname }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 任务列表（/帕鲁主线 /帕鲁支线） ----------------
MISSIONLIST_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ title }}</div>
    <div class="subtitle"><span class="pill soft">{{ subtitle }}</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for it in rows %}
    <div style="display:flex;align-items:center;gap:9px;padding:7px 2px;{% if not loop.last %}border-bottom:1px solid rgba(232,198,106,.12){% endif %}">
      <span style="flex:none;min-width:30px;height:24px;padding:0 6px;border-radius:7px;background:linear-gradient(135deg,#f3d98a,#e8c66a);color:#0d0820;font-size:12.5px;font-weight:800;text-align:center;line-height:24px">{{ it.tag }}</span>
      <span style="flex:none;font-size:14.5px;font-weight:700;color:#f3ecd2;max-width:42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ it.name }}</span>
      <span style="flex:1;font-size:12.5px;color:#b9a9d6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ it.brief }}</span>
    </div>
    {% endfor %}
    <div style="margin-top:12px;font-size:12px;color:#b9a9d6;line-height:1.7">💡 发「{{ detailhint }}」看某个任务的详细攻略{% if pagehint %}；{{ pagehint }}{% endif %}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

MISSIONLIST_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ title }}</div>
    <div class="subtitle"><span class="pill">{{ subtitle }}</span></div>
  </div></div>
  <div class="frame">
    {% for it in rows %}
    <div style="display:flex;align-items:center;gap:9px;padding:6px 2px;{% if not loop.last %}border-bottom:2px solid rgba(107,74,36,.3){% endif %}">
      <span style="flex:none;min-width:30px;height:24px;padding:0 6px;background:#6b4a24;color:#fff7e0;font-size:12.5px;font-weight:700;text-align:center;line-height:24px">{{ it.tag }}</span>
      <span style="flex:none;font-size:14.5px;font-weight:700;color:#2c1a0a;max-width:42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ it.name }}</span>
      <span style="flex:1;font-size:12.5px;color:#574012;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ it.brief }}</span>
    </div>
    {% endfor %}
    <div style="margin-top:11px;font-size:12px;color:#574012;line-height:1.7">发「{{ detailhint }}」看详细攻略{% if pagehint %}；{{ pagehint }}{% endif %}</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- Boss 详情（/帕鲁塔主 /帕鲁突袭 <名>） ----------------
BOSS_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:84px;height:84px;border-radius:18px;background:radial-gradient(circle at 50% 38%,{{color}}55,rgba(18,12,48,.5) 72%);border:2px solid {{color}}cc;display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:72px;height:72px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:48px">{{ emoji }}</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill soft" style="color:{{color}}">{{ catlabel }}</span>{% for e in elements %}<span class="pill soft">{{ e }}</span>{% endfor %}{% if difficulty %}<span class="pill soft">{{ difficulty }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div style="background:rgba(12,8,38,.42);border:1px solid {{color}}44;border-radius:12px;padding:10px 12px"><div style="font-size:12px;color:#b9a9d6">等级</div><div style="font-size:20px;font-weight:800;color:#f3ecd2">Lv.{{ level or "—" }}</div></div>
      <div style="background:rgba(12,8,38,.42);border:1px solid {{color}}44;border-radius:12px;padding:10px 12px"><div style="font-size:12px;color:#b9a9d6">生命值</div><div style="font-size:20px;font-weight:800;color:#ff9a9a">{{ hp or "—" }}</div></div>
    </div>
    {% if location %}<div class="sec-t" style="margin-top:13px">📍 所在</div><div style="font-size:14.5px;color:#ece3f7">{{ location }}</div>{% endif %}
    {% if drops %}<div class="sec-t" style="margin-top:13px">🎁 掉落</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for d in drops %}<span class="pill soft">{{ d }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:13px">⚔️ 攻略提示</div>
    <div style="font-size:13px;color:#c9bfe6;line-height:1.8">{{ tip }}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

BOSS_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    {% if icon %}<div style="flex:none;width:80px;height:80px;background:{{color}}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:66px;height:66px;object-fit:contain;image-rendering:pixelated"></div>{% else %}<div style="flex:none;font-size:44px">{{ emoji }}</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill">{{ catlabel }}</span>{% for e in elements %}<span class="pill">{{ e }}</span>{% endfor %}{% if difficulty %}<span class="pill">{{ difficulty }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="frame">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:9px">
      <div style="background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:9px 11px"><div style="font-size:12px;color:#574012">等级</div><div style="font-size:19px;color:#46200a">Lv.{{ level or "—" }}</div></div>
      <div style="background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:9px 11px"><div style="font-size:12px;color:#574012">生命值</div><div style="font-size:19px;color:#8f1212">{{ hp or "—" }}</div></div>
    </div>
    {% if location %}<div class="sec-t" style="margin-top:12px">所在</div><div style="font-size:14.5px;color:#46200a">{{ location }}</div>{% endif %}
    {% if drops %}<div class="sec-t" style="margin-top:12px">掉落</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for d in drops %}<span class="pill">{{ d }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:12px">攻略提示</div>
    <div style="font-size:13px;color:#574012;line-height:1.8">{{ tip }}</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 帕鲁对比（/帕鲁对比 <A> <B>） ----------------
COMPARE_TMPL = _HEAD + """
  .cmpval { flex:1; font-size:17px; font-weight:800; }
  .cmpwin { color:#9effb6; }
  .cmplose { color:#8a82a8; }
  .cmpeq { color:#e9e0f5; }
</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:stretch;justify-content:space-between;width:100%;gap:6px;position:relative;z-index:2">
    <div style="flex:1;text-align:center">
      <div style="width:90px;height:90px;margin:0 auto;border-radius:18px;background:radial-gradient(circle at 50% 38%,{{ left.color }}44,rgba(18,12,48,.5) 72%);border:2px solid {{ left.color }}aa;display:flex;align-items:center;justify-content:center">{% if left.icon %}<img src="{{ left.icon }}" style="width:78px;height:78px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))">{% else %}<span style="font-size:44px">📕</span>{% endif %}</div>
      <div style="font-size:18px;font-weight:800;color:#f3ecd2;margin-top:6px">{{ left.name }}</div>
      <div style="font-size:12px;color:#c9bfe6">{{ left.elements }}</div>
    </div>
    <div style="flex:none;display:flex;align-items:center"><div style="width:50px;height:50px;border-radius:50%;background:linear-gradient(135deg,#f3d98a,#e8c466);box-shadow:0 0 16px rgba(232,198,106,.6),inset 0 0 10px rgba(255,255,255,.4);display:flex;align-items:center;justify-content:center;color:#2a1d05;font-size:20px;font-weight:900;font-style:italic;transform:rotate(-8deg)">VS</div></div>
    <div style="flex:1;text-align:center">
      <div style="width:90px;height:90px;margin:0 auto;border-radius:18px;background:radial-gradient(circle at 50% 38%,{{ right.color }}44,rgba(18,12,48,.5) 72%);border:2px solid {{ right.color }}aa;display:flex;align-items:center;justify-content:center">{% if right.icon %}<img src="{{ right.icon }}" style="width:78px;height:78px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))">{% else %}<span style="font-size:44px">📕</span>{% endif %}</div>
      <div style="font-size:18px;font-weight:800;color:#f3ecd2;margin-top:6px">{{ right.name }}</div>
      <div style="font-size:12px;color:#c9bfe6">{{ right.elements }}</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for s in stats %}
    <div style="display:flex;align-items:center;padding:8px 4px;{% if not loop.last %}border-bottom:1px solid rgba(232,198,106,.12){% endif %}">
      <span class="cmpval {{ 'cmpwin' if s.lwin else ('cmplose' if s.rwin else 'cmpeq') }}" style="text-align:right">{{ s.lval }}{% if s.lwin %} ▲{% endif %}</span>
      <span style="flex:none;width:96px;text-align:center;font-size:13px;color:#b9a9d6">{{ s.label }}</span>
      <span class="cmpval {{ 'cmpwin' if s.rwin else ('cmplose' if s.lwin else 'cmpeq') }}" style="text-align:left">{% if s.rwin %}▲ {% endif %}{{ s.rval }}</span>
    </div>
    {% endfor %}
    {% if works %}<div class="sec-t" style="margin-top:13px">🔨 工作适性（左 ‹ › 右）</div>
    <div style="display:flex;flex-direction:column;gap:5px">
      {% for w in works %}<div style="display:flex;align-items:center;font-size:13px"><span style="flex:1;text-align:right;color:{{ '#9effb6' if w.l>w.r else '#8a82a8' }}">{{ w.l or '-' }}</span><span style="flex:none;width:96px;text-align:center;color:#c9bfe6">{{ w.label }}</span><span style="flex:1;text-align:left;color:{{ '#9effb6' if w.r>w.l else '#8a82a8' }}">{{ w.r or '-' }}</span></div>{% endfor %}
    </div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

COMPARE_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:stretch;justify-content:space-between;width:100%;gap:6px">
    <div style="flex:1;text-align:center">
      <div style="width:86px;height:86px;margin:0 auto;background:{{ left.color }}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center">{% if left.icon %}<img src="{{ left.icon }}" style="width:72px;height:72px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:40px">▥</span>{% endif %}</div>
      <div style="font-size:17px;font-weight:700;color:#2c1a0a;margin-top:5px">{{ left.name }}</div>
      <div style="font-size:12px;color:#574012">{{ left.elements }}</div>
    </div>
    <div style="flex:none;display:flex;align-items:center"><div style="width:46px;height:46px;background:#e8c66a;border:3px solid #6b4a24;display:flex;align-items:center;justify-content:center;color:#2a1d05;font-size:18px;font-weight:900">VS</div></div>
    <div style="flex:1;text-align:center">
      <div style="width:86px;height:86px;margin:0 auto;background:{{ right.color }}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center">{% if right.icon %}<img src="{{ right.icon }}" style="width:72px;height:72px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:40px">▥</span>{% endif %}</div>
      <div style="font-size:17px;font-weight:700;color:#2c1a0a;margin-top:5px">{{ right.name }}</div>
      <div style="font-size:12px;color:#574012">{{ right.elements }}</div>
    </div>
  </div></div>
  <div class="frame">
    {% for s in stats %}
    <div style="display:flex;align-items:center;padding:7px 4px;{% if not loop.last %}border-bottom:2px solid rgba(107,74,36,.3){% endif %}">
      <span style="flex:1;text-align:right;font-size:17px;font-weight:700;color:{{ '#1d7a36' if s.lwin else ('#9a8a6a' if s.rwin else '#382207') }}">{{ s.lval }}{% if s.lwin %} ▲{% endif %}</span>
      <span style="flex:none;width:96px;text-align:center;font-size:13px;color:#574012">{{ s.label }}</span>
      <span style="flex:1;text-align:left;font-size:17px;font-weight:700;color:{{ '#1d7a36' if s.rwin else ('#9a8a6a' if s.lwin else '#382207') }}">{% if s.rwin %}▲ {% endif %}{{ s.rval }}</span>
    </div>
    {% endfor %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 可孵化（/帕鲁可孵化） ----------------
HATCH_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🥚 {{ title }}</div>
    <div class="subtitle"><span class="pill soft">{{ subtitle }}</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" style="padding:8px 10px;gap:8px;align-items:center">
      <div style="flex:none;display:flex;align-items:center;gap:7px;width:46%;min-width:0">
        {% if r.icon %}<img src="{{ r.icon }}" style="width:42px;height:42px;object-fit:contain;flex-shrink:0;filter:drop-shadow(0 2px 5px rgba(0,0,0,.5))">{% else %}<span style="font-size:24px">🥚</span>{% endif %}
        <span style="font-size:15px;font-weight:800;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</span>
      </div>
      <span style="flex-shrink:0;color:#9a93b8;font-size:13px">←</span>
      <div style="flex:1;display:flex;align-items:center;gap:5px;min-width:0;justify-content:flex-end">
        {% if r.a_icon %}<img src="{{ r.a_icon }}" style="width:28px;height:28px;object-fit:contain;flex-shrink:0">{% endif %}
        <span style="font-size:12.5px;color:#c9bfe6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.a }}</span>
        <span style="color:#e8c466;flex-shrink:0">＋</span>
        {% if r.b_icon %}<img src="{{ r.b_icon }}" style="width:28px;height:28px;object-fit:contain;flex-shrink:0">{% endif %}
        <span style="font-size:12.5px;color:#c9bfe6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.b }}</span>
      </div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:12px;text-align:center;font-size:12.5px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 {{ pager }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

HATCH_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">▣ {{ title }}</div>
    <div class="subtitle"><span class="pill">{{ subtitle }}</span></div>
  </div></div>
  <div class="frame">
    {% for r in rows %}
    <div style="display:flex;padding:7px 8px;gap:8px;align-items:center;{% if not loop.last %}border-bottom:2px solid rgba(107,74,36,.3){% endif %}">
      <div style="flex:none;display:flex;align-items:center;gap:6px;width:46%;min-width:0">
        {% if r.icon %}<img src="{{ r.icon }}" style="width:40px;height:40px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:22px">▥</span>{% endif %}
        <span style="font-size:15px;font-weight:700;color:#2c1a0a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</span>
      </div>
      <span style="flex-shrink:0;color:#7a6a4a">←</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0;justify-content:flex-end">
        {% if r.a_icon %}<img src="{{ r.a_icon }}" style="width:26px;height:26px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
        <span style="font-size:12px;color:#574012;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.a }}</span>
        <span style="color:#8f1212;flex-shrink:0">＋</span>
        {% if r.b_icon %}<img src="{{ r.b_icon }}" style="width:26px;height:26px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% endif %}
        <span style="font-size:12px;color:#574012;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.b }}</span>
      </div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:11px;text-align:center;font-size:12.5px;color:#46200a;background:rgba(156,107,26,.15);border:2px solid #6a4524;padding:8px 11px">{{ pager }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 词条继承概率（/帕鲁继承） ----------------
INHERIT_TMPL = _HEAD + _PCHIP + """
  .pbox { flex:1; min-width:0; background:rgba(18,12,48,.5); border:1px solid rgba(232,198,106,.22); border-radius:14px; padding:11px 12px; }
  .pbox .pt { font-size:13px; font-weight:800; color:#e8c466; margin-bottom:8px; }
  .pchips { display:flex; flex-wrap:wrap; gap:6px; }
  .bar { height:11px; border-radius:6px; background:linear-gradient(90deg,#7ab8ff,#6366F1); }
  .barbg { flex:1; height:11px; border-radius:6px; background:rgba(255,255,255,.1); overflow:hidden; }
</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🧬 词条继承概率</div>
    <div class="subtitle">两只亲代配种，孩子继承词条的概率（社区实测模型）</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:flex;gap:11px;align-items:stretch">
      <div class="pbox"><div class="pt">👨 父代词条</div><div class="pchips">{% if a_chips %}{% for c in a_chips %}<span class="pname pl-{{ c.color }}">{{ c.stars }} {{ c.name }}</span>{% endfor %}{% else %}<span style="color:#9c8fc0;font-size:12px">（未填）</span>{% endif %}</div></div>
      <div class="pbox"><div class="pt">👩 母代词条</div><div class="pchips">{% if b_chips %}{% for c in b_chips %}<span class="pname pl-{{ c.color }}">{{ c.stars }} {{ c.name }}</span>{% endfor %}{% else %}<span style="color:#9c8fc0;font-size:12px">（未填）</span>{% endif %}</div></div>
    </div>
    <div style="margin-top:15px;text-align:center;background:linear-gradient(135deg,rgba(99,102,241,.28),rgba(122,184,255,.14));border:1px solid rgba(232,198,106,.32);border-radius:16px;padding:16px 14px">
      {% if feasible %}
      <div style="font-size:13px;color:#cfc1ea">同时继承这 {{ n }} 个词条的概率</div>
      <div style="font-size:46px;font-weight:900;color:#fff;line-height:1.1;margin-top:2px">{{ p_all }}<span style="font-size:24px">%</span></div>
      {% else %}
      <div style="font-size:16px;font-weight:800;color:#ff9a9a">{{ headline }}</div>
      <div style="font-size:12.5px;color:#cfc1ea;margin-top:6px">孩子词条最多 4 格，请把目标精简到 4 个以内</div>
      {% endif %}
    </div>
    <div class="sec-t" style="margin-top:16px">🎲 继承「父母词条」数量的概率</div>
    {% for d in dist %}
    <div style="display:flex;align-items:center;gap:10px;padding:5px 0">
      <span style="flex:none;width:84px;font-size:13px;color:#cfc1ea">{{ d.j }} 个词条</span>
      <div class="barbg"><div class="bar" style="width:{{ d.p }}%"></div></div>
      <span style="flex:none;width:42px;text-align:right;font-size:13px;font-weight:800;color:#e8c466">{{ d.p }}%</span>
    </div>
    {% endfor %}
    <div class="sec-t" style="margin-top:16px">📊 每个词条单独的继承率</div>
    {% for c in pool %}
    <div style="display:flex;align-items:center;gap:9px;padding:5px 0;border-bottom:1px solid rgba(232,198,106,.1)">
      <span class="pname pl-{{ c.color }}" style="flex:none">{{ c.stars }} {{ c.name }}</span>
      {% if c.effect %}<span style="flex:1;min-width:0;font-size:11.5px;color:#9c8fc0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ c.effect }}</span>{% else %}<span style="flex:1"></span>{% endif %}
      <span style="flex:none;font-size:14px;font-weight:800;color:#7fe0a0">{{ c.p_single }}%</span>
    </div>
    {% endfor %}
    {% if shared %}<div style="margin-top:12px;font-size:12px;color:#ffd34d">⭐ 双亲都带「{{ shared|join('、') }}」，词条池中只算一份。</div>{% endif %}
    {% if unknown %}<div style="margin-top:6px;font-size:12px;color:#ff9a9a">⚠ 没认出：{{ unknown|join('、') }}（已忽略，请用游戏内全名）</div>{% endif %}
    <div style="margin-top:12px;font-size:11.5px;color:#9c8fc0;line-height:1.65">📌 模型：孩子从父母「去重词条池」里继承 1/2/3/4 个的概率为 40%/30%/20%/10%；空余格子还可能随机刷出新词条。实际为概率，单次孵化结果随机，多孵几窝更稳。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

INHERIT_PIX = _PH + _PCHIP_PIX + """
  .pbox { flex:1; min-width:0; background:rgba(221,198,149,.5); border:2px solid #6a4524; padding:9px 10px; }
  .pbox .pt { font-size:13px; color:#8f1212; margin-bottom:7px; }
  .pchips { display:flex; flex-wrap:wrap; gap:5px; }
  .barbg { flex:1; height:12px; background:rgba(90,58,30,.2); border:2px solid #6a4524; overflow:hidden; }
  .bar { height:100%; background:#c0291f; }
</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">▦ 词条继承概率</div>
    <div class="subtitle">两只亲代配种，孩子继承词条的概率（社区实测模型）</div>
  </div></div>
  <div class="frame">
    <div style="display:flex;gap:10px;align-items:stretch">
      <div class="pbox"><div class="pt">父代词条</div><div class="pchips">{% if a_chips %}{% for c in a_chips %}<span class="pname pl-{{ c.color }}">{{ c.stars }} {{ c.name }}</span>{% endfor %}{% else %}<span style="color:#7a5a2a;font-size:12px">（未填）</span>{% endif %}</div></div>
      <div class="pbox"><div class="pt">母代词条</div><div class="pchips">{% if b_chips %}{% for c in b_chips %}<span class="pname pl-{{ c.color }}">{{ c.stars }} {{ c.name }}</span>{% endfor %}{% else %}<span style="color:#7a5a2a;font-size:12px">（未填）</span>{% endif %}</div></div>
    </div>
    <div style="margin-top:14px;text-align:center;background:rgba(221,198,149,.62);border:3px solid #6a4524;padding:15px 12px">
      {% if feasible %}
      <div style="font-size:13px;color:#574012">同时继承这 {{ n }} 个词条的概率</div>
      <div style="font-size:44px;color:#8f1212;line-height:1.1;margin-top:2px">{{ p_all }}<span style="font-size:22px">%</span></div>
      {% else %}
      <div style="font-size:16px;color:#8f1212">{{ headline }}</div>
      <div style="font-size:12.5px;color:#574012;margin-top:6px">孩子词条最多 4 格，请把目标精简到 4 个以内</div>
      {% endif %}
    </div>
    <div class="sec-t" style="margin-top:15px">继承「父母词条」数量的概率</div>
    {% for d in dist %}
    <div style="display:flex;align-items:center;gap:9px;padding:5px 0">
      <span style="flex:none;width:80px;font-size:13px;color:#574012">{{ d.j }} 个词条</span>
      <div class="barbg"><div class="bar" style="width:{{ d.p }}%"></div></div>
      <span style="flex:none;width:42px;text-align:right;font-size:13px;color:#8f1212">{{ d.p }}%</span>
    </div>
    {% endfor %}
    <div class="sec-t" style="margin-top:15px">每个词条单独的继承率</div>
    {% for c in pool %}
    <div style="display:flex;align-items:center;gap:9px;padding:5px 0;border-bottom:2px dotted rgba(90,58,30,.25)">
      <span class="pname pl-{{ c.color }}" style="flex:none">{{ c.stars }} {{ c.name }}</span>
      {% if c.effect %}<span style="flex:1;min-width:0;font-size:11.5px;color:#7a5a2a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ c.effect }}</span>{% else %}<span style="flex:1"></span>{% endif %}
      <span style="flex:none;font-size:14px;color:#2f7a3a">{{ c.p_single }}%</span>
    </div>
    {% endfor %}
    {% if shared %}<div style="margin-top:11px;font-size:12px;color:#8f6a12">★ 双亲都带「{{ shared|join('、') }}」，词条池中只算一份。</div>{% endif %}
    {% if unknown %}<div style="margin-top:6px;font-size:12px;color:#a02b1f">⚠ 没认出：{{ unknown|join('、') }}（已忽略，请用游戏内全名）</div>{% endif %}
    <div style="margin-top:11px;font-size:11.5px;color:#7a5a2a;line-height:1.65">模型：孩子从父母「去重词条池」继承 1/2/3/4 个的概率为 40%/30%/20%/10%；空格还可能随机刷新词条。结果随机，多孵几窝更稳。</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 竞技场（/帕鲁竞技场） ----------------
ARENA_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🏟️ 帕鲁竞技场</div>
    <div class="subtitle">单人挑战 NPC 训练家 · 6 段位 · 赢「战斗券」兑换稀有装备</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="font-size:13px;color:#cfc1ea;line-height:1.7;margin-bottom:12px">在岛上的竞技场入口报名，用自己的帕鲁队伍轮流挑战各段位的训练家。胜利获得 <b style="color:#ffd86b">战斗券</b>，可在 <b>竞技场商店</b> 兑换设计图/帕鲁球等。发「/帕鲁竞技场 段位名」看对手阵容。</div>
    {% for t in tiers %}
    <div style="display:flex;align-items:center;gap:11px;padding:10px 2px;border-bottom:1px solid rgba(232,198,106,.12)">
      <span style="flex:none;font-size:26px">{{ t.emoji }}</span>
      <div style="flex:1;min-width:0">
        <div style="font-size:16px;font-weight:800;color:#f3ecd2">{{ t.tier }} <span style="font-size:12px;color:#9c8fc0;font-weight:600">推荐 Lv.{{ t.level }} · {{ t.count }} 位对手</span></div>
        <div style="font-size:12px;color:#b9a9d6;margin-top:2px">🏅 首通 {{ t.first }}</div>
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:13px;text-align:center;font-size:12.5px;color:#d8cdf0;background:rgba(99,102,241,.16);border:1px solid rgba(232,198,106,.2);border-radius:12px;padding:9px 12px">📖 发「/帕鲁竞技场 {{ tiers[4].tier }}」看对手阵容 · 「/帕鲁商人 竞技场商店」看战斗券兑换</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

ARENA_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">▣ 帕鲁竞技场</div>
    <div class="subtitle">单人挑战 NPC 训练家 · 6 段位 · 赢「战斗券」兑换稀有装备</div>
  </div></div>
  <div class="frame">
    <div style="font-size:13px;color:#574012;line-height:1.7;margin-bottom:12px">用自己的帕鲁队伍挑战各段位训练家，胜利获得 <b style="color:#8f1212">战斗券</b>，在 <b>竞技场商店</b> 兑换稀有道具。发「/帕鲁竞技场 段位名」看对手阵容。</div>
    {% for t in tiers %}
    <div style="display:flex;align-items:center;gap:10px;padding:9px 2px;border-bottom:2px dotted rgba(90,58,30,.25)">
      <span style="flex:none;font-size:24px">{{ t.emoji }}</span>
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;color:#46200a">{{ t.tier }} <span style="font-size:12px;color:#7a5a2a">推荐 Lv.{{ t.level }} · {{ t.count }} 位对手</span></div>
        <div style="font-size:12px;color:#7a5a2a;margin-top:2px">首通 {{ t.first }}</div>
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:12px;text-align:center;font-size:12.5px;color:#46200a;background:rgba(156,107,26,.15);border:2px solid #6a4524;padding:8px 11px">发「/帕鲁竞技场 {{ tiers[4].tier }}」看对手阵容 · 「/帕鲁商人 竞技场商店」看兑换</div>
  </div>
  """ + _PF + """
</div></body></html>"""

ARENA_TIER_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ emoji }} 竞技场 · {{ tier }}</div>
    <div class="subtitle"><span class="pill soft">推荐 Lv.{{ level }}</span><span class="pill soft">{{ teams|length }} 位对手</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:6px">
      <div style="flex:1;min-width:140px;background:rgba(18,12,48,.5);border:1px solid rgba(232,198,106,.25);border-radius:12px;padding:9px 11px"><div style="font-size:12px;color:#ffd86b;margin-bottom:3px">🏅 首通奖励</div><div style="font-size:12.5px;color:#ece3f7;line-height:1.5">{% for r in first %}{{ r.name }}×{{ r.qty }}{% if not loop.last %} · {% endif %}{% endfor %}</div></div>
      <div style="flex:1;min-width:140px;background:rgba(18,12,48,.5);border:1px solid rgba(232,198,106,.18);border-radius:12px;padding:9px 11px"><div style="font-size:12px;color:#b9a9d6;margin-bottom:3px">🔁 重复奖励</div><div style="font-size:12.5px;color:#cfc1ea;line-height:1.5">{% for r in repeat %}{{ r.name }}×{{ r.qty }}{% if not loop.last %} · {% endif %}{% endfor %}</div></div>
    </div>
    <div class="sec-t" style="margin-top:14px">⚔️ 对手阵容</div>
    {% for tm in teams %}
    <div style="padding:9px 2px;border-bottom:1px solid rgba(232,198,106,.1)">
      <div style="font-size:14px;font-weight:800;color:#f3ecd2;margin-bottom:5px">{{ tm.trainer }} <span style="font-size:12px;color:#9c8fc0;font-weight:600">Lv.{{ tm.level }}</span></div>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        {% for p in tm.pals %}
        <div style="display:flex;align-items:center;gap:5px;background:rgba(99,102,241,.14);border:1px solid rgba(232,198,106,.18);border-radius:9px;padding:3px 8px 3px 4px">
          {% if p.icon %}<img src="{{ p.icon }}" style="width:26px;height:26px;object-fit:contain">{% endif %}
          <span style="font-size:12px;color:#e9e0f5">{{ p.name }}</span>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:12px;font-size:12px;color:#9c8fc0;line-height:1.6">💡 对手等级 Lv.{{ level }}；带克制属性的帕鲁、配高威力主动技能更稳。胜利得「战斗券」→ /帕鲁商人 竞技场商店 兑换。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

ARENA_TIER_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ emoji }} 竞技场 · {{ tier }}</div>
    <div class="subtitle"><span class="pill">推荐 Lv.{{ level }}</span><span class="pill">{{ teams|length }} 位对手</span></div>
  </div></div>
  <div class="frame">
    <div style="display:flex;gap:9px;flex-wrap:wrap;margin-bottom:6px">
      <div style="flex:1;min-width:140px;background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:8px 10px"><div style="font-size:12px;color:#8f1212;margin-bottom:3px">首通奖励</div><div style="font-size:12.5px;color:#46200a;line-height:1.5">{% for r in first %}{{ r.name }}×{{ r.qty }}{% if not loop.last %} · {% endif %}{% endfor %}</div></div>
      <div style="flex:1;min-width:140px;background:rgba(221,198,149,.4);border:2px solid #6a4524;padding:8px 10px"><div style="font-size:12px;color:#7a5a2a;margin-bottom:3px">重复奖励</div><div style="font-size:12.5px;color:#574012;line-height:1.5">{% for r in repeat %}{{ r.name }}×{{ r.qty }}{% if not loop.last %} · {% endif %}{% endfor %}</div></div>
    </div>
    <div class="sec-t" style="margin-top:14px">对手阵容</div>
    {% for tm in teams %}
    <div style="padding:9px 2px;border-bottom:2px dotted rgba(90,58,30,.25)">
      <div style="font-size:14px;color:#46200a;margin-bottom:5px">{{ tm.trainer }} <span style="font-size:12px;color:#7a5a2a">Lv.{{ tm.level }}</span></div>
      <div style="display:flex;flex-wrap:wrap;gap:8px">
        {% for p in tm.pals %}
        <div style="display:flex;align-items:center;gap:5px;background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:2px 7px 2px 3px">
          {% if p.icon %}<img src="{{ p.icon }}" style="width:24px;height:24px;object-fit:contain;image-rendering:pixelated">{% endif %}
          <span style="font-size:12px;color:#46200a">{{ p.name }}</span>
        </div>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:12px;font-size:12px;color:#7a5a2a;line-height:1.6">对手等级 Lv.{{ level }}；带克制属性+高威力技能更稳。胜利得战斗券→ /帕鲁商人 竞技场商店 兑换。</div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 主动技能（/帕鲁技能 <名>） ----------------
SKILL_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    <div style="flex:none;width:74px;height:74px;border-radius:18px;background:radial-gradient(circle at 50% 38%,{{color}}55,rgba(18,12,48,.5) 72%);border:2px solid {{color}}cc;display:flex;align-items:center;justify-content:center;font-size:38px">{{ emoji }}</div>
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill soft" style="color:{{color}}">{{ element }}属性</span>{% if is_fruit %}<span class="pill soft">🍐 技能果实可得</span>{% endif %}{% if effect %}<span class="pill soft">{{ effect }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div style="background:rgba(12,8,38,.42);border:1px solid {{color}}44;border-radius:12px;padding:10px 12px"><div style="font-size:12px;color:#b9a9d6">威力</div><div style="font-size:22px;font-weight:800;color:#ffd86b">{{ power or "—" }}</div></div>
      <div style="background:rgba(12,8,38,.42);border:1px solid {{color}}44;border-radius:12px;padding:10px 12px"><div style="font-size:12px;color:#b9a9d6">冷却(秒)</div><div style="font-size:22px;font-weight:800;color:#9effb6">{{ cooldown or "—" }}</div></div>
    </div>
    <div class="sec-t" style="margin-top:13px">📖 效果</div>
    <div style="font-size:14.5px;color:#e9e0f5;line-height:1.8">{{ desc or "（暂无描述）" }}</div>
    {% if is_fruit %}<div style="margin-top:12px;font-size:12.5px;color:#bdf0c8;line-height:1.7">🍐 此技能可通过「{{ element }}之技能果实：{{ name }}」喂给帕鲁学会（技能果实在地牢/野外宝箱、商人处获取）。</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

SKILL_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    <div style="flex:none;width:70px;height:70px;background:{{color}}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center;font-size:34px">{{ emoji }}</div>
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle"><span class="pill">{{ element }}属性</span>{% if is_fruit %}<span class="pill">技能果实</span>{% endif %}{% if effect %}<span class="pill">{{ effect }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="frame">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:9px">
      <div style="background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:9px 11px"><div style="font-size:12px;color:#574012">威力</div><div style="font-size:21px;color:#46200a">{{ power or "—" }}</div></div>
      <div style="background:rgba(221,198,149,.5);border:2px solid #6a4524;padding:9px 11px"><div style="font-size:12px;color:#574012">冷却(秒)</div><div style="font-size:21px;color:#1d5a2a">{{ cooldown or "—" }}</div></div>
    </div>
    <div class="sec-t" style="margin-top:12px">效果</div>
    <div style="font-size:14.5px;color:#382207;line-height:1.8">{{ desc or "（暂无描述）" }}</div>
    {% if is_fruit %}<div style="margin-top:11px;font-size:12.5px;color:#1d5a2a;line-height:1.7">可通过技能果实喂给帕鲁学会。</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 商人（/帕鲁商人 /帕鲁哪里买） ----------------
MERCHANT_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<div style="flex:none;width:80px;height:80px;border-radius:18px;background:radial-gradient(circle at 50% 38%,rgba(232,198,106,.28),rgba(18,12,48,.5) 72%);border:2px solid rgba(232,198,106,.6);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:66px;height:66px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))"></div>{% else %}<div style="flex:none;font-size:46px">{{ emoji }}</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ title }}</div>
      <div class="subtitle">{% for b in badges %}<span class="pill soft">{{ b }}</span>{% endfor %}</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% if note %}<div style="font-size:13px;color:#c9bfe6;margin-bottom:10px">{{ note }}</div>{% endif %}
    {% for r in rows %}
    <div style="display:flex;align-items:center;gap:9px;padding:7px 2px;{% if not loop.last %}border-bottom:1px solid rgba(232,198,106,.12){% endif %}">
      <span style="flex:1;font-size:14.5px;color:#f3ecd2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</span>
      {% if r.sub %}<span style="flex:none;font-size:12px;color:#b9a9d6">{{ r.sub }}</span>{% endif %}
      {% if r.right %}<span style="flex:none;font-size:14px;font-weight:800;color:#ffd86b">{{ r.right }}</span>{% endif %}
    </div>
    {% endfor %}
    {% if foot %}<div style="margin-top:11px;font-size:12px;color:#b9a9d6;line-height:1.7">{{ foot }}</div>{% endif %}
  </div>
  """ + _FOOT + """
</div></body></html>"""

MERCHANT_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    {% if icon %}<div style="flex:none;width:76px;height:76px;background:rgba(214,184,124,.3);border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:62px;height:62px;object-fit:contain;image-rendering:pixelated"></div>{% else %}<div style="flex:none;font-size:42px">{{ emoji }}</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ title }}</div>
      <div class="subtitle">{% for b in badges %}<span class="pill">{{ b }}</span>{% endfor %}</div>
    </div>
  </div></div>
  <div class="frame">
    {% if note %}<div style="font-size:13px;color:#574012;margin-bottom:9px">{{ note }}</div>{% endif %}
    {% for r in rows %}
    <div style="display:flex;align-items:center;gap:9px;padding:6px 2px;{% if not loop.last %}border-bottom:2px solid rgba(107,74,36,.3){% endif %}">
      <span style="flex:1;font-size:14.5px;color:#2c1a0a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</span>
      {% if r.sub %}<span style="flex:none;font-size:12px;color:#574012">{{ r.sub }}</span>{% endif %}
      {% if r.right %}<span style="flex:none;font-size:14px;color:#8f1212">{{ r.right }}</span>{% endif %}
    </div>
    {% endfor %}
    {% if foot %}<div style="margin-top:10px;font-size:12px;color:#574012;line-height:1.7">{{ foot }}</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""


STYLES = {
    "fantasy": {"status": STATUS_TMPL, "players": PLAYERS_TMPL, "settings": SETTINGS_TMPL,
                "help": HELP_TMPL, "message": MSG_TMPL, "stats": STATS_TMPL, "rank": RANK_TMPL,
                "profile": PROFILE_TMPL, "daily": DAILY_TMPL, "paldex": PALDEX_TMPL, "breed": BREED_TMPL,
                "reverse": REVERSE_TMPL, "drop": DROP_TMPL, "droplist": DROPLIST_TMPL,
                "heatmap": HEATMAP_TMPL, "power": POWER_TMPL, "route": ROUTE_TMPL, "shiny": SHINY_TMPL,
                "symptom": SYMPTOM_TMPL,
                "item": ITEM_TMPL, "itemcat": ITEMCAT_TMPL,
                "facility": FACILITY_TMPL, "tech": TECH_TMPL, "grid": GRID_TMPL, "map": MAP_TMPL,
                "lab_overview": LAB_OVERVIEW_TMPL, "lab_list": LAB_LIST_TMPL, "lab_detail": LAB_DETAIL_TMPL,
                "bag": BAG_TMPL, "team": TEAM_TMPL, "palbox": PALBOX_TMPL, "guild": GUILD_TMPL,
                "basecamp": BASECAMP_TMPL,
                "element": ELEMENT_TMPL, "habitat": HABITAT_TMPL, "passrec": PASSREC_TMPL,
                "mission": MISSION_TMPL, "missionlist": MISSIONLIST_TMPL, "boss": BOSS_TMPL,
                "merchant": MERCHANT_TMPL, "skill": SKILL_TMPL, "skillfruit": SKILLFRUIT_TMPL, "implant": IMPLANT_TMPL, "compare": COMPARE_TMPL,
                "hatch": HATCH_TMPL, "inherit": INHERIT_TMPL,
                "arena": ARENA_TMPL, "arena_tier": ARENA_TIER_TMPL},
    "pixel": {"status": STATUS_PIX, "players": PLAYERS_PIX, "settings": SETTINGS_PIX,
              "help": HELP_PIX, "message": MSG_PIX, "stats": STATS_PIX, "rank": RANK_PIX,
              "profile": PROFILE_PIX, "daily": DAILY_PIX, "paldex": PALDEX_PIX, "breed": BREED_PIX,
              "reverse": REVERSE_PIX, "drop": DROP_PIX, "droplist": DROPLIST_PIX,
              "heatmap": HEATMAP_PIX, "power": POWER_PIX, "route": ROUTE_PIX, "shiny": SHINY_PIX,
              "symptom": SYMPTOM_PIX,
              "item": ITEM_PIX, "itemcat": ITEMCAT_PIX,
              "facility": FACILITY_PIX, "tech": TECH_PIX, "grid": GRID_PIX, "map": MAP_PIX,
              "bag": BAG_PIX, "team": TEAM_PIX, "palbox": PALBOX_PIX, "guild": GUILD_PIX,
              "basecamp": BASECAMP_PIX,
              "element": ELEMENT_PIX, "habitat": HABITAT_PIX, "passrec": PASSREC_PIX,
              "mission": MISSION_PIX, "missionlist": MISSIONLIST_PIX, "boss": BOSS_PIX,
              "merchant": MERCHANT_PIX, "skill": SKILL_PIX, "compare": COMPARE_PIX,
              "hatch": HATCH_PIX, "inherit": INHERIT_PIX,
              "arena": ARENA_PIX, "arena_tier": ARENA_TIER_PIX},
}
STYLE_NAMES = {"fantasy": "🌌 奇幻玻璃", "pixel": "📜 像素羊皮纸"}
STYLE_ALIAS = {"奇幻": "fantasy", "玻璃": "fantasy", "fantasy": "fantasy", "二次元": "fantasy",
               "像素": "pixel", "羊皮纸": "pixel", "复古": "pixel", "pixel": "pixel"}

# 模板字符串 -> 卡名(两套风格都映射，供 _bg_for 查专属背景图)
TEMPLATE_KEYS = {}
for _st in STYLES.values():
    for _k, _t in _st.items():
        TEMPLATE_KEYS[_t] = _k
