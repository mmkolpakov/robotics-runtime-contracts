from __future__ import annotations

from pathlib import Path

import pytest

from robotics_runtime_contracts.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "scenario" / "valid" / "simulation-realtime.yaml"


def test_cli_validates_yaml_document(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(FIXTURE)]) == 0

    captured = capsys.readouterr()
    assert captured.out == "valid: acceptance-scenario.v1\n"
    assert captured.err == ""


def test_cli_reports_contract_path_for_invalid_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = tmp_path / "invalid.yaml"
    document.write_text(
        "schema_version: acceptance-scenario.v1\nunknown: true\n",
        encoding="utf-8",
    )

    assert main(["validate", str(document)]) == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "invalid: $" in captured.err


def test_cli_quiet_mode_has_no_success_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", "--quiet", str(FIXTURE)]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
