import pytest

from fetch import common

REG = {"test-src": {"id": "test-src"}}


def test_small_json_is_committed_and_manifest_written(tmp_path):
    s = common.write_snapshot("test-src", b'{"a":1}', ".json", url="https://example.org/x", raw_dir=tmp_path, registry=REG, retrieved="2026-01-01")
    assert s.committed and s.path == tmp_path / "test-src" / "2026-01-01.json" and s.path.read_bytes() == b'{"a":1}'
    assert "sha256" in (tmp_path / "MANIFEST.yaml").read_text()


def test_identical_content_is_not_written_twice(tmp_path):
    kw = dict(url="https://example.org/x", raw_dir=tmp_path, registry=REG)
    common.write_snapshot("test-src", b"same", ".json", retrieved="2026-01-01", **kw)
    again = common.write_snapshot("test-src", b"same", ".json", retrieved="2026-02-01", **kw)
    assert again.unchanged and not (tmp_path / "test-src" / "2026-02-01.json").exists()


def test_pdf_is_not_committed(tmp_path):
    s = common.write_snapshot("test-src", b"%PDF", ".pdf", url="https://example.org/a.pdf", raw_dir=tmp_path, registry=REG)
    assert not s.committed and "_large" in s.path.parts


def test_oversized_json_is_refused(tmp_path):
    with pytest.raises(common.FetchError, match="5 MB"):
        common.write_snapshot("test-src", b"x" * (5 * 1024 * 1024 + 1), ".json", url="https://example.org/b", raw_dir=tmp_path, registry=REG)


def test_unregistered_source_is_refused(tmp_path):
    with pytest.raises(common.UnregisteredSource):
        common.write_snapshot("nope", b"x", ".json", url="https://example.org/c", raw_dir=tmp_path, registry=REG)
