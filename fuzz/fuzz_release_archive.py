"""Hash synthetic in-memory archives through the real bounded parser."""
import gzip
from pathlib import Path
import re
import sys
import tarfile
import zlib

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with atheris.instrument_imports():
    from hardware.release_artifact import _archive_payload


@atheris.instrument_func
def test_one_input(data):
    try:
        # Recompute the transport checksum so mutations reach TAR parsing.
        files = _archive_payload(gzip.compress(data, mtime=0), "inverter-control")
    except (ValueError, OSError, EOFError, tarfile.TarError, zlib.error):
        return
    assert len(files) <= 4096
    for name, digest in files.items():
        assert name and not name.startswith("/") and "\\" not in name
        assert all(part not in ("", ".", "..") for part in name.split("/"))
        assert re.fullmatch("[0-9a-f]{64}", digest)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
