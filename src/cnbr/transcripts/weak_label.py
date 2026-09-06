# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportArgumentType=false

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import time
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx

from cnbr.config import HostedWeakLabelConfig, LocalGgufWeakLabelConfig, WeakLabelConfig


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


def parse_json_verdict(text: str) -> str:
    """Parse only the constrained JSON contract; never infer a label from prose."""
    decoder = json.JSONDecoder()
    candidates = [text]
    candidates.extend(text[index:] for index, character in enumerate(text) if character == "{")
    for candidate in candidates:
        try:
            payload, _ = decoder.raw_decode(candidate.lstrip())
        except json.JSONDecodeError:
            continue
        verdict = payload.get("verdict") if isinstance(payload, dict) else None
        if verdict in {"yes", "no", "unsure"} and set(payload) == {"verdict"}:
            return str(verdict)
    return "unparseable"


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
    output_path = repo_root / config.output_path
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list) or not all(isinstance(row, dict) for row in existing):
            raise ValueError("Hosted weak-label checkpoint must be a list of objects")
        rows = cast(list[dict[str, object]], existing)
    else:
        rows = []
    completed_task_ids = {str(row.get("task_id")) for row in rows}
    for task in tasks:
        data = cast(dict[str, Any], task["data"])
        task_id = str(data["task_id"])
        if task_id in completed_task_ids:
            continue
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
        rows.append(
            {
                "task_id": task_id,
                "candidate_topic": str(data["candidate_topic"]),
                "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "weak_verdict": parse_verdict(completion),
                "human_verdict": human.get(task_id),
            }
        )
        completed_task_ids.add(task_id)
        # This ignored local checkpoint prevents duplicate external processing after a provider
        # or credit failure. It contains no excerpt text.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
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


def _resolve_llama_executable(name: str) -> Path:  # pragma: no cover - Windows runtime adapter
    discovered = shutil.which(name)
    if discovered:
        return Path(discovered)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        package_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        candidates = sorted(package_root.glob(f"ggml.llamacpp*/{name}.exe"))
        if candidates:
            return candidates[-1]
    raise RuntimeError(f"{name} was not found; install the official llama.cpp Windows package")


def _free_loopback_port() -> int:  # pragma: no cover - exercised with local runtime
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@contextmanager
def _local_llama_server(
    config: LocalGgufWeakLabelConfig, model_path: Path
) -> Iterator[str]:  # pragma: no cover - exercised with local runtime
    """Run one hidden loopback-only model server for the entire calibration."""
    port = _free_loopback_port()
    command = [
        str(_resolve_llama_executable("llama-server")),
        "-m",
        str(model_path),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-c",
        str(config.context_tokens),
        "-t",
        str(config.threads),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + config.timeout_seconds
    try:
        with httpx.Client(timeout=2) as client:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("llama-server exited during startup")
                try:
                    if client.get(f"{base_url}/health").is_success:
                        yield base_url
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
        raise RuntimeError("llama-server did not become ready before timeout")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def _run_server_verdict(
    client: httpx.Client, base_url: str, config: LocalGgufWeakLabelConfig, topic: str, text: str
) -> str:  # pragma: no cover - exercised with local runtime
    response = client.post(
        f"{base_url}/v1/chat/completions",
        json={
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Reply only with a JSON object having one verdict field. "
                        "Its value must be yes, no, or unsure."
                    ),
                },
                {"role": "user", "content": f"Candidate topic: {topic}\nExcerpt:\n{text}"},
            ],
            "temperature": 0,
            "max_tokens": config.max_new_tokens,
            "response_format": {"type": "json_object"},
        },
    )
    response.raise_for_status()
    payload = response.json()
    try:
        content = str(payload["choices"][0]["message"]["content"])
    except (IndexError, KeyError, TypeError) as error:
        raise RuntimeError("llama-server returned an invalid chat-completion response") from error
    return parse_json_verdict(content)


def run_local_gguf_weak_label_calibration(
    config: LocalGgufWeakLabelConfig, repo_root: Path
) -> dict[str, object]:  # pragma: no cover - exercised with local runtime
    """Calibrate a local GGUF model only after its JSON contract passes synthetic checks."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    model_path = repo_root / config.model_path
    if not model_path.is_file():
        raise RuntimeError(f"GGUF model is missing: {model_path}")
    synthetic_cases = [
        ("pricing", "The company increased prices across its products.", "yes"),
        ("pricing", "The company hired additional warehouse staff.", "no"),
        ("pricing", "The conference call began at 9 a.m.", "unsure"),
    ]
    with _local_llama_server(config, model_path) as base_url, httpx.Client(
        timeout=config.timeout_seconds
    ) as client:
        gate_results = [
            _run_server_verdict(client, base_url, config, topic, text)
            for topic, text, _ in synthetic_cases
        ]
        expected = [expected for _, _, expected in synthetic_cases]
        if gate_results != expected:
            raise RuntimeError(
                "Local GGUF synthetic structured-output gate failed: "
                f"expected={expected}, received={gate_results}"
            )
        tasks = _select_calibration_tasks(
            config.task_paths, repo_root, config.max_tasks_per_topic_per_mode
        )
        human = _load_human_labels(config.human_label_paths, repo_root)
        rows: list[dict[str, object]] = []
        for task in tasks:
            data = cast(dict[str, Any], task["data"])
            text = str(data["text"])[: config.max_input_characters]
            task_id = str(data["task_id"])
            rows.append(
                {
                    "task_id": task_id,
                    "candidate_topic": str(data["candidate_topic"]),
                    "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "weak_verdict": _run_server_verdict(
                        client, base_url, config, str(data["candidate_topic"]), text
                    ),
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
            "model_sha256": _sha256(model_path),
            "execution": "local_cpu_llama_cpp",
            "synthetic_gate": "passed",
            "external_processing_authorized": False,
            "scale_up_allowed": False,
        },
    )
