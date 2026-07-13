"""ingame 主题基建测试(阶段B):三套主题键一致 / 模板可编译 / Asset Manifest / asset() 解析器。

- 不依赖 astrbot 运行时(assets 模块与 templates 常量均为纯 Python)。
- jinja2 缺失时跳过编译测试。
"""
import json
import os

import pytest

from astrbot_plugin_palworld.render import templates as T
from astrbot_plugin_palworld.render.assets import AssetResolver

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- 主题键一致
def test_three_themes_registered():
    assert set(T.STYLES) == {"fantasy", "pixel", "ingame"}


def test_three_themes_have_identical_keys():
    fk = set(T.STYLES["fantasy"])
    pk = set(T.STYLES["pixel"])
    ik = set(T.STYLES["ingame"])
    assert fk == pk, f"pixel 与 fantasy 键不一致: 缺 {fk - pk}, 多 {pk - fk}"
    assert fk == ik, f"ingame 与 fantasy 键不一致: 缺 {fk - ik}, 多 {ik - fk}"
    # 回归:补齐前 fantasy 56 / pixel 43;补齐后应一致且 >= 56
    assert len(fk) >= 56


def test_style_names_and_alias_cover_ingame():
    assert "ingame" in T.STYLE_NAMES
    assert T.STYLE_ALIAS.get("ingame") == "ingame"
    assert T.STYLE_ALIAS.get("游戏原生") == "ingame"


def test_conf_schema_lists_ingame():
    with open(os.path.join(_ROOT, "_conf_schema.json"), encoding="utf-8") as f:
        schema = json.load(f)
    assert "ingame" in schema["card_style"]["options"]


# ---------------------------------------------------------------- 模板可编译
def test_all_templates_compile():
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(autoescape=False)
    for style, cards in T.STYLES.items():
        for key, tmpl in cards.items():
            try:
                env.from_string(tmpl)
            except jinja2.exceptions.TemplateSyntaxError as e:  # noqa: PERF203
                pytest.fail(f"{style}.{key} 模板语法错误: {e}")


# ---------------------------------------------------------------- Asset Manifest
def _manifest():
    with open(os.path.join(_ROOT, "data", "ingame", "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def test_manifest_valid_and_files_exist():
    m = _manifest()
    base = os.path.join(_ROOT, "data", "ingame")
    verified = 0
    for ns, entries in m.items():
        if ns.startswith("_"):
            continue
        for k, v in entries.items():
            if k.startswith("_") or not isinstance(v, dict):
                continue
            rel = v.get("ingame")
            if rel:
                assert os.path.exists(os.path.join(base, rel)), f"{ns}.{k} 素材缺失: {rel}"
                verified += 1
    assert verified >= 45  # 已提取并绑定的真实图标数(回归下限)


def test_manifest_status_fields_valid():
    m = _manifest()
    allowed = set(m["_meta"]["status_values"])
    for ns, entries in m.items():
        if ns.startswith("_"):
            continue
        for k, v in entries.items():
            if k.startswith("_") or not isinstance(v, dict):
                continue
            assert v.get("status") in allowed, f"{ns}.{k} 非法 status={v.get('status')}"


# ---------------------------------------------------------------- asset() 解析器
def _resolver():
    return AssetResolver(_ROOT)


def test_resolver_fantasy_keeps_fallback_text():
    r = _resolver()
    # fallback 文字(Emoji)仍保留,供无游戏图标时回退
    assert r.text("element.fire", "fantasy") == "🔥"
    assert r.text("work.mining", "pixel") == "⛏️"


def test_game_icon_shared_across_all_themes():
    """新规则:游戏有原图的语义键,fantasy/pixel/ingame 三主题都返回同一张真实游戏图标(共享素材层)。"""
    r = _resolver()
    for key in ("element.fire", "work.mining", "work.emit_flame", "currency.gold", "pal.alpha", "pal.mutation"):
        for style in ("fantasy", "pixel", "ingame"):
            uri = r.img(key, style)
            assert uri.startswith("data:image/png;base64,"), f"{key}@{style} 应返回真实游戏图标,实为 {uri[:30]!r}"
        # game_icon() 是主题无关的共享入口
        assert r.game_icon(key).startswith("data:image/png;base64,")


def test_plugin_ext_still_per_theme():
    """插件扩展概念(游戏无图):ingame 用中性 SVG,fantasy/pixel 返回空串(模板回退 Emoji)。"""
    r = _resolver()
    assert r.img("server.cpu", "ingame").startswith("data:image/svg+xml")
    assert r.img("server.cpu", "fantasy") == "" and r.img("server.cpu", "pixel") == ""
    assert r.game_icon("server.cpu") == ""   # 非游戏图标


def test_resolver_ingame_returns_real_icon_data_uri():
    r = _resolver()
    uri = r.img("element.fire", "ingame")
    assert uri.startswith("data:image/png;base64,")
    # 工作图标同理
    assert r.img("work.mining", "ingame").startswith("data:image/png;base64,")


def test_resolver_plugin_key_alias():
    r = _resolver()
    # 插件内部键 element.火 / work.emit_flame 经 _plugin_key_map 归一到同一素材
    assert r.img("element.火", "ingame") == r.img("element.fire", "ingame")
    assert r.img("work.emit_flame", "ingame") == r.img("work.kindling", "ingame")


def test_resolver_missing_ingame_falls_back_to_placeholder_not_error():
    r = _resolver()
    # pending-extract(有键无图) → 统一缺失占位(stat.san 尚未提取到游戏图标)
    assert r.img("stat.san", "ingame") == r.missing_uri
    # 完全未知键 → 缺失占位,不抛异常
    assert r.img("totally.unknown", "ingame") == r.missing_uri
    # fallback 文字仍可取到
    assert r.text("stat.san", "fantasy") == "🧠"


def test_resolver_plugin_ext_svg():
    import base64
    r = _resolver()
    # 游戏无此语义的功能键 → 插件扩展 SVG(data URI),不是游戏图标、不报错
    uri = r.img("server.cpu", "ingame")
    assert uri.startswith("data:image/svg+xml;base64,")
    svg = base64.b64decode(uri.split(",", 1)[1]).decode("utf-8")
    assert svg.startswith("<svg") and "currentColor" not in svg  # 已替换为具体色
    # fantasy 下 server.cpu 无 emoji(文字标签)
    assert r.text("server.cpu", "fantasy") == ""


def test_all_plugin_ext_svgs_exist():
    m = _manifest()
    base = os.path.join(_ROOT, "data", "ingame")
    for k, v in m["plugin_ext"].items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        if v.get("status") == "plugin-ext":
            sv = v.get("plugin_svg")
            assert sv and os.path.exists(os.path.join(base, sv + ".svg")), f"{k} 缺 SVG: {sv}"


def test_ingame_css_renders_with_parts():
    jinja2 = pytest.importorskip("jinja2")
    r = _resolver()
    parts = r.component_uris()
    assert len(parts) >= 20
    # _IH(含 _INGAME_CSS)注入 parts 后应能编译渲染,不残留未解析变量
    env = jinja2.Environment(autoescape=False)
    out = env.from_string(T._IH).render(parts=parts, zoom=2, cw=540)
    assert "{{" not in out
    for token in ("--pal-gold", "border-image", "data:image/png;base64,"):
        assert token in out, f"ingame CSS 缺 {token}"


def test_component_textures_exist_and_resolve():
    m = _manifest()
    assert "component" in m, "manifest 缺 component 命名空间(UI 组件纹理)"
    base = os.path.join(_ROOT, "data", "ingame")
    r = _resolver()
    n = 0
    for k, v in m["component"].items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        rel = v.get("ingame")
        assert rel and os.path.exists(os.path.join(base, rel)), f"component.{k} 缺纹理: {rel}"
        assert r.img(f"component.{k}", "ingame").startswith("data:image/png;base64,")
        n += 1
    assert n >= 20  # 已提取的组件纹理数


def test_resolver_resolve_shape():
    r = _resolver()
    # 游戏语义键:三主题 resolve 的 img 都是真实游戏图标;text(Emoji 回退)仍在
    a = r.resolve("element.water", "ingame")
    assert a["img"].startswith("data:image/png;base64,")
    b = r.resolve("element.water", "fantasy")
    assert b["img"].startswith("data:image/png;base64,") and b["text"] == "💧"


# ------------------------------------------------- ingame 静态模板无未白名单 Emoji
def test_ingame_converted_templates_have_no_unwhitelisted_emoji():
    """已改造为 ingame 专属的模板不得含开发者预设 Emoji(游戏图标经 asset() 走图,不塞 Emoji)。
    白名单放行结构性符号(星级/箭头/分隔),不误伤。仍为 fantasy 临时回退的卡跳过(逐卡改造中)。"""
    import re
    # 真 Emoji 区间(排除下方白名单里的结构符)
    emoji_re = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF]")
    whitelist = set("★☆◈●○◆◇◢◣→←↑↓·✓✔▲▼▶◀■□♦♠")
    converted = [(k, t) for k, t in T.STYLES["ingame"].items() if t is not T.STYLES["fantasy"].get(k)]
    assert converted, "应至少有一张已改造的 ingame 卡(paldex)"
    for key, tmpl in converted:
        found = [c for c in emoji_re.findall(tmpl) if c not in whitelist]
        assert not found, f"ingame.{key} 含未替换 Emoji: {found}"
