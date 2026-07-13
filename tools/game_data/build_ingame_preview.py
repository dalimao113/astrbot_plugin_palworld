#!/usr/bin/env python3
"""生成 ingame 主题组件预览 HTML(docs/ingame_preview.html)。

用真实游戏纹理(data/ingame/parts,经 AssetResolver 注入)+ 真实图标 + render/templates._INGAME_CSS
拼装一张示例卡,供无本地浏览器时通过 Artifact / 浏览器预览组件效果。
纯预览工具,不参与运行时。用法:python tools/game_data/build_ingame_preview.py
"""
from __future__ import annotations

import base64
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(_ROOT))

from astrbot_plugin_palworld.render import templates as T  # noqa: E402
from astrbot_plugin_palworld.render.assets import AssetResolver  # noqa: E402


def _png(rel: str) -> str:
    with open(os.path.join(_ROOT, rel), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def main() -> int:
    from jinja2 import Environment
    R = AssetResolver(_ROOT)
    parts = R.component_uris()

    def img(k: str) -> str:
        return R.img(k, "ingame")

    env = Environment(autoescape=False)
    css = env.from_string(T._INGAME_CSS).render(parts=parts, zoom=1, cw=540)
    css += ("\n  html,body{width:auto !important;} body{align-items:center; min-height:100vh;}"
            "\n  .page{width:540px; max-width:100%; margin:0 auto;}"
            "\n  .demo-note{width:540px;max-width:100%;margin:14px auto 4px;color:#b6a888;font-size:12.5px;"
            "line-height:1.6;background:rgba(0,0,0,.35);border:1px solid rgba(201,183,141,.3);padding:10px 13px;}"
            "\n  .demo-note b{color:#f0cf7a;}")

    el = {k: img(f"element.{k}") for k in
          ("fire", "water", "grass", "electric", "ice", "ground", "dark", "dragon", "neutral")}
    wk = {k: img(f"work.{k}") for k in ("mining", "handiwork", "kindling", "watering", "transport", "cooling")}
    st = {k: img(f"stat.{k}") for k in ("hp", "defense", "hunger")}
    pals = [_png(f"data/images/{n}.png") for n in ("BlueDragon", "WoolFox", "PinkCat")]
    fps_svg, up_svg = img("server.fps"), img("server.uptime")

    body = _BODY.format(crest=el["dragon"], el=el, wk=wk, st=st,
                        pal0=pals[0], pal1=pals[1], pal2=pals[2],
                        fps=fps_svg, up=up_svg,
                        foot=T._IF.replace("{{ now }}", "2026-07-12 22:00"))
    html = "<title>Palworld ingame 主题 · 组件预览</title>\n<style>" + css + "</style>\n" + body
    out = os.path.join(_ROOT, "docs", "ingame_preview.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[done] {out} ({len(html)} bytes)")
    return 0


# 展示卡 body(见 docs/ingame_preview.html);用 str.format,el/wk/st 为 dict。
_BODY = """
<div class="demo-note">🎮 <b>ingame 游戏原生主题 · 组件预览</b>(阶段C)。用的是<b>从游戏客户端提取的真实 UI 纹理</b>
(八角节点框/切角物品槽/帕鲁卡框/进度条)+ 真实属性/工作/数值图标。<br>
⚠️ 配色/间距为<b>临时值</b>,待游戏截图再精校(色板、slice、字号)。这版先验证组件与纹理能正确拼装。</div>
<div class="page">
  <div class="ig-head">
    <div class="ig-crest"><img src="{crest}"></div>
    <div style="flex:1;min-width:0">
      <div class="ig-title">冰龙 · 帕鲁详情</div>
      <div class="ig-sub"><span class="ig-pill gold">图鉴 #085</span>
        <span class="ig-badge"><img src="{el[dragon]}">龙</span>
        <span class="ig-badge"><img src="{el[ice]}">冰</span></div>
    </div>
    <div class="ig-badge-on">在线</div>
  </div>
  <div class="ig-tabs"><span class="ig-tab on">属性</span><span class="ig-tab">技能</span>
    <span class="ig-tab">工作</span><span class="ig-tab">掉落</span></div>
  <div class="ig-panel"><div class="ig-sec">基础数值</div>
    <div class="ig-stat"><div class="lab"><span class="ic"><img src="{st[hp]}">生命</span><b>115</b></div>
      <div class="ig-track"><div class="ig-fill hp" style="width:78%"></div></div></div>
    <div class="ig-stat"><div class="lab"><span class="ic"><img src="{el[neutral]}">近战攻击</span><b>100</b></div>
      <div class="ig-track"><div class="ig-fill" style="width:66%"></div></div></div>
    <div class="ig-stat"><div class="lab"><span class="ic"><img src="{st[defense]}">防御力</span><b>95</b></div>
      <div class="ig-track"><div class="ig-fill" style="width:60%"></div></div></div>
    <div class="ig-stat"><div class="lab"><span class="ic"><img src="{st[hunger]}">饱食度</span><b>450</b></div>
      <div class="ig-track"><div class="ig-fill san" style="width:88%"></div></div></div></div>
  <div class="ig-panel hi"><div class="ig-sec">工作适性</div>
    <div style="display:flex;flex-wrap:wrap;gap:7px">
      <span class="ig-work"><img src="{wk[kindling]}">点火 Lv3</span>
      <span class="ig-work"><img src="{wk[mining]}">采矿 Lv2</span>
      <span class="ig-work"><img src="{wk[handiwork]}">手工 Lv2</span>
      <span class="ig-work"><img src="{wk[transport]}">搬运 Lv1</span>
      <span class="ig-work"><img src="{wk[cooling]}">制冷 Lv4</span></div></div>
  <div class="ig-panel"><div class="ig-sec">属性节点(八角框:普通/金/选中)</div>
    <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <div class="ig-node"><img src="{el[fire]}"></div>
      <div class="ig-node gold"><img src="{el[water]}"></div>
      <div class="ig-node sel"><img src="{el[electric]}"></div>
      <div class="ig-node"><img src="{el[grass]}"></div>
      <div class="ig-node gold"><img src="{el[dark]}"></div>
      <div class="ig-node sel"><img src="{el[ground]}"></div></div></div>
  <div class="ig-panel"><div class="ig-sec">物品槽(切角,选中态)</div>
    <div class="ig-grid">
      <div class="ig-slot"><img src="{wk[mining]}"><span class="qty">12</span></div>
      <div class="ig-slot"><img src="{el[fire]}"><span class="qty">3</span></div>
      <div class="ig-slot sel"><img src="{st[hp]}"><span class="qty">7</span></div>
      <div class="ig-slot"><img src="{wk[watering]}"></div>
      <div class="ig-slot"><img src="{el[ice]}"><span class="qty">99</span></div></div></div>
  <div class="ig-panel hi"><div class="ig-sec">帕鲁卡 & 服务器扩展图标</div>
    <div style="display:flex;gap:10px;align-items:flex-start">
      <div class="ig-palcard" style="width:96px"><span class="ig-corner">✨</span><img src="{pal0}"><span class="nm">冰龙</span></div>
      <div class="ig-palcard" style="width:96px"><img src="{pal1}"><span class="nm">羊毛狐</span></div>
      <div class="ig-palcard" style="width:96px"><img src="{pal2}"><span class="nm">粉红猫</span></div>
      <div style="flex:1;display:flex;flex-direction:column;gap:8px;padding-top:4px">
        <span class="ig-btn"><img src="{fps}" style="width:16px;height:16px">服务器 58 FPS</span>
        <span class="ig-btn"><img src="{up}" style="width:16px;height:16px">运行 3天8时</span>
        <span class="ig-pill" style="opacity:.85">↑ 插件扩展 SVG(游戏无此概念)</span></div></div></div>
  {foot}
</div>
"""


if __name__ == "__main__":
    raise SystemExit(main())
