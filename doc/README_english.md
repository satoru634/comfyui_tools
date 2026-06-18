# comfyui_tools

A collection of Python utilities for ComfyUI. Each tool is an independent subdirectory.

**✨ 日本語版は[こちら](../README.md)**

## 🖥️ Environment

- Python 3.12 or higher

## 🔧 Setup

Run the initialization script in the `setup/` directory to create a virtual environment and install dependencies.

**Windows:**
```bat
setup\setup_venv.bat
```

**Linux / macOS:**
```bash
bash setup/setup_venv.sh
```

After running the script, activate the virtual environment with the following command.

**Windows:**
```bat
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
source .venv/bin/activate
```

## 🛠️ Tools

| Tool | Description |
|---|---|
| [`run_workflow/`](../run_workflow/doc/README_english.md) | A tool for automatically running ComfyUI workflows from Python |
| [`generate_image_bot/`](../generate_image_bot/doc/README_english.md) | A Discord bot that instructs ComfyUI to generate images via mentions and returns the generated images |
| [`captioning_tool/`](../captioning_tool/doc/README_english.md) | A tool that batch-tags images in a directory using WD Timm Tagger and generates `.txt` caption files |

## ⚙️ Submodules

| Submodule | Repository | Description |
|---|---|---|
| [`sd_scripts/`](../sd_scripts/) | [kohya-ss/sd-scripts](https://github.com/kohya-ss/sd-scripts) | A collection of fine-tuning and LoRA training scripts for Stable Diffusion models |

On first clone, initialize the submodule:

```bash
git submodule update --init
```

## 🪪 License

[MIT](../LICENSE)
