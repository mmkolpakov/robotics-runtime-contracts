from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from robotics_runtime_contracts import (
    ContractValidationError,
    ExtensionValidationError,
    SemanticValidationError,
    UnknownSchemaError,
    validate_document,
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
    if arguments.command != "validate":
        raise AssertionError(f"unhandled command: {arguments.command}")

    try:
        extension_schemas = _read_extension_schemas(arguments.extension_schema)
        if arguments.schema is not None and len(arguments.documents) != 1:
            raise ValueError("--schema requires exactly one document")
        if arguments.documents.count("-") > 1:
            raise ValueError("standard input may be selected only once")
        documents = []
        for path in arguments.documents:
            document = _read_document(path)
            validate_document(
                document,
                schema=arguments.schema,
                extension_schemas=extension_schemas or None,
            )
            documents.append((path, document))
    except (
        ContractValidationError,
        ExtensionValidationError,
        SemanticValidationError,
        UnknownSchemaError,
        OSError,
        UnicodeError,
        ValueError,
        yaml.YAMLError,
    ) as error:
        print(f"invalid: {error}", file=sys.stderr)
        return 1

    if not arguments.quiet:
        if len(documents) == 1:
            print(f"valid: {documents[0][1]['schema_version']}")
        else:
            for path, document in documents:
                print(f"valid: {path}: {document['schema_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
