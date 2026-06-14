"""WD Timm Tagger ワークフローの実行を担うクラス。単独でも import 経由でも利用できる。"""

import json
import uuid
from pathlib import Path

from modules.comfyui_client import ComfyUIClient
from modules.load_files import (
    load_tagger_config,
    validate_wd14_tagger_config,
)


class Wd14TaggerRunner:
    """WD Timm Tagger ワークフローの実行を担うクラス。単独でも import 経由でも利用できる。"""

    _LOAD_IMAGE_TITLE = "画像を読み込む"
    _TAGGER_TITLE = "WD Timm Tagger"
    _PREVIEW_TITLE = "プレビュー任意"

    def __init__(self, config_path: str = "config.json"):
        self.config = load_tagger_config(config_path)
        validate_wd14_tagger_config(self.config)
        self._client = ComfyUIClient(self.config["comfyui_url"])
        self._template, self._title_to_id = self._load_template()

    def _load_template(self) -> tuple[dict, dict]:
        path = Path(__file__).parent.parent / "templates" / "template_wd14_tagger.json"
        with open(path, encoding="utf-8") as f:
            template = json.load(f)
        title_to_id = {
            node["_meta"]["title"]: nid
            for nid, node in template.items()
            if "_meta" in node
        }
        return template, title_to_id

    def tag(self, image_data: bytes, filename: str = "image.png") -> str:
        """画像バイト列を受け取り、タグ文字列を返す。エラー時は ValueError を送出。"""
        uploaded_name = self._client.upload_image(image_data, filename)
        workflow = self._build_workflow(uploaded_name)
        client_id = str(uuid.uuid4())
        prompt_id = self._client.submit(workflow, client_id)
        self._client.monitor(prompt_id, client_id)
        return self._extract_tags(prompt_id)

    def _build_workflow(self, image_filename: str) -> dict:
        import copy

        workflow = copy.deepcopy(self._template)
        wd14 = self.config["wd14_tagger"]
        workflow[self._title_to_id[self._LOAD_IMAGE_TITLE]]["inputs"][
            "image"
        ] = image_filename
        tagger_inputs = workflow[self._title_to_id[self._TAGGER_TITLE]]["inputs"]
        tagger_inputs["model_name"] = wd14["model_name"]
        tagger_inputs["general_threshold"] = wd14["general_threshold"]
        tagger_inputs["character_threshold"] = wd14["character_threshold"]
        return workflow

    def _extract_tags(self, prompt_id: str) -> str:
        history = self._client.get_history(prompt_id)
        preview_id = self._title_to_id[self._PREVIEW_TITLE]
        text_list = history.get("outputs", {}).get(preview_id, {}).get("text")
        if not text_list:
            raise ValueError("WD Timm Tagger の出力が取得できませんでした")
        return text_list[0]
