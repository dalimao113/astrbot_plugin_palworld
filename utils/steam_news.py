"""Steam 帕鲁公告的官方本地化正文解析与长文本分段。"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from typing import Optional


PALWORLD_APP_ID = 1623730
_LONG_ID_RE = re.compile(r"(?<!\d)(\d{10,})(?!\d)")
_CJK_RE = re.compile(r"[\u3400-\u9fff]")


def announcement_id_from_url(source_url: str) -> Optional[str]:
    """从 Steam News 返回的外链中提取公告数字 ID。"""
    ids = _LONG_ID_RE.findall(str(source_url or ""))
    return ids[-1] if ids else None


def localized_announcement_url(source_url: str, language: str = "schinese") -> Optional[str]:
    """把 Steam News 外链规范化为固定域名的官方本地化详情页。"""
    announcement_id = announcement_id_from_url(source_url)
    if not announcement_id:
        return None
    return (
        f"https://steamcommunity.com/ogg/{PALWORLD_APP_ID}/announcements/"
        f"detail/{announcement_id}?l={language}"
    )


def _html_attribute(page: str, name: str) -> Optional[str]:
    match = re.search(
        rf"\b{re.escape(name)}=(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
        str(page or ""),
        flags=re.DOTALL,
    )
    if not match:
        return None
    return html.unescape(match.group("value"))


def _json_attribute(page: str, name: str):
    raw = _html_attribute(page, name)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def bbcode_to_text(raw: str) -> str:
    """把 Steam 公告 BBCode 转成适合 QQ 阅读的纯文本，保留正文与文本链接。"""
    value = html.unescape(str(raw or "")).replace("\r\n", "\n").replace("\r", "\n")

    # 图片由 Steam 页面负责展示；纯文字公告保留所有改动条目，但不发送大量截图链接。
    value = re.sub(r"\[img(?:[^\]]*)\].*?\[/img\]", "", value, flags=re.IGNORECASE | re.DOTALL)

    def youtube_repl(match: re.Match) -> str:
        video_id = (match.group(1) or "").split(";", 1)[0].strip()
        return f"\nhttps://www.youtube.com/watch?v={video_id}\n" if video_id else "\n"

    value = re.sub(
        r"\[previewyoutube=[\"']?([^\"'\]]+)[\"']?\](?:\[/previewyoutube\])?",
        youtube_repl,
        value,
        flags=re.IGNORECASE,
    )

    def url_repl(match: re.Match) -> str:
        href = (match.group(1) or match.group(2) or "").strip().strip("\"'")
        label = (match.group(3) or "").strip()
        if not href:
            return label
        if not label or label == href:
            return href
        return f"{label}（{href}）"

    value = re.sub(
        r"\[url(?:=(?:[\"']([^\"']+)[\"']|([^\]]+)))?\](.*?)\[/url\]",
        url_repl,
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )

    value = re.sub(r"\[hr[^\]]*\](?:\[/hr\])?", "\n────────\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\[\*\]", "\n• ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[/?(?:list|olist)[^\]]*\]", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\[/?tr[^\]]*\]", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\[/td\]", " | ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[td[^\]]*\]", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\[/?table[^\]]*\]", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\[(?:p|h[1-6]|quote)[^\]]*\]", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\[/(?:p|h[1-6]|quote)\]", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\[br\s*/?\]", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"\[/?[a-z][^\]]*\]", "", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).replace("\u200b", "").replace("\ufeff", "")
    value = "".join(
        char for char in value
        if char in "\n\t" or unicodedata.category(char)[0] != "C"
    )

    lines: list[str] = []
    for raw_line in value.splitlines():
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if line:
            lines.append(line)
        elif lines and lines[-1] != "":
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).strip()


def parse_localized_announcement_page(page: str) -> Optional[dict[str, str]]:
    """解析 Steam 详情页内嵌事件 JSON，只返回当前落地公告的官方简体中文正文。"""
    landing = _json_attribute(page, "data-eventinfinitescrolllanding")
    events = _json_attribute(page, "data-partnereventstore")
    if not landing or not isinstance(events, list):
        return None

    landing = str(landing)
    for event in events:
        if not isinstance(event, dict):
            continue
        body = event.get("announcement_body")
        if not isinstance(body, dict) or str(body.get("gid", "")) != landing:
            continue
        language = body.get("language")
        title = html.unescape(str(body.get("headline", "") or "")).strip()
        text = bbcode_to_text(body.get("body", ""))
        # Steam language=6 是简体中文；旧页面缺字段时用实际中文字符作兼容判断。
        if language not in (None, 6, "6") or not _CJK_RE.search(f"{title}\n{text}"):
            return None
        if not title or not text:
            return None
        return {"title": title, "text": text, "announcement_gid": landing}
    return None


def split_long_text(text: str, max_chars: int = 2800) -> list[str]:
    """按段落/换行/句号分块，不丢正文，供 QQ 合并转发节点使用。"""
    if max_chars < 200:
        raise ValueError("max_chars 不能小于 200")
    remaining = str(text or "").strip()
    chunks: list[str] = []
    while len(remaining) > max_chars:
        cut = 0
        delimiter_len = 0
        for delimiter in ("\n\n", "\n", "。", "；"):
            pos = remaining.rfind(delimiter, max_chars // 2, max_chars + 1)
            if pos > cut:
                cut = pos
                delimiter_len = len(delimiter)
        if cut <= 0:
            cut = max_chars
            delimiter_len = 0
        else:
            cut += delimiter_len
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
