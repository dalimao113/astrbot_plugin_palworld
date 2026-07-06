"""纯文本工具 + main.py 配置字面量防漂移。"""
import ast
import pathlib

from astrbot_plugin_palworld import config
from astrbot_plugin_palworld.utils import text

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_esc_escapes_html():
    assert text._esc('<img onerror=x>&"') == "&lt;img onerror=x&gt;&amp;&quot;"
    assert text._esc(None) == ""


def test_egg_to_cn():
    assert text.egg_to_cn("Large Scorching Egg") == "大型灼热蛋"
    assert text.egg_to_cn("Huge Dragon Egg") == "巨型龙蛋"
    assert text.egg_to_cn("") == ""


def test_config_get_literals_match_defaults():
    """扫描 main.py 中 self.config.get(key, 字面量)，字面量必须等于 DEFAULTS[key]。

    这是任务四的防漂移护栏：确保散落的取值默认值不与规范来源 config.DEFAULTS 背离。
    """
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    mismatches = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"):
            continue
        recv = node.func.value
        if not (isinstance(recv, ast.Attribute) and recv.attr == "config"):
            continue
        if len(node.args) < 2:
            continue
        key_node, default_node = node.args[0], node.args[1]
        if not (isinstance(key_node, ast.Constant) and isinstance(default_node, ast.Constant)):
            continue
        key, default = key_node.value, default_node.value
        if key in config.DEFAULTS and config.DEFAULTS[key] != default:
            mismatches.append((key, default, config.DEFAULTS[key]))
    assert not mismatches, f"main.py config.get 字面量与 DEFAULTS 不一致: {mismatches}"
