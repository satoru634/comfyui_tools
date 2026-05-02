# generate_image_bot.py 仕様書 -処理概要-

## レート制限・同時リクエスト制限

### ユーザー単位のレート制限

同一ユーザーから直前のリクエスト受付から **30秒以内** に再リクエストが来た場合は拒否する。**ただし、そのユーザーの処理中リクエストが 1 件以上ある場合はレート制限を適用しない（並行リクエストを妨げないため）。**

- 「リクエスト受付」のタイミングは同時リクエスト上限チェック直前とする。メンションメッセージ経由はパース成功後、モーダル経由はモーダル送信直後に計上する（パース失敗は計上しない）
- 処理中リクエストがある場合は、レート制限チェックと計上をスキップする
- 拒否時はエラーリアクション（`❌`）を付けて、残り待機秒数を含むメッセージを返信する
- 制限はユーザー単位で管理する
- ボット再起動時にリセットされる（永続化しない）

### ユーザー単位の同時リクエスト上限

**同一ユーザーの処理中リクエスト数が 4 件に達している場合、そのユーザーからの新規リクエストを拒否する。**

- 他のユーザーが生成中であっても、別ユーザーや同一ユーザー（上限未満）のリクエストは受け付ける
- カウンタはリクエストの処理開始時（⏳ 付与と同時）にインクリメントし、処理完了時（成功・エラー問わず）にデクリメントする
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
7. 処理中リクエストがない場合のみレート制限チェックを行い、制限中であればエラーリアクション（`❌`）を付けて返信し、処理を中断する
8. 同時リクエスト上限チェックを行い、上限（4件）に達していればエラーリアクション（`❌`）を付けて返信し、処理を中断する
9. 同時リクエストカウンタをインクリメントし、処理中リアクション（`⏳`）をメッセージに付ける
10. `image_orientation` が指定されている場合は `config.json` の `image_size[image_orientation]` を取得し、`WorkflowRunner.execute(loras, prompts, image_size=...)` を呼び出す。省略時は `image_size=None` を渡す（`asyncio.to_thread()` でラップ）
11. 成功時: `comfyui_output_dir` から出力画像ファイルを読み込む。各ファイルについて `Path.resolve()` で正規化したパスが `comfyui_output_dir` 配下に収まることを確認し、サイズが 10MB 未満であることを確認してから Discord に送信し、完了リアクション（`✅`）を付ける
12. エラー時: エラーリアクション（`❌`）を付けてエラーメッセージを返信する
13. 処理完了後（成功・エラー問わず）、同時リクエストカウンタをデクリメントし、処理中リアクション（`⏳`）を削除する

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
| 処理中（ステップ9で付与、ステップ13で削除） | `reactions.processing` | `⏳` |
| 生成成功 | `reactions.success` | `✅` |
| エラー（パース失敗 / レート制限 / 生成ロック / 実行失敗） | `reactions.error` | `❌` |

## アーキテクチャ

### クラス構成

| クラス | 責務 |
|---|---|
| `MessageParser` | メンションメッセージのテキストをパースし `loras` / `prompts` / `image_orientation` を取り出す |
| `RateLimiter` | ユーザーごとのクールダウンとユーザー単位の同時リクエスト上限を管理し、リクエストの受付可否を判定する |
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
