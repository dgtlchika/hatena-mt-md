#!/usr/bin/env python3
"""hatena-mt-md: はてなブログの MT 形式エクスポートを Markdown へ変換する CLI。

はてなブログの公式エクスポートは Movable Type (MT) 形式のテキストで、
そのままでは他のブログ／Obsidian／静的サイトジェネレータへ持ち込めない。
本ツールは MT ファイルを読み、1記事＝1 Markdown ファイル（YAML frontmatter 付き）
へ変換する。依存は Python 標準ライブラリのみ。

使い方:
    python3 hatena_mt_md.py hatena.export.txt --out ./posts
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

ENTRY_SEP = "--------"
SECTION_SEP = "-----"

# ---------------------------------------------------------------------------
# MT 形式のパース
# ---------------------------------------------------------------------------


@dataclass
class Entry:
    author: str = ""
    title: str = ""
    basename: str = ""
    status: str = "Publish"
    date: datetime | None = None
    categories: list[str] = field(default_factory=list)
    body: str = ""
    extended_body: str = ""
    meta: dict[str, str] = field(default_factory=dict)


def _parse_meta_block(block: str, entry: Entry) -> None:
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().upper()
        value = value.strip()
        if key == "CATEGORY":
            if value:
                entry.categories.append(value)
        elif key == "TITLE":
            entry.title = value
        elif key == "AUTHOR":
            entry.author = value
        elif key == "BASENAME":
            entry.basename = value
        elif key == "STATUS":
            entry.status = value
        elif key == "DATE":
            for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
                try:
                    entry.date = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
        entry.meta[key] = value


def parse_mt(text: str) -> list[Entry]:
    """MT エクスポート文字列を Entry のリストにする。"""
    entries: list[Entry] = []
    raw_entries = re.split(r"^--------\s*$", text, flags=re.MULTILINE)
    for raw in raw_entries:
        raw = raw.strip("\r\n")
        if not raw.strip():
            continue
        sections = re.split(r"^-----\s*$", raw, flags=re.MULTILINE)
        entry = Entry()
        _parse_meta_block(sections[0], entry)
        for section in sections[1:]:
            stripped = section.strip("\r\n")
            if stripped.startswith("BODY:"):
                entry.body = stripped[len("BODY:") :].strip("\r\n")
            elif stripped.startswith("EXTENDED BODY:"):
                entry.extended_body = stripped[len("EXTENDED BODY:") :].strip("\r\n")
            # COMMENT: / PING: セクションは移行対象外として読み飛ばす
        if entry.title or entry.body:
            entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# HTML → Markdown 変換（標準ライブラリのみの軽量変換）
# ---------------------------------------------------------------------------

_BLOCK_TAGS = {
    "p", "div", "section", "article", "figure", "figcaption",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "blockquote", "pre", "table", "hr",
}
_DROP_CONTENT_TAGS = {"script", "style"}


class _HTMLToMD(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._link_stack: list[str | None] = []
        self._list_stack: list[str] = []
        self._in_pre = 0
        self._pre_lang = ""
        self._drop_depth = 0
        self._in_table = 0
        self._table_html: list[str] = []

    # -- helpers ---------------------------------------------------------
    def _emit(self, s: str) -> None:
        if self._in_table:
            self._table_html.append(s)
        else:
            self.out.append(s)

    def _newline_if_needed(self) -> None:
        text = "".join(self._table_html if self._in_table else self.out)
        if text and not text.endswith("\n"):
            self._emit("\n")

    # -- parser callbacks -------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return
        if tag == "table":
            self._in_table += 1
            if self._in_table == 1:
                self._newline_if_needed()
                self._table_html = []
            self._table_html.append(self.get_starttag_text() or "<table>")
            return
        if self._in_table:
            self._table_html.append(self.get_starttag_text() or f"<{tag}>")
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._newline_if_needed()
            self._emit("\n" + "#" * int(tag[1]) + " ")
        elif tag == "p":
            self._newline_if_needed()
            self._emit("\n")
        elif tag == "br":
            self._emit("  \n")
        elif tag == "hr":
            self._newline_if_needed()
            self._emit("\n---\n")
        elif tag == "a":
            # はてなキーワードリンクはリンクを外して本文だけ残す
            classes = (attr.get("class") or "").split()
            href = attr.get("href") or ""
            if "keyword" in classes or "d.hatena.ne.jp/keyword/" in href:
                self._link_stack.append(None)
            else:
                self._link_stack.append(href)
                self._emit("[")
        elif tag == "img":
            src = attr.get("src") or ""
            alt = attr.get("alt") or ""
            if src:
                self._newline_if_needed()
                self._emit(f"\n![{alt}]({src})\n")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "code":
            if not self._in_pre:
                self._emit("`")
        elif tag == "pre":
            self._in_pre += 1
            self._newline_if_needed()
            self._emit("\n```\n")
        elif tag == "blockquote":
            self._newline_if_needed()
            self._emit("\n> ")
        elif tag in ("ul", "ol"):
            self._list_stack.append(tag)
            self._newline_if_needed()
        elif tag == "li":
            self._newline_if_needed()
            depth = max(0, len(self._list_stack) - 1)
            marker = "1." if self._list_stack and self._list_stack[-1] == "ol" else "-"
            self._emit("  " * depth + marker + " ")
        elif tag in ("div", "section", "article", "figure"):
            self._newline_if_needed()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.handle_starttag(tag, attrs)
        elif tag == "br":
            self._emit("  \n")
        elif tag == "hr":
            self._newline_if_needed()
            self._emit("\n---\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._drop_depth:
            return
        if tag == "table":
            self._in_table -= 1
            if self._in_table == 0:
                table_html = "".join(self._table_html).strip()
                self.out.append("\n" + table_html + "\n")
                self._table_html = []
            else:
                self._table_html.append("</table>")
            return
        if self._in_table:
            self._table_html.append(f"</{tag}>")
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p"):
            self._emit("\n")
        elif tag == "a":
            href = self._link_stack.pop() if self._link_stack else None
            if href is not None:
                self._emit(f"]({href})")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "code":
            if not self._in_pre:
                self._emit("`")
        elif tag == "pre":
            self._in_pre = max(0, self._in_pre - 1)
            self._emit("\n```\n")
        elif tag == "blockquote":
            self._emit("\n")
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._emit("\n")

    def handle_data(self, data: str) -> None:
        if self._drop_depth:
            return
        if self._in_table:
            self._table_html.append(html.escape(data) if "<" in data else data)
            return
        if self._in_pre:
            self._emit(data)
        else:
            self._emit(re.sub(r"\s+", " ", data))

    def result(self) -> str:
        text = "".join(self.out)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def html_to_md(html_text: str) -> str:
    parser = _HTMLToMD()
    parser.feed(html_text)
    parser.close()
    return parser.result()


# ---------------------------------------------------------------------------
# はてな記法（テキスト本文）の軽処理
# ---------------------------------------------------------------------------

_FOTOLIFE_RE = re.compile(
    r"\[f:id:([A-Za-z0-9_-]+):(\d{14})[a-z](?::plain)?(?::image)?\]"
)


def fotolife_to_image(text: str) -> str:
    """[f:id:user:YYYYMMDDHHMMSSp:plain] を画像 Markdown に変換する。"""

    def repl(m: re.Match[str]) -> str:
        user, ts = m.group(1), m.group(2)
        url = (
            f"https://cdn-ak.f.st-hatena.com/images/fotolife/"
            f"{user[0]}/{user}/{ts[:8]}/{ts}.jpg"
        )
        return f"![]({url})"

    return _FOTOLIFE_RE.sub(repl, text)


def looks_like_html(body: str) -> bool:
    return bool(re.search(r"<(p|div|h[1-6]|ul|ol|blockquote|pre|table|img|a)\b", body))


# ---------------------------------------------------------------------------
# 出力
# ---------------------------------------------------------------------------


def yaml_escape(value: str) -> str:
    if re.search(r'[:#\[\]{}",&*?<>|%@`]|^\s|\s$', value) or value == "":
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def entry_to_markdown(entry: Entry) -> str:
    lines: list[str] = ["---"]
    lines.append(f"title: {yaml_escape(entry.title)}")
    if entry.date:
        lines.append(f"date: {entry.date.strftime('%Y-%m-%dT%H:%M:%S')}")
    if entry.categories:
        cats = ", ".join(yaml_escape(c) for c in entry.categories)
        lines.append(f"categories: [{cats}]")
    if entry.basename:
        lines.append(f"slug: {yaml_escape(entry.basename)}")
    if entry.author:
        lines.append(f"author: {yaml_escape(entry.author)}")
    lines.append(f"draft: {'true' if entry.status.lower() != 'publish' else 'false'}")
    lines.append("---")
    lines.append("")

    body = entry.body
    if entry.extended_body:
        body = body + "\n\n" + entry.extended_body if body else entry.extended_body
    body = fotolife_to_image(body)
    if looks_like_html(body):
        body = html_to_md(body)
    lines.append(body.strip())
    lines.append("")
    return "\n".join(lines)


def output_filename(entry: Entry, used: set[str]) -> str:
    if entry.basename:
        base = entry.basename.replace("/", "-")
    elif entry.date:
        base = entry.date.strftime("%Y-%m-%d")
    else:
        base = "entry"
    name = re.sub(r"[\\/:*?\"<>|]", "-", base) + ".md"
    candidate = name
    n = 2
    while candidate in used:
        candidate = name[:-3] + f"-{n}.md"
        n += 1
    used.add(candidate)
    return candidate


def convert_file(input_path: Path, out_dir: Path, dry_run: bool = False) -> tuple[int, int]:
    text = input_path.read_text(encoding="utf-8", errors="replace")
    entries = parse_mt(text)
    used: set[str] = set()
    written = 0
    for entry in entries:
        name = output_filename(entry, used)
        md = entry_to_markdown(entry)
        if dry_run:
            print(f"[dry-run] {name}（{entry.title}）")
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / name).write_text(md, encoding="utf-8")
            print(f"変換: {name}（{entry.title}）")
        written += 1
    return written, len(entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hatena-mt-md",
        description="はてなブログの MT 形式エクスポートを記事ごとの Markdown へ変換する",
    )
    parser.add_argument("input", help="MT 形式エクスポートファイル（.txt）")
    parser.add_argument("--out", "-o", default="./posts", help="出力ディレクトリ（既定: ./posts）")
    parser.add_argument("--dry-run", action="store_true", help="書き込まず変換見通しだけ表示")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"入力ファイルがありません: {in_path}", file=sys.stderr)
        return 1
    written, total = convert_file(in_path, Path(args.out), dry_run=args.dry_run)
    print(f"完了: {written}件を変換しました（検出 {total}件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
