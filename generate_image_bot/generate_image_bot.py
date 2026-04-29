"""Discord ボット: ComfyUI 画像生成"""

import argparse
import asyncio
import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp
import discord

# run_workflow は同リポジトリの兄弟ディレクトリにあるためパスを追加する
sys.path.insert(0, str(Path(__file__).parent.parent / "run_workflow"))
from run_workflow import WorkflowRunner  # noqa: E402

# ── 定数 ─────────────────────────────────────────────────────────────────────

# config.json の reactions / messages で必須となるキー一覧
_REACTION_KEYS = ("processing", "success", "error")
_MESSAGE_KEYS = (
    "rate_limit",
    "generating",
    "parse_error",
    "execution_error",
    "file_too_large",
    "unexpected_error",
    "dm_not_supported",
    "shutdown_in_progress",
)
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB: Discord の添付ファイル上限に合わせた閾値

# Discord ボット経由でユーザー入力を受け取るため、巨大文字列によるメモリ枯渇を防ぐ上限
MAX_PROMPT_LENGTH = 3000

# ── ログ出力 ──────────────────────────────────────────────────────────────────


def write_log(
    log_dir: Path,
    user_id: int,
    username: str,
    parsed: dict,
    status: str,
    outputs: list,
    error: str | None,
) -> None:
    """生成試行の結果を log_dir 配下に result_YYYYMMDD_hhmmss.json として書き出す。"""
    # ディレクトリが存在しない場合は自動生成する
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now()
    filename = f"result_{ts.strftime('%Y%m%d_%H%M%S')}.json"
    data = {
        "status": status,
        "timestamp": ts.isoformat(timespec="seconds"),
        "user_id": user_id,
        "username": username,
        "loras": parsed.get("loras", []),
        "positive": parsed.get("positive", ""),
        "negative": parsed.get("negative", ""),
        "outputs": outputs,
        "error": error,
    }
    with open(log_dir / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 設定読み込み ──────────────────────────────────────────────────────────────


def _parse_shutdown_time(value: str) -> tuple[int, int]:
    """'hh:mm' 形式の文字列を (hour, minute) タプルに変換する。不正な場合は ValueError。"""
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError(
            f"'shutdown_time' は 'hh:mm' 形式で指定してください（例: '03:00'）: {value!r}"
        )
    hour, minute = int(value[:2]), int(value[3:])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"'shutdown_time' の時刻が不正です: {value!r}")
    return hour, minute


def _validate_reactions(reactions: dict) -> None:
    """reactions セクションの型と必須キーを検証する。"""
    if not isinstance(reactions, dict):
        raise ValueError(
            "config.json の 'reactions' はオブジェクト形式である必要があります"
        )
    for key in _REACTION_KEYS:
        if key not in reactions:
            raise ValueError(f"config.json の 'reactions' に '{key}' キーがありません")
        if not isinstance(reactions[key], str) or not reactions[key].strip():
            raise ValueError(f"'reactions.{key}' は空でない文字列である必要があります")


def _validate_messages(messages: dict) -> None:
    """messages セクションの型と必須キーを検証する。"""
    if not isinstance(messages, dict):
        raise ValueError(
            "config.json の 'messages' はオブジェクト形式である必要があります"
        )
    for key in _MESSAGE_KEYS:
        if key not in messages:
            raise ValueError(f"config.json の 'messages' に '{key}' キーがありません")
        if not isinstance(messages[key], str):
            raise ValueError(f"'messages.{key}' は文字列である必要があります")


def load_config(config_path: str) -> dict:
    """設定ファイルを読み込み、必須キーの存在と型を検証して返す。"""
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ValueError("設定ファイルが見つかりません")
    except json.JSONDecodeError as e:
        raise ValueError(f"config.json の解析に失敗しました: {e}")

    if not isinstance(data, dict):
        raise ValueError("config.json はオブジェクト形式である必要があります")

    # トップレベルの文字列キーを検証する
    for key in ("discord_token", "comfyui_output_dir", "run_workflow_config"):
        if key not in data:
            raise ValueError(f"config.json に '{key}' キーがありません")
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"'{key}' は空でない文字列である必要があります")

    if "reactions" not in data:
        raise ValueError("config.json に 'reactions' キーがありません")
    _validate_reactions(data["reactions"])

    if "messages" not in data:
        raise ValueError("config.json に 'messages' キーがありません")
    _validate_messages(data["messages"])

    # shutdown_time は省略・null 可（指定時は hh:mm 形式で検証する）
    st = data.get("shutdown_time")
    if st is not None:
        if not isinstance(st, str):
            raise ValueError(
                "'shutdown_time' は 'hh:mm' 形式の文字列または null である必要があります"
            )
        _parse_shutdown_time(st)

    return data


# ── メッセージパース ───────────────────────────────────────────────────────────


class MessageParser:
    # メンション除去用と行頭キーワード検出用の正規表現
    _MENTION = re.compile(r"<@!?\d+>")
    _KEYWORD = re.compile(r"^(loras|positive|negative)\s*:", re.IGNORECASE)

    def parse(self, text: str) -> dict:
        """メンションメッセージをパースして loras / positive / negative を返す。
        positive / negative が欠落している場合は ValueError を送出する。"""
        cleaned = self._MENTION.sub("", text)
        sections = self._collect_sections(cleaned)
        self._validate_required(sections)
        return {
            "loras": self._parse_loras(sections.get("loras", "")),
            "positive": sections["positive"],
            "negative": sections["negative"],
        }

    def _collect_sections(self, text: str) -> dict:
        """テキストを行ごとに走査し、キーワード行で区切られたセクションを収集する。
        キーワード行以外は直前のセクションの継続行として扱う。"""
        sections = {}
        current_key = None
        current_lines = []

        for raw_line in text.splitlines():
            line = raw_line.strip()
            m = self._KEYWORD.match(line)
            if m:
                # 新しいキーワードが始まる前に直前のセクションを確定する
                if current_key is not None:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = m.group(1).lower()
                value_start = line[m.end() :].strip()
                current_lines = [value_start] if value_start else []
            elif current_key is not None:
                # キーワード行以外は継続行として追記する
                # プロンプト内の "face:1.3" 等の ":" はここで安全に処理される
                current_lines.append(line)

        # ループ終了後に最後のセクションを確定する
        if current_key is not None:
            sections[current_key] = "\n".join(current_lines).strip()

        return sections

    def _validate_required(self, sections: dict) -> None:
        """positive / negative が両方存在することを確認する。"""
        for key in ("positive", "negative"):
            if key not in sections:
                raise ValueError(f"'{key}' キーが見つかりません")

    def _parse_loras(self, loras_str: str) -> list:
        """カンマ区切りの LoRA 名文字列をリストに変換する。空文字列は空リストを返す。"""
        if not loras_str:
            return []
        return [name.strip() for name in loras_str.split(",") if name.strip()]


# ── レート制限・生成ロック ─────────────────────────────────────────────────────


class RateLimiter:
    COOLDOWN_SECONDS = 30

    def __init__(self):
        self._last_request: dict = {}  # user_id -> monotonic timestamp
        self._generating = False

    def check_user(self, user_id: int) -> float:
        """残りクールダウン秒数を返す。制限なしなら 0.0。"""
        elapsed = time.monotonic() - self._last_request.get(user_id, 0.0)
        return max(0.0, self.COOLDOWN_SECONDS - elapsed)

    def record_request(self, user_id: int) -> None:
        """レート制限カウント用にリクエスト時刻を記録する。"""
        self._last_request[user_id] = time.monotonic()

    def is_generating(self) -> bool:
        """グローバル生成ロックの状態を返す。"""
        return self._generating

    def set_generating(self, value: bool) -> None:
        """グローバル生成ロックをセット / 解除する。"""
        self._generating = value


# ── スラッシュコマンド モーダル ────────────────────────────────────────────────


class GenImageModal(discord.ui.Modal, title="画像生成"):
    loras = discord.ui.TextInput(
        label="LoRAs",
        required=False,
        placeholder="lora1, lora2",
        max_length=400,
    )
    positive = discord.ui.TextInput(
        label="Positive",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="masterpiece, best quality, 1girl",
        max_length=MAX_PROMPT_LENGTH,
    )
    negative = discord.ui.TextInput(
        label="Negative",
        style=discord.TextStyle.paragraph,
        required=True,
        placeholder="worst quality, bad quality",
        max_length=MAX_PROMPT_LENGTH,
    )

    def __init__(self, bot: "ImageBot"):
        super().__init__()
        self._bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        parsed = self._build_parsed()
        await interaction.response.send_message(self._build_message_text(parsed))
        message = await interaction.original_response()
        await self._bot._process_generation(message, parsed, interaction.user)

    def _build_parsed(self) -> dict:
        loras_str = self.loras.value.strip()
        return {
            "loras": [n.strip() for n in loras_str.split(",") if n.strip()],
            "positive": self.positive.value.strip(),
            "negative": self.negative.value.strip(),
        }

    def _build_message_text(self, parsed: dict) -> str:
        lines = []
        if parsed["loras"]:
            lines.append(f"loras: {', '.join(parsed['loras'])}")
        lines.append(f"positive: {parsed['positive']}")
        lines.append(f"negative: {parsed['negative']}")
        return "\n".join(lines)


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
        # ログディレクトリはスクリプトと同階層の log/ に固定する
        self._log_dir = Path(__file__).parent / "log"
        self._runner = runner or WorkflowRunner(config["run_workflow_config"])
        # shutdown_time が設定されている場合はタプル (hour, minute) で保持する
        st = config.get("shutdown_time")
        self._shutdown_time: tuple[int, int] | None = (
            _parse_shutdown_time(st) if st else None
        )
        # シャットダウン要求フラグ（True になると新規リクエストを受け付けない）
        self._shutdown_requested = False

    async def setup_hook(self):
        self.tree = discord.app_commands.CommandTree(self)
        self.tree.command(name="gen_image", description="ComfyUI で画像を生成します")(
            self._gen_image_command
        )
        await self.tree.sync()

    async def on_ready(self):
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
                while self._limiter.is_generating():
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
        await self._process_generation(message, parsed, message.author)

    async def _process_generation(self, message, parsed: dict, user):
        """レート制限 → グローバルロック → 生成 の共通フロー。メンション・モーダル両経路で使用。"""
        # レート制限チェック（パース成功後 / モーダル送信直後に計上）
        remaining = self._limiter.check_user(user.id)
        if remaining > 0:
            secs = math.ceil(remaining)
            await self._reply_error(
                message, self._fmt("rate_limit", remaining_seconds=secs)
            )
            return

        self._limiter.record_request(user.id)

        # グローバルロックチェック（同時生成は 1 件のみ許可）
        if self._limiter.is_generating():
            await self._reply_error(message, self._fmt("generating"))
            return

        # ロックを取得し、処理中リアクションを付与する
        self._limiter.set_generating(True)
        await message.add_reaction(self._config["reactions"]["processing"])
        try:
            await self._generate_and_send(message, parsed, user)
        finally:
            # 成功・失敗を問わず必ずロック解除と処理中リアクションの削除を行う
            self._limiter.set_generating(False)
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

        # WorkflowRunner.execute() は同期処理のため to_thread でイベントループをブロックしない
        try:
            outputs = await asyncio.to_thread(
                self._runner.execute, parsed["loras"], prompts
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
            if size >= _MAX_FILE_SIZE:
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


# ── エントリポイント ──────────────────────────────────────────────────────────


_RECONNECT_WAIT = 30  # WSServerHandshakeError 発生時の再接続待機秒数


def main():
    """コマンドライン引数を解析して設定を読み込み、ボットを起動する。
    Discord ゲートウェイへの WebSocket ハンドシェイクが失敗した場合は待機後に再起動する。"""
    parser = argparse.ArgumentParser(description="ComfyUI Discord ボット")
    parser.add_argument(
        "-c",
        "--config",
        default=str(Path(__file__).parent / "config.json"),
        help="設定ファイルのパス（省略時: config.json）",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    while True:
        try:
            ImageBot(config).run(config["discord_token"])
            break  # shutdown_watcher による正常終了
        except aiohttp.WSServerHandshakeError as e:
            # Discord ゲートウェイが HTTP 520 等を返した場合は待機後に再接続する
            print(
                f"WebSocket ハンドシェイクエラー ({e}), "
                f"{_RECONNECT_WAIT}秒後に再接続します..."
            )
            time.sleep(_RECONNECT_WAIT)


if __name__ == "__main__":
    main()
