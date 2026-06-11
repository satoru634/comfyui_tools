# run_workflow.py 仕様書 — WD14 Tagger 機能

## 概要

ComfyUI の WD Timm Tagger ワークフロー（`bedovyy/ComfyUI-WD-Timm-Tagger`）を
Python から実行し、画像のタグ文字列を取得する機能。
`Wd14TaggerRunner` クラスとして `modules/wd14_tagger_runner.py` に実装し、単独でも import 経由でも利用できる。

---

## `Wd14TaggerRunner` クラス

`run_workflow/modules/wd14_tagger_runner.py` に定義する。

```python
class Wd14TaggerRunner:
    def __init__(self, config_path: str): ...
    def tag(self, image_data: bytes, filename: str = "image.png") -> str: ...
```

| メソッド | 説明 |
|---|---|
| `__init__(config_path)` | `config.json` を読み込み、`ComfyUIClient` を初期化する。`template_wd14_tagger.json` も読み込んで保持する |
| `tag(image_data, filename)` | 画像バイト列を受け取り、ComfyUI にアップロードしてワークフローを実行し、タグ文字列を返す |

### `tag` メソッドの内部処理

```
1. ComfyUIClient.upload_image(image_data, filename) で画像をアップロードし、戻り値のファイル名を取得
2. テンプレートを deepcopy し、"画像を読み込む" ノードの inputs.image にファイル名を設定
3. "WD Timm Tagger" ノードの inputs.model_name / inputs.general_threshold / inputs.character_threshold を config の値で設定
4. ComfyUIClient.submit(workflow, client_id) でワークフローを送信し、prompt_id を取得
5. ComfyUIClient.monitor(prompt_id, client_id) で WebSocket によるワークフロー完了を監視する
6. ComfyUIClient.get_history(prompt_id) から "プレビュー任意" ノードの text[0] を取得して返す
7. いずれかのステップで失敗した場合は ValueError を送出する
```

### Python から import して使う例

```python
runner = Wd14TaggerRunner("run_workflow/config.json")

with open("photo.jpg", "rb") as f:
    image_data = f.read()

tags = runner.tag(image_data)
print(tags)
# masterpiece, 1girl, solo, long hair, blue eyes, ...
```

---

## ワークフローテンプレート

### テンプレートファイル

`run_workflow/templates/template_wd14_tagger.json`

WD Timm Tagger ノード、LoadImage ノード、PreviewAny ノードを含む ComfyUI ワークフロー JSON。
各ノードの `_meta.title` は以下の通り。

| `_meta.title` | ノードの種類 | 書き換える内容 |
|---|---|---|
| `"画像を読み込む"` | `LoadImage` | `inputs.image` にアップロードした画像ファイル名を設定 |
| `"WD Timm Tagger"` | `WDTimmTagger`（bedovyy/ComfyUI-WD-Timm-Tagger） | `inputs.model_name` / `inputs.general_threshold` / `inputs.character_threshold` を config の値で設定 |
| `"プレビュー任意"` | `PreviewAny` | 書き換えなし（タグ取得のみに使用） |

### タグ出力の取得

`WDTimmTagger` ノードは history に出力を保存しない。`PreviewAny`（`"プレビュー任意"`）ノードを経由して
`text` キーでタグ文字列を取得する。

```python
node_id = title_to_node_id["プレビュー任意"]
tags = history["outputs"][node_id]["text"][0]
```

`text` キーが存在しない場合は `ValueError` を送出する。

---

## `ComfyUIClient` の拡張

`run_workflow/modules/comfyui_client.py` に以下のメソッドを追加する。

```python
def upload_image(self, image_data: bytes, filename: str = "image.png") -> str:
    """画像を ComfyUI にアップロードし、ComfyUI 側のファイル名を返す"""

def get_history(self, prompt_id: str) -> dict:
    """ComfyUI の履歴から指定された prompt_id のデータを返す"""
```

#### `upload_image`

- `POST <comfyui_url>/upload/image` に multipart/form-data で送信する
- レスポンスの `name` フィールドを返す
- HTTP エラー時は `ValueError` を送出する

#### `get_history`

- `GET <comfyui_url>/history/{prompt_id}` を呼び出す
- レスポンスから `prompt_id` キーに対応する dict を返す（存在しない場合は空 dict）
- HTTP エラー時は `ValueError` を送出する

### `_monitor_ws` の競合状態対策

ComfyUI がワークフローを高速実行（数ミリ秒以内）した場合、WebSocket 接続確立前に
`execution_complete` が送出される競合状態が発生する。
これを回避するため、`_monitor_ws` はメッセージ受信に `asyncio.wait_for`（タイムアウト 2 秒）を使用し、
タイムアウト時は `GET /history/{prompt_id}` で完了済みかをポーリングする。

---

## 設定ファイル（`run_workflow/config.json` への追加）

```json
{
  "wd14_tagger": {
    "model_name": "wd-eva02-large-tagger-v3",
    "general_threshold": 0.35,
    "character_threshold": 0.85
  }
}
```

| キー | 説明 |
|---|---|
| `model_name` | 使用するモデル名（WD Timm Tagger の `model_name` 入力に渡す値） |
| `general_threshold` | 一般タグの出力しきい値（0.0〜1.0） |
| `character_threshold` | キャラクタータグのしきい値（0.0〜1.0） |

---

## ファイル構成の変更

```
run_workflow/
  run_workflow.py           # --tag / --image フラグ追加、_run_tagger() 追加
  config.json               # wd14_tagger セクションを追加
  modules/
    comfyui_client.py       # upload_image / get_history メソッドを追加、_monitor_ws 競合対策を追加
    load_files.py           # wd14_tagger セクションのバリデーションを追加
    wd14_tagger_runner.py   # 新規: Wd14TaggerRunner クラス
  templates/
    template_wd14_tagger.json  # 新規: WD Timm Tagger ワークフローテンプレート
  test/
    test_wd14_tagger_runner.py  # 新規: Wd14TaggerRunner のテスト
    test_comfyui_client.py      # upload_image / get_history / _is_completed メソッドのテストを追加
    test_load_files.py          # wd14_tagger バリデーションのテストを追加
    test_run_workflow.py        # _run_tagger() のテストを追加
```

### アーキテクチャへの追加

```
Wd14TaggerRunner → ComfyUIClient（画像アップロード・ワークフロー送信・WebSocket 監視・履歴取得）
```

---

## エラーハンドリング

| エラー種別 | `tag()` の挙動 |
|---|---|
| ComfyUI への画像アップロード失敗 | `ValueError` を送出する |
| ワークフロー実行エラー（ComfyUI 未起動等） | `ValueError` を送出する |
| history に `text` キーが存在しない | `ValueError` を送出する |

---

## テスト

| テストファイル | 追加・変更 | 内容 |
|---|---|---|
| `test/test_wd14_tagger_runner.py` | 新規 | `Wd14TaggerRunner.tag()` のユニットテスト。`ComfyUIClient` を `unittest.mock` でモックする |
| `test/test_comfyui_client.py` | 追加 | `upload_image` / `get_history` / `_is_completed` メソッドのユニットテスト |
| `test/test_load_files.py` | 追加 | `wd14_tagger` セクションのバリデーションテスト |
| `test/test_run_workflow.py` | 追加 | `_run_tagger()` のユニットテスト |
