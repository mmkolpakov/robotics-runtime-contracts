from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from robotics_runtime_contracts import (
    resolve_schema_name,
    validate_document,
)
from robotics_runtime_contracts._qualification import (
    validate_qualification_artifacts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="robotics-contracts",
        description="Validate robotics runtime contract documents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser(
        "validate",
        help="validate a JSON or YAML document",
    )
    validate.add_argument(
        "documents",
        nargs="+",
        help="one or more document paths; - reads one document from standard input",
    )
    validate.add_argument(
        "--schema",
        help="override the schema declared by schema_version",
    )
    validate.add_argument(
        "--extension-schema",
        action="append",
        default=[],
        metavar="URI=PATH",
        help="supply a digest-pinned domain extension schema; may be repeated",
    )
    validate.add_argument(
        "--quiet",
        action="store_true",
        help="produce no output when validation succeeds",
    )
    qualification = subparsers.add_parser(
        "validate-qualification",
        help="validate a complete qualification artifact set",
    )
    qualification.add_argument(
        "--artifact",
        action="append",
        required=True,
        metavar="KIND:SUBJECT=PATH",
        help="supply a qualification artifact; may be repeated",
    )
    qualification.add_argument(
        "--extension-schema",
        action="append",
        default=[],
        metavar="URI=PATH",
        help="supply a digest-pinned domain extension schema; may be repeated",
    )
    qualification.add_argument(
        "--quiet",
        action="store_true",
        help="produce no output when validation succeeds",
    )
    qualification.add_argument(
        "--output",
        metavar="PATH",
        help="write metadata for the exact validated artifact bytes as JSON",
    )
    return parser


def _read_document(path: str) -> Mapping[str, Any]:
    source = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    document = yaml.safe_load(source)
    if not isinstance(document, Mapping):
        raise ValueError("document root must be an object")
    return document


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


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    documents: list[tuple[str, str]] = []

    try:
        extension_schemas = _read_extension_schemas(arguments.extension_schema)
        if arguments.command == "validate":
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
                selected_schema = arguments.schema or document.get("schema_version")
                if not isinstance(selected_schema, str):
                    raise ValueError("document must declare schema_version")
                documents.append((path, resolve_schema_name(selected_schema)))
        elif arguments.command == "validate-qualification":
            result = validate_qualification_artifacts(
                arguments.artifact,
                extension_schemas,
            )
            if arguments.output:
                Path(arguments.output).write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
        else:
            raise AssertionError(f"unhandled command: {arguments.command}")
    except (
        OSError,
        ValueError,
        yaml.YAMLError,
    ) as error:
        print(f"invalid: {error}", file=sys.stderr)
        return 1

    if not arguments.quiet:
        if arguments.command == "validate-qualification":
            print("valid: qualification artifact set")
        elif len(documents) == 1:
            print(f"valid: {documents[0][1]}")
        else:
            for path, schema_name in documents:
                print(f"valid: {path}: {schema_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
