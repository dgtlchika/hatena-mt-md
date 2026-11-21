import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hatena_mt_md import (  # noqa: E402
    convert_file,
    entry_to_markdown,
    fotolife_to_image,
    html_to_md,
    parse_mt,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.export.txt"


def load_entries():
    return parse_mt(FIXTURE.read_text(encoding="utf-8"))


def test_parse_two_entries():
    entries = load_entries()
    assert len(entries) == 2
    e1 = entries[0]
    assert e1.title == "テスト記事1"
    assert e1.basename == "2026/11/20/1234567890"
    assert e1.status == "Publish"
    assert e1.categories == ["テスト", "日記"]
    assert e1.date is not None and e1.date.year == 2026 and e1.date.month == 11
    # コメントセクションは本文に混入しない
    assert "コメント本文" not in e1.body


def test_html_body_conversion():
    md = entry_to_markdown(load_entries()[0])
    assert "### 見出しです" in md
    assert "- 項目1" in md
    assert "[外部リンク](https://example.com/)" in md
    assert "**太字**" in md
    assert 'print("hello")' in md
    # はてなキーワードリンクは外れ、語だけが残る
    assert "d.hatena.ne.jp/keyword" not in md
    assert "テストキーワードリンク" in md
    # 追記が本文の後ろに付く
    assert "追記の段落です" in md
    # frontmatter
    assert "title: テスト記事1" in md
    assert "date: 2026-11-20T10:30:00" in md
    assert "draft: false" in md


def test_markdown_body_and_fotolife():
    md = entry_to_markdown(load_entries()[1])
    assert "draft: true" in md
    assert "## Markdown見出し" in md
    expected = "https://cdn-ak.f.st-hatena.com/images/fotolife/t/testuser/20261121/20261121090000.jpg"
    assert f"![]({expected})" in md


def test_fotolife_regex():
    out = fotolife_to_image("[f:id:abc:20260102030405j:plain]")
    assert out.startswith("![](https://cdn-ak.f.st-hatena.com/images/fotolife/a/abc/20260102/20260102030405.jpg)")


def test_html_to_md_table_passthrough():
    md = html_to_md("<p>前</p><table><tr><td>セル</td></tr></table><p>後</p>")
    assert "<table>" in md and "セル" in md


def test_convert_file_writes(tmp_path):
    out = tmp_path / "posts"
    written, total = convert_file(FIXTURE, out)
    assert (written, total) == (2, 2)
    files = sorted(p.name for p in out.glob("*.md"))
    assert files == ["2026-11-20-1234567890.md", "2026-11-21-1234567891.md"]
