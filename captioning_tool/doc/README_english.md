# captioning_tool

A tool that tags image files in a specified directory using WD Timm Tagger (ComfyUI) and batch-generates `.txt` caption files with the same name as each image.

Primarily intended for preparing caption files for LoRA training datasets.

**✨ 日本語版は[こちら](../README.md)**

## Features

- Batch tagging of images in a directory (supported extensions: `.jpg` `.jpeg` `.png` `.webp`)
- Existing `.txt` files are skipped by default (use `--overwrite` to overwrite)
- Recursive processing of subdirectories (`--recursive`)
- Prepending tags (e.g., trigger words) to captions (`--prepend`)
- Removing unwanted tags (`--exclude`)
- Tag summary report generation (`--report`)

## Requirements

- Python 3.12+
- A running ComfyUI instance (default: `http://127.0.0.1:8188`)
- ComfyUI custom node: [ComfyUI-WD-Timm-Tagger](https://github.com/bedovyy/ComfyUI-WD-Timm-Tagger)

## Setup

Refer to the [Setup section](../../doc/README_english.md#-setup) in the repository root.

## Configuration

**`config.json`** — Specifies the ComfyUI connection, WD14 Tagger settings, and default tags.

```json
{
  "comfyui_url": "http://127.0.0.1:8188",
  "wd14_tagger": {
    "model_name": "wd-eva02-large-tagger-v3",
    "general_threshold": 0.35,
    "character_threshold": 0.85
  },
  "prepend_tags": [],
  "exclude_tags": []
}
```

| Key | Description |
|---|---|
| `comfyui_url` | ComfyUI server URL |
| `wd14_tagger.model_name` | The WD Timm Tagger model to use |
| `wd14_tagger.general_threshold` | Output threshold for general tags (0.0–1.0) |
| `wd14_tagger.character_threshold` | Threshold for character tags (0.0–1.0) |
| `prepend_tags` | List of tags to prepend to all images |
| `exclude_tags` | List of tags to remove from all images |

## Usage

### Basic Execution

```bash
python captioning_tool.py <directory>
```

### Options

| Option | Short | Default | Description |
|---|---|---|---|
| `<directory>` | — | Required | Path to the target directory |
| `--recursive` | `-r` | False | Recursively process subdirectories |
| `--overwrite` | — | False | Overwrite existing `.txt` files |
| `--prepend` | `-p` | — | Tags to prepend (comma-separated). Combined with values in `config.json` |
| `--exclude` | `-e` | — | Tags to exclude (comma-separated). Combined with values in `config.json` |
| `--report` | — | False | Generate a tag summary report after processing |
| `--config` | `-c` | `config.json` | Path to the configuration file |

### Examples

```bash
# Basic execution (tag unprocessed images in ./images)
python captioning_tool.py ./images

# Prepend a trigger word and remove rating tags
python captioning_tool.py ./images --prepend "my_chara" --exclude "rating:general, rating:safe"

# Process including subdirectories and overwrite existing files
python captioning_tool.py ./dataset -r --overwrite

# Also generate a tag summary report
python captioning_tool.py ./images --report
```

### Tag Filter Processing Order

```
WD14 output
  → Remove exclude tags (case-insensitive, exact match)
  → Remove tags that duplicate prepend tags (WD14 side is removed)
  → Insert prepend tags at the beginning
  → Write to .txt
```

**Processing example:**

```
prepend: "my_chara, 1girl"
exclude: "rating:general"

WD14 output: "1girl, solo, long hair, rating:general"
Result:      "my_chara, 1girl, solo, long hair"
```

## Tag Summary Report

When `--report` is specified, after processing completes, all `.txt` files in the target directory are read to count tag occurrences, and the results are saved as `tags_report.txt`.

```
1girl: 42
solo: 38
long hair: 31
blue eyes: 28
...
```

- Target: all `.txt` files in the directory (including pre-existing files; `tags_report.txt` itself is excluded)
- Sort: by occurrence count descending (ties sorted alphabetically)
- When `--recursive` is specified, subdirectories are also included in the count

## Tests

```bash
python -m pytest test/
```

## File Structure

```
captioning_tool/
  captioning_tool.py    # Main script (CaptioningTool + entry point)
  config.json           # ComfyUI connection settings, WD14 settings, default tag settings
  test/
    test_captioning_tool.py
  doc/
    SPEC.md
```
