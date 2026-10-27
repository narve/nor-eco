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


def test_a_source_that_flips_between_versions_is_stored_once_per_version(tmp_path):
    kw = dict(url="https://example.org/x", raw_dir=tmp_path, registry=REG, retrieved="2026-01-01")
    a = common.write_snapshot("test-src", b"version A", ".html", **kw)
    b = common.write_snapshot("test-src", b"version B", ".html", **kw)   # same day, different content: new file, nothing overwritten
    again_a = common.write_snapshot("test-src", b"version A", ".html", **kw)
    assert a.path != b.path and a.path.read_bytes() == b"version A" and b.path.read_bytes() == b"version B"
    assert again_a.unchanged and again_a.path == a.path
    assert len(list((tmp_path / "test-src").iterdir())) == 2


def test_volatile_html_attributes_are_normalized():
    one = b'<meta name="csp-nonce" content="AAA"/><script nonce="AAA"></script><div id="fin-figur-ca9d0a34-8000-4d51-aded-6556ac7cf626"></div>'
    two = b'<meta name="csp-nonce" content="BBB"/><script nonce="BBB"></script><div id="fin-figur-493caf9e-38cd-46a4-a715-926a31178983"></div>'
    assert common.normalize_html(one) == common.normalize_html(two)


def test_same_day_snapshots_are_ordered_by_sequence_not_by_file_name(tmp_path):
    kw = dict(url="https://example.org/x", raw_dir=tmp_path, registry=REG, retrieved="2026-01-01")
    common.write_snapshot("test-src", b"one", ".json", **kw)
    common.write_snapshot("test-src", b"two", ".json", **kw)
    entries = sorted(common._load_manifest(tmp_path / "MANIFEST.yaml"), key=common.snapshot_order)
    assert [e["file"] for e in entries] == ["test-src/2026-01-01.json", "test-src/2026-01-01-2.json"]  # «-2» is the newer one
