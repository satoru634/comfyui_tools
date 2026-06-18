# captioning_tool

指定ディレクトリ内の画像ファイルを WD Timm Tagger（ComfyUI）でタグ付けし、
各画像と同名の `.txt` キャプションファイルをバッチ生成するツールです。

LoRA 学習用データセットのキャプションファイル整備を主な用途として想定しています。

**✨ English version is [here](./doc/README_english.md).**

## 機能

- ディレクトリ内の画像を一括タグ付け（対応拡張子: `.jpg` `.jpeg` `.png` `.webp`）
- 既存の `.txt` ファイルはデフォルトでスキップ（`--overwrite` で上書き）
- サブディレクトリの再帰処理（`--recursive`）
- 冒頭追記タグ（トリガーワードなど）の付与（`--prepend`）
- 不要タグの除去（`--exclude`）
- タグ集計レポートの生成（`--report`）

## 必要環境

- Python 3.12+
- 起動済みの ComfyUI（デフォルト: `http://127.0.0.1:8188`）
- ComfyUI カスタムノード: [ComfyUI-WD-Timm-Tagger](https://github.com/bedovyy/ComfyUI-WD-Timm-Tagger)

## セットアップ

リポジトリルートの[セットアップ](../README.md#セットアップ)を参照してください。

## 設定

**`config.json`** — ComfyUI の接続先・WD14 Tagger 設定・デフォルトタグを記述します。

```json
{
  "comfyui_url": "http://127.0.0.1:8188",
  "wd14_tagger": {
    "model_name": "wd-eva02-large-tagger-v3",
    "general_threshold": 0.35,
    "character_threshold": 0.85
  },
  "prepend_tags": [],
  "exclude_tags": []
}
```

| キー | 説明 |
|---|---|
| `comfyui_url` | ComfyUI サーバーの URL |
| `wd14_tagger.model_name` | 使用する WD Timm Tagger のモデル名 |
| `wd14_tagger.general_threshold` | 一般タグの出力しきい値（0.0〜1.0） |
| `wd14_tagger.character_threshold` | キャラクタータグのしきい値（0.0〜1.0） |
| `prepend_tags` | 全画像の冒頭に追記するタグのリスト |
| `exclude_tags` | 全画像から除去するタグのリスト |

## 使い方

### 基本実行

```bash
python captioning_tool.py <directory>
```

### オプション一覧

| オプション | 省略形 | デフォルト | 説明 |
|---|---|---|---|
| `<directory>` | — | 必須 | 処理対象ディレクトリのパス |
| `--recursive` | `-r` | False | サブディレクトリも再帰的に処理する |
| `--overwrite` | — | False | 既存の `.txt` ファイルを上書きする |
| `--prepend` | `-p` | — | 冒頭に追記するタグ（カンマ区切り）。`config.json` の値と合算 |
| `--exclude` | `-e` | — | 除外するタグ（カンマ区切り）。`config.json` の値と合算 |
| `--report` | — | False | 処理完了後にタグ集計レポートを生成する |
| `--config` | `-c` | `config.json` | 設定ファイルのパス |

### 実行例

```bash
# 基本実行（./images 内の未処理画像をタグ付け）
python captioning_tool.py ./images

# トリガーワードを先頭に付与し、レーティングタグを除去
python captioning_tool.py ./images --prepend "my_chara" --exclude "rating:general, rating:safe"

# サブディレクトリも含めて処理し、既存ファイルを上書き
python captioning_tool.py ./dataset -r --overwrite

# タグ集計レポートも生成する
python captioning_tool.py ./images --report
```

### タグフィルタの処理順序

```
WD14 出力
  → exclude タグを除去（大文字小文字無視・完全一致）
  → prepend タグと重複するタグを除去（WD14 側を削除）
  → prepend タグを先頭に挿入
  → .txt に書き込む
```

**処理例:**

```
prepend: "my_chara, 1girl"
exclude: "rating:general"

WD14 出力: "1girl, solo, long hair, rating:general"
結果:       "my_chara, 1girl, solo, long hair"
```

## タグ集計レポート

`--report` を指定すると、処理完了後に処理対象ディレクトリ内の全 `.txt` ファイルを
読み込んでタグの出現回数を集計し、`tags_report.txt` として出力します。

```
1girl: 42
solo: 38
long hair: 31
blue eyes: 28
...
```

- 対象: ディレクトリ内の全 `.txt`（既存ファイルも含む。`tags_report.txt` 自身は除外）
- ソート: 出現回数の多い順（同数はアルファベット順）
- `--recursive` が指定された場合はサブディレクトリも集計対象に含む

## テスト

```bash
python -m pytest test/
```

## ファイル構成

```
captioning_tool/
  captioning_tool.py    # メインスクリプト（CaptioningTool・エントリポイント）
  config.json           # ComfyUI 接続設定・WD14 設定・デフォルトタグ設定
  test/
    test_captioning_tool.py
  doc/
    SPEC.md
```
