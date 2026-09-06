# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cnbr.config import HostedWeakLabelConfig, WeakLabelConfig


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _get_hf_token(repo_root: Path) -> str | None:
    """Read an environment token first, then the ignored local .env file; never log it."""
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    env_path = repo_root / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "HF_TOKEN":
            candidate = value.strip().strip("\"'")
            return candidate or None
    return None


def parse_verdict(text: str) -> str:
    match = re.search(r"\b(yes|no|unsure)\b", text.lower())
    return match.group(1) if match else "unparseable"


def _select_calibration_tasks(
    task_paths: list[Path], repo_root: Path, maximum_per_group: int
) -> list[dict[str, object]]:
    task_pool = [task for path in task_paths for task in json.loads((repo_root / path).read_text())]
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for task in task_pool:
        data = cast(dict[str, object], task["data"])
        mode = str(data.get("selection_mode", "lexical_match"))
        grouped.setdefault((str(data["candidate_topic"]), mode), []).append(task)
    return [
        task
        for _, group in sorted(grouped.items())
        for task in sorted(
            group, key=lambda item: str(cast(dict[str, object], item["data"])["task_id"])
        )[:maximum_per_group]
    ]


def _load_human_labels(paths: list[Path], repo_root: Path) -> dict[str, str]:
    return {
        str(row["task_id"]): str(row["verdict"])
        for path in paths
        for row in json.loads((repo_root / path).read_text())
    }


def _write_weak_label_outputs(
    *,
    config: WeakLabelConfig | HostedWeakLabelConfig,
    repo_root: Path,
    rows: list[dict[str, object]],
    extra_manifest: dict[str, object],
) -> dict[str, object]:
    if len({str(row["task_id"]) for row in rows}) != len(rows):
        raise ValueError("Weak-label tasks are not unique")
    output_path = repo_root / config.output_path
    manifest_path = repo_root / config.manifest_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    comparable = [row for row in rows if row["human_verdict"] in {"yes", "no", "unsure"}]
    agreements = sum(row["weak_verdict"] == row["human_verdict"] for row in comparable)
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "task_count": len(rows),
        "task_selection": "bounded_per_topic_per_selection_mode",
        "human_labeled_count": len(comparable),
        "exact_agreement": agreements / len(comparable) if comparable else None,
        "weak_verdict_counts": dict(
            sorted(Counter(str(row["weak_verdict"]) for row in rows).items())
        ),
        "output_sha256": _sha256(output_path),
        "interpretation": "Weak-supervision calibration only; human labels remain ground truth.",
        **extra_manifest,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def run_local_weak_label_benchmark(config: WeakLabelConfig, repo_root: Path) -> dict[str, object]:
    """Run a pinned local model against human-reviewed tasks; never use as ground truth."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tasks = _select_calibration_tasks(
        config.task_paths, repo_root, config.max_tasks_per_topic_per_mode
    )
    human = _load_human_labels(config.human_label_paths, repo_root)
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id,
        revision=config.model_revision,
        local_files_only=True,
        trust_remote_code=False,
    )
    model = AutoModelForCausalLM.from_pretrained(
        config.model_id,
        revision=config.model_revision,
        local_files_only=True,
        trust_remote_code=False,
        torch_dtype=torch.float32,
    ).to("cpu")
    model.eval()
    rows: list[dict[str, object]] = []
    for task in tasks:
        data = cast(dict[str, Any], task["data"])
        messages = [
            {"role": "system", "content": "Reply with exactly one word: Yes, No, or Unsure."},
            {
                "role": "user",
                "content": f"Candidate topic: {data['candidate_topic']}\nExcerpt:\n{data['text']}",
            },
        ]
        tokenized = tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            truncation=True,
            max_length=config.max_input_tokens,
        )
        input_ids = tokenized["input_ids"] if isinstance(tokenized, Mapping) else tokenized
        with torch.inference_mode():
            output = model.generate(
                input_ids,
                do_sample=False,
                max_new_tokens=config.max_new_tokens,
                pad_token_id=tokenizer.eos_token_id,
            )
        completion = tokenizer.decode(output[0][input_ids.shape[1] :], skip_special_tokens=True)
        task_id = str(data["task_id"])
        rows.append(
            {
                "task_id": task_id,
                "candidate_topic": str(data["candidate_topic"]),
                "weak_verdict": parse_verdict(completion),
                "human_verdict": human.get(task_id),
            }
        )
    return _write_weak_label_outputs(
        config=config,
        repo_root=repo_root,
        rows=rows,
        extra_manifest={
        "model_id": config.model_id,
        "model_revision": config.model_revision,
        "execution": "local_cpu",
        },
    )


def run_hosted_weak_label_calibration(
    config: HostedWeakLabelConfig, repo_root: Path
) -> dict[str, object]:
    """Evaluate a fixed, owner-authorized calibration sample through Hugging Face."""
    token = _get_hf_token(repo_root)
    if not token:
        raise RuntimeError("HF_TOKEN is required for hosted weak-label calibration")
    from huggingface_hub import HfApi, InferenceClient

    tasks = _select_calibration_tasks(
        config.task_paths, repo_root, config.max_tasks_per_topic_per_mode
    )
    if len(tasks) > 12:
        raise ValueError("Hosted calibration is capped at 12 tasks")
    human = _load_human_labels(config.human_label_paths, repo_root)
    model_info = HfApi(token=token).model_info(config.model_id, revision=config.model_revision)
    client = InferenceClient(
        model=config.model_id,
        provider=config.provider,
        token=token,
        timeout=config.timeout_seconds,
    )
    rows: list[dict[str, object]] = []
    for task in tasks:
        data = cast(dict[str, Any], task["data"])
        text = str(data["text"])[: config.max_input_characters]
        response = client.chat_completion(
            messages=[
                {"role": "system", "content": "Reply with exactly one word: Yes, No, or Unsure."},
                {
                    "role": "user",
                    "content": f"Candidate topic: {data['candidate_topic']}\nExcerpt:\n{text}",
                },
            ],
            max_tokens=config.max_new_tokens,
            temperature=0.0,
        )
        completion = str(response.choices[0].message.content or "")
        task_id = str(data["task_id"])
        rows.append(
            {
                "task_id": task_id,
                "candidate_topic": str(data["candidate_topic"]),
                "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "weak_verdict": parse_verdict(completion),
                "human_verdict": human.get(task_id),
            }
        )
    return _write_weak_label_outputs(
        config=config,
        repo_root=repo_root,
        rows=rows,
        extra_manifest={
            "model_id": config.model_id,
            "requested_model_revision": config.model_revision,
            "resolved_model_revision": model_info.sha,
            "provider": config.provider,
            "execution": "hugging_face_hosted",
            "external_processing_authorized": config.allow_external_processing,
            "scale_up_allowed": False,
        },
    )
