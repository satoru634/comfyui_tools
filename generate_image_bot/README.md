# generate_image_bot

Discord から ComfyUI に画像生成を指示し、生成された画像を Discord に返送するボットです。

内部で `run_workflow` の `WorkflowRunner` / `Wd14TaggerRunner` を使用して画像生成・タグ付けを実行します。

ボットの動作記録（起動・終了・Discord イベント・画像生成結果）は `log/YYYYMMDD/` ディレクトリに JSON 形式で記録されます。

## 機能

- **メンションメッセージ**によるプロンプト入力（キーワード形式: `workflow:` / `positive:` / `negative:` / `loras:` / `image_orientation:`）
- **スラッシュコマンド**（`/gen_image`）によるモーダル入力で画像生成
- **スラッシュコマンド**（`/tag_image`）による画像タグ付け（WD Timm Tagger 使用）
- ワークフローをリクエストごとに指定して切り替え（省略時は `run_workflow/config.json` の `default_workflow` を使用）
- 画像の向き（`vertical` / `horizontal` / `square`）を指定して画像サイズを切り替え（省略時は `run_workflow/config.json` の既定値を使用）
- ユーザー単位のレート制限（30秒クールダウン）
- 複数ユーザーのリクエストを並行処理（同一ユーザーは最大 4 件まで同時送信可能）
- 生成結果を Discord に画像添付で返信
- リアクション絵文字による進捗通知（処理中 / 成功 / エラー）
- 指定した時刻にボットを自動停止（処理中のリクエストを完了してから終了）
- ボット起動・終了・Discord イベント・画像生成結果を `log/YYYYMMDD/` 配下に JSON で記録

## 必要環境

- Python 3.12+
- 起動済みの ComfyUI（`/tag_image` 使用時は `bedovyy/ComfyUI-WD-Timm-Tagger` カスタムノードも必要）
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
| ファイルを添付（Attach Files） | 生成画像・タグ付け画像の送信 |
| リアクションを付ける（Add Reactions） | ⏳ / ✅ / ❌ の付与 |
| スラッシュコマンドを使用 (Use Slash Commands) | `/gen_image` / `/tag_image` の使用 |

## セットアップ

リポジトリルートの[セットアップ](../README.md#セットアップ)を参照してください。

## 設定

**`config.json`** — Discord トークンや ComfyUI の出力先などを記述します。

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "comfyui_output_dir": "C:/path/to/ComfyUI/output",
  "run_workflow_config": "../run_workflow/config.json",
  "shutdown_time": "03:00",
  "reactions": {
    "processing": "⏳",
    "success": "✅",
    "error": "❌"
  },
  "messages": {
    "rate_limit": "リクエストが連続しています。あと {remaining_seconds} 秒待ってから再試行してください。",
    "concurrent_limit": "リクエストの同時処理上限に達しています。しばらくお待ちください。",
    "parse_error": "メッセージの形式が正しくありません:\n{error}",
    "execution_error": "生成に失敗しました:\n{error}",
    "file_too_large": "画像ファイルが大きすぎます（{size_mb} MB）",
    "unexpected_error": "予期しないエラーが発生しました",
    "dm_not_supported": "DM からは使用できません。サーバーのチャンネルで実行してください。",
    "shutdown_in_progress": "ボットはシャットダウン中です。しばらくしてから再試行してください。",
    "tag_image_invalid_type": "画像ファイルのみ対応しています。",
    "tag_image_error": "タグ付けに失敗しました:\n{error}",
    "tag_image_invalid_format": "画像形式が不正です。対応形式: JPEG, PNG, WEBP, GIF, BMP",
    "tag_image_resolution_too_large": "画像の解像度が大きすぎます（最大 4096x4096）",
    "invalid_workflow": "ワークフロー '{workflow}' は存在しません。"
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
| `reactions` | 処理中 / 成功 / エラー時に付与するリアクション絵文字 |
| `messages` | ボットが返信するメッセージのテンプレート |

画像サイズ（`vertical` / `horizontal` / `square`）は `run_workflow/config.json` 内の各ワークフローに定義します。

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

**メンションメッセージ（画像生成）**

ボットにメンションし、キーワード形式でプロンプトを入力します。

```
@bot
workflow: anima
loras: my_lora, another_lora
positive: masterpiece, best quality, 1girl,
  (detailed face:1.3), solo
negative: worst quality, bad quality, blurry
image_orientation: vertical
```

- `workflow:` は省略可能（省略時は `run_workflow/config.json` の `default_workflow` を使用）
- `loras:` は省略可能（省略時は LoRA なしで生成）
- `positive:` / `negative:` は必須
- `image_orientation:` は省略可能（`vertical` / `horizontal` / `square`。省略時は `run_workflow/config.json` の既定サイズを使用）
- プロンプトは複数行で記述できます

**スラッシュコマンド — `/gen_image`（画像生成）**

テキストチャンネルで `/gen_image` を入力するとモーダルが表示されます。各フィールドに入力して送信すると、太字形式のメッセージがチャンネルに投稿されて画像生成が始まります。

**スラッシュコマンド — `/tag_image`（画像タグ付け）**

テキストチャンネルで `/tag_image` を入力し、`image` パラメータに画像ファイルを添付して送信します。WD Timm Tagger でタグを解析し、タグ文字列と元の画像を返信します。

| 制約 | 内容 |
|---|---|
| 対応形式 | `image/*` MIME type かつ JPEG / PNG / WEBP / GIF / BMP |
| ファイルサイズ上限 | 10 MB 未満 |
| 解像度上限 | 4096×4096 以下 |

添付ファイルは Pillow で実フォーマット検証を行い、実行ファイルを画像として偽装したファイルを拒否します。返信時のファイル名は元のファイル名を使用せず、タイムスタンプベースの UUID に変換します。

詳細な使用方法については[USERS_MANUAL](./doc/USERS_MANUAL.md)を参照してください。

## 出力

### Discord への返信（画像生成）

生成成功時は画像ファイルを添付して返信します。

```
[⏳ リアクション付与]
...（生成中）...
[画像ファイルを添付して返信]
[⏳ リアクション削除、✅ リアクション付与]
```

### Discord への返信（タグ付け）

タグ付け成功時はタグ文字列と元の画像を添付して返信します。

```
[⏳ リアクション付与]
...（タグ付け中）...
[タグ文字列 + 元の画像を添付して返信]
[⏳ リアクション削除、✅ リアクション付与]
```

### ログファイル

`log/YYYYMMDD/` 配下に日付ごとのサブディレクトリを作成して以下の 3 種類のログを記録します。

| ファイル名 | 出力契機 |
|---|---|
| `result_hhmmss_ffffff.json` | 画像生成を試みた際（成功・失敗ともに） |
| `system_hhmmss_ffffff.json` | ボット起動・終了時 |
| `discord_hhmmss_ffffff.json` | Discord 接続完了・メンション受信・スラッシュコマンド受信時 |

**生成ログの例:**

```json
{
  "status": "success",
  "timestamp": "2026-04-25T12:34:56",
  "user_id": 123456789,
  "username": "discord_username",
  "workflow": "anima",
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

**システムログの例（起動時）:**

```json
{
  "type": "startup",
  "timestamp": "2026-04-25T12:34:56",
  "shutdown_time": "03:00"
}
```

## テスト

```bash
python -m pytest test/
```

## ファイル構成

```
generate_image_bot/
  generate_image_bot.py  # エントリポイント（起動・再接続ループ）
  config.json            # ボット設定（トークン・パス等）
  doc/
    SPEC.md              # 仕様書（概要・ファイル構成）
    SPEC/                # セクション別仕様書
    USERS_MANUAL.md
  modules/
    image_bot.py         # ImageBot クラス（/gen_image・/tag_image コマンド含む）
    gen_image_modal.py   # GenImageModal クラス（/gen_image モーダル）
    message_parser.py    # MessageParser クラス
    rate_limiter.py      # RateLimiter クラス
    load_config.py       # 設定ファイルの読み込み・バリデーション
    common_lib.py        # ログ書き込み等の共通処理
    const.py             # 定数定義
  log/                   # ログ出力ディレクトリ（自動生成）
    YYYYMMDD/            # 日付ディレクトリ（自動生成）
      result_hhmmss_ffffff.json
      system_hhmmss_ffffff.json
      discord_hhmmss_ffffff.json
  test/
    conftest.py
    test_image_bot.py
    test_gen_image_modal.py
    test_message_parser.py
    test_rate_limiter.py
    test_load_config.py
    test_common_lib.py
    test_helper.py
```
