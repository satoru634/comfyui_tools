# generate_image_bot

A Discord bot that instructs ComfyUI to generate images and returns the generated images to Discord.

Internally uses `WorkflowRunner` / `Wd14TaggerRunner` from `run_workflow` to perform image generation and tagging.

Bot activity logs (startup, shutdown, Discord events, and image generation results) are recorded in JSON format under the `log/YYYYMMDD/` directory.

**✨ 日本語版は[こちら](../README.md)**

## Features

- Prompt input via **mention messages** using keyword format: `workflow:` / `positive:` / `negative:` / `loras:` / `image_orientation:`
- Image generation via **slash command** (`/gen_image`) with modal input
- Image tagging via **slash command** (`/tag_image`) using WD Timm Tagger
- Per-request workflow switching (defaults to `default_workflow` in `run_workflow/config.json` if omitted)
- Image orientation (`vertical` / `horizontal` / `square`) selection for image size switching (defaults to the config default if omitted)
- Per-user rate limiting (30-second cooldown)
- Concurrent request handling for multiple users (up to 4 simultaneous requests per user)
- Image delivery as Discord attachment
- Progress notification via reaction emojis (processing / success / error)
- Automatic bot shutdown at a specified time (waits for in-progress requests to complete before stopping)
- Bot startup, shutdown, Discord events, and image generation results logged as JSON under `log/YYYYMMDD/`

## Requirements

- Python 3.12+
- A running ComfyUI instance (when using `/tag_image`, the `bedovyy/ComfyUI-WD-Timm-Tagger` custom node is also required)
- `run_workflow` (sibling directory in the same repository)
- Discord Bot token

## Setup

### 1. Creating a Discord Bot and Adding It to Your Server

Create an application on the [Discord Developer Portal](https://discord.com/developers/applications), enable the Bot, and obtain the token.

Set the token in the `discord_token` field of `config.json`.

**Privileged Gateway Intents**

Enable the following in the Bot settings on the Developer Portal:

| Intent | Purpose |
|---|---|
| Message Content Intent | Reading message body (prompt) |

**Generating an Invite URL via the OAuth2 URL Generator**

In the Developer Portal under "OAuth2 → URL Generator", select the following and add the bot to your server using the generated URL:

| Item | Setting |
|---|---|
| Scopes | `bot` |

Bot Permissions:

| Permission | Purpose |
|---|---|
| View Channels | Receiving messages |
| Send Messages | Replying with images and error messages |
| Attach Files | Sending generated images and tagged images |
| Add Reactions | Adding ⏳ / ✅ / ❌ reactions |
| Use Slash Commands | Using `/gen_image` / `/tag_image` |

### 2. Virtual Environment Setup

Refer to the [Setup section](../../doc/README_english.md#-setup) in the repository root.

## Configuration

**`config.json`** — Specifies the Discord token, ComfyUI output directory, and other settings.

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
    "rate_limit": "Requests are coming in too fast. Please wait {remaining_seconds} more second(s) before retrying.",
    "concurrent_limit": "The concurrent request limit has been reached. Please wait a moment.",
    "parse_error": "The message format is incorrect:\n{error}",
    "execution_error": "Image generation failed:\n{error}",
    "file_too_large": "The image file is too large ({size_mb} MB)",
    "unexpected_error": "An unexpected error occurred",
    "dm_not_supported": "This command cannot be used in DMs. Please run it in a server channel.",
    "shutdown_in_progress": "The bot is shutting down. Please try again later.",
    "tag_image_invalid_type": "Only image files are supported.",
    "tag_image_error": "Tagging failed:\n{error}",
    "tag_image_invalid_format": "Invalid image format. Supported formats: JPEG, PNG, WEBP, GIF, BMP",
    "tag_image_resolution_too_large": "The image resolution is too large (max 4096x4096)",
    "invalid_workflow": "Workflow '{workflow}' does not exist."
  }
}
```

`config.json` contains the token and is not included in this repository to prevent accidental exposure. Create it based on the content above.

**Main configuration keys:**

| Key | Description |
|---|---|
| `discord_token` | Discord Bot token |
| `comfyui_output_dir` | Absolute path to the ComfyUI output folder |
| `run_workflow_config` | Path to `run_workflow/config.json` |
| `shutdown_time` | Time to stop the bot (`"hh:mm"` format; omit or set to `null` for no auto-shutdown) |
| `reactions` | Reaction emojis to add during processing / success / error |
| `messages` | Message templates for bot replies |

Image sizes (`vertical` / `horizontal` / `square`) are defined per workflow in `run_workflow/config.json`.

Both Unicode emojis (e.g., `⏳`) and custom emojis (e.g., `<:name:id>`) can be specified in `reactions`.

## Usage

### Starting the Bot

```bash
python generate_image_bot.py
python generate_image_bot.py --config /path/to/config.json
```

| Option | Default | Description |
|---|---|---|
| `-c` / `--config` | `config.json` in the same directory as the script | Path to the configuration file |

### Discord Operations

There are two ways to interact: **mention messages** and **slash commands**.

**Mention Message (Image Generation)**

Mention the bot and enter the prompt in keyword format.

```
@bot
workflow: anima
loras: my_lora, another_lora
positive: masterpiece, best quality, 1girl,
  (detailed face:1.3), solo
negative: worst quality, bad quality, blurry
image_orientation: vertical
```

- `workflow:` is optional (defaults to `default_workflow` in `run_workflow/config.json`)
- `loras:` is optional (generates without LoRA if omitted)
- `positive:` / `negative:` are required
- `image_orientation:` is optional (`vertical` / `horizontal` / `square`; defaults to the config default size if omitted)
- Prompts can span multiple lines

**Slash Command — `/gen_image` (Image Generation)**

Type `/gen_image` in a text channel to open a modal. Fill in the fields and submit; a bold-formatted message will be posted to the channel and image generation will begin.

**Slash Command — `/tag_image` (Image Tagging)**

Type `/tag_image` in a text channel, attach an image file to the `image` parameter, and submit. WD Timm Tagger will analyze the tags and return the tag string along with the original image.

| Constraint | Details |
|---|---|
| Supported formats | `image/*` MIME type and JPEG / PNG / WEBP / GIF / BMP |
| File size limit | Less than 10 MB |
| Resolution limit | 4096×4096 or less |

Attachments are validated for actual format using Pillow to reject executables disguised as images. Returned filenames are converted to timestamp-based UUIDs instead of the original filename.

For detailed usage, refer to [USERS_MANUAL](./USERS_MANUAL.md).

## Output

### Discord Reply (Image Generation)

On success, the bot replies with the image file attached.

```
[⏳ reaction added]
...(generating)...
[reply with image file attached]
[⏳ reaction removed, ✅ reaction added]
```

### Discord Reply (Tagging)

On success, the bot replies with the tag string and the original image attached.

```
[⏳ reaction added]
...(tagging)...
[tag string + original image attached as reply]
[⏳ reaction removed, ✅ reaction added]
```

### Log Files

Date-based subdirectories are created under `log/YYYYMMDD/`, containing three types of logs:

| Filename | When created |
|---|---|
| `result_hhmmss_ffffff.json` | Each time image generation is attempted (both success and failure) |
| `system_hhmmss_ffffff.json` | On bot startup and shutdown |
| `discord_hhmmss_ffffff.json` | On Discord connection, mention received, or slash command received |

**Example generation log:**

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

**Example system log (startup):**

```json
{
  "type": "startup",
  "timestamp": "2026-04-25T12:34:56",
  "shutdown_time": "03:00"
}
```

## Tests

```bash
python -m pytest test/
```

## File Structure

```
generate_image_bot/
  generate_image_bot.py  # Entry point (startup and reconnect loop)
  config.json            # Bot configuration (token, paths, etc.)
  doc/
    SPEC.md              # Specification (overview and file structure)
    SPEC/                # Per-section specifications
    USERS_MANUAL.md
  modules/
    image_bot.py         # ImageBot class (includes /gen_image and /tag_image commands)
    gen_image_modal.py   # GenImageModal class (/gen_image modal)
    message_parser.py    # MessageParser class
    rate_limiter.py      # RateLimiter class
    load_config.py       # Config file loading and validation
    common_lib.py        # Shared utilities (log writing, etc.)
    const.py             # Constants
  log/                   # Log output directory (auto-generated)
    YYYYMMDD/            # Date directory (auto-generated)
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
