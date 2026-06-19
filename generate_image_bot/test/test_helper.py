"""generate_image_bot.py のテストコードで使用するヘルパー関数群"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import discord

from modules.image_bot import ImageBot

# ── helpers ───────────────────────────────────────────────────────────────────


def valid_config() -> dict:
    return {
        "discord_token": "test_token",
        "comfyui_output_dir": "C:/output",
        "run_workflow_config": "../run_workflow/config.json",
        "reactions": {
            "processing": "⏳",
            "success": "✅",
            "error": "❌",
        },
        "messages": {
            "rate_limit": "あと {remaining_seconds} 秒待ってください。",
            "concurrent_limit": "リクエストが上限に達しています。しばらくお待ちください。",
            "parse_error": "形式が正しくありません: {error}",
            "execution_error": "生成に失敗しました: {error}",
            "file_too_large": "画像が大きすぎます（{size_mb} MB）",
            "unexpected_error": "予期しないエラーが発生しました",
            "dm_not_supported": "DM からは使用できません。",
            "shutdown_in_progress": "シャットダウン中です。",
            "tag_image_invalid_type": "画像ファイルのみ対応しています。",
            "tag_image_error": "タグ付けに失敗しました: {error}",
            "tag_image_invalid_format": "画像形式が不正です。対応形式: JPEG, PNG, WEBP, GIF, BMP",
            "tag_image_resolution_too_large": "画像の解像度が大きすぎます（最大 4096x4096）",
            "invalid_workflow": "ワークフロー '{workflow}' は存在しません。",
        },
    }


def write_config(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def make_bot_for_test(
    config: dict, runner, output_dir=None, wd14_runner=None
) -> ImageBot:
    if output_dir is not None:
        config = {**config, "comfyui_output_dir": str(output_dir)}
    # MagicMock の runner に JSON シリアライズ可能なデフォルト属性を設定する
    if isinstance(runner, MagicMock):
        runner.prompt_id = None
        runner.template_path = None
        runner.parameters = {}
    with patch.object(discord.Client, "__init__", return_value=None):
        bot = ImageBot(config, runner, wd14_runner or MagicMock())
    # discord.Client.user は _connection.user を参照するため両方設定する
    bot._connection = MagicMock()
    bot._connection.user = MagicMock()
    bot._connection.user.id = 12345
    bot._connection.user.name = "TestBot"
    return bot


def make_message(bot_user, content: str, guild_set: bool = True, is_own: bool = False):
    msg = MagicMock()
    if is_own:
        msg.author = bot_user
    else:
        msg.author = MagicMock()
        msg.author.id = 99999
        msg.author.name = "testuser"
    msg.content = content
    if guild_set:
        msg.guild = MagicMock()
        msg.guild.id = 222
    else:
        msg.guild = None
    msg.mentions = [bot_user]
    msg.add_reaction = AsyncMock()
    msg.remove_reaction = AsyncMock()
    msg.reply = AsyncMock()
    msg.channel = MagicMock()
    msg.channel.id = 111
    msg.channel.send = AsyncMock()
    return msg


VALID_CONTENT = "<@1>\npositive: 1girl\nnegative: bad quality"
VALID_OUTPUTS = [{"filename": "output.png", "subfolder": "", "type": "output"}]
