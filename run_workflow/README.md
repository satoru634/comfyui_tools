# run_workflow

ComfyUI の REST API と WebSocket を使い、ワークフローを Python から自動実行するツールです。

LoRA の枚数に応じてテンプレートを自動選択し、プロンプト・LoRA・画像サイズを差し込んで実行します。

実行結果（出力ファイル一覧・エラー情報）は `result.json` に記録されます。

## 機能

- LoRA 0〜4 個に対応したテンプレートの自動選択
- プロンプト（positive / negative）と LoRA の差し込み
- 画像サイズ（width / height）の指定（省略時は `config.json` の既定値を使用）
- WebSocket によるリアルタイム進捗監視
- 実行ごとにシード値をランダム生成
- 成功・失敗を `result.json` に記録

## 必要環境

- Python 3.12+
- 起動済みの ComfyUI（デフォルト: `http://127.0.0.1:8188`）

## セットアップ

```bash
cd run_workflow
pip install -r requirements.txt
```

## 設定

**`config.json`** — ComfyUI の接続先・既定画像サイズ・LoRA マッピングを記述します。

```json
{
  "comfyui_url": "http://127.0.0.1:8188",
  "default_image_size": {
    "width": 512,
    "height": 512
  },
  "loras": {
    "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
  }
}
```

- `default_image_size`: 入力 JSON で `image_size` を省略した場合に使用する既定の画像サイズ。
- `loras`: LoRA キー名とファイル名・強度のマッピング。

## 使い方

### CLI

```bash
python run_workflow.py -i input.json -o result.json
```

**引数一覧:**

| 引数 | 省略形 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `--input` | `-i` | ○ | — | 入力 JSON ファイルのパス |
| `--output` | `-o` | — | `result_<timestamp>.json` | 結果 JSON の出力先 |
| `--config` | `-c` | — | `config.json` | 設定ファイルのパス |

**`input.json` フォーマット:**

```json
{
  "loras": ["my_lora"],
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

| フィールド | 必須 | 説明 |
|---|---|---|
| `loras` | ○ | `config.json` の `loras` に定義したキー名を 0〜4 個指定 |
| `prompts.positive` / `prompts.negative` | ○ | プロンプト文字列（最大 3000 文字） |
| `image_size.width` / `image_size.height` | — | 画像サイズ（512〜2048、8 の倍数）。省略時は `default_image_size` を使用 |

### Python から import

```python
from run_workflow import WorkflowRunner

runner = WorkflowRunner("config.json")

# image_size を指定する場合
runner.execute(
    ["my_lora"],
    {"positive": "...", "negative": "..."},
    image_size={"width": 768, "height": 1024},
)

# image_size を省略する場合（config.json の default_image_size を使用）
runner.execute(["my_lora"], {"positive": "...", "negative": "..."})
```

## 出力

実行後に `result.json` が生成されます。

```json
{
  "status": "success",
  "prompt_id": "abc123",
  "timestamp": "2026-04-25T12:00:00",
  "parameters": {
    "positive": "masterpiece, best quality, 1girl ...",
    "negative": "worst quality, bad quality ...",
    "loras": [{"name": "my_lora", "file": "my_lora.safetensors", "strength": 0.8}],
    "image_size": {"width": 768, "height": 1024}
  },
  "outputs": [
    {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}
  ],
  "error": null
}
```

## テスト

```bash
python -m pytest test/ -v
```

## テンプレートについて

`templates/` に収録されているワークフローはサンプルです。

ComfyUI で作成した任意のワークフローに差し替えて使用できます（テンプレートのノード特定方法は [SPEC.md](./doc/SPEC.md) を参照）。

サンプルテンプレートを実際に動作させるには、ComfyUI に以下が必要です。

| 種別 | 名前 |
|---|---|
| カスタムノード | [ComfyUI-Impact-Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack) |
| モデル | WAI-illustrious-SDXL v16.0 |
| アップスケーラー | RealESRGAN x2 |

## ファイル構成

```
run_workflow/
  run_workflow.py         # メインスクリプト
  config.json             # 接続設定・既定画像サイズ・LoRAマッピング
  requirements.txt
  templates/
    template_lora_0.json  # LoRA 0個用テンプレート
    template_lora_1.json
    template_lora_2.json
    template_lora_3.json
    template_lora_4.json
  test/
    test_run_workflow.py
```
