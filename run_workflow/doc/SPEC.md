# run_workflow.py 仕様書

## 概要

ComfyUI のワークフローを Python から自動実行するスクリプト。
WebSocket で進捗をリアルタイム監視し、結果を `result.json` に記録する。

## ファイル構成

```
run_workflow/
  run_workflow.py         # メインスクリプト（WorkflowRunner・エントリポイント）
  config.json             # 接続設定・既定画像サイズ・LoRAマッピング
  requirements.txt
  modules/
    load_files.py         # 設定・入力ファイルの読み込みと検証
    workflow_builder.py   # テンプレート選択・書き換え
    comfyui_client.py     # ComfyUI REST API / WebSocket クライアント
  templates/
    template_lora_0.json  # LoRA 0個用
    template_lora_1.json  # LoRA 1個用
    template_lora_2.json  # LoRA 2個用
    template_lora_3.json  # LoRA 3個用
    template_lora_4.json  # LoRA 4個用
  test/
    test_helper.py
    test_run_workflow.py
    test_load_files.py
    test_workflow_builder.py
    test_comfyui_client.py
  doc/
    SPEC.md
```

## 設定ファイル

### config.json
```json
{
  "comfyui_url": "http://127.0.0.1:8188",
  "default_image_size": {
    "width": 512,
    "height": 512
  },
  "loras": {
    "my_lora": {"file": "my_lora.safetensors", "strength": 0.8},
    "another_lora": {"file": "another_lora.safetensors", "strength": 0.7}
  }
}
```

- `default_image_size`: 入力 JSON で `image_size` を省略した場合に使用する既定の画像サイズ。
- `loras`: LoRA キー名とファイル名・強度のマッピング。入力 JSON の `loras` リストで指定するキー名はここに定義する。

## 入力インターフェース

### 実行コマンド

```bash
python run_workflow.py --input input.json --output result.json
```

| オプション | 省略形 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `--input` | `-i` | ○ | — | 入力 JSON ファイルのパス |
| `--output` | `-o` | — | `result_<timestamp>.json` | 結果 JSON の出力先 |
| `--config` | `-c` | — | `config.json` | 設定ファイルのパス |

### 入力 JSON フォーマット

```json
{
  "loras": ["LoRA_name_1", "LoRA_name_2"],
  "prompts": {
    "positive": "masterpiece, best quality, 1girl ...",
    "negative": "worst quality, bad quality ..."
  },
  "image_size": {
    "width": 768,
    "height": 1024
  }
}
```

- `loras`: `config.json` の `loras` に定義したキー名を指定する。0〜4個まで指定可能。
- `prompts.positive` / `prompts.negative`: プロンプト文字列。
- `image_size` (省略可能): 生成する画像のサイズ。省略時は `config.json` の `default_image_size` を使用する。
  - `width` / `height`: 整数。512〜2048 の範囲で 8 の倍数であること。

## テンプレートの自動選択

入力 JSON の `loras` の個数に応じて、使用するテンプレートを自動で選択する。

| LoRA 個数 | 使用テンプレート |
|---|---|
| 0 | `templates/template_lora_0.json` |
| 1 | `templates/template_lora_1.json` |
| 2 | `templates/template_lora_2.json` |
| 3 | `templates/template_lora_3.json` |
| 4 | `templates/template_lora_4.json` |

## テンプレートのノード特定

ワークフロー JSON のノード `_meta.title` で書き換え対象ノードを識別する。
テンプレートを作成する際は、対象ノードに以下のタイトルを設定すること。

| `_meta.title` | 書き換える内容 |
|---|---|
| `positive_prompt` | `prompts.positive` の文字列 |
| `negative_prompt` | `prompts.negative` の文字列 |
| `empty_latent_image` | `image_size.width` / `image_size.height` |
| `lora_loader_1` | 1つ目のLoRAファイル名・ストレングス |
| `lora_loader_2` | 2つ目のLoRAファイル名・ストレングス |
| `lora_loader_3` | 3つ目のLoRAファイル名・ストレングス |
| `lora_loader_4` | 4つ目のLoRAファイル名・ストレングス |

`class_type` や `_meta.title` によらず、`inputs.seed` フィールドを持つすべてのノードは実行ごとにランダム生成した値（`0〜2^53`）で上書きする。対象ノードにはすべて同一の seed 値を使用する。

## アーキテクチャ

### クラス・モジュール構成

| クラス / モジュール | 責務 |
|---|---|
| `WorkflowRunner` | `WorkflowBuilder`・`ComfyUIClient` を束ねてワークフロー実行を制御するファサード |
| `WorkflowBuilder` | テンプレート選択・読み込み・プロンプト/LoRA/画像サイズ/seed の書き換え |
| `ComfyUIClient` | ComfyUI REST API 呼び出し・WebSocket 監視 |
| `load_files` | `config.json` と入力 JSON の読み込み・検証 (`load_config`, `load_and_validate_input`, `validate_inputs`) |

### 実装上の制約

- **WebSocket バイナリフレームのスキップ**: ComfyUI はプレビュー画像をバイナリフレームで送信する。`if isinstance(raw, bytes): continue` を必ず入れること。これを省略すると `json.loads()` が失敗する。
- **テンプレートは deepcopy してから書き換える**: `WorkflowBuilder.apply()` では `copy.deepcopy()` を先頭で行い、元テンプレートを汚染しない。

## 処理フロー

1. `config.json` を読み込み、接続先 URL・LoRA定義・`default_image_size` を取得する
2. 入力 JSON を読み込む
3. `image_size` が省略されている場合、`config.json` の `default_image_size` を使用する
4. LoRA名 → ファイル名・ストレングスを解決する
5. LoRA の個数に応じてテンプレートを自動選択し、プロンプト・LoRA・画像サイズを書き換える
6. `POST /prompt` でワークフローを送信し、`prompt_id` を取得する
7. WebSocket (`ws://host/ws?clientId=<uuid>`) で実行完了またはエラーを監視する
8. 完了後、`GET /history/{prompt_id}` で出力ファイル一覧を取得する
9. `result.json` を出力して終了する

## result.json フォーマット

### 成功時
```json
{
  "status": "success",
  "prompt_id": "abc123",
  "timestamp": "2026-04-22T20:30:00",
  "template": "...templates/template_lora_2.json",
  "parameters": {
    "positive": "masterpiece, best quality, 1girl ...",
    "negative": "worst quality, bad quality ...",
    "loras": [
      {"name": "my_lora", "file": "my_lora.safetensors", "strength": 0.8},
      {"name": "another_lora", "file": "another_lora.safetensors", "strength": 0.7}
    ],
    "image_size": {"width": 768, "height": 1024}
  },
  "outputs": [
    {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}
  ],
  "error": null
}
```

### エラー時
```json
{
  "status": "error",
  "prompt_id": null,
  "timestamp": "2026-04-22T20:30:00",
  "template": "...templates/template_lora_1.json",
  "parameters": {
    "positive": "masterpiece, best quality, 1girl ...",
    "negative": "worst quality, bad quality ...",
    "loras": [
      {"name": "my_lora", "file": "my_lora.safetensors", "strength": 0.8}
    ],
    "image_size": {"width": 512, "height": 512}
  },
  "outputs": [],
  "error": "ComfyUI に接続できません: Connection refused"
}
```

## エラーハンドリング

| エラー種別 | 対応 |
|---|---|
| ComfyUI 未起動・接続失敗 | result.json にエラー記録して終了 |
| 入力 JSON のフォーマットが不正 | result.json にエラー記録して終了 |
| LoRA名が config.json の loras に存在しない | result.json にエラー記録して終了 |
| LoRA が 5個以上指定された | result.json にエラー記録して終了 |
| `image_size.width` / `image_size.height` が整数でない | result.json にエラー記録して終了 |
| `image_size.width` / `image_size.height` が 512〜2048 の範囲外 | result.json にエラー記録して終了 |
| `image_size.width` / `image_size.height` が 8 の倍数でない | result.json にエラー記録して終了 |
| `config.json` に `default_image_size` がない | result.json にエラー記録して終了 |
| テンプレートファイルが存在しない | result.json にエラー記録して終了 |
| テンプレートに `empty_latent_image` ノードが見つからない | result.json にエラー記録して終了 |
| ComfyUI 側のワークフロー実行エラー | result.json にエラー記録して終了 |

## WD14 Tagger 機能

[WD14 Tagger 機能仕様書](./SPEC/wd14_tagger.md)を参照。

## 開発ルール

- `config.json` に統合できるものは別ファイルを作らない。
- 新しいクラスや関数を追加する場合は `WorkflowRunner` → `WorkflowBuilder` → `ComfyUIClient` の依存方向を崩さない。
- プロンプト最大長 `MAX_PROMPT_LENGTH = 3000` はメモリ枯渇防止のため変更・削除しない。

## 依存ライブラリ

- `websockets` — WebSocket 接続・進捗監視
- `requests` — REST API 呼び出し
- `pytest` — テスト

## 実行例(CLI)
```bash
python run_workflow.py --input input.json --output result.json --config config.json
```

## 実行例(Pythonからimportして使用)
```python
runner = WorkflowRunner("config.json")

# image_size を指定する場合
outputs = runner.execute(
    ["my_lora"],
    {"positive": "...", "negative": "..."},
    image_size={"width": 768, "height": 1024},
)

# image_size を省略する場合（config.json の default_image_size を使用）
outputs = runner.execute(["my_lora"], {"positive": "...", "negative": "..."})
```
