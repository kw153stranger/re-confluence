"""CLI가 6개 서브커맨드를 노출하고 각 스텁이 실행되는지 검증 (DoD M0)."""

from typer.testing import CliRunner

from reconf.cli import app

runner = CliRunner()

STAGES = ["export", "analyze", "cluster", "build", "review", "upload"]


def test_help_lists_all_stages():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in STAGES:
        assert stage in result.output


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "reconf" in result.output


def test_each_stage_stub_runs(tmp_path):
    """각 단계 스텁이 오류 없이 실행되고 vault 디렉토리를 만든다."""
    vault = tmp_path / "vault"
    for stage in STAGES:
        result = runner.invoke(app, [stage, "--vault", str(vault)])
        assert result.exit_code == 0, f"{stage} failed: {result.output}"
    assert (vault / "raw").is_dir()


def test_config_loading_from_file(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("source:\n  space: MYSPACE\nvault: ./v\n", encoding="utf-8")
    vault = str(tmp_path / "vault")
    result = runner.invoke(app, ["export", "--config", str(cfg), "--vault", vault])
    assert result.exit_code == 0
