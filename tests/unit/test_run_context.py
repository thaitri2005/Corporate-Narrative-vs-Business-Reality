import hashlib
from pathlib import Path

from cnbr.run_context import sha256_file


def test_sha256_file(tmp_path: Path) -> None:
    target = tmp_path / "sample.txt"
    target.write_bytes(b"cnbr\n")
    assert sha256_file(target) == hashlib.sha256(b"cnbr\n").hexdigest()
