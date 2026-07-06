"""渲染引擎：data 组装、图片/兜底、Jinja autoescape 关闭（需 stub；jinja 测试可选）。"""
import asyncio

import pytest

import astrbot_plugin_palworld.main as main
from astrbot_plugin_palworld.render.renderer import Renderer

P = main.PalworldPlugin


class Ev:
    def image_result(self, url):
        return ("IMG", url)

    def plain_result(self, txt):
        return ("TXT", txt)


def _mk(ret="http://img/x.png"):
    o = P.__new__(P)
    o.config = {"local_render": False}
    o._theme = lambda: "#111"
    o._bg_for = lambda t: "BGDATA"
    o._t = lambda k: f"T:{k}"
    calls = []

    async def hr(tmpl, data, options=None):
        calls.append((tmpl, dict(data), options))
        return ret
    o.html_render = hr
    o._renderer = Renderer(o)
    return o, calls


def test_render_injects_common_fields():
    o, calls = _mk()
    r = asyncio.run(o._render("T:status", {"foo": 1}))
    assert r == "http://img/x.png"
    _, data, _ = calls[-1]
    assert data["theme"] == "#111"
    assert data["bg"] == "BGDATA"
    assert data["foo"] == 1
    assert "now" in data and "zoom" in data and "cw" in data


def test_img_success_and_fallback():
    o, _ = _mk()
    assert asyncio.run(o._img(Ev(), "T:x", {})) == ("IMG", "http://img/x.png")
    o, _ = _mk(ret=None)
    assert asyncio.run(o._img(Ev(), "T:x", {}))[0] == "TXT"


def test_msg_card_composition():
    o, calls = _mk()
    asyncio.run(o._msg_card(Ev(), "🔔", "标题", "描述"))
    tmpl, data, _ = calls[-1]
    assert tmpl == "T:message"
    assert data["icon"] == "🔔" and data["title"] == "标题" and data["color"] == "#111"


def test_jinja_autoescape_disabled():
    pytest.importorskip("jinja2")
    o, _ = _mk()
    # autoescape 故意关闭：不自动转义（转义由调用方 _esc 负责）
    assert o._renderer.jinja("{{x}}").render(x="<b>&") == "<b>&"
