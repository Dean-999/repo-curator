"""Bounded Python syntax observations without importing target modules."""

import ast
from typing import Any, Dict, Iterable, List

from repo_curator.profiles import _read_file


PYTHON_STRUCTURE_SCHEMA_VERSION = "repo-curator.python-structure.v1"
PYTHON_SOURCE_LIMIT = 256 * 1024
PYTHON_NODE_LIMIT = 20_000


def observe_python_structure(
    root_fd: int,
    inventory_records: Iterable[Dict[str, Any]],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    observations = []
    for record in inventory_records:
        path = record["repository_relative_path"]
        if record["object_type"] != "REGULAR_FILE" or not path.endswith(".py"):
            continue
        observations.append(
            _observe_file(
                root_fd,
                record,
                run_id,
                created_at,
                len(observations) + 1,
            )
        )
    return observations


def _observe_file(
    root_fd: int,
    record: Dict[str, Any],
    run_id: str,
    created_at: str,
    sequence: int,
) -> Dict[str, Any]:
    limitations: List[str] = []
    imports: List[str] = []
    definitions: List[Dict[str, str]] = []
    has_main_guard = False
    try:
        content, truncated = _read_file(
            root_fd, record["repository_relative_path"], PYTHON_SOURCE_LIMIT
        )
    except OSError:
        limitations.append("PYTHON_STRUCTURE_UNREADABLE")
    else:
        if truncated:
            limitations.append("PYTHON_STRUCTURE_SIZE_LIMIT")
        else:
            try:
                tree = ast.parse(content, filename="<repository-python-source>")
                nodes = []
                for node in ast.walk(tree):
                    nodes.append(node)
                    if len(nodes) > PYTHON_NODE_LIMIT:
                        raise _NodeLimitExceeded
                imports = _imports(nodes)
                definitions = _definitions(tree)
                has_main_guard = any(_is_main_guard(node) for node in tree.body)
                limitations.append("PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR")
            except _NodeLimitExceeded:
                limitations.append("PYTHON_STRUCTURE_NODE_LIMIT")
            except SyntaxError:
                limitations.append("PYTHON_SYNTAX_ERROR")
            except (TypeError, ValueError):
                limitations.append("PYTHON_SOURCE_MALFORMED")
            except MemoryError:
                limitations.append("PYTHON_STRUCTURE_MEMORY_LIMIT")
            except RecursionError:
                limitations.append("PYTHON_STRUCTURE_RECURSION_LIMIT")
    path = record["repository_relative_path"]
    return {
        "artifact_id": record["artifact_id"],
        "content_id": record["content_id"],
        "created_at": created_at,
        "definitions": definitions,
        "has_main_guard": has_main_guard,
        "imports": imports,
        "limitations": sorted(set(limitations)),
        "module_name": _module_name(path),
        "repository_relative_path": path,
        "run_id": run_id,
        "schema_version": PYTHON_STRUCTURE_SCHEMA_VERSION,
        "structure_id": f"pystruct_{run_id}_{sequence:08d}",
    }


class _NodeLimitExceeded(Exception):
    pass


def _imports(nodes: Iterable[ast.AST]) -> List[str]:
    names = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return sorted(names)


def _definitions(tree: ast.Module) -> List[Dict[str, str]]:
    definitions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.append({"kind": "FUNCTION", "name": node.name})
        elif isinstance(node, ast.ClassDef):
            definitions.append({"kind": "CLASS", "name": node.name})
    return sorted(definitions, key=lambda item: (item["kind"], item["name"]))


def _is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    comparison = node.test
    if len(comparison.ops) != 1 or not isinstance(comparison.ops[0], ast.Eq):
        return False
    if len(comparison.comparators) != 1:
        return False
    return (
        _is_name_dunder(comparison.left)
        and _is_main_literal(comparison.comparators[0])
    ) or (
        _is_main_literal(comparison.left)
        and _is_name_dunder(comparison.comparators[0])
    )


def _is_name_dunder(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id == "__name__"


def _is_main_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == "__main__"


def _module_name(path: str) -> str:
    components = path[:-3].split("/")
    if components[-1] == "__init__":
        components = components[:-1]
    return ".".join(components)
