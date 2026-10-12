"""Build a read-only payload binding from independently pinned release files.

No download, extraction, package import, installation or device command occurs.
"""

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

from hardware.device_runner import validate_release_artifact, verify_release_files

MAX_EXPANDED_ARCHIVE = 128 * 1024 * 1024


class _BoundedArchiveReader:
    """Limit decompressed bytes before tarfile can allocate extended headers."""

    def __init__(self, source, maximum):
        self.source = source
        self.maximum = maximum
        self.total = 0

    def read(self, size=-1):
        remaining = self.maximum - self.total + 1
        data = self.source.read(remaining if size < 0 else min(size, remaining))
        self.total += len(data)
        if self.total > self.maximum:
            raise ValueError("Expanded release archive exceeds size limit")
        return data


def pinned_bytes(path, expected, maximum):
    """Reject missing independent pins and unbounded local inputs."""
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("An independent SHA-256 pin is required")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("Release input must be a bounded regular file")
    with path.open("rb") as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Release input exceeds size limit")
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Release input does not match its independent SHA-256 pin")
    return data


def bind_release(archive, manifest, archive_sha256, manifest_sha256, release_tag):
    """Preserve promoted RC provenance while binding all distributed payload bytes."""
    raw = pinned_bytes(archive, archive_sha256, 32 * 1024 * 1024)
    metadata = json.loads(pinned_bytes(manifest, manifest_sha256, 1024 * 1024))
    repository = metadata.get("repository")
    if repository not in {"victron-venus/inverter-control", "victron-venus/inverter-climate"}:
        raise ValueError("Unsupported release repository")
    if release_tag not in {metadata["tag"], "v" + metadata["version"].removeprefix("v")}:
        raise ValueError("Release tag does not match the build or promoted version")
    assets = [a for a in metadata["assets"] if a.get("name") == archive.name]
    if (
        len(assets) != 1
        or assets[0].get("sha256") != archive_sha256
        or assets[0].get("size") != len(raw)
    ):
        raise ValueError("Release manifest does not bind the exact archive")
    files = _archive_payload(raw, repository.split("/")[1])
    artifact = {
        "repository": repository,
        "release_tag": release_tag,
        "build_tag": metadata["tag"],
        "source_sha": metadata["source_sha"],
        "manifest_sha256": manifest_sha256,
        "asset_name": archive.name,
        "asset_sha256": archive_sha256,
        "files": dict(sorted(files.items())),
    }
    return validate_release_artifact(artifact)


def _archive_payload(raw, prefix):
    """Hash bounded regular entries without extracting archive-controlled paths."""
    files, names, total = {}, set(), 0
    # PAX/GNU metadata is decoded inside tarfile before member iteration. Bound
    # that input too, not just the compressed archive and yielded file payloads.
    with (
        gzip.GzipFile(fileobj=io.BytesIO(raw)) as expanded,
        tarfile.open(
            fileobj=_BoundedArchiveReader(expanded, MAX_EXPANDED_ARCHIVE), mode="r|"
        ) as package,
    ):
        for member in package:
            parts = member.name.rstrip("/").split("/")
            canonical = "/".join(parts)
            if (
                len(names) >= 4096
                or canonical in names
                or parts[0] != prefix
                or any(part in {"", ".", ".."} for part in parts)
                or "\\" in member.name
            ):
                raise ValueError("Ambiguous or escaping release archive entry")
            names.add(canonical)
            if member.isdir():
                continue
            if not member.isfile() or len(parts) < 2 or member.size > 8 * 1024 * 1024:
                raise ValueError("Only bounded regular payload files are supported")
            total += member.size
            if total > 64 * 1024 * 1024:
                raise ValueError("Release payload is too large")
            name = "/".join(parts[1:])
            stream = package.extractfile(member)
            if stream is None:
                raise ValueError("Unreadable release archive entry")
            with stream:
                content = stream.read(member.size + 1)
            if len(content) != member.size:
                raise ValueError("Truncated release payload")
            files[name] = hashlib.sha256(content).hexdigest()
    return files


def main(argv=None):
    """Write a new binding; optionally compare an already-unpacked local payload."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--release-tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-root", type=Path)
    args = parser.parse_args(argv)
    artifact = bind_release(
        args.archive, args.manifest, args.archive_sha256, args.manifest_sha256, args.release_tag
    )
    if args.verify_root:
        verify_release_files(args.verify_root, artifact)
    with args.output.open("x") as target:
        target.write(json.dumps(artifact, indent=2) + "\n")
    print("Payload identity bound. This is not hardware qualification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
