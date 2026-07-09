from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"
VALID_DIR = ROOT / "fixtures" / "valid"
INVALID_DIR = ROOT / "fixtures" / "invalid"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_key(path: Path) -> str:
    return path.name.replace(".v1.schema.json", "")


def build_registry() -> tuple[dict[str, dict], Registry]:
    schemas = {
        schema_key(path): load_json(path)
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }
    pairs = []
    for schema in schemas.values():
        resource = Resource.from_contents(schema)
        pairs.append((schema["$id"], resource))
        pairs.append((Path(schema["$id"]).name, resource))
    return schemas, Registry().with_resources(pairs)


SCHEMAS, REGISTRY = build_registry()

VALID_SCHEMA_BY_FIXTURE = {
    "artifact-store-policy.json": "artifact-store-policy",
    "domain-extension.json": "domain-extension-manifest",
    "evidence-dry-run.json": "evidence-manifest",
    "evidence-manifest.json": "evidence-manifest",
    "model-artifact.json": "model-artifact",
    "perception-provider-custom-approved.json": "perception-provider",
    "perception-provider-standard.json": "perception-provider",
    "run-metrics.json": "run-metrics",
    "runtime-profile.json": "runtime-profile",
    "scenario-composition.json": "scenario-composition-manifest",
    "scenario-minimal.json": "scenario-manifest",
    "stack-compatibility.json": "stack-compatibility",
    "stack-lock.json": "stack-lock",
}

INVALID_SCHEMA_BY_FIXTURE = {
    "composition-no-trace.json": "scenario-composition-manifest",
    "evidence-dry-run-pass.json": "evidence-manifest",
    "evidence-pass-with-skip.json": "evidence-manifest",
    "perception-provider-custom-missing-approval.json": "perception-provider",
    "scenario-hil-missing-confirmation.json": "scenario-manifest",
    "scenario-missing-wall-timeout.json": "scenario-manifest",
    "stack-lock-unknown-commit.json": "stack-lock",
    "stack-lock-unknown-digest.json": "stack-lock",
}


@pytest.mark.parametrize("schema_name,schema", sorted(SCHEMAS.items()))
def test_schema_is_valid(schema_name: str, schema: dict) -> None:
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].endswith(f"{schema_name}.v1.schema.json")


@pytest.mark.parametrize("fixture_path", sorted(VALID_DIR.glob("*.json")))
def test_valid_fixtures(fixture_path: Path) -> None:
    schema = SCHEMAS[VALID_SCHEMA_BY_FIXTURE[fixture_path.name]]
    validator = Draft202012Validator(schema, registry=REGISTRY)
    validator.validate(load_json(fixture_path))


@pytest.mark.parametrize("fixture_path", sorted(INVALID_DIR.glob("*.json")))
def test_invalid_fixtures(fixture_path: Path) -> None:
    schema = SCHEMAS[INVALID_SCHEMA_BY_FIXTURE[fixture_path.name]]
    validator = Draft202012Validator(schema, registry=REGISTRY)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(load_json(fixture_path))


def test_no_unmapped_fixtures() -> None:
    valid_names = {path.name for path in VALID_DIR.glob("*.json")}
    invalid_names = {path.name for path in INVALID_DIR.glob("*.json")}
    assert valid_names == set(VALID_SCHEMA_BY_FIXTURE)
    assert invalid_names == set(INVALID_SCHEMA_BY_FIXTURE)


def test_wall_timeout_exceeds_duration() -> None:
    scenario = load_json(VALID_DIR / "scenario-minimal.json")
    assert scenario["simulation"]["wall_timeout_sec"] > scenario["simulation"]["duration_sec"]


def test_evidence_pass_requires_executed_process_execution_check() -> None:
    evidence = load_json(VALID_DIR / "evidence-manifest.json")
    assert any(
        check["name"] == "process_execution" and check["result"] == "executed"
        for check in evidence["checks"]
    )
    schema = SCHEMAS["evidence-manifest"]
    validator = Draft202012Validator(schema, registry=REGISTRY)

    without_process_execution = {
        **evidence,
        "checks": [c for c in evidence["checks"] if c["name"] != "process_execution"],
    }
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(without_process_execution)


def test_evidence_dry_run_cannot_claim_pass() -> None:
    dry_run = load_json(VALID_DIR / "evidence-dry-run.json")
    assert dry_run["result"] == "not_run"
    schema = SCHEMAS["evidence-manifest"]
    validator = Draft202012Validator(schema, registry=REGISTRY)

    faked_pass = {**dry_run, "result": "pass"}
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(faked_pass)


def test_stack_lock_rejects_unknown_literals() -> None:
    schema = SCHEMAS["stack-lock"]
    commit_pattern = schema["properties"]["repositories"]["additionalProperties"]["properties"][
        "commit"
    ]["pattern"]
    digest_pattern = schema["properties"]["images"]["additionalProperties"]["properties"][
        "digest"
    ]["pattern"]
    assert "unknown" not in commit_pattern
    assert "unknown" not in digest_pattern


def test_package_exposes_schemas() -> None:
    from robotics_runtime_contracts import schema_dir, schema_path

    assert schema_dir().is_dir()
    assert schema_path("stack-lock.v1.schema.json").is_file()


def test_packaged_schemas_match_repository_schemas() -> None:
    from robotics_runtime_contracts import schema_dir

    packaged = {
        path.name: path.read_text(encoding="utf-8")
        for path in schema_dir().glob("*.schema.json")
    }
    repository = {
        path.name: path.read_text(encoding="utf-8")
        for path in SCHEMA_DIR.glob("*.schema.json")
    }
    assert packaged == repository
