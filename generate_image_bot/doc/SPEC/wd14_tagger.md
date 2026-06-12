# generate_image_bot.py 仕様書 — WD14 Tagger タグ付け機能

## 概要

スラッシュコマンド `/tag_image` で Discord の画像添付を受け取り、
`run_workflow` の `Wd14TaggerRunner` を通じて ComfyUI の WD Timm Tagger ワークフローを実行し、
推論結果をカンマ区切りのタグ文字列として返送する機能。

WD14 Tagger の中核処理（画像アップロード・ワークフロー実行・タグ取得）は
`run_workflow` 側に実装する。本仕様書は Discord ボット固有の部分のみを定義する。

- ワークフロー・クライアント・設定の仕様: [run_workflow WD14 Tagger 仕様書](../../../../run_workflow/doc/SPEC/wd14_tagger.md)

---

## スラッシュコマンド `/tag_image`

### トリガー

テキストチャンネルで `/tag_image` を実行する。

- DM からのコマンドは ephemeral エラーで拒否する
- シャットダウン要求中は ephemeral エラーで拒否する

### 入力

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `image` | `discord.Attachment` | 必須 | タグ付け対象の画像ファイル |

- MIME type が `image/` で始まらない場合は ephemeral エラーで拒否する
- ファイルサイズが `MAX_FILE_SIZE`（10 MB）以上の場合は ephemeral エラーで拒否する
- Pillow による実フォーマット検証に失敗した場合は ephemeral エラーで拒否する
- 画像の解像度が 4096×4096 を超える場合は ephemeral エラーで拒否する

### 処理フロー

1. DM チェック → ephemeral エラーで中断
2. シャットダウン要求中チェック → ephemeral エラーで中断
3. attachment の MIME type チェック → ephemeral エラーで中断
4. attachment のサイズチェック → ephemeral エラーで中断
5. `attachment.read()` で画像バイト列を取得
6. Pillow で実フォーマット検証・解像度検証 → 不正な場合は ephemeral エラーで中断
7. タイムスタンプベース UUID でセーフなファイル名を生成する
8. レート制限チェック（既存 `RateLimiter` を流用、画像生成と同一の制限）
   - 制限中の場合は ❌ リアクション付与 + 残り待機秒数を返信して中断
9. 同時リクエスト上限チェック
   - 上限（4件）に達している場合は ❌ リアクション付与 + メッセージ返信して中断
10. 同時リクエストカウンタをインクリメント
11. ⏳ リアクション付与
12. `asyncio.to_thread` で `Wd14TaggerRunner.tag(image_data, safe_filename)` を呼び出してタグ文字列を取得
13. タグ文字列と添付画像（UUID ファイル名）を元のコマンドへの reply として送信
14. ✅ リアクション付与
15. 同時リクエストカウンタをデクリメント、⏳ リアクション削除

### 出力

```
masterpiece, 1girl, solo, long hair, blue eyes, white dress, ...
```

- カンマ + スペース区切り
- 元の添付画像（UUID ファイル名）と合わせてコマンドメッセージへの reply として送信する

---

## 画像検証

`_validate_image_data(image_data: bytes) -> str` をモジュールレベルの関数として実装する。

### 検証内容

| 検証項目 | 実装 | 制限値 |
|---|---|---|
| 実フォーマット確認 | `PIL.Image.open()` + `img.load()` | JPEG / PNG / WEBP / GIF / BMP のみ許可 |
| 解像度 | `img.width` / `img.height` | 4096×4096 以下 |
| デコンプレッション爆弾対策 | `PIL.Image.MAX_IMAGE_PIXELS` | 50,000,000 px（モジュールロード時に設定） |

- `PIL.Image.load()` で完全デコードを強制し、実行ファイルを画像として偽装したファイルを検出する
- フォーマットが不正または対応外の場合は `ValueError("tag_image_invalid_format")` を送出する
- 解像度が超過した場合は `ValueError("tag_image_resolution_too_large")` を送出する

---

## セーフファイル名生成

`_make_safe_filename(image_format: str) -> str` をモジュールレベルの関数として実装する。

- `uuid.uuid1()`（タイムスタンプベース UUID）を使用して一意なファイル名を生成する
- 拡張子は Pillow が返すフォーマット名（`"JPEG"` → `.jpg` 等）から決定する
- 生成例: `550e8400-e29b-11d4-a716-446655440000.png`

このファイル名を `Wd14TaggerRunner.tag()` と `discord.File()` の両方に渡す。

---

## `ImageBot` への組み込み

`ImageBot.__init__()` で `Wd14TaggerRunner` を初期化して保持する。
`run_workflow_config` が指す `run_workflow/config.json` を渡す。

```python
from run_workflow.modules.wd14_tagger_runner import Wd14TaggerRunner

self.wd14_runner = Wd14TaggerRunner(self.run_workflow_config_path)
```

---

## `messages` テンプレートへの追加

```json
{
  "messages": {
    "tag_image_invalid_type": "画像ファイルのみ対応しています。",
    "tag_image_error": "タグ付けに失敗しました:\n{error}",
    "tag_image_invalid_format": "画像形式が不正です。対応形式: JPEG, PNG, WEBP, GIF, BMP",
    "tag_image_resolution_too_large": "画像の解像度が大きすぎます（最大 4096x4096）"
  }
}
```

| キー | 使用プレースホルダー | 説明 |
|---|---|---|
| `tag_image_invalid_type` | なし | MIME type が `image/*` 以外のファイルが添付された場合の ephemeral 返信 |
| `tag_image_error` | `{error}` | タグ付け処理失敗時のエラー返信 |
| `tag_image_invalid_format` | なし | Pillow 検証に失敗した場合（偽装ファイル・対応外形式）の ephemeral 返信 |
| `tag_image_resolution_too_large` | なし | 解像度が 4096×4096 超の場合の ephemeral 返信 |

---

## エラーハンドリング

既存のエラー一覧に以下を追加する。

| エラー種別 | ボットの挙動 |
|---|---|
| DM からの `/tag_image` コマンド | ephemeral でサポート対象外を通知する |
| シャットダウン要求中の `/tag_image` コマンド | ephemeral でシャットダウン中を通知する |
| attachment の MIME type が `image/*` 以外 | ephemeral で `tag_image_invalid_type` を返信する（❌ リアクションなし） |
| attachment のサイズが 10 MB 以上 | ephemeral で `file_too_large` を返信する（❌ リアクションなし） |
| Pillow 検証失敗（偽装・対応外形式） | ephemeral で `tag_image_invalid_format` を返信する（❌ リアクションなし） |
| 解像度が 4096×4096 超 | ephemeral で `tag_image_resolution_too_large` を返信する（❌ リアクションなし） |
| `Wd14TaggerRunner.tag()` が `ValueError` を送出 | ❌ リアクション + `tag_image_error` を返信する |
| 予期しない例外 | ❌ リアクション + `unexpected_error` を返信する |

---

## ファイル構成の変更

```
generate_image_bot/
  config.json               # messages に 4 件のキーを追加
  modules/
    image_bot.py            # /tag_image ハンドラ追加、画像検証・UUID ファイル名生成を追加
    load_config.py          # messages の新規キーバリデーションを追加
    const.py                # MESSAGE_KEYS に 4 件のキーを追加
  test/
    test_image_bot.py       # /tag_image ハンドラ・_validate_image_data・_make_safe_filename のテストを追加
    test_load_config.py     # 新規メッセージキーのバリデーションテストを追加
```

### アーキテクチャへの追加

```
ImageBot → Wd14TaggerRunner（run_workflow/modules/wd14_tagger_runner.py から import）
ImageBot → _validate_image_data()（モジュールレベル、Pillow 使用）
ImageBot → _make_safe_filename()（モジュールレベル、uuid.uuid1() 使用）
```

---

## テスト

| テストファイル | 追加・変更 | 内容 |
|---|---|---|
| `test/test_image_bot.py` | 追加 | `/tag_image` ハンドラのテスト（DM 拒否・MIME チェック・サイズチェック・フォーマット検証・解像度検証・正常系・エラー系）。`Wd14TaggerRunner` と検証関数を `unittest.mock.patch` でモックする |
| `test/test_image_bot.py` | 追加 | `_validate_image_data` のユニットテスト（有効 PNG・不正バイト列・解像度超過） |
| `test/test_image_bot.py` | 追加 | `_make_safe_filename` のユニットテスト（拡張子・一意性） |
| `test/test_load_config.py` | 追加 | 新規 4 件のメッセージキーのバリデーションテスト |
