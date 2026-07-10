"""Store 경로 규칙·멱등 JSON I/O·content_hash 검증."""

from reconf.models import AnalysisResult
from reconf.store import Store, content_hash


def test_ensure_dirs(tmp_path):
    s = Store(tmp_path / "vault")
    s.ensure_dirs()
    assert s.raw_dir.is_dir()
    assert s.analysis_dir.is_dir()
    assert s.embeddings_dir.is_dir()
    assert s.build_dir.is_dir()


def test_write_read_json_roundtrip(tmp_path):
    s = Store(tmp_path / "vault")
    a = AnalysisResult(source_page_id="42", title_normalized="t", business="구매관리")
    path = s.analysis_path("42")
    s.write_json(path, a)
    assert path.exists()
    loaded = s.read_json(path, AnalysisResult)
    assert loaded == a


def test_write_is_idempotent_upsert(tmp_path):
    s = Store(tmp_path / "vault")
    a1 = AnalysisResult(source_page_id="42", title_normalized="t", business="A")
    a2 = AnalysisResult(source_page_id="42", title_normalized="t", business="B")
    path = s.analysis_path("42")
    s.write_json(path, a1)
    s.write_json(path, a2)  # 덮어쓰기 = UPSERT
    assert s.read_json(path, AnalysisResult).business == "B"


def test_content_hash_stable_and_sensitive():
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("hello!")
