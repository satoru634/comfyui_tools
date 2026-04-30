import json
from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────────────────


def write_json(path: Path, data) -> str:
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def valid_input(**overrides) -> dict:
    base = {
        "loras": ["my_lora"],
        "prompts": {
            "positive": "masterpiece, best quality",
            "negative": "worst quality",
        },
    }
    base.update(overrides)
    return base


def valid_lora_list() -> dict:
    return {
        "my_lora": {"file": "my_lora.safetensors", "strength": 0.8},
        "another_lora": {"file": "another_lora.safetensors", "strength": 0.7},
    }


def valid_image_size(**overrides) -> dict:
    base = {"width": 512, "height": 512}
    base.update(overrides)
    return base


def valid_config(**overrides) -> dict:
    base = {
        "comfyui_url": "http://127.0.0.1:8188",
        "default_image_size": valid_image_size(),
        "loras": valid_lora_list(),
    }
    base.update(overrides)
    return base


def make_workflow(
    lora_count: int, with_sampler: bool = True, with_latent: bool = True
) -> dict:
    workflow = {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["0", 1]},
            "_meta": {"title": "positive_prompt"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "", "clip": ["0", 1]},
            "_meta": {"title": "negative_prompt"},
        },
    }
    for i in range(1, lora_count + 1):
        workflow[str(10 + i)] = {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "", "strength_model": 1.0, "strength_clip": 1.0},
            "_meta": {"title": f"lora_loader_{i}"},
        }
    if with_sampler:
        workflow["99"] = {
            "class_type": "KSampler",
            "inputs": {"seed": 12345, "steps": 20, "cfg": 7},
            "_meta": {"title": "Kサンプラー"},
        }
        workflow["98"] = {
            "class_type": "FaceDetailer",
            "inputs": {"seed": 99999, "steps": 20, "cfg": 7},
            "_meta": {"title": "FaceDetailer"},
        }
    if with_latent:
        workflow["5"] = {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
            "_meta": {"title": "empty_latent_image"},
        }
    return workflow


def make_loras(count: int) -> list[dict]:
    return [
        {"name": f"lora{i}", "file": f"lora{i}.safetensors", "strength": 0.5 + i * 0.1}
        for i in range(1, count + 1)
    ]


def make_ws_message(**kwargs) -> str:
    return json.dumps(kwargs)
