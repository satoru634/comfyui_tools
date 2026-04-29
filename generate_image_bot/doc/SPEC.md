# generate_image_bot.py 仕様書

## 概要

Discord のメンションで ComfyUI に画像生成を指示し、生成された画像を Discord に返送するボット。
`run_workflow/run_workflow.py` の `WorkflowRunner` を import して利用する。

画像生成のトリガーは以下の 2 種類：

- **メンションメッセージ**: ボットへのメンションにキーワード形式でプロンプトを付けて送信する（既存機能）
- **スラッシュコマンド** (`/gen_image`): コマンドを実行するとモーダルが開き、フォームに入力して送信する

## ファイル構成

```
comfyui_tools/
  run_workflow/
    run_workflow.py        # 画像生成エンジン（import して使用）
    config.json            # ComfyUI 接続設定・LoRAマッピング
    templates/             # ワークフローテンプレート
  generate_image_bot/
    generate_image_bot.py  # メインボットスクリプト
    config.json            # ボット設定（トークン・パス等）
    SPEC.md                # 本ファイル
    requirements.txt       # 依存ライブラリ
    log/                   # ログ出力ディレクトリ（自動生成）
      result_YYYYMMDD_hhmmss.json
    test/
      test_generate_image_bot.py
```

## 設定ファイル

### config.json

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

| キー | 説明 |
|---|---|
| `discord_token` | Discord Bot トークン |
| `comfyui_output_dir` | ComfyUI の output フォルダへの絶対パス |
| `run_workflow_config` | `run_workflow/config.json` へのパス（相対 or 絶対） |
| `shutdown_time` | ボットを停止する時刻（後述）。省略または `null` で停止なし |
| `image_size` | 画像の向きごとの生成サイズ（後述） |
| `reactions` | ボットが付けるリアクション絵文字（後述） |
| `messages` | ボットが返信するメッセージのテンプレート（後述） |

### image_size

`image_orientation` の値に応じて使用する画像サイズを定義する。

| キー | 説明 |
|---|---|
| `vertical` | 縦向き（`image_orientation: vertical`）のときに使用するサイズ |
| `horizontal` | 横向き（`image_orientation: horizontal`）のときに使用するサイズ |

- 各値は `{"width": <整数>, "height": <整数>}` の形式で記述する。
- バリデーションルールは `run_workflow` の `image_size` と同一（512〜2048 の整数、8 の倍数）。
- `image_orientation` が省略された場合、`image_size` は `run_workflow/config.json` の `default_image_size` が使用される（このボット側の `image_size` は参照しない）。

### shutdown_time

| 設定値 | 動作 |
|---|---|
| 省略 または `null` | 自動停止しない |
| `"hh:mm"` 形式の文字列（例: `"03:00"`） | 毎日その時刻にボットを停止する |

- 曜日・日付は考慮しない（毎日同じ時刻に停止する）
- 停止時刻になると新規リクエストの受付を停止し、処理中のリクエストが完了してからボットを終了する
- 形式が不正な場合（`hh:mm` 以外、または存在しない時刻）は起動時にエラーとなる
- ボット起動時に停止時刻をコンソールに出力する

### reactions

| キー | デフォルト | 説明 |
|---|---|---|
| `processing` | `⏳` | 処理中に付与し、処理完了後に削除するリアクション |
| `success` | `✅` | 生成成功時に付与するリアクション |
| `error` | `❌` | エラー時に付与するリアクション |

Unicode 絵文字（例: `⏳`）とカスタム絵文字（例: `<:name:id>`）の両方を指定できる。

### messages テンプレート

`messages` の各値は Python の `str.format()` 形式で記述し、プレースホルダーは以下の通り。

| キー | 使用プレースホルダー | 説明 |
|---|---|---|
| `rate_limit` | `{remaining_seconds}` | レート制限中の返信。残り待機秒数を埋め込む |
| `generating` | なし | グローバルロック中（生成中）の返信 |
| `parse_error` | `{error}` | フォーマット不正時の返信。パースエラー内容を埋め込む |
| `execution_error` | `{error}` | ワークフロー実行失敗時の返信。エラー内容を埋め込む（内部ファイルパスが含まれる場合があるため、公開サーバーでは固定文字列への変更を推奨） |
| `file_too_large` | `{size_mb}` | ファイルサイズ超過時の返信。ファイルサイズ（MB・小数点1桁）を埋め込む |
| `unexpected_error` | なし | 予期しない例外発生時の返信 |
| `dm_not_supported` | なし | スラッシュコマンドを DM から実行した場合の ephemeral 返信 |
| `shutdown_in_progress` | なし | シャットダウン要求中にスラッシュコマンドを実行した場合の ephemeral 返信 |

プレースホルダーを省略した場合、そのまま固定文字列として使用する。
プレースホルダーの名前は変更・削除不可。未知のプレースホルダーを追加してもエラーにはならない（無視される）。

## 入力インターフェース

### メンションメッセージ

#### トリガー

ボットへのメンションを含むメッセージ。

#### 入力フォーマット

キーワード形式を採用する。

```
@bot
loras: lora1, lora2
positive: masterpiece, best quality, 1girl,
  (detailed face:1.3), solo
negative: worst quality, bad quality,
  blurry
image_orientation: vertical
```

- `loras:` 行は省略可能（省略時は LoRA なしで実行）
- `positive:` / `negative:` は必須
- `image_orientation:` 行は省略可能（省略時は `run_workflow/config.json` の `default_image_size` を使用）
- `image_orientation:` の値は `vertical`（縦）または `horizontal`（横）のみ受け付ける
- 各キーワードは **行頭** に置く（`キーワード:` の形式）
- プロンプトは複数行にわたって記述できる（次のキーワード行が来るまで継続）

#### パース規則

1. メッセージ本文からメンション部分（`<@...>`）を除去する
2. 残りのテキストを行単位に分割する
3. 行が `loras:` / `positive:` / `negative:` / `image_orientation:` のいずれかで始まる場合、そのキーワードの値収集を開始する
4. それ以外の行は、直前のキーワードの値に改行付きで追記する（継続行）
5. 収集した各値は前後の空白・改行をトリム（`strip()`）する

**`:` の扱い**

キーワードの判定は行頭のパターンのみで行う。
値の中に `:` が含まれていても（例: `(detailed face:1.3)`）継続行として扱われるため、強調構文は問題なく使用できる。

```
# 正しく動作する例
positive: masterpiece, (detailed face:1.3), (eyes:1.2)
```

#### 入力バリデーション

`run_workflow.py` の `_validate_loras` / `_validate_prompts` がバリデーションを担うため、
ボット側は以下のみを担当する。

| 検証内容 | ボット側 |
|---|---|
| フォーマットのパース失敗（必須キーの欠落等） | ボット側で検出しエラーメッセージ返信 |
| `image_orientation` の値が `vertical` / `horizontal` 以外 | ボット側で検出しエラーメッセージ返信 |
| LoRA 名・プロンプトの内容検証 | `WorkflowRunner.execute()` に委譲 |

---

### スラッシュコマンド（`/gen_image`）

#### トリガー

テキストチャンネルで `/gen_image` を入力する。

DM からのコマンドは無視する（リアクション・返信なし）。

#### モーダル

コマンド実行時に `GenImageModal` が表示される。フィールドは以下の通り。

| フィールド名 | ラベル | 入力スタイル | 必須 |
|---|---|---|---|
| `loras` | LoRAs | 1行テキスト | 省略可 |
| `positive` | Positive | 複数行テキスト | 必須 |
| `negative` | Negative | 複数行テキスト | 必須 |
| `image_orientation` | Image Orientation (vertical / horizontal) | 1行テキスト | 省略可 |

#### モーダル送信後の動作

1. 入力値からキーワード形式のメッセージを生成してチャンネルに送信する（`loras` が空の場合は `loras:` 行を省略、`image_orientation` が空の場合は `image_orientation:` 行を省略）
2. 送信されたメッセージを起点として、メンションメッセージと同じ生成フローを実行する

**返信メッセージの例（loras あり、image_orientation あり）**

```
loras: my_lora, another_lora
positive: masterpiece, best quality, 1girl
negative: worst quality, bad quality
image_orientation: vertical
```

**返信メッセージの例（loras なし、image_orientation なし）**

```
positive: masterpiece, best quality, 1girl
negative: worst quality, bad quality
```

#### 入力バリデーション

モーダル経由では `MessageParser` を経由せず入力値を直接 `parsed` に組み立てるため、パースエラーは発生しない。
`image_orientation` の値チェック（`vertical` / `horizontal` 以外は弾く）はボット側で行う。
LoRA 名・プロンプトの内容検証は `WorkflowRunner.execute()` に委譲する（メンションメッセージと同様）。

## レート制限・生成ロック

### ユーザー単位のレート制限

同一ユーザーから直前のリクエスト受付から **30秒以内** に再リクエストが来た場合は拒否する。

- 「リクエスト受付」のタイミングはグローバルロックチェック直前とする。メンションメッセージ経由はパース成功後、モーダル経由はモーダル送信直後に計上する（パース失敗は計上しない）
- 拒否時はエラーリアクション（`❌`）を付けて、残り待機秒数を含むメッセージを返信する
- 制限はユーザー単位で管理する
- ボット再起動時にリセットされる（永続化しない）

### グローバル生成ロック

**いずれかのユーザーの生成が進行中である間は、すべてのユーザーからの新規リクエストを拒否する。**

- ロックは生成開始時（⏳ 付与と同時）にセットし、生成完了時（成功・エラー問わず）に解除する
- 拒否時はエラーリアクション（`❌`）を付けてメッセージを返信する
- ボット再起動時にリセットされる（永続化しない）

## 処理フロー

### メンションメッセージ経由

1. `on_message` でボットへのメンションを検出する
2. 自分自身のメッセージには反応しない
3. DM（`message.guild is None`）の場合は無視する（リアクション・返信なし）
4. シャットダウン要求中の場合は無視する（リアクション・返信なし）
5. メッセージ本文をパースし、`loras` / `positive` / `negative` / `image_orientation` を取り出す
6. パース失敗時はエラーリアクション（`❌`）を付けてエラーメッセージを返信し、処理を中断する
7. レート制限チェックを行い、制限中であればエラーリアクション（`❌`）を付けて返信し、処理を中断する
8. グローバルロックチェックを行い、生成中であればエラーリアクション（`❌`）を付けて返信し、処理を中断する
9. グローバルロックをセットし、処理中リアクション（`⏳`）をメッセージに付ける
10. `image_orientation` が指定されている場合は `config.json` の `image_size[image_orientation]` を取得し、`WorkflowRunner.execute(loras, prompts, image_size=...)` を呼び出す。省略時は `image_size=None` を渡す（`asyncio.to_thread()` でラップ）
11. 成功時: `comfyui_output_dir` から出力画像ファイルを読み込む。各ファイルについて `Path.resolve()` で正規化したパスが `comfyui_output_dir` 配下に収まることを確認し、サイズが 10MB 未満であることを確認してから Discord に送信し、完了リアクション（`✅`）を付ける
12. エラー時: エラーリアクション（`❌`）を付けてエラーメッセージを返信する
13. 処理完了後（成功・エラー問わず）、グローバルロックを解除し、処理中リアクション（`⏳`）を削除する

### スラッシュコマンド（`/gen_image`）経由

1. `/gen_image` コマンドを受信する
2. DM（`interaction.guild is None`）の場合は ephemeral メッセージでサポート対象外を通知し、処理を中断する
3. シャットダウン要求中の場合は ephemeral メッセージで通知し、処理を中断する
4. `interaction.response.send_modal(GenImageModal(...))` でモーダルを表示する
5. ユーザーが入力して送信すると `GenImageModal.on_submit` が呼ばれる
6. モーダルの入力値から `parsed`（`loras` / `positive` / `negative` / `image_orientation`）を直接組み立てる
7. キーワード形式のメッセージを `interaction.response.send_message()` でチャンネルに送信する
8. `interaction.original_response()` で送信されたメッセージオブジェクトを取得する
9. 以降はメンションメッセージ経由のステップ 7〜13 と同じ（`message` の代わりに取得したメッセージオブジェクトを使用）

## リアクション仕様

使用する絵文字は `config.json` の `reactions` で定義する。

| タイミング | config キー | デフォルト |
|---|---|---|
| 処理中（ステップ8で付与、ステップ12で削除） | `reactions.processing` | `⏳` |
| 生成成功 | `reactions.success` | `✅` |
| エラー（パース失敗 / レート制限 / 生成ロック / 実行失敗） | `reactions.error` | `❌` |

## 出力

- 成功時: 生成画像ファイルを Discord のメッセージに添付して返信する
- 複数画像が生成された場合は、すべてを1件のメッセージにまとめて添付する
- `type` が `output` のファイルのみ送信対象とする（`temp` 等は無視する）
- 送信前に各ファイルのサイズをチェックし、**1ファイルでも 10MB 以上**であればエラーとして扱う
- エラー時: エラー内容を文字列でメッセージ返信する

## ログ出力

### 概要

画像生成を試みた際（グローバルロック取得後）のリクエスト結果を `log/` ディレクトリに JSON 形式で保存する。
ログはデバッグ・運用監視を目的とし、ユーザー非公開の内部記録として使用する。

### ログファイルパス

```
generate_image_bot/log/result_YYYYMMDD_hhmmss.json
```

- `log/` ディレクトリが存在しない場合は自動生成する。
- ファイル名はリクエスト処理時刻から生成する（`datetime.now()` ベース）。

### ログ出力タイミング

| 状況 | ログ出力 |
|---|---|
| 生成成功 | あり（status: success） |
| `WorkflowRunner.execute()` が ValueError | あり（status: error） |
| 予期しない例外 | あり（status: error） |
| `_resolve_files()` で ValueError | あり（status: error） |
| パースエラー | なし（生成を開始していないため） |
| レート制限 | なし（生成を開始していないため） |
| グローバルロック中 | なし（生成を開始していないため） |

### ログ JSON フォーマット

```json
{
  "status": "success",
  "timestamp": "2026-04-25T12:34:56",
  "user_id": 123456789,
  "username": "discord_username",
  "loras": ["lora1"],
  "positive": "masterpiece, 1girl",
  "negative": "worst quality",
  "image_orientation": "vertical",
  "outputs": [{"filename": "output.png", "subfolder": "", "type": "output"}],
  "error": null
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `status` | string | `"success"` または `"error"` |
| `timestamp` | string | ISO 8601 形式（秒精度） |
| `user_id` | integer | Discord ユーザー ID |
| `username` | string | Discord ユーザー名 |
| `loras` | array | 使用 LoRA 名のリスト |
| `positive` | string | ポジティブプロンプト |
| `negative` | string | ネガティブプロンプト |
| `image_orientation` | string \| null | 画像の向き（`"vertical"` / `"horizontal"` / `null`。省略時は null） |
| `outputs` | array | `WorkflowRunner.execute()` の戻り値（エラー時は空配列またはエラー前の出力） |
| `error` | string \| null | エラーメッセージ（成功時は null） |

## エラーハンドリング

| エラー種別 | ボットの挙動 |
|---|---|
| DM からのメンションメッセージ | 無視する（リアクション・返信なし） |
| DM からのスラッシュコマンド | ephemeral でサポート対象外を通知する |
| シャットダウン要求中のメンションメッセージ | 無視する（リアクション・返信なし） |
| シャットダウン要求中のスラッシュコマンド | ephemeral でシャットダウン中を通知する |
| フォーマット不正（必須キー欠落 等） | `❌` + エラー内容を返信 |
| `image_orientation` の値が `vertical` / `horizontal` 以外 | `❌` + エラー内容を返信 |
| レート制限（30秒以内の再リクエスト） | `❌` + 残り待機秒数を返信 |
| グローバルロック中（生成中） | `❌` + 生成中メッセージを返信 |
| `WorkflowRunner.execute()` が ValueError | `❌` + エラー内容を返信 |
| 出力画像ファイルが存在しない | `❌` + エラー内容を返信 |
| 出力ファイルのパスが `comfyui_output_dir` 外を指す | `❌` + エラー内容を返信 |
| 出力画像が 10MB 以上 | `❌` + 「画像ファイルが大きすぎます（XX MB）」を返信 |
| 予期しない例外 | `❌` + 「予期しないエラーが発生しました」を返信 |

## アーキテクチャ

### クラス構成

| クラス | 責務 |
|---|---|
| `MessageParser` | メンションメッセージのテキストをパースし `loras` / `prompts` / `image_orientation` を取り出す |
| `RateLimiter` | ユーザーごとのクールダウンとグローバル生成ロックを管理し、リクエストの受付可否を判定する |
| `GenImageModal` | `discord.ui.Modal` を継承し、`/gen_image` コマンドで表示するモーダルのフィールド定義と `on_submit` 処理を担当する |
| `ImageBot` | `discord.Client` を継承し、`on_message`・スラッシュコマンドのイベントを処理するメインクラス。停止時刻のウォッチャータスクも管理する |

### 依存関係

```
ImageBot → MessageParser
ImageBot → RateLimiter
ImageBot → WorkflowRunner（run_workflow.py から import）
ImageBot → GenImageModal（コンストラクタ引数で bot 自身の参照を渡す）
GenImageModal → ImageBot（生成フローの呼び出し）
```

### スラッシュコマンドの登録

`ImageBot` は `setup_hook()` 内で `discord.app_commands.CommandTree` に `/gen_image` コマンドを追加し、`tree.sync()` でグローバル同期する。

### 非同期対応

`WorkflowRunner.execute()` は同期処理（`asyncio.run()` を内部使用）のため、
`discord.py` のイベントループをブロックしないよう `asyncio.to_thread()` でラップする。

## 開発ルール

- `discord_token` は `config.json` に記述し、ソースコードにハードコードしない。
- `config.json` は `.gitignore` に追加し、リポジトリに含めない。
- 新機能を追加する場合は `ImageBot` → `MessageParser` / `RateLimiter` → `WorkflowRunner` の依存方向を崩さない。
- 関数は 30 行以内を目安にする。
- メッセージテンプレートの展開は `str.format_map()` を使い、既知のキーのみを渡す辞書を与えること（`str.format()` は `{obj.__class__}` 等の属性アクセスを展開するため使用しない）。

## 依存ライブラリ

- `discord.py` — Discord API クライアント
- `run_workflow`（ローカル import）

## 実行

```bash
python generate_image_bot.py
python generate_image_bot.py --config /path/to/config.json
```

| オプション | 省略時 | 説明 |
|---|---|---|
| `-c` / `--config` | スクリプトと同じディレクトリの `config.json` | 設定ファイルのパス |

## 使用例

### 通常リクエスト

```
ユーザー: @bot
          loras: my_lora, another_lora
          positive: masterpiece, best quality, 1girl,
            (detailed face:1.3), solo
          negative: worst quality, bad quality, blurry
          image_orientation: vertical

ボット:   [⏳ リアクション付与]
          ...（生成中）...
          [画像ファイルを添付して返信]
          [⏳ リアクション削除、✅ リアクション付与]
```

### レート制限時

```
ユーザー: @bot
          positive: 1girl
          negative: worst quality

ボット:   [❌ リアクション付与]
          リクエストが連続しています。あと 18 秒待ってから再試行してください。
```

### スラッシュコマンド経由

```
ユーザー: /gen_image
          → GenImageModal が表示される

          [LoRAs]              my_lora, another_lora
          [Positive]           masterpiece, best quality, 1girl
          [Negative]           worst quality, bad quality
          [Image Orientation]  vertical

          → 送信ボタンを押す

ボット:   loras: my_lora, another_lora
          positive: masterpiece, best quality, 1girl
          negative: worst quality, bad quality
          image_orientation: vertical
          [⏳ リアクション付与]
          ...（生成中）...
          [画像ファイルを添付して返信]
          [⏳ リアクション削除、✅ リアクション付与]
```
