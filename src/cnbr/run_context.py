from __future__ import annotations

import hashlib
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str) -> str | None:
    command = ["git", "-c", f"safe.directory={repo_root.as_posix()}", *args]
    try:
        result = subprocess.run(
            command,
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


@dataclass(frozen=True)
class RunContext:
    run_id: str
    started_at: str
    command: str
    code_commit: str | None
    dirty_worktree: bool | None
    config_hash: str
    input_hash: str
    seed: int

    def to_dict(self) -> dict[str, str | int | bool | None]:
        return asdict(self)


def make_run_context(
    *, repo_root: Path, command: str, config_hash: str, input_hash: str, seed: int
) -> RunContext:
    commit = _git(repo_root, "rev-parse", "HEAD")
    porcelain = _git(repo_root, "status", "--porcelain")
    dirty = None if porcelain is None else bool(porcelain)
    identity = hashlib.sha256(
        f"{command}|{commit}|{config_hash}|{input_hash}|{seed}".encode()
    ).hexdigest()[:16]
    return RunContext(
        run_id=identity,
        started_at=datetime.now(UTC).isoformat(),
        command=command,
        code_commit=commit,
        dirty_worktree=dirty,
        config_hash=config_hash,
        input_hash=input_hash,
        seed=seed,
    )
