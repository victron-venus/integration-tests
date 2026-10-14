"""Build and verify the reviewed host-tools source distribution without devices."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from release_version_adapter import checked_version

PROJECT = "integration-tests"
INVENTORY = "release-files.json"
MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024


def inventory(root: Path) -> list[str]:
    """Require exact reviewed paths; directories never implicitly add new files."""
    names = json.loads((root / INVENTORY).read_text())["files"]
    if (
        not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) for name in names)
        or names != sorted(set(names))
    ):
        raise ValueError("Source inventory must be a sorted unique list")
    for name in names:
        path = PurePosixPath(name)
        if (
            path.is_absolute()
            or str(path) != name
            or ".." in path.parts
            or "\\" in name
        ):
            raise ValueError("Source inventory contains an unsafe path")
    if "SOURCE_VERSION" not in names or INVENTORY not in names:
        raise ValueError("Source inventory lacks its identity")
    return names


def sources(root: Path) -> dict[str, bytes]:
    """Read only tracked regular files from the explicit distribution inventory."""
    tracked = set(
        subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
        .decode()
        .split("\0")
    )
    files = {}
    for name in inventory(root):
        path = root / name
        if name not in tracked or path.is_symlink() or not path.is_file():
            raise ValueError("Missing, untracked or linked release input: " + name)
        if path.resolve() != root.resolve() / name:
            raise ValueError("Source inventory traverses a linked directory")
        if path.stat().st_size > MAX_FILE:
            raise ValueError("Source input exceeds its size limit")
        files[name] = path.read_bytes()
    if sum(map(len, files.values())) > MAX_TOTAL:
        raise ValueError("Source inventory exceeds its total size limit")
    return files


def build(root: Path, base: str, channel: str, output: Path) -> Path:
    """Package the actual frozen version overlay and immutable source inventory."""
    if channel not in {"beta", "rc", "nightly"}:
        raise ValueError("Stable publication requires an accepted RC")
    version = checked_version(root, base, channel)
    files = sources(root)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("Source output directory must be empty")
    archive = output / f"{PROJECT}-{version}.tar.gz"
    with (
        archive.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped,
        tarfile.open(fileobj=zipped, mode="w") as package,
    ):
        for name, content in files.items():
            entry = tarfile.TarInfo(f"{PROJECT}/{name}")
            entry.mode = 0o755 if (root / name).stat().st_mode & 0o111 else 0o644
            entry.size = len(content)
            package.addfile(entry, io.BytesIO(content))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {archive.name}\n")
    return archive


def unpack(archive: Path, root: Path, destination: Path) -> Path:
    """Validate exact membership, bytes and regular-file bounds before extraction."""
    expected = sources(root)
    with tarfile.open(archive) as package:
        members = package.getmembers()
        names = [member.name for member in members]
        if names != [f"{PROJECT}/{name}" for name in expected]:
            raise ValueError("Archive membership differs from the reviewed inventory")
        for member, (name, content) in zip(members, expected.items()):
            if (
                not member.isfile()
                or member.size != len(content)
                or member.size > MAX_FILE
                or member.mode != (0o755 if (root / name).stat().st_mode & 0o111 else 0o644)
            ):
                raise ValueError("Unexpected archive file type or size")
            stream = package.extractfile(member)
            if stream is None or stream.read(MAX_FILE + 1) != content:
                raise ValueError("Archive bytes differ from the source overlay")
            target = destination / PROJECT / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(member.mode)
    return destination / PROJECT


def verify(archive: Path, root: Path) -> None:
    """Exercise shipped code/resources outside the checkout without live services."""
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="integration-tests-source-install-") as directory:
        installed = unpack(archive, root, Path(directory))
        commands = [
            [sys.executable, "-m", "unittest", "hardware.test_offline_release_guards"],
            [sys.executable, "-m", "compileall", "-q", "hardware"],
        ]
        for command in commands:
            subprocess.run(command, cwd=installed, check=True)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError("Source archive changed during verification")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base")
    parser.add_argument("channel", choices=("beta", "rc", "nightly"))
    parser.add_argument("--output", type=Path, default=Path("release-dist"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    archive = build(root, args.base, args.channel, args.output)
    verify(archive, root)
    print(archive)


if __name__ == "__main__":
    main()
