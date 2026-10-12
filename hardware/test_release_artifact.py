"""Release provenance and changed-payload rejection without device access."""

import copy
import hashlib
import io
import json
import tarfile
from types import SimpleNamespace

import pytest

from hardware import release_artifact
from hardware.device_runner import _identity_text, validate_release_artifact, verify_release_files
from hardware.release_artifact import bind_release, pinned_bytes


def sha(data):
    return hashlib.sha256(data).hexdigest()


def test_expanded_reader_bounds_a_single_large_read():
    reads = []

    class RecordingInput(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    reader = release_artifact._BoundedArchiveReader(RecordingInput(b"x" * 20), 8)
    with pytest.raises(ValueError, match="Expanded release archive"):
        reader.read(10**9)
    assert reads == [9]


def test_expanded_reader_bounds_cumulative_reads_and_allows_exact_limit():
    reader = release_artifact._BoundedArchiveReader(io.BytesIO(b"x" * 8), 8)
    assert reader.read(3) == b"xxx"
    assert reader.read() == b"xxxxx"
    assert reader.read() == b""
    reader = release_artifact._BoundedArchiveReader(io.BytesIO(b"x" * 9), 8)
    assert reader.read(3) == b"xxx"
    with pytest.raises(ValueError, match="Expanded release archive"):
        reader.read(6)


@pytest.mark.parametrize("format", [tarfile.PAX_FORMAT, tarfile.GNU_FORMAT])
def test_compressed_extended_headers_cannot_bypass_expanded_limit(monkeypatch, format):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz", format=format) as package:
        member = tarfile.TarInfo("inverter-control/version")
        member.size = 1
        if format == tarfile.PAX_FORMAT:
            member.pax_headers = {"comment": "x" * 16384}
        else:
            member.name = "inverter-control/" + "x" * 16384
        package.addfile(member, io.BytesIO(b"1"))
    assert len(archive.getvalue()) < 1024
    monkeypatch.setattr(release_artifact, "MAX_EXPANDED_ARCHIVE", 4096)
    with pytest.raises(ValueError, match="Expanded release archive"):
        release_artifact._archive_payload(archive.getvalue(), "inverter-control")


def test_bounded_pax_metadata_keeps_original_payload_hash():
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz", format=tarfile.PAX_FORMAT) as package:
        member = tarfile.TarInfo("inverter-control/version")
        member.size = 5
        member.pax_headers = {"comment": "reviewed release", "mtime": "123.45"}
        package.addfile(member, io.BytesIO(b"1.2.3"))
    assert release_artifact._archive_payload(archive.getvalue(), "inverter-control") == {
        "version": sha(b"1.2.3")
    }


def test_release_read_remains_bounded_when_input_grows_after_stat():
    reads = []

    class GrowingInput(io.BytesIO):
        def read(self, size):
            reads.append(size)
            return super().read(size)

    path = SimpleNamespace(
        is_symlink=lambda: False,
        is_file=lambda: True,
        stat=lambda: SimpleNamespace(st_size=0),
        open=lambda mode: GrowingInput(b"0123456789"),
    )
    expected = sha(b"0123456789")
    with pytest.raises(ValueError, match="size limit"):
        pinned_bytes(path, expected, 4)
    assert reads == [5]


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


def test_identity_marker_limit_and_valid_utf8(tmp_path):
    marker = tmp_path / "version"
    marker.write_text("v3.75\n", encoding="utf-8")
    assert _identity_text(marker) == "v3.75"
    marker.write_bytes(b"x" * 4096)
    assert len(_identity_text(marker)) == 4096
    with marker.open("wb") as source:
        source.truncate(8 * 1024 * 1024)
    with pytest.raises(ValueError, match="Identity file exceeds size limit"):
        _identity_text(marker)


def test_operator_selected_absolute_root_does_not_depend_on_cwd(released, tmp_path, monkeypatch):
    arguments, root = released
    artifact = bind_release(*arguments)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert len(verify_release_files(root, artifact)) == 64


def test_payload_directory_symlink_cannot_escape_selected_root(released, tmp_path):
    arguments, root = released
    artifact = bind_release(*arguments)
    outside = tmp_path / "external-code"
    (root / "inverter_control").rename(outside)
    (root / "inverter_control").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
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
    archive_pin, manifest_pin = sha(archive.read_bytes()), sha(manifest.read_bytes())
    with pytest.raises(ValueError, match="archive entry|payload files"):
        bind_release(archive, manifest, archive_pin, manifest_pin, tag)
