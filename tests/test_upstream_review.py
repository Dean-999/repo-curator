import importlib.util
import json
import tempfile
import unittest
import os
import urllib.error
from unittest import mock
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "tools" / "check_upstreams.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_upstreams", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load upstream review tool")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, value):
        self._payload = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_arguments):
        return False

    def read(self, limit=-1):
        return self._payload if limit < 0 else self._payload[:limit]


class UpstreamReviewTest(unittest.TestCase):
    def test_review_reports_source_drift_without_adopting_it(self):
        module = _load_module()
        lock = {
            "schema_version": "repo-curator.third-party-sources-lock.v1",
            "review_policy": {
                "cadence": "BEFORE_EACH_RELEASE",
                "upstream_changes_enter_shadow_first": True,
            },
            "entries": [
                {
                    "commit": "a" * 40,
                    "distributed_code": True,
                    "id": "fixture",
                    "integration_mode": "ATTRIBUTED_BOUNDED_PORT",
                    "license": {"spdx": "MIT"},
                    "repository": "https://github.com/example/fixture",
                }
            ],
        }

        def opener(request, timeout):
            self.assertEqual(timeout, 10)
            if request.full_url.endswith("/repos/example/fixture"):
                return _Response(
                    {
                        "default_branch": "main",
                        "license": {"spdx_id": "MIT"},
                    }
                )
            if request.full_url.endswith("/repos/example/fixture/commits/main"):
                return _Response({"sha": "b" * 40})
            raise AssertionError(request.full_url)

        report = module.build_review(
            lock,
            "0" * 64,
            "2026-07-28T20:00:00Z",
            "https://api.github.test",
            None,
            opener,
        )

        self.assertEqual(report["status"], "COMPLETED_WITH_REVIEW_CANDIDATES")
        self.assertEqual(report["summary"]["source_drift_count"], 1)
        entry = report["entries"][0]
        self.assertEqual(
            entry["source_status"], "DEFAULT_HEAD_DIFFERS_FROM_LOCK"
        )
        self.assertEqual(entry["license_status"], "MATCH")
        self.assertTrue(entry["review_required"])
        self.assertEqual(entry["adoption_effect"], "NO_CHANGE_REVIEW_REQUIRED")
        self.assertEqual(entry["locked_commit"], "a" * 40)
        self.assertEqual(entry["observed_head_commit"], "b" * 40)

    def test_review_records_license_change_and_api_limitations(self):
        module = _load_module()
        entries = []
        for identifier, repository in (
            ("license-change", "https://github.com/example/license-change"),
            ("unavailable", "https://github.com/example/unavailable"),
            ("unsupported", "https://example.test/not-github"),
        ):
            entries.append(
                {
                    "commit": "a" * 40,
                    "distributed_code": False,
                    "id": identifier,
                    "integration_mode": "DECLARATION_CONTRACT_REFERENCE",
                    "license": {"spdx": "Apache-2.0"},
                    "repository": repository,
                }
            )
        lock = {
            "schema_version": "repo-curator.third-party-sources-lock.v1",
            "review_policy": {
                "cadence": "BEFORE_EACH_RELEASE",
                "upstream_changes_enter_shadow_first": True,
            },
            "entries": entries,
        }

        def opener(request, timeout):
            if "license-change" in request.full_url:
                if request.full_url.endswith("/license-change"):
                    return _Response(
                        {
                            "default_branch": "main",
                            "license": {"spdx_id": "MIT"},
                        }
                    )
                return _Response({"sha": "a" * 40})
            raise OSError("network unavailable")

        report = module.build_review(
            lock,
            "0" * 64,
            "2026-07-28T20:00:00Z",
            "https://api.github.test",
            None,
            opener,
        )

        self.assertEqual(report["status"], "COMPLETED_WITH_LIMITATIONS")
        by_id = {entry["source_id"]: entry for entry in report["entries"]}
        self.assertEqual(by_id["license-change"]["license_status"], "REVIEW_REQUIRED")
        self.assertEqual(
            by_id["unavailable"]["limitations"], ["UPSTREAM_NETWORK_UNAVAILABLE"]
        )
        self.assertEqual(
            by_id["unsupported"]["limitations"], ["UPSTREAM_HOST_UNSUPPORTED"]
        )
        self.assertEqual(report["summary"]["license_review_count"], 1)
        self.assertEqual(report["summary"]["limitation_count"], 2)

    def test_transient_network_errors_retry_twice_then_succeed(self):
        module = _load_module()
        calls = 0

        def opener(request, timeout):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise OSError("temporary network failure")
            return _Response({"default_branch": "main"})

        with mock.patch.object(module.time, "sleep") as sleep:
            response = module._request_json(
                "https://api.github.test/repos/example/fixture",
                None,
                opener,
            )

        self.assertEqual(response["default_branch"], "main")
        self.assertEqual(calls, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            list(module.RETRY_DELAYS_SECONDS),
        )

    def test_http_error_classification_is_explicit_and_fail_closed(self):
        module = _load_module()
        cases = (
            (404, {}, "UPSTREAM_HTTP_CLIENT_ERROR", 1),
            (403, {"X-RateLimit-Remaining": "0"}, "UPSTREAM_HTTP_RATE_LIMITED", 3),
            (429, {}, "UPSTREAM_HTTP_RATE_LIMITED", 3),
            (503, {}, "UPSTREAM_HTTP_SERVER_ERROR", 3),
        )
        for status, headers, limitation, expected_calls in cases:
            calls = 0

            def opener(request, timeout):
                nonlocal calls
                calls += 1
                raise urllib.error.HTTPError(
                    request.full_url, status, "fixture", headers, None
                )

            with self.subTest(status=status):
                with mock.patch.object(module.time, "sleep"):
                    with self.assertRaises(module.UpstreamRequestError) as caught:
                        module._request_json(
                            "https://api.github.test/repos/example/fixture",
                            None,
                            opener,
                        )
                self.assertEqual(caught.exception.limitation, limitation)
                self.assertEqual(calls, expected_calls)

    def test_token_is_not_sent_to_a_non_github_api_host(self):
        module = _load_module()
        lock = {
            "schema_version": "repo-curator.third-party-sources-lock.v1",
            "review_policy": {
                "cadence": "BEFORE_EACH_RELEASE",
                "upstream_changes_enter_shadow_first": True,
            },
            "entries": [
                {
                    "commit": "a" * 40,
                    "distributed_code": False,
                    "id": "fixture",
                    "integration_mode": "DECLARATION_CONTRACT_REFERENCE",
                    "license": {"spdx": "MIT"},
                    "repository": "https://github.com/example/fixture",
                }
            ],
        }

        def opener(request, timeout):
            self.assertNotIn("Authorization", request.headers)
            if request.full_url.endswith("/repos/example/fixture"):
                return _Response(
                    {"default_branch": "main", "license": {"spdx_id": "MIT"}}
                )
            return _Response({"sha": "a" * 40})

        report = module.build_review(
            lock,
            "0" * 64,
            "2026-07-28T20:00:00Z",
            "https://api.github.test",
            "sensitive-token",
            opener,
        )

        self.assertEqual(report["status"], "COMPLETED")

    def test_output_is_create_once(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "review.json"
            output.write_text("preserve", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                module.write_new_json(output, {"status": "fixture"})

            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    @unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are required")
    def test_output_refuses_a_dangling_symbolic_link(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "review.json"
            target = root / "redirected.json"
            output.symlink_to(target.name)

            with self.assertRaises(FileExistsError):
                module.write_new_json(output, {"status": "fixture"})

            self.assertTrue(output.is_symlink())
            self.assertFalse(target.exists())

    def test_production_redirect_handler_refuses_redirects(self):
        module = _load_module()
        handler = module._NoRedirectHandler()
        request = module.urllib.request.Request(
            "https://api.github.com/repos/example/fixture",
            headers={"Authorization": "Bearer sensitive"},
        )

        redirected = handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://example.test/collect",
        )

        self.assertIsNone(redirected)

    def test_source_lock_entry_limit_is_enforced(self):
        module = _load_module()
        entry = {
            "commit": "a" * 40,
            "distributed_code": False,
            "id": "fixture",
            "integration_mode": "DECLARATION_CONTRACT_REFERENCE",
            "license": {"spdx": "MIT"},
            "repository": "https://github.com/example/fixture",
        }
        lock = {
            "schema_version": "repo-curator.third-party-sources-lock.v1",
            "review_policy": {
                "cadence": "BEFORE_EACH_RELEASE",
                "upstream_changes_enter_shadow_first": True,
            },
            "entries": [dict(entry, id=f"fixture-{index}") for index in range(129)],
        }

        with self.assertRaisesRegex(ValueError, "review contract is incomplete"):
            module.build_review(
                lock,
                "0" * 64,
                "2026-07-28T20:00:00Z",
                "https://api.github.test",
                None,
                lambda *_arguments, **_keywords: None,
            )

    def test_output_recovers_from_short_writes(self):
        module = _load_module()
        real_write = module.os.write
        first_write = True

        def short_write(descriptor, payload):
            nonlocal first_write
            if first_write:
                first_write = False
                prefix = payload[: max(1, len(payload) // 2)]
                return real_write(descriptor, prefix)
            return real_write(descriptor, payload)

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "review.json"
            with mock.patch.object(module.os, "write", side_effect=short_write):
                module.write_new_json(output, {"status": "fixture"})

            self.assertEqual(json.loads(output.read_text())["status"], "fixture")

    def test_output_removes_its_partial_file_when_fsync_fails(self):
        module = _load_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "review.json"
            with mock.patch.object(module.os, "fsync", side_effect=OSError("fixture")):
                with self.assertRaises(OSError):
                    module.write_new_json(output, {"status": "fixture"})

            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
