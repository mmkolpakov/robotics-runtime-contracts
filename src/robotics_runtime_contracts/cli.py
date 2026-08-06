from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

import yaml

from robotics_runtime_contracts import (
    ensure_finite_numbers,
    loads_mapping,
    resolve_schema_name,
    validate_document,
)
from robotics_runtime_contracts._qualification import validate_qualification_artifacts
from robotics_runtime_contracts.document_ops import (
    create_execution_permit,
    describe_schema,
    resolve_merge_patches,
    semantic_diff,
)


class CLIArgumentError(ValueError):
    """Raised for stable machine-readable command-line parsing failures."""

    error_id = "cli.arguments_invalid"


class ContractArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CLIArgumentError(message)


def _add_extension_schemas(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--extension-schema",
        action="append",
        default=[],
        metavar="URI=PATH",
        help="supply a digest-pinned domain extension schema; may be repeated",
    )


def _parser() -> argparse.ArgumentParser:
    parser = ContractArgumentParser(
        prog="robotics-contracts",
        description="Validate and operate on robotics runtime contract documents.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="diagnostic and status output format",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate JSON or YAML documents")
    validate.add_argument(
        "documents",
        nargs="+",
        help="one or more document paths; - reads one document from standard input",
    )
    validate.add_argument("--schema", help="override schema_version")
    _add_extension_schemas(validate)
    validate.add_argument("--quiet", action="store_true")

    qualification = subparsers.add_parser(
        "validate-qualification",
        help="validate a complete qualification artifact set",
    )
    qualification.add_argument(
        "--artifact",
        action="append",
        required=True,
        metavar="KIND:SUBJECT=PATH",
    )
    _add_extension_schemas(qualification)
    qualification.add_argument("--quiet", action="store_true")
    qualification.add_argument("--output", metavar="PATH")

    describe = subparsers.add_parser("describe", help="describe a published schema")
    describe.add_argument("schema")

    diff = subparsers.add_parser("diff", help="create an RFC 7396 document patch")
    diff.add_argument("source", metavar="SOURCE")
    diff.add_argument("target", metavar="TARGET")
    diff.add_argument("--output", metavar="PATH")

    scenario = subparsers.add_parser("scenario", help="operate on scenario documents")
    scenario_commands = scenario.add_subparsers(dest="scenario_command", required=True)
    resolve = scenario_commands.add_parser(
        "resolve",
        help="materialize RFC 7396 overlays into one validated scenario",
    )
    resolve.add_argument("base", metavar="BASE")
    resolve.add_argument("--overlay", action="append", default=[], required=True, metavar="PATH")
    resolve.add_argument("--output", required=True, metavar="PATH")
    resolve.add_argument("--trace-output", metavar="PATH")
    _add_extension_schemas(resolve)

    permit = subparsers.add_parser("permit", help="operate on physical-execution permits")
    permit_commands = permit.add_subparsers(dest="permit_command", required=True)
    permit_init = permit_commands.add_parser(
        "init",
        help="create a validated unsigned execution-permit.v1 predicate",
    )
    permit_init.add_argument("--scenario-sha256", required=True)
    permit_init.add_argument("--image-digest", required=True)
    permit_init.add_argument("--trust-policy-sha256", required=True)
    permit_init.add_argument("--environment", required=True, choices=("hil", "real_robot"))
    permit_init.add_argument("--target-id", required=True)
    permit_init.add_argument(
        "--identity-kind",
        required=True,
        choices=(
            "udev_serial",
            "pci_device",
            "mavlink_system_component",
            "x509_spki",
            "tpm_ek",
            "vendor_soc",
        ),
    )
    permit_init.add_argument("--identity-sha256", required=True)
    permit_init.add_argument(
        "--hardware-scope",
        action="append",
        required=True,
        choices=("compute", "sensor", "controller"),
    )
    permit_init.add_argument("--operator-id", required=True)
    permit_init.add_argument("--approver-id", required=True)
    permit_init.add_argument("--interlock-reference", required=True)
    permit_init.add_argument("--interlock-sha256", required=True)
    permit_init.add_argument("--validity-sec", type=int, default=900)
    permit_init.add_argument("--output", required=True, metavar="PATH")
    return parser


def _read_document_source(path: str) -> tuple[Mapping[str, Any], bytes]:
    source = sys.stdin.buffer.read() if path == "-" else Path(path).read_bytes()
    document = loads_mapping(source, source_name=path)
    return document, source


def _read_document(path: str) -> Mapping[str, Any]:
    return _read_document_source(path)[0]


def _write_document(path: str | Path, document: Mapping[str, Any]) -> Path:
    ensure_finite_numbers(document)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() in {".yaml", ".yml"}:
        content = yaml.safe_dump(dict(document), sort_keys=False)
    else:
        content = json.dumps(document, allow_nan=False, indent=2, sort_keys=True) + "\n"
    output.write_text(content, encoding="utf-8")
    return output


def _read_extension_schemas(values: Sequence[str]) -> dict[str, bytes]:
    schemas: dict[str, bytes] = {}
    for value in values:
        uri, separator, path = value.partition("=")
        if not separator or not uri or not path:
            raise ValueError("--extension-schema must use URI=PATH")
        if uri in schemas:
            raise ValueError(f"duplicate extension schema URI: {uri}")
        schemas[uri] = Path(path).read_bytes()
    return schemas


def _emit(payload: Mapping[str, Any], *, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, allow_nan=False, sort_keys=True))
    else:
        print(str(payload.get("message", json.dumps(payload, allow_nan=False, sort_keys=True))))


def _emit_error(error: Exception, *, output_format: str) -> None:
    payload: dict[str, Any] = {
        "error_id": getattr(error, "error_id", "input.invalid"),
        "message": str(error),
    }
    json_path = getattr(error, "json_path", None)
    if json_path is not None:
        payload["path"] = json_path
    if output_format == "json":
        print(
            json.dumps({"error": payload}, allow_nan=False, sort_keys=True),
            file=sys.stderr,
        )
    else:
        print(f"invalid: {payload['message']} [{payload['error_id']}]", file=sys.stderr)


def _scenario_resolve(arguments: argparse.Namespace) -> None:
    extension_schemas = _read_extension_schemas(arguments.extension_schema)
    base, base_source = _read_document_source(arguments.base)
    overlay_sources = [_read_document_source(path) for path in arguments.overlay]
    overlays = [document for document, _source in overlay_sources]
    inputs = {
        Path(path).expanduser().resolve()
        for path in (arguments.base, *arguments.overlay)
        if path != "-"
    }
    output_path = Path(arguments.output).expanduser().resolve()
    trace_path = (
        Path(arguments.trace_output).expanduser().resolve() if arguments.trace_output else None
    )
    if output_path in inputs or trace_path in inputs:
        raise ValueError("scenario outputs must not overwrite an input document")
    if trace_path is not None and trace_path == output_path:
        raise ValueError("--output and --trace-output must identify different files")
    resolved = resolve_merge_patches(
        base,
        overlays,
        extension_schemas=extension_schemas or None,
    )
    output = _write_document(arguments.output, resolved)
    trace = {
        "base": {
            "path": arguments.base,
            "sha256": hashlib.sha256(base_source).hexdigest(),
        },
        "overlays": [
            {
                "path": path,
                "sha256": hashlib.sha256(source).hexdigest(),
            }
            for path, (_document, source) in zip(
                arguments.overlay,
                overlay_sources,
                strict=True,
            )
        ],
        "resolved": str(output),
        "resolved_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    if arguments.trace_output:
        _write_document(arguments.trace_output, trace)
    _emit({**trace, "message": f"resolved: {output}"}, output_format=arguments.format)


def _permit_init(arguments: argparse.Namespace) -> None:
    permit = create_execution_permit(
        scenario_sha256=arguments.scenario_sha256,
        image_digest=arguments.image_digest,
        trust_policy_sha256=arguments.trust_policy_sha256,
        environment=arguments.environment,
        target_id=arguments.target_id,
        identity_kind=arguments.identity_kind,
        identity_sha256=arguments.identity_sha256,
        hardware_scope=arguments.hardware_scope,
        operator_id=arguments.operator_id,
        approver_id=arguments.approver_id,
        interlock_reference=arguments.interlock_reference,
        interlock_sha256=arguments.interlock_sha256,
        validity_sec=arguments.validity_sec,
    )
    output = _write_document(arguments.output, permit)
    _emit(
        {
            "message": f"created unsigned permit: {output}",
            "permit": str(output),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        },
        output_format=arguments.format,
    )


def main(argv: Sequence[str] | None = None) -> int:
    tokens = list(argv) if argv is not None else sys.argv[1:]
    output_format = "text"
    for index, token in enumerate(tokens):
        if token == "--format" and index + 1 < len(tokens):
            output_format = tokens[index + 1]
        elif token.startswith("--format="):
            output_format = token.partition("=")[2]
    try:
        arguments = _parser().parse_args(tokens)
    except CLIArgumentError as error:
        _emit_error(
            error,
            output_format=output_format if output_format in {"text", "json"} else "text",
        )
        return 2
    documents: list[tuple[str, str]] = []
    try:
        if arguments.command == "validate":
            extension_schemas = _read_extension_schemas(arguments.extension_schema)
            if arguments.schema is not None and len(arguments.documents) != 1:
                raise ValueError("--schema requires exactly one document")
            if arguments.documents.count("-") > 1:
                raise ValueError("standard input may be selected only once")
            for path in arguments.documents:
                document = _read_document(path)
                validate_document(
                    document,
                    schema=arguments.schema,
                    extension_schemas=extension_schemas or None,
                )
                selected = arguments.schema or document.get("schema_version")
                if not isinstance(selected, str):
                    raise ValueError("document must declare schema_version")
                documents.append((path, resolve_schema_name(selected)))
        elif arguments.command == "validate-qualification":
            result = validate_qualification_artifacts(
                arguments.artifact,
                _read_extension_schemas(arguments.extension_schema),
            )
            if arguments.output:
                _write_document(arguments.output, result)
        elif arguments.command == "describe":
            print(
                json.dumps(
                    describe_schema(arguments.schema),
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        elif arguments.command == "diff":
            patch = semantic_diff(
                _read_document(arguments.source),
                _read_document(arguments.target),
            )
            if arguments.output:
                _write_document(arguments.output, patch)
            else:
                print(json.dumps(patch, allow_nan=False, indent=2, sort_keys=True))
            return 0
        elif arguments.command == "scenario":
            _scenario_resolve(arguments)
            return 0
        elif arguments.command == "permit":
            _permit_init(arguments)
            return 0
        else:
            raise AssertionError(f"unhandled command: {arguments.command}")
    except (OSError, ValueError, yaml.YAMLError) as error:
        _emit_error(error, output_format=arguments.format)
        return 1

    if arguments.quiet:
        return 0
    if arguments.command == "validate-qualification":
        _emit(
            {"message": "valid: qualification artifact set", "status": "valid"},
            output_format=arguments.format,
        )
    elif len(documents) == 1:
        _emit(
            {"message": f"valid: {documents[0][1]}", "schema": documents[0][1]},
            output_format=arguments.format,
        )
    else:
        for path, schema_name in documents:
            _emit(
                {
                    "message": f"valid: {path}: {schema_name}",
                    "path": path,
                    "schema": schema_name,
                },
                output_format=arguments.format,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
