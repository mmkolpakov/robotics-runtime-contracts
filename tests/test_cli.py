from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from robotics_runtime_contracts.cli import main
from tests.support import qualification_specifications

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "scenario" / "valid" / "simulation-realtime.yaml"


def test_cli_validates_yaml_document(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(FIXTURE)]) == 0

    captured = capsys.readouterr()
    assert captured.out == "valid: acceptance-scenario.v4\n"
    assert captured.err == ""


def test_cli_reports_contract_path_for_invalid_document(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    document = tmp_path / "invalid.yaml"
    document.write_text(
        "schema_version: acceptance-scenario.v4\nunknown: true\n",
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


def test_cli_validates_multiple_documents_in_one_process(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate", "--quiet", str(FIXTURE), str(FIXTURE)]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_cli_rejects_schema_override_for_a_batch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "validate",
                "--schema",
                "acceptance-scenario.v4",
                str(FIXTURE),
                str(FIXTURE),
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert "--schema requires exactly one document" in captured.err


def test_cli_rejects_an_incomplete_qualification_artifact_set(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "validate-qualification",
                "--artifact",
                f"scenario:scenario.json={FIXTURE}",
                "--quiet",
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert "requires exactly one acceptance_run" in captured.err


def test_cli_validates_a_complete_qualification_and_writes_exact_metadata(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    specifications = qualification_specifications("transport")
    artifacts = [
        value for specification in specifications for value in ("--artifact", specification)
    ]
    output = tmp_path / "validated-artifacts.json"

    assert main(["validate-qualification", *artifacts, "--quiet", "--output", str(output)]) == 0

    metadata = json.loads(output.read_text(encoding="utf-8"))
    assert metadata["run_id"] == "run-00000000-0000-4000-8000-000000000001"
    assert {item["subject_name"]: item["sha256"] for item in metadata["artifacts"]} == {
        specification.partition(":")[2].partition("=")[0]: hashlib.sha256(
            Path(specification.partition("=")[2]).read_bytes()
        ).hexdigest()
        for specification in specifications
    }
    assert capsys.readouterr().out == ""


def test_cli_rejects_a_noncanonical_qualification_subject(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "validate-qualification",
                "--artifact",
                f"scenario:../scenario.json={FIXTURE}",
                "--quiet",
            ]
        )
        == 1
    )

    assert "non-canonical qualification subject name" in capsys.readouterr().err
