# run_workflow

ComfyUI の REST API と WebSocket を使い、ワークフローを Python から自動実行するツールです。

LoRA の枚数に応じてテンプレートを自動選択し、プロンプト・LoRA・画像サイズを差し込んで実行します。
また、WD Timm Tagger ワークフローを使って画像のタグ文字列を取得する機能も備えています。

実行結果（出力ファイル一覧・エラー情報）は `result.json` に記録されます。

## 機能

- LoRA 0〜4 個に対応したテンプレートの自動選択
- プロンプト（positive / negative）と LoRA の差し込み
- 画像サイズ（width / height）の指定（省略時は `config.json` の既定値を使用）
- WebSocket によるリアルタイム進捗監視
- 実行ごとにシード値をランダム生成
- 成功・失敗を `result.json` に記録
- WD Timm Tagger による画像タグ付け（`bedovyy/ComfyUI-WD-Timm-Tagger` 使用）

## 必要環境

- Python 3.12+
- 起動済みの ComfyUI（デフォルト: `http://127.0.0.1:8188`）

## セットアップ

```bash
cd run_workflow
pip install -r requirements.txt
```

## 設定

**`config.json`** — ComfyUI の接続先・既定画像サイズ・LoRA マッピング・WD14 Tagger 設定を記述します。

```json
{
  "comfyui_url": "http://127.0.0.1:8188",
  "default_image_size": {
    "width": 512,
    "height": 512
  },
  "loras": {
    "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
  },
  "wd14_tagger": {
    "model_name": "wd-eva02-large-tagger-v3",
    "general_threshold": 0.35,
    "character_threshold": 0.85
  }
}
```

| キー | 説明 |
|---|---|
| `default_image_size` | 入力 JSON で `image_size` を省略した場合に使用する既定の画像サイズ |
| `loras` | LoRA キー名とファイル名・強度のマッピング |
| `wd14_tagger.model_name` | WD Timm Tagger で使用するモデル名 |
| `wd14_tagger.general_threshold` | 一般タグの出力しきい値（0.0〜1.0） |
| `wd14_tagger.character_threshold` | キャラクタータグのしきい値（0.0〜1.0） |

## 使い方

### CLI — 画像生成

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

### CLI — WD14 タグ付け

画像ファイルを指定してタグ文字列を stdout に出力します。

```bash
python run_workflow.py --tag --image photo.jpg
python run_workflow.py -t -g photo.jpg -c config.json
```

**引数一覧:**

| 引数 | 省略形 | 必須 | 説明 |
|---|---|---|---|
| `--tag` | `-t` | ○ | WD14 Tagger モードで実行する |
| `--image` | `-g` | ○ | タグ付け対象の画像ファイルパス |
| `--config` | `-c` | — | 設定ファイルのパス（省略時: `config.json`） |

**出力例:**

```
1girl, solo, long hair, blue eyes, smile, ...
```

### Python から import — 画像生成

```python
from run_workflow import WorkflowRunner

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

`execute()` はスレッドセーフです。複数スレッドから同一インスタンスを同時呼び出しできます。

### Python から import — WD14 タグ付け

```python
from modules.wd14_tagger_runner import Wd14TaggerRunner

runner = Wd14TaggerRunner("config.json")

with open("photo.jpg", "rb") as f:
    image_data = f.read()

tags = runner.tag(image_data, "photo.jpg")
print(tags)
# 1girl, solo, long hair, blue eyes, ...
```

## 出力

実行後に `result.json` が生成されます。

```json
{
  "status": "success",
  "prompt_id": "abc123",
  "timestamp": "2026-04-25T12:00:00",
  "template": "templates/template_lora_1.json",
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
python -m pytest test/
```

## テンプレートについて

`templates/` に収録されているワークフローはサンプルです。

ComfyUI で作成した任意のワークフローに差し替えて使用できます（テンプレートのノード特定方法は [SPEC.md](./doc/SPEC.md) を参照）。

### 画像生成テンプレート

サンプルテンプレートを実際に動作させるには、ComfyUI に以下が必要です。

| 種別 | 名前 |
|---|---|
| カスタムノード | [ComfyUI-Impact-Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack) |
| モデル | WAI-illustrious-SDXL v16.0 |
| アップスケーラー | RealESRGAN x2 |

### WD14 Tagger テンプレート

| 種別 | 名前 |
|---|---|
| カスタムノード | [ComfyUI-WD-Timm-Tagger](https://github.com/bedovyy/ComfyUI-WD-Timm-Tagger) |

## ファイル構成

```
run_workflow/
  run_workflow.py              # メインスクリプト（WorkflowRunner・エントリポイント）
  config.json                  # 接続設定・既定画像サイズ・LoRAマッピング・WD14設定
  requirements.txt
  modules/
    load_files.py              # 設定・入力ファイルの読み込みと検証
    workflow_builder.py        # テンプレート選択・書き換え
    comfyui_client.py          # ComfyUI REST API / WebSocket クライアント
    wd14_tagger_runner.py      # WD Timm Tagger ワークフロー実行
  templates/
    template_lora_0.json       # LoRA 0個用テンプレート
    template_lora_1.json
    template_lora_2.json
    template_lora_3.json
    template_lora_4.json
    template_wd14_tagger.json  # WD Timm Tagger ワークフローテンプレート
  test/
    test_helper.py
    test_run_workflow.py
    test_load_files.py
    test_workflow_builder.py
    test_comfyui_client.py
    test_wd14_tagger_runner.py
  doc/
    SPEC.md
```
