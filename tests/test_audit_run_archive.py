import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from tools.audit_run_archive import (
    AuditRunArchiveError,
    build_archive,
    verify_archive,
)


class AuditRunArchiveTest(unittest.TestCase):
    def test_build_is_deterministic_and_restore_verifies_every_member(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = self._corpus(root)
            first = root / "first.tar.gz"
            second = root / "second.tar.gz"
            first_manifest = root / "first.json"
            second_manifest = root / "second.json"
            arguments = {
                "corpus_root": corpus,
                "source_git_commit": "a" * 40,
                "release_tag": "corpus-pilot-v1",
                "asset_name": "pilot-audit-runs-v1.tar.gz",
                "repository": "example/repo-curator",
            }

            build_archive(
                **arguments,
                output_archive=first,
                output_manifest=first_manifest,
            )
            build_archive(
                **arguments,
                output_archive=second,
                output_manifest=second_manifest,
            )

            self.assertEqual(first.read_bytes(), second.read_bytes())
            restore = root / "restore"
            result = verify_archive(first, first_manifest, restore)
            self.assertEqual(result["status"], "VERIFIED")
            self.assertTrue(result["restored"])
            restored = (
                restore
                / "artifacts"
                / "audit-runs"
                / "repo-a"
                / "run-a"
                / "inventory.jsonl"
            )
            self.assertEqual(restored.read_text(encoding="utf-8"), '{"fixture":1}\n')

    def test_build_rejects_symlink_member_and_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = self._corpus(root)
            audit_root = corpus / "artifacts" / "audit-runs"
            (audit_root / "link").symlink_to(audit_root / "repo-a")
            output = root / "archive.tar.gz"
            manifest = root / "manifest.json"

            with self.assertRaisesRegex(AuditRunArchiveError, "symbolic link"):
                build_archive(
                    corpus_root=corpus,
                    source_git_commit="a" * 40,
                    release_tag="corpus-pilot-v1",
                    asset_name="pilot-audit-runs-v1.tar.gz",
                    repository="example/repo-curator",
                    output_archive=output,
                    output_manifest=manifest,
                )

            (audit_root / "link").unlink()
            output.write_bytes(b"preserve")
            with self.assertRaisesRegex(AuditRunArchiveError, "already exists"):
                build_archive(
                    corpus_root=corpus,
                    source_git_commit="a" * 40,
                    release_tag="corpus-pilot-v1",
                    asset_name="pilot-audit-runs-v1.tar.gz",
                    repository="example/repo-curator",
                    output_archive=output,
                    output_manifest=manifest,
                )
            self.assertEqual(output.read_bytes(), b"preserve")

    def test_verify_rejects_tampering_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = self._corpus(root)
            archive = root / "archive.tar.gz"
            manifest = root / "manifest.json"
            build_archive(
                corpus_root=corpus,
                source_git_commit="a" * 40,
                release_tag="corpus-pilot-v1",
                asset_name="pilot-audit-runs-v1.tar.gz",
                repository="example/repo-curator",
                output_archive=archive,
                output_manifest=manifest,
            )
            archive.write_bytes(archive.read_bytes() + b"tampered")
            with self.assertRaisesRegex(AuditRunArchiveError, "SHA-256"):
                verify_archive(archive, manifest)

            unsafe = root / "unsafe.tar.gz"
            with tarfile.open(unsafe, "w:gz") as output:
                info = tarfile.TarInfo("../../escape")
                info.size = 1
                output.addfile(info, io.BytesIO(b"x"))
            record = json.loads(manifest.read_text(encoding="utf-8"))
            import hashlib

            record["archive"]["sha256"] = (
                "sha256:" + hashlib.sha256(unsafe.read_bytes()).hexdigest()
            )
            record["archive"]["member_count"] = 1
            record["members"] = [
                {
                    "path": "../../escape",
                    "sha256": hashlib.sha256(b"x").hexdigest(),
                    "size_bytes": 1,
                }
            ]
            unsafe_manifest = root / "unsafe.json"
            unsafe_manifest.write_text(json.dumps(record), encoding="utf-8")
            with self.assertRaisesRegex(AuditRunArchiveError, "restore root"):
                verify_archive(unsafe, unsafe_manifest)

    @staticmethod
    def _corpus(root: Path) -> Path:
        corpus = root / "pilot"
        run = corpus / "artifacts" / "audit-runs" / "repo-a" / "run-a"
        run.mkdir(parents=True)
        inventory = run / "inventory.jsonl"
        inventory.write_text('{"fixture":1}\n', encoding="utf-8")
        import hashlib

        run_record = run / "run.json"
        run_record.write_text('{"status":"FINALIZED"}\n', encoding="utf-8")
        registry = {
            "schema_version": "repo-curator.pilot-audit-run-registry.v1",
            "audit_runs": [
                {
                    "repository_id": "repo-a",
                    "run_id": "run-a",
                    "run_path": "artifacts/audit-runs/repo-a/run-a/run.json",
                    "run_sha256": "sha256:"
                    + hashlib.sha256(run_record.read_bytes()).hexdigest(),
                    "snapshot_descriptor_sha256": "sha256:" + "b" * 64,
                }
            ],
        }
        snapshots = {
            "schema_version": "repo-curator.pilot-snapshot-registry.v1",
            "repositories": [
                {
                    "access": "public-mit",
                    "commit_sha": "c" * 40,
                    "repository_id": "repo-a",
                    "source_url": "https://example.test/repo-a",
                }
            ],
        }
        (corpus / "audit-run-registry.json").write_text(
            json.dumps(registry), encoding="utf-8"
        )
        (corpus / "snapshot-registry.json").write_text(
            json.dumps(snapshots), encoding="utf-8"
        )
        return corpus


if __name__ == "__main__":
    unittest.main()
