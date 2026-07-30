"""Produce an advisory, create-once review of locked GitHub upstream sources."""

import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK_PATH = Path("third_party") / "sources.lock.yaml"
SCHEMA_VERSION = "repo-curator.upstream-review.v1"
RESPONSE_BYTE_LIMIT = 1024 * 1024
SOURCE_LOCK_BYTE_LIMIT = 1024 * 1024
SOURCE_ENTRY_LIMIT = 128
HTTP_TIMEOUT_SECONDS = 10
RETRY_DELAYS_SECONDS = (0.1, 0.3)
_GITHUB_COMPONENT = re.compile(r"[A-Za-z0-9_.-]+\Z")


class UpstreamRequestError(ValueError):
    """A stable, non-secret classification for one failed metadata request."""

    def __init__(self, limitation: str):
        super().__init__(limitation)
        self.limitation = limitation


def main(arguments: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="compare locked source metadata with current GitHub metadata"
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checked-at", default=_utc_now())
    parsed = parser.parse_args(arguments)
    try:
        checked_at = _validated_timestamp(parsed.checked_at)
        lock_bytes = _read_bounded_regular_file(
            REPOSITORY_ROOT / SOURCE_LOCK_PATH, SOURCE_LOCK_BYTE_LIMIT
        )
        lock = json.loads(lock_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
        if not isinstance(lock, dict):
            raise ValueError("source lock must be a JSON object")
        token = os.environ.get("GITHUB_TOKEN")
        report = build_review(
            lock,
            hashlib.sha256(lock_bytes).hexdigest(),
            checked_at,
            "https://api.github.com",
            token,
            urllib.request.build_opener(_NoRedirectHandler()).open,
        )
        write_new_json(parsed.output, report)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(f"repo-curator: upstream review failed: {error}", file=os.sys.stderr)
        return 2
    return 0


def build_review(
    lock: Dict[str, Any],
    source_lock_sha256: str,
    checked_at: str,
    api_base: str,
    token: Optional[str],
    opener: Callable[..., Any],
) -> Dict[str, Any]:
    entries = lock.get("entries")
    policy = lock.get("review_policy")
    if (
        lock.get("schema_version")
        != "repo-curator.third-party-sources-lock.v1"
        or not isinstance(entries, list)
        or not entries
        or len(entries) > SOURCE_ENTRY_LIMIT
        or not isinstance(policy, dict)
        or not isinstance(policy.get("cadence"), str)
        or not policy.get("cadence")
        or policy.get("upstream_changes_enter_shadow_first") is not True
        or re.fullmatch(r"[0-9a-f]{64}", source_lock_sha256) is None
    ):
        raise ValueError("source lock review contract is incomplete")
    _validated_timestamp(checked_at)
    for entry in entries:
        _validated_entry(entry)
    identifiers = [entry["id"] for entry in entries]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("source lock identifiers must be unique")
    results = [
        _review_entry(entry, api_base.rstrip("/"), token, opener)
        for entry in sorted(entries, key=lambda value: value["id"])
    ]
    source_drift_count = sum(
        result["source_status"] == "DEFAULT_HEAD_DIFFERS_FROM_LOCK"
        for result in results
    )
    license_review_count = sum(
        result["license_status"] == "REVIEW_REQUIRED" for result in results
    )
    limitation_count = sum(bool(result["limitations"]) for result in results)
    review_required_count = sum(bool(result["review_required"]) for result in results)
    status = (
        "COMPLETED_WITH_LIMITATIONS"
        if limitation_count
        else "COMPLETED_WITH_REVIEW_CANDIDATES"
        if review_required_count
        else "COMPLETED"
    )
    return {
        "checked_at": checked_at,
        "entries": results,
        "review_policy": {
            "adoption": "MANUAL_REVIEW_ONLY",
            "cadence": policy.get("cadence"),
            "upstream_changes_enter_shadow_first": policy.get(
                "upstream_changes_enter_shadow_first"
            ),
        },
        "schema_version": SCHEMA_VERSION,
        "source_lock_sha256": source_lock_sha256,
        "status": status,
        "summary": {
            "entry_count": len(results),
            "license_review_count": license_review_count,
            "limitation_count": limitation_count,
            "review_required_count": review_required_count,
            "source_drift_count": source_drift_count,
        },
    }


def _review_entry(
    entry: Dict[str, Any],
    api_base: str,
    token: Optional[str],
    opener: Callable[..., Any],
) -> Dict[str, Any]:
    locked_license = entry["license"].get("spdx")
    result = {
        "adoption_effect": "NO_CHANGE_REVIEW_REQUIRED",
        "distributed_code": entry["distributed_code"],
        "integration_mode": entry["integration_mode"],
        "license_status": "UNAVAILABLE",
        "limitations": [],
        "locked_commit": entry["commit"],
        "locked_license_spdx": locked_license,
        "observed_default_branch": None,
        "observed_head_commit": None,
        "observed_license_spdx": None,
        "repository": entry["repository"],
        "review_required": False,
        "source_id": entry["id"],
        "source_status": "UNAVAILABLE",
    }
    coordinates = _github_coordinates(entry["repository"])
    if coordinates is None:
        result["limitations"] = ["UPSTREAM_HOST_UNSUPPORTED"]
        return result
    owner, repository = coordinates
    try:
        metadata = _request_json(
            f"{api_base}/repos/{owner}/{repository}", token, opener
        )
        default_branch = metadata.get("default_branch")
        license_record = metadata.get("license")
        if not isinstance(default_branch, str) or not default_branch:
            raise ValueError("upstream default branch is unavailable")
        head = _request_json(
            f"{api_base}/repos/{owner}/{repository}/commits/"
            + urllib.parse.quote(default_branch, safe=""),
            token,
            opener,
        ).get("sha")
        if not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40}", head) is None:
            raise ValueError("upstream head commit is malformed")
    except UpstreamRequestError as error:
        result["limitations"] = [error.limitation]
        return result
    except (ValueError, json.JSONDecodeError):
        result["limitations"] = ["UPSTREAM_RESPONSE_INVALID"]
        return result
    observed_license = (
        license_record.get("spdx_id") if isinstance(license_record, dict) else None
    )
    result["observed_default_branch"] = default_branch
    result["observed_head_commit"] = head
    result["observed_license_spdx"] = observed_license
    result["source_status"] = (
        "LOCKED_COMMIT_IS_DEFAULT_HEAD"
        if head == entry["commit"]
        else "DEFAULT_HEAD_DIFFERS_FROM_LOCK"
    )
    if locked_license in {None, "", "NOASSERTION"}:
        result["license_status"] = "NOT_COMPARABLE"
    elif not isinstance(observed_license, str) or observed_license in {
        "",
        "NOASSERTION",
    }:
        result["license_status"] = "UNAVAILABLE"
        result["limitations"] = ["UPSTREAM_LICENSE_METADATA_UNAVAILABLE"]
    else:
        result["license_status"] = (
            "MATCH" if observed_license == locked_license else "REVIEW_REQUIRED"
        )
    result["review_required"] = (
        result["source_status"] == "DEFAULT_HEAD_DIFFERS_FROM_LOCK"
        or result["license_status"] == "REVIEW_REQUIRED"
    )
    result["adoption_effect"] = (
        "NO_CHANGE_REVIEW_REQUIRED"
        if result["review_required"] or result["limitations"]
        else "NO_CHANGE"
    )
    return result


def _request_json(
    url: str, token: Optional[str], opener: Callable[..., Any]
) -> Dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "repo-curator-upstream-review",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    parsed_url = urllib.parse.urlsplit(url)
    if (
        token
        and parsed_url.scheme == "https"
        and parsed_url.netloc.lower() == "api.github.com"
    ):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    payload = None
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        try:
            with opener(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                payload = response.read(RESPONSE_BYTE_LIMIT + 1)
            break
        except urllib.error.HTTPError as error:
            limitation, retryable = _http_error_classification(error)
            if not retryable or attempt >= len(RETRY_DELAYS_SECONDS):
                raise UpstreamRequestError(limitation) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            if attempt >= len(RETRY_DELAYS_SECONDS):
                raise UpstreamRequestError("UPSTREAM_NETWORK_UNAVAILABLE") from error
        time.sleep(RETRY_DELAYS_SECONDS[attempt])
    if payload is None:
        raise UpstreamRequestError("UPSTREAM_NETWORK_UNAVAILABLE")
    if len(payload) > RESPONSE_BYTE_LIMIT:
        raise UpstreamRequestError("UPSTREAM_RESPONSE_INVALID")
    try:
        value = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_unique_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise UpstreamRequestError("UPSTREAM_RESPONSE_INVALID") from error
    if not isinstance(value, dict):
        raise UpstreamRequestError("UPSTREAM_RESPONSE_INVALID")
    return value


def _http_error_classification(
    error: urllib.error.HTTPError,
) -> Tuple[str, bool]:
    status = error.code
    headers = error.headers or {}
    rate_limited = status == 429 or (
        status == 403
        and (
            headers.get("Retry-After") is not None
            or headers.get("X-RateLimit-Remaining") == "0"
        )
    )
    if rate_limited:
        return "UPSTREAM_HTTP_RATE_LIMITED", True
    if status in {408, 500, 502, 503, 504}:
        return "UPSTREAM_HTTP_SERVER_ERROR", True
    return "UPSTREAM_HTTP_CLIENT_ERROR", False


def _github_coordinates(repository_url: Any) -> Optional[Tuple[str, str]]:
    if not isinstance(repository_url, str):
        return None
    parsed = urllib.parse.urlsplit(repository_url)
    parts = [part for part in parsed.path.split("/") if part]
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() != "github.com"
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
    ):
        return None
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository or any(
        _GITHUB_COMPONENT.fullmatch(component) is None
        for component in (owner, repository)
    ):
        return None
    return owner, repository


def _validated_entry(entry: Any) -> None:
    required = {
        "commit",
        "distributed_code",
        "id",
        "integration_mode",
        "license",
        "repository",
    }
    if (
        not isinstance(entry, dict)
        or not required.issubset(entry)
        or not isinstance(entry["id"], str)
        or not entry["id"]
        or not isinstance(entry["commit"], str)
        or re.fullmatch(r"[0-9a-f]{40}", entry["commit"]) is None
        or not isinstance(entry["distributed_code"], bool)
        or not isinstance(entry["integration_mode"], str)
        or not isinstance(entry["license"], dict)
        or not isinstance(entry["license"].get("spdx"), str)
        or not isinstance(entry["repository"], str)
    ):
        raise ValueError("source lock entry is incomplete")


def write_new_json(path: Path, value: Dict[str, Any]) -> None:
    path = path.absolute()
    try:
        parent = path.parent.resolve(strict=True)
    except OSError as error:
        raise ValueError("upstream review output parent is not a directory") from error
    if not parent.is_dir() or not path.name:
        raise ValueError("upstream review output parent is not a directory")
    payload = (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")
    parent_descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    descriptor = None
    created_identity = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_descriptor)
        created = os.fstat(descriptor)
        created_identity = (created.st_dev, created.st_ino)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.fsync(parent_descriptor)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        _remove_created_partial(parent_descriptor, path.name, created_identity)
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("upstream review receipt write made no progress")
        offset += written


def _remove_created_partial(
    parent_descriptor: int,
    name: str,
    created_identity: Optional[Tuple[int, int]],
) -> None:
    if created_identity is None:
        return
    try:
        current = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != created_identity:
            return
        os.unlink(name, dir_fd=parent_descriptor)
        os.fsync(parent_descriptor)
    except OSError:
        pass


def _read_bounded_regular_file(path: Path, limit: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise ValueError("source lock is not a bounded regular file")
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    if len(payload) > limit:
        raise ValueError("source lock exceeds byte limit")
    return payload


def _validated_timestamp(value: str) -> str:
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("checked-at must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("checked-at must include a timezone")
    return value


def _utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
