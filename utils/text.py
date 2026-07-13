"""可复用纯文本工具：HTML 转义、帕鲁蛋名翻译。
从 main.py 原样迁出，逻辑未改（重构第一阶段）。"""
from __future__ import annotations

import html as _html
import re as _re
import unicodedata as _ud

# 零宽/BOM 字符(U+200B/C/D、U+2060、U+FEFF)
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
# UE 本地化语义引用 <itemName id=|X|/>(也兼容 <ItemName id="X"/> 等写法)
_ITEMNAME = _re.compile(r"<\s*itemName\s+id=[|\"']?([^|\"'>]+)[|\"']?\s*/?>", _re.I)
# UE RichText 纯样式标签 <xxx ...> / </...>(itemName 先解析,这里只清剩余样式标签)
_UE_TAG = _re.compile(r"</?[a-zA-Z][^<>]*?>")
# 占位/缺失文本(视为空):zh-hans text / zh_Hans_Text / None 等
_PLACEHOLDER = {"zh-hans text", "zh_hans_text", "none", "null", ""}


def is_missing_text(s) -> bool:
    """判断是否为缺失/占位文本(zh-hans text / None / 空)。"""
    return (str(s).strip().lower() if s is not None else "") in _PLACEHOLDER


def clean_text(s, resolve=None) -> str:
    """统一清洗游戏数据里的用户可见文本(替代各 handler 各自 replace)。

    - `<itemName id=|X|/>` 等语义引用 -> `resolve(X)`(可选,如 item_id->中文名);解析不到则去除,不显示原始标签。
    - 去 UE RichText 纯样式标签(保留其中文字)。
    - 统一 CRLF/CR -> LF;去零宽字符与控制字符(保留换行)。
    - 占位值("zh-hans text"/"None" 等)视为空,返回 ""。
    - **不删除 Emoji**(Emoji 是 So 类,非控制字符);本函数只用于游戏数据文本,不处理玩家昵称/公告/聊天。
    """
    if s is None:
        return ""
    s = str(s)

    def _resolve_itemname(m):
        rid = m.group(1)
        if resolve:
            v = resolve(rid)
            if v:
                return str(v)
        return ""

    s = _ITEMNAME.sub(_resolve_itemname, s)
    s = _UE_TAG.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n").translate(_ZERO_WIDTH)
    s = "".join(ch for ch in s if ch == "\n" or _ud.category(ch)[0] != "C")
    if is_missing_text(s):
        return ""
    return s.strip()


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
