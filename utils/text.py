"""可复用纯文本工具：HTML 转义、帕鲁蛋名翻译。
从 main.py 原样迁出，逻辑未改（重构第一阶段）。"""
from __future__ import annotations

import html as _html


# 帕鲁蛋名翻译（尺寸前缀 + 属性类型，覆盖所有组合）
_EGG_SIZE = {"Large": "大型", "Huge": "巨型", "Mega": "超巨型"}
_EGG_TYPE = {"Common": "普通", "Damp": "湿润", "Verdant": "青翠", "Scorching": "灼热",
             "Frozen": "冰冻", "Electric": "电气", "Rocky": "岩石", "Dark": "暗黑", "Dragon": "龙",
             "Uncommon": "优质", "Rare": "稀有", "Epic": "史诗", "Legendary": "传说"}


def _esc(s):
    """把玩家/群友可控字符串转义后再放进 HTML 卡片模板（Jinja autoescape 关闭，
    模板里有大量故意内嵌的 HTML，不能开全局转义，只能对不可信字段逐个转义）。
    防止把昵称/公会名/喊话等改成 <img onerror=...> 在渲染宿主机执行脚本。
    对正常文本（中文/emoji）无副作用。"""
    return _html.escape(str(s)) if s is not None else ""


def egg_to_cn(egg: str) -> str:
    """把英文蛋名(如 Large Scorching Egg)译成中文(大型灼热蛋)。"""
    if not egg:
        return ""
    parts = egg.replace(" Egg", "").replace("Egg", "").split()
    size = ""
    if parts and parts[0] in _EGG_SIZE:
        size = _EGG_SIZE[parts[0]]
        parts = parts[1:]
    typ = _EGG_TYPE.get(parts[0], parts[0]) if parts else ""
    return f"{size}{typ}蛋"
