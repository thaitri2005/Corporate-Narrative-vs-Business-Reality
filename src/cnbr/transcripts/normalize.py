from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import polars as pl

from cnbr.config import TranscriptNormalizeConfig

VALID_ROLES = {"executive", "company_other", "analyst", "operator", "unknown"}


def _stable_id(*parts: object) -> str:
    value = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(value.encode()).hexdigest()


def _normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value)).replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(text.split())


def _role_for_turn(
    speaker_raw: str, participant_roles: dict[str, tuple[str, str]]
) -> tuple[str, str | None, list[str]]:
    normalized = _normalize_name(speaker_raw)
    matched = participant_roles.get(normalized)
    if matched is not None:
        return matched[0], matched[1], []
    lowered = speaker_raw.casefold()
    if normalized == "operator":
        return "operator", None, []
    if "analyst" in lowered:
        return "analyst", None, ["role_inferred_from_speaker_label"]
    return "unknown", None, ["speaker_not_in_participant_list"]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _content_flags(text: str) -> list[str]:
    lowered = text.casefold()
    flags: list[str] = []
    if "motley fool" in lowered or (lowered.startswith("more ") and " analysis" in lowered):
        flags.append("possible_source_footer")
    if "[inaudible]" in lowered:
        flags.append("inaudible_marker")
    if 0 < len(text.split()) < 3:
        flags.append("very_short_text")
    return flags


def normalize_transcripts(config: TranscriptNormalizeConfig, repo_root: Path) -> dict[str, object]:
    """Normalize STRUX calls into deterministic call, participant, and utterance tables."""
    invalid_roles = set(config.role_by_position.values()) - VALID_ROLES
    if invalid_roles:
        raise ValueError(f"Invalid canonical transcript roles: {sorted(invalid_roles)}")
    input_path = repo_root / config.input_path
    source = pl.read_parquet(input_path)
    universe = pl.read_parquet(repo_root / config.universe_path).select("ticker", "company_id")
    company_by_ticker = dict(universe.iter_rows())
    call_rows: list[dict[str, object]] = []
    participant_rows: list[dict[str, object]] = []
    utterance_rows: list[dict[str, object]] = []

    for source_row_no, row in enumerate(source.iter_rows(named=True)):
        ticker = str(row["ticker"])
        company_id = company_by_ticker.get(ticker)
        if company_id is None:
            raise ValueError(f"STRUX ticker absent from universe: {ticker}")
        call_date = str(row["date"])
        call_id = _stable_id("strux-call", config.source_revision, ticker, call_date)
        participants = cast(list[dict[str, Any]], row["participants"])
        participant_roles: dict[str, tuple[str, str]] = {}
        for participant_no, participant in enumerate(participants):
            name_raw = str(participant.get("name", ""))
            position = str(participant.get("position", ""))
            role = config.role_by_position.get(position, "unknown")
            name_normalized = _normalize_name(name_raw)
            participant_id = _stable_id(call_id, "participant", participant_no)
            participant_roles[name_normalized] = (role, participant_id)
            participant_rows.append(
                {
                    "schema_version": config.schema_version,
                    "call_id": call_id,
                    "participant_id": participant_id,
                    "participant_no": participant_no,
                    "company_id": company_id,
                    "speaker_name_raw": name_raw,
                    "speaker_name_normalized": name_normalized,
                    "speaker_role": role,
                    "source_position": position,
                    "source_description": str(participant.get("description", "")),
                    "source_listed": True,
                }
            )
        sequence_no = 0
        unknown_turn_count = 0
        for section, source_key in (
            ("prepared_remarks", "prepared_remarks"),
            ("qa", "questions_and_answers"),
        ):
            turns = cast(list[dict[str, Any]], row[source_key])
            for turn_no, turn in enumerate(turns):
                speaker_raw = str(turn.get("name", ""))
                role, participant_id, role_flags = _role_for_turn(speaker_raw, participant_roles)
                speaker_normalized = _normalize_name(speaker_raw)
                if participant_id is None:
                    participant_id = _stable_id(call_id, "observed-speaker", speaker_normalized)
                    participant_roles[speaker_normalized] = (role, participant_id)
                    participant_rows.append(
                        {
                            "schema_version": config.schema_version,
                            "call_id": call_id,
                            "participant_id": participant_id,
                            "participant_no": len(participant_rows),
                            "company_id": company_id,
                            "speaker_name_raw": speaker_raw,
                            "speaker_name_normalized": speaker_normalized,
                            "speaker_role": role,
                            "source_position": "",
                            "source_description": "",
                            "source_listed": False,
                        }
                    )
                unknown_turn_count += role == "unknown"
                speech = cast(list[object], turn.get("speech", []))
                for segment_no, segment in enumerate(speech):
                    text = _normalize_text(segment)
                    flags = [*role_flags, *_content_flags(text)]
                    if not text:
                        flags.append("blank_text")
                    text_sha256 = hashlib.sha256(text.encode()).hexdigest()
                    utterance_rows.append(
                        {
                            "schema_version": config.schema_version,
                            "call_id": call_id,
                            "utterance_id": _stable_id(call_id, sequence_no),
                            "participant_id": participant_id,
                            "sequence_no": sequence_no,
                            "company_id": company_id,
                            "ticker": ticker,
                            "call_date": call_date,
                            "section": section,
                            "speaker_name_raw": speaker_raw,
                            "speaker_name_normalized": speaker_normalized,
                            "speaker_role": role,
                            "source_turn_no": turn_no,
                            "source_segment_no": segment_no,
                            "text": text,
                            "text_sha256": text_sha256,
                            "word_count": len(text.split()),
                            "quality_flags": flags,
                        }
                    )
                    sequence_no += 1
        call_rows.append(
            {
                "schema_version": config.schema_version,
                "call_id": call_id,
                "company_id": company_id,
                "ticker": ticker,
                "call_date": call_date,
                "source_id": "strux",
                "source_revision": config.source_revision,
                "source_row_no": source_row_no,
                "participant_count": len(participants),
                "utterance_count": sequence_no,
                "unknown_speaker_turn_count": unknown_turn_count,
                "fiscal_mapping_status": "pending",
            }
        )

    hash_counts = Counter(
        str(row["text_sha256"])
        for row in utterance_rows
        if cast(int, row["word_count"]) >= config.duplicate_minimum_words
    )
    for row in utterance_rows:
        row["is_exact_duplicate"] = (
            cast(int, row["word_count"]) >= config.duplicate_minimum_words
            and hash_counts[str(row["text_sha256"])] > 1
        )

    calls = pl.DataFrame(call_rows).sort("ticker", "call_date")
    participants_frame = pl.DataFrame(participant_rows).sort("call_id", "participant_no")
    utterances = pl.DataFrame(utterance_rows).sort("call_id", "sequence_no")
    output_paths = {
        "calls": repo_root / config.calls_path,
        "participants": repo_root / config.participants_path,
        "utterances": repo_root / config.utterances_path,
    }
    for path in (*output_paths.values(), repo_root / config.manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    calls.write_parquet(output_paths["calls"], compression="zstd")
    participants_frame.write_parquet(output_paths["participants"], compression="zstd")
    utterances.write_parquet(output_paths["utterances"], compression="zstd")
    unknown_turns = sum(cast(int, row["unknown_speaker_turn_count"]) for row in call_rows)
    manifest: dict[str, object] = {
        "schema_version": config.schema_version,
        "created_at": datetime.now(UTC).isoformat(),
        "config_sha256": config.content_hash(),
        "source_revision": config.source_revision,
        "call_count": calls.height,
        "participant_count": participants_frame.height,
        "utterance_count": utterances.height,
        "unknown_speaker_turn_count": unknown_turns,
        "exact_duplicate_utterance_count": utterances.filter(pl.col("is_exact_duplicate")).height,
        "output_paths": {
            name: path.relative_to(repo_root).as_posix() for name, path in output_paths.items()
        },
        "input_sha256": _sha256_file(input_path),
        "output_sha256": {name: _sha256_file(path) for name, path in output_paths.items()},
        "fiscal_mapping_status": "pending",
    }
    manifest_path = repo_root / config.manifest_path
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
