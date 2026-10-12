"""Release provenance and changed-payload rejection without device access."""

import copy
import hashlib
import io
import json
import tarfile

import pytest

from hardware.device_runner import validate_release_artifact, verify_release_files
from hardware.release_artifact import bind_release


def sha(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def released(tmp_path):
    files = {
        "version": b"1.2.3\n",
        "main.py": b"# entry\n",
        "inverter_control/dbus_native.py": b"# client\n",
        "inverter_control/controller.py": b"# complete payload\n",
    }
    archive = tmp_path / "inverter-control-1.2.3.tar.gz"
    with tarfile.open(archive, "w:gz") as package:
        for name, data in files.items():
            entry = tarfile.TarInfo("inverter-control/" + name)
            entry.size = len(data)
            package.addfile(entry, io.BytesIO(data))
    manifest = tmp_path / "release-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "repository": "victron-venus/inverter-control",
                "tag": "v1.2.3-rc.1",
                "version": "1.2.3",
                "source_sha": "a" * 40,
                "assets": [
                    {
                        "name": archive.name,
                        "size": archive.stat().st_size,
                        "sha256": sha(archive.read_bytes()),
                    }
                ],
            }
        )
    )
    arguments = (archive, manifest, sha(archive.read_bytes()), sha(manifest.read_bytes()), "v1.2.3")
    root = tmp_path / "installed"
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return arguments, root


def test_promoted_release_keeps_rc_provenance_and_all_payload_files(released):
    arguments, root = released
    artifact = bind_release(*arguments)
    assert artifact["release_tag"] == "v1.2.3"
    assert artifact["build_tag"] == "v1.2.3-rc.1"
    assert len(artifact["files"]) == 4
    assert len(verify_release_files(root, artifact)) == 64


@pytest.mark.parametrize("name", ["version", "main.py", "inverter_control/controller.py"])
def test_same_native_client_does_not_hide_changed_application(released, name):
    arguments, root = released
    artifact = bind_release(*arguments)
    (root / name).write_bytes(b"changed code without changing native client")
    with pytest.raises(ValueError, match="payload mismatch"):
        verify_release_files(root, artifact)


@pytest.mark.parametrize("which", [0, 1])
def test_changed_release_inputs_fail_independent_digest_pin(released, which):
    arguments, _ = released
    arguments[which].write_bytes(b"changed")
    with pytest.raises(ValueError, match="independent SHA-256"):
        bind_release(*arguments)


def test_wrong_tag_cannot_relabel_same_payload(released):
    arguments, _ = released
    with pytest.raises(ValueError, match="tag does not match"):
        bind_release(*arguments[:-1], "v9.9.9")


@pytest.mark.parametrize("name", ["../outside", "/outside", "inverter_control/../outside", "a\\b"])
def test_unsafe_inventory_paths_fail_without_reading_payload(released, name):
    arguments, _ = released
    artifact = copy.deepcopy(bind_release(*arguments))
    artifact["files"][name] = "a" * 64
    with pytest.raises(ValueError, match="path or digest"):
        validate_release_artifact(artifact)


def test_symlink_cannot_substitute_external_code(released, tmp_path):
    arguments, root = released
    artifact = bind_release(*arguments)
    outside = tmp_path / "outside"
    outside.write_bytes((root / "main.py").read_bytes())
    (root / "main.py").unlink()
    (root / "main.py").symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        verify_release_files(root, artifact)


def test_oversized_installed_file_is_bounded(released):
    arguments, root = released
    artifact = bind_release(*arguments)
    with (root / "main.py").open("wb") as source:
        source.truncate(8 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="size limit"):
        verify_release_files(root, artifact)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../outside", tarfile.REGTYPE),
        ("inverter-control/link", tarfile.SYMTYPE),
        ("inverter-control/main.py", tarfile.REGTYPE),
    ],
)
def test_archive_traversal_links_and_duplicate_entries_are_rejected(released, name, kind):
    arguments, _ = released
    archive, manifest, _, _, tag = arguments
    with tarfile.open(archive, "r:gz") as package:
        entries = [(member, package.extractfile(member).read()) for member in package]
    with tarfile.open(archive, "w:gz") as package:
        for member, data in entries:
            package.addfile(member, io.BytesIO(data))
        member = tarfile.TarInfo(name)
        member.type = kind
        member.linkname = "/outside" if kind == tarfile.SYMTYPE else ""
        package.addfile(member, io.BytesIO(b""))
    metadata = json.loads(manifest.read_text())
    metadata["assets"][0].update(size=archive.stat().st_size, sha256=sha(archive.read_bytes()))
    manifest.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="archive entry|payload files"):
        bind_release(archive, manifest, sha(archive.read_bytes()), sha(manifest.read_bytes()), tag)
