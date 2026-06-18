# run_workflow

ComfyUI の REST API と WebSocket を使い、ワークフローを Python から自動実行するツールです。

LoRA の枚数に応じてテンプレートを自動選択し、プロンプト・LoRA・画像サイズを差し込んで実行します。
ワークフロー（モデル）ごとにテンプレート・LoRA・デフォルト画像サイズを切り替えられます。
また、WD Timm Tagger ワークフローを使って画像のタグ文字列を取得する機能も備えています。

実行結果（出力ファイル一覧・エラー情報）は `result.json` に記録されます。

## 機能

- ワークフロー名でテンプレートセット・LoRA・デフォルト画像サイズを切り替え
- LoRA 0〜4 個に対応したテンプレートの自動選択
- プロンプト（positive / negative）と LoRA の差し込み
- 画像サイズ（width / height）の指定（省略時はワークフロー別のデフォルト値を使用）
- WebSocket によるリアルタイム進捗監視
- 実行ごとにシード値をランダム生成
- 成功・失敗を `result.json` に記録
- WD Timm Tagger による画像タグ付け（`bedovyy/ComfyUI-WD-Timm-Tagger` 使用）

## 必要環境

- Python 3.12+
- 起動済みの ComfyUI（デフォルト: `http://127.0.0.1:8188`）

## セットアップ

リポジトリルートの[セットアップ](../README.md#セットアップ)を参照してください。

## 設定

**`config.json`** — ComfyUI の接続先・ワークフロー別設定・WD14 Tagger 設定を記述します。

```json
{
  "comfyui_url": "http://127.0.0.1:8188",
  "default_workflow": "sdxl",
  "workflows": {
    "sdxl": {
      "default_image_size": {"width": 832, "height": 1216},
      "image_size": {
        "vertical":   {"width": 832,  "height": 1216},
        "horizontal": {"width": 1216, "height": 832},
        "square":     {"width": 1024, "height": 1024}
      },
      "loras": {
        "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
      }
    },
    "anima": {
      "default_image_size": {"width": 1024, "height": 1024},
      "image_size": {
        "vertical":   {"width": 832,  "height": 1216},
        "horizontal": {"width": 1216, "height": 832},
        "square":     {"width": 1024, "height": 1024}
      },
      "loras": {
        "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
      }
    }
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
| `default_workflow` | `--workflow` を省略したときに使用するワークフロー名 |
| `workflows.<name>.default_image_size` | 入力 JSON で `image_size` を省略した場合に使用する既定の画像サイズ |
| `workflows.<name>.image_size` | 向きごとの画像サイズ（`vertical`/`horizontal`/`square` の 3 キーが必須）。`generate_image_bot` から参照される |
| `workflows.<name>.loras` | LoRA キー名とファイル名・強度のマッピング |
| `wd14_tagger.model_name` | WD Timm Tagger で使用するモデル名 |
| `wd14_tagger.general_threshold` | 一般タグの出力しきい値（0.0〜1.0） |
| `wd14_tagger.character_threshold` | キャラクタータグのしきい値（0.0〜1.0） |

## 使い方

### CLI — 画像生成

```bash
# ワークフローを指定して実行
python run_workflow.py -i input.json -w sdxl -o result.json

# ワークフローを省略（config.json の default_workflow を使用）
python run_workflow.py -i input.json
```

**引数一覧:**

| 引数 | 省略形 | 必須 | デフォルト | 説明 |
|---|---|---|---|---|
| `--input` | `-i` | ○ | — | 入力 JSON ファイルのパス |
| `--workflow` | `-w` | — | config の `default_workflow` | ワークフロー名 |
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
| `loras` | ○ | 使用するワークフローの `loras` に定義したキー名を 0〜4 個指定 |
| `prompts.positive` / `prompts.negative` | ○ | プロンプト文字列（最大 3000 文字） |
| `image_size.width` / `image_size.height` | — | 画像サイズ（512〜2048、8 の倍数）。省略時はワークフローの `default_image_size` を使用 |

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

# ワークフローを指定
runner = WorkflowRunner("config.json", workflow_name="anima")

# ワークフローを省略（config.json の default_workflow を使用）
runner = WorkflowRunner("config.json")

# image_size を指定する場合
outputs = runner.execute(
    ["my_lora"],
    {"positive": "...", "negative": "..."},
    image_size={"width": 768, "height": 1024},
)

# image_size を省略する場合（ワークフローの default_image_size を使用）
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
  "template": "templates/sdxl/template_lora_1.json",
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

## 新しいワークフローの追加手順

1. `templates/<workflow_name>/` ディレクトリを作成し、`template_lora_0.json` 〜 `template_lora_4.json` を配置する
2. テンプレートの書き換え対象ノードに以下の `_meta.title` を設定する

| `_meta.title` | 書き換える内容 |
|---|---|
| `positive_prompt` | ポジティブプロンプト |
| `negative_prompt` | ネガティブプロンプト |
| `empty_latent_image` | 画像の width / height |
| `lora_loader_1` 〜 `lora_loader_4` | LoRA ファイル名・ストレングス |

3. `config.json` の `workflows` に同名のキーを追加する

```json
"workflows": {
  "<workflow_name>": {
    "default_image_size": {"width": 1024, "height": 1024},
    "image_size": {
      "vertical":   {"width": 832,  "height": 1216},
      "horizontal": {"width": 1216, "height": 832},
      "square":     {"width": 1024, "height": 1024}
    },
    "loras": {
      "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
    }
  }
}
```

ノードタイトルの詳細は [doc/SPEC.md](./doc/SPEC.md) を参照してください。

## テスト

```bash
python -m pytest test/
```

## テンプレートについて

`templates/` に収録されているワークフローはサンプルです。ComfyUI で作成した任意のワークフローに差し替えて使用できます。

### sdxl テンプレート

| 種別 | 名前 |
|---|---|
| カスタムノード | [ComfyUI-Impact-Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack) |
| モデル | WAI-illustrious-SDXL v16.0 |
| アップスケーラー | RealESRGAN x2 |

### anima / anima_rapid テンプレート

| 種別 | 名前 |
|---|---|
| モデル | waiANIMA v1.0 |
| LoRA | anima-turbo-lora v0.2 |

### WD14 Tagger テンプレート

| 種別 | 名前 |
|---|---|
| カスタムノード | [ComfyUI-WD-Timm-Tagger](https://github.com/bedovyy/ComfyUI-WD-Timm-Tagger) |

## ファイル構成

```
run_workflow/
  run_workflow.py              # メインスクリプト（WorkflowRunner・エントリポイント）
  config.json                  # 接続設定・ワークフロー別設定・WD14設定
  modules/
    load_files.py              # 設定・入力ファイルの読み込みと検証
    workflow_builder.py        # テンプレート選択・書き換え
    comfyui_client.py          # ComfyUI REST API / WebSocket クライアント
    wd14_tagger_runner.py      # WD Timm Tagger ワークフロー実行
  templates/
    sdxl/                      # SDXL テンプレート
      template_lora_0.json ... template_lora_4.json
    anima/                     # waiANIMA テンプレート
      template_lora_0.json ... template_lora_4.json
    anima_rapid/               # waiANIMA 高速版テンプレート
      template_lora_0.json ... template_lora_4.json
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
