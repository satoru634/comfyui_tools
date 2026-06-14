# SPEC.md — captioning_tool

## 概要

`run_workflow` の `Wd14TaggerRunner` を使い、指定ディレクトリ内の画像ファイルにタグ付けして、
各画像と同名の `.txt` ファイルとして保存するバッチ処理ツール。
LoRA 学習などのキャプションファイル整備を主な用途として想定する。

---

## ファイル構成

```
captioning_tool/
  captioning_tool.py    # メインスクリプト（CaptioningTool・エントリポイント）
  config.json           # ComfyUI 接続設定・WD14 設定・デフォルトタグ設定
  doc/
    SPEC.md             # 本ファイル
  test/
    test_captioning_tool.py
```

---

## 設定ファイル

### config.json

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
| `prepend_tags` | 全画像の冒頭に追記するタグのリスト（デフォルト: 空） |
| `exclude_tags` | 全画像から除去するタグのリスト（デフォルト: 空） |

---

## CLI インターフェース

### 実行コマンド

```bash
python captioning_tool.py <directory> [options]
```

### オプション

| オプション | 省略形 | デフォルト | 説明 |
|---|---|---|---|
| `<directory>` | — | 必須 | 処理対象ディレクトリのパス |
| `--recursive` | `-r` | False | サブディレクトリも再帰的に処理する |
| `--overwrite` | — | False | 既存の `.txt` ファイルを上書きする（デフォルト: スキップ） |
| `--prepend` | `-p` | — | 冒頭に追記するタグ（カンマ区切り）。`config.json` の値と合算される |
| `--exclude` | `-e` | — | 除外するタグ（カンマ区切り）。`config.json` の値と合算される |
| `--report` | — | False | 処理完了後にタグ集計レポートを生成する |
| `--config` | `-c` | `config.json` | 設定ファイルのパス |

### 実行例

```bash
# 基本実行
python captioning_tool.py ./images

# トリガーワードを先頭に付与し、レーティングタグを除去
python captioning_tool.py ./images --prepend "my_chara" --exclude "rating:general, rating:safe"

# サブディレクトリも含めて再帰的に処理（既存ファイルは上書き）
python captioning_tool.py ./dataset -r --overwrite

# 処理完了後にタグ集計レポートを生成する
python captioning_tool.py ./images --report

# 設定ファイルを指定
python captioning_tool.py ./images --config /path/to/config.json
```

---

## 処理フロー

1. `config.json` を読み込む。存在しない・フォーマット不正の場合はエラーを出力して終了する
2. 指定ディレクトリの存在を確認する。存在しない場合はエラーを出力して終了する
3. 対象画像ファイルを収集する（対応拡張子: `.jpg` `.jpeg` `.png` `.webp`）
   - `--recursive` が指定された場合はサブディレクトリも再帰的に収集する
4. 各画像に対して以下を実行する:
   a. 対応する `.txt` ファイルがすでに存在し、かつ `--overwrite` が指定されていない場合はスキップする
   b. 画像をバイト列として読み込む
   c. `Wd14TaggerRunner.tag()` を呼び出してタグ文字列を取得する
   d. タグフィルタを適用する（下記「タグフィルタ処理」参照）
   e. 同名 `.txt` ファイルに書き込む
   f. 進捗を stdout に出力する（例: `[1/42] photo.jpg → OK`）
5. 処理完了後にサマリを出力する（例: `完了: 処理 40, スキップ 1, エラー 1`）
6. `--report` が指定されている場合、タグ集計レポートを生成する（下記「タグ集計レポート」参照）

---

## タグフィルタ処理

`_apply_tag_filters(tags: str) -> str` で以下の順に処理する。

### 処理順序

```
WD14 出力タグ
  → (1) exclude タグを除去
  → (2) prepend タグと重複するタグを除去（WD14 側を削除）
  → (3) prepend タグを先頭に挿入
  → 書き込む
```

### (1) exclude タグの除去

- `config.json` の `exclude_tags` と `--exclude` で指定されたタグの **union** を除外対象とする
- マッチング: **完全一致・大文字小文字無視**（`rating:general` は `Rating:General` にもマッチする）
- タグの前後の空白を trim してから比較する

### (2) prepend 重複の除去

- `config.json` の `prepend_tags` と `--prepend` で指定されたタグの **union** を prepend タグとする
- WD14 出力の中に prepend タグと重複するタグが存在する場合、WD14 側を除去する（prepend を優先する）
- マッチング: 完全一致・大文字小文字無視

### (3) prepend タグの挿入

- `config.json` の値 → `--prepend` の値の順で先頭に挿入する

### 処理例

```
prepend_tags (config): ["my_chara"]
--prepend: "1girl"
--exclude: "rating:general"

WD14 出力: "1girl, solo, long hair, rating:general"

(1) exclude 除去:  "1girl, solo, long hair"
(2) prepend 重複除去: "solo, long hair"（"1girl" を除去）
(3) prepend 挿入:  "my_chara, 1girl, solo, long hair"
```

---

## タグ集計レポート

### 概要

`--report` フラグを指定した場合、キャプショニング処理の完了後に処理対象ディレクトリ内の
全 `.txt` ファイルを読み込み、タグの出現回数を集計して `tags_report.txt` として出力する。

### 集計対象

- 処理対象ディレクトリ（`--recursive` 指定時はサブディレクトリも含む）内の **全 `.txt` ファイル**
  - 今回新たに生成したものだけでなく、既存のファイルも含む
  - `tags_report.txt` 自身は集計対象から除外する

### 出力ファイル

| 項目 | 内容 |
|---|---|
| ファイル名 | `tags_report.txt` |
| 出力先 | 処理対象ディレクトリ直下 |
| 既存ファイルの扱い | 常に上書き |

### 出力フォーマット

各行を `タグ名: 出現回数` の形式で出力する。出現回数の多い順にソートし、同数の場合はタグ名のアルファベット順とする。

```
1girl: 42
solo: 38
long hair: 31
blue eyes: 28
...
```

### 処理手順

```
1. 対象ディレクトリ内の全 .txt ファイルを収集する（tags_report.txt は除外）
2. 各 .txt ファイルをカンマ区切りで読み込み、タグを抽出する
3. 全タグの出現回数を集計する（大文字小文字はそのまま保持）
4. 出現回数の多い順（同数はアルファベット順）でソートする
5. tags_report.txt に書き出す
6. 生成完了を stdout に出力する（例: `レポートを保存しました: ./images/tags_report.txt`）
```

---

## アーキテクチャ

### クラス構成

```python
class CaptioningTool:
    def __init__(self, config_path: str = "config.json",
                 extra_prepend: list[str] = [],
                 extra_exclude: list[str] = []):
        ...

    def process_directory(self, directory: Path,
                          recursive: bool = False,
                          overwrite: bool = False) -> tuple[int, int, int]:
        """(処理数, スキップ数, エラー数) を返す"""
        ...

    def generate_report(self, directory: Path, recursive: bool = False) -> None:
        """ディレクトリ内の全 .txt を集計して tags_report.txt を出力する"""
        ...

    def _process_image(self, image_path: Path, overwrite: bool) -> bool:
        """タグ取得 → フィルタ → .txt 書き込み。成功で True を返す"""
        ...

    def _apply_tag_filters(self, tags: str) -> str:
        """exclude 除去 → prepend 重複除去 → prepend 挿入"""
        ...

    def _collect_all_tags(self, directory: Path, recursive: bool) -> dict[str, int]:
        """ディレクトリ内の全 .txt からタグを収集し、{タグ名: 出現回数} を返す"""
        ...
```

| メソッド | 説明 |
|---|---|
| `__init__` | `config.json` を読み込み、`Wd14TaggerRunner` を初期化する。`config.json` の prepend/exclude と引数の extra_prepend/extra_exclude を合算して保持する |
| `process_directory` | ディレクトリ内の画像を順次処理し、(処理数, スキップ数, エラー数) のタプルを返す |
| `generate_report` | ディレクトリ内の全 `.txt` を読み込み、タグを集計して `tags_report.txt` を出力する |
| `_process_image` | 単一画像のタグ取得・フィルタ適用・`.txt` 書き込みを行う |
| `_apply_tag_filters` | タグ文字列にフィルタを適用して返す |
| `_collect_all_tags` | 全 `.txt` ファイルからタグを収集して `{タグ名: 出現回数}` の辞書を返す。`tags_report.txt` は除外する |

### `Wd14TaggerRunner` の利用方法

`run_workflow/` ディレクトリを `sys.path` に追加して import する。

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "run_workflow"))
from modules.wd14_tagger_runner import Wd14TaggerRunner
```

### 依存関係

```
CaptioningTool → Wd14TaggerRunner（run_workflow/modules/wd14_tagger_runner.py）
Wd14TaggerRunner → ComfyUIClient（run_workflow/modules/comfyui_client.py）
```

---

## エラーハンドリング

| エラー種別 | 挙動 |
|---|---|
| `config.json` の読み込み失敗・フォーマット不正 | エラーメッセージを出力して終了（exit code 1） |
| 指定ディレクトリが存在しない | エラーメッセージを出力して終了（exit code 1） |
| 画像ファイルの読み込み失敗 | エラーログを出力してスキップ、処理継続 |
| `tag()` の失敗（ComfyUI 未起動・接続失敗等） | エラーログを出力してスキップ、処理継続 |
| `.txt` ファイルの書き込み失敗 | エラーログを出力してスキップ、処理継続 |
| `tags_report.txt` の書き込み失敗 | エラーメッセージを出力して終了（exit code 1） |

---

## テスト

| テストファイル | 内容 |
|---|---|
| `test/test_captioning_tool.py` | `CaptioningTool` のユニットテスト。`Wd14TaggerRunner` を `unittest.mock` でモックする |

### 主なテストケース

- `_apply_tag_filters`: exclude 除去・prepend 重複除去・prepend 挿入の各動作
- `_process_image`: スキップ動作（既存 `.txt` あり）・上書き動作・エラー時スキップ
- `process_directory`: 処理数・スキップ数・エラー数の集計
- `--recursive` フラグ: サブディレクトリの画像が収集されるか
- `_collect_all_tags`: 複数 `.txt` からのタグ集計・`tags_report.txt` 自身の除外
- `generate_report`: 出現回数の多い順ソート・同数時のアルファベット順ソート・ファイル出力内容

---

## 依存ライブラリ

`run_workflow` の依存ライブラリ（`websockets`, `requests`）を間接的に使用する。
追加で必要な外部ライブラリはない。
