from __future__ import annotations

from html import escape
import re
from typing import Any


_WIKI_TYPE_NAMES = {
    "wiki",
    "wikitext",
    "wikitextfield",
    "wikitextfieldvalue",
}
_STYLE_OPEN_RE = re.compile(
    r"%%\((?P<style>(?:[^()]|\([^()]*\)){1,1000})\)"
)
_NAMED_STYLE_OPEN_RE = re.compile(r"%%(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*")
_SAFE_STYLE_NAMES = {
    "background-color",
    "color",
    "font-size",
    "font-style",
    "font-weight",
    "text-decoration",
}
_SAFE_COLOR_RE = re.compile(
    r"(?:#[0-9a-fA-F]{3,8}|[A-Za-z]{1,24}|rgba?\([0-9.,%\s]+\))\Z"
)
_SAFE_SIZE_RE = re.compile(r"(?:\d+(?:\.\d+)?(?:px|pt|em|rem|%)|small|medium|large)\Z")
_SAFE_WEIGHT_RE = re.compile(r"(?:normal|bold|bolder|lighter|[1-9]00)\Z")
_SAFE_FONT_STYLE_RE = re.compile(r"(?:normal|italic|oblique)\Z")
_SAFE_DECORATION_RE = re.compile(
    r"(?:none|underline|line-through|underline line-through|line-through underline)\Z"
)
_THEME_FOREGROUND_COLORS = {
    "black",
    "white",
    "#000",
    "#000000",
    "#fff",
    "#ffffff",
}
_NAMED_COLOR_STYLES = {
    "black",
    "blue",
    "cyan",
    "gray",
    "green",
    "magenta",
    "orange",
    "pink",
    "red",
    "white",
    "yellow",
}


def _normalized_type_name(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if "<" in text:
        text = text.split("<", 1)[0].strip()
    return text.replace("_", "").replace("-", "")


def is_explicit_wiki_type(value: Any) -> bool:
    """메타데이터가 Wiki 형식을 명시한 경우만 참을 반환한다."""
    return _normalized_type_name(value) in _WIKI_TYPE_NAMES


def payload_uses_wiki(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    return any(
        is_explicit_wiki_type(payload.get(key))
        for key in ("type", "valueModel", "format", "descriptionFormat")
    )


def _safe_style_value(name: str, value: str) -> str | None:
    normalized = value.strip().casefold()
    blocked_tokens = ("url(", "expression", "javascript")
    if not normalized or any(token in normalized for token in blocked_tokens):
        return None
    if name in {"color", "background-color"}:
        if not _SAFE_COLOR_RE.fullmatch(normalized):
            return None
        if name == "color" and normalized in _THEME_FOREGROUND_COLORS:
            return None
        return normalized
    if name == "font-size" and _SAFE_SIZE_RE.fullmatch(normalized):
        return normalized
    if name == "font-weight" and _SAFE_WEIGHT_RE.fullmatch(normalized):
        return normalized
    if name == "font-style" and _SAFE_FONT_STYLE_RE.fullmatch(normalized):
        return normalized
    if name == "text-decoration" and _SAFE_DECORATION_RE.fullmatch(normalized):
        return normalized
    return None


def sanitize_wiki_style(style: str) -> str:
    declarations: list[str] = []
    for declaration in str(style or "").split(";"):
        if ":" not in declaration:
            continue
        raw_name, raw_value = declaration.split(":", 1)
        name = raw_name.strip().casefold()
        if name not in _SAFE_STYLE_NAMES:
            continue
        value = _safe_style_value(name, raw_value)
        if value is not None:
            declarations.append(f"{name}: {value}")
    return "; ".join(declarations)


def _render_basic_markup(text: str) -> str:
    rendered = escape(text, quote=False)
    rendered = re.sub(r"__([^_\n]+?)__", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"''([^'\n]+?)''", r"<em>\1</em>", rendered)
    rendered = re.sub(r"\{\{([^{}\n]+?)\}\}", r"<code>\1</code>", rendered)
    return rendered.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _closing_index(source: str, start: int) -> tuple[int, int] | None:
    candidates = [
        (index, len(token))
        for token in ("%%", "%!")
        if (index := source.find(token, start)) >= 0
    ]
    return min(candidates) if candidates else None


def codebeamer_wiki_to_html(value: Any) -> str:
    """안전한 Codebeamer Wiki 스타일 일부를 Qt rich text용 HTML로 바꾼다."""
    source = str(value or "")
    parts: list[str] = []
    position = 0
    while position < len(source):
        style_match = _STYLE_OPEN_RE.search(source, position)
        named_match = _NAMED_STYLE_OPEN_RE.search(source, position)
        matches = [match for match in (style_match, named_match) if match is not None]
        if not matches:
            parts.append(_render_basic_markup(source[position:]))
            break
        opening = min(matches, key=lambda match: match.start())
        parts.append(_render_basic_markup(source[position : opening.start()]))
        closing = _closing_index(source, opening.end())
        if closing is None:
            parts.append(_render_basic_markup(source[opening.start() :]))
            break
        closing_position, closing_length = closing
        content = _render_basic_markup(source[opening.end() : closing_position])
        if opening.re is _STYLE_OPEN_RE:
            style = sanitize_wiki_style(opening.group("style"))
        else:
            name = opening.group("name").casefold()
            style = f"color: {name}" if name in _NAMED_COLOR_STYLES else ""
            if name in _THEME_FOREGROUND_COLORS:
                style = ""
        parts.append(f'<span style="{style}">{content}</span>' if style else content)
        position = closing_position + closing_length
    return "".join(parts)


__all__ = [
    "codebeamer_wiki_to_html",
    "is_explicit_wiki_type",
    "payload_uses_wiki",
    "sanitize_wiki_style",
]
