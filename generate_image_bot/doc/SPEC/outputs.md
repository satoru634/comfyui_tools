# generate_image_bot.py 仕様書 -出力-

## 出力

- 成功時: 生成画像ファイルを Discord のメッセージに添付して返信する
- 複数画像が生成された場合は、すべてを1件のメッセージにまとめて添付する
- `type` が `output` のファイルのみ送信対象とする（`temp` 等は無視する）
- 送信前に各ファイルのサイズをチェックし、**1ファイルでも 10MB 以上**であればエラーとして扱う
- エラー時: エラー内容を文字列でメッセージ返信する

## ログ出力

### 概要

以下の 3 種類のログを `log/YYYYMMDD/` ディレクトリに JSON 形式で保存する。
ログはデバッグ・運用監視を目的とし、ユーザー非公開の内部記録として使用する。

| ログ種別 | ファイル名 | 出力契機 |
|---|---|---|
| 生成ログ | `result_hhmmss_ffffff.json` | 画像生成を試みた際（成功・失敗問わず） |
| システムログ | `system_hhmmss_ffffff.json` | ボット起動・終了時 |
| Discord ログ | `discord_hhmmss_ffffff.json` | Discord 接続完了・メンション受信・スラッシュコマンド受信時 |

- `log/YYYYMMDD/` ディレクトリが存在しない場合は自動生成する。
- ファイル名はイベント発生時刻から生成する（`datetime.now()` ベース）。

---

### 生成ログ (`result_hhmmss_ffffff.json`)

#### ログファイルパス

```
generate_image_bot/log/YYYYMMDD/result_hhmmss_ffffff.json
```

#### ログ出力タイミング

| 状況 | ログ出力 |
|---|---|
| 生成成功 | あり（status: success） |
| `WorkflowRunner.execute()` が ValueError | あり（status: error） |
| 予期しない例外 | あり（status: error） |
| `_resolve_output_paths()` で ValueError | あり（status: error） |
| パースエラー | なし（生成を開始していないため） |
| レート制限 | なし（生成を開始していないため） |

#### ログ JSON フォーマット

```json
{
  "status": "success",
  "timestamp": "2026-04-25T12:34:56",
  "user_id": 123456789,
  "username": "discord_username",
  "workflow": "anima",
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
| `workflow` | string \| null | 使用したワークフロー名（省略時は null） |
| `loras` | array | 使用 LoRA 名のリスト |
| `positive` | string | ポジティブプロンプト |
| `negative` | string | ネガティブプロンプト |
| `image_orientation` | string \| null | 画像の向き（`"vertical"` / `"horizontal"` / `"square"` / `null`。省略時は null） |
| `outputs` | array | `WorkflowRunner.execute()` の戻り値（エラー時は空配列またはエラー前の出力） |
| `error` | string \| null | エラーメッセージ（成功時は null） |

---

### システムログ (`system_hhmmss_ffffff.json`)

#### ログファイルパス

```
generate_image_bot/log/YYYYMMDD/system_hhmmss_ffffff.json
```

#### ログ出力タイミング

| 状況 | `type` |
|---|---|
| ボット起動（`main()` でボット起動直前） | `"startup"` |
| ボット終了（`main()` で `bot.run()` 正常終了後） | `"shutdown"` |

#### ログ JSON フォーマット（startup）

```json
{
  "type": "startup",
  "timestamp": "2026-05-03T12:34:56",
  "shutdown_time": "18:00"
}
```

#### ログ JSON フォーマット（shutdown）

```json
{
  "type": "shutdown",
  "timestamp": "2026-05-03T18:00:00",
  "reason": "scheduled"
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `type` | string | `"startup"` または `"shutdown"` |
| `timestamp` | string | ISO 8601 形式（秒精度） |
| `shutdown_time` | string \| null | 設定された停止時刻（`"HH:MM"` 形式）。未設定時は `null`（startup のみ） |
| `reason` | string | 終了理由（`"scheduled"`: 定刻、`"signal"`: 外部シグナル）（shutdown のみ） |

---

### Discord ログ (`discord_hhmmss_ffffff.json`)

#### ログファイルパス

```
generate_image_bot/log/YYYYMMDD/discord_hhmmss_ffffff.json
```

#### ログ出力タイミング

| 状況 | `type` |
|---|---|
| Discord への接続完了（`on_ready`） | `"discord_ready"` |
| ボットへのメンション受信（`on_message`） | `"discord_message"` |
| スラッシュコマンド受信（`/gen_image`） | `"discord_slash_command"` |

DM・自分自身のメッセージなど無視するケースでもログを出力しない。
処理対象となったイベントのみを記録する。

#### ログ JSON フォーマット（discord_ready）

```json
{
  "type": "discord_ready",
  "timestamp": "2026-05-03T12:34:57",
  "bot_user_id": 123456789,
  "bot_username": "BotName"
}
```

#### ログ JSON フォーマット（discord_message / discord_slash_command）

```json
{
  "type": "discord_message",
  "timestamp": "2026-05-03T12:35:00",
  "user_id": 987654321,
  "username": "user_name",
  "channel_id": 111111111,
  "guild_id": 222222222
}
```

| フィールド | 型 | 説明 |
|---|---|---|
| `type` | string | `"discord_ready"` / `"discord_message"` / `"discord_slash_command"` |
| `timestamp` | string | ISO 8601 形式（秒精度） |
| `bot_user_id` | integer | ボット自身の Discord ユーザー ID（discord_ready のみ） |
| `bot_username` | string | ボット自身のユーザー名（discord_ready のみ） |
| `user_id` | integer | イベント発火ユーザーの Discord ユーザー ID（discord_message / discord_slash_command） |
| `username` | string | イベント発火ユーザーの Discord ユーザー名（discord_message / discord_slash_command） |
| `channel_id` | integer | チャンネル ID（discord_message / discord_slash_command） |
| `guild_id` | integer | サーバー ID（discord_message / discord_slash_command） |
