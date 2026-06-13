import html
import re

from bs4 import BeautifulSoup


WHITESPACE_RE = re.compile(r"\s+")
INLINE_MATH_RE = re.compile(r"\$[^$]+\$")
LATEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\{[^}]*\}")
INVISIBLE_RE = re.compile(r"[\u200b-\u200f\u2060\ufeff]")


def clean_title(value: str, max_length: int = 500) -> str:
    unescaped = html.unescape(value or "")
    plain = (
        BeautifulSoup(unescaped, "html.parser").get_text(" ", strip=True)
        if "<" in unescaped
        else unescaped
    )
    return WHITESPACE_RE.sub(" ", plain).strip()[:max_length]


def clean_body(value: str | None, max_length: int = 8000) -> str:
    if not value:
        return ""
    plain = (
        BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        if "<" in value
        else value
    )
    unescaped = INVISIBLE_RE.sub("", html.unescape(plain))
    return WHITESPACE_RE.sub(" ", unescaped).strip()[:max_length]


def strip_latex(value: str) -> str:
    without_math = INLINE_MATH_RE.sub("", value)
    without_commands = LATEX_COMMAND_RE.sub("", without_math)
    return without_commands.replace("$", "")


def clean_llm_text(value: str | None, max_length: int) -> str:
    cleaned = strip_latex(clean_body(value, max_length))
    return cleaned.encode("utf-8", errors="ignore").decode("utf-8")
