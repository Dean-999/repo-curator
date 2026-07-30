"""Descriptor-relative filesystem observation for repository audits."""

import hashlib
import errno
import os
import stat
from dataclasses import dataclass, replace
from typing import Optional

from repo_curator.budgets import AuditBudgets
from repo_curator.identity import collision_key, content_identity, directory_merkle


CONTROL_DIRECTORY_NAME = ".repo-curator"


@dataclass(frozen=True)
class ObservedArtifact:
    path: str
    path_bytes: bytes
    object_type: str
    stat_result: Optional[os.stat_result]
    fingerprint_scheme: Optional[str]
    fingerprint: Optional[str]
    symlink_target_text: Optional[str]
    profile_eligibility: str
    warnings: tuple[str, ...]


@dataclass
class _ScanState:
    hashed_bytes: int = 0
    artifact_limit_reached: bool = False


def scan_root(root_fd: int, budgets: AuditBudgets = AuditBudgets()) -> list[ObservedArtifact]:
    """Inventory entries with *at APIs; never follow a symlink or read a special object."""
    root_stat = os.fstat(root_fd)
    artifacts = [
        ObservedArtifact(
            path=".",
            path_bytes=b".",
            object_type="DIRECTORY",
            stat_result=root_stat,
            fingerprint_scheme=None,
            fingerprint=None,
            symlink_target_text=None,
            profile_eligibility="NOT_APPLICABLE",
            warnings=(),
        )
    ]
    _scan_directory(root_fd, root_fd, ".", b".", 0, artifacts, budgets, _ScanState())
    return _apply_case_collision_warnings(_assign_directory_fingerprints(artifacts))


def _scan_directory(
    root_fd: int,
    directory_fd: int,
    relative_directory: str,
    relative_directory_bytes: bytes,
    depth: int,
    artifacts: list[ObservedArtifact],
    budgets: AuditBudgets,
    state: _ScanState,
) -> None:
    try:
        names = _bounded_directory_names(
            directory_fd,
            budgets.max_directory_entries,
            CONTROL_DIRECTORY_NAME if relative_directory == "." else None,
        )
    except OSError as error:
        if relative_directory == ".":
            raise
        _append_directory_warning(
            artifacts, relative_directory, _warning_for_error(error)
        )
        return
    if names is None:
        _append_directory_warning(artifacts, relative_directory, "DIRECTORY_ENTRY_LIMIT")
        return
    for name in names:
        if state.artifact_limit_reached:
            return
        name_bytes = os.fsencode(name)
        if relative_directory == "." and name_bytes == os.fsencode(CONTROL_DIRECTORY_NAME):
            continue
        relative_path = name if relative_directory == "." else f"{relative_directory}/{name}"
        relative_path_bytes = (
            name_bytes
            if relative_directory_bytes == b"."
            else relative_directory_bytes + b"/" + name_bytes
        )
        if len(artifacts) >= budgets.max_artifacts:
            _append_directory_warning(
                artifacts, relative_directory, "INVENTORY_ARTIFACT_LIMIT"
            )
            state.artifact_limit_reached = True
            return
        try:
            observed_stat = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError as error:
            artifacts.append(
                _limited_artifact(
                    relative_path,
                    relative_path_bytes,
                    "UNKNOWN",
                    None,
                    _warning_for_error(error),
                )
            )
            continue
        git_boundary_warning = _git_boundary_warning(relative_path, name_bytes)
        if git_boundary_warning is not None:
            try:
                artifacts.append(
                    _git_boundary_artifact(
                        directory_fd,
                        name,
                        relative_path,
                        relative_path_bytes,
                        observed_stat,
                        git_boundary_warning,
                    )
                )
            except OSError as error:
                artifacts.append(
                    _limited_artifact(
                        relative_path,
                        relative_path_bytes,
                        _object_type(observed_stat.st_mode),
                        observed_stat,
                        _warning_for_error(error),
                    )
                )
            continue
        object_type = _object_type(observed_stat.st_mode)

        if object_type == "SYMLINK":
            try:
                artifacts.append(
                    _symlink_artifact(
                        root_fd,
                        directory_fd,
                        name,
                        relative_path,
                        relative_path_bytes,
                        observed_stat,
                    )
                )
            except OSError as error:
                artifacts.append(
                    _limited_artifact(
                        relative_path,
                        relative_path_bytes,
                        object_type,
                        observed_stat,
                        _warning_for_error(error),
                    )
                )
            continue

        if object_type == "SPECIAL_FILE":
            artifacts.append(
                ObservedArtifact(
                    path=relative_path,
                    path_bytes=relative_path_bytes,
                    object_type=object_type,
                    stat_result=observed_stat,
                    fingerprint_scheme=None,
                    fingerprint=None,
                    symlink_target_text=None,
                    profile_eligibility="NOT_APPLICABLE",
                    warnings=("SPECIAL_FILE_NOT_READ",),
                )
            )
            continue

        if object_type == "DIRECTORY":
            try:
                child_fd = os.open(name, _directory_open_flags(), dir_fd=directory_fd)
            except OSError as error:
                artifacts.append(
                    _limited_artifact(
                        relative_path,
                        relative_path_bytes,
                        object_type,
                        observed_stat,
                        _warning_for_error(error),
                    )
                )
                continue
            try:
                opened_stat = os.fstat(child_fd)
                _require_same_object(relative_path, observed_stat, opened_stat)
                if depth + 1 >= budgets.max_depth:
                    _require_named_entry_identity(
                        directory_fd, name, relative_path, opened_stat
                    )
                    artifacts.append(
                        _limited_artifact(
                            relative_path,
                            relative_path_bytes,
                            object_type,
                            opened_stat,
                            "INVENTORY_DEPTH_LIMIT",
                        )
                    )
                    continue
                nested_git = _nested_git_boundary(
                    child_fd, relative_path, relative_path_bytes
                )
                if nested_git is not None:
                    _require_named_entry_identity(
                        directory_fd, name, relative_path, opened_stat
                    )
                    if len(artifacts) + 2 > budgets.max_artifacts:
                        artifacts.append(
                            _limited_artifact(
                                relative_path,
                                relative_path_bytes,
                                object_type,
                                opened_stat,
                                "INVENTORY_ARTIFACT_LIMIT",
                            )
                        )
                        state.artifact_limit_reached = True
                        return
                    artifacts.append(
                        ObservedArtifact(
                            path=relative_path,
                            path_bytes=relative_path_bytes,
                            object_type=object_type,
                            stat_result=opened_stat,
                            fingerprint_scheme=None,
                            fingerprint=None,
                            symlink_target_text=None,
                            profile_eligibility="NOT_APPLICABLE",
                            warnings=("NESTED_REPOSITORY_BOUNDARY",),
                        )
                    )
                    artifacts.append(nested_git)
                    continue
                if _is_python_virtual_environment(child_fd):
                    _require_named_entry_identity(
                        directory_fd, name, relative_path, opened_stat
                    )
                    artifacts.append(
                        ObservedArtifact(
                            path=relative_path,
                            path_bytes=relative_path_bytes,
                            object_type=object_type,
                            stat_result=opened_stat,
                            fingerprint_scheme=None,
                            fingerprint=None,
                            symlink_target_text=None,
                            profile_eligibility="NOT_APPLICABLE",
                            warnings=("PYTHON_VIRTUAL_ENVIRONMENT_BOUNDARY_NOT_RECURSED",),
                        )
                    )
                    continue
                artifacts.append(
                    ObservedArtifact(
                        path=relative_path,
                        path_bytes=relative_path_bytes,
                        object_type=object_type,
                        stat_result=opened_stat,
                        fingerprint_scheme=None,
                        fingerprint=None,
                        symlink_target_text=None,
                        profile_eligibility="NOT_APPLICABLE",
                        warnings=(),
                    )
                )
                _scan_directory(
                    root_fd,
                    child_fd,
                    relative_path,
                    relative_path_bytes,
                    depth + 1,
                    artifacts,
                    budgets,
                    state,
                )
                _require_named_entry_identity(
                    directory_fd, name, relative_path, opened_stat
                )
            except OSError as error:
                _replace_artifact_with_limitation(
                    artifacts,
                    relative_path,
                    _warning_for_error(error),
                    observed_stat,
                )
            except ValueError:
                _replace_artifact_with_limitation(
                    artifacts,
                    relative_path,
                    "ARTIFACT_CHANGED_DURING_INVENTORY",
                    observed_stat,
                )
            finally:
                os.close(child_fd)
            continue

        artifacts.append(
            _regular_file_artifact(
                directory_fd,
                name,
                relative_path,
                relative_path_bytes,
                observed_stat,
                budgets,
                state,
            )
        )


def _bounded_directory_names(
    directory_fd: int, maximum_entries: int, excluded_name: Optional[str]
) -> Optional[list[str]]:
    names: list[str] = []
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            if excluded_name is not None and os.fsencode(entry.name) == os.fsencode(excluded_name):
                continue
            names.append(entry.name)
            if len(names) > maximum_entries:
                return None
    return sorted(names, key=os.fsencode)


def _is_python_virtual_environment(directory_fd: int) -> bool:
    """Recognize only the standard local venv marker without reading its content."""
    try:
        marker_stat = os.stat("pyvenv.cfg", dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return stat.S_ISREG(marker_stat.st_mode)


def _regular_file_artifact(
    directory_fd: int,
    name: str,
    relative_path: str,
    relative_path_bytes: bytes,
    observed_stat: os.stat_result,
    budgets: AuditBudgets,
    state: _ScanState,
) -> ObservedArtifact:
    if observed_stat.st_size > budgets.max_file_bytes:
        return _limited_artifact(
            relative_path,
            relative_path_bytes,
            "REGULAR_FILE",
            observed_stat,
            "CONTENT_HASH_SKIPPED_SIZE_LIMIT",
        )
    if observed_stat.st_size > budgets.max_total_hash_bytes - state.hashed_bytes:
        return _limited_artifact(
            relative_path,
            relative_path_bytes,
            "REGULAR_FILE",
            observed_stat,
            "CONTENT_HASH_SKIPPED_TOTAL_BYTES_LIMIT",
        )
    try:
        file_fd = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
            dir_fd=directory_fd,
        )
    except OSError as error:
        return _limited_artifact(
            relative_path,
            relative_path_bytes,
            "REGULAR_FILE",
            observed_stat,
            _warning_for_error(error),
        )
    try:
        opened_stat = os.fstat(file_fd)
        _require_same_object(relative_path, observed_stat, opened_stat)
        if not stat.S_ISREG(opened_stat.st_mode):
            raise ValueError(f"artifact changed type during inventory: {relative_path}")
        if opened_stat.st_size > budgets.max_file_bytes:
            raise ValueError(f"artifact changed during inventory: {relative_path}")
        fingerprint = _hash_file_descriptor(file_fd, budgets.max_file_bytes)
        final_stat = os.fstat(file_fd)
        _require_unchanged_file(relative_path, opened_stat, final_stat)
        _require_named_entry_identity(
            directory_fd, name, relative_path, final_stat
        )
        state.hashed_bytes += final_stat.st_size
        return ObservedArtifact(
            path=relative_path,
            path_bytes=relative_path_bytes,
            object_type="REGULAR_FILE",
            stat_result=final_stat,
            fingerprint_scheme="sha256-file-v1",
            fingerprint=fingerprint,
            symlink_target_text=None,
            profile_eligibility="ELIGIBLE",
            warnings=(),
        )
    except OSError as error:
        return _limited_artifact(
            relative_path,
            relative_path_bytes,
            "REGULAR_FILE",
            observed_stat,
            _warning_for_error(error),
        )
    except ValueError:
        return _limited_artifact(
            relative_path,
            relative_path_bytes,
            "REGULAR_FILE",
            observed_stat,
            "ARTIFACT_CHANGED_DURING_INVENTORY",
        )
    finally:
        os.close(file_fd)


def _limited_artifact(
    path: str,
    path_bytes: bytes,
    object_type: str,
    stat_result: Optional[os.stat_result],
    warning: str,
) -> ObservedArtifact:
    return ObservedArtifact(
        path=path,
        path_bytes=path_bytes,
        object_type=object_type,
        stat_result=stat_result,
        fingerprint_scheme=None,
        fingerprint=None,
        symlink_target_text=None,
        profile_eligibility="NOT_APPLICABLE",
        warnings=(warning,),
    )


def _warning_for_error(error: OSError) -> str:
    if isinstance(error, FileNotFoundError):
        return "ARTIFACT_DISAPPEARED"
    if error.errno in {errno.ELOOP, errno.ENOTDIR, errno.ESTALE}:
        return "ARTIFACT_CHANGED_DURING_INVENTORY"
    return "ARTIFACT_UNREADABLE"


def _append_directory_warning(
    artifacts: list[ObservedArtifact], path: str, warning: str
) -> None:
    for index, artifact in enumerate(artifacts):
        if artifact.path == path:
            artifacts[index] = replace(
                artifact,
                fingerprint_scheme=None,
                fingerprint=None,
                profile_eligibility="NOT_APPLICABLE",
                warnings=tuple(sorted(set(artifact.warnings) | {warning})),
            )
            return


def _replace_artifact_with_limitation(
    artifacts: list[ObservedArtifact],
    path: str,
    warning: str,
    fallback_stat: Optional[os.stat_result],
) -> None:
    descendant_prefix = f"{path}/"
    artifacts[:] = [
        artifact
        for artifact in artifacts
        if not artifact.path.startswith(descendant_prefix)
    ]
    for index, artifact in enumerate(artifacts):
        if artifact.path == path:
            artifacts[index] = _limited_artifact(
                artifact.path,
                artifact.path_bytes,
                artifact.object_type,
                artifact.stat_result or fallback_stat,
                warning,
            )
            return
    path_bytes = path.encode("utf-8", errors="surrogateescape")
    artifacts.append(
        _limited_artifact(path, path_bytes, "DIRECTORY", fallback_stat, warning)
    )


def _symlink_artifact(
    root_fd: int,
    directory_fd: int,
    name: str,
    relative_path: str,
    relative_path_bytes: bytes,
    observed_stat: os.stat_result,
) -> ObservedArtifact:
    target_text = os.readlink(name, dir_fd=directory_fd)
    target_bytes = os.fsencode(target_text)
    return ObservedArtifact(
        path=relative_path,
        path_bytes=relative_path_bytes,
        object_type="SYMLINK",
        stat_result=observed_stat,
        fingerprint_scheme="sha256-symlink-target-v1",
        fingerprint=hashlib.sha256(target_bytes).hexdigest(),
        symlink_target_text=target_text,
        profile_eligibility="NOT_APPLICABLE",
        warnings=_symlink_warnings(root_fd, relative_path_bytes, target_bytes),
    )


def _symlink_warnings(
    root_fd: int, relative_path_bytes: bytes, target_bytes: bytes
) -> tuple[str, ...]:
    if target_bytes.startswith(b"/"):
        return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
    return _relative_target_warning(
        root_fd, _parent_path_bytes(relative_path_bytes), target_bytes
    )


def _relative_target_warning(
    root_fd: int, parent_path_bytes: bytes, target_bytes: bytes
) -> tuple[str, ...]:
    directory_fds = [root_fd]
    try:
        if parent_path_bytes != b".":
            for component in parent_path_bytes.split(b"/"):
                warning = _push_target_directory(directory_fds, component)
                if warning:
                    return warning
        target_components = [
            component
            for component in target_bytes.split(b"/")
            if component not in (b"", b".")
        ]
        for index, component in enumerate(target_components):
            if component == b"..":
                if len(directory_fds) == 1:
                    return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
                os.close(directory_fds.pop())
                continue
            current_fd = directory_fds[-1]
            try:
                observed = os.stat(
                    component, dir_fd=current_fd, follow_symlinks=False
                )
            except (FileNotFoundError, NotADirectoryError):
                return ("SYMLINK_TARGET_MISSING",)
            except OSError:
                return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
            if stat.S_ISLNK(observed.st_mode):
                return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
            if not stat.S_ISDIR(observed.st_mode):
                if index == len(target_components) - 1:
                    return ()
                return ("SYMLINK_TARGET_MISSING",)
            warning = _push_target_directory(directory_fds, component, observed)
            if warning:
                return warning
        return ()
    finally:
        while len(directory_fds) > 1:
            os.close(directory_fds.pop())


def _push_target_directory(
    directory_fds: list[int], component: bytes, observed: Optional[os.stat_result] = None
) -> tuple[str, ...]:
    current_fd = directory_fds[-1]
    if observed is None:
        try:
            observed = os.stat(component, dir_fd=current_fd, follow_symlinks=False)
        except (FileNotFoundError, NotADirectoryError):
            return ("SYMLINK_TARGET_MISSING",)
        except OSError:
            return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
    if stat.S_ISLNK(observed.st_mode):
        return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
    if not stat.S_ISDIR(observed.st_mode):
        return ("SYMLINK_TARGET_MISSING",)
    try:
        next_fd = os.open(component, _directory_open_flags(), dir_fd=current_fd)
    except OSError:
        return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
    opened = os.fstat(next_fd)
    if (observed.st_dev, observed.st_ino) != (opened.st_dev, opened.st_ino):
        os.close(next_fd)
        return ("SYMLINK_TARGET_OUTSIDE_ROOT",)
    directory_fds.append(next_fd)
    return ()


def _parent_path_bytes(relative_path_bytes: bytes) -> bytes:
    if relative_path_bytes == b"." or b"/" not in relative_path_bytes:
        return b"."
    return relative_path_bytes.rsplit(b"/", 1)[0]


def _nested_git_boundary(
    directory_fd: int, relative_path: str, relative_path_bytes: bytes
) -> Optional[ObservedArtifact]:
    try:
        observed_stat = os.stat(
            ".git", dir_fd=directory_fd, follow_symlinks=False
        )
    except OSError:
        return None
    nested_path = f"{relative_path}/.git"
    nested_path_bytes = relative_path_bytes + b"/.git"
    return _git_boundary_artifact(
        directory_fd,
        ".git",
        nested_path,
        nested_path_bytes,
        observed_stat,
        "NESTED_REPOSITORY_BOUNDARY",
    )


def _git_boundary_artifact(
    directory_fd: int,
    name: str,
    relative_path: str,
    relative_path_bytes: bytes,
    observed_stat: os.stat_result,
    warning: str,
) -> ObservedArtifact:
    object_type = _object_type(observed_stat.st_mode)
    symlink_target_text = (
        os.readlink(name, dir_fd=directory_fd)
        if object_type == "SYMLINK"
        else None
    )
    return ObservedArtifact(
        path=relative_path,
        path_bytes=relative_path_bytes,
        object_type=object_type,
        stat_result=observed_stat,
        fingerprint_scheme=None,
        fingerprint=None,
        symlink_target_text=symlink_target_text,
        profile_eligibility="NOT_APPLICABLE",
        warnings=(warning,),
    )


def _git_boundary_warning(relative_path: str, name_bytes: bytes) -> Optional[str]:
    if name_bytes != b".git":
        return None
    return (
        "PROTECTED_GIT_CONTROL"
        if relative_path == ".git"
        else "NESTED_REPOSITORY_BOUNDARY"
    )


def _object_type(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "DIRECTORY"
    if stat.S_ISREG(mode):
        return "REGULAR_FILE"
    if stat.S_ISLNK(mode):
        return "SYMLINK"
    return "SPECIAL_FILE"


def _assign_directory_fingerprints(
    artifacts: list[ObservedArtifact],
) -> list[ObservedArtifact]:
    result = list(artifacts)
    indexes = {artifact.path: index for index, artifact in enumerate(result)}
    directories = sorted(
        (artifact for artifact in result if artifact.object_type == "DIRECTORY"),
        key=lambda artifact: _location_depth(artifact.path),
        reverse=True,
    )
    for directory in directories:
        index = indexes[directory.path]
        current_directory = result[index]
        children = [
            artifact
            for artifact in result
            if _parent_location(artifact.path) == directory.path
        ]
        limited_children = [
            child for child in children if content_identity(child) is None
        ]
        if limited_children:
            propagated_warnings = {
                warning for child in limited_children for warning in child.warnings
            }
            result[index] = replace(
                current_directory,
                fingerprint_scheme=None,
                fingerprint=None,
                warnings=tuple(
                    sorted(set(current_directory.warnings) | propagated_warnings)
                ),
            )
            continue
        if current_directory.warnings:
            continue
        manifest = [
            {
                "content_id": content_identity(child),
                "executable": bool(child.stat_result and child.stat_result.st_mode & 0o111),
                "name": child.path_bytes.rsplit(b"/", 1)[-1].decode(
                    "utf-8", errors="surrogateescape"
                ),
                "object_type": child.object_type,
                "symlink_target_text": child.symlink_target_text,
            }
            for child in sorted(children, key=lambda artifact: artifact.path_bytes)
        ]
        result[index] = replace(
            current_directory,
            fingerprint_scheme="merkle-dir-v1",
            fingerprint=directory_merkle(manifest).split(":", 1)[1],
        )
    return result


def _apply_case_collision_warnings(
    artifacts: list[ObservedArtifact],
) -> list[ObservedArtifact]:
    collision_groups: dict[str, list[int]] = {}
    for index, artifact in enumerate(artifacts):
        collision_groups.setdefault(collision_key(artifact.path), []).append(index)
    result = list(artifacts)
    for indexes in collision_groups.values():
        if len(indexes) > 1:
            for index in indexes:
                artifact = result[index]
                if "CASE_COLLISION" not in artifact.warnings:
                    result[index] = replace(
                        artifact,
                        warnings=artifact.warnings + ("CASE_COLLISION",),
                    )
    return result


def _parent_location(location: str) -> Optional[str]:
    if location == ".":
        return None
    parent = location.rsplit("/", 1)[0] if "/" in location else "."
    return parent


def _location_depth(location: str) -> int:
    return 0 if location == "." else location.count("/") + 1


def _hash_file_descriptor(file_descriptor: int, maximum_bytes: int) -> str:
    digest = hashlib.sha256()
    bytes_read = 0
    while True:
        chunk = os.read(file_descriptor, min(1024 * 1024, maximum_bytes - bytes_read))
        if not chunk:
            return digest.hexdigest()
        bytes_read += len(chunk)
        digest.update(chunk)
        if bytes_read == maximum_bytes:
            return digest.hexdigest()


def _require_same_object(
    relative_path: str, observed: os.stat_result, opened: os.stat_result
) -> None:
    if (observed.st_dev, observed.st_ino) != (opened.st_dev, opened.st_ino):
        raise ValueError(f"artifact changed during inventory: {relative_path}")


def _require_named_entry_identity(
    directory_fd: int,
    name: str,
    relative_path: str,
    opened: os.stat_result,
) -> None:
    """Require that a directory entry still names the descriptor's object."""
    named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    _require_same_object(relative_path, named, opened)


def _require_unchanged_file(
    relative_path: str, before: os.stat_result, after: os.stat_result
) -> None:
    before_state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_state = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_state != after_state:
        raise ValueError(f"artifact changed during inventory: {relative_path}")


def _directory_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
