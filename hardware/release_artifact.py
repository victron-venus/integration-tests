"""Build a read-only payload binding from independently pinned release files.

No download, extraction, package import, installation or device command occurs.
"""

import argparse
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

from hardware.device_runner import validate_release_artifact, verify_release_files


def pinned_bytes(path, expected, maximum):
    """Reject missing independent pins and unbounded local inputs."""
    if re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("An independent SHA-256 pin is required")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("Release input must be a bounded regular file")
    data = path.read_bytes()
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
    prefix = repository.split("/")[1]
    files, names, total = {}, set(), 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as package:
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
