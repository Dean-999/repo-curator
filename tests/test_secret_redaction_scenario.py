import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class SecretRedactionScenarioTest(unittest.TestCase):
    def test_shared_classifier_redacts_provider_and_labeled_secret_categories(self):
        from repo_curator.secret_redaction import redact_text

        values = [
            "AKIA234567ABCDEF2345",
            "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            (
                "eyJhbGciOiJIUzI1NiJ9."
                "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
                "abcdefghijklmnopqrstuvwxyz012345"
            ),
            (
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                "AAAA\n"
                "-----END OPENSSH PRIVATE KEY-----"
            ),
            "correct-horse-battery-staple",
            "sk-abcdefghijklmnop",
        ]
        redacted, categories = redact_text(
            "\n".join(values[:4])
            + "\npassword="
            + values[4]
            + "\n"
            + values[5]
        )

        self.assertEqual(
            categories,
            [
                "AWS_ACCESS_KEY",
                "GITHUB_TOKEN",
                "HIGH_CONFIDENCE_TOKEN",
                "JWT",
                "PASSWORD",
                "PRIVATE_KEY",
            ],
        )
        for value in values:
            self.assertNotIn(value, redacted)

    def test_history_classifier_returns_categories_only(self):
        from repo_curator.secret_redaction import detect_secret_categories

        categories, limitations = detect_secret_categories(
            b"gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\n"
        )

        self.assertEqual(categories, ["GITHUB_TOKEN"])
        self.assertEqual(limitations, [])

    def test_history_classifier_rejects_non_text_blobs(self):
        from repo_curator.secret_redaction import detect_secret_categories

        expected = ([], ["GIT_SECRET_HISTORY_NON_TEXT_BLOB"])
        self.assertEqual(detect_secret_categories(b"text\x00data"), expected)
        self.assertEqual(detect_secret_categories(b"\xff\xfe"), expected)

    def test_uri_userinfo_credentials_are_redacted(self):
        from repo_curator.secret_redaction import redact_text

        value = "https://fixture-user:fixture-password@example.test/data.csv"
        redacted, categories = redact_text(value)

        self.assertEqual(categories, ["URI_CREDENTIAL"])
        self.assertEqual(
            redacted,
            "https://[REDACTED:URI_CREDENTIAL]@example.test/data.csv",
        )

    def test_high_confidence_provider_secrets_are_redacted_before_persistence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            values = {
                "AWS_ACCESS_KEY": "AKIA234567ABCDEF2345",
                "GITHUB_TOKEN": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                "JWT": (
                    "eyJhbGciOiJIUzI1NiJ9."
                    "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
                    "abcdefghijklmnopqrstuvwxyz012345"
                ),
                "PRIVATE_KEY": (
                    "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
                    "-----END OPENSSH PRIVATE KEY-----"
                ),
            }
            (repository / "provider-secrets.txt").write_text(
                "\n".join(values.values()) + "\nghp_short is ordinary text\n",
                encoding="utf-8",
            )
            boundary_secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            (repository / "boundary-secret.txt").write_text(
                "x" * 500 + boundary_secret + "\n", encoding="utf-8"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "repo_curator",
                    "audit",
                    "--root",
                    str(repository),
                    "--run-id",
                    "secret-redaction-run",
                    "--created-at",
                    "2026-07-28T00:00:00Z",
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            profile_bytes = (
                repository
                / ".repo-curator"
                / "runs"
                / "secret-redaction-run"
                / "profiles.jsonl"
            ).read_bytes()
            profile = next(
                item
                for item in (
                    json.loads(line) for line in profile_bytes.decode("utf-8").splitlines()
                )
                if item["repository_relative_path"] == "provider-secrets.txt"
            )

            self.assertEqual(profile["redactions"], sorted(values))
            for secret in values.values():
                self.assertNotIn(secret.encode("utf-8"), profile_bytes)
            self.assertIn("ghp_short is ordinary text", profile["sample"])
            boundary_profile = next(
                item
                for item in (
                    json.loads(line) for line in profile_bytes.decode("utf-8").splitlines()
                )
                if item["repository_relative_path"] == "boundary-secret.txt"
            )
            self.assertIn("[REDACTED:GITHUB_TOKEN]", boundary_profile["sample"])
            self.assertNotIn("ghp_ABCDEFG", boundary_profile["sample"])


if __name__ == "__main__":
    unittest.main()
