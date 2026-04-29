# generate_image_bot

Discord から ComfyUI に画像生成を指示し、生成された画像を Discord に返送するボットです。

内部で `run_workflow` の `WorkflowRunner` を使用して画像生成を実行します。

リクエスト結果（出力ファイル情報・エラー情報）は `log/` ディレクトリに記録されます。

## 機能

- **メンションメッセージ**によるプロンプト入力（キーワード形式: `positive:` / `negative:` / `loras:` / `image_orientation:`）
- **スラッシュコマンド**（`/gen_image`）によるモーダル入力
- 画像の向き（`vertical` / `horizontal`）を指定して画像サイズを切り替え（省略時は `run_workflow/config.json` の既定値を使用）
- ユーザー単位のレート制限（30秒クールダウン）
- グローバル生成ロック（同時生成は 1 件のみ）
- 生成結果を Discord に画像添付で返信
- リアクション絵文字による進捗通知（処理中 / 成功 / エラー）
- 指定した時刻にボットを自動停止（処理中のリクエストを完了してから終了）
- リクエスト結果を `log/result_YYYYMMDD_hhmmss.json` に記録

## 必要環境

- Python 3.12+
- 起動済みの ComfyUI
- `run_workflow`（同リポジトリの兄弟ディレクトリ）
- Discord Bot トークン

## セットアップ

### 1. Discord Bot の作成とサーバーへの追加

[Discord Developer Portal](https://discord.com/developers/applications) でアプリケーションを作成し、Bot を有効化してトークンを取得します。

取得したトークンは `config.json` の `discord_token` に設定します。

**Privileged Gateway Intents の設定**

Developer Portal の Bot 設定画面で以下を有効にします。

| Intents | 用途 |
|---|---|
| Message Content Intent | メッセージ本文（プロンプト）の読み取り |

**OAuth2 URL ジェネレーターでの招待 URL 生成**

Developer Portal の「OAuth2 → URL Generator」で以下を選択し、生成された URL からサーバーに Bot を追加します。

| 項目 | 設定値 |
|---|---|
| Scopes | `bot` |

Bot の権限（Bot Permissions）:

| 権限 | 用途 |
|---|---|
| チャンネルを表示（View Channels） | メッセージの受信 |
| メッセージを送る（Send Messages） | 画像・エラーメッセージの返信 |
| ファイルを添付（Attach Files） | 生成画像の送信 |
| リアクションを付ける（Add Reactions） | ⏳ / ✅ / ❌ の付与 |
| スラッシュコマンドを使用 (Use Slash Commands) | 画像生成のモーダルウィンドウ起動 |

### 2. 依存ライブラリのインストール

```bash
cd generate_image_bot
pip install -r requirements.txt
```

## 設定

**`config.json`** — Discord トークンや ComfyUI の出力先などを記述します。

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "comfyui_output_dir": "C:/path/to/ComfyUI/output",
  "run_workflow_config": "../run_workflow/config.json",
  "shutdown_time": "03:00",
  "image_size": {
    "vertical": {"width": 832, "height": 1216},
    "horizontal": {"width": 1216, "height": 832}
  },
  "reactions": {
    "processing": "⏳",
    "success": "✅",
    "error": "❌"
  },
  "messages": {
    "rate_limit": "リクエストが連続しています。あと {remaining_seconds} 秒待ってから再試行してください。",
    "generating": "現在他のリクエストを処理中です。しばらくお待ちください。",
    "parse_error": "メッセージの形式が正しくありません:\n{error}",
    "execution_error": "生成に失敗しました:\n{error}",
    "file_too_large": "画像ファイルが大きすぎます（{size_mb} MB）",
    "unexpected_error": "予期しないエラーが発生しました",
    "dm_not_supported": "DM からは使用できません。サーバーのチャンネルで実行してください。",
    "shutdown_in_progress": "ボットはシャットダウン中です。しばらくしてから再試行してください。"
  }
}
```

`config.json` にはトークンが含まれるため、事故を防ぐ目的で本リポジトリには含めていません。

上記内容を基に`config.json`を作成してください。

**主な設定項目:**

| キー | 説明 |
|---|---|
| `discord_token` | Discord Bot トークン |
| `comfyui_output_dir` | ComfyUI の output フォルダへの絶対パス |
| `run_workflow_config` | `run_workflow/config.json` へのパス |
| `shutdown_time` | ボットを停止する時刻（`"hh:mm"` 形式。省略または `null` で停止なし） |
| `image_size` | `vertical` / `horizontal` それぞれの画像サイズ（`width` / `height`。整数、512〜2048、8 の倍数） |
| `reactions` | 処理中 / 成功 / エラー時に付与するリアクション絵文字 |
| `messages` | ボットが返信するメッセージのテンプレート（`dm_not_supported` / `shutdown_in_progress` を含む） |

Unicode 絵文字（例: `⏳`）とカスタム絵文字（例: `<:name:id>`）の両方を `reactions` に指定できます。

## 使い方

### 起動

```bash
python generate_image_bot.py
python generate_image_bot.py --config /path/to/config.json
```

| オプション | 省略時 | 説明 |
|---|---|---|
| `-c` / `--config` | スクリプトと同じディレクトリの `config.json` | 設定ファイルのパス |

### Discord からの操作

操作方法は **メンションメッセージ** と **スラッシュコマンド** の 2 種類があります。

**メンションメッセージ**

ボットにメンションし、キーワード形式でプロンプトを入力します。

```
@bot
loras: my_lora, another_lora
positive: masterpiece, best quality, 1girl,
  (detailed face:1.3), solo
negative: worst quality, bad quality, blurry
image_orientation: vertical
```

- `loras:` は省略可能（省略時は LoRA なしで生成）
- `positive:` / `negative:` は必須
- `image_orientation:` は省略可能（`vertical` または `horizontal`。省略時は `run_workflow/config.json` の既定サイズを使用）
- プロンプトは複数行で記述できます

**スラッシュコマンド**

テキストチャンネルで `/gen_image` を入力するとモーダルが表示されます。各フィールドに入力して送信すると、キーワード形式のメッセージがチャンネルに投稿されて画像生成が始まります。

詳細な使用方法については[USERS_MANUAL](./doc/USERS_MANUAL.md)を参照してください。

## 出力

### Discord への返信

生成成功時は画像ファイルを添付して返信します。

```
[⏳ リアクション付与]
...（生成中）...
[画像ファイルを添付して返信]
[⏳ リアクション削除、✅ リアクション付与]
```

### ログファイル

`log/result_YYYYMMDD_hhmmss.json` に生成試行のログを記録します（成功・失敗ともに）。

```json
{
  "status": "success",
  "timestamp": "2026-04-25T12:34:56",
  "user_id": 123456789,
  "username": "discord_username",
  "loras": ["my_lora"],
  "positive": "masterpiece, 1girl",
  "negative": "worst quality",
  "image_orientation": "vertical",
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

## ファイル構成

```
generate_image_bot/
  generate_image_bot.py  # メインボットスクリプト
  config.json            # ボット設定（トークン・パス等）
  requirements.txt
  log/                   # ログ出力ディレクトリ（自動生成）
    result_YYYYMMDD_hhmmss.json
  test/
    test_generate_image_bot.py
```
