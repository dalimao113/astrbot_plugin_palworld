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
      <div class="subtitle">当前帕鲁世界规则与倍率配置{% if server_version %} · 服务端 {{ server_version }}{% endif %}</div>
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
    <div class="cmd"><div class="c"><b>/帕鲁战力榜</b></div><div class="d">已知帕鲁战力等级排行(翻页/详情)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁玩家战力榜</b></div><div class="d">玩家拥有/抓捕帕鲁战力排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁闪光墙</b></div><div class="d">全服闪光帕鲁收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁头目墙</b></div><div class="d">全服头目(Alpha)收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁图鉴榜</b></div><div class="d">全服图鉴收集进度排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁资产榜</b></div><div class="d">全服帕鲁身价排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会战力</b></div><div class="d">各公会战力总和排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁更新公告</b></div><div class="d">官方最新更新公告(中文)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁肝帝榜</b> <span style="opacity:.7">[今日/总榜]</span></div><div class="d">在线时长排行(默认本周,可加 今日/总榜)</div></div>
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
    <div class="cmd"><div class="c"><b>/帕鲁词条大全</b> [分类]</div><div class="d">全部词条分类查询详情</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁觉醒</b></div><div class="d">1.0 觉醒材料与机制</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁突变</b></div><div class="d">1.0 突变机制与特殊蛋糕</div></div>
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
    <div class="cmd"><div class="c"><b>/帕鲁植入体</b> [名/页]</div><div class="d">🆕 68种改造词条·编号查:/帕鲁植入体查询 N</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁世界树</b></div><div class="d">🆕 1.0最终boss专题:暮尘蛾&夜蔓爵</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁1.0</b></div><div class="d">🆕 1.0正式版支持总览·数据统计·新功能导览</div></div>
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
      <div class="title">{{ name }}{% if is_tower_boss %} <span style="font-size:15px;vertical-align:middle;background:linear-gradient(135deg,#c0392b,#8e2318);color:#fff;padding:3px 11px;border-radius:9px;font-weight:800;box-shadow:0 2px 7px rgba(192,57,43,.55)">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-2px;margin-right:3px">{% else %}🗼 {% endif %}塔主</span>{% elif is_boss %} <span style="font-size:15px;vertical-align:middle;background:linear-gradient(135deg,#d68910,#a86008);color:#fff;padding:3px 11px;border-radius:9px;font-weight:800;box-shadow:0 2px 7px rgba(214,137,16,.5)">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-2px;margin-right:3px">{% else %}👑 {% endif %}头目</span>{% endif %}</div>
      <div class="subtitle">
        <span class="pill soft">图鉴 #{{ index }}</span>
        {% for e in elements %}<span class="pill soft">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}
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
      {% if price %}<span class="pill soft">{% if icons.currency.gold %}<img src="{{ icons.currency.gold }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}💰{% endif %} 贩卖价 {{ price }}金币</span>{% endif %}
      {% if size %}<span class="pill soft">📏 体型 {{ size }}</span>{% endif %}
    </div>
    <div style="font-size:11px;color:#8a82a8;line-height:1.6;margin-bottom:12px">💰贩卖价＝把这只帕鲁卖给商人/帕鲁贩子得到的金币（非道具购买价，故「/帕鲁哪里买」查不到）　📈刷新＝野外出现的等级参考范围　📏体型＝帕鲁个头（XS最小 → XL最大，越大越占地、骑乘体感越壮）</div>{% endif %}
    {% if traits %}<div class="sec-t">🧭 习性</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px">{% for t in traits %}<span class="pill soft">{{ t.k }} · {{ t.v }}</span>{% endfor %}</div>{% endif %}
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
    <div style="display:flex;flex-wrap:wrap;gap:8px">{% for w in works %}<span class="pill soft">{% if icons.work[w.k] %}<img src="{{ icons.work[w.k] }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}</div>{% endif %}
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
        <div style="margin-top:8px;display:flex;gap:5px;justify-content:center;flex-wrap:wrap">{% for e in a.elements %}<span class="pill soft" style="font-size:11px;padding:2px 9px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}</div>
      </div>
      <div style="font-size:30px;font-weight:900;color:#e8c466;flex-shrink:0">＋</div>
      <div class="tile" style="flex:1;max-width:150px;text-align:center;padding:15px 8px">
        {% if b.icon %}<img src="{{ b.icon }}" style="width:52px;height:52px;object-fit:contain;display:block;margin:0 auto 6px;filter:drop-shadow(0 2px 4px rgba(0,0,0,.5))">{% endif %}
        <div style="font-size:18px;font-weight:800;color:#f3ecd2;word-break:break-word">{{ b.name }}</div>
        <div style="font-size:12px;color:#9c8fc0;margin-top:3px">#{{ b.index }}</div>
        <div style="margin-top:8px;display:flex;gap:5px;justify-content:center;flex-wrap:wrap">{% for e in b.elements %}<span class="pill soft" style="font-size:11px;padding:2px 9px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}</div>
      </div>
    </div>
    <div style="text-align:center;font-size:14px;color:#e8c466;font-weight:800;margin:4px 0 2px">═══ 后代 ═══</div>
    <div style="text-align:center;padding:8px 0 6px">
      {% if c.icon %}<img src="{{ c.icon }}" style="width:72px;height:72px;object-fit:contain;display:block;margin:0 auto 4px;filter:drop-shadow(0 3px 6px rgba(0,0,0,.55))">{% endif %}
      <div class="num-gold" style="font-size:30px">{{ c.name }}</div>
      <div style="font-size:13px;color:#9c8fc0;margin-top:4px">图鉴 #{{ c.index }} · {{ "★" * (c.rarity if c.rarity <= 5 else 5) if c.rarity else "★" }}</div>
      <div style="display:flex;gap:6px;justify-content:center;margin-top:10px">{% for e in c.elements %}<span class="pill gold" style="font-size:13px;padding:4px 13px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}</div>
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


# ====================================================================
# ingame 游戏原生主题 · 通用 UI 组件系统(阶段C)
# 用真实游戏 UI 纹理(data/ingame/parts/,经 {{ parts.* }} 由渲染层注入 base64)
# 拼装 border-image 九宫格组件;图标经 asset() 走 manifest。
# ⚠️ 配色/间距/slice 为**临时值**,标 PROVISIONAL,待游戏截图校准(见 INGAME_UI_REFERENCE.md)。
# 不改 fantasy/pixel。三套主题模板键仍一致(ingame 卡逐步接入,当前重点卡先用)。
# ====================================================================
_INGAME_CSS = """
  /* ---- 冷调「古代科技终端」配色。面板色阶采自游戏 UI 蓝灰(button #484860 推导)---- */
  :root{
    --pal-ink:#15151c; --pal-panel:#1f1f2a; --pal-panel-hi:#2b2b39;   /* 游戏 UI 蓝灰色相 */
    --pal-line:rgba(255,255,255,.10); --pal-line-soft:rgba(255,255,255,.06);
    --pal-gold:#f0e070; --pal-gold-dim:#c9a94e;      /* 采自游戏 node_gold(#f0e070);仅稀有度/专属技能/头目 */
    --pal-cyan:#2ec6ff;                              /* 采自游戏 node_selected(#00a8f0/#14caff);选中/科技点缀 */
    --pal-text:#ffffff; --pal-text-2:#e2e8f0; --pal-sub:#9ca3af; --pal-dim:#6b7280;
    --pal-danger:#e0664f; --pal-good:#8bd06a;
    --pal-slot:url({{ parts.slot_item }}); --pal-slotpal:url({{ parts.slot_pal }});
    --pal-tab:url({{ parts.tab_base }}); --pal-btn:url({{ parts.button }});
    --pal-node:url({{ parts.node_dark }}); --pal-node-gold:url({{ parts.node_gold }});
    --pal-node-sel:url({{ parts.node_selected }});
  }
  *{ margin:0; padding:0; box-sizing:border-box;
     font-family:"HarmonyOS Sans SC","Microsoft YaHei","PingFang SC","Noto Sans SC",system-ui,sans-serif; }
  html{ zoom:{{ zoom }}; } html,body{ width:{{ cw|default(540) }}px; }
  body{ color:var(--pal-text-2); position:relative; display:flex; flex-direction:column;
    background:
      radial-gradient(120% 78% at 50% -12%, rgba(46,198,255,.06), transparent 55%),
      linear-gradient(170deg,#1c1c26,#15151c 62%,#0f0f16); }
  body::after{ content:""; position:absolute; inset:0; pointer-events:none;
    box-shadow: inset 0 0 100px 26px rgba(0,0,0,.4); }
  .page{ position:relative; z-index:2; flex:1 1 auto; display:flex; flex-direction:column;
    min-height:300px; padding:22px 18px 16px; }

  /* ---- GameWindow / GameHeader ---- */
  .ig-head{ display:flex; align-items:center; gap:12px; margin-bottom:14px; }
  .ig-crest{ flex:none; width:46px; height:46px; background:var(--pal-node) center/contain no-repeat;
    display:flex; align-items:center; justify-content:center; }
  .ig-crest img{ width:26px; height:26px; object-fit:contain; }
  .ig-title{ font-size:22px; font-weight:800; letter-spacing:.5px; color:var(--pal-text);
    line-height:1.15; text-wrap:balance; }
  .ig-sub{ font-size:12.5px; color:var(--pal-sub); margin-top:4px; display:flex; gap:7px;
    flex-wrap:wrap; align-items:center; }
  .ig-badge-on{ flex:none; margin-left:auto; font-size:12px; font-weight:700; color:#0e1015;
    background:var(--pal-good); padding:5px 13px; border-radius:3px; }

  /* ---- GamePanel(冷灰面板 + 极细扁平描边,去发光)---- */
  .ig-panel{ position:relative; background:var(--pal-panel); margin-bottom:12px; padding:15px 16px;
    border:1px solid var(--pal-line); border-radius:3px; }
  .ig-panel.hi{ background:var(--pal-panel-hi); }

  /* ---- GameSectionTitle(纤细实线,冷青色标记)---- */
  .ig-sec{ display:flex; align-items:center; gap:8px; font-size:13.5px; font-weight:700;
    color:var(--pal-text-2); letter-spacing:1.5px; margin:0 0 12px; padding-bottom:9px;
    border-bottom:1px solid var(--pal-line); }
  .ig-sec::before{ content:""; width:3px; height:13px; background:var(--pal-cyan); border-radius:1px; }

  /* ---- GameItemSlot / grid(切角物品槽)---- */
  .ig-grid{ display:grid; grid-template-columns:repeat(5,1fr); gap:9px; }
  .ig-slot{ position:relative; aspect-ratio:1; border:15px solid transparent;
    border-image:var(--pal-slot) 30 fill stretch; display:flex; align-items:center; justify-content:center; }
  .ig-slot img{ width:100%; height:100%; object-fit:contain; filter:drop-shadow(0 1px 2px rgba(0,0,0,.6)); }
  .ig-slot .qty{ position:absolute; right:2px; bottom:0; font-size:12px; font-weight:800;
    color:var(--pal-text); text-shadow:0 1px 2px #000; font-variant-numeric:tabular-nums; }
  .ig-slot.sel{ border-image:var(--pal-node-sel) 30 fill stretch; }

  /* ---- GamePalSlot(帕鲁卡)---- */
  .ig-palcard{ position:relative; border:16px solid transparent; border-image:var(--pal-slotpal) 26 fill stretch;
    padding:2px; display:flex; flex-direction:column; align-items:center; }
  .ig-palcard img{ width:100%; aspect-ratio:1; object-fit:contain; }
  .ig-palcard .nm{ font-size:12px; color:var(--pal-text-2); margin-top:2px; max-width:100%;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .ig-corner{ position:absolute; top:5px; left:5px; font-size:13px; }

  /* ---- GameNode(八角节点,承载属性/科技图标)---- */
  .ig-node{ position:relative; width:52px; height:52px; background:var(--pal-node) center/contain no-repeat;
    display:flex; align-items:center; justify-content:center; flex:none; }
  .ig-node.gold{ background-image:var(--pal-node-gold); }
  .ig-node.sel{ background-image:var(--pal-node-sel); }
  .ig-node img{ width:56%; height:56%; object-fit:contain; }

  /* ---- GameElementBadge / GameWorkChip ---- */
  .ig-badge{ display:inline-flex; align-items:center; gap:5px; font-size:12.5px; color:var(--pal-text-2);
    background:rgba(255,255,255,.05); border:1px solid var(--pal-line); border-radius:3px; padding:3px 9px 3px 5px; }
  .ig-badge img{ width:18px; height:18px; object-fit:contain; }
  .ig-work{ display:inline-flex; align-items:center; gap:5px; font-size:12px; color:var(--pal-sub);
    background:rgba(255,255,255,.04); border-radius:3px; padding:3px 8px 3px 4px; }
  .ig-work img{ width:17px; height:17px; object-fit:contain; }

  /* ---- GameStatBar ---- */
  .ig-stat{ margin-bottom:9px; }
  .ig-stat .lab{ display:flex; align-items:center; justify-content:space-between; font-size:12.5px;
    color:var(--pal-sub); margin-bottom:4px; }
  .ig-stat .lab b{ color:var(--pal-text); font-variant-numeric:tabular-nums; }
  .ig-stat .lab .ic{ display:inline-flex; align-items:center; gap:5px; }
  .ig-stat .lab img{ width:15px; height:15px; }
  .ig-track{ height:12px; border:1px solid var(--pal-line); border-radius:2px;
    background:rgba(0,0,0,.35); overflow:hidden; }
  .ig-fill{ height:100%; background:linear-gradient(180deg,#e2e8f0,#94a3b8); }
  .ig-fill.hp{ background:linear-gradient(180deg,#8bd06a,#4f9a3c); }
  .ig-fill.san{ background:linear-gradient(180deg,#7dd3e0,#3f97ab); }

  /* ---- GameTabs / GameButton / pill ---- */
  .ig-tabs{ display:flex; gap:6px; margin-bottom:10px; }
  .ig-tab{ font-size:12.5px; color:var(--pal-sub); border:10px solid transparent;
    border-image:var(--pal-tab) 12 fill stretch; padding:0 4px; line-height:1; }
  .ig-tab.on{ color:var(--pal-text); font-weight:700; filter:brightness(1.3); }
  .ig-btn{ display:inline-flex; align-items:center; gap:6px; font-size:12.5px; color:var(--pal-text-2);
    border:9px solid transparent; border-image:var(--pal-btn) 9 fill stretch; padding:2px 6px; }
  .ig-pill{ display:inline-flex; align-items:center; gap:4px; font-size:11.5px; color:var(--pal-sub);
    background:rgba(30,41,59,.6); border:1px solid transparent; border-radius:3px; padding:2px 9px; }
  .ig-pill.gold{ color:var(--pal-gold); background:rgba(240,207,122,.10); border-color:rgba(240,207,122,.28); }

  .ig-foot{ margin-top:auto; padding-top:12px; text-align:center; font-size:11.5px; color:var(--pal-sub);
    border-top:1px solid var(--pal-line); }
  .ig-foot b{ color:var(--pal-dim); }

  /* ---- 头部立绘框(帕鲁卡框):与 fantasy/pixel 一致——头部左侧、醒目 ---- */
  .ig-head{ align-items:flex-start; }
  .ig-portrait{ flex:none; width:108px; height:108px; border:15px solid transparent;
    border-image:var(--pal-slotpal) 26 fill stretch; display:flex; align-items:center; justify-content:center; }
  .ig-portrait img{ width:100%; height:100%; object-fit:contain; filter:drop-shadow(0 3px 7px rgba(0,0,0,.6)); }
  .ig-boss{ font-size:13px; vertical-align:middle; font-weight:800; color:#0e0b07;
    background:linear-gradient(180deg,#f0cf7a,#c99a48); padding:2px 10px; border-radius:2px; }
  .ig-boss.tower{ background:linear-gradient(180deg,#e0664f,#b23b2a); color:#fff; }

  /* ---- 3×3 数值瓦片(纯白数值,极细描边)---- */
  .ig-stiles{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
  .ig-stile{ background:rgba(255,255,255,.03); border:1px solid var(--pal-line-soft); border-radius:3px;
    padding:10px 4px 8px; text-align:center; }
  .ig-stile .v{ font-size:22px; font-weight:700; color:var(--pal-text); line-height:1;
    font-variant-numeric:tabular-nums; }
  .ig-stile .k{ font-size:11px; color:var(--pal-sub); margin-top:5px; display:flex; align-items:center;
    justify-content:center; gap:4px; }
  .ig-stile .k img{ width:13px; height:13px; opacity:.85; }

  /* ---- 技能行(名左 + 斜切属性牌+威力右):主次拉开 ---- */
  .ig-sk{ display:flex; align-items:center; gap:10px; padding:8px 2px;
    border-bottom:1px solid var(--pal-line-soft); }
  .ig-sk:last-child{ border-bottom:none; }
  .ig-sk .nm{ flex:1; min-width:0; font-size:14.5px; font-weight:700; color:var(--pal-text);
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .ig-sk .pw{ flex:none; display:flex; align-items:center; gap:8px; font-size:12px; color:var(--pal-dim);
    font-variant-numeric:tabular-nums; }
  /* 斜切属性牌:承载游戏原生属性 PNG,居中贴在威力数值左侧 */
  .ig-eplate{ display:inline-flex; align-items:center; justify-content:center; width:34px; height:24px;
    background:rgba(255,255,255,.06); border:1px solid var(--pal-line-soft);
    clip-path:polygon(14% 0,100% 0,86% 100%,0 100%); }
  .ig-eplate img{ width:20px; height:20px; object-fit:contain; vertical-align:middle; }
  .ig-drop{ display:flex; align-items:center; justify-content:space-between; padding:6px 0;
    border-bottom:1px solid var(--pal-line-soft); }
  .ig-drop .l{ display:flex; align-items:center; gap:7px; font-size:14px; color:var(--pal-text-2); }
  .ig-drop .l img{ width:24px; height:24px; object-fit:contain; }
  .ig-drop .r{ font-size:12px; color:var(--pal-dim); font-variant-numeric:tabular-nums; }

  /* ---- 被动词条块(右侧等级箭头 PNG)---- */
  .ig-passrow{ position:relative; display:flex; align-items:center; gap:10px; padding:11px 44px 11px 13px;
    margin-bottom:8px; background:rgba(255,255,255,.03); border:1px solid var(--pal-line-soft);
    border-left:3px solid var(--pal-line); border-radius:3px; }
  .ig-passrow.pos{ border-left-color:var(--pal-good); }
  .ig-passrow.neg{ border-left-color:var(--pal-danger); }
  .ig-passrow .pn{ font-size:14.5px; font-weight:700; color:var(--pal-text); }
  .ig-passrow .pe{ font-size:12.5px; color:var(--pal-sub); margin-top:3px; line-height:1.45; }
  .ig-passrow .tag{ font-size:10px; color:var(--pal-sub); background:rgba(30,41,59,.6);
    border-radius:2px; padding:1px 6px; margin-left:6px; vertical-align:middle; }
  /* 游戏原生等级箭头:限高 20px,宽度自适应,绝对定位悬浮右缘 */
  .ig-rank{ position:absolute; right:12px; top:50%; transform:translateY(-50%);
    height:20px; width:auto; object-fit:contain; }
  .ig-rank.pos{ filter:brightness(0) saturate(100%) invert(84%) sepia(28%) saturate(560%)
    hue-rotate(2deg) brightness(103%) contrast(94%); }   /* 白遮罩→金 */
  .ig-rank.neg{ filter:brightness(0) saturate(100%) invert(46%) sepia(58%) saturate(3200%)
    hue-rotate(332deg) brightness(97%) contrast(93%); }   /* 白遮罩→红 */

  /* ---- 词条大全分类行 / 推荐词条行(单列,手机竖屏)---- */
  .ig-catrow{ display:flex; flex-direction:column; padding:11px 13px; margin-bottom:8px;
    background:rgba(255,255,255,.03); border:1px solid var(--pal-line-soft);
    border-left:3px solid var(--pal-line); border-radius:3px; }
  .ig-catrow .cn{ font-size:15px; font-weight:700; color:var(--pal-text); }
  .ig-catrow .cc{ font-size:11px; font-weight:700; margin-left:8px; }
  .ig-catrow .cs{ font-size:11.5px; color:var(--pal-sub); margin-top:5px; line-height:1.5;
    max-height:2.2em; overflow:hidden; }
  .ig-recrow{ display:flex; align-items:center; gap:10px; margin-bottom:7px; background:rgba(255,255,255,.03);
    border:1px solid var(--pal-line-soft); border-radius:3px; padding:8px 12px; }
  .ig-recrow .rn{ flex:none; min-width:74px; font-size:14px; font-weight:700; color:var(--pal-text); }
  .ig-recrow .re{ flex:1; min-width:0; font-size:12.5px; color:var(--pal-sub); line-height:1.45; }
  .ig-recrow .rs{ flex:none; font-size:12px; color:var(--pal-gold); letter-spacing:1px; }

  /* ---- 服务器状态 / 在线玩家 ---- */
  .ig-stile .si{ height:20px; margin-bottom:2px; display:flex; align-items:center; justify-content:center; }
  .ig-stile .si img{ width:18px; height:18px; object-fit:contain; opacity:.85; }
  .ig-prow{ display:flex; align-items:center; gap:9px; padding:9px 4px;
    border-bottom:1px solid var(--pal-line-soft); }
  .ig-prow:last-child{ border-bottom:none; }
  .ig-prow .pnm{ flex:1; min-width:0; font-size:14.5px; font-weight:700; color:var(--pal-text);
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .ig-prow .pdur{ font-size:12px; color:var(--pal-sub); font-variant-numeric:tabular-nums;
    min-width:56px; text-align:right; }
  .ig-ping{ font-size:11px; color:#fff; border-radius:2px; padding:2px 7px; min-width:52px;
    text-align:center; font-variant-numeric:tabular-nums; }
  .ig-fill.hot{ background:linear-gradient(180deg,#e0664f,#b23b2a); }
  .ig-badge-off{ flex:none; margin-left:auto; font-size:12px; font-weight:700; color:#fff;
    background:var(--pal-danger); padding:5px 13px; border-radius:3px; }

  /* ---- 背包物品格(切角槽 + 名 + 数量)---- */
  .ig-bgrid{ display:grid; grid-template-columns:repeat(4,1fr); gap:9px; }
  .ig-bcell{ text-align:center; min-width:0; }
  .ig-bcell .bn{ font-size:11.5px; color:var(--pal-sub); margin-top:5px; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; }

  /* ---- 帕鲁箱格(稀有度边框 + 立绘 + 闪光/头目标)---- */
  .ig-pbgrid{ display:grid; grid-template-columns:repeat(4,1fr); gap:9px; }
  .ig-palcell{ position:relative; background:rgba(255,255,255,.03); border:1.5px solid var(--pal-line);
    border-radius:4px; padding:9px 4px 7px; text-align:center; min-width:0; }
  .ig-palcell .no{ position:absolute; top:3px; left:4px; font-size:10px; font-weight:700; color:var(--pal-sub);
    background:rgba(0,0,0,.4); border-radius:3px; padding:0 5px; z-index:2; font-variant-numeric:tabular-nums; }
  .ig-palcell .mk{ position:absolute; top:-5px; right:-3px; width:20px; height:20px; object-fit:contain; z-index:2;
    filter:drop-shadow(0 1px 2px rgba(0,0,0,.7)); }
  .ig-palcell .pv{ height:54px; display:flex; align-items:center; justify-content:center; }
  .ig-palcell .pv img{ width:54px; height:54px; object-fit:contain; }
  .ig-palcell .pn{ font-size:11.5px; color:var(--pal-text-2); margin-top:3px; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; }
  .ig-palcell .pl{ font-size:11px; color:var(--pal-sub); }
  .ig-palcell .cd{ color:var(--pal-gold); }
  .ig-palcell.rt-common{ border-color:#6b7280; }
  .ig-palcell.rt-uncommon{ border-color:#4a90d9; }
  .ig-palcell.rt-rare{ border-color:#9b5cd9; }
  .ig-palcell.rt-epic{ border-color:#e0a83a; box-shadow:0 0 8px rgba(224,168,58,.28); }
  .ig-palcell.rt-legend{ border-color:#e0664f; box-shadow:0 0 8px rgba(224,102,79,.28); }
  .ig-palcell.hurt{ box-shadow:0 0 0 2px #e0664f inset; }
  .ig-palcell .hb{ display:inline-block; margin-top:3px; font-size:9.5px; font-weight:700;
    border-radius:3px; padding:0 5px; line-height:15px; }
  .ig-palcell .hb-bad{ background:#d42c2c; color:#fff; }
  .ig-palcell .hb-warn{ background:#e07a1a; color:#fff; }

  /* ---- 玩家档案:头像 / 状态点 KV / 出战队伍 ---- */
  .ig-avatar{ width:90px; height:90px; margin:0 auto; border-radius:50%; padding:3px;
    background:rgba(255,255,255,.08); border:1px solid var(--pal-line); }
  .ig-avatar img{ width:100%; height:100%; border-radius:50%; object-fit:cover; display:block; }
  .ig-avatar.ph{ display:flex; align-items:center; justify-content:center; }
  .ig-avatar.ph img{ width:44px; height:44px; border-radius:0; opacity:.65; }
  .ig-kv{ display:flex; justify-content:space-between; align-items:baseline;
    background:rgba(255,255,255,.03); border:1px solid var(--pal-line-soft); border-radius:3px; padding:8px 11px; }
  .ig-kv .kn{ font-size:12px; color:var(--pal-sub); }
  .ig-kv .kp{ font-size:15px; font-weight:800; color:var(--pal-gold); font-variant-numeric:tabular-nums; }
  .ig-party{ display:flex; flex-wrap:wrap; gap:10px; justify-content:center; }
  .ig-pmini{ width:78px; text-align:center; }
  .ig-pmini .pv{ position:relative; width:64px; height:64px; margin:0 auto; background:rgba(255,255,255,.03);
    border:1px solid var(--pal-line); border-radius:4px; display:flex; align-items:center; justify-content:center; }
  .ig-pmini .pv img{ width:54px; height:54px; object-fit:contain; }
  .ig-pmini .pv .mk{ position:absolute; top:-6px; right:-6px; width:18px; height:18px; z-index:2;
    filter:drop-shadow(0 1px 2px rgba(0,0,0,.7)); }
  .ig-pmini .pn{ font-size:11.5px; color:var(--pal-text-2); margin-top:5px; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; }
  .ig-pmini .pl{ font-size:11px; color:var(--pal-sub); }

  /* ---- 队伍卡(单列,每只详情)---- */
  .ig-teamcard{ display:flex; gap:13px; }
  .ig-teamcard .tpic{ flex:none; width:90px; height:90px; border:13px solid transparent;
    border-image:var(--pal-slotpal) 26 fill stretch; display:flex; align-items:center; justify-content:center;
    position:relative; }
  .ig-teamcard .tpic img{ width:100%; height:100%; object-fit:contain; }
  .ig-teamcard .tpic .mk{ position:absolute; top:-4px; right:-4px; width:20px; height:20px; z-index:2;
    filter:drop-shadow(0 1px 2px rgba(0,0,0,.7)); }
  .ig-ivr{ display:flex; gap:6px; margin-top:9px; }
  .ig-ivb{ flex:1; background:rgba(255,255,255,.03); border:1px solid var(--pal-line-soft); border-radius:3px;
    padding:5px 4px; text-align:center; }
  .ig-ivb .ivk{ font-size:10.5px; color:var(--pal-sub); }
  .ig-ivb .ivv{ font-size:15px; font-weight:800; color:var(--pal-text); font-variant-numeric:tabular-nums; }
  .ig-ivb.tal .ivv{ color:var(--pal-gold); }
  .ig-subsec{ font-size:12px; font-weight:700; color:var(--pal-sub); letter-spacing:.5px; margin:12px 0 5px; }
  .ig-partner{ display:flex; align-items:center; gap:9px; background:rgba(240,207,122,.08);
    border:1px solid rgba(240,207,122,.28); border-radius:3px; padding:8px 11px; }
  .ig-partner .pt{ flex:none; font-size:13.5px; font-weight:800; color:var(--pal-gold); }
  .ig-partner .pd{ flex:1; min-width:0; font-size:12px; color:var(--pal-sub); line-height:1.4; }

  /* ---- 图鉴/物品网格(编号+图标+名+头目标)---- */
  .ig-dexgrid{ display:grid; grid-template-columns:repeat(5,1fr); gap:8px; }
  .ig-dexcell{ position:relative; display:flex; flex-direction:column; align-items:center; padding:10px 3px 7px;
    background:rgba(255,255,255,.03); border:1px solid var(--pal-line-soft); border-radius:4px; min-width:0; }
  .ig-dexcell .no{ position:absolute; top:3px; left:4px; font-size:9.5px; font-weight:700; color:var(--pal-sub);
    background:rgba(0,0,0,.4); border-radius:3px; padding:0 4px; font-variant-numeric:tabular-nums; }
  .ig-dexcell .bmk{ position:absolute; top:2px; right:3px; width:16px; height:16px; object-fit:contain; z-index:2;
    filter:drop-shadow(0 1px 2px rgba(0,0,0,.8)); }
  .ig-dexcell .pv{ width:58px; height:58px; display:flex; align-items:center; justify-content:center; }
  .ig-dexcell .pv img{ width:58px; height:58px; object-fit:contain; }
  .ig-dexcell .nm{ margin-top:5px; font-size:11px; color:var(--pal-text-2); text-align:center; line-height:1.2;
    height:2.4em; overflow:hidden; word-break:break-all; }

  /* ---- 排行榜行(肝帝/战力/财富/公会)---- */
  .ig-rankrow{ display:flex; align-items:center; gap:10px; padding:9px 10px; margin-bottom:7px;
    background:rgba(255,255,255,.03); border:1px solid var(--pal-line-soft); border-radius:3px; }
  .ig-rankrow.top{ border-color:rgba(240,207,122,.35); background:rgba(240,207,122,.06); }
  .ig-rankrow .mdl{ width:30px; flex:none; text-align:center; font-size:16px; font-weight:800; color:var(--pal-gold); }
  .ig-rankrow .pic{ width:40px; height:40px; flex:none; object-fit:contain; }
  .ig-rankrow .rn{ font-size:14.5px; font-weight:700; color:var(--pal-text); display:flex; align-items:center;
    gap:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .ig-rankrow .rn .inl{ width:16px; height:16px; object-fit:contain; }
  .ig-rankrow .rs{ font-size:12px; color:var(--pal-sub); margin-top:2px; white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; }
  .ig-rankrow .rv{ font-size:15px; font-weight:800; color:var(--pal-gold); font-variant-numeric:tabular-nums; }
  .ig-rankrow .dot{ width:8px; height:8px; border-radius:50%; background:var(--pal-good); flex:none; }

  /* ---- 闪光/头目墙(3列)/ 反配种行 ---- */
  .ig-shwall{ display:grid; grid-template-columns:repeat(3,1fr); gap:9px; }
  .ig-shcell{ display:flex; flex-direction:column; align-items:center; padding:10px 6px;
    background:rgba(240,207,122,.06); border:1px solid rgba(240,207,122,.28); border-radius:4px; min-width:0; }
  .ig-shcell .pv{ width:52px; height:52px; display:flex; align-items:center; justify-content:center; }
  .ig-shcell .pv img{ width:52px; height:52px; object-fit:contain; }
  .ig-shcell .nm{ font-size:12.5px; font-weight:700; color:var(--pal-text); margin-top:5px; text-align:center;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%; }
  .ig-shcell .ow{ font-size:11px; color:var(--pal-sub); white-space:nowrap; overflow:hidden;
    text-overflow:ellipsis; max-width:100%; }
  .ig-breedrow{ display:flex; align-items:center; gap:8px; padding:8px 4px;
    border-bottom:1px solid var(--pal-line-soft); }
  .ig-breedrow:last-child{ border-bottom:none; }
  .ig-breedrow .pa{ flex:1; display:flex; align-items:center; gap:7px; justify-content:flex-end; min-width:0; }
  .ig-breedrow .pb{ flex:1; display:flex; align-items:center; gap:7px; min-width:0; }
  .ig-breedrow img{ width:34px; height:34px; object-fit:contain; flex:none; }
  .ig-breedrow .nm{ font-size:13.5px; font-weight:700; color:var(--pal-text); white-space:nowrap;
    overflow:hidden; text-overflow:ellipsis; }
  .ig-breedrow .plus{ color:var(--pal-gold); font-weight:800; flex:none; }

  /* ---- 属性克制图(2列)---- */
  .ig-elemgrid{ display:grid; grid-template-columns:1fr 1fr; gap:9px; }
  .ig-ecard{ background:rgba(255,255,255,.03); border:1px solid var(--pal-line); border-radius:4px; padding:11px 12px; }
  .ig-ecard .er{ display:flex; align-items:center; gap:5px; flex-wrap:wrap; font-size:12.5px;
    color:var(--pal-text-2); margin-top:7px; }
  .ig-ecard .lb{ font-weight:700; min-width:34px; }
  .ig-ecard .et{ display:inline-flex; align-items:center; gap:3px; padding:1px 7px; border-radius:2px;
    font-size:12px; background:rgba(255,255,255,.05); border:1px solid var(--pal-line-soft); }
  .ig-ecard .et img{ width:15px; height:15px; object-fit:contain; }

  /* ---- 帮助命令 / 词条继承 / 对比 ---- */
  .ig-cmd{ display:inline-block; width:49%; box-sizing:border-box; vertical-align:top; padding:6px 4px; }
  .ig-cmd .c{ display:block; font-size:13.5px; font-weight:700; color:var(--pal-text); }
  .ig-cmd .c b{ color:var(--pal-gold); background:rgba(240,207,122,.1); border:1px solid rgba(240,207,122,.25);
    padding:1px 7px; border-radius:2px; }
  .ig-cmd .d{ display:block; font-size:11.5px; color:var(--pal-sub); margin-top:3px; }
  .ig-new{ font-size:9px; font-weight:800; color:#0e1015; background:var(--pal-cyan); border-radius:2px;
    padding:0 4px; margin-left:3px; vertical-align:middle; }
  .ig-chip{ display:inline-flex; align-items:center; gap:3px; font-size:12px; font-weight:700; padding:2px 8px;
    border-radius:2px; background:rgba(255,255,255,.05); border:1px solid var(--pal-line-soft); color:var(--pal-text-2); }
  .ig-chip.legend{ color:var(--pal-gold); border-color:var(--pal-gold-dim); }
  .ig-chip.epic{ color:#c49bff; border-color:#9b5cd9; }
  .ig-chip.rare{ color:#7dc0ff; border-color:#4a90d9; }
  .ig-chip.bad{ color:#ff9b9b; border-color:var(--pal-danger); }
  .ig-vs{ width:48px; height:48px; border-radius:50%; background:var(--pal-gold); color:#0e1015; font-size:18px;
    font-weight:900; font-style:italic; display:flex; align-items:center; justify-content:center; flex:none; }
  .ig-cmprow{ display:flex; align-items:center; padding:8px 4px; border-bottom:1px solid var(--pal-line-soft); }
  .ig-cmprow:last-child{ border-bottom:none; }
  .ig-cmprow .cv{ flex:1; font-size:16px; font-weight:800; font-variant-numeric:tabular-nums; }
  .ig-cmprow .cl{ flex:none; width:96px; text-align:center; font-size:12.5px; color:var(--pal-sub); }
  .cv.win{ color:var(--pal-good); } .cv.lose{ color:var(--pal-dim); } .cv.eq{ color:var(--pal-text-2); }
  .ig-inbar{ flex:1; height:10px; border-radius:2px; background:rgba(0,0,0,.35); overflow:hidden; }
  .ig-inbar > span{ display:block; height:100%; background:linear-gradient(90deg,#7dd3e0,#3f97ab); }

  /* ---- 据点工作帕鲁 ---- */
  .ig-wk{ display:flex; align-items:flex-start; gap:11px; padding:10px 2px; border-bottom:1px solid var(--pal-line-soft); }
  .ig-wk:last-child{ border-bottom:none; }
  .ig-wk .wpic{ flex:none; width:50px; height:50px; border-radius:4px; background:rgba(255,255,255,.03);
    border:1px solid var(--pal-line); display:flex; align-items:center; justify-content:center; position:relative; }
  .ig-wk .wpic img{ width:42px; height:42px; object-fit:contain; }
  .ig-wk .wpic .mk{ position:absolute; top:-5px; right:-5px; width:17px; height:17px; z-index:2; }
  .ig-hpill{ font-size:10.5px; font-weight:800; border-radius:2px; padding:1px 6px; color:#fff; }
  .ig-wtag{ font-size:10.5px; color:var(--pal-sub); background:rgba(255,255,255,.04); border-radius:2px; padding:1px 6px; }
  .ig-cure{ margin-top:8px; border-left:3px solid var(--pal-gold-dim); background:rgba(255,255,255,.03);
    border-radius:0 3px 3px 0; padding:8px 11px; }
  .ig-cure .cs{ font-size:12.5px; font-weight:800; color:var(--pal-gold); }
  .ig-cure .cd{ font-size:11.5px; color:var(--pal-sub); line-height:1.55; margin-top:3px; }
  .ig-cure .citem{ display:inline-flex; align-items:center; gap:5px; background:rgba(255,255,255,.04);
    border:1px solid var(--pal-line-soft); border-radius:2px; padding:2px 8px 2px 3px; margin:5px 5px 0 0; }
  .ig-cure .citem img{ width:30px; height:30px; object-fit:contain; }
  .ig-cure .citem span{ font-size:11px; color:var(--pal-text-2); }
"""
_IH = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><style>""" + _INGAME_CSS
_IF = ('<footer class="ig-foot">◈ {{ now }} · '
       '<b>大狸猫 · 帕鲁服务器管家</b> · <span style="opacity:.7">ingame 主题(开发中)</span></footer>')


# ---- ingame 版帕鲁详情(阶段D 第一张真卡)。变量契约与 PALDEX_TMPL 完全一致 + 注入 icons 图标映射 ----
PALDEX_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    {% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="ig-title">{{ name }}{% if is_tower_boss %} <span class="ig-boss tower">塔主</span>{% elif is_boss %} <span class="ig-boss">头目</span>{% endif %}</div>
      <div class="ig-sub">
        <span class="ig-pill">图鉴 #{{ index }}</span>
        {% for e in elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}
        <span class="ig-pill gold">{{ "★" * (rarity if rarity <= 5 else 5) if rarity else "★" }}</span>
        {% if nocturnal %}<span class="ig-pill">夜行</span>{% endif %}
      </div>
    </div>
  </div>
  {% if desc %}<div class="ig-panel" style="padding:12px 14px"><div style="font-size:13px;color:var(--pal-sub);line-height:1.65">{{ desc }}</div></div>{% endif %}
  {% if egg or lv or price or cap or size %}<div style="display:flex;flex-wrap:wrap;gap:7px;margin-bottom:12px">
    {% if egg %}<span class="ig-pill">{{ egg }}</span>{% endif %}
    {% if lv %}<span class="ig-pill">刷新 {{ lv }}</span>{% endif %}
    {% if cap %}<span class="ig-pill">捕获率 ×{{ cap }}</span>{% endif %}
    {% if price %}<span class="ig-pill">贩卖价 {{ price }}金币</span>{% endif %}
    {% if size %}<span class="ig-pill">体型 {{ size }}</span>{% endif %}
  </div>{% endif %}
  {% if traits %}<div class="ig-panel"><div class="ig-sec">习性</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for t in traits %}<span class="ig-pill">{{ t.k }} · {{ t.v }}</span>{% endfor %}</div></div>{% endif %}
  <div class="ig-panel">
    <div class="ig-sec">基础数值</div>
    <div class="ig-stiles">
      <div class="ig-stile"><div class="v">{{ hp }}</div><div class="k">{% if icons.stat.hp %}<img src="{{ icons.stat.hp }}">{% endif %}生命</div></div>
      <div class="ig-stile"><div class="v">{{ atk }}</div><div class="k">近战攻击</div></div>
      <div class="ig-stile"><div class="v">{{ shot }}</div><div class="k">远程攻击</div></div>
      <div class="ig-stile"><div class="v">{{ defense }}</div><div class="k">{% if icons.stat.defense %}<img src="{{ icons.stat.defense }}">{% endif %}防御力</div></div>
      <div class="ig-stile"><div class="v">{{ stamina }}</div><div class="k">耐力</div></div>
      <div class="ig-stile"><div class="v">{{ food }}</div><div class="k">{% if icons.stat.hunger %}<img src="{{ icons.stat.hunger }}">{% endif %}进食量</div></div>
      <div class="ig-stile"><div class="v">{{ walk }}</div><div class="k">走路速度</div></div>
      <div class="ig-stile"><div class="v">{{ run }}</div><div class="k">奔跑速度</div></div>
      <div class="ig-stile"><div class="v">{{ ride }}</div><div class="k">骑乘速度</div></div>
    </div>
  </div>
  {% if ranch %}<div class="ig-panel hi"><div class="ig-sec">牧场产出</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for r in ranch %}<span class="ig-work">{% if r.icon %}<img src="{{ r.icon }}">{% endif %}{{ r.name }}</span>{% endfor %}</div></div>{% endif %}
  <div class="ig-panel">
    <div class="ig-sec">主动技能</div>
    {% for s in skills %}<div class="ig-sk"><div class="nm">{{ s.name }}</div><div class="pw">{% if s.elem and icons.element[s.elem] %}<span class="ig-eplate"><img src="{{ icons.element[s.elem] }}"></span>{% endif %}威力 {{ s.power }} · CD {{ s.cd }}s</div></div>{% endfor %}
  </div>
  {% if works %}<div class="ig-panel hi"><div class="ig-sec">工作适性</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for w in works %}<span class="ig-work">{% if icons.work[w.k] %}<img src="{{ icons.work[w.k] }}">{% endif %}{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}</div></div>{% endif %}
  {% if drops %}<div class="ig-panel"><div class="ig-sec">掉落物品</div>
    {% for d in drops %}<div class="ig-drop"><span class="l">{% if d.icon %}<img src="{{ d.icon }}">{% endif %}{{ d.name }}</span><span class="r">{% if d.qty %}×{{ d.qty }} · {% endif %}{{ d.rate }}%</span></div>{% endfor %}</div>{% endif %}
  {% if partner_title %}<div class="ig-panel hi"><div class="ig-sec">伙伴技能</div>
    <div style="font-size:14.5px;font-weight:800;color:var(--pal-gold)">{{ partner_title }}</div>
    <div style="font-size:13px;color:var(--pal-sub);line-height:1.6;margin-top:5px">{{ partner_desc }}</div></div>{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版被动词条列表(阶段D)。变量契约与 PASSLIST_TMPL 一致 + 用游戏原生等级箭头 PNG ----
PASSLIST_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    <div style="flex:1;min-width:0">
      <div class="ig-title">{{ cat }}</div>
      <div class="ig-sub"><span class="ig-pill">{{ count }} 个词条</span></div>
    </div>
  </div>
  <div class="ig-panel">
    {% set rk = icons.passive_rank %}
    {% for it in items %}
    <div class="ig-passrow {% if it.sign>0 %}pos{% elif it.sign<0 %}neg{% endif %}">
      <div style="flex:1;min-width:0">
        <div><span class="pn">{{ it.name }}</span>{% if it.rank %}<span class="tag">Lv{{ it.rank }}</span>{% endif %}{% if it.cat %}<span class="tag">{{ it.cat }}</span>{% endif %}</div>
        {% if it.effect %}<div class="pe">{{ it.effect }}</div>{% endif %}
      </div>
      {% set lv = it.rank if it.rank else 1 %}
      {% if it.sign < 0 %}<img class="ig-rank neg" src="{{ rk.rank_down }}">
      {% elif it.sign > 0 %}<img class="ig-rank pos" src="{{ rk.rank_up3 if lv >= 3 else (rk.rank_up2 if lv == 2 else rk.rank_up1) }}">
      {% else %}<img class="ig-rank" src="{{ rk.rank_up1 }}">{% endif %}
    </div>
    {% endfor %}
    <div style="margin-top:6px;text-align:center;font-size:11px;color:var(--pal-dim)">↑金=增益 · ↓红=减益 · 箭头层数=词条等级 — 发「/帕鲁词条大全」看全部分类</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版词条大全总览(单列,不用两列网格)。变量契约与 PASSDEX_TMPL 一致 ----
PASSDEX_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">词条大全</div>
    <div class="ig-sub">帕鲁被动词条百科 · 共 <b style="color:var(--pal-text)">{{ total }}</b> 个 · 9 大类别</div>
  </div></div>
  <div class="ig-panel">
    {% for c in cats %}
    <div class="ig-catrow" style="border-left-color:{{ c.color }}">
      <div><span class="cn">{{ c.name }}</span><span class="cc" style="color:{{ c.color }}">{{ c.count }} 个词条</span></div>
      {% if c.sample %}<div class="cs">{{ c.sample }}…</div>{% endif %}
    </div>
    {% endfor %}
    <div style="margin-top:6px;text-align:center;font-size:11.5px;color:var(--pal-dim)">发「/帕鲁词条大全 攻击」看该类全部词条 · 「/帕鲁词条大全 力量」查具体效果</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版推荐词条(单列)。变量契约与 PASSREC_TMPL 一致 ----
PASSREC_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    {% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="ig-title">{{ name }} · 推荐词条</div>
      <div class="ig-sub"><span class="ig-pill">No.{{ index }}</span>{% for e in elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}{% for r in roles %}<span class="ig-pill">{{ r }}型</span>{% endfor %}</div>
    </div>
  </div>
  {% for sec in sections %}
  <div class="ig-panel {% if not loop.first %}hi{% endif %}">
    <div class="ig-sec">{{ sec.title }}</div>
    {% for it in sec['items'] %}
    <div class="ig-recrow"><span class="rn">{{ it.name }}</span><span class="re">{{ it.effect }}</span><span class="rs">{{ it.stars }}</span></div>
    {% endfor %}
  </div>
  {% endfor %}
  <div class="ig-panel"><div style="font-size:12px;color:var(--pal-sub);line-height:1.75">词条 ★ 越多越稀有。战斗帕鲁优先攻击/元素增伤,基地帕鲁优先工作速度,搬运/骑乘优先移速;「吸血鬼」让帕鲁夜间不睡持续干活。词条可在配种时遗传或用书本洗练。</div></div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版服务器状态。变量契约与 STATUS_TMPL 一致 + server.* 插件扩展 SVG ----
STATUS_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    <div style="flex:1;min-width:0">
      <div class="ig-title">{{ servername }}</div>
      <div class="ig-sub">{{ version }}</div>
    </div>
    {% if online %}<span class="ig-badge-on">在线</span>{% else %}<span class="ig-badge-off">离线</span>{% endif %}
  </div>
  <div class="ig-panel">
    <div style="text-align:center">
      <div style="color:var(--pal-sub);font-size:12px;letter-spacing:2px">当前在线人数</div>
      <div style="line-height:1;margin-top:6px">
        <span style="font-size:64px;font-weight:800;color:var(--pal-text);font-variant-numeric:tabular-nums">{{ cur }}</span>
        <span style="font-size:30px;font-weight:700;color:var(--pal-dim)">/{{ maxn }}</span>
        <span style="font-size:14px;color:var(--pal-dim);margin-left:4px">人</span>
      </div>
    </div>
    <div class="ig-stiles" style="margin-top:16px">
      <div class="ig-stile"><div class="si"><img src="{{ icons.server.fps }}"></div><div class="v">{{ fps }}</div><div class="k">服务器FPS</div></div>
      <div class="ig-stile"><div class="si"><img src="{{ icons.server.world_day }}"></div><div class="v">{{ days }}</div><div class="k">游戏天数</div></div>
      <div class="ig-stile"><div class="si"><img src="{{ icons.server.uptime }}"></div><div class="v">{{ uptime }}</div><div class="k">运行时长</div></div>
    </div>
  </div>
  {% if players %}<div class="ig-panel hi">
    <div class="ig-sec">在线玩家</div>
    {% for p in players %}
    <div class="ig-prow">
      <span class="pnm">{{ p.name }}</span>
      <span class="ig-pill">Lv.{{ p.level }}</span>
      <span class="pdur">{% if p.dur %}{{ p.dur }}{% else %}—{% endif %}</span>
      <span class="ig-ping" style="background:{{ p.ping_color }}">{{ p.ping }}ms</span>
    </div>
    {% endfor %}
  </div>{% endif %}
  {% if load %}<div class="ig-panel">
    <div class="ig-sec">服务器负载</div>
    <div class="ig-stat"><div class="lab"><span class="ic"><img src="{{ icons.server.cpu }}">CPU</span><b>{{ load.cpu }}%</b></div><div class="ig-track"><div class="ig-fill {{ 'hot' if load.cpu_bar>=80 else '' }}" style="width:{{ load.cpu_bar }}%"></div></div></div>
    <div class="ig-stat"><div class="lab"><span class="ic"><img src="{{ icons.server.memory }}">内存</span><b>{{ load.mem_text }} · {{ load.mem_pct }}%</b></div><div class="ig-track"><div class="ig-fill {{ 'hot' if load.mem_bar>=80 else '' }}" style="width:{{ load.mem_bar }}%"></div></div></div>
  </div>{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版在线玩家。变量契约与 PLAYERS_TMPL 一致 ----
PLAYERS_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    <div style="flex:1;min-width:0">
      <div class="ig-title">在线玩家</div>
      <div class="ig-sub">实时帕鲁岛冒险者名单</div>
    </div>
    <span class="ig-pill gold">{{ count }} 人在线</span>
  </div>
  {% if not players %}
  <div class="ig-panel" style="flex:1;display:flex;align-items:center;justify-content:center;min-height:220px">
    <div style="text-align:center"><div style="font-size:16px;color:var(--pal-text-2)">暂无玩家在线</div><div style="font-size:12.5px;color:var(--pal-sub);margin-top:6px">帕鲁岛静悄悄～ 快喊小伙伴上线冒险吧!</div></div>
  </div>
  {% else %}
  <div class="ig-panel">
    {% for p in players %}
    <div class="ig-prow">
      <span style="width:26px;height:26px;flex:none;border-radius:50%;background:rgba(255,255,255,.06);border:1px solid var(--pal-line);color:var(--pal-sub);font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;font-variant-numeric:tabular-nums">{{ loop.index }}</span>
      <span class="pnm">{{ p.name }}</span>
      <span class="ig-pill">Lv.{{ p.level }}</span>
      <span class="ig-ping" style="background:{{ p.ping_color }}">{{ p.ping }}ms</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版背包(切角物品槽 + 游戏物品图标)。变量契约与 BAG_TMPL 一致 ----
BAG_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">{{ name }} 的背包</div>
    <div class="ig-sub">共 {{ total }} 种物品{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 背包/装备/饰品栏</div>
  </div></div>
  <div class="ig-panel">
    {% if cells %}<div class="ig-bgrid">
    {% for c in cells %}<div class="ig-bcell"><div class="ig-slot">{% if c.icon %}<img src="{{ c.icon }}">{% endif %}<span class="qty">×{{ c.count }}</span></div><div class="bn">{{ c.name }}</div></div>{% endfor %}
    </div>{% else %}<div style="color:var(--pal-sub);text-align:center;padding:24px">背包空空如也～</div>{% endif %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:12.5px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帕鲁箱(稀有度边框 + 立绘 + 闪光/头目游戏图标)。变量契约与 PALBOX_TMPL 一致 ----
PALBOX_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">{{ name }} 的帕鲁箱</div>
    <div class="ig-sub">共 {{ total }} 只 · 第 {{ page }}/{{ pages }} 页 · 发「/帕鲁箱查询 编号」看详情</div>
  </div></div>
  <div class="ig-panel">
    {% if cells %}<div class="ig-pbgrid">
    {% for c in cells %}<div class="ig-palcell rt-{{ c.rtier }}{% if c.health.hurt %} hurt{% endif %}">
      <span class="no">{{ c.no }}</span>
      {% if c.lucky %}<img class="mk" src="{{ icons.pal.lucky }}">{% elif c.alpha %}<img class="mk" src="{{ icons.pal.alpha }}">{% endif %}
      <div class="pv">{% if c.icon %}<img src="{{ c.icon }}">{% endif %}</div>
      <div class="pn">{{ c.name }}</div><div class="pl">Lv.{{ c.level }}{% if c.condense %} <span class="cd">{{ "★"*c.condense }}</span>{% endif %}</div>
      {% if c.health.hurt %}<div class="hb hb-{{ c.health.tone }}">{{ c.health.label }}</div>{% endif %}
    </div>{% endfor %}
    </div>{% else %}<div style="color:var(--pal-sub);text-align:center;padding:24px">帕鲁箱空空如也～</div>{% endif %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:12.5px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版玩家档案。变量契约与 PROFILE_TMPL 一致 ----
PROFILE_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">我的帕鲁档案</div>
    <div class="ig-sub">绑定角色的在线数据</div>
  </div></div>
  <div class="ig-panel">
    <div style="text-align:center;padding:4px 0 10px">
      {% if avatar %}<div class="ig-avatar"><img src="{{ avatar }}"></div>
      {% else %}<div class="ig-avatar ph"><img src="{{ icons.server.player_count }}"></div>{% endif %}
      <div style="font-size:24px;font-weight:800;color:var(--pal-text);margin-top:8px;word-break:break-word">{{ name }}</div>
      <div style="margin-top:10px">{% if online %}<span class="ig-badge-on" style="margin-left:0">在线 · Lv.{{ level }}</span>{% else %}<span class="ig-badge-off" style="margin-left:0">离线中</span>{% endif %}</div>
      {% if titles %}<div style="margin-top:11px;display:flex;flex-wrap:wrap;gap:7px;justify-content:center">{% for t in titles %}<span class="ig-pill">{{ t }}</span>{% endfor %}</div>{% endif %}
    </div>
    <div class="ig-stiles">
      <div class="ig-stile"><div class="v">{{ week_dur }}</div><div class="k">本周在线</div></div>
      <div class="ig-stile"><div class="v">{{ total_dur }}</div><div class="k">累计在线</div></div>
      <div class="ig-stile"><div class="v">{{ rank }}</div><div class="k">本周排名</div></div>
    </div>
  </div>
  {% if has_save %}
  <div class="ig-panel hi">
    <div class="ig-sec">存档实况</div>
    <div class="ig-stiles">
      <div class="ig-stile"><div class="v">Lv.{{ s_level }}</div><div class="k">角色等级</div></div>
      <div class="ig-stile"><div class="v">{{ tech }}</div><div class="k">技术点</div></div>
      <div class="ig-stile"><div class="v">{{ recipes }}</div><div class="k">解锁配方</div></div>
    </div>
    <div class="ig-stiles" style="margin-top:8px">
      <div class="ig-stile"><div class="v">{{ max_hp }}</div><div class="k">{% if icons.stat.hp %}<img src="{{ icons.stat.hp }}">{% endif %}最大生命</div></div>
      <div class="ig-stile"><div class="v">{{ max_sp }}</div><div class="k">最大耐力</div></div>
      <div class="ig-stile"><div class="v">{{ weight }}</div><div class="k">{% if icons.stat.weight %}<img src="{{ icons.stat.weight }}">{% endif %}负重上限</div></div>
    </div>
    <div class="ig-stiles" style="margin-top:8px">
      <div class="ig-stile"><div class="v">{{ hp|int }}</div><div class="k">当前生命</div></div>
      <div class="ig-stile"><div class="v">{{ shield|int }}</div><div class="k">护盾值</div></div>
      <div class="ig-stile"><div class="v">{{ stomach|int }}</div><div class="k">{% if icons.stat.hunger %}<img src="{{ icons.stat.hunger }}">{% endif %}饱食度</div></div>
    </div>
    <div class="ig-stiles" style="margin-top:8px">
      <div class="ig-stile"><div class="v">{{ pal_total }}</div><div class="k">帕鲁总数</div></div>
      <div class="ig-stile"><div class="v">{{ dex_owned }}<span style="font-size:12px;color:var(--pal-dim)">/{{ dex_total }}</span></div><div class="k">图鉴收集</div></div>
      <div class="ig-stile"><div class="v" style="{% if hurt_n %}color:var(--pal-danger){% endif %}">{{ hurt_n }}</div><div class="k">受伤帕鲁</div></div>
    </div>
    {% if status %}
    <div class="ig-sec" style="margin-top:14px">状态点强化</div>
    <div class="ig-stiles">
      {% for s in status %}<div class="ig-kv"><span class="kn">{{ s.name }}</span><span class="kp" style="{% if not s.points %}color:var(--pal-dim){% endif %}">+{{ s.points }}</span></div>{% endfor %}
    </div>
    {% endif %}
  </div>
  {% if party %}
  <div class="ig-panel">
    <div class="ig-sec">出战队伍 · {{ party_n }} 只</div>
    <div class="ig-party">
      {% for p in party %}
      <div class="ig-pmini">
        <div class="pv">{% if p.icon %}<img src="{{ p.icon }}">{% endif %}{% if p.lucky %}<img class="mk" src="{{ icons.pal.lucky }}">{% elif p.alpha %}<img class="mk" src="{{ icons.pal.alpha }}">{% endif %}</div>
        <div class="pn">{{ p.name }}</div><div class="pl">Lv.{{ p.level }}</div>
      </div>
      {% endfor %}
    </div>
  </div>{% endif %}
  <div class="ig-panel"><div style="font-size:12.5px;color:var(--pal-sub);line-height:1.7">背包 <b style="color:var(--pal-text)">{{ bag_n }}</b> 种物品,发 /帕鲁背包 看明细;帕鲁箱 <b style="color:var(--pal-text)">{{ palbox_n }}</b> 只,发 /帕鲁箱 浏览{% if party %};发 /帕鲁队伍 看出战面板{% endif %}</div></div>
  {% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版出战队伍(单列,每只详情)。变量契约与 TEAM_TMPL 一致 ----
TEAM_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">{{ title }}</div>
    <div class="ig-sub">{{ subtitle }}</div>
  </div></div>
  {% for p in pals %}
  <div class="ig-panel {% if not loop.first %}hi{% endif %}">
    <div class="ig-teamcard">
      <div class="tpic">{% if p.icon %}<img src="{{ p.icon }}">{% endif %}{% if p.lucky %}<img class="mk" src="{{ icons.pal.lucky }}">{% elif p.alpha %}<img class="mk" src="{{ icons.pal.alpha }}">{% endif %}</div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
          <span style="font-size:19px;font-weight:800;color:var(--pal-text)">{{ p.name }}</span>
          {% if p.nickname %}<span style="font-size:12.5px;color:var(--pal-sub);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">「{{ p.nickname }}」</span>{% endif %}
          {% if p.condense %}<span style="font-size:12.5px;color:var(--pal-gold);letter-spacing:1px">{{ "★" * p.condense }}</span>{% endif %}
        </div>
        <div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px">
          <span class="ig-pill">Lv.{{ p.level }}</span>
          {% if p.gender %}<span class="ig-pill">{{ p.gender }}</span>{% endif %}
          {% for e in p.elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}
          {% if p.health.hurt %}<span class="ig-pill" style="background:{% if p.health.tone=='bad' %}#d42c2c{% else %}#e07a1a{% endif %};color:#fff">{{ p.health.label }}{% if p.health.tone=='bad' %}·放终端可恢复{% endif %}</span>{% endif %}
        </div>
        <div class="ig-ivr">
          <div class="ig-ivb"><div class="ivv">{{ p.hp }}</div><div class="ivk">生命</div></div>
          <div class="ig-ivb"><div class="ivv">{{ p.cur_atk }}</div><div class="ivk">攻击</div></div>
          <div class="ig-ivb"><div class="ivv">{{ p.cur_def }}</div><div class="ivk">防御</div></div>
          <div class="ig-ivb"><div class="ivv">{{ p.craft_speed }}</div><div class="ivk">工作速度</div></div>
        </div>
        <div class="ig-ivr">
          <div class="ig-ivb tal"><div class="ivv">{{ p.iv_hp }}</div><div class="ivk">生命天赋</div></div>
          <div class="ig-ivb tal"><div class="ivv">{{ p.iv_atk }}</div><div class="ivk">攻击天赋</div></div>
          <div class="ig-ivb tal"><div class="ivv">{{ p.iv_def }}</div><div class="ivk">防御天赋</div></div>
        </div>
        {% if p.works %}<div class="ig-subsec">工作适性</div>
        <div style="display:flex;flex-wrap:wrap;gap:6px">{% for w in p.works %}<span class="ig-work">{% if icons.work[w.name] %}<img src="{{ icons.work[w.name] }}">{% endif %}{{ w.name }} Lv{{ w.level }}</span>{% endfor %}</div>{% endif %}
        {% if p.partner.title %}<div class="ig-subsec">伙伴技能</div>
        <div class="ig-partner"><span class="pt">{{ p.partner.title }}</span>{% if p.partner.desc %}<span class="pd">{{ p.partner.desc }}</span>{% endif %}</div>{% endif %}
        {% if p.passives %}<div class="ig-subsec">词条</div>
        {% for s in p.passives %}<div class="ig-passrow {% if s.color=='bad' %}neg{% elif s.color in ['legend','epic','rare'] %}pos{% endif %}" style="padding:8px 40px 8px 11px;margin-bottom:6px">
          <div style="flex:1;min-width:0"><span class="pn" style="font-size:13.5px">{{ s.name }}</span>{% if s.effect %}<div class="pe">{{ s.effect }}</div>{% endif %}</div>
          {% if s.color=='bad' %}<img class="ig-rank neg" src="{{ icons.passive_rank.rank_down }}">{% else %}<img class="ig-rank pos" src="{{ icons.passive_rank.rank_up3 if (s.arrows|length)>=3 else (icons.passive_rank.rank_up2 if (s.arrows|length)==2 else icons.passive_rank.rank_up1) }}">{% endif %}
        </div>{% endfor %}{% endif %}
        {% if p.wazas %}<div class="ig-subsec">技能</div>
        {% for w in p.wazas %}<div class="ig-sk"><div class="nm" style="font-size:13.5px">{{ w.name }}</div><div class="pw">{% if w.elem and icons.element[w.elem] %}<span class="ig-eplate"><img src="{{ icons.element[w.elem] }}"></span>{% endif %}{% if w.power %}威力 {{ w.power }}{% endif %}</div></div>{% endfor %}{% endif %}
      </div>
    </div>
  </div>
  {% endfor %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版消息卡(错误/空态/确认/成功)。变量契约与 MSG_TMPL 一致。icon 为 handler 动态传入 ----
MSG_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ head }}</div></div></div>
  <div class="ig-panel" style="flex:1;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:40px 24px">
    {% if icon %}<div style="width:52px;height:52px;margin-bottom:16px;opacity:.9"><img src="{{ icon }}" style="width:100%;height:100%;object-fit:contain"></div>{% endif %}
    <div style="font-size:23px;font-weight:800;color:var(--pal-text);line-height:1.35;word-break:break-word">{{ title }}</div>
    {% if desc %}<div style="margin-top:16px;font-size:14px;line-height:1.7;color:var(--pal-sub);white-space:pre-line;word-break:break-word;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;padding:14px 16px;text-align:left;max-width:400px">{{ desc }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版在线统计。变量契约与 STATS_TMPL 一致 ----
STATS_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">在线统计</div><div class="ig-sub">今日数据与近 7 日在线峰值</div>
  </div></div>
  <div class="ig-panel">
    <div class="ig-stiles">
      <div class="ig-stile"><div class="v">{{ peak }}</div><div class="k">今日峰值</div></div>
      <div class="ig-stile"><div class="v">{{ avg }}</div><div class="k">今日平均</div></div>
      <div class="ig-stile"><div class="v">{{ cur }}</div><div class="k">当前在线</div></div>
    </div>
  </div>
  <div class="ig-panel hi">
    <div class="ig-sec">近 7 日在线峰值</div>
    <div style="display:flex;align-items:flex-end;gap:9px;height:160px;padding:6px 2px 0">
      {% for d in days %}
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%">
        <div style="font-size:12px;font-weight:700;color:var(--pal-text-2);margin-bottom:4px">{{ d.peak }}</div>
        <div style="width:70%;min-height:4px;height:{{ d.h }}%;border-radius:2px 2px 0 0;background:linear-gradient(180deg,#7dd3e0,#3f97ab)"></div>
        <div style="font-size:10.5px;color:var(--pal-sub);margin-top:7px">{{ d.label }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版服务器设置(单列)。变量契约与 SETTINGS_TMPL 一致 ----
SETTINGS_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">服务器设置</div>
    <div class="ig-sub">当前帕鲁世界规则与倍率配置{% if server_version %} · 服务端 {{ server_version }}{% endif %}</div>
  </div></div>
  <div class="ig-panel">
    {% for it in items %}
    <div class="ig-kv" style="margin-bottom:7px;border-left:3px solid var(--pal-cyan)">
      <span class="kn">{{ it.k }}</span><span class="kp" style="color:var(--pal-text)">{{ it.v }}</span>
    </div>
    {% endfor %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版网格列表(图鉴/物品/武器/坐骑等浏览)。变量契约与 GRID_TMPL 一致 ----
GRID_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">{{ title }}</div><div class="ig-sub">{{ sub }}</div>
  </div></div>
  <div class="ig-panel">
    <div class="ig-dexgrid">
      {% for c in cells %}
      <div class="ig-dexcell">
        <span class="no">{{ c.no }}</span>
        {% if c.boss %}<img class="bmk" src="{{ icons.pal.alpha }}">{% endif %}
        <div class="pv">{% if c.icon %}<img src="{{ c.icon }}">{% endif %}</div>
        <div class="nm">{{ c.name }}</div>
      </div>
      {% endfor %}
    </div>
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:12.5px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版物品分类总览(单列)。变量契约与 ITEMCAT_TMPL 一致 ----
ITEMCAT_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0">
    <div class="ig-title">物品图鉴</div><div class="ig-sub">共 {{ total }} 件 · 选择分类浏览</div>
  </div></div>
  <div class="ig-panel">
    {% for c in cats %}
    <div class="ig-catrow" style="flex-direction:row;align-items:center;gap:10px;border-left-color:var(--pal-cyan)">
      <span class="cn" style="flex:1;min-width:0">{{ c.name }}</span>
      <span style="color:var(--pal-sub);font-size:13px;font-variant-numeric:tabular-nums">{{ c.count }}</span>
    </div>
    {% endfor %}
    <div style="margin-top:8px;text-align:center;font-size:12px;color:var(--pal-dim)">发「/帕鲁物品 武器」浏览某类 · 「/帕鲁物品 羊毛」查详情</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版科技详情。变量契约与 TECH_TMPL 一致 ----
TECH_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    {% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% endif %}
    <div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div>
      <div class="ig-sub">
        {% if is_boss %}<span class="ig-pill gold">古代科技</span>{% endif %}
        {% if level %}<span class="ig-pill">解锁 Lv.{{ level }}</span>{% endif %}
        {% if points %}<span class="ig-badge">{% if icons.currency.tech_point %}<img src="{{ icons.currency.tech_point }}">{% endif %}{{ points }} 技术点</span>{% endif %}
      </div>
    </div>
  </div>
  <div class="ig-panel"><div style="font-size:14.5px;color:var(--pal-text-2);line-height:1.85;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div></div>
  {% if unlock %}<div class="ig-panel hi"><div class="ig-sec">解锁条件</div><div style="font-size:14px;color:var(--pal-sub);line-height:1.75;white-space:pre-line">{{ unlock }}</div></div>{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版物品详情。变量契约与 ITEM_TMPL 一致 ----
ITEM_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    {% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% endif %}
    <div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div>
      <div class="ig-sub"><span class="ig-pill">{{ type }}</span></div></div>
  </div>
  <div class="ig-panel"><div style="font-size:14.5px;color:var(--pal-text-2);line-height:1.85;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div>
    {% if price or sphere %}<div style="display:flex;flex-wrap:wrap;gap:7px;margin-top:12px">
      {% if price %}<span class="ig-badge">{% if icons.currency.gold %}<img src="{{ icons.currency.gold }}">{% endif %}商人价 <b style="color:var(--pal-gold);margin-left:2px">{{ price }}</b> 金币</span>{% endif %}
      {% if sphere %}<span class="ig-pill">捕获力 ×{{ sphere.cap }}</span><span class="ig-pill">品阶 {{ sphere.rank }}</span>{% endif %}
    </div>{% endif %}
  </div>
  {% if materials %}<div class="ig-panel hi"><div class="ig-sec">制作材料</div>
    {% for m in materials %}<div class="ig-drop"><span class="l">{% if m.icon %}<img src="{{ m.icon }}">{% endif %}{{ m.name }}</span><span class="r" style="color:var(--pal-gold);font-weight:800">×{{ m.count }}</span></div>{% endfor %}
    {% if benches %}<div class="ig-subsec">制作台</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for b in benches %}<span class="ig-pill">{{ b }}</span>{% endfor %}</div>{% endif %}
  </div>{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版设施详情。变量契约与 FACILITY_TMPL 一致 ----
FACILITY_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    {% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% endif %}
    <div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div>
      <div class="ig-sub">{% if category %}<span class="ig-pill">{{ category }}</span>{% endif %}</div></div>
  </div>
  <div class="ig-panel"><div style="font-size:14.5px;color:var(--pal-text-2);line-height:1.85;white-space:pre-line;word-break:break-word">{{ description or "（暂无描述）" }}</div></div>
  {% if materials %}<div class="ig-panel hi"><div class="ig-sec">建造材料</div>
    {% for m in materials %}<div class="ig-drop"><span class="l">{% if m.icon %}<img src="{{ m.icon }}">{% endif %}{{ m.name }}</span><span class="r" style="color:var(--pal-gold);font-weight:800">×{{ m.count }}</span></div>{% endfor %}
    {% if build %}<div style="margin-top:10px;font-size:13px;color:var(--pal-sub);line-height:1.6">{{ build }}</div>{% endif %}
  </div>{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版主动技能详情。变量契约与 SKILL_TMPL 一致 ----
SKILL_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    <div class="ig-node" style="width:60px;height:60px">{% if icons.element[element] %}<img src="{{ icons.element[element] }}">{% endif %}</div>
    <div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div>
      <div class="ig-sub"><span class="ig-badge">{% if icons.element[element] %}<img src="{{ icons.element[element] }}">{% endif %}{{ element }}属性</span>{% if is_fruit %}<span class="ig-pill">技能果实可得</span>{% endif %}{% if effect %}<span class="ig-pill">{{ effect }}</span>{% endif %}</div></div>
  </div>
  <div class="ig-panel">
    <div class="ig-ivr" style="margin-top:0">
      <div class="ig-ivb"><div class="ivv">{{ power or "—" }}</div><div class="ivk">威力</div></div>
      <div class="ig-ivb"><div class="ivv">{{ cooldown or "—" }}</div><div class="ivk">冷却(秒)</div></div>
    </div>
    <div class="ig-sec" style="margin-top:14px">效果</div>
    <div style="font-size:14.5px;color:var(--pal-text-2);line-height:1.8">{{ desc or "（暂无描述）" }}</div>
    {% if is_fruit %}<div style="margin-top:12px;font-size:12.5px;color:var(--pal-sub);line-height:1.7">此技能可通过「{{ element }}之技能果实：{{ name }}」喂给帕鲁学会(技能果实在地牢/野外宝箱、商人处获取)。</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版排行榜(肝帝/图鉴/财富等)。变量契约与 RANK_TMPL 一致 ----
RANK_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ rank_title | default('本周肝帝榜') }}</div>
    <div class="ig-sub">{{ rank_sub | default('本周在线时长排行 · 看谁最肝～') }}</div></div></div>
  {% if not rows %}
  <div class="ig-panel" style="flex:1;display:flex;align-items:center;justify-content:center;min-height:200px"><div style="text-align:center"><div style="font-size:16px;color:var(--pal-text-2)">本周还没有在线记录</div><div style="font-size:12.5px;color:var(--pal-sub);margin-top:6px">玩起来！在线时长会自动统计上榜～</div></div></div>
  {% else %}
  <div class="ig-panel">
    {% for r in rows %}
    <div class="ig-rankrow{% if loop.index <= 3 %} top{% endif %}">
      <div class="mdl">{{ r.medal }}</div>
      <div style="flex:1;min-width:0"><div class="rn">{{ r.name }}{% if r.online %}<span class="dot"></span>{% endif %}</div><div class="ig-track" style="margin-top:6px"><div class="ig-fill" style="width:{{ r.pct }}%"></div></div></div>
      <div class="rv">{{ r.dur }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版全服战力榜。变量契约与 POWER_TMPL 一致 ----
POWER_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ title | default('全服战力榜') }}</div><div class="ig-sub">{{ sub }}</div></div></div>
  <div class="ig-panel">
    {% for r in rows %}
    <div class="ig-rankrow{% if r.rank <= 3 %} top{% endif %}">
      <div class="mdl">{{ r.medal }}</div>
      {% if r.icon %}<img class="pic" src="{{ r.icon }}">{% endif %}
      <div style="flex:1;min-width:0"><div class="rn">{{ r.name }}{% if r.lucky %}<img class="inl" src="{{ icons.pal.lucky }}">{% elif r.alpha %}<img class="inl" src="{{ icons.pal.alpha }}">{% endif %}</div><div class="rs">Lv.{{ r.level }}{% if r.owner %} · {{ r.owner }}{% endif %}{% if r.element %} · {{ r.element }}{% endif %}</div></div>
      <div style="text-align:right;flex:none"><div class="rv">{{ r.power }}</div><div class="ig-track" style="width:56px;margin-top:4px"><div class="ig-fill" style="width:{{ r.pct }}%"></div></div></div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:9px;text-align:center;font-size:12px;color:var(--pal-gold)">{{ pager }}</div>{% endif %}
    <div style="margin-top:9px;text-align:center;font-size:11px;color:var(--pal-dim)">战力为综合评分(等级/种族/天赋/浓缩/被动),仅供横向对比</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帕鲁战力榜。变量契约与 PALPOWER_TMPL 一致 ----
PALPOWER_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁战力榜</div><div class="ig-sub">{{ sub }}</div></div></div>
  <div class="ig-panel">
    {% for r in rows %}
    <div class="ig-rankrow{% if r.rank <= 3 %} top{% endif %}">
      <div class="mdl">{{ r.medal }}</div>
      {% if r.icon %}<img class="pic" src="{{ r.icon }}">{% endif %}
      <div style="flex:1;min-width:0"><div class="rn">{{ r.name }}{% if r.boss=='tower' %}<img class="inl" src="{{ icons.pal.alpha }}">{% elif r.boss=='boss' %}<img class="inl" src="{{ icons.pal.alpha }}">{% endif %}</div><div class="rs">{{ r.element }} · 稀有度 {{ r.rarity }}</div></div>
      <div style="text-align:right;flex:none"><div class="rv">{{ r.power }}</div><div class="ig-track" style="width:56px;margin-top:4px"><div class="ig-fill" style="width:{{ r.pct }}%"></div></div></div>
    </div>
    {% endfor %}
    <div style="margin-top:9px;text-align:center;font-size:11px;color:var(--pal-dim)">第 {{ page }}/{{ total_pages }} 页 · 「/帕鲁战力榜 帕鲁名」查详情</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版单帕鲁战力详情。变量契约与 PALPOWERDETAIL_TMPL 一致 ----
PALPOWERDETAIL_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">
    {% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% endif %}
    <div style="flex:1;min-width:0"><div class="ig-title">{{ name }} · 战力</div>
      <div class="ig-sub"><span class="ig-pill">#{{ rank }} / {{ total }}</span>{% for e in elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}<span class="ig-pill">稀有度 {{ rarity }}</span></div></div>
    <div style="text-align:right;flex:none"><div style="font-size:30px;font-weight:800;color:var(--pal-gold);line-height:1">{{ power }}</div><div style="font-size:11px;color:var(--pal-sub)">种族战力</div></div>
  </div>
  <div class="ig-panel">
    {% for s in stats %}
    <div class="ig-stat"><div class="lab"><span>{{ s.k }}</span><b>{{ s.v }}</b></div><div class="ig-track"><div class="ig-fill" style="width:{{ s.pct }}%"></div></div></div>
    {% endfor %}
    {% if partner %}<div style="margin-top:12px;font-size:13px;color:var(--pal-sub)">伙伴技能：{{ partner }}</div>{% endif %}
    <div style="margin-top:12px;padding-top:10px;border-top:1px solid var(--pal-line);text-align:center;font-size:11px;color:var(--pal-dim);line-height:1.7">种族值 生命{{ base.hp }} · 近战{{ base.melee }} · 远程{{ base.shot }} · 防御{{ base.df }} · Lv{{ reflv }}满级战力</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版公会。变量契约与 GUILD_TMPL 一致 ----
GUILD_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ gname }}</div><div class="ig-sub">公会成员 · 共 {{ total }} 人{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %}</div></div></div>
  <div class="ig-panel">
    <div class="ig-stiles" style="margin-bottom:12px">
      <div class="ig-stile"><div class="v">{{ total }}</div><div class="k">成员数</div></div>
      <div class="ig-stile"><div class="v" style="font-size:14px">{{ leader }}</div><div class="k">会长</div></div>
      <div class="ig-stile"><div class="v">{{ rank }}</div><div class="k">成员规模</div></div>
    </div>
    {% for m in members %}<div class="ig-prow"><span style="width:26px;height:26px;flex:none;border-radius:50%;background:rgba(255,255,255,.06);border:1px solid var(--pal-line);color:var(--pal-sub);font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center">{{ m.no }}</span><span class="pnm">{{ m.name }}</span>{% if m.is_leader %}<span class="ig-pill gold">会长</span>{% endif %}</div>{% endfor %}
    {% if pager %}<div style="margin-top:13px;text-align:center;font-size:12.5px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版掉落查询。变量契约与 DROP_TMPL 一致 ----
DROP_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if item_icon %}<div class="ig-portrait" style="width:70px;height:70px;border-width:10px"><img src="{{ item_icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">掉落查询</div><div class="ig-sub">掉落「{{ item }}」的帕鲁 · 共 {{ total }} 种{% if pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %}</div></div></div>
  <div class="ig-panel">
    {% for r in rows %}<div class="ig-rankrow">{% if r.icon %}<img class="pic" src="{{ r.icon }}">{% endif %}<div style="flex:1;min-width:0"><div class="rn">{{ r.pal }}</div><div class="rs">No.{{ r.index }}</div></div><div style="text-align:right;flex:none"><div class="rv">{{ r.rate }}%</div>{% if r.qty %}<div class="rs">×{{ r.qty }}</div>{% endif %}</div></div>{% endfor %}
    {% if pager %}<div style="margin-top:12px;text-align:center;font-size:12.5px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版掉落物品目录(单列)。变量契约与 DROPLIST_TMPL 一致 ----
DROPLIST_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">掉落物品目录</div><div class="ig-sub">{{ sub }}</div></div></div>
  <div class="ig-panel">
    {% for r in rows %}<div class="ig-drop"><span class="l">{% if r.icon %}<img src="{{ r.icon }}">{% endif %}{{ r.name }}</span><span class="r">{{ r.count }} 只掉</span></div>{% endfor %}
    <div style="margin-top:10px;text-align:center;font-size:12px;color:var(--pal-dim)">发 /帕鲁哪里掉 物品名 查掉落的帕鲁{% if pager %} · {{ pager }}{% endif %}</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版闪光/头目墙(3列)。变量契约与 SHINY_TMPL 一致 ----
SHINY_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ title }}</div><div class="ig-sub">{{ sub }}</div></div></div>
  <div class="ig-panel">
    <div class="ig-shwall">
    {% for r in rows %}<div class="ig-shcell"><div class="pv">{% if r.icon %}<img src="{{ r.icon }}">{% endif %}</div><div class="nm">{{ r.name }}</div><div class="ow">{{ r.owner }}</div></div>{% endfor %}
    </div>
    {% if top_owners %}<div style="margin-top:12px;text-align:center;font-size:12.5px;color:var(--pal-sub)">收藏家：{{ top_owners }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帕鲁伤病治疗。变量契约与 SYMPTOM_TMPL 一致 ----
SYMPTOM_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁伤病治疗</div><div class="ig-sub">{{ sub }}</div></div></div>
{% if single %}
  <div class="ig-panel"><div style="font-size:18px;font-weight:800;color:var(--pal-text);text-align:center">{{ name }}</div>
    <div style="margin-top:12px;font-size:14.5px;color:var(--pal-text-2);line-height:1.9;white-space:pre-line;word-break:break-word;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;padding:12px 15px">{{ desc }}</div>
  </div>
  {% if items %}<div class="ig-panel hi"><div class="ig-sec">治疗道具</div>
    <div style="display:flex;flex-wrap:wrap;gap:12px;justify-content:center">
    {% for it in items %}<div style="text-align:center;width:100px"><div class="ig-slot" style="width:80px;margin:0 auto">{% if it.icon %}<img src="{{ it.icon }}">{% endif %}</div><div style="margin-top:6px;font-size:13px;color:var(--pal-text-2)">{{ it.name }}</div></div>{% endfor %}
    </div>
  </div>{% endif %}
{% else %}
  <div class="ig-panel">
    {% for r in rows %}<div class="ig-rankrow" style="align-items:flex-start">
      <div style="flex:none;display:flex;gap:6px">{% for it in r.items %}<div class="ig-slot" style="width:46px">{% if it.icon %}<img src="{{ it.icon }}">{% endif %}</div>{% endfor %}</div>
      <div style="flex:1;min-width:0"><div style="font-size:15px;font-weight:800;color:var(--pal-text)">{{ r.name }}</div><div style="font-size:12.5px;color:var(--pal-sub);line-height:1.55;margin-top:2px">{{ r.desc }}</div></div>
    </div>{% endfor %}
  </div>
{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版反配种。变量契约与 REVERSE_TMPL 一致 ----
REVERSE_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if target_icon %}<div class="ig-portrait" style="width:70px;height:70px;border-width:10px"><img src="{{ target_icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">反配种</div><div class="ig-sub">配出「{{ target }}」#{{ target_index }} 的亲代组合 · 共 {{ total }} 组 · 第 {{ page }}/{{ pages }} 页</div></div></div>
  <div class="ig-panel">
    {% for r in rows %}<div class="ig-breedrow">
      <div class="pa"><span class="nm">{{ r.a }}</span>{% if r.a_icon %}<img src="{{ r.a_icon }}">{% endif %}</div>
      <span class="plus">＋</span>
      <div class="pb">{% if r.b_icon %}<img src="{{ r.b_icon }}">{% endif %}<span class="nm">{{ r.b }}</span></div>
    </div>{% endfor %}
    {% if pager %}<div style="margin-top:12px;text-align:center;font-size:12.5px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版在线热力图。变量契约与 HEATMAP_TMPL 一致 ----
HEATMAP_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">在线热力图</div><div class="ig-sub">{{ sub }}</div></div></div>
  <div class="ig-panel">
    {% set colors = ['rgba(255,255,255,.05)','rgba(125,211,224,.28)','rgba(125,211,224,.55)','rgba(240,207,122,.55)','#f0cf7a'] %}
    <div style="display:flex;gap:2px;padding-left:32px;margin-bottom:3px">{% for h in range(24) %}<div style="flex:1;font-size:8px;color:var(--pal-dim);text-align:center">{{ h }}</div>{% endfor %}</div>
    {% for r in rows %}<div style="display:flex;align-items:center;gap:2px;margin-bottom:2px"><div style="width:30px;font-size:11px;color:var(--pal-sub);flex-shrink:0">{{ r.label }}</div>{% for c in r.cells %}<div style="flex:1;height:16px;border-radius:2px;background:{{ colors[c] }}"></div>{% endfor %}</div>{% endfor %}
    <div style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:12px;font-size:11px;color:var(--pal-sub)"><span>少</span>{% for c in colors %}<div style="width:18px;height:11px;border-radius:2px;background:{{ c }}"></div>{% endfor %}<span>多</span></div>
    {% if hint %}<div style="margin-top:11px;text-align:center;font-size:12.5px;color:var(--pal-text-2)">{{ hint }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版属性克制图(2列)。变量契约与 ELEMENT_TMPL 一致 ----
ELEMENT_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁属性克制图</div><div class="ig-sub"><span class="ig-pill">9 系属性</span><span class="ig-pill">克制方 ×1.5 伤害</span></div></div></div>
  <div class="ig-panel">
    <div class="ig-elemgrid">
    {% for e in elems %}
      <div class="ig-ecard" style="border-color:{{ e.color }}66">
        <div style="display:flex;align-items:center;gap:8px"><div class="ig-node" style="width:36px;height:36px">{% if icons.element[e.cn] %}<img src="{{ icons.element[e.cn] }}">{% endif %}</div><span style="font-size:15px;font-weight:800;color:{{ e.color }}">{{ e.cn }}属性</span></div>
        <div class="er"><span class="lb" style="color:var(--pal-good)">克制</span>{% if e.strong %}{% for s in e.strong %}<span class="et">{% if icons.element[s.cn] %}<img src="{{ icons.element[s.cn] }}">{% endif %}{{ s.cn }}</span>{% endfor %}{% else %}<span style="color:var(--pal-dim)">无</span>{% endif %}</div>
        <div class="er"><span class="lb" style="color:var(--pal-danger)">被克</span>{% if e.weak %}{% for w in e.weak %}<span class="et">{% if icons.element[w.cn] %}<img src="{{ icons.element[w.cn] }}">{% endif %}{{ w.cn }}</span>{% endfor %}{% else %}<span style="color:var(--pal-dim)">无</span>{% endif %}</div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:13px;font-size:12px;color:var(--pal-sub);line-height:1.7">用克制属性的帕鲁/技能攻击,伤害提升约 50%;被克制时己方更脆。捕捉强力帕鲁时带克制属性更省球。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版栖息分布(带地图)。变量契约与 HABITAT_TMPL 一致 ----
HABITAT_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-portrait" style="width:76px;height:76px;border-width:11px"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ name }} · 栖息分布</div><div class="ig-sub"><span class="ig-pill">No.{{ index }}</span>{% for e in elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}{% if nocturnal %}<span class="ig-pill">夜行</span>{% endif %}{% if map_label %}<span class="ig-pill">{{ map_label }}</span>{% endif %}</div></div></div>
  <div style="position:relative;width:100%;border:1px solid var(--pal-line);border-radius:3px;overflow:hidden">
    <img src="{{ mapimg }}" style="display:block;width:100%">
    <div style="position:absolute;inset:0;mix-blend-mode:screen">{% for pt in points %}<div style="position:absolute;left:{{pt.l}}%;top:{{pt.t}}%;width:26px;height:26px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,{{color}}d0,{{color}}00 62%)"></div>{% endfor %}</div>
    {% for pt in boss_points %}<img src="{{ icons.pal.alpha }}" style="position:absolute;left:{{pt.l}}%;top:{{pt.t}}%;transform:translate(-50%,-100%);z-index:6;width:22px;height:22px;filter:drop-shadow(0 1px 3px rgba(0,0,0,.95))">{% endfor %}
  </div>
  <div class="ig-panel" style="margin-top:12px">
    <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:13px;color:var(--pal-text-2)"><span style="display:inline-flex;align-items:center;gap:5px"><span style="width:12px;height:12px;border-radius:50%;background:{{color}};display:inline-block"></span>栖息热区</span>{% if boss_points %}<span class="ig-pill" style="background:#d42c2c;color:#fff">{{ boss_label }} {{ boss_lv }} · {{ boss_points|length }}处</span>{% endif %}<span class="ig-pill">{{ count }} 个刷新点</span>{% if has_day and has_night %}<span class="ig-pill">日夜均刷</span>{% elif nocturnal %}<span class="ig-pill">夜间为主</span>{% endif %}</div>
    {% if regions %}<div class="ig-sec" style="margin-top:13px">主要出没区域</div>
    <div style="display:flex;flex-direction:column;gap:7px">{% for r in regions %}<div style="display:flex;align-items:center;gap:9px"><span style="flex:none;width:92px;font-size:13px;color:var(--pal-text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</span><span style="flex:1;height:10px;border-radius:2px;background:rgba(0,0,0,.35);overflow:hidden"><span style="display:block;height:100%;width:{{ r.pct }}%;background:linear-gradient(90deg,{{color}}88,{{color}})"></span></span><span style="flex:none;width:36px;text-align:right;font-size:12px;color:var(--pal-sub)">{{ r.pct }}%</span></div>{% endfor %}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版玩家分布地图。变量契约与 MAP_TMPL 一致 ----
MAP_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">在线玩家分布</div><div class="ig-sub">{{ subtitle }}</div></div></div>
  {% for m in maps %}
  {% if maps|length > 1 %}<div class="ig-sec" style="margin:{% if not loop.first %}16px{% else %}2px{% endif %} 0 8px">{{ m.label }} · {{ m.players|length }} 人</div>{% endif %}
  <div style="position:relative;width:100%;border:1px solid var(--pal-line);border-radius:3px;overflow:hidden">
    <img src="{{ m.mapimg }}" style="display:block;width:100%">
    {% for p in m.players %}<div style="position:absolute;left:{{ p.left }}%;top:{{ p.top }}%;transform:translate(-50%,-100%);width:16px;height:21px;z-index:5"><div style="position:absolute;top:0;left:0;width:16px;height:16px;border-radius:50%;background:radial-gradient(circle at 55% 40%,#ff9a9a,#d12f2f);border:1.5px solid #fff"></div><div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:0;height:0;border-left:3.5px solid transparent;border-right:3.5px solid transparent;border-top:6px solid #d12f2f"></div><div style="position:absolute;top:0;left:0;width:16px;height:16px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:9px;font-weight:800">{{ p.no }}</div></div>{% endfor %}
  </div>
  <div class="ig-panel" style="margin-top:12px">
    {% for p in m.players %}<div class="ig-prow"><span style="width:24px;height:24px;flex:none;border-radius:50%;background:var(--pal-gold);color:#0e1015;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center">{{ p.no }}</span><span class="pnm">{{ p.name }}</span><span class="ig-pill">Lv.{{ p.level }}</span><span style="margin-left:auto;text-align:right"><span style="font-size:13px;color:var(--pal-text-2)">{{ p.region }}</span><span style="display:block;font-size:11px;color:var(--pal-dim)">坐标 {{ p.coord }}</span></span></div>{% endfor %}
  </div>
  {% endfor %}
  {% if offmap %}
  <div class="ig-panel" style="margin-top:12px">
    <div class="ig-sec" style="margin-bottom:6px">位置待确认 · 不在已知地图范围</div>
    {% for p in offmap %}<div class="ig-prow"><span style="width:24px;height:24px;flex:none;border-radius:50%;background:var(--pal-panel-hi);color:var(--pal-text-2);font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center">{{ p.no }}</span><span class="pnm">{{ p.name }}</span><span class="ig-pill">Lv.{{ p.level }}</span><span style="margin-left:auto;font-size:11px;color:var(--pal-dim)">坐标 {{ p.coord }}</span></div>{% endfor %}
  </div>
  {% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版任务详情。变量契约与 MISSION_TMPL 一致 ----
MISSION_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div><div class="ig-sub"><span class="ig-pill" style="color:{{tcolor}}">{{ tlabel }}</span>{% if order %}<span class="ig-pill">主线 第 {{ order }}/{{ order_total or 55 }}</span>{% endif %}{% if group %}<span class="ig-pill">{{ group }}</span>{% endif %}</div></div></div>
  <div class="ig-panel">{% if desc %}<div style="font-size:14.5px;color:var(--pal-text-2);line-height:1.85;white-space:pre-line">{{ desc }}</div>{% endif %}
    <div class="ig-sec" style="margin-top:14px">目标</div><div style="font-size:14px;color:var(--pal-text-2);line-height:1.7">{{ objective or "按上方任务说明完成即可" }}{% if coords %}<br><span class="ig-pill" style="margin-top:6px;display:inline-block">地图坐标 <b style="color:var(--pal-gold);margin-left:3px">{{ coords }}</b></span>{% endif %}</div>
    {% if exp or rewards %}<div class="ig-sec" style="margin-top:14px">任务奖励</div><div style="display:flex;flex-wrap:wrap;gap:7px">{% if exp %}<span class="ig-pill gold">经验 +{{ exp }}</span>{% endif %}{% for r in rewards %}<span class="ig-pill">{{ r.name }} ×{{ r.qty }}</span>{% endfor %}</div>{% endif %}
    {% if nextname %}<div class="ig-sec" style="margin-top:14px">下一环</div><div style="font-size:14px;color:var(--pal-sub)">{{ nextname }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版任务列表。变量契约与 MISSIONLIST_TMPL 一致 ----
MISSIONLIST_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ title }}</div><div class="ig-sub"><span class="ig-pill">{{ subtitle }}</span></div></div></div>
  <div class="ig-panel">
    {% for it in rows %}<div class="ig-prow"><span class="ig-pill gold" style="min-width:30px;text-align:center;justify-content:center">{{ it.tag }}</span><span style="flex:none;font-size:14px;font-weight:700;color:var(--pal-text);max-width:42%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ it.name }}</span><span style="flex:1;min-width:0;font-size:12.5px;color:var(--pal-sub);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ it.brief }}</span></div>{% endfor %}
    <div style="margin-top:10px;font-size:12px;color:var(--pal-dim);line-height:1.7">发「{{ detailhint }}」看某个任务的详细攻略{% if pagehint %};{{ pagehint }}{% endif %}</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版 Boss/塔主/突袭 详情。变量契约与 BOSS_TMPL 一致 ----
BOSS_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-portrait" style="width:78px;height:78px;border-width:11px"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div><div class="ig-sub"><span class="ig-pill" style="color:{{color}}">{{ catlabel }}</span>{% for e in elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}{% if difficulty %}<span class="ig-pill">{{ difficulty }}</span>{% endif %}</div></div></div>
  <div class="ig-panel">
    <div class="ig-ivr" style="margin-top:0"><div class="ig-ivb"><div class="ivv">Lv.{{ level or "—" }}</div><div class="ivk">等级</div></div><div class="ig-ivb"><div class="ivv" style="color:var(--pal-danger)">{{ hp or "—" }}</div><div class="ivk">生命值</div></div></div>
    {% if location %}<div class="ig-sec" style="margin-top:13px">所在</div><div style="font-size:14px;color:var(--pal-text-2)">{{ location }}</div>{% endif %}
    {% if drops %}<div class="ig-sec" style="margin-top:13px">掉落</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for d in drops %}<span class="ig-pill">{{ d }}</span>{% endfor %}</div>{% endif %}
    <div class="ig-sec" style="margin-top:13px">攻略提示</div><div style="font-size:13px;color:var(--pal-sub);line-height:1.8">{{ tip }}</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版商人。变量契约与 MERCHANT_TMPL 一致 ----
MERCHANT_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-portrait" style="width:74px;height:74px;border-width:10px"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ title }}</div><div class="ig-sub">{% for b in badges %}<span class="ig-pill">{{ b }}</span>{% endfor %}</div></div></div>
  <div class="ig-panel">{% if note %}<div style="font-size:13px;color:var(--pal-sub);margin-bottom:10px">{{ note }}</div>{% endif %}
    {% for r in rows %}<div class="ig-prow"><span style="flex:1;min-width:0;font-size:14.5px;color:var(--pal-text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.name }}</span>{% if r.sub %}<span style="flex:none;font-size:12px;color:var(--pal-sub)">{{ r.sub }}</span>{% endif %}{% if r.right %}<span style="flex:none;font-size:14px;font-weight:800;color:var(--pal-gold)">{{ r.right }}</span>{% endif %}</div>{% endfor %}
    {% if foot %}<div style="margin-top:10px;font-size:12px;color:var(--pal-dim);line-height:1.7">{{ foot }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版技能果实。变量契约与 SKILLFRUIT_TMPL 一致 ----
SKILLFRUIT_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% else %}<div class="ig-node" style="width:60px;height:60px">{% if icons.element[element] %}<img src="{{ icons.element[element] }}">{% endif %}</div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ fruit_name }}</div><div class="ig-sub"><span class="ig-badge">{% if icons.element[element] %}<img src="{{ icons.element[element] }}">{% endif %}{{ element }}属性</span>{% if power and power != "0" %}<span class="ig-pill">威力 {{ power }}</span>{% endif %}{% if cooldown %}<span class="ig-pill">冷却 {{ cooldown }}s</span>{% endif %}</div></div></div>
  <div class="ig-panel">{% if effect %}<span class="ig-pill gold" style="margin-bottom:10px;display:inline-block">{{ effect }}</span>{% endif %}<div style="font-size:14.5px;color:var(--pal-text-2);line-height:1.9;white-space:pre-line;word-break:break-word">{{ desc or "（暂无描述）" }}</div>
    <div class="ig-sec" style="margin-top:14px">用法</div><div style="font-size:14px;color:var(--pal-sub);line-height:1.75;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;padding:12px 14px">将此技能果实喂给帕鲁,即可让它学会主动技能<b style="color:var(--pal-gold)">「{{ tech }}」</b>。技能果实可在世界各地的宝箱等处获得。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版植入体。变量契约与 IMPLANT_TMPL 一致 ----
IMPLANT_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-portrait"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div><div class="ig-sub">{% if rank %}<span class="ig-pill gold">稀有度 {{ "★" * (rank if rank <= 5 else 5) }}</span>{% endif %}{% if consumable %}<span class="ig-pill" style="background:#e07a1a;color:#fff">耗材·一次性</span>{% else %}<span class="ig-pill">可反复植入</span>{% endif %}</div></div></div>
  <div class="ig-panel"><div class="ig-sec">赋予词条</div>
    <div style="display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;padding:12px 14px"><span style="font-size:16px;font-weight:800;color:var(--pal-text)">「{{ passive }}」</span>{% if effect %}<span style="font-size:14px;color:{% if sign < 0 %}var(--pal-danger){% else %}var(--pal-good){% endif %}">{{ effect }}</span>{% endif %}</div>
    <div class="ig-sec" style="margin-top:14px">用法</div><div style="font-size:14px;color:var(--pal-sub);line-height:1.75">在据点的帕鲁改造设备上,用此植入体为帕鲁植入被动词条「{{ passive }}」。{% if consumable %}耗材型使用后消耗,效果通常更强力。{% else %}可反复植入或替换词条。{% endif %}</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版世界树守护者。变量契约与 WORLDTREE_TMPL 一致 ----
WORLDTREE_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">世界树 Boss</div><div class="ig-sub"><span class="ig-pill gold">1.0 世界树</span><span class="ig-pill">守护者 + 最终 Boss</span></div></div></div>
  <div class="ig-panel"><div style="font-size:13.5px;color:var(--pal-sub);line-height:1.75">世界树深处的守护者(暮尘蛾 / 夜蔓爵,可捕获)镇守通往深渊之路;击败后在最深处迎战最终剧情 Boss「枯星龙」(苏醒,不可捕获)。对应主线「通往深渊之路 → 苏醒」。</div></div>
  {% for b in bosses %}
  <div class="ig-panel hi"><div class="ig-teamcard">
    {% if b.icon %}<div class="tpic"><img src="{{ b.icon }}"></div>{% endif %}
    <div style="flex:1;min-width:0"><div style="font-size:18px;font-weight:800;color:var(--pal-text)">{{ b.name }} <span style="font-size:12px;color:var(--pal-sub);font-weight:400">#{{ b.index }}</span> <span class="ig-pill{% if not b.is_final %} gold{% endif %}"{% if b.is_final %} style="color:var(--pal-danger)"{% endif %}>{{ b.role }}</span></div>
      <div style="margin:5px 0;display:flex;flex-wrap:wrap;gap:5px">{% for e in b.elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}<span class="ig-pill">稀有度 {{ b.rarity }}</span>{% if b.hp %}<span class="ig-pill">HP {{ b.hp }}</span>{% endif %}{% if b.story_only %}<span class="ig-pill" style="color:var(--pal-danger)">剧情战·不可捕获</span>{% endif %}</div>
      {% if b.partner %}<div style="font-size:12.5px;color:var(--pal-good);margin-top:2px">伙伴技能：{{ b.partner }}</div>{% endif %}
      {% if b.skills %}<div style="font-size:12px;color:var(--pal-text-2);margin-top:4px;line-height:1.6"><b style="color:var(--pal-sub)">技能</b> {{ b.skills|join('、') }}</div>{% endif %}
      {% if b.drops %}<div style="font-size:12px;color:var(--pal-gold);margin-top:3px"><b style="color:var(--pal-sub)">掉落</b> {{ b.drops|join('、') }}</div>{% endif %}
    </div>
  </div></div>
  {% endfor %}
  <div class="ig-panel"><div style="font-size:12.5px;color:var(--pal-sub)">发 /帕鲁图鉴 {{ bosses[0].name }} 看完整属性/工作适性/伙伴技能详情;发 /帕鲁栖息地 红菇娘（或 燎火舞伶 / 磐甲龙）可查看世界树独立地图。</div></div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版 1.0 总览。变量契约与 V10_TMPL 一致 ----
V10_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">幻兽帕鲁 1.0 · 全面支持</div><div class="ig-sub"><span class="ig-pill gold">正式版数据已更新</span></div></div></div>
  <div class="ig-panel"><div class="ig-sec">数据收录 <span style="font-size:11px;color:var(--pal-sub);font-weight:400">· 帕鲁 {{ stats['pals'] }} 只可收集,含变体共 {{ stats['pals_total'] }} 个数据实体</span></div>
    <div class="ig-stiles">
      {% set cells = [("帕鲁图鉴",stats['pals']),("物品",stats['items']),("主动技能",stats['skills']),("科技",stats['tech']),("建筑设施",stats['buildings']),("制作配方",stats['recipes']),("研究所",stats['lab']),("技能果实",stats['fruits']),("植入体",stats['implants'])] %}
      {% for label,num in cells %}<div class="ig-stile"><div class="v">{{ num }}</div><div class="k">{{ label }}</div></div>{% endfor %}
    </div>
  </div>
  <div class="ig-panel hi"><div class="ig-sec">1.0 新增查询</div>
    <div style="display:flex;flex-direction:column;gap:7px;font-size:13px;color:var(--pal-text-2)">
      <div><b style="color:var(--pal-gold)">/帕鲁研究所</b> — 全局增益研究,按「手工1」编号查</div>
      <div><b style="color:var(--pal-gold)">/帕鲁技能果实</b> — 92种果实按元素分类</div>
      <div><b style="color:var(--pal-gold)">/帕鲁植入体</b> — 68种改造词条</div>
      <div><b style="color:var(--pal-gold)">/帕鲁世界树</b> — 最终boss专题</div>
    </div>
    <div style="margin-top:12px;font-size:12px;color:var(--pal-dim)">全部查询支持:名称 / 模糊 / 编号 / 分类浏览。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帕鲁觉醒。变量契约与 AWAKENING_TMPL 一致 ----
AWAKENING_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁觉醒</div><div class="ig-sub">1.0 觉醒系统 · 世界树能量解放隐藏能力</div></div></div>
  <div class="ig-panel"><div class="ig-sec">九系觉醒晶石</div>
    <div class="ig-stiles">
    {% for g in gems %}<div class="ig-stile" style="border-color:{{g.color}}66"><div style="height:40px;display:flex;align-items:center;justify-content:center">{% if g.gem_icon %}<img src="{{g.gem_icon}}" style="width:36px;height:36px;object-fit:contain">{% elif icons.element[g.elem] %}<img src="{{ icons.element[g.elem] }}" style="width:32px;height:32px;object-fit:contain">{% endif %}</div><div style="font-size:12.5px;font-weight:800;color:{{g.color}}">{{g.elem}}系</div><div style="font-size:10px;color:var(--pal-dim);margin-top:1px">{{g.mat}}→晶石</div></div>{% endfor %}
    </div>
    <div style="margin-top:13px;padding:11px 13px;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;font-size:12.5px;color:var(--pal-sub);line-height:1.75"><b style="color:var(--pal-gold)">觉醒机制</b>:击败世界树 Boss 后解锁。用对应属性的辉石加工成觉醒晶石,让该属性帕鲁「觉醒」、解放隐藏能力。<br>具体觉醒提升数值与所需晶石数量,游戏文件未以数据表明确提供,以游戏内为准;暂不支持读取存档中的觉醒状态。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帕鲁突变。变量契约与 MUTATION_TMPL 一致 ----
MUTATION_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁突变</div><div class="ig-sub">1.0 突变机制 · 特殊蛋糕影响配种结果</div></div></div>
  <div class="ig-panel"><div class="ig-sec">特殊蛋糕(放入繁殖牧场影响后代)</div>
    {% for c in cakes %}<div class="ig-drop"><span class="l">{% if c.icon %}<img src="{{c.icon}}">{% endif %}<span style="display:flex;flex-direction:column;min-width:0"><span style="font-size:14px;font-weight:700;color:var(--pal-text)">{{c.name}}</span><span style="font-size:11.5px;color:var(--pal-sub);line-height:1.4">{{c.effect}}</span></span></span></div>{% endfor %}
    {% if eggs %}<div class="ig-sec" style="margin-top:14px">突变帕鲁蛋</div><div style="display:flex;gap:8px;flex-wrap:wrap">{% for e in eggs %}<span class="ig-pill">{% if e.icon %}<img src="{{e.icon}}" style="width:16px;height:16px;vertical-align:middle;margin-right:3px">{% endif %}{{e.name}}</span>{% endfor %}</div>{% endif %}
    <div style="margin-top:13px;padding:11px 13px;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;font-size:12.5px;color:var(--pal-sub);line-height:1.75"><b style="color:var(--pal-gold)">突变机制</b>:豪华蔬菜蛋糕提升后代突变概率;突变帕鲁外观/属性与普通不同,可能带专属词条。蘑菇蛋糕提升天赋、蔬菜蛋糕一次产2蛋、特制蛋糕提升被动继承。<br>突变准确概率游戏未公开,此处仅说明机制、不猜测数值。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版研究所总览。变量契约与 LAB_OVERVIEW_TMPL 一致 ----
LAB_OVERVIEW_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁研究所</div><div class="ig-sub"><span class="ig-pill">共 {{ total }} 项研究</span><span class="ig-pill">9 大工作适性</span></div></div></div>
  <div class="ig-panel"><div style="font-size:13.5px;color:var(--pal-sub);line-height:1.75;margin-bottom:13px">在据点建造「研究所」后,投入材料与帕鲁工时研究各类工作适性的<b style="color:var(--pal-gold)">全局增益</b>(工作速度/据点战力/孵化/远征等),效果对全服帕鲁生效。</div>
    <div class="ig-stiles">
    {% for c in cats %}<div class="ig-stile"><div style="height:36px;display:flex;align-items:center;justify-content:center">{% if c.icon %}<img src="{{ c.icon }}" style="width:30px;height:30px;object-fit:contain">{% elif c.emoji %}<span style="font-size:28px">{{ c.emoji }}</span>{% endif %}</div><div style="font-size:14px;font-weight:800;color:var(--pal-text)">{{ c.name }}</div><div style="font-size:11px;color:var(--pal-sub);margin-top:3px">{{ c.count }} 项 · <span style="color:var(--pal-good)">{{ c.essential }} 必需</span></div></div>{% endfor %}
    </div>
    <div style="margin-top:13px;font-size:12.5px;color:var(--pal-dim);line-height:1.7">发 /帕鲁研究所 手工 看某类全部研究;发 /帕鲁研究所 &lt;研究名&gt; 看单项材料/前置。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版研究所分类列表(单列)。变量契约与 LAB_LIST_TMPL 一致 ----
LAB_LIST_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-node" style="width:44px;height:44px"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ category }}</div><div class="ig-sub"><span class="ig-pill">{{ items|length }} 项研究</span></div></div></div>
  <div class="ig-panel">
    {% for it in items %}<div class="ig-prow"><span class="ig-pill gold" style="min-width:24px;justify-content:center">{{ loop.index }}</span>{% if it.essential %}<span class="ig-pill" style="background:#5cc97a;color:#0e1015">必需</span>{% endif %}<div style="flex:1;min-width:0"><div style="font-size:14.5px;font-weight:700;color:var(--pal-text)">{{ it.name }}</div>{% if it.effect %}<div style="font-size:12px;color:var(--pal-good);margin-top:2px">{{ it.effect }}</div>{% endif %}</div></div>{% endfor %}
    <div style="margin-top:10px;font-size:12.5px;color:var(--pal-dim)">按编号查:发 /帕鲁研究所 {{ cat_short }}1;或 /帕鲁研究所 &lt;研究名&gt; 查详情。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版研究所详情。变量契约与 LAB_DETAIL_TMPL 一致 ----
LAB_DETAIL_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-node" style="width:52px;height:52px"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ name }}</div><div class="ig-sub"><span class="ig-pill">{{ category }}</span>{% if essential %}<span class="ig-pill" style="background:#5cc97a;color:#0e1015">必需研究</span>{% endif %}{% if work %}<span class="ig-pill">{{ work }} 工时</span>{% endif %}</div></div></div>
  {% if effect %}<div class="ig-panel"><div class="ig-sec">研究效果</div><div style="font-size:15px;color:var(--pal-good);font-weight:700;background:rgba(139,208,106,.1);border:1px solid rgba(139,208,106,.3);border-radius:3px;padding:11px 14px">{{ effect }}</div></div>{% endif %}
  {% if materials %}<div class="ig-panel hi"><div class="ig-sec">所需材料</div><div style="display:flex;flex-wrap:wrap;gap:7px">{% for m in materials %}<span class="ig-pill">{{ m.name }} <b style="color:var(--pal-gold);margin-left:3px">×{{ m.count }}</b></span>{% endfor %}</div></div>{% endif %}
  {% if prereq %}<div class="ig-panel"><div class="ig-sec">前置研究</div><div style="font-size:14px;color:var(--pal-sub)">需先完成「{{ prereq }}」</div></div>{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帕鲁配种。变量契约与 BREED_TMPL 一致 ----
BREED_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁配种</div><div class="ig-sub">亲代组合的后代</div></div></div>
  <div class="ig-panel">
    <div style="display:flex;align-items:center;justify-content:center;gap:10px;padding:4px 0 12px">
      <div class="ig-stile" style="flex:1;max-width:150px;padding:14px 8px">{% if a.icon %}<img src="{{ a.icon }}" style="width:50px;height:50px;object-fit:contain;display:block;margin:0 auto 6px">{% endif %}<div style="font-size:17px;font-weight:800;color:var(--pal-text)">{{ a.name }}</div><div style="font-size:11px;color:var(--pal-sub);margin-top:3px">#{{ a.index }}</div><div style="margin-top:7px;display:flex;gap:4px;justify-content:center;flex-wrap:wrap">{% for e in a.elements %}<span class="ig-badge" style="font-size:11px;padding:1px 6px 1px 4px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}</div></div>
      <div style="font-size:26px;font-weight:900;color:var(--pal-gold);flex:none">＋</div>
      <div class="ig-stile" style="flex:1;max-width:150px;padding:14px 8px">{% if b.icon %}<img src="{{ b.icon }}" style="width:50px;height:50px;object-fit:contain;display:block;margin:0 auto 6px">{% endif %}<div style="font-size:17px;font-weight:800;color:var(--pal-text)">{{ b.name }}</div><div style="font-size:11px;color:var(--pal-sub);margin-top:3px">#{{ b.index }}</div><div style="margin-top:7px;display:flex;gap:4px;justify-content:center;flex-wrap:wrap">{% for e in b.elements %}<span class="ig-badge" style="font-size:11px;padding:1px 6px 1px 4px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}</div></div>
    </div>
    <div style="text-align:center;font-size:13px;color:var(--pal-gold);font-weight:800;margin:2px 0">═══ 后代 ═══</div>
    <div style="text-align:center;padding:6px 0">{% if c.icon %}<img src="{{ c.icon }}" style="width:70px;height:70px;object-fit:contain;display:block;margin:0 auto 4px">{% endif %}<div style="font-size:26px;font-weight:800;color:var(--pal-text)">{{ c.name }}</div><div style="font-size:12px;color:var(--pal-sub);margin-top:4px">图鉴 #{{ c.index }} · <span style="color:var(--pal-gold)">{{ "★" * (c.rarity if c.rarity <= 5 else 5) if c.rarity else "★" }}</span></div><div style="display:flex;gap:6px;justify-content:center;margin-top:9px">{% for e in c.elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}</div></div>
  </div>
  {% if child_breeds %}<div class="ig-panel hi"><div class="ig-sec">用 {{ child_name }} 继续配</div>
    {% for cb in child_breeds %}<div class="ig-breedrow"><div class="pa"><span class="nm" style="font-size:12.5px">{{ child_name }} ＋ {{ cb.partner }}</span></div><span class="plus">→</span><div class="pb">{% if cb.result_icon %}<img src="{{ cb.result_icon }}">{% endif %}<span class="nm" style="font-size:12.5px">{{ cb.result }}</span></div></div>{% endfor %}
  </div>{% endif %}
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版配种路线。变量契约与 ROUTE_TMPL 一致 ----
ROUTE_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if target_icon %}<div class="ig-portrait" style="width:66px;height:66px;border-width:9px"><img src="{{ target_icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">配种路线 → {{ target }}</div><div class="ig-sub">{{ sub }}</div></div></div>
  <div class="ig-panel">
    {% for s in steps %}<div class="ig-rankrow{% if s.is_target %} top{% endif %}" style="gap:5px;padding:8px 8px">
      <span style="width:18px;flex:none;color:var(--pal-gold);font-weight:800;font-size:12px">{{ s.n }}</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;justify-content:flex-end;min-width:0"><span style="font-size:12px;color:var(--pal-text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.a }}{% if s.a_owned %}<span style="color:var(--pal-good)">✓</span>{% endif %}</span>{% if s.a_icon %}<img src="{{ s.a_icon }}" style="width:28px;height:28px;object-fit:contain;flex:none">{% endif %}</div>
      <span style="color:var(--pal-sub);flex:none;font-size:11px">＋</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0">{% if s.b_icon %}<img src="{{ s.b_icon }}" style="width:28px;height:28px;object-fit:contain;flex:none">{% endif %}<span style="font-size:12px;color:var(--pal-text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.b }}{% if s.b_owned %}<span style="color:var(--pal-good)">✓</span>{% endif %}</span></div>
      <span style="color:var(--pal-gold);flex:none;font-weight:800">→</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0">{% if s.c_icon %}<img src="{{ s.c_icon }}" style="width:30px;height:30px;object-fit:contain;flex:none">{% endif %}<span style="font-size:12.5px;font-weight:700;color:{% if s.is_target %}var(--pal-gold){% else %}var(--pal-text){% endif %};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ s.c }}</span></div>
    </div>{% endfor %}
    <div style="margin-top:10px;text-align:center;font-size:11px;color:var(--pal-dim)">✓=你已拥有 · 按顺序配,每步产物用于下一步</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版可孵化列表。变量契约与 HATCH_TMPL 一致 ----
HATCH_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ title }}</div><div class="ig-sub"><span class="ig-pill">{{ subtitle }}</span></div></div></div>
  <div class="ig-panel">
    {% for r in rows %}<div class="ig-rankrow" style="gap:8px">
      <div style="flex:none;display:flex;align-items:center;gap:7px;width:44%;min-width:0">{% if r.icon %}<img src="{{ r.icon }}" style="width:40px;height:40px;object-fit:contain;flex:none">{% endif %}<span style="font-size:14.5px;font-weight:800;color:var(--pal-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}</span></div>
      <span style="flex:none;color:var(--pal-sub);font-size:12px">←</span>
      <div style="flex:1;display:flex;align-items:center;gap:4px;min-width:0;justify-content:flex-end">{% if r.a_icon %}<img src="{{ r.a_icon }}" style="width:26px;height:26px;object-fit:contain;flex:none">{% endif %}<span style="font-size:12px;color:var(--pal-sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.a }}</span><span style="color:var(--pal-gold);flex:none">＋</span>{% if r.b_icon %}<img src="{{ r.b_icon }}" style="width:26px;height:26px;object-fit:contain;flex:none">{% endif %}<span style="font-size:12px;color:var(--pal-sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.b }}</span></div>
    </div>{% endfor %}
    {% if pager %}<div style="margin-top:10px;text-align:center;font-size:12px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版词条继承概率。变量契约与 INHERIT_TMPL 一致 ----
INHERIT_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">词条继承概率</div><div class="ig-sub">两只亲代配种,孩子继承词条的概率(社区实测模型)</div></div></div>
  <div class="ig-panel">
    <div style="display:flex;gap:10px">
      <div style="flex:1;min-width:0"><div style="font-size:12.5px;font-weight:800;color:var(--pal-sub);margin-bottom:7px">父代词条</div><div style="display:flex;flex-wrap:wrap;gap:5px">{% if a_chips %}{% for c in a_chips %}<span class="ig-chip {{ c.color }}">{{ c.stars }} {{ c.name }}</span>{% endfor %}{% else %}<span style="color:var(--pal-dim);font-size:12px">(未填)</span>{% endif %}</div></div>
      <div style="flex:1;min-width:0"><div style="font-size:12.5px;font-weight:800;color:var(--pal-sub);margin-bottom:7px">母代词条</div><div style="display:flex;flex-wrap:wrap;gap:5px">{% if b_chips %}{% for c in b_chips %}<span class="ig-chip {{ c.color }}">{{ c.stars }} {{ c.name }}</span>{% endfor %}{% else %}<span style="color:var(--pal-dim);font-size:12px">(未填)</span>{% endif %}</div></div>
    </div>
    {% if feasible %}<div style="margin-top:14px;text-align:center;background:rgba(125,211,224,.08);border:1px solid rgba(125,211,224,.3);border-radius:3px;padding:15px 14px">
      <div style="font-size:13px;color:var(--pal-sub)">同时继承这 {{ n }} 个词条的概率</div>
      <div style="font-size:44px;font-weight:800;color:var(--pal-text);line-height:1.1;margin-top:2px">{{ p_all }}<span style="font-size:22px;color:var(--pal-sub)">%</span></div>
    </div>{% endif %}
    <div class="ig-sec" style="margin-top:16px">继承「父母词条」数量的概率</div>
    {% for d in dist %}<div style="display:flex;align-items:center;gap:10px;padding:5px 0"><span style="flex:none;width:80px;font-size:13px;color:var(--pal-text-2)">{{ d.j }} 个词条</span><div class="ig-inbar"><span style="width:{{ d.p }}%"></span></div><span style="flex:none;width:42px;text-align:right;font-size:13px;font-weight:800;color:var(--pal-gold)">{{ d.p }}%</span></div>{% endfor %}
    <div class="ig-sec" style="margin-top:16px">每个词条单独的继承率</div>
    {% for c in pool %}<div style="display:flex;align-items:center;gap:9px;padding:5px 0;border-bottom:1px solid var(--pal-line-soft)"><span class="ig-chip {{ c.color }}" style="flex:none">{{ c.stars }} {{ c.name }}</span>{% if c.effect %}<span style="flex:1;min-width:0;font-size:11.5px;color:var(--pal-sub);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ c.effect }}</span>{% else %}<span style="flex:1"></span>{% endif %}<span style="flex:none;font-size:14px;font-weight:800;color:var(--pal-good)">{{ c.p_single }}%</span></div>{% endfor %}
    {% if shared %}<div style="margin-top:12px;font-size:12px;color:var(--pal-gold)">双亲都带「{{ shared|join('、') }}」,词条池中只算一份。</div>{% endif %}
    {% if unknown %}<div style="margin-top:6px;font-size:12px;color:var(--pal-danger)">没认出：{{ unknown|join('、') }}(已忽略,请用游戏内全名)</div>{% endif %}
    <div style="margin-top:12px;font-size:11.5px;color:var(--pal-dim);line-height:1.65">模型:孩子从父母去重词条池里继承 1/2/3/4 个的概率为 40%/30%/20%/10%;空余格子还可能随机刷出新词条。实际为概率,多孵几窝更稳。<br>此 40/30/20/10 为<b>社区实测模型</b>,游戏未公开官方数值,仅供参考。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帕鲁对比。变量契约与 COMPARE_TMPL 一致 ----
COMPARE_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head" style="align-items:center">
    <div style="flex:1;text-align:center;min-width:0"><div class="ig-portrait" style="margin:0 auto;width:82px;height:82px;border-width:11px"><img src="{{ left.icon }}"></div><div style="font-size:16px;font-weight:800;color:var(--pal-text);margin-top:6px">{{ left.name }}</div><div style="font-size:11px;color:var(--pal-sub)">{{ left.elements }}</div></div>
    <div class="ig-vs">VS</div>
    <div style="flex:1;text-align:center;min-width:0"><div class="ig-portrait" style="margin:0 auto;width:82px;height:82px;border-width:11px"><img src="{{ right.icon }}"></div><div style="font-size:16px;font-weight:800;color:var(--pal-text);margin-top:6px">{{ right.name }}</div><div style="font-size:11px;color:var(--pal-sub)">{{ right.elements }}</div></div>
  </div>
  <div class="ig-panel">
    {% for s in stats %}<div class="ig-cmprow"><span class="cv {{ 'win' if s.lwin else ('lose' if s.rwin else 'eq') }}" style="text-align:right">{{ s.lval }}{% if s.lwin %} ▲{% endif %}</span><span class="cl">{{ s.label }}</span><span class="cv {{ 'win' if s.rwin else ('lose' if s.lwin else 'eq') }}" style="text-align:left">{% if s.rwin %}▲ {% endif %}{{ s.rval }}</span></div>{% endfor %}
    {% if works %}<div class="ig-sec" style="margin-top:13px">工作适性(左 ‹ › 右)</div>
    <div style="display:flex;flex-direction:column;gap:5px">{% for w in works %}<div style="display:flex;align-items:center;font-size:13px"><span style="flex:1;text-align:right;color:{{ 'var(--pal-good)' if w.l>w.r else 'var(--pal-dim)' }}">{{ w.l or '-' }}</span><span style="flex:none;width:96px;text-align:center;color:var(--pal-sub)">{{ w.label }}</span><span style="flex:1;text-align:left;color:{{ 'var(--pal-good)' if w.r>w.l else 'var(--pal-dim)' }}">{{ w.r or '-' }}</span></div>{% endfor %}</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版竞技场总览。变量契约与 ARENA_TMPL 一致 ----
ARENA_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁竞技场</div><div class="ig-sub">单人挑战 NPC 训练家 · 6 段位 · 赢「战斗券」兑换稀有装备</div></div></div>
  <div class="ig-panel"><div style="font-size:13px;color:var(--pal-sub);line-height:1.7;margin-bottom:12px">在岛上的竞技场入口报名,用自己的帕鲁队伍轮流挑战各段位的训练家。胜利获得 <b style="color:var(--pal-gold)">战斗券</b>,可在竞技场商店兑换设计图/帕鲁球等。发「/帕鲁竞技场 段位名」看对手阵容。</div>
    {% for t in tiers %}<div class="ig-prow"><span style="flex:1;min-width:0"><span style="font-size:15px;font-weight:800;color:var(--pal-text)">{{ t.tier }}</span> <span style="font-size:11px;color:var(--pal-sub)">推荐 Lv.{{ t.level }} · {{ t.count }} 位对手</span><span style="display:block;font-size:11.5px;color:var(--pal-sub);margin-top:2px">首通 {{ t.first }}</span></span></div>{% endfor %}
    <div style="margin-top:12px;text-align:center;font-size:12px;color:var(--pal-dim)">发「/帕鲁竞技场 {{ tiers[4].tier }}」看对手阵容 · 「/帕鲁商人 竞技场商店」看战斗券兑换</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版竞技场段位。变量契约与 ARENA_TIER_TMPL 一致 ----
ARENA_TIER_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">竞技场 · {{ tier }}</div><div class="ig-sub"><span class="ig-pill">推荐 Lv.{{ level }}</span><span class="ig-pill">{{ teams|length }} 位对手</span></div></div></div>
  <div class="ig-panel">
    <div style="display:flex;gap:9px;flex-wrap:wrap">
      <div style="flex:1;min-width:140px;background:rgba(240,207,122,.06);border:1px solid rgba(240,207,122,.28);border-radius:3px;padding:9px 11px"><div style="font-size:12px;color:var(--pal-gold);margin-bottom:3px">首通奖励</div><div style="font-size:12.5px;color:var(--pal-text-2);line-height:1.5">{% for r in first %}{{ r.name }}×{{ r.qty }}{% if not loop.last %} · {% endif %}{% endfor %}</div></div>
      <div style="flex:1;min-width:140px;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;padding:9px 11px"><div style="font-size:12px;color:var(--pal-sub);margin-bottom:3px">重复奖励</div><div style="font-size:12.5px;color:var(--pal-sub);line-height:1.5">{% for r in repeat %}{{ r.name }}×{{ r.qty }}{% if not loop.last %} · {% endif %}{% endfor %}</div></div>
    </div>
    <div class="ig-sec" style="margin-top:14px">对手阵容</div>
    {% for tm in teams %}<div style="padding:9px 2px;border-bottom:1px solid var(--pal-line-soft)"><div style="font-size:14px;font-weight:800;color:var(--pal-text);margin-bottom:5px">{{ tm.trainer }} <span style="font-size:12px;color:var(--pal-sub);font-weight:600">Lv.{{ tm.level }}</span></div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for p in tm.pals %}<span class="ig-work">{% if p.icon %}<img src="{{ p.icon }}">{% endif %}{{ p.name }}</span>{% endfor %}</div></div>{% endfor %}
    <div style="margin-top:12px;font-size:12px;color:var(--pal-dim);line-height:1.6">对手等级 Lv.{{ level }};带克制属性的帕鲁、配高威力主动技能更稳。胜利得「战斗券」→ /帕鲁商人 竞技场商店 兑换。</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版早晚报/周结算。变量契约与 DAILY_TMPL 一致 ----
DAILY_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ title }}</div><div class="ig-sub">{{ now }}</div></div></div>
  <div class="ig-panel">
    <div style="color:var(--pal-text-2);font-size:14px;line-height:1.6;margin-bottom:13px">{{ greeting }}</div>
    <div style="display:flex;align-items:center;gap:10px;padding:11px 14px;background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;font-size:14px;font-weight:700;color:var(--pal-text)">
      {% if online %}<span class="ig-badge-on" style="margin-left:0">在线</span>当前 {{ cur }}/{{ maxn }} 人 · FPS {{ fps }} · 世界第 {{ days }} 天{% else %}<span class="ig-badge-off" style="margin-left:0">离线</span>服务器当前连不上{% endif %}
    </div>
    <div class="ig-stiles" style="margin-top:13px">
      <div class="ig-stile"><div class="v">{{ today_peak }}</div><div class="k">今日峰值</div></div>
      <div class="ig-stile"><div class="v">{{ today_avg }}</div><div class="k">今日平均</div></div>
      {% if show_yday %}<div class="ig-stile"><div class="v">{{ yday_peak }}</div><div class="k">昨日峰值</div></div>{% else %}<div class="ig-stile"><div class="v">{{ record }}</div><div class="k">历史纪录</div></div>{% endif %}
    </div>
  </div>
  <div class="ig-panel hi">
    <div class="ig-sec">今日肝帝 TOP3</div>
    {% if today_top %}{% for p in today_top %}<div class="ig-prow"><span style="width:22px;flex:none;color:var(--pal-gold);font-weight:800;text-align:center">{{ loop.index }}</span><span class="pnm">{{ p.name }}</span><span style="color:var(--pal-gold);font-weight:800;font-size:14px">{{ p.dur }}</span></div>{% endfor %}{% else %}<div style="color:var(--pal-dim);font-size:13px;padding:4px 0">今天还没有人上线哦～</div>{% endif %}
    <div class="ig-sec" style="margin-top:15px">本周肝帝榜 TOP3</div>
    {% if week_top %}{% for p in week_top %}<div class="ig-prow"><span style="width:22px;flex:none;color:var(--pal-gold);font-weight:800;text-align:center">{{ loop.index }}</span><span class="pnm">{{ p.name }}</span><span style="color:var(--pal-gold);font-weight:800;font-size:14px">{{ p.dur }}</span></div>{% endfor %}{% else %}<div style="color:var(--pal-dim);font-size:13px;padding:4px 0">本周还没有在线记录～</div>{% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版帮助菜单(静态命令表)。无动态数据 ----
_IGN = '<span class="ig-new">NEW</span>'
HELP_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">帕鲁指令帮助</div><div class="ig-sub">指令一行一条,看清楚再发哦～</div></div></div>
  <div class="ig-panel">
    <div class="ig-sec">查询(所有人可用)</div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁</b></div><div class="d">查看服务器状态</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁状态</b></div><div class="d">同上,服务器状态总览</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁在线</b></div><div class="d">查看在线玩家列表</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁设置</b></div><div class="d">查看服务器倍率与规则</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁统计</b></div><div class="d">今日峰值/平均 + 近7日趋势</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁热力</b></div><div class="d">7×24 在线热力图·看高峰时段</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁战力榜</b></div><div class="d">已知帕鲁战力等级排行(翻页/详情)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁玩家战力榜</b></div><div class="d">玩家拥有/抓捕帕鲁战力排行</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁闪光墙</b></div><div class="d">全服闪光帕鲁收藏展示</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁头目墙</b></div><div class="d">全服头目(Alpha)收藏展示</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁图鉴榜</b></div><div class="d">全服图鉴收集进度排行</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁资产榜</b></div><div class="d">全服帕鲁身价排行</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁公会战力</b></div><div class="d">各公会战力总和排行</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁更新公告</b></div><div class="d">官方最新更新公告(中文)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁肝帝榜</b> <span style="opacity:.7">[今日/总榜]</span></div><div class="d">在线时长排行(默认本周,可加 今日/总榜)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁图鉴</b> [名/字]</div><div class="d">详情或模糊列表·空=全部·翻页</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁编号</b> 13B</div><div class="d">按图鉴编号查(支持变种)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁配种</b> 亲A 亲B</div><div class="d">查后代 + 子代继续配</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁反配种</b> 帕鲁名</div><div class="d">列出能配成它的组合</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁怎么配</b> 帕鲁名</div><div class="d">用你现有帕鲁算配种路线</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁继承</b> 词条A｜词条B</div><div class="d">算后代继承词条的概率</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁哪里掉</b> 物品</div><div class="d">查哪些帕鲁掉落该物品</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁物品</b> [名/类]</div><div class="d">详情/分类浏览/翻页</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁设施</b> [名/字]</div><div class="d">详情或模糊列表·空=全部·翻页</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁科技</b> [名/字]</div><div class="d">详情或模糊列表·空=全部·翻页</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁研究所</b> [类/名]</div><div class="d">""" + _IGN + """ 全局增益研究·9大适性·材料/前置</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁栖息区域</b> 帕鲁名</div><div class="d">地图上涂出它的刷新热区</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁推荐词条</b> 帕鲁名</div><div class="d">按角色推荐高价值词条</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁词条大全</b> [分类]</div><div class="d">全部词条分类查询详情</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁觉醒</b></div><div class="d">1.0 觉醒材料与机制</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁突变</b></div><div class="d">1.0 突变机制与特殊蛋糕</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁属性克制</b></div><div class="d">九系属性克制关系图</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁主线</b> [页]</div><div class="d">按剧情顺序列出主线任务</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁支线</b> [NPC]</div><div class="d">支线任务(可按 NPC 筛选)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁任务</b> 任务名</div><div class="d">任务详细攻略：目标/坐标/奖励</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁塔主</b> [名]</div><div class="d">高塔塔主：属性/等级/血量/攻略</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁突袭</b> [名]</div><div class="d">突袭 Boss 数据与打法提示</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁竞技场</b> [段位]</div><div class="d">竞技场对手阵容/段位奖励</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁商人</b> [名]</div><div class="d">各商店卖什么 + 价格/货币</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁哪里买</b> 物品</div><div class="d">某物品在哪个商店买、多少钱</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁技能</b> 名/属性</div><div class="d">主动技能威力/冷却/效果</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁技能果实</b> [属性/名]</div><div class="d">""" + _IGN + """ 92种果实图鉴·带图标·教什么技能</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁植入体</b> [名/页]</div><div class="d">""" + _IGN + """ 68种改造词条·编号查:/帕鲁植入体查询 N</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁世界树</b></div><div class="d">""" + _IGN + """ 1.0最终boss专题:暮尘蛾&夜蔓爵</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁1.0</b></div><div class="d">""" + _IGN + """ 1.0正式版支持总览·数据统计·新功能导览</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁钓鱼</b></div><div class="d">钓鱼能钓到什么 + 概率</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁工作</b> 工种</div><div class="d">某工种(采矿/搬运…)最强帕鲁排行</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁坐骑</b></div><div class="d">可骑乘帕鲁按奔跑速度排行</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁对比</b> A B</div><div class="d">两只帕鲁数值并排对比</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁料理</b> [效果]</div><div class="d">有增益的料理(攻击/工作速度/配种…)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁武器</b> [名]</div><div class="d">武器攻击力/解锁科技/弹药</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁帮助</b></div><div class="d">显示本帮助卡片</div></div>
  </div>
  <div class="ig-panel hi">
    <div class="ig-sec">玩家自助(所有人可用)</div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁绑定</b> 游戏名</div><div class="d">绑定你的帕鲁角色</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁我</b></div><div class="d">个人档案·等级/技术点/队伍/背包</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁背包</b></div><div class="d">查看自己的背包物品明细</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁队伍</b></div><div class="d">查看自己出战帕鲁的面板</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁箱</b> [页]</div><div class="d">帕鲁箱全部帕鲁·翻页</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁可孵化</b></div><div class="d">用你箱里的帕鲁能配出哪些新帕鲁</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁据点</b></div><div class="d">据点帕鲁：工作/适性/血量/SAN/伤病</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁症状</b> [状态]</div><div class="d">伤病治疗速查(骨折/濒死/低SAN…)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁公会帕鲁</b> [页]</div><div class="d">公会终端：全公会成员帕鲁汇总</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁箱查询</b> 编号</div><div class="d">看帕鲁箱某只的详细面板</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁公会</b></div><div class="d">查看自己公会的成员/会长</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁公会榜</b></div><div class="d">公会在线时长排行榜</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁订阅</b> 游戏名</div><div class="d">某玩家上线时 @ 你</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁退订</b> 游戏名</div><div class="d">取消上线提醒</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁找人</b> 游戏名</div><div class="d">查某玩家是否在线</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁喊话</b> 内容</div><div class="d">把话广播到游戏内</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁喊</b> 游戏名</div><div class="d">@绑定的玩家喊TA上线</div></div>
  </div>
  <div class="ig-panel">
    <div class="ig-sec">管理(仅管理员)</div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁公告</b> 内容</div><div class="d">向服务器广播公告</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁踢</b> ID [理由]</div><div class="d">踢出指定玩家</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁封</b> ID [理由]</div><div class="d">封禁玩家(需确认)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁解封</b> ID</div><div class="d">解除封禁</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁存档</b></div><div class="d">立即保存世界存档</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁关服</b> 秒 [提示]</div><div class="d">定时关服(需确认)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁重启服务器</b></div><div class="d">存档后重启服务器(需确认)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁备份列表</b></div><div class="d">查看所有自动备份存档</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁回档</b> 编号</div><div class="d">回档到指定备份(需确认)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁重置存档</b></div><div class="d">删档重开·全新世界(需确认)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁恢复存档</b></div><div class="d">还原上一次重置前的存档(需确认)</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁审计</b></div><div class="d">查看最近管理操作记录</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁自检</b></div><div class="d">一键体检配置/连接/存档/渲染</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁地图</b></div><div class="d">在线玩家世界地图分布</div></div>
    <div class="ig-cmd"><div class="c"><b>/帕鲁确认</b></div><div class="d">确认上一条危险操作</div></div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---- ingame 版据点帕鲁。变量契约与 BASECAMP_TMPL 一致 ----
BASECAMP_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">{{ name }} 的据点帕鲁{% if multi %} · {{ sel_label }}{% endif %}</div><div class="ig-sub">据点工作帕鲁状态{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 数据来自存档</div></div></div>
  {% if multi %}<div class="ig-panel"><div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center">
    {% for b in bases %}<span class="ig-pill{% if b.no==selected %} gold{% endif %}">据点{{ b.no }} · {{ b.count }}只</span>{% endfor %}
    <span style="font-size:11px;color:var(--pal-dim)">发 /帕鲁据点 &lt;号&gt; 切换</span></div></div>{% endif %}
  <div class="ig-panel">
    <div class="ig-stiles" style="margin-bottom:12px">
      <div class="ig-stile"><div class="v">{{ total }}</div><div class="k">工作帕鲁</div></div>
      <div class="ig-stile"><div class="v" style="{% if hurt %}color:var(--pal-danger){% endif %}">{{ hurt }}</div><div class="k">受伤</div></div>
      <div class="ig-stile"><div class="v" style="{% if hungry %}color:#e0a01a{% endif %}">{{ hungry }}</div><div class="k">饥饿</div></div>
    </div>
    {% if cells %}
    {% for c in cells %}
    <div class="ig-wk">
      <div class="wpic">{% if c.icon %}<img src="{{ c.icon }}">{% endif %}{% if c.lucky %}<img class="mk" src="{{ icons.pal.lucky }}">{% elif c.alpha %}<img class="mk" src="{{ icons.pal.alpha }}">{% endif %}</div>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><span style="font-size:15px;font-weight:800;color:var(--pal-text)">{{ c.name }}</span><span style="font-size:12px;color:var(--pal-gold);font-weight:700">Lv.{{ c.level }}</span>{% for e in c.elements %}<span class="ig-badge" style="font-size:10.5px;padding:1px 6px 1px 3px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px">{% endif %}{{ e }}</span>{% endfor %}{% if c.health.hurt %}<span class="ig-hpill" style="background:{% if c.health.tone=='bad' %}#d42c2c{% else %}#e07a1a{% endif %}">{{ c.health.label }}</span>{% endif %}{% if c.starving %}<span class="ig-hpill" style="background:#e0a01a;color:#0e1015">饥饿</span>{% endif %}{% if c.low_san %}<span class="ig-hpill" style="background:#c05bd0">理智低</span>{% endif %}</div>
        <div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:10px;font-size:12px;color:var(--pal-text-2)">
          <span>{% if c.working %}正在{{ c.current_work }}{% else %}{{ c.current_work }}{% endif %}</span>
          <span style="display:inline-flex;align-items:center;gap:3px;{% if c.max_hp and c.hp_pct < 40 %}color:var(--pal-danger){% endif %}">{% if icons.stat.hp %}<img src="{{ icons.stat.hp }}" style="width:13px;height:13px">{% endif %}{{ c.hp }}{% if c.max_hp %}/{{ c.max_hp }}{% endif %}</span>
          <span style="display:inline-flex;align-items:center;gap:3px;{% if c.starving %}color:#e0a01a{% endif %}">{% if icons.stat.hunger %}<img src="{{ icons.stat.hunger }}" style="width:13px;height:13px">{% endif %}{{ c.stomach }}%</span>
          <span style="{% if c.low_san %}color:var(--pal-danger){% endif %}">SAN {{ c.sanity }}</span>
        </div>
        <div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px">{% if c.works %}{% for w in c.works %}<span class="ig-wtag">{% if icons.work[w.k] %}<img src="{{ icons.work[w.k] }}" style="width:12px;height:12px;vertical-align:middle;margin-right:2px">{% endif %}{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}{% else %}<span style="font-size:11px;color:var(--pal-dim)">无基地工作适性</span>{% endif %}</div>
        {% if c.cure_tips %}<div class="ig-cure">{% for t in c.cure_tips %}<div style="{% if not loop.first %}margin-top:8px{% endif %}"><div class="cs">{{ t.symptom }}</div><div class="cd">{{ t.desc }}</div>{% if t.drugs %}<div>{% for it in t.drugs %}<span class="citem">{% if it.icon %}<img src="{{ it.icon }}">{% endif %}<span>{{ it.name }}</span></span>{% endfor %}</div>{% endif %}</div>{% endfor %}</div>{% endif %}
      </div>
    </div>
    {% endfor %}
    {% if hurt or hungry or low_san %}<div style="margin-top:10px;font-size:12px;color:var(--pal-sub);background:rgba(255,255,255,.03);border:1px solid var(--pal-line);border-radius:3px;padding:9px 12px">有帕鲁受伤/理智低？发 <b style="color:var(--pal-gold)">/帕鲁症状 &lt;状态&gt;</b>(如 /帕鲁症状 骨折)查治疗方法</div>{% endif %}
    {% if pager %}<div style="margin-top:10px;text-align:center;font-size:12.5px;color:var(--pal-dim)">{{ pager }}</div>{% endif %}
    {% else %}
    <div style="text-align:center;padding:22px 10px;line-height:1.8"><div style="font-size:15px;color:var(--pal-text-2)">据点里暂时没有部署帕鲁</div><div style="font-size:12.5px;color:var(--pal-dim);margin-top:6px">在游戏里把帕鲁从帕鲁箱放到据点工作后,这里就会显示它们的状态(属性/工作适性/受伤·饥饿)。</div></div>
    {% endif %}
  </div>
  """ + _IF + """
</div></body></html>"""


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
  <div class="head"><div><div class="title">⚙ 服务器设置</div><div class="subtitle">当前帕鲁世界规则与倍率{% if server_version %} · 服务端 {{ server_version }}{% endif %}</div></div></div>
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
    <div class="cmd"><div class="c"><b>/帕鲁战力榜</b></div><div class="d">已知帕鲁战力等级排行(翻页/详情)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁玩家战力榜</b></div><div class="d">玩家拥有/抓捕帕鲁战力排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁闪光墙</b></div><div class="d">全服闪光帕鲁收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁头目墙</b></div><div class="d">全服头目(Alpha)收藏展示</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁图鉴榜</b></div><div class="d">全服图鉴收集进度排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁资产榜</b></div><div class="d">全服帕鲁身价排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁公会战力</b></div><div class="d">各公会战力总和排行</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁更新公告</b></div><div class="d">官方最新更新公告(中文)</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁肝帝榜</b> <span style="opacity:.7">[今日/总榜]</span></div><div class="d">在线时长排行(默认本周,可加 今日/总榜)</div></div>
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
    <div class="cmd"><div class="c"><b>/帕鲁词条大全</b> [分类]</div><div class="d">全部词条分类查询</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁觉醒</b></div><div class="d">觉醒材料与机制</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁突变</b></div><div class="d">突变机制与特殊蛋糕</div></div>
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
    <div class="cmd"><div class="c"><b>/帕鲁植入体</b> [名/页]</div><div class="d">🆕 68种·编号查/帕鲁植入体查询 N</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁世界树</b></div><div class="d">🆕 1.0最终boss:暮尘蛾&夜蔓爵</div></div>
    <div class="cmd"><div class="c"><b>/帕鲁1.0</b></div><div class="d">🆕 1.0支持总览/新功能导览</div></div>
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
  <div class="head"><div><div class="title">🏕️ {{ name }} 的据点帕鲁{% if multi %} · {{ sel_label }}{% endif %}</div><div class="subtitle">据点工作帕鲁状态{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 数据来自存档</div></div></div>
  <div class="glass">""" + _GEMS + """
    {% if multi %}<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;align-items:center">
      {% for b in bases %}<span class="pill {% if b.no==selected %}gold{% else %}soft{% endif %}">据点{{ b.no }} · {{ b.count }}只</span>{% endfor %}
      <span style="font-size:11px;color:#9c8fc0">发 /帕鲁据点 &lt;号&gt; 切换</span>
    </div>{% endif %}
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
          {% for e in c.elements %}<span style="font-size:10.5px;color:#cfc1ea;background:rgba(99,102,241,.18);border-radius:5px;padding:0 6px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:11px;height:11px;object-fit:contain;vertical-align:-1px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}
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
          {% if c.works %}{% for w in c.works %}<span class="wtag">{% if icons.work[w.k] %}<img src="{{ icons.work[w.k] }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}{% else %}<span style="font-size:11px;color:#9c8fc0">无基地工作适性</span>{% endif %}
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
  <div class="head"><div><div class="title">☖ {{ name }} 的据点帕鲁{% if multi %} · {{ sel_label }}{% endif %}</div><div class="subtitle">据点工作帕鲁状态{% if pages and pages > 1 %} · 第 {{ page }}/{{ pages }} 页{% endif %} · 数据来自存档</div></div></div>
  <div class="frame">
    {% if multi %}<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:11px;align-items:center">
      {% for b in bases %}<span class="pill"{% if b.no==selected %} style="background:#6b4a24;color:#fff7e0"{% endif %}>据点{{ b.no }}·{{ b.count }}</span>{% endfor %}
      <span style="font-size:11px;color:#7a6a4a">/帕鲁据点 &lt;号&gt;</span>
    </div>{% endif %}
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
          {% for e in c.elements %}<span style="font-size:10.5px;color:#574012;background:rgba(156,107,26,.18);padding:0 5px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:11px;height:11px;object-fit:contain;vertical-align:-1px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}
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
          {% if c.works %}{% for w in c.works %}<span class="wtag">{% if icons.work[w.k] %}<img src="{{ icons.work[w.k] }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}{% else %}<span style="font-size:11px;color:#7a5a2a">无基地工作适性</span>{% endif %}
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
        {% if p.lucky %}<span class="pill soft">{% if icons.pal.lucky %}<img src="{{ icons.pal.lucky }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}✨ {% endif %}闪光</span>{% elif p.alpha %}<span class="pill soft">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}👑 {% endif %}头目</span>{% endif %}
        {% if p.health.hurt %}<span class="pill" style="background:linear-gradient(135deg,{% if p.health.tone=='bad' %}#ff6a6a,#d42c2c{% else %}#ffb24a,#e07a1a{% endif %});color:#fff;font-weight:800">⚠ {{ p.health.label }}{% if p.health.tone=='bad' %}·放终端可恢复{% endif %}</span>{% endif %}
      </div>
      <div class="ivr">
        <div class="ivb hpb"><div class="ivk">生命值</div><div class="ivv">{{ p.hp }}</div></div>
        <div class="ivb"><div class="ivk">攻击</div><div class="ivv">{{ p.cur_atk }}</div></div>
        <div class="ivb"><div class="ivk">防御</div><div class="ivv">{{ p.cur_def }}</div></div>
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
        {% if p.lucky %}<span class="pill">{% if icons.pal.lucky %}<img src="{{ icons.pal.lucky }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}✨{% endif %}闪光</span>{% elif p.alpha %}<span class="pill">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}♛{% endif %}头目</span>{% endif %}
        {% if p.health.hurt %}<span class="pill" style="background:{% if p.health.tone=='bad' %}#d42c2c{% else %}#e07a1a{% endif %};color:#fff">⚠{{ p.health.label }}{% if p.health.tone=='bad' %}·放终端可恢复{% endif %}</span>{% endif %}
      </div>
      <div class="ivr">
        <div class="ivb hpb"><div class="ivk">生命值</div><div class="ivv">{{ p.hp }}</div></div>
        <div class="ivb"><div class="ivk">攻击</div><div class="ivv">{{ p.cur_atk }}</div></div>
        <div class="ivb"><div class="ivk">防御</div><div class="ivv">{{ p.cur_def }}</div></div>
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
      <div class="subtitle">{% if is_tower_boss %}<span class="pill" style="background:#c0392b;color:#fff">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}🗼{% endif %}塔主</span>{% elif is_boss %}<span class="pill" style="background:#d68910;color:#fff">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}👑{% endif %}头目</span>{% endif %}<span class="pill">#{{ index }}</span>{% for e in elements %}<span class="pill">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}<span class="pill">{{ "★"*(rarity if rarity <= 5 else 5) if rarity else "★" }}</span>{% if nocturnal %}<span class="pill">夜行</span>{% endif %}</div>
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
    {% if traits %}<div class="sec-t">习性</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">{% for t in traits %}<span class="pill">{{ t.k }} · {{ t.v }}</span>{% endfor %}</div>{% endif %}
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
    {% if works %}<div class="sec-t" style="margin-top:15px">工作适性</div><div style="display:flex;flex-wrap:wrap;gap:7px">{% for w in works %}<span class="pill">{% if icons.work[w.k] %}<img src="{{ icons.work[w.k] }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ w.k }} Lv{{ w.lv }}</span>{% endfor %}</div>{% endif %}
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
        <div style="margin-top:7px;display:flex;gap:4px;justify-content:center;flex-wrap:wrap">{% for e in a.elements %}<span class="pill" style="font-size:10px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:11px;height:11px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}</div>
      </div>
      <div style="font-size:26px;color:#8f1212;flex-shrink:0">+</div>
      <div class="tile" style="flex:1;max-width:150px;text-align:center;padding:13px 8px">
        {% if b.icon %}<img src="{{ b.icon }}" style="width:48px;height:48px;object-fit:contain;display:block;margin:0 auto 5px;image-rendering:pixelated">{% endif %}
        <div style="font-size:17px;color:#46200a;word-break:break-word">{{ b.name }}</div>
        <div style="font-size:11px;color:#523f10;margin-top:3px">#{{ b.index }}</div>
        <div style="margin-top:7px;display:flex;gap:4px;justify-content:center;flex-wrap:wrap">{% for e in b.elements %}<span class="pill" style="font-size:10px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:11px;height:11px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}</div>
      </div>
    </div>
    <div style="text-align:center;font-size:14px;color:#7a3604;margin:2px 0">==== 后代 ====</div>
    <div style="text-align:center;padding:8px 0 4px">
      {% if c.icon %}<img src="{{ c.icon }}" style="width:64px;height:64px;object-fit:contain;display:block;margin:0 auto 4px;image-rendering:pixelated">{% endif %}
      <div class="num-big" style="font-size:28px">{{ c.name }}</div>
      <div style="font-size:12px;color:#523f10;margin-top:4px">图鉴 #{{ c.index }} · {{ "★"*(c.rarity if c.rarity <= 5 else 5) if c.rarity else "★" }}</div>
      <div style="display:flex;gap:5px;justify-content:center;margin-top:9px">{% for e in c.elements %}<span class="pill red" style="font-size:13px;padding:3px 12px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}</div>
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
        <span style="position:absolute;top:4px;right:6px;font-size:13px">{% if icons.pal[badge_kind] %}<img src="{{ icons.pal[badge_kind] }}" style="width:16px;height:16px;object-fit:contain">{% else %}{{ badge }}{% endif %}</span>
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
        <span style="position:absolute;top:3px;right:5px;font-size:12px">{% if icons.pal[badge_kind] %}<img src="{{ icons.pal[badge_kind] }}" style="width:15px;height:15px;object-fit:contain;image-rendering:pixelated">{% else %}{{ badge }}{% endif %}</span>
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
    <div class="title">{{ title | default('🏆 全服战力榜') }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" {% if r.rank <= 3 %}style="padding:9px 12px;gap:9px;align-items:center;background:linear-gradient(100deg,rgba(232,198,106,0.16),rgba(18,12,48,0.5) 60%);border-color:rgba(232,198,106,0.4)"{% else %}style="padding:9px 12px;gap:9px;align-items:center"{% endif %}>
      <div style="width:30px;flex-shrink:0;text-align:center;font-size:17px;font-weight:900;color:#e8c466">{{ r.medal }}</div>
      {% if r.icon %}<img src="{{ r.icon }}" style="width:42px;height:42px;object-fit:contain;flex-shrink:0">{% else %}<span style="font-size:24px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.lucky %} ✨{% elif r.alpha %} 👑{% endif %}</div>
        <div style="font-size:12px;color:#9c8fc0">Lv.{{ r.level }}{% if r.owner %} · 🧑{{ r.owner }}{% endif %}{% if r.element %} · {{ r.element }}{% endif %}</div>
      </div>
      <div style="flex-shrink:0;text-align:right;min-width:62px">
        <div style="font-size:16px;font-weight:800;color:#e8c466">{{ r.power }}</div>
        <div class="bar" style="margin-top:4px;width:56px"><div class="barf" style="width:{{ r.pct }}%"></div></div>
      </div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:10px;text-align:center;font-size:12px;color:#e8c466">{{ pager }}</div>{% endif %}
    <div style="margin-top:11px;text-align:center;font-size:11.5px;color:#9c8fc0">战力为综合评分(等级/种族/天赋/浓缩/被动),仅供横向对比</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# 帕鲁战力等级排行（全图鉴种族战力，/帕鲁战力榜，翻页）
PALPOWER_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">⚔️ 帕鲁战力榜</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for r in rows %}
    <div class="row" {% if r.rank <= 3 %}style="padding:9px 12px;gap:9px;align-items:center;background:linear-gradient(100deg,rgba(232,198,106,0.16),rgba(18,12,48,0.5) 60%);border-color:rgba(232,198,106,0.4)"{% else %}style="padding:9px 12px;gap:9px;align-items:center"{% endif %}>
      <div style="width:30px;flex-shrink:0;text-align:center;font-size:17px;font-weight:900;color:#e8c466">{{ r.medal }}</div>
      {% if r.icon %}<img src="{{ r.icon }}" style="width:42px;height:42px;object-fit:contain;flex-shrink:0">{% else %}<span style="font-size:24px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;font-weight:700;color:#f3ecd2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.boss=='tower' %} <span style="font-size:10.5px;background:#c0392b;color:#fff;padding:1px 6px;border-radius:5px;font-weight:800">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}🗼{% endif %}塔主</span>{% elif r.boss=='boss' %} <span style="font-size:10.5px;background:#d68910;color:#fff;padding:1px 6px;border-radius:5px;font-weight:800">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}👑{% endif %}头目</span>{% endif %}</div>
        <div style="font-size:12px;color:#9c8fc0">{{ r.element }} · 稀有度 {{ r.rarity }}</div>
      </div>
      <div style="flex-shrink:0;text-align:right;min-width:62px">
        <div style="font-size:16px;font-weight:800;color:#e8c466">{{ r.power }}</div>
        <div class="bar" style="margin-top:4px;width:56px"><div class="barf" style="width:{{ r.pct }}%"></div></div>
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:11px;text-align:center;font-size:11.5px;color:#9c8fc0">第 {{ page }}/{{ total_pages }} 页 · 发「/帕鲁战力榜 页码」翻页 · 「/帕鲁战力榜 帕鲁名」查详情</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# 单帕鲁战力详情（/帕鲁战力榜 帕鲁名）
PALPOWERDETAIL_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">⚔️ {{ name }} · 战力详情</div>
    <div class="subtitle">战力排名 #{{ rank }} / {{ total }} · Lv{{ reflv }} 满级属性</div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:16px">
      {% if icon %}<img src="{{ icon }}" style="width:76px;height:76px;object-fit:contain;flex-shrink:0">{% else %}<span style="font-size:40px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:22px;font-weight:800;color:#f3ecd2">{{ name }}</div>
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">{% for e in elements %}<span class="pill soft" style="font-size:12px">{{ e }}</span>{% endfor %}<span class="pill soft" style="font-size:12px">稀有度 {{ rarity }}</span></div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:34px;font-weight:900;color:#e8c466;line-height:1">{{ power }}</div>
        <div style="font-size:12px;color:#9c8fc0;margin-top:3px">种族战力</div>
      </div>
    </div>
    {% for s in stats %}
    <div style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;font-size:13px;color:#cfc1ea;margin-bottom:4px"><span>{{ s.k }}</span><span class="gold" style="font-weight:800">{{ s.v }}</span></div>
      <div class="bar"><div class="barf" style="width:{{ s.pct }}%"></div></div>
    </div>
    {% endfor %}
    {% if partner %}<div style="margin-top:14px;font-size:13px;color:#c2b2dd">🤝 伙伴技能：{{ partner }}</div>{% endif %}
    <div style="margin-top:13px;padding-top:10px;border-top:1px solid rgba(232,198,106,0.15);text-align:center;font-size:11.5px;color:#9c8fc0;line-height:1.7">种族值 生命{{ base.hp }} · 近战{{ base.melee }} · 远程{{ base.shot }} · 防御{{ base.df }}<br>战力 = Lv{{ reflv }}满级(HP×0.5 + 攻击 + 防御) · 游戏公式实测校准 · 发「/帕鲁战力榜」看总榜</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


POWER_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{{ title | default('🏆 全服战力榜') }}</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="frame">
    {% for r in rows %}
    <div class="row" style="padding:8px 11px;gap:8px;align-items:center">
      <div style="width:28px;flex-shrink:0;text-align:center;font-size:16px;color:#7a1f1f">{{ r.medal }}</div>
      {% if r.icon %}<img src="{{ r.icon }}" style="width:38px;height:38px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:22px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.lucky %} ✨{% elif r.alpha %} 👑{% endif %}</div>
        <div style="font-size:12px;color:#7a5a1a">Lv.{{ r.level }}{% if r.owner %} · {{ r.owner }}{% endif %}{% if r.element %} · {{ r.element }}{% endif %}</div>
      </div>
      <div style="flex-shrink:0;font-size:16px;color:#7a1f1f">{{ r.power }}</div>
    </div>
    {% endfor %}
    {% if pager %}<div style="margin-top:10px;text-align:center;font-size:12px;color:#7a3604">{{ pager }}</div>{% endif %}
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
      {% if price %}<span style="display:inline-flex;align-items:center;gap:5px;background:linear-gradient(135deg,rgba(232,198,106,.24),rgba(232,198,106,.07));border:1px solid rgba(232,198,106,.5);border-radius:11px;padding:5px 12px;font-size:14px;color:#f3e3b0">{% if icons.currency.gold %}<img src="{{ icons.currency.gold }}" style="width:15px;height:15px;object-fit:contain">{% else %}💰{% endif %} 商人价 <b style="color:#ffd86b">{{ price }}</b> 金币</span>{% endif %}
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
      {% if price %}<span style="background:rgba(156,107,26,.22);border:2px solid #6a4524;padding:4px 10px;font-size:13px;color:#46200a">{% if icons.currency.gold %}<img src="{{ icons.currency.gold }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-2px">{% else %}💰{% endif %} 商人价 {{ price }} 金币</span>{% endif %}
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
        {% if c.icon %}<img src="{{ c.icon }}" style="width:40px;height:40px;object-fit:contain;filter:drop-shadow(0 1px 3px rgba(0,0,0,.5))">{% else %}<div style="font-size:38px;line-height:1">{{ c.emoji }}</div>{% endif %}
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
    <div class="title">{% if icon %}<img src="{{ icon }}" style="width:24px;height:24px;object-fit:contain;vertical-align:-4px;margin-right:4px">{% else %}{{ emoji }} {% endif %}{{ category }}</div>
    <div class="subtitle"><span class="pill soft">{{ items|length }} 项研究</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:flex;flex-direction:column;gap:8px">
      {% for it in items %}
      <div style="display:flex;align-items:center;gap:10px;padding:10px 13px;border-radius:12px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.16)">
        <span style="flex:none;min-width:26px;height:26px;line-height:26px;text-align:center;font-size:13px;font-weight:800;color:#0d0820;background:linear-gradient(135deg,#f3d98a,#e8c66a);border-radius:8px">{{ loop.index }}</span>
        {% if it.essential %}<span style="flex:none;font-size:11px;font-weight:800;color:#0d0820;background:#7cfc9a;border-radius:6px;padding:2px 6px">必需</span>{% endif %}
        <div style="flex:1;min-width:0">
          <div style="font-size:15px;font-weight:700;color:#ece3f7">{{ it.name }}</div>
          {% if it.effect %}<div style="font-size:12.5px;color:#9effb6;margin-top:2px">{{ it.effect }}</div>{% endif %}
        </div>
      </div>{% endfor %}
    </div>
    <div style="margin-top:13px;font-size:13px;color:#9c8fc0">按编号查:发 <b style="color:#e8c466">/帕鲁研究所 {{ cat_short }}1</b>(该类第1项);或 <b style="color:#e8c466">/帕鲁研究所 &lt;研究名&gt;</b> 查详情。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

LAB_DETAIL_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:15px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:72px;height:72px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))">{% else %}<div style="flex:none;font-size:72px">{{ emoji }}</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        <span class="pill soft">{% if icon %}<img src="{{ icon }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% else %}{{ emoji }} {% endif %}{{ category }}</span>
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
        <span class="pill" style="background:{{ color }}33;border-color:{{ color }}88">{% if icons.element[element] %}<img src="{{ icons.element[element] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% else %}{{ emoji }} {% endif %}{{ element }}属性</span>
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
        {% if rank %}<span class="pill" style="background:rgba(232,198,106,.24)">稀有度 {{ "★" * (rank if rank <= 5 else 5) }}</span>{% endif %}
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


# ---------------- 世界树最终boss专题(1.0) ----------------
WORLDTREE_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🌳 世界树 Boss</div>
    <div class="subtitle"><span class="pill" style="background:rgba(124,252,154,.2);border-color:rgba(124,252,154,.45)">1.0 世界树</span><span class="pill soft">守护者 + 最终 Boss</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="font-size:13.5px;color:#cfc1ea;line-height:1.75;margin-bottom:6px">世界树深处的守护者(暮尘蛾 / 夜蔓爵，可捕获)镇守通往深渊之路；击败它们后，在最深处迎战最终剧情 Boss「枯星龙」(苏醒，剧情战不可捕获)。对应主线「通往深渊之路 → 苏醒」。</div>
    {% for b in bosses %}
    <div style="display:flex;gap:14px;padding:13px;margin-top:11px;border-radius:15px;background:rgba(12,8,38,.5);border:1px solid {% if b.is_final %}rgba(255,120,120,.4){% else %}rgba(200,140,255,.28){% endif %}">
      {% if b.icon %}<img src="{{ b.icon }}" style="width:88px;height:88px;flex:none;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))">{% else %}<div style="flex:none;font-size:60px">🌳</div>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:19px;font-weight:800;color:#e8c466">{{ b.name }} <span style="font-size:13px;color:#9c8fc0;font-weight:400">#{{ b.index }}</span> <span class="pill" style="font-size:11px;{% if b.is_final %}background:rgba(255,120,120,.22);border-color:rgba(255,120,120,.5);color:#ffb0b0{% else %}background:rgba(124,252,154,.16);border-color:rgba(124,252,154,.4);color:#9effb6{% endif %}">{{ b.role }}</span></div>
        <div style="margin:5px 0;display:flex;flex-wrap:wrap;gap:5px">{% for e in b.elements %}<span class="pill soft" style="font-size:12px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}<span class="pill soft" style="font-size:12px">稀有度 {{ b.rarity }}</span>{% if b.hp %}<span class="pill soft" style="font-size:12px">HP种族值 {{ b.hp }}</span>{% endif %}{% if b.story_only %}<span class="pill soft" style="font-size:12px;color:#ffb0b0">剧情战·不可捕获</span>{% endif %}</div>
        {% if b.partner %}<div style="font-size:12.5px;color:#bff7cc;margin-top:2px">🛡 伙伴技能：{{ b.partner }}</div>{% endif %}
        {% if b.skills %}<div style="font-size:12px;color:#cfc1ea;margin-top:4px;line-height:1.6"><b style="color:#9c8fc0">技能</b> {{ b.skills|join('、') }}</div>{% endif %}
        {% if b.drops %}<div style="font-size:12px;color:#e8c466;margin-top:3px"><b style="color:#9c8fc0">掉落</b> {{ b.drops|join('、') }}</div>{% endif %}
      </div>
    </div>{% endfor %}
    <div style="margin-top:13px;font-size:13px;color:#9c8fc0">发 <b style="color:#e8c466">/帕鲁图鉴 {{ bosses[0].name }}</b> 看完整属性/工作适性/伙伴技能详情;发 /帕鲁栖息地 红菇娘（或 燎火舞伶 / 磐甲龙）可查看世界树独立地图。</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# ---------------- 1.0 支持总览(1.0) ----------------
V10_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🎉 幻兽帕鲁 1.0 · 全面支持</div>
    <div class="subtitle"><span class="pill" style="background:rgba(124,252,154,.2);border-color:rgba(124,252,154,.45)">正式版数据已更新</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">数据收录 <span style="font-size:11px;font-weight:400;color:#9c8fc0">· 帕鲁 {{ stats['pals'] }} 只可收集（官方正式图鉴），含变体共 {{ stats['pals_total'] }} 个数据实体</span></div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:9px">
      {% set cells = [("帕鲁图鉴",stats['pals'],"🐾"),("物品",stats['items'],"🎒"),("主动技能",stats['skills'],"✨"),("科技",stats['tech'],"🔬"),("建筑设施",stats['buildings'],"🏛️"),("制作配方",stats['recipes'],"🛠️"),("研究所",stats['lab'],"🧪"),("技能果实",stats['fruits'],"🍐"),("植入体",stats['implants'],"🧬")] %}
      {% for label,num,emo in cells %}
      <div style="display:flex;flex-direction:column;align-items:center;padding:12px 5px;border-radius:13px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.16)">
        <div style="font-size:24px">{{ emo }}</div>
        <div style="font-size:23px;font-weight:800;color:#e8c466;line-height:1.1;margin-top:3px">{{ num }}</div>
        <div style="font-size:11.5px;color:#b9a9d6;margin-top:2px">{{ label }}</div>
      </div>{% endfor %}
    </div>
    <div class="sec-t" style="margin-top:16px">1.0 新增查询</div>
    <div style="display:flex;flex-direction:column;gap:7px">
      <div style="font-size:13.5px;color:#e9e0f5"><b style="color:#e8c466">/帕鲁研究所</b> — 全局增益研究,9大工作适性,按「手工1」编号查</div>
      <div style="font-size:13.5px;color:#e9e0f5"><b style="color:#e8c466">/帕鲁技能果实</b> — 92种果实按元素分类,按「火1」编号查</div>
      <div style="font-size:13.5px;color:#e9e0f5"><b style="color:#e8c466">/帕鲁植入体</b> — 68种改造词条,「/帕鲁植入体查询 N」按编号</div>
      <div style="font-size:13.5px;color:#e9e0f5"><b style="color:#e8c466">/帕鲁世界树</b> — 最终boss暮尘蛾&夜蔓爵专题</div>
    </div>
    <div style="margin-top:13px;font-size:12.5px;color:#9c8fc0">全部查询支持:名称 / 模糊(含关键字返列表) / 编号 / 分类浏览。</div>
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
        {% if c.boss %}<div style="position:absolute;top:3px;right:4px;font-size:13px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.85));z-index:2">{% if c.boss=='tower' %}🗼{% else %}👑{% endif %}</div>{% endif %}
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
        {% if c.boss %}<div style="position:absolute;top:2px;right:3px;font-size:12px;z-index:2">{% if c.boss=='tower' %}🗼{% else %}👑{% endif %}</div>{% endif %}
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
  {% for m in maps %}
  {% if maps|length > 1 %}<div style="margin:{% if not loop.first %}16px{% else %}2px{% endif %} 0 8px;font-size:15px;font-weight:800;color:#f3d98a">◈ {{ m.label }} <span style="font-size:12.5px;color:#9a93b8;font-weight:600">· {{ m.players|length }} 人</span></div>{% endif %}
  <div style="position:relative;width:100%;border-radius:16px;overflow:hidden;border:1px solid rgba(232,198,106,.3);box-shadow:0 4px 16px rgba(0,0,0,.45)">
    <img src="{{ m.mapimg }}" style="display:block;width:100%">
    {% for p in m.players %}
    <div style="position:absolute;left:{{ p.left }}%;top:{{ p.top }}%;transform:translate(-50%,-100%);width:16px;height:21px;z-index:5">
      <div style="position:absolute;top:0;left:0;width:16px;height:16px;border-radius:50%;background:radial-gradient(circle at 55% 40%,#ff9a9a,#d12f2f);border:1.5px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.65)"></div>
      <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:0;height:0;border-left:3.5px solid transparent;border-right:3.5px solid transparent;border-top:6px solid #d12f2f"></div>
      <div style="position:absolute;top:0;left:0;width:16px;height:16px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:9px;font-weight:800;text-shadow:0 1px 2px rgba(0,0,0,.5)">{{ p.no }}</div>
    </div>
    {% endfor %}
  </div>
  <div class="glass" style="margin-top:12px">""" + _GEMS + """
    {% for p in m.players %}
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
  {% endfor %}
  {% if offmap %}
  <div class="glass" style="margin-top:12px">
    <div style="font-size:13.5px;font-weight:800;color:#f3d98a;margin-bottom:4px">◈ 位置待确认 <span style="font-size:11.5px;color:#9a93b8;font-weight:600">· 不在已知地图范围</span></div>
    {% for p in offmap %}
    <div style="display:flex;align-items:center;gap:9px;padding:7px 2px;{% if not loop.last %}border-bottom:1px solid rgba(232,198,106,.12){% endif %}">
      <span style="flex:none;width:24px;height:24px;border-radius:50%;background:#3a3350;color:#c9bfe6;font-size:13px;font-weight:800;text-align:center;line-height:24px">{{ p.no }}</span>
      <span style="font-size:15px;font-weight:700;color:#f3ecd2">{{ p.name }}</span>
      <span class="pill soft">Lv.{{ p.level }}</span>
      <span style="margin-left:auto;font-size:11.5px;color:#9a93b8">坐标 {{ p.coord }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
  """ + _FOOT + """
</div></body></html>"""


MAP_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">▦ 在线玩家分布</div>
    <div class="subtitle">{{ subtitle }}</div>
  </div></div>
  {% for m in maps %}
  {% if maps|length > 1 %}<div style="margin:{% if not loop.first %}16px{% else %}2px{% endif %} 0 8px;font-size:15px;font-weight:700;color:#46200a">■ {{ m.label }} <span style="font-size:12.5px;color:#7a6a4a">· {{ m.players|length }} 人</span></div>{% endif %}
  <div style="position:relative;width:100%;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.4)">
    <img src="{{ m.mapimg }}" style="display:block;width:100%;image-rendering:auto">
    {% for p in m.players %}
    <div style="position:absolute;left:{{ p.left }}%;top:{{ p.top }}%;transform:translate(-50%,-100%);width:24px;height:29px;z-index:5">
      <div style="position:absolute;top:0;left:0;width:24px;height:21px;background:#d12f2f;border:2px solid #fff7e0"></div>
      <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:8px solid #d12f2f"></div>
      <div style="position:absolute;top:0;left:0;width:24px;height:21px;display:flex;align-items:center;justify-content:center;color:#fff7e0;font-size:12px;font-weight:700">{{ p.no }}</div>
    </div>
    {% endfor %}
  </div>
  <div class="frame" style="margin-top:12px">
    {% for p in m.players %}
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
  {% endfor %}
  {% if offmap %}
  <div class="frame" style="margin-top:12px">
    <div style="font-size:13.5px;font-weight:700;color:#46200a;margin-bottom:4px">■ 位置待确认 <span style="font-size:11.5px;color:#7a6a4a">· 不在已知地图范围</span></div>
    {% for p in offmap %}
    <div style="display:flex;align-items:center;gap:9px;padding:6px 2px;{% if not loop.last %}border-bottom:2px solid rgba(107,74,36,.3){% endif %}">
      <span style="flex:none;width:24px;height:24px;background:#8a7a5a;color:#fff7e0;font-size:13px;font-weight:700;text-align:center;line-height:24px">{{ p.no }}</span>
      <span style="font-size:15px;font-weight:700;color:#2c1a0a">{{ p.name }}</span>
      <span class="pill">Lv.{{ p.level }}</span>
      <span style="margin-left:auto;font-size:11.5px;color:#7a6a4a">坐标 {{ p.coord }}</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
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
          {% if icons.element[e.cn] %}<img src="{{ icons.element[e.cn] }}" style="width:24px;height:24px;object-fit:contain;filter:drop-shadow(0 1px 2px rgba(0,0,0,.5))">{% else %}<span style="font-size:24px">{{ e.emoji }}</span>{% endif %}
          <span style="font-size:18px;font-weight:800;color:{{ e.color }}">{{ e.cn }}属性</span>
        </div>
        <div class="erow">
          <span style="color:#7CFC9A;font-weight:700;min-width:38px">克制</span>
          {% if e.strong %}{% for s in e.strong %}<span class="etag" style="background:#7CFC9A22;color:#9effb6">{% if icons.element[s.cn] %}<img src="{{ icons.element[s.cn] }}" style="width:15px;height:15px;object-fit:contain">{% else %}{{ s.emoji }}{% endif %} {{ s.cn }}</span>{% endfor %}{% else %}<span style="color:#9a93b8">无</span>{% endif %}
        </div>
        <div class="erow">
          <span style="color:#ff8a8a;font-weight:700;min-width:38px">被克</span>
          {% if e.weak %}{% for w in e.weak %}<span class="etag" style="background:#ff6b6b22;color:#ffb0b0">{% if icons.element[w.cn] %}<img src="{{ icons.element[w.cn] }}" style="width:15px;height:15px;object-fit:contain">{% else %}{{ w.emoji }}{% endif %} {{ w.cn }}</span>{% endfor %}{% else %}<span style="color:#9a93b8">无</span>{% endif %}
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
          {% if icons.element[e.cn] %}<img src="{{ icons.element[e.cn] }}" style="width:22px;height:22px;object-fit:contain;image-rendering:pixelated">{% else %}<span style="font-size:22px">{{ e.emoji }}</span>{% endif %}
          <span style="font-size:17px;color:#46200a">{{ e.cn }}属性</span>
        </div>
        <div class="erow"><span style="color:#1d7a36;min-width:34px">克制</span>{% if e.strong %}{% for s in e.strong %}<span class="etag" style="background:#bdf0c8">{% if icons.element[s.cn] %}<img src="{{ icons.element[s.cn] }}" style="width:14px;height:14px;object-fit:contain;image-rendering:pixelated;vertical-align:-2px">{% else %}{{ s.emoji }}{% endif %}{{ s.cn }}</span>{% endfor %}{% else %}<span style="color:#7a6a4a">无</span>{% endif %}</div>
        <div class="erow"><span style="color:#8f1212;min-width:34px">被克</span>{% if e.weak %}{% for w in e.weak %}<span class="etag" style="background:#f3c4c4">{% if icons.element[w.cn] %}<img src="{{ icons.element[w.cn] }}" style="width:14px;height:14px;object-fit:contain;image-rendering:pixelated;vertical-align:-2px">{% else %}{{ w.emoji }}{% endif %}{{ w.cn }}</span>{% endfor %}{% else %}<span style="color:#7a6a4a">无</span>{% endif %}</div>
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
      <div class="subtitle"><span class="pill soft">No.{{ index }}</span>{% for e in elements %}<span class="pill soft">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}{% if nocturnal %}<span class="pill soft">🌙 夜行</span>{% endif %}{% if map_label %}<span class="pill" style="background:rgba(92,201,122,.25);border-color:rgba(92,201,122,.5);color:#8fe0a8">🗺️ {{ map_label }}</span>{% endif %}</div>
    </div>
  </div></div>
  <div style="position:relative;width:100%;border-radius:16px;overflow:hidden;border:1px solid {{color}}66;box-shadow:0 4px 16px rgba(0,0,0,.45)">
    <img src="{{ mapimg }}" style="display:block;width:100%">
    <div style="position:absolute;inset:0;mix-blend-mode:screen">
      {% for pt in points %}<div style="position:absolute;left:{{pt.l}}%;top:{{pt.t}}%;width:26px;height:26px;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,{{color}}d0,{{color}}00 62%)"></div>{% endfor %}
    </div>
    {% for pt in boss_points %}<div style="position:absolute;left:{{pt.l}}%;top:{{pt.t}}%;transform:translate(-50%,-100%);z-index:6;font-size:20px;filter:drop-shadow(0 1px 3px rgba(0,0,0,.95))">{% if boss_is_tower %}🗼{% else %}👑{% endif %}</div>{% endfor %}
  </div>
  <div class="glass" style="margin-top:12px">""" + _GEMS + """
    <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:13.5px;color:#e9e0f5">
      <span style="display:inline-flex;align-items:center;gap:5px"><span style="width:13px;height:13px;border-radius:50%;background:{{color}};display:inline-block;box-shadow:0 0 7px {{color}}"></span>栖息热区</span>
      {% if boss_points %}<span class="pill" style="background:#c0392b;color:#fff">{{ boss_label }} {{ boss_lv }} · {{ boss_points|length }}处</span>{% endif %}
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
      <div class="subtitle"><span class="pill">No.{{ index }}</span>{% for e in elements %}<span class="pill">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}{% if nocturnal %}<span class="pill">夜行</span>{% endif %}</div>
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
      <div class="subtitle"><span class="pill soft">No.{{ index }}</span>{% for e in elements %}<span class="pill soft">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}{% for r in roles %}<span class="pill soft">{{ r }}型</span>{% endfor %}</div>
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


# 词条大全·分类总览（/帕鲁词条大全）
PASSDEX_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    <div style="flex:none;width:66px;height:66px;border-radius:17px;background:radial-gradient(circle at 50% 38%,rgba(232,198,106,.4),rgba(18,12,48,.5) 72%);border:2px solid rgba(232,198,106,.6);display:flex;align-items:center;justify-content:center;font-size:34px">📜</div>
    <div style="flex:1;min-width:0">
      <div class="title">词条大全</div>
      <div class="subtitle">帕鲁被动词条百科 · 共 <b style="color:#e8c466">{{ total }}</b> 个 · 9 大类别</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
    {% for c in cats %}
      <div style="position:relative;padding:13px 14px 12px 19px;border-radius:15px;background:linear-gradient(135deg,{{c.color}}26,rgba(18,12,48,.5) 78%);border:1px solid {{c.color}}55;overflow:hidden">
        <div style="position:absolute;left:0;top:0;bottom:0;width:5px;background:{{c.color}}"></div>
        <div style="display:flex;align-items:center;gap:10px">
          <div style="flex:none;width:40px;height:40px;border-radius:11px;background:{{c.color}}30;border:1px solid {{c.color}}66;display:flex;align-items:center;justify-content:center;font-size:21px">{{c.icon}}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:16px;font-weight:800;color:#f3ecd2">{{c.name}}</div>
            <div style="font-size:11px;color:{{c.color}};font-weight:800">{{c.count}} 个词条</div>
          </div>
        </div>
        <div style="margin-top:8px;font-size:11px;color:#b9a9d6;line-height:1.5;height:2.2em;overflow:hidden">{{c.sample}}…</div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:13px;padding:10px 14px;border-radius:12px;background:rgba(99,102,241,.13);border:1px solid rgba(232,198,106,.2);text-align:center;font-size:12px;color:#d8cdf0;line-height:1.7">🔍 发「<b>/帕鲁词条大全 攻击</b>」看该类全部词条 · 「<b>/帕鲁词条大全 力量</b>」查具体效果</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# 词条大全·分类列表/搜索结果（/帕鲁词条大全 <分类/词条名>）
PASSLIST_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    <div style="flex:none;width:64px;height:64px;border-radius:16px;background:radial-gradient(circle at 50% 40%,{{color}}55,rgba(18,12,48,.5) 72%);border:2px solid {{color}}aa;display:flex;align-items:center;justify-content:center;font-size:32px">{{ icon }}</div>
    <div style="flex:1;min-width:0">
      <div class="title">{{ cat }}</div>
      <div class="subtitle"><span class="pill soft">{{ count }} 个词条</span></div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for it in items %}
    <div style="display:flex;align-items:center;gap:11px;padding:10px 12px;margin-bottom:7px;border-radius:12px;background:rgba(12,8,38,.45);border:1px solid rgba(232,198,106,.12);border-left:3px solid {% if it.sign>0 %}#5cc97a{% elif it.sign<0 %}#e15b5b{% else %}#9c8fc0{% endif %}">
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">
          <span style="font-size:14.5px;font-weight:800;color:#f3ecd2">{{ it.name }}</span>
          {% if it.rank %}<span style="font-size:10px;background:{{color}}33;color:{{color}};border:1px solid {{color}}66;padding:1px 6px;border-radius:5px;font-weight:800">Lv{{ it.rank }}</span>{% endif %}
          {% if it.cat %}<span class="pill soft" style="font-size:10px">{{ it.cat }}</span>{% endif %}
        </div>
        {% if it.effect %}<div style="font-size:12.5px;color:#cbbde8;margin-top:3px;line-height:1.45">{{ it.effect }}</div>{% endif %}
      </div>
      <span style="flex:none;font-size:14px">{% if it.sign>0 %}🟢{% elif it.sign<0 %}🔴{% else %}⚪{% endif %}</span>
    </div>
    {% endfor %}
    <div style="margin-top:5px;text-align:center;font-size:11.5px;color:#9c8fc0">🟢增益 · 🔴减益 · ⚪中性 — 发「/帕鲁词条大全」看全部分类</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

PASSREC_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    {% if icon %}<div style="flex:none;width:80px;height:80px;background:{{color}}33;border:3px solid #6b4a24;box-shadow:inset 0 0 0 2px rgba(255,247,224,.5);display:flex;align-items:center;justify-content:center"><img src="{{ icon }}" style="width:66px;height:66px;object-fit:contain;image-rendering:pixelated"></div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">▣ {{ name }} · 推荐词条</div>
      <div class="subtitle"><span class="pill">No.{{ index }}</span>{% for e in elements %}<span class="pill">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}{% for r in roles %}<span class="pill">{{ r }}型</span>{% endfor %}</div>
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
      <div class="subtitle"><span class="pill soft" style="color:{{tcolor}}">{{ tlabel }}</span>{% if order %}<span class="pill soft">主线 第 {{ order }}/{{ order_total or 55 }}</span>{% endif %}{% if group %}<span class="pill soft">{{ group }}</span>{% endif %}</div>
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
      <div class="subtitle"><span class="pill">{{ tlabel }}</span>{% if order %}<span class="pill">主线 {{ order }}/{{ order_total or 55 }}</span>{% endif %}{% if group %}<span class="pill">{{ group }}</span>{% endif %}</div>
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
      <div class="subtitle"><span class="pill soft" style="color:{{color}}">{{ catlabel }}</span>{% for e in elements %}<span class="pill soft">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}{% if difficulty %}<span class="pill soft">{{ difficulty }}</span>{% endif %}</div>
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
      <div class="subtitle"><span class="pill">{{ catlabel }}</span>{% for e in elements %}<span class="pill">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ e }}</span>{% endfor %}{% if difficulty %}<span class="pill">{{ difficulty }}</span>{% endif %}</div>
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
    <div style="margin-top:12px;font-size:11.5px;color:#9c8fc0;line-height:1.65">📌 模型：孩子从父母「去重词条池」里继承 1/2/3/4 个的概率为 40%/30%/20%/10%；空余格子还可能随机刷出新词条。实际为概率，单次孵化结果随机，多孵几窝更稳。<br>此 40/30/20/10 为<b style="color:#e8c466">社区实测模型</b>，游戏未公开官方数值，仅供参考。</div>
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
    <div style="margin-top:11px;font-size:11.5px;color:#7a5a2a;line-height:1.65">模型：孩子从父母「去重词条池」继承 1/2/3/4 个的概率为 40%/30%/20%/10%；空格还可能随机刷新词条。结果随机，多孵几窝更稳。<br>此 40/30/20/10 为<b>社区实测模型</b>，游戏未公开官方数值，仅供参考。</div>
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


# 觉醒系统（/帕鲁觉醒）
AWAKENING_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    <div style="flex:none;width:64px;height:64px;border-radius:16px;background:radial-gradient(circle at 50% 40%,rgba(232,198,106,.4),rgba(18,12,48,.5) 72%);border:2px solid rgba(232,198,106,.6);display:flex;align-items:center;justify-content:center;font-size:32px">🌟</div>
    <div style="flex:1;min-width:0"><div class="title">帕鲁觉醒</div>
      <div class="subtitle">1.0 觉醒系统 · 世界树能量解放隐藏能力</div></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">九系觉醒晶石</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px">
    {% for g in gems %}
      <div style="padding:10px 6px;border-radius:12px;background:linear-gradient(135deg,{{g.color}}22,rgba(18,12,48,.5) 78%);border:1px solid {{g.color}}55;text-align:center">
        {% if g.gem_icon %}<img src="{{g.gem_icon}}" style="width:40px;height:40px;object-fit:contain">{% else %}<div style="font-size:26px">💎</div>{% endif %}
        <div style="font-size:12.5px;font-weight:800;color:{{g.color}};margin-top:3px">{{g.elem}}系</div>
        <div style="font-size:10px;color:#b9a9d6;margin-top:1px">{{g.mat}}→晶石</div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:13px;padding:11px 14px;border-radius:12px;background:rgba(12,8,38,.5);border:1px solid rgba(232,198,106,.18);font-size:12.5px;color:#cbbde8;line-height:1.75">
      💡 <b style="color:#e8c466">觉醒机制</b>：击败世界树 Boss 后解锁。用对应属性的<b>辉石</b>加工成<b>觉醒晶石</b>，让该属性帕鲁「觉醒」、解放隐藏能力。<br>
      ⚠️ 具体觉醒提升数值与所需晶石数量，游戏文件未以数据表明确提供，以游戏内为准；<b>暂不支持读取玩家存档中的觉醒状态</b>。
    </div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# 突变系统（/帕鲁突变）
MUTATION_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    <div style="flex:none;width:64px;height:64px;border-radius:16px;background:radial-gradient(circle at 50% 40%,rgba(180,110,224,.45),rgba(18,12,48,.5) 72%);border:2px solid rgba(180,110,224,.7);display:flex;align-items:center;justify-content:center;font-size:32px">🧬</div>
    <div style="flex:1;min-width:0"><div class="title">帕鲁突变</div>
      <div class="subtitle">1.0 突变机制 · 特殊蛋糕影响配种结果</div></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">特殊蛋糕（放入繁殖牧场影响后代）</div>
    <div style="display:flex;flex-direction:column;gap:8px">
    {% for c in cakes %}
      <div style="display:flex;align-items:center;gap:11px;padding:9px 11px;border-radius:12px;background:rgba(12,8,38,.45);border:1px solid rgba(232,198,106,.13)">
        {% if c.icon %}<img src="{{c.icon}}" style="width:40px;height:40px;object-fit:contain;flex-shrink:0">{% else %}<span style="font-size:26px">🍰</span>{% endif %}
        <div style="flex:1;min-width:0"><div style="font-size:14px;font-weight:800;color:#e8c466">{{c.name}}</div>
          <div style="font-size:12px;color:#c2b2dd;margin-top:2px;line-height:1.45">{{c.effect}}</div></div>
      </div>
    {% endfor %}
    </div>
    {% if eggs %}<div class="sec-t" style="margin-top:14px">突变帕鲁蛋</div>
    <div style="display:flex;gap:9px;flex-wrap:wrap">
    {% for e in eggs %}<span class="pill soft" style="font-size:12px">{% if e.icon %}<img src="{{e.icon}}" style="width:18px;height:18px;vertical-align:middle;margin-right:3px">{% endif %}{{e.name}}</span>{% endfor %}
    </div>{% endif %}
    <div style="margin-top:13px;padding:11px 14px;border-radius:12px;background:rgba(12,8,38,.5);border:1px solid rgba(180,110,224,.2);font-size:12.5px;color:#cbbde8;line-height:1.75">
      💡 <b style="color:#b06ee0">突变机制</b>：<b>豪华蔬菜蛋糕</b>提升后代突变概率；突变帕鲁外观/属性与普通不同，可能带专属词条。<b>蘑菇蛋糕</b>提升天赋、<b>蔬菜蛋糕</b>一次产 2 蛋、<b>特制蛋糕</b>提升被动继承。<br>
      ⚠️ 突变<b>准确概率游戏未公开</b>，此处仅说明机制、不猜测数值。
    </div>
  </div>
  """ + _FOOT + """
</div></body></html>"""


# ====================================================================
# pixel 补齐:此前仅 fantasy 有、pixel 缺失的 13 键(palpower/palpowerdetail/
# lab_*/passdex/passlist/awakening/mutation/skillfruit/implant/worldtree/v10)。
# 补齐后三套主题模板键集合一致(见 test_theme_keys)。变量契约与 fantasy 完全一致。
# ====================================================================
PALPOWER_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">⚔️ 帕鲁战力榜</div>
    <div class="subtitle">{{ sub }}</div>
  </div></div>
  <div class="frame">
    {% for r in rows %}
    <div class="row" style="padding:8px 11px;gap:8px;align-items:center">
      <div style="width:28px;flex-shrink:0;text-align:center;font-size:16px;color:#7a1f1f">{{ r.medal }}</div>
      {% if r.icon %}<img src="{{ r.icon }}" style="width:38px;height:38px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:22px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;color:#382207;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{{ r.name }}{% if r.boss=='tower' %} <span class="pill red" style="font-size:10.5px">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}🗼{% endif %}塔主</span>{% elif r.boss=='boss' %} <span class="pill" style="font-size:10.5px">{% if icons.pal.alpha %}<img src="{{ icons.pal.alpha }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% else %}👑{% endif %}头目</span>{% endif %}</div>
        <div style="font-size:12px;color:#7a5a1a">{{ r.element }} · 稀有度 {{ r.rarity }}</div>
      </div>
      <div style="flex-shrink:0;text-align:right;min-width:58px">
        <div style="font-size:16px;color:#7a1f1f">{{ r.power }}</div>
        <div class="bar" style="margin-top:4px;width:52px"><div class="barf" style="width:{{ r.pct }}%"></div></div>
      </div>
    </div>
    {% endfor %}
    <div style="margin-top:11px;text-align:center;font-size:11.5px;color:#7a5a1a">第 {{ page }}/{{ total_pages }} 页 · 发「/帕鲁战力榜 页码」翻页 · 「/帕鲁战力榜 帕鲁名」查详情</div>
  </div>
  """ + _PF + """
</div></body></html>"""

PALPOWERDETAIL_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">⚔️ {{ name }} · 战力详情</div>
    <div class="subtitle">战力排名 #{{ rank }} / {{ total }} · Lv{{ reflv }} 满级属性</div>
  </div></div>
  <div class="frame">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
      {% if icon %}<img src="{{ icon }}" style="width:70px;height:70px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:38px">🐾</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:20px;color:#46200a">{{ name }}</div>
        <div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">{% for e in elements %}<span class="pill" style="font-size:12px">{{ e }}</span>{% endfor %}<span class="pill" style="font-size:12px">稀有度 {{ rarity }}</span></div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div class="num-big" style="font-size:32px">{{ power }}</div>
        <div style="font-size:12px;color:#7a5a1a;margin-top:3px">种族战力</div>
      </div>
    </div>
    {% for s in stats %}
    <div style="margin-bottom:10px">
      <div style="display:flex;justify-content:space-between;font-size:13px;color:#574012;margin-bottom:4px"><span>{{ s.k }}</span><span class="gold">{{ s.v }}</span></div>
      <div class="bar"><div class="barf" style="width:{{ s.pct }}%"></div></div>
    </div>
    {% endfor %}
    {% if partner %}<div style="margin-top:14px;font-size:13px;color:#574012">🤝 伙伴技能：{{ partner }}</div>{% endif %}
    <div style="margin-top:13px;padding-top:10px;border-top:2px solid rgba(90,58,30,0.35);text-align:center;font-size:11.5px;color:#7a5a1a;line-height:1.7">种族值 生命{{ base.hp }} · 近战{{ base.melee }} · 远程{{ base.shot }} · 防御{{ base.df }}<br>战力 = Lv{{ reflv }}满级(HP×0.5 + 攻击 + 防御) · 发「/帕鲁战力榜」看总榜</div>
  </div>
  """ + _PF + """
</div></body></html>"""

LAB_OVERVIEW_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🔬 帕鲁研究所</div>
    <div class="subtitle"><span class="pill">共 {{ total }} 项研究</span><span class="pill">9 大工作适性</span></div>
  </div></div>
  <div class="frame">
    <div style="font-size:14px;color:#523f10;line-height:1.75;margin-bottom:14px">在据点建造「研究所」后，投入材料与帕鲁工时研究各类工作适性的<b class="ink">全局增益</b>(工作速度 / 据点战力 / 孵化 / 远征 等)，效果对全服帕鲁生效。</div>
    <div class="m3">
      {% for c in cats %}
      <div class="tile" style="display:flex;flex-direction:column;align-items:center;padding:13px 6px 10px">
        {% if c.icon %}<img src="{{ c.icon }}" style="width:36px;height:36px;object-fit:contain;image-rendering:pixelated">{% else %}<div style="font-size:34px;line-height:1">{{ c.emoji }}</div>{% endif %}
        <div style="margin-top:7px;font-size:15px;color:#46200a">{{ c.name }}</div>
        <div style="margin-top:4px;font-size:12px;color:#7a5a1a">{{ c.count }} 项 · <span class="ink">{{ c.essential }} 必需</span></div>
      </div>{% endfor %}
    </div>
    <div style="margin-top:15px;font-size:13px;color:#7a5a1a;line-height:1.7">发 <b class="gold">/帕鲁研究所 手工</b> 看某类全部研究；发 <b class="gold">/帕鲁研究所 &lt;研究名&gt;</b> 看单项材料/前置。</div>
  </div>
  """ + _PF + """
</div></body></html>"""

LAB_LIST_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">{% if icon %}<img src="{{ icon }}" style="width:24px;height:24px;object-fit:contain;vertical-align:-4px;margin-right:4px">{% else %}{{ emoji }} {% endif %}{{ category }}</div>
    <div class="subtitle"><span class="pill">{{ items|length }} 项研究</span></div>
  </div></div>
  <div class="frame">
    {% for it in items %}
    <div class="row" style="gap:10px">
      <span style="flex:none;min-width:24px;text-align:center;font-size:13px;color:#3a2410;background:#caa860;border:2px solid #6a4524">{{ loop.index }}</span>
      {% if it.essential %}<span class="pill" style="font-size:11px;background:#7c8a46;color:#fff3d0">必需</span>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:15px;color:#382207">{{ it.name }}</div>
        {% if it.effect %}<div style="font-size:12.5px;color:#5a6a26;margin-top:2px">{{ it.effect }}</div>{% endif %}
      </div>
    </div>{% endfor %}
    <div style="margin-top:13px;font-size:13px;color:#7a5a1a">按编号查:发 <b class="gold">/帕鲁研究所 {{ cat_short }}1</b>(该类第1项);或 <b class="gold">/帕鲁研究所 &lt;研究名&gt;</b> 查详情。</div>
  </div>
  """ + _PF + """
</div></body></html>"""

LAB_DETAIL_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:14px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:60px;height:60px;object-fit:contain;image-rendering:pixelated">{% else %}<div style="flex:none;font-size:60px">{{ emoji }}</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        <span class="pill">{% if icon %}<img src="{{ icon }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px;image-rendering:pixelated">{% else %}{{ emoji }} {% endif %}{{ category }}</span>
        {% if essential %}<span class="pill" style="background:#7c8a46;color:#fff3d0">✔ 必需研究</span>{% endif %}
        {% if work %}<span class="pill">⏳ {{ work }} 工时</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="frame">
    {% if effect %}<div class="sec-t">研究效果</div>
    <div style="font-size:15px;color:#5a6a26;background:rgba(124,138,70,0.14);border:2px solid #7c8a46;padding:11px 14px">{{ effect }}</div>{% endif %}
    {% if materials %}<div class="sec-t" style="margin-top:15px">所需材料</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px">
      {% for m in materials %}<span class="pill">{{ m.name }} <b class="gold">×{{ m.count }}</b></span>{% endfor %}
    </div>{% endif %}
    {% if prereq %}<div class="sec-t" style="margin-top:15px">前置研究</div>
    <div style="font-size:14px;color:#523f10;background:rgba(90,58,30,0.12);border:2px solid #6a4524;padding:10px 14px">🔗 需先完成「{{ prereq }}」</div>{% endif %}
  </div>
  """ + _PF + """
</div></body></html>"""

SKILLFRUIT_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:14px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:84px;height:84px;object-fit:contain;image-rendering:pixelated">{% else %}<div style="flex:none;font-size:60px">🍐</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ fruit_name }}</div>
      <div class="subtitle">
        <span class="pill">{% if icons.element[element] %}<img src="{{ icons.element[element] }}" style="width:14px;height:14px;object-fit:contain;vertical-align:-3px;margin-right:3px;image-rendering:pixelated">{% else %}{{ emoji }} {% endif %}{{ element }}属性</span>
        {% if power and power != "0" %}<span class="pill">⚔ 威力 {{ power }}</span>{% endif %}
        {% if cooldown %}<span class="pill">⏱ 冷却 {{ cooldown }}s</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="frame">
    {% if effect %}<span class="pill" style="background:#7c8a46;color:#fff3d0;margin-bottom:11px">{{ effect }}</span>{% endif %}
    <div style="font-size:15px;color:#382207;line-height:1.9;white-space:pre-line;word-break:break-word">{{ desc or "（暂无描述）" }}</div>
    <div class="sec-t" style="margin-top:15px">用法</div>
    <div style="font-size:14px;color:#523f10;line-height:1.75;background:rgba(90,58,30,0.12);border:2px solid #6a4524;padding:12px 14px">🍐 将此技能果实喂给帕鲁，即可让它学会主动技能<b class="gold">「{{ tech }}」</b>。技能果实可在世界各地的<b>宝箱</b>等处获得。</div>
  </div>
  """ + _PF + """
</div></body></html>"""

IMPLANT_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:14px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:84px;height:84px;object-fit:contain;image-rendering:pixelated">{% else %}<div style="flex:none;font-size:60px">🧬</div>{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title">{{ name }}</div>
      <div class="subtitle">
        {% if rank %}<span class="pill">稀有度 {{ "★" * (rank if rank <= 5 else 5) }}</span>{% endif %}
        {% if consumable %}<span class="pill red">🔥 耗材·一次性</span>{% else %}<span class="pill">♻ 可反复植入</span>{% endif %}
      </div>
    </div>
  </div></div>
  <div class="frame">
    <div class="sec-t">赋予词条</div>
    <div style="display:flex;align-items:center;gap:10px;background:rgba(90,58,30,0.12);border:2px solid #6a4524;padding:12px 14px">
      <span style="font-size:17px;color:#7a3604">「{{ passive }}」</span>
      {% if effect %}<span style="font-size:14px;color:{% if sign < 0 %}#8f1212{% else %}#5a6a26{% endif %}">{{ effect }}</span>{% endif %}
    </div>
    <div class="sec-t" style="margin-top:15px">用法</div>
    <div style="font-size:14px;color:#523f10;line-height:1.75;background:rgba(90,58,30,0.12);border:2px solid #6a4524;padding:12px 14px">🧬 在据点的<b>帕鲁改造设备</b>上，用此植入体为帕鲁植入被动词条<b class="gold">「{{ passive }}」</b>。{% if consumable %}耗材型植入体使用后消耗，效果通常更强力。{% else %}可反复植入或替换词条。{% endif %}</div>
  </div>
  """ + _PF + """
</div></body></html>"""

WORLDTREE_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🌳 世界树 Boss</div>
    <div class="subtitle"><span class="pill" style="background:#7c8a46;color:#fff3d0">1.0 世界树</span><span class="pill">守护者 + 最终 Boss</span></div>
  </div></div>
  <div class="frame">
    <div style="font-size:13.5px;color:#523f10;line-height:1.75;margin-bottom:6px">世界树深处的守护者(暮尘蛾 / 夜蔓爵，可捕获)镇守通往深渊之路;击败后在最深处迎战最终剧情 Boss「枯星龙」(苏醒，不可捕获)。对应主线「通往深渊之路 → 苏醒」。</div>
    {% for b in bosses %}
    <div class="row" style="align-items:flex-start;gap:12px;padding:12px">
      {% if b.icon %}<img src="{{ b.icon }}" style="width:78px;height:78px;flex:none;object-fit:contain;image-rendering:pixelated">{% else %}<div style="flex:none;font-size:52px">🌳</div>{% endif %}
      <div style="flex:1;min-width:0">
        <div style="font-size:18px;color:#7a3604">{{ b.name }} <span style="font-size:12px;color:#7a5a1a">#{{ b.index }}</span> <span class="pill" style="font-size:11px;{% if b.is_final %}background:#c0392b;color:#fff{% else %}background:#5a7a30;color:#fff3d0{% endif %}">{{ b.role }}</span></div>
        <div style="margin:5px 0;display:flex;flex-wrap:wrap;gap:5px">{% for e in b.elements %}<span class="pill" style="font-size:12px">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:12px;height:12px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}<span class="pill" style="font-size:12px">稀有度 {{ b.rarity }}</span>{% if b.hp %}<span class="pill" style="font-size:12px">HP种族值 {{ b.hp }}</span>{% endif %}{% if b.story_only %}<span class="pill" style="font-size:12px;background:#c0392b;color:#fff">剧情战·不可捕获</span>{% endif %}</div>
        {% if b.partner %}<div style="font-size:12.5px;color:#5a6a26;margin-top:2px">🛡 伙伴技能：{{ b.partner }}</div>{% endif %}
        {% if b.skills %}<div style="font-size:12px;color:#382207;margin-top:4px;line-height:1.6"><b style="color:#7a5a1a">技能</b> {{ b.skills|join('、') }}</div>{% endif %}
        {% if b.drops %}<div style="font-size:12px;color:#7a3604;margin-top:3px"><b style="color:#7a5a1a">掉落</b> {{ b.drops|join('、') }}</div>{% endif %}
      </div>
    </div>{% endfor %}
    <div style="margin-top:13px;font-size:13px;color:#7a5a1a">发 <b class="gold">/帕鲁图鉴 {{ bosses[0].name }}</b> 看完整属性/工作适性/伙伴技能详情;发 /帕鲁栖息地 红菇娘（或 燎火舞伶 / 磐甲龙）可查看世界树独立地图。</div>
  </div>
  """ + _PF + """
</div></body></html>"""

V10_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🎉 幻兽帕鲁 1.0 · 全面支持</div>
    <div class="subtitle"><span class="pill" style="background:#7c8a46;color:#fff3d0">正式版数据已更新</span></div>
  </div></div>
  <div class="frame">
    <div class="sec-t">数据收录 <span style="font-size:11px;color:#7a5a1a">· 帕鲁 {{ stats['pals'] }} 只可收集（官方正式图鉴），含变体共 {{ stats['pals_total'] }} 个数据实体</span></div>
    <div class="m3">
      {% set cells = [("帕鲁图鉴",stats['pals'],"🐾"),("物品",stats['items'],"🎒"),("主动技能",stats['skills'],"✨"),("科技",stats['tech'],"🔬"),("建筑设施",stats['buildings'],"🏛️"),("制作配方",stats['recipes'],"🛠️"),("研究所",stats['lab'],"🧪"),("技能果实",stats['fruits'],"🍐"),("植入体",stats['implants'],"🧬")] %}
      {% for label,num,emo in cells %}
      <div class="tc tile">
        <div class="i">{{ emo }}</div>
        <div class="v">{{ num }}</div>
        <div class="k">{{ label }}</div>
      </div>{% endfor %}
    </div>
    <div class="sec-t" style="margin-top:16px">1.0 新增查询</div>
    <div style="display:flex;flex-direction:column;gap:7px">
      <div style="font-size:13.5px;color:#382207"><b class="gold">/帕鲁研究所</b> — 全局增益研究,9大工作适性,按「手工1」编号查</div>
      <div style="font-size:13.5px;color:#382207"><b class="gold">/帕鲁技能果实</b> — 92种果实按元素分类,按「火1」编号查</div>
      <div style="font-size:13.5px;color:#382207"><b class="gold">/帕鲁植入体</b> — 68种改造词条,「/帕鲁植入体查询 N」按编号</div>
      <div style="font-size:13.5px;color:#382207"><b class="gold">/帕鲁世界树</b> — 最终boss暮尘蛾&夜蔓爵专题</div>
    </div>
    <div style="margin-top:13px;font-size:12.5px;color:#7a5a1a">全部查询支持:名称 / 模糊(含关键字返列表) / 编号 / 分类浏览。</div>
  </div>
  """ + _PF + """
</div></body></html>"""

PASSDEX_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    <div style="flex:none;width:60px;height:60px;background:#caa860;border:2px solid #6a4524;display:flex;align-items:center;justify-content:center;font-size:30px">📜</div>
    <div style="flex:1;min-width:0">
      <div class="title">词条大全</div>
      <div class="subtitle">帕鲁被动词条百科 · 共 <b class="gold">{{ total }}</b> 个 · 9 大类别</div>
    </div>
  </div></div>
  <div class="frame">
    <div class="m2">
    {% for c in cats %}
      <div class="tile" style="padding:12px 13px 11px 16px;border-left:5px solid {{c.color}}">
        <div style="display:flex;align-items:center;gap:9px">
          <div style="flex:none;width:36px;height:36px;background:#caa860;border:2px solid #6a4524;display:flex;align-items:center;justify-content:center;font-size:19px">{{c.icon}}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:15px;color:#46200a">{{c.name}}</div>
            <div style="font-size:11px;color:#7a3604">{{c.count}} 个词条</div>
          </div>
        </div>
        <div style="margin-top:8px;font-size:11px;color:#7a5a1a;line-height:1.5;height:2.2em;overflow:hidden">{{c.sample}}…</div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:13px;padding:10px 13px;background:rgba(90,58,30,0.12);border:2px solid #6a4524;text-align:center;font-size:12px;color:#523f10;line-height:1.7">🔍 发「<b>/帕鲁词条大全 攻击</b>」看该类全部词条 · 「<b>/帕鲁词条大全 力量</b>」查具体效果</div>
  </div>
  """ + _PF + """
</div></body></html>"""

PASSLIST_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    <div style="flex:none;width:58px;height:58px;background:#caa860;border:2px solid #6a4524;display:flex;align-items:center;justify-content:center;font-size:28px">{{ icon }}</div>
    <div style="flex:1;min-width:0">
      <div class="title">{{ cat }}</div>
      <div class="subtitle"><span class="pill">{{ count }} 个词条</span></div>
    </div>
  </div></div>
  <div class="frame">
    {% for it in items %}
    <div class="row" style="gap:11px;border-left:4px solid {% if it.sign>0 %}#7c8a46{% elif it.sign<0 %}#9a4636{% else %}#6a4524{% endif %}">
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">
          <span style="font-size:14.5px;color:#382207">{{ it.name }}</span>
          {% if it.rank %}<span class="pill" style="font-size:10px">Lv{{ it.rank }}</span>{% endif %}
          {% if it.cat %}<span class="pill" style="font-size:10px">{{ it.cat }}</span>{% endif %}
        </div>
        {% if it.effect %}<div style="font-size:12.5px;color:#574012;margin-top:3px;line-height:1.45">{{ it.effect }}</div>{% endif %}
      </div>
      <span style="flex:none;font-size:14px">{% if it.sign>0 %}🟢{% elif it.sign<0 %}🔴{% else %}⚪{% endif %}</span>
    </div>
    {% endfor %}
    <div style="margin-top:5px;text-align:center;font-size:11.5px;color:#7a5a1a">🟢增益 · 🔴减益 · ⚪中性 — 发「/帕鲁词条大全」看全部分类</div>
  </div>
  """ + _PF + """
</div></body></html>"""

AWAKENING_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    <div style="flex:none;width:58px;height:58px;background:#caa860;border:2px solid #6a4524;display:flex;align-items:center;justify-content:center;font-size:28px">🌟</div>
    <div style="flex:1;min-width:0"><div class="title">帕鲁觉醒</div>
      <div class="subtitle">1.0 觉醒系统 · 世界树能量解放隐藏能力</div></div>
  </div></div>
  <div class="frame">
    <div class="sec-t">九系觉醒晶石</div>
    <div class="m3">
    {% for g in gems %}
      <div class="tile" style="padding:10px 6px;text-align:center;border-color:{{g.color}}">
        {% if g.gem_icon %}<img src="{{g.gem_icon}}" style="width:38px;height:38px;object-fit:contain;image-rendering:pixelated">{% else %}<div style="font-size:24px">💎</div>{% endif %}
        <div style="font-size:12.5px;color:{{g.color}};margin-top:3px">{{g.elem}}系</div>
        <div style="font-size:10px;color:#7a5a1a;margin-top:1px">{{g.mat}}→晶石</div>
      </div>
    {% endfor %}
    </div>
    <div style="margin-top:13px;padding:11px 13px;background:rgba(90,58,30,0.12);border:2px solid #6a4524;font-size:12.5px;color:#523f10;line-height:1.75">
      💡 <b class="gold">觉醒机制</b>：击败世界树 Boss 后解锁。用对应属性的<b>辉石</b>加工成<b>觉醒晶石</b>，让该属性帕鲁「觉醒」、解放隐藏能力。<br>
      ⚠️ 具体觉醒提升数值与所需晶石数量，游戏文件未以数据表明确提供，以游戏内为准；<b>暂不支持读取玩家存档中的觉醒状态</b>。
    </div>
  </div>
  """ + _PF + """
</div></body></html>"""

MUTATION_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    <div style="flex:none;width:58px;height:58px;background:#caa860;border:2px solid #6a4524;display:flex;align-items:center;justify-content:center;font-size:28px">🧬</div>
    <div style="flex:1;min-width:0"><div class="title">帕鲁突变</div>
      <div class="subtitle">1.0 突变机制 · 特殊蛋糕影响配种结果</div></div>
  </div></div>
  <div class="frame">
    <div class="sec-t">特殊蛋糕（放入繁殖牧场影响后代）</div>
    <div style="display:flex;flex-direction:column;gap:8px">
    {% for c in cakes %}
      <div class="row" style="gap:11px">
        {% if c.icon %}<img src="{{c.icon}}" style="width:38px;height:38px;object-fit:contain;image-rendering:pixelated;flex-shrink:0">{% else %}<span style="font-size:24px">🍰</span>{% endif %}
        <div style="flex:1;min-width:0"><div style="font-size:14px;color:#7a3604">{{c.name}}</div>
          <div style="font-size:12px;color:#574012;margin-top:2px;line-height:1.45">{{c.effect}}</div></div>
      </div>
    {% endfor %}
    </div>
    {% if eggs %}<div class="sec-t" style="margin-top:14px">突变帕鲁蛋</div>
    <div style="display:flex;gap:9px;flex-wrap:wrap">
    {% for e in eggs %}<span class="pill" style="font-size:12px">{% if e.icon %}<img src="{{e.icon}}" style="width:18px;height:18px;vertical-align:middle;margin-right:3px;image-rendering:pixelated">{% endif %}{{e.name}}</span>{% endfor %}
    </div>{% endif %}
    <div style="margin-top:13px;padding:11px 13px;background:rgba(90,58,30,0.12);border:2px solid #6a4524;font-size:12.5px;color:#523f10;line-height:1.75">
      💡 <b class="ink">突变机制</b>：<b>豪华蔬菜蛋糕</b>提升后代突变概率；突变帕鲁外观/属性与普通不同，可能带专属词条。<b>蘑菇蛋糕</b>提升天赋、<b>蔬菜蛋糕</b>一次产 2 蛋、<b>特制蛋糕</b>提升被动继承。<br>
      ⚠️ 突变<b>准确概率游戏未公开</b>，此处仅说明机制、不猜测数值。
    </div>
  </div>
  """ + _PF + """
</div></body></html>"""


# ---------------- 小队进度(首选1)。变量:members[{name,paldeck,fasttravel,towers,field_bosses,dungeon,relics,areas,next[]}] + dex_total + checklist[{item,done_by[],count}] + hint ----------------
_SQUAD_STATS = ("图鉴 {{ m.paldeck }}/{{ dex_total }}", "传送点 {{ m.fasttravel }}", "塔主 {{ m.towers }}",
                "野外boss {{ m.field_bosses }}", "地牢 {{ m.dungeon }}", "遗物 {{ m.relics }}", "区域 {{ m.areas }}")

SQUAD_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">👥 小队进度</div>
    <div class="subtitle"><span class="pill soft">{{ count }} 名队员</span><span class="pill soft">存档自动同步</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% for m in members %}
    <div style="padding:11px 13px;margin-bottom:9px;border-radius:13px;background:rgba(12,8,38,.42);border:1px solid rgba(232,198,106,.18)">
      <div style="font-size:16px;font-weight:800;color:#f3ecd2">{{ m.name }}</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px">
        <span class="pill soft" style="font-size:11.5px">图鉴 {{ m.paldeck }}/{{ dex_total }}</span>
        <span class="pill soft" style="font-size:11.5px">传送点 {{ m.fasttravel }}</span>
        <span class="pill soft" style="font-size:11.5px">塔主 {{ m.towers }}</span>
        <span class="pill soft" style="font-size:11.5px">野外Boss {{ m.field_bosses }}</span>
        <span class="pill soft" style="font-size:11.5px">地牢 {{ m.dungeon }}</span>
        <span class="pill soft" style="font-size:11.5px">遗物 {{ m.relics }}</span>
        <span class="pill soft" style="font-size:11.5px">区域 {{ m.areas }}</span>
      </div>
      {% if m.next %}<div style="font-size:12.5px;color:#9effb6;margin-top:6px">🎯 下一步：{{ m.next|join('、') }}</div>{% endif %}
    </div>
    {% endfor %}
    {% if checklist %}<div class="sec-t" style="margin-top:6px">📋 小队手动目标</div>
    {% for c in checklist %}<div style="display:flex;align-items:center;gap:8px;padding:5px 0;font-size:13.5px;color:#cfc1ea">
      <span style="color:#7cfc9a">✅</span><b style="color:#f3ecd2">{{ c.item }}</b>
      <span style="margin-left:auto;font-size:12px;color:#9c8fc0">{{ c.done_by|join('、') }}（{{ c.count }}）</span></div>{% endfor %}{% endif %}
    <div style="margin-top:12px;font-size:11px;color:#8a82a8;line-height:1.6">{{ hint }}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

SQUAD_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">▦ 小队进度</div>
    <div class="subtitle"><span class="pill">{{ count }} 名队员</span><span class="pill">存档自动同步</span></div>
  </div></div>
  <div class="frame">
    {% for m in members %}
    <div style="padding:10px 11px;margin-bottom:8px;border:2px solid #6b4a24;background:rgba(221,198,149,.4)">
      <div style="font-size:15px;font-weight:700;color:#2c1a0a">{{ m.name }}</div>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:5px">
        <span class="pill" style="font-size:11px">图鉴 {{ m.paldeck }}/{{ dex_total }}</span>
        <span class="pill" style="font-size:11px">传送点 {{ m.fasttravel }}</span>
        <span class="pill" style="font-size:11px">塔主 {{ m.towers }}</span>
        <span class="pill" style="font-size:11px">野外Boss {{ m.field_bosses }}</span>
        <span class="pill" style="font-size:11px">地牢 {{ m.dungeon }}</span>
        <span class="pill" style="font-size:11px">遗物 {{ m.relics }}</span>
        <span class="pill" style="font-size:11px">区域 {{ m.areas }}</span>
      </div>
      {% if m.next %}<div style="font-size:12px;color:#1d7a36;margin-top:5px">下一步：{{ m.next|join('、') }}</div>{% endif %}
    </div>
    {% endfor %}
    {% if checklist %}<div class="sec-t" style="margin-top:6px">小队手动目标</div>
    {% for c in checklist %}<div style="display:flex;gap:8px;padding:4px 0;font-size:13px;color:#382207"><b>{{ c.item }}</b><span style="margin-left:auto;font-size:11px;color:#7a5a1a">{{ c.done_by|join('、') }}（{{ c.count }}）</span></div>{% endfor %}{% endif %}
    <div style="margin-top:11px;font-size:11px;color:#7a6a4a;line-height:1.6">{{ hint }}</div>
  </div>
  """ + _PF + """
</div></body></html>"""

SQUAD_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">小队进度</div><div class="ig-sub"><span class="ig-pill">{{ count }} 名队员</span><span class="ig-pill">存档自动同步</span></div></div></div>
  {% for m in members %}
  <div class="ig-panel hi"><div style="font-size:16px;font-weight:800;color:var(--pal-text)">{{ m.name }}</div>
    <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:6px">
      <span class="ig-pill">图鉴 {{ m.paldeck }}/{{ dex_total }}</span><span class="ig-pill">传送点 {{ m.fasttravel }}</span>
      <span class="ig-pill">塔主 {{ m.towers }}</span><span class="ig-pill">野外Boss {{ m.field_bosses }}</span>
      <span class="ig-pill">地牢 {{ m.dungeon }}</span><span class="ig-pill">遗物 {{ m.relics }}</span><span class="ig-pill">区域 {{ m.areas }}</span>
    </div>
    {% if m.next %}<div style="font-size:12.5px;color:var(--pal-good);margin-top:6px">下一步：{{ m.next|join('、') }}</div>{% endif %}
  </div>
  {% endfor %}
  {% if checklist %}<div class="ig-panel"><div class="ig-sec">小队手动目标</div>
    {% for c in checklist %}<div class="ig-prow"><b style="color:var(--pal-text)">{{ c.item }}</b><span style="margin-left:auto;font-size:12px;color:var(--pal-sub)">{{ c.done_by|join('、') }}（{{ c.count }}）</span></div>{% endfor %}</div>{% endif %}
  <div class="ig-panel"><div style="font-size:11.5px;color:var(--pal-dim);line-height:1.6">{{ hint }}</div></div>
  """ + _IF + """
</div></body></html>"""


# ---------------- 据点体检(首选2)。变量:workers,working,coverage[{cn,count,maxlv,essential,gap}],hurt,hungry,low_san,sick,advices[],source ----------------
BASEHEALTH_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">🏰 据点体检{% if multi %} · {{ sel_label }}{% endif %}</div>
    <div class="subtitle"><span class="pill soft">工人 {{ workers }}</span><span class="pill soft">工作中 {{ working }}</span></div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    {% if multi %}<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:11px">
      <span class="pill {% if not selected %}gold{% else %}soft{% endif %}">全部</span>
      {% for b in bases %}<span class="pill {% if b.no==selected %}gold{% else %}soft{% endif %}">据点{{ b.no }} · {{ b.count }}只</span>{% endfor %}
      <span style="font-size:11px;color:#9c8fc0;align-self:center">发 /帕鲁据点体检 &lt;号&gt; 看单个据点</span>
    </div>{% endif %}
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">
      <span class="pill" style="background:{% if hurt %}rgba(255,120,120,.2){% else %}rgba(124,252,154,.14){% endif %}">残血 {{ hurt }}</span>
      <span class="pill" style="background:{% if hungry %}rgba(255,180,80,.2){% else %}rgba(124,252,154,.14){% endif %}">饥饿 {{ hungry }}</span>
      <span class="pill" style="background:{% if low_san %}rgba(200,140,255,.2){% else %}rgba(124,252,154,.14){% endif %}">理智低 {{ low_san }}</span>
      <span class="pill" style="background:{% if sick %}rgba(255,120,120,.2){% else %}rgba(124,252,154,.14){% endif %}">工作病 {{ sick }}</span>
    </div>
    <div class="sec-t">工作适性覆盖</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px">
    {% for c in coverage %}
      <div style="display:flex;align-items:center;gap:7px;padding:6px 10px;border-radius:10px;background:{% if c.gap and c.essential %}rgba(255,90,90,.14){% else %}rgba(12,8,38,.4){% endif %};border:1px solid {% if c.gap and c.essential %}rgba(255,90,90,.4){% else %}rgba(232,198,106,.16){% endif %}">
        <span style="font-size:13px;color:#f3ecd2;{% if c.essential %}font-weight:800{% endif %}">{{ c.cn }}</span>
        <span style="margin-left:auto;font-size:12.5px;color:{% if c.gap %}#ff9a9a{% else %}#9effb6{% endif %}">{% if c.gap %}缺{% else %}{{ c.count }} 只 · Lv{{ c.maxlv }}{% endif %}</span>
      </div>
    {% endfor %}
    </div>
    <div class="sec-t" style="margin-top:15px">📋 体检建议</div>
    {% for a in advices %}<div style="font-size:13px;color:#cfc1ea;line-height:1.7;margin-top:3px">• {{ a }}</div>{% endfor %}
    <div style="margin-top:12px;font-size:11px;color:#8a82a8;line-height:1.6">{{ source }}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

BASEHEALTH_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div>
    <div class="title">■ 据点体检{% if multi %} · {{ sel_label }}{% endif %}</div>
    <div class="subtitle"><span class="pill">工人 {{ workers }}</span><span class="pill">工作中 {{ working }}</span></div>
  </div></div>
  <div class="frame">
    {% if multi %}<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px">
      <span class="pill"{% if not selected %} style="background:#6b4a24;color:#fff7e0"{% endif %}>全部</span>
      {% for b in bases %}<span class="pill"{% if b.no==selected %} style="background:#6b4a24;color:#fff7e0"{% endif %}>据点{{ b.no }}·{{ b.count }}</span>{% endfor %}
      <span style="font-size:11px;color:#7a6a4a;align-self:center">/帕鲁据点体检 &lt;号&gt;</span>
    </div>{% endif %}
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:11px">
      <span class="pill">残血 {{ hurt }}</span><span class="pill">饥饿 {{ hungry }}</span><span class="pill">理智低 {{ low_san }}</span><span class="pill">工作病 {{ sick }}</span>
    </div>
    <div class="sec-t">工作适性覆盖</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px">
    {% for c in coverage %}
      <div style="display:flex;gap:6px;padding:5px 9px;border:2px solid {% if c.gap and c.essential %}#c0392b{% else %}#6b4a24{% endif %};background:{% if c.gap and c.essential %}rgba(192,57,43,.14){% else %}rgba(221,198,149,.35){% endif %}">
        <span style="font-size:12.5px;color:#2c1a0a;{% if c.essential %}font-weight:700{% endif %}">{{ c.cn }}</span>
        <span style="margin-left:auto;font-size:12px;color:{% if c.gap %}#8f1212{% else %}#1d7a36{% endif %}">{% if c.gap %}缺{% else %}{{ c.count }}·Lv{{ c.maxlv }}{% endif %}</span>
      </div>
    {% endfor %}
    </div>
    <div class="sec-t" style="margin-top:14px">体检建议</div>
    {% for a in advices %}<div style="font-size:13px;color:#382207;line-height:1.7;margin-top:3px">• {{ a }}</div>{% endfor %}
    <div style="margin-top:11px;font-size:11px;color:#7a6a4a;line-height:1.6">{{ source }}</div>
  </div>
  """ + _PF + """
</div></body></html>"""

BASEHEALTH_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head"><div style="flex:1;min-width:0"><div class="ig-title">据点体检{% if multi %} · {{ sel_label }}{% endif %}</div><div class="ig-sub"><span class="ig-pill">工人 {{ workers }}</span><span class="ig-pill">工作中 {{ working }}</span></div></div></div>
  {% if multi %}<div class="ig-panel"><div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center">
    <span class="ig-pill{% if not selected %} gold{% endif %}">全部</span>
    {% for b in bases %}<span class="ig-pill{% if b.no==selected %} gold{% endif %}">据点{{ b.no }} · {{ b.count }}只</span>{% endfor %}
    <span style="font-size:11px;color:var(--pal-dim)">发 /帕鲁据点体检 &lt;号&gt;</span>
  </div></div>{% endif %}
  <div class="ig-panel">
    <div style="display:flex;flex-wrap:wrap;gap:6px">
      <span class="ig-pill"{% if hurt %} style="color:var(--pal-danger)"{% endif %}>残血 {{ hurt }}</span><span class="ig-pill"{% if hungry %} style="color:var(--pal-gold)"{% endif %}>饥饿 {{ hungry }}</span>
      <span class="ig-pill">理智低 {{ low_san }}</span><span class="ig-pill"{% if sick %} style="color:var(--pal-danger)"{% endif %}>工作病 {{ sick }}</span>
    </div>
  </div>
  <div class="ig-panel hi"><div class="ig-sec">工作适性覆盖</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:7px">
    {% for c in coverage %}<div class="ig-prow" style="justify-content:space-between"><span{% if c.essential %} style="font-weight:800"{% endif %}>{{ c.cn }}</span><span style="font-size:12px;color:{% if c.gap %}var(--pal-danger){% else %}var(--pal-good){% endif %}">{% if c.gap %}缺{% else %}{{ c.count }} · Lv{{ c.maxlv }}{% endif %}</span></div>{% endfor %}
    </div>
  </div>
  <div class="ig-panel"><div class="ig-sec">体检建议</div>
    {% for a in advices %}<div style="font-size:13px;color:var(--pal-text-2);line-height:1.7;margin-top:3px">• {{ a }}</div>{% endfor %}
    <div style="margin-top:10px;font-size:11px;color:var(--pal-dim)">{{ source }}</div>
  </div>
  """ + _IF + """
</div></body></html>"""


# ---------------- 养成(首选3)。变量:name,icon,elements,level,nickname,count,condense,condense_max,souls[{k,lv}],awakened,gem,element_cn,iv_*,passives[],wazas[],notes[],source ----------------
GROWTH_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:76px;height:76px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))">{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title" style="font-size:24px">{{ name }}{% if nickname %} <span style="font-size:14px;color:#9c8fc0">「{{ nickname }}」</span>{% endif %}</div>
      <div class="subtitle"><span class="pill soft">Lv.{{ level }}</span>{% for e in elements %}<span class="pill soft">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px">{% endif %}{{ e }}</span>{% endfor %}{% if count > 1 %}<span class="pill soft">你有 {{ count }} 只 · 看第 {{ pick|default(1) }} 只</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="glass">""" + _GEMS + """
    <div class="sec-t">浓缩</div>
    <div style="font-size:22px;letter-spacing:2px;color:#e8c466">{% for i in range(condense_max) %}{% if i < condense %}★{% else %}<span style="color:#4a3f6a">☆</span>{% endif %}{% endfor %} <span style="font-size:14px;color:#cfc1ea">{{ condense }}/{{ condense_max }}★</span></div>
    {% if souls %}<div class="sec-t" style="margin-top:14px">帕鲁之魂强化</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for s in souls %}<span class="pill soft">{{ s.k }} +{{ s.lv }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:14px">觉醒</div>
    <div style="font-size:14px;color:{% if awakened %}#7fe0a0{% else %}#ffce6b{% endif %}">{% if awakened %}✔ 已觉醒{% else %}○ 未觉醒{% if gem %} · 需「{{ gem }}」{% endif %}{% endif %}</div>
    <div class="sec-t" style="margin-top:14px">个体值(天赋 · 捕捉固定)</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px"><span class="pill soft">HP {{ iv_hp }}/100</span><span class="pill soft">攻击 {{ iv_atk }}/100</span><span class="pill soft">防御 {{ iv_def }}/100</span></div>
    {% if passives %}<div class="sec-t" style="margin-top:14px">词条 <span style="font-size:11px;color:#9c8fc0">{{ passives|length }}/4</span></div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for x in passives %}<span class="pill soft">{{ x }}</span>{% endfor %}</div>{% endif %}
    {% if wazas %}<div class="sec-t" style="margin-top:14px">已装备技能</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for x in wazas %}<span class="pill soft">{{ x }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:15px">养成建议</div>
    {% for n in notes %}<div style="font-size:12.5px;color:#cfc1ea;line-height:1.7;margin-top:2px">• {{ n }}</div>{% endfor %}
    <div style="margin-top:11px;font-size:11px;color:#8a82a8;line-height:1.6">{{ source }}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

GROWTH_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:70px;height:70px;object-fit:contain;image-rendering:pixelated">{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title" style="font-size:22px">{{ name }}{% if nickname %} <span style="font-size:13px;color:#7a5a1a">「{{ nickname }}」</span>{% endif %}</div>
      <div class="subtitle"><span class="pill">Lv.{{ level }}</span>{% for e in elements %}<span class="pill">{% if icons.element[e] %}<img src="{{ icons.element[e] }}" style="width:13px;height:13px;object-fit:contain;vertical-align:-2px;margin-right:2px;image-rendering:pixelated">{% endif %}{{ e }}</span>{% endfor %}{% if count > 1 %}<span class="pill">你有 {{ count }} 只 · 看第 {{ pick|default(1) }} 只</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="frame">
    <div class="sec-t">浓缩</div>
    <div style="font-size:20px;letter-spacing:2px;color:#7a3604">{% for i in range(condense_max) %}{% if i < condense %}★{% else %}☆{% endif %}{% endfor %} <span style="font-size:13px;color:#523f10">{{ condense }}/{{ condense_max }}★</span></div>
    {% if souls %}<div class="sec-t" style="margin-top:12px">帕鲁之魂强化</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for s in souls %}<span class="pill">{{ s.k }} +{{ s.lv }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:12px">觉醒</div>
    <div style="font-size:14px;color:{% if awakened %}#1d7a36{% else %}#8f5a12{% endif %}">{% if awakened %}✔ 已觉醒{% else %}○ 未觉醒{% if gem %} · 需「{{ gem }}」{% endif %}{% endif %}</div>
    <div class="sec-t" style="margin-top:12px">个体值(天赋 · 捕捉固定)</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px"><span class="pill">HP {{ iv_hp }}/100</span><span class="pill">攻击 {{ iv_atk }}/100</span><span class="pill">防御 {{ iv_def }}/100</span></div>
    {% if passives %}<div class="sec-t" style="margin-top:12px">词条 {{ passives|length }}/4</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for x in passives %}<span class="pill">{{ x }}</span>{% endfor %}</div>{% endif %}
    {% if wazas %}<div class="sec-t" style="margin-top:12px">已装备技能</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for x in wazas %}<span class="pill">{{ x }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:13px">养成建议</div>
    {% for n in notes %}<div style="font-size:12.5px;color:#382207;line-height:1.7;margin-top:2px">• {{ n }}</div>{% endfor %}
    <div style="margin-top:10px;font-size:11px;color:#7a6a4a;line-height:1.6">{{ source }}</div>
  </div>
  """ + _PF + """
</div></body></html>"""

GROWTH_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-portrait" style="width:70px;height:70px;border-width:10px"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">{{ name }}{% if nickname %} 「{{ nickname }}」{% endif %}</div><div class="ig-sub"><span class="ig-pill">Lv.{{ level }}</span>{% for e in elements %}<span class="ig-badge">{% if icons.element[e] %}<img src="{{ icons.element[e] }}">{% endif %}{{ e }}</span>{% endfor %}{% if count > 1 %}<span class="ig-pill">你有 {{ count }} 只 · 看第 {{ pick|default(1) }} 只</span>{% endif %}</div></div></div>
  <div class="ig-panel"><div class="ig-sec">浓缩</div>
    <div style="font-size:20px;letter-spacing:2px;color:var(--pal-gold)">{% for i in range(condense_max) %}{% if i < condense %}★{% else %}☆{% endif %}{% endfor %} <span style="font-size:13px;color:var(--pal-sub)">{{ condense }}/{{ condense_max }}★</span></div></div>
  {% if souls %}<div class="ig-panel hi"><div class="ig-sec">帕鲁之魂强化</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for s in souls %}<span class="ig-pill">{{ s.k }} +{{ s.lv }}</span>{% endfor %}</div></div>{% endif %}
  <div class="ig-panel"><div class="ig-sec">觉醒</div><div style="font-size:14px;color:{% if awakened %}var(--pal-good){% else %}var(--pal-gold){% endif %}">{% if awakened %}✔ 已觉醒{% else %}○ 未觉醒{% if gem %} · 需「{{ gem }}」{% endif %}{% endif %}</div></div>
  <div class="ig-panel"><div class="ig-sec">个体值(天赋 · 捕捉固定)</div><div style="display:flex;flex-wrap:wrap;gap:6px"><span class="ig-pill">HP {{ iv_hp }}/100</span><span class="ig-pill">攻击 {{ iv_atk }}/100</span><span class="ig-pill">防御 {{ iv_def }}/100</span></div></div>
  {% if passives %}<div class="ig-panel"><div class="ig-sec">词条 {{ passives|length }}/4</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for x in passives %}<span class="ig-pill">{{ x }}</span>{% endfor %}</div></div>{% endif %}
  {% if wazas %}<div class="ig-panel"><div class="ig-sec">已装备技能</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for x in wazas %}<span class="ig-pill">{{ x }}</span>{% endfor %}</div></div>{% endif %}
  <div class="ig-panel"><div class="ig-sec">养成建议</div>{% for n in notes %}<div style="font-size:12.5px;color:var(--pal-text-2);line-height:1.7;margin-top:2px">• {{ n }}</div>{% endfor %}<div style="margin-top:9px;font-size:11px;color:var(--pal-dim)">{{ source }}</div></div>
  """ + _IF + """
</div></body></html>"""


MATROUTE_TMPL = _HEAD + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:13px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:64px;height:64px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.6))">{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title" style="font-size:23px">材料路线 · {{ name }}</div>
      <div class="subtitle"><span class="pill soft">制作 ×{{ mult }}</span><span class="pill soft">原料 {{ base|length }} 种</span>{% if inter %}<span class="pill soft">中间产物 {{ inter|length }} 种</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="glass">
    <div class="sec-t">直接配方</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for m in direct %}<span class="pill soft">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ m.name }} ×{{ m.count }}{% if m.craftable %} <span style="color:#8fd3ff;font-size:10px">·可制作</span>{% endif %}</span>{% endfor %}</div>
    {% if benches %}<div style="margin-top:8px;font-size:12px;color:#cfc1ea">🔧 制作台(全链路)：{% for b in benches %}{{ b }}{% if not loop.last %} / {% endif %}{% endfor %}</div>{% endif %}
    {% if inter %}<div class="sec-t" style="margin-top:15px">中间产物(需先制作)</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for m in inter %}<span class="pill soft">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ m.name }} ×{{ m.count }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:15px">原料总需求(展开到底) <span style="font-size:11px;color:#9c8fc0">共 {{ base|length }} 种</span></div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">{% for m in base %}<span class="pill soft">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ m.name }} ×{{ m.count }}</span>{% endfor %}</div>
    <div style="margin-top:12px;font-size:11px;color:#8a82a8;line-height:1.6">{{ source }}</div>
  </div>
  """ + _FOOT + """
</div></body></html>"""

MATROUTE_PIX = _PH + """</style></head><body><div class="page">
  <div class="head"><div style="display:flex;align-items:center;gap:12px;width:100%">
    {% if icon %}<img src="{{ icon }}" style="flex:none;width:60px;height:60px;object-fit:contain;image-rendering:pixelated">{% endif %}
    <div style="flex:1;min-width:0">
      <div class="title" style="font-size:21px">材料路线 · {{ name }}</div>
      <div class="subtitle"><span class="pill">制作 ×{{ mult }}</span><span class="pill">原料 {{ base|length }} 种</span>{% if inter %}<span class="pill">中间产物 {{ inter|length }} 种</span>{% endif %}</div>
    </div>
  </div></div>
  <div class="frame">
    <div class="sec-t">直接配方</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for m in direct %}<span class="pill">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px;image-rendering:pixelated">{% endif %}{{ m.name }} ×{{ m.count }}{% if m.craftable %} <span style="color:#7a3604;font-size:10px">·可制作</span>{% endif %}</span>{% endfor %}</div>
    {% if benches %}<div style="margin-top:8px;font-size:12px;color:#523f10">🔧 制作台(全链路)：{% for b in benches %}{{ b }}{% if not loop.last %} / {% endif %}{% endfor %}</div>{% endif %}
    {% if inter %}<div class="sec-t" style="margin-top:13px">中间产物(需先制作)</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for m in inter %}<span class="pill">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px;image-rendering:pixelated">{% endif %}{{ m.name }} ×{{ m.count }}</span>{% endfor %}</div>{% endif %}
    <div class="sec-t" style="margin-top:13px">原料总需求(展开到底) {{ base|length }} 种</div>
    <div style="display:flex;flex-wrap:wrap;gap:6px">{% for m in base %}<span class="pill">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px;image-rendering:pixelated">{% endif %}{{ m.name }} ×{{ m.count }}</span>{% endfor %}</div>
    <div style="margin-top:11px;font-size:11px;color:#7a6a4a;line-height:1.6">{{ source }}</div>
  </div>
  """ + _PF + """
</div></body></html>"""

MATROUTE_ING = _IH + """</style></head><body><div class="page">
  <div class="ig-head">{% if icon %}<div class="ig-portrait" style="width:60px;height:60px;border-width:8px"><img src="{{ icon }}"></div>{% endif %}<div style="flex:1;min-width:0"><div class="ig-title">材料路线 · {{ name }}</div><div class="ig-sub"><span class="ig-pill">制作 ×{{ mult }}</span><span class="ig-pill">原料 {{ base|length }} 种</span>{% if inter %}<span class="ig-pill">中间产物 {{ inter|length }} 种</span>{% endif %}</div></div></div>
  <div class="ig-panel"><div class="ig-sec">直接配方</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for m in direct %}<span class="ig-pill">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ m.name }} ×{{ m.count }}{% if m.craftable %} <span style="color:var(--pal-accent);font-size:10px">·可制作</span>{% endif %}</span>{% endfor %}</div>{% if benches %}<div style="margin-top:8px;font-size:12px;color:var(--pal-sub)">制作台(全链路)：{% for b in benches %}{{ b }}{% if not loop.last %} / {% endif %}{% endfor %}</div>{% endif %}</div>
  {% if inter %}<div class="ig-panel hi"><div class="ig-sec">中间产物(需先制作)</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for m in inter %}<span class="ig-pill">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ m.name }} ×{{ m.count }}</span>{% endfor %}</div></div>{% endif %}
  <div class="ig-panel"><div class="ig-sec">原料总需求(展开到底) · {{ base|length }} 种</div><div style="display:flex;flex-wrap:wrap;gap:6px">{% for m in base %}<span class="ig-pill">{% if m.icon %}<img src="{{ m.icon }}" style="width:15px;height:15px;object-fit:contain;vertical-align:-3px;margin-right:3px">{% endif %}{{ m.name }} ×{{ m.count }}</span>{% endfor %}</div><div style="margin-top:9px;font-size:11px;color:var(--pal-dim)">{{ source }}</div></div>
  """ + _IF + """
</div></body></html>"""


STYLES = {
    "fantasy": {"status": STATUS_TMPL, "players": PLAYERS_TMPL, "settings": SETTINGS_TMPL,
                "help": HELP_TMPL, "message": MSG_TMPL, "stats": STATS_TMPL, "rank": RANK_TMPL,
                "profile": PROFILE_TMPL, "daily": DAILY_TMPL, "paldex": PALDEX_TMPL, "breed": BREED_TMPL,
                "reverse": REVERSE_TMPL, "drop": DROP_TMPL, "droplist": DROPLIST_TMPL,
                "heatmap": HEATMAP_TMPL, "power": POWER_TMPL, "route": ROUTE_TMPL, "shiny": SHINY_TMPL,
                "palpower": PALPOWER_TMPL, "palpowerdetail": PALPOWERDETAIL_TMPL,
                "symptom": SYMPTOM_TMPL,
                "item": ITEM_TMPL, "itemcat": ITEMCAT_TMPL,
                "facility": FACILITY_TMPL, "tech": TECH_TMPL, "grid": GRID_TMPL, "map": MAP_TMPL,
                "lab_overview": LAB_OVERVIEW_TMPL, "lab_list": LAB_LIST_TMPL, "lab_detail": LAB_DETAIL_TMPL,
                "bag": BAG_TMPL, "team": TEAM_TMPL, "palbox": PALBOX_TMPL, "guild": GUILD_TMPL,
                "basecamp": BASECAMP_TMPL, "squad": SQUAD_TMPL, "basehealth": BASEHEALTH_TMPL, "growth": GROWTH_TMPL, "matroute": MATROUTE_TMPL,
                "element": ELEMENT_TMPL, "habitat": HABITAT_TMPL, "passrec": PASSREC_TMPL,
                "passdex": PASSDEX_TMPL, "passlist": PASSLIST_TMPL,
                "awakening": AWAKENING_TMPL, "mutation": MUTATION_TMPL,
                "mission": MISSION_TMPL, "missionlist": MISSIONLIST_TMPL, "boss": BOSS_TMPL,
                "merchant": MERCHANT_TMPL, "skill": SKILL_TMPL, "skillfruit": SKILLFRUIT_TMPL, "implant": IMPLANT_TMPL, "worldtree": WORLDTREE_TMPL, "v10": V10_TMPL, "compare": COMPARE_TMPL,
                "hatch": HATCH_TMPL, "inherit": INHERIT_TMPL,
                "arena": ARENA_TMPL, "arena_tier": ARENA_TIER_TMPL},
    "pixel": {"status": STATUS_PIX, "players": PLAYERS_PIX, "settings": SETTINGS_PIX,
              "help": HELP_PIX, "message": MSG_PIX, "stats": STATS_PIX, "rank": RANK_PIX,
              "profile": PROFILE_PIX, "daily": DAILY_PIX, "paldex": PALDEX_PIX, "breed": BREED_PIX,
              "reverse": REVERSE_PIX, "drop": DROP_PIX, "droplist": DROPLIST_PIX,
              "heatmap": HEATMAP_PIX, "power": POWER_PIX, "route": ROUTE_PIX, "shiny": SHINY_PIX,
              "palpower": PALPOWER_PIX, "palpowerdetail": PALPOWERDETAIL_PIX,
              "symptom": SYMPTOM_PIX,
              "item": ITEM_PIX, "itemcat": ITEMCAT_PIX,
              "facility": FACILITY_PIX, "tech": TECH_PIX, "grid": GRID_PIX, "map": MAP_PIX,
              "lab_overview": LAB_OVERVIEW_PIX, "lab_list": LAB_LIST_PIX, "lab_detail": LAB_DETAIL_PIX,
              "bag": BAG_PIX, "team": TEAM_PIX, "palbox": PALBOX_PIX, "guild": GUILD_PIX,
              "basecamp": BASECAMP_PIX, "squad": SQUAD_PIX, "basehealth": BASEHEALTH_PIX, "growth": GROWTH_PIX, "matroute": MATROUTE_PIX,
              "element": ELEMENT_PIX, "habitat": HABITAT_PIX, "passrec": PASSREC_PIX,
              "passdex": PASSDEX_PIX, "passlist": PASSLIST_PIX,
              "awakening": AWAKENING_PIX, "mutation": MUTATION_PIX,
              "mission": MISSION_PIX, "missionlist": MISSIONLIST_PIX, "boss": BOSS_PIX,
              "merchant": MERCHANT_PIX, "skill": SKILL_PIX,
              "skillfruit": SKILLFRUIT_PIX, "implant": IMPLANT_PIX, "worldtree": WORLDTREE_PIX, "v10": V10_PIX,
              "compare": COMPARE_PIX,
              "hatch": HATCH_PIX, "inherit": INHERIT_PIX,
              "arena": ARENA_PIX, "arena_tier": ARENA_TIER_PIX},
}
# ingame 游戏原生主题(独立第三套)。**开发期临时回退**:各卡尚未逐一改造前,
# 复用 fantasy 模板串以保证 56 个模板键齐全、指令不异常;逐卡替换后再改为 ingame 专属模板。
# 该临时回退是**显式记录**的(见 docs/INGAME_ICON_COVERAGE.md),非「悄悄用别的主题」。
STYLES["ingame"] = dict(STYLES["fantasy"])
STYLES["ingame"]["squad"] = SQUAD_ING
STYLES["ingame"]["basehealth"] = BASEHEALTH_ING
STYLES["ingame"]["growth"] = GROWTH_ING
STYLES["ingame"]["matroute"] = MATROUTE_ING
# 阶段D:已改造为 ingame 专属布局的卡(其余仍临时回退 fantasy,见 INGAME_ICON_COVERAGE.md)
STYLES["ingame"]["paldex"] = PALDEX_ING
STYLES["ingame"]["passlist"] = PASSLIST_ING
STYLES["ingame"]["passdex"] = PASSDEX_ING
STYLES["ingame"]["passrec"] = PASSREC_ING
STYLES["ingame"]["status"] = STATUS_ING
STYLES["ingame"]["players"] = PLAYERS_ING
STYLES["ingame"]["bag"] = BAG_ING
STYLES["ingame"]["palbox"] = PALBOX_ING
STYLES["ingame"]["profile"] = PROFILE_ING
STYLES["ingame"]["team"] = TEAM_ING
STYLES["ingame"]["message"] = MSG_ING
STYLES["ingame"]["stats"] = STATS_ING
STYLES["ingame"]["settings"] = SETTINGS_ING
STYLES["ingame"]["grid"] = GRID_ING
STYLES["ingame"]["itemcat"] = ITEMCAT_ING
STYLES["ingame"]["tech"] = TECH_ING
STYLES["ingame"]["item"] = ITEM_ING
STYLES["ingame"]["facility"] = FACILITY_ING
STYLES["ingame"]["skill"] = SKILL_ING
STYLES["ingame"]["rank"] = RANK_ING
STYLES["ingame"]["power"] = POWER_ING
STYLES["ingame"]["palpower"] = PALPOWER_ING
STYLES["ingame"]["palpowerdetail"] = PALPOWERDETAIL_ING
STYLES["ingame"]["guild"] = GUILD_ING
STYLES["ingame"]["drop"] = DROP_ING
STYLES["ingame"]["droplist"] = DROPLIST_ING
STYLES["ingame"]["shiny"] = SHINY_ING
STYLES["ingame"]["symptom"] = SYMPTOM_ING
STYLES["ingame"]["reverse"] = REVERSE_ING
STYLES["ingame"]["heatmap"] = HEATMAP_ING
STYLES["ingame"]["element"] = ELEMENT_ING
STYLES["ingame"]["habitat"] = HABITAT_ING
STYLES["ingame"]["map"] = MAP_ING
STYLES["ingame"]["mission"] = MISSION_ING
STYLES["ingame"]["missionlist"] = MISSIONLIST_ING
STYLES["ingame"]["boss"] = BOSS_ING
STYLES["ingame"]["merchant"] = MERCHANT_ING
STYLES["ingame"]["skillfruit"] = SKILLFRUIT_ING
STYLES["ingame"]["implant"] = IMPLANT_ING
STYLES["ingame"]["worldtree"] = WORLDTREE_ING
STYLES["ingame"]["v10"] = V10_ING
STYLES["ingame"]["awakening"] = AWAKENING_ING
STYLES["ingame"]["mutation"] = MUTATION_ING
STYLES["ingame"]["lab_overview"] = LAB_OVERVIEW_ING
STYLES["ingame"]["lab_list"] = LAB_LIST_ING
STYLES["ingame"]["lab_detail"] = LAB_DETAIL_ING
STYLES["ingame"]["breed"] = BREED_ING
STYLES["ingame"]["route"] = ROUTE_ING
STYLES["ingame"]["hatch"] = HATCH_ING
STYLES["ingame"]["inherit"] = INHERIT_ING
STYLES["ingame"]["compare"] = COMPARE_ING
STYLES["ingame"]["arena"] = ARENA_ING
STYLES["ingame"]["arena_tier"] = ARENA_TIER_ING
STYLES["ingame"]["daily"] = DAILY_ING
STYLES["ingame"]["help"] = HELP_ING
STYLES["ingame"]["basecamp"] = BASECAMP_ING
STYLE_NAMES = {"fantasy": "🌌 奇幻玻璃", "pixel": "📜 像素羊皮纸", "ingame": "游戏原生"}
STYLE_ALIAS = {"奇幻": "fantasy", "玻璃": "fantasy", "fantasy": "fantasy", "二次元": "fantasy",
               "像素": "pixel", "羊皮纸": "pixel", "复古": "pixel", "pixel": "pixel",
               "游戏": "ingame", "原生": "ingame", "游戏原生": "ingame", "ingame": "ingame"}

# 模板字符串 -> 卡名(两套风格都映射，供 _bg_for 查专属背景图)
TEMPLATE_KEYS = {}
for _st in STYLES.values():
    for _k, _t in _st.items():
        TEMPLATE_KEYS[_t] = _k
