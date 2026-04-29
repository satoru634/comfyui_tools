# CLAUDE.md — comfyui_tools

このファイルは、リポジトリ内のコードを扱う際に Claude Code (claude.ai/code) へ指針を提供します。

## 言語設定
- 常に日本語で会話する
- コメントも日本語で記述する
- エラーメッセージの説明も日本語で行う
- ドキュメントも日本語で生成する

## プロジェクト概要

ComfyUI 関連の Python ツール群。各ツールはサブディレクトリとして独立している。

| ツール | 説明 | 詳細 |
|---|---|---|
| `run_workflow/` | ComfyUI のワークフローを Python から自動実行するツール | [SPEC.md](run_workflow/doc/SPEC.md) |
| `generate_image_bot/` | Discord のメンションで ComfyUI に画像生成を指示し、生成された画像を返送する Discord ボット | [SPEC.md](generate_image_bot/doc/SPEC.md) |

## テスト

- テストの実装はpytestで行う
- ComfyUI への実際の通信は `unittest.mock` でモックする
- テスト関数・クラス名は **英語** で記述する
- 新機能を実装したら必ず対応するテストも追加し、全件パスを確認してから完了とする
- テスト実装後はblackフォーマッターでフォーマットする。

## 開発ルール

- 関数は 30 行以内を目安にする。
- 関連する機能はクラスにまとめる。
- 実装後はblackフォーマッターでフォーマットする。
