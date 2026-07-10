"""reconf CLI — typer 진입점 (구현설계 §5).

6개 서브커맨드(export/analyze/cluster/build/review/upload)를 제공하며,
공통 옵션(--vault/--config/--resume/--dry-run)을 통해 단계 독립·재실행한다.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated

import typer

from . import __version__
from .config import Config
from .logging_setup import get_logger, setup_logging
from .store import Store

app = typer.Typer(
    name="reconf",
    help="Confluence AI 재구성 — 업무 중심 IA 배치 파이프라인",
    no_args_is_help=True,
    add_completion=False,
)

log = get_logger("cli")

# 공통 옵션 타입 별칭
ConfigOpt = Annotated[str | None, typer.Option("--config", "-c", help="config.yaml 경로")]
VaultOpt = Annotated[str | None, typer.Option("--vault", help="vault 디렉토리 경로")]
ResumeOpt = Annotated[bool, typer.Option("--resume", help="중단 지점부터 재실행")]
DryRunOpt = Annotated[bool, typer.Option("--dry-run", help="변경 없이 시뮬레이션")]


def _prepare(config: str | None, vault: str | None) -> tuple[Config, Store]:
    setup_logging()
    cfg = Config.load(config)
    store = Store(vault or cfg.vault)
    return cfg, store


@contextmanager
def _friendly_errors():
    """설정 누락 등 RuntimeError를 traceback 없이 깔끔히 종료(exit 1)."""
    try:
        yield
    except RuntimeError as e:
        typer.secho(f"오류: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None


@app.command()
def version() -> None:
    """버전 출력."""
    typer.echo(f"reconf {__version__}")


@app.command()
def export(
    config: ConfigOpt = None,
    vault: VaultOpt = None,
    resume: ResumeOpt = False,
    dry_run: DryRunOpt = False,
) -> None:
    """[Export] Confluence 페이지·첨부 수집 → Raw Markdown."""
    cfg, store = _prepare(config, vault)
    from . import export as _stage

    with _friendly_errors():
        _stage.run(cfg, store, resume=resume, dry_run=dry_run)


@app.command()
def analyze(
    config: ConfigOpt = None,
    vault: VaultOpt = None,
    resume: ResumeOpt = False,
    dry_run: DryRunOpt = False,
) -> None:
    """[Analyze] 로컬 LLM 분류·요약 → analysis JSON."""
    cfg, store = _prepare(config, vault)
    from . import analyze as _stage

    with _friendly_errors():
        _stage.run(cfg, store, resume=resume, dry_run=dry_run)


@app.command()
def cluster(
    config: ConfigOpt = None,
    vault: VaultOpt = None,
    resume: ResumeOpt = False,
    dry_run: DryRunOpt = False,
) -> None:
    """[Cluster] 동일 업무 병합·연도 그룹핑·중복 탐지."""
    cfg, store = _prepare(config, vault)
    from . import cluster as _stage

    with _friendly_errors():
        _stage.run(cfg, store, resume=resume, dry_run=dry_run)


@app.command()
def build(
    config: ConfigOpt = None,
    vault: VaultOpt = None,
    resume: ResumeOpt = False,
    dry_run: DryRunOpt = False,
) -> None:
    """[Build] 업무 중심 IA·Page Properties·Labels 생성."""
    cfg, store = _prepare(config, vault)
    from . import build as _stage

    _stage.run(cfg, store, resume=resume, dry_run=dry_run)


@app.command()
def review(
    config: ConfigOpt = None,
    vault: VaultOpt = None,
    export_queue: Annotated[
        bool, typer.Option("--export-queue", help="검수 큐 export")
    ] = False,
    apply: Annotated[
        str | None, typer.Option("--apply", help="검수 결과(review.json) 반영")
    ] = None,
    resume: ResumeOpt = False,
    dry_run: DryRunOpt = False,
) -> None:
    """[Review] 사람 검수 — 분류 확인·수정·승인."""
    cfg, store = _prepare(config, vault)
    from . import review as _stage

    _stage.run(cfg, store, export_queue=export_queue, apply=apply, resume=resume, dry_run=dry_run)


@app.command()
def upload(
    config: ConfigOpt = None,
    vault: VaultOpt = None,
    target_space: Annotated[
        str | None, typer.Option("--target-space", help="신규 Space key")
    ] = None,
    resume: ResumeOpt = False,
    dry_run: DryRunOpt = False,
) -> None:
    """[Upload] 신규 Space 생성·멱등 업로드."""
    cfg, store = _prepare(config, vault)
    from . import upload as _stage

    with _friendly_errors():
        _stage.run(cfg, store, target_space=target_space, resume=resume, dry_run=dry_run)


if __name__ == "__main__":
    app()
