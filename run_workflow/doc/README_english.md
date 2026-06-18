# run_workflow

A tool for automatically running ComfyUI workflows from Python using the REST API and WebSocket.

Automatically selects a template based on the number of LoRAs, then injects prompts, LoRAs, and image size to execute the workflow.
Templates, LoRAs, and default image sizes can be switched per workflow (model).
Also includes a feature to retrieve tag strings from images using the WD Timm Tagger workflow.

Execution results (output file list and error information) are recorded in `result.json`.

**✨ 日本語版は[こちら](../README.md)**

## Features

- Switch template sets, LoRAs, and default image sizes by workflow name
- Automatic template selection supporting 0 to 4 LoRAs
- Injection of prompts (positive / negative) and LoRAs
- Image size (width / height) specification (defaults to the per-workflow default when omitted)
- Real-time progress monitoring via WebSocket
- Random seed generation per execution
- Success/failure recording in `result.json`
- Image tagging via WD Timm Tagger (using `bedovyy/ComfyUI-WD-Timm-Tagger`)

## Requirements

- Python 3.12+
- A running ComfyUI instance (default: `http://127.0.0.1:8188`)

## Setup

Refer to the [Setup section](../../doc/README_english.md#-setup) in the repository root.

## Configuration

**`config.json`** — Specifies the ComfyUI connection, per-workflow settings, and WD14 Tagger settings.

```json
{
  "comfyui_url": "http://127.0.0.1:8188",
  "default_workflow": "sdxl",
  "workflows": {
    "sdxl": {
      "default_image_size": {"width": 832, "height": 1216},
      "image_size": {
        "vertical":   {"width": 832,  "height": 1216},
        "horizontal": {"width": 1216, "height": 832},
        "square":     {"width": 1024, "height": 1024}
      },
      "loras": {
        "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
      }
    },
    "anima": {
      "default_image_size": {"width": 1024, "height": 1024},
      "image_size": {
        "vertical":   {"width": 832,  "height": 1216},
        "horizontal": {"width": 1216, "height": 832},
        "square":     {"width": 1024, "height": 1024}
      },
      "loras": {
        "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
      }
    }
  },
  "wd14_tagger": {
    "model_name": "wd-eva02-large-tagger-v3",
    "general_threshold": 0.35,
    "character_threshold": 0.85
  }
}
```

| Key | Description |
|---|---|
| `default_workflow` | The workflow name used when `--workflow` is omitted |
| `workflows.<name>.default_image_size` | The default image size used when `image_size` is omitted in the input JSON |
| `workflows.<name>.image_size` | Image sizes per orientation (`vertical` / `horizontal` / `square` — all three keys required). Referenced by `generate_image_bot` |
| `workflows.<name>.loras` | Mapping of LoRA key names to filenames and strengths |
| `wd14_tagger.model_name` | The model name to use with WD Timm Tagger |
| `wd14_tagger.general_threshold` | Output threshold for general tags (0.0–1.0) |
| `wd14_tagger.character_threshold` | Threshold for character tags (0.0–1.0) |

## Usage

### CLI — Image Generation

```bash
# Run with a specified workflow
python run_workflow.py -i input.json -w sdxl -o result.json

# Omit the workflow (uses default_workflow from config.json)
python run_workflow.py -i input.json
```

**Arguments:**

| Argument | Short | Required | Default | Description |
|---|---|---|---|---|
| `--input` | `-i` | Yes | — | Path to the input JSON file |
| `--workflow` | `-w` | No | `default_workflow` from config | Workflow name |
| `--output` | `-o` | No | `result_<timestamp>.json` | Output path for the result JSON |
| `--config` | `-c` | No | `config.json` | Path to the configuration file |

**`input.json` format:**

```json
{
  "loras": ["my_lora"],
  "prompts": {
    "positive": "masterpiece, best quality, 1girl ...",
    "negative": "worst quality, bad quality ..."
  },
  "image_size": {
    "width": 768,
    "height": 1024
  }
}
```

| Field | Required | Description |
|---|---|---|
| `loras` | Yes | 0–4 key names defined under the workflow's `loras` in config |
| `prompts.positive` / `prompts.negative` | Yes | Prompt strings (max 3000 characters) |
| `image_size.width` / `image_size.height` | No | Image size (512–2048, multiples of 8). Uses the workflow's `default_image_size` if omitted |

### CLI — WD14 Tagging

Outputs a tag string to stdout for the specified image file.

```bash
python run_workflow.py --tag --image photo.jpg
python run_workflow.py -t -g photo.jpg -c config.json
```

**Arguments:**

| Argument | Short | Required | Description |
|---|---|---|---|
| `--tag` | `-t` | Yes | Run in WD14 Tagger mode |
| `--image` | `-g` | Yes | Path to the image file to tag |
| `--config` | `-c` | No | Path to the configuration file (default: `config.json`) |

**Example output:**

```
1girl, solo, long hair, blue eyes, smile, ...
```

### Import from Python — Image Generation

```python
from run_workflow import WorkflowRunner

# Specify a workflow
runner = WorkflowRunner("config.json", workflow_name="anima")

# Omit the workflow (uses default_workflow from config.json)
runner = WorkflowRunner("config.json")

# With image_size specified
outputs = runner.execute(
    ["my_lora"],
    {"positive": "...", "negative": "..."},
    image_size={"width": 768, "height": 1024},
)

# Without image_size (uses the workflow's default_image_size)
outputs = runner.execute(["my_lora"], {"positive": "...", "negative": "..."})
```

`execute()` is thread-safe. Multiple threads can call the same instance simultaneously.

### Import from Python — WD14 Tagging

```python
from modules.wd14_tagger_runner import Wd14TaggerRunner

runner = Wd14TaggerRunner("config.json")

with open("photo.jpg", "rb") as f:
    image_data = f.read()

tags = runner.tag(image_data, "photo.jpg")
print(tags)
# 1girl, solo, long hair, blue eyes, ...
```

## Output

A `result.json` file is generated after execution.

```json
{
  "status": "success",
  "prompt_id": "abc123",
  "timestamp": "2026-04-25T12:00:00",
  "template": "templates/sdxl/template_lora_1.json",
  "parameters": {
    "positive": "masterpiece, best quality, 1girl ...",
    "negative": "worst quality, bad quality ...",
    "loras": [{"name": "my_lora", "file": "my_lora.safetensors", "strength": 0.8}],
    "image_size": {"width": 768, "height": 1024}
  },
  "outputs": [
    {"filename": "ComfyUI_00001_.png", "subfolder": "", "type": "output"}
  ],
  "error": null
}
```

## Adding a New Workflow

1. Create a `templates/<workflow_name>/` directory and place `template_lora_0.json` through `template_lora_4.json` inside it.
2. Set the following `_meta.title` values on the nodes to be overwritten in the template:

| `_meta.title` | Content to overwrite |
|---|---|
| `positive_prompt` | Positive prompt |
| `negative_prompt` | Negative prompt |
| `empty_latent_image` | Image width / height |
| `lora_loader_1` to `lora_loader_4` | LoRA filename and strength |

3. Add a key with the same name under `workflows` in `config.json`:

```json
"workflows": {
  "<workflow_name>": {
    "default_image_size": {"width": 1024, "height": 1024},
    "image_size": {
      "vertical":   {"width": 832,  "height": 1216},
      "horizontal": {"width": 1216, "height": 832},
      "square":     {"width": 1024, "height": 1024}
    },
    "loras": {
      "my_lora": {"file": "my_lora.safetensors", "strength": 0.8}
    }
  }
}
```

For details on node titles, refer to [SPEC.md](./SPEC.md).

## Tests

```bash
python -m pytest test/
```

## About Templates

The workflows included in `templates/` are samples. You can replace them with any workflow created in ComfyUI.

### sdxl Template

| Type | Name |
|---|---|
| Custom Node | [ComfyUI-Impact-Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack) |
| Model | WAI-illustrious-SDXL v16.0 |
| Upscaler | RealESRGAN x2 |

### anima / anima_rapid Templates

| Type | Name |
|---|---|
| Model | waiANIMA v1.0 |
| LoRA | anima-turbo-lora v0.2 |

### WD14 Tagger Template

| Type | Name |
|---|---|
| Custom Node | [ComfyUI-WD-Timm-Tagger](https://github.com/bedovyy/ComfyUI-WD-Timm-Tagger) |

## File Structure

```
run_workflow/
  run_workflow.py              # Main script (WorkflowRunner + entry point)
  config.json                  # Connection settings, per-workflow settings, WD14 settings
  modules/
    load_files.py              # Config and input file loading and validation
    workflow_builder.py        # Template selection and substitution
    comfyui_client.py          # ComfyUI REST API / WebSocket client
    wd14_tagger_runner.py      # WD Timm Tagger workflow execution
  templates/
    sdxl/                      # SDXL templates
      template_lora_0.json ... template_lora_4.json
    anima/                     # waiANIMA templates
      template_lora_0.json ... template_lora_4.json
    anima_rapid/               # waiANIMA fast templates
      template_lora_0.json ... template_lora_4.json
    template_wd14_tagger.json  # WD Timm Tagger workflow template
  test/
    test_helper.py
    test_run_workflow.py
    test_load_files.py
    test_workflow_builder.py
    test_comfyui_client.py
    test_wd14_tagger_runner.py
  doc/
    SPEC.md
```
