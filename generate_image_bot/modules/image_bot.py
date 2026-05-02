"""Discord ボット: 画像生成ボットの実装"""

import asyncio
import math
import sys
from datetime import datetime
from pathlib import Path

import discord

from modules.common_lib import write_log
from modules.load_config import parse_shutdown_time
from modules.message_parser import MessageParser
from modules.gen_image_modal import GenImageModal
from modules.rate_limiter import RateLimiter

from modules.const import (
    MAX_FILE_SIZE,
)

# generate_image_bot と run_workflow が同名の modules パッケージを持つため、
# インポート前後で sys.modules を退避・復元して名前空間の衝突を防ぐ
_bot_modules = {
    k: v for k, v in sys.modules.items() if k == "modules" or k.startswith("modules.")
}
for _k in list(_bot_modules):
    del sys.modules[_k]
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "run_workflow"))
from run_workflow import WorkflowRunner  # noqa: E402

sys.modules.update(_bot_modules)
del _bot_modules

# ── Discord ボット ─────────────────────────────────────────────────────────────


class ImageBot(discord.Client):
    def __init__(self, config: dict, runner=None):
        """設定を受け取り、各コンポーネントを初期化する。
        runner を省略すると config の run_workflow_config から WorkflowRunner を生成する。"""
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self._config = config
        self._parser = MessageParser()
        self._limiter = RateLimiter()
        # comfyui_output_dir はパストラバーサル判定の基準になるため resolve() で正規化する
        self._output_dir = Path(config["comfyui_output_dir"]).resolve()
        # ログディレクトリは generate_image_bot/ 直下の log/ に固定する
        self._log_dir = Path(__file__).parent.parent / "log"
        self._runner = runner or WorkflowRunner(config["run_workflow_config"])
        # shutdown_time が設定されている場合はタプル (hour, minute) で保持する
        st = config.get("shutdown_time")
        self._shutdown_time: tuple[int, int] | None = (
            parse_shutdown_time(st) if st else None
        )
        # シャットダウン要求フラグ（True になると新規リクエストを受け付けない）
        self._shutdown_requested = False

    async def setup_hook(self):
        """on_ready より前に呼び出される初期化フック。スラッシュコマンドを登録する。"""
        self.tree = discord.app_commands.CommandTree(self)
        self.tree.command(name="gen_image", description="ComfyUI で画像を生成します")(
            self._gen_image_command
        )
        await self.tree.sync()

    async def on_ready(self):
        """ボット起動後の処理。シャットダウン時刻が設定されている場合はウォッチャーを起動する。"""
        print(f"ボット起動: {self.user}")
        if self._shutdown_time is not None:
            h, m = self._shutdown_time
            print(f"停止時刻: {h:02d}:{m:02d}")
            asyncio.create_task(self._shutdown_watcher())

    async def on_message(self, message: discord.Message):
        """メッセージ受信時のエントリポイント。対象外のメッセージを早期リターンで除外する。"""
        if message.author == self.user:
            # 自分自身のメッセージには反応しない（無限ループ防止）
            return
        if message.guild is None:
            # DM は無視する（リアクション・返信なし）
            return
        if self.user not in message.mentions:
            return
        await self._handle_request(message)

    async def _gen_image_command(self, interaction: discord.Interaction):
        """/gen_image コマンドのエントリポイント。DM での使用を拒否し、モーダルを表示する。"""
        if interaction.guild is None:
            await interaction.response.send_message(
                self._fmt("dm_not_supported"), ephemeral=True
            )
            return
        if self._shutdown_requested:
            await interaction.response.send_message(
                self._fmt("shutdown_in_progress"), ephemeral=True
            )
            return
        await interaction.response.send_modal(GenImageModal(self))

    async def _shutdown_watcher(self):
        """30秒ごとに現在時刻を確認し、停止時刻に達したらシャットダウンを開始する。
        処理中のリクエストが完了してから close() を呼び出す。"""
        triggered_minute = None
        while not self.is_closed():
            await asyncio.sleep(30)
            now = datetime.now()
            current_minute = (now.hour, now.minute)
            # 同じ分に複数回トリガーしないよう triggered_minute で管理する
            if (
                current_minute == self._shutdown_time
                and current_minute != triggered_minute
            ):
                triggered_minute = current_minute
                self._shutdown_requested = True
                # 実行中の生成が完了するまで待機してから終了する
                while self._limiter.has_active():
                    await asyncio.sleep(1)
                await self.close()
                return

    async def _handle_request(self, message: discord.Message):
        """メンションメッセージ経由: パースして共通生成フローへ渡す。"""
        # シャットダウン要求中は新規リクエストを無視する
        if self._shutdown_requested:
            return
        # パースに失敗した場合はレート制限を計上しない
        try:
            parsed = self._parser.parse(message.content)
        except ValueError as e:
            await self._reply_error(message, self._fmt("parse_error", error=str(e)))
            return
        await self.process_generation(message, parsed, message.author)

    async def process_generation(self, message, parsed: dict, user):
        """レート制限 → 同時リクエスト上限チェック → 生成 の共通フロー。メンション・モーダル両経路で使用。"""
        # 処理中リクエストがない場合のみレート制限を適用する（並行リクエストはスキップ）
        if not self._limiter.has_user_active(user.id):
            remaining = self._limiter.check_user(user.id)
            if remaining > 0:
                secs = math.ceil(remaining)
                await self._reply_error(
                    message, self._fmt("rate_limit", remaining_seconds=secs)
                )
                return
            self._limiter.record_request(user.id)

        # 同一ユーザーの同時リクエスト上限チェック（上限は MAX_CONCURRENT 件）
        if self._limiter.check_concurrent(user.id):
            await self._reply_error(message, self._fmt("concurrent_limit"))
            return

        # カウンタをインクリメントし、処理中リアクションを付与する
        self._limiter.increment_active(user.id)
        await message.add_reaction(self._config["reactions"]["processing"])
        try:
            await self._generate_and_send(message, parsed, user)
        finally:
            # 成功・失敗を問わず必ずカウンタのデクリメントと処理中リアクションの削除を行う
            self._limiter.decrement_active(user.id)
            try:
                await message.remove_reaction(
                    self._config["reactions"]["processing"], self.user
                )
            except discord.HTTPException:
                pass

    async def _generate_and_send(self, message, parsed: dict, user):
        """WorkflowRunner で画像を生成し、出力ファイルを Discord に送信する。
        各終了パスでログを書き出す。"""
        prompts = {"positive": parsed["positive"], "negative": parsed["negative"]}
        user_id = user.id
        username = user.name

        # image_orientation が指定されている場合は config の image_size から対応サイズを取得する
        orientation = parsed.get("image_orientation")
        image_size = self._config["image_size"][orientation] if orientation else None

        # WorkflowRunner.execute() は同期処理のため to_thread でイベントループをブロックしない
        try:
            outputs = await asyncio.to_thread(
                self._runner.execute, parsed["loras"], prompts, image_size
            )
        except ValueError as e:
            # LoRA 名やプロンプトの検証エラー等、想定内の失敗
            write_log(self._log_dir, user_id, username, parsed, "error", [], str(e))
            await self._reply_error(message, self._fmt("execution_error", error=str(e)))
            return
        except Exception as e:
            # 接続断など予期しない例外はユーザーには詳細を見せない
            write_log(self._log_dir, user_id, username, parsed, "error", [], str(e))
            await self._reply_error(message, self._fmt("unexpected_error"))
            return

        # 出力ファイルの存在・パス・サイズを検証する
        try:
            file_paths = self._resolve_output_paths(outputs)
        except ValueError as e:
            write_log(
                self._log_dir, user_id, username, parsed, "error", outputs, str(e)
            )
            await self._reply_error(message, str(e))
            return

        write_log(self._log_dir, user_id, username, parsed, "success", outputs, None)
        try:
            await message.channel.send(
                files=[discord.File(str(p)) for p in file_paths], reference=message
            )
        except discord.HTTPException:
            # 参照先メッセージが削除された場合は参照なしで投稿する
            # HTTPException 後に discord.File が閉じられるため再生成する
            await message.channel.send(files=[discord.File(str(p)) for p in file_paths])
        try:
            await message.add_reaction(self._config["reactions"]["success"])
        except discord.HTTPException:
            pass

    def _resolve_output_paths(self, outputs: list) -> list:
        """outputs リストから type が output のファイルを検証し Path のリストを返す。"""
        paths = []
        for item in outputs:
            # type が output 以外（temp 等）はスキップする
            if item.get("type") != "output":
                continue
            path = (
                self._output_dir / item.get("subfolder", "") / item["filename"]
            ).resolve()
            # resolve() 後に output_dir 配下に収まるか確認してパストラバーサルを防ぐ
            if not path.is_relative_to(self._output_dir):
                raise ValueError(f"出力ファイルのパスが不正です: {item['filename']}")
            if not path.exists():
                raise ValueError(f"出力ファイルが見つかりません: {item['filename']}")
            size = path.stat().st_size
            if size >= MAX_FILE_SIZE:
                size_mb = size / (1024 * 1024)
                raise ValueError(self._fmt("file_too_large", size_mb=f"{size_mb:.1f}"))
            paths.append(path)
        return paths

    async def _reply_error(self, message: discord.Message, text: str):
        """エラーリアクションを付与してメッセージに返信する。"""
        await message.add_reaction(self._config["reactions"]["error"])
        await message.reply(text)

    def _fmt(self, key: str, **kwargs) -> str:
        """config の messages テンプレートを展開する。
        format_map を使うことで未知のキーを無視し、属性アクセス形式の展開も防ぐ。"""
        return self._config["messages"][key].format_map(kwargs)
