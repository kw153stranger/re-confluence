"""CLI가 6개 서브커맨드를 노출하고 각 스텁이 실행되는지 검증 (DoD M0)."""

from typer.testing import CliRunner

from reconf.cli import app

runner = CliRunner()

STAGES = ["export", "analyze", "cluster", "build", "review", "upload"]
STUB_STAGES = ["build", "review", "upload"]  # M2 미구현 → 스텁(정상 종료)
SERVICE_STAGES = ["export", "analyze", "cluster"]  # 외부 서비스 필요


def test_help_lists_all_stages():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in STAGES:
        assert stage in result.output


def test_each_stage_shows_help():
    for stage in STAGES:
        result = runner.invoke(app, [stage, "--help"])
        assert result.exit_code == 0, f"{stage} --help failed"


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "reconf" in result.output


def test_stub_stages_run(tmp_path):
    """아직 미구현 단계(build/review/upload) 스텁은 정상 종료하고 vault를 만든다."""
    vault = tmp_path / "vault"
    for stage in STUB_STAGES:
        result = runner.invoke(app, [stage, "--vault", str(vault)])
        assert result.exit_code == 0, f"{stage} failed: {result.output}"
    assert (vault / "raw").is_dir()


def test_export_fails_gracefully_without_credentials(tmp_path):
    """Confluence 접속 정보가 없으면 traceback 없이 오류 메시지 + exit 1."""
    vault = tmp_path / "vault"
    result = runner.invoke(app, ["export", "--vault", str(vault)])
    assert result.exit_code == 1
    assert "오류" in result.output


def test_empty_vault_stages_no_crash(tmp_path):
    """raw/analysis가 비어도 analyze/cluster는 크래시 없이 종료한다."""
    vault = tmp_path / "vault"
    for stage in ["analyze", "cluster"]:
        result = runner.invoke(app, [stage, "--vault", str(vault)])
        assert result.exit_code == 0, f"{stage}: {result.output}"


def test_config_loading_from_file(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("source:\n  space: MYSPACE\nvault: ./v\n", encoding="utf-8")
    vault = str(tmp_path / "vault")
    result = runner.invoke(app, ["build", "--config", str(cfg), "--vault", vault])
    assert result.exit_code == 0
