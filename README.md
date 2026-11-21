# hatena-mt-md

はてなブログの公式エクスポート（**Movable Type / MT 形式**）を、記事ごとの
**Markdown ファイル**へ変換する CLI です。依存は **Python 標準ライブラリのみ**。

はてなブログから他のブログサービス・静的サイトジェネレータ（Hugo 等）・Obsidian へ
引っ越すとき、MT 形式のテキストはそのままでは使えず、移行のたびに使い捨ての
変換スクリプトを書いたり、テキストエディタで手作業の置換を繰り返したりするのが
通例になっています。本ツールはその変換を定型化します。

## できること

- **一括変換**: MT エクスポートファイルから、全記事を 1 記事＝1 Markdown ファイルに変換
- **frontmatter**: タイトル・公開日・カテゴリ・スラッグ（BASENAME）・著者・下書き状態を YAML で付与
- **HTML → Markdown 変換**: 見たままモード／HTML モードの本文を見出し・リンク・画像・リスト・引用・コードブロック等の Markdown に変換
- **はてなキーワードリンクの除去**: `<a class="keyword" ...>` はリンクを外し、語だけを残す（移行時の定番の落とし穴）
- **フォトライフ記法の変換**: `[f:id:user:YYYYMMDDHHMMSSp:plain]` を画像 Markdown に変換
- **Markdown モードの本文はそのまま**: HTML タグを含まない本文は変換せず通す
- **EXTENDED BODY（追記）** は本文の後ろへ連結。コメント・トラックバックは移行対象外として読み飛ばす
- **dry-run**: 書き込まずに変換見通しだけ確認できる

表（table）は Markdown への自動変換が崩れやすいため、HTML のまま保持します。

## 動作環境

- Python 3.10 以上（標準ライブラリのみで動作）

## インストール

```bash
pip install git+https://github.com/dgtlchika/hatena-mt-md
```

clone して直接実行もできます（依存ゼロ）。

```bash
git clone https://github.com/dgtlchika/hatena-mt-md
cd hatena-mt-md
python3 hatena_mt_md.py hatena.export.txt --out ./posts
```

## 使い方

はてなブログの「設定 → 詳細設定 → 記事のバックアップとエクスポート」から
ダウンロードしたファイルを用意します。

```bash
# 基本
hatena-mt-md hatena.export.txt --out ./posts

# まず見通しだけ確認
hatena-mt-md hatena.export.txt --out ./posts --dry-run
```

出力ファイル名は BASENAME から生成します（例: `2026/11/20/1234567890` → `2026-11-20-1234567890.md`）。

出力例:

```markdown
---
title: テスト記事1
date: 2026-11-20T10:30:00
categories: [テスト, 日記]
slug: 2026/11/20/1234567890
author: testuser
draft: false
---

最初の段落です。テストキーワードリンクを含みます。

### 見出しです

- 項目1
- 項目2
```

## 制限

- 画像ファイル自体のダウンロードはしません（フォトライフ記法は CDN の URL に変換、HTML 内の画像は元の URL のまま）
- はてな記法モードの本文は、フォトライフ記法の変換を除き、そのまま出力します
- 複雑な HTML（入れ子の表、独自クラス付きブロック等）は完全には再現できません。表は HTML のまま保持します
- 埋め込み（YouTube 等の iframe）は変換対象外で、HTML 本文の場合は要素が落ちることがあります

## テスト

```bash
python3 -m pytest tests/
```

## ライセンス

MIT

---

## 作者について

このツールは「デジタル地下室」が、自分のブログ運用で実際に困ったことを解消するために作ったものです。同じ困りごとの解説や、作った過程は note に書いています。

- note（デジタル地下室）: https://note.com/sumaho_lab
- X: https://x.com/dgtl_chika
- GitHub: https://github.com/dgtlchika

不具合報告・要望は Issue へどうぞ。確認して対応します。
