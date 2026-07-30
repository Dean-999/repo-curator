import hashlib
import json
import unittest

from repo_curator.approval import validate_approval


class ApprovalScenarioTest(unittest.TestCase):
    def test_valid_approval_binds_exact_plan_and_complete_context(self):
        plan_bytes, approval, context = self._fixture()

        result = validate_approval(plan_bytes, approval, context)

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["approved_action_ids"], ["action-1"])

    def test_any_plan_byte_or_bound_context_change_invalidates_approval(self):
        plan_bytes, approval, context = self._fixture()
        changed_plan = plan_bytes.replace(b"archive/", b"archive-x/")

        result = validate_approval(changed_plan, approval, context)
        self.assertFalse(result["valid"])
        self.assertIn("APPROVAL_PLAN_HASH_MISMATCH", result["errors"])

        for key, value, code in (
            ("repository_state_hash", "sha256:changed", "DRIFT_REPOSITORY_STATE"),
            ("effective_policy_hash", "sha256:changed", "APPROVAL_POLICY_HASH_MISMATCH"),
            ("decision_set_hash", "sha256:changed", "APPROVAL_DECISION_SET_HASH_MISMATCH"),
        ):
            modified = dict(context)
            modified[key] = value
            result = validate_approval(plan_bytes, approval, modified)
            self.assertFalse(result["valid"])
            self.assertIn(code, result["errors"])

        modified_approval = dict(approval)
        modified_approval["repository_state_hash"] = "sha256:other"
        result = validate_approval(plan_bytes, modified_approval, context)
        self.assertFalse(result["valid"])
        self.assertIn("DRIFT_REPOSITORY_STATE", result["errors"])

    def test_approval_cannot_expand_actions_destinations_or_recommendations(self):
        plan_bytes, approval, context = self._fixture()
        for field, value, code in (
            ("approved_action_ids", ["action-1", "action-other"], "APPROVAL_UNKNOWN_ACTION"),
            ("approved_recommendation_ids", ["recommendation-1", "other"], "APPROVAL_UNKNOWN_RECOMMENDATION"),
            ("destinations", ["archive/alternate.txt"], "APPROVAL_SCOPE_EXPANSION"),
            ("destination_path", "archive/alternate.txt", "APPROVAL_SCOPE_EXPANSION"),
        ):
            modified = dict(approval)
            modified[field] = value
            result = validate_approval(plan_bytes, modified, context)
            self.assertFalse(result["valid"])
            self.assertIn(code, result["errors"])

    def test_prevalidation_rejects_unsafe_action_conditions_before_mutation(self):
        plan_bytes, approval, context = self._fixture()
        cases = (
            ({"source_path": "../outside"}, "PATH_TRAVERSAL"),
            ({"source_external_symlink": True}, "PATH_EXTERNAL_SYMLINK"),
            ({"source_path": ".git/config"}, "PATH_PROTECTED"),
            ({"destination_exists": True}, "PATH_DESTINATION_EXISTS"),
            ({"case_collision": True}, "PATH_CASE_COLLISION"),
            ({"same_filesystem": False}, "CROSS_FILESYSTEM_MOVE_UNSUPPORTED"),
            ({"retention_closure_satisfied": False}, "RETENTION_CLOSURE_INCOMPLETE"),
            ({"type": "DELETE"}, "ACTION_UNSUPPORTED_TYPE"),
            ({"repository_mode": "FILESYSTEM"}, "PREFLIGHT_REPOSITORY_MODE"),
        )
        for changes, code in cases:
            with self.subTest(code=code):
                changed_plan = self._plan_bytes(action_changes=changes)
                changed_approval = self._approval(changed_plan)
                result = validate_approval(changed_plan, changed_approval, context)
                self.assertFalse(result["valid"])
                self.assertIn(code, result["errors"])

    def test_budget_and_bundle_constraints_fail_closed(self):
        plan_bytes, approval, context = self._fixture()
        for changes, code in (
            ({"affected_bytes": 101}, "BUDGET_AFFECTED_BYTES"),
            ({"bundle_complete": False}, "BUNDLE_INCOMPLETE"),
            ({"bundle_member_artifact_ids": ["art-a", "art-b"]}, "BUNDLE_PARTIAL_MOVEMENT"),
        ):
            with self.subTest(code=code):
                changed_plan = self._plan_bytes(action_changes=changes)
                changed_approval = self._approval(changed_plan)
                result = validate_approval(changed_plan, changed_approval, context)
                self.assertFalse(result["valid"])
                self.assertIn(code, result["errors"])

    def test_approval_budget_cannot_exceed_the_reviewed_plan_ceiling(self):
        plan_bytes, approval, context = self._fixture()
        approval["mutation_budget"] = {"max_actions": 2, "max_affected_bytes": 101, "max_blast_radius": 2}

        result = validate_approval(plan_bytes, approval, context)

        self.assertFalse(result["valid"])
        self.assertIn("APPROVAL_BUDGET_EXPANSION", result["errors"])

    def test_malformed_action_or_budget_returns_a_stable_rejection(self):
        plan_bytes, approval, context = self._fixture()
        malformed_plan = self._plan_bytes(action_changes={"affected_bytes": "100"})

        result = validate_approval(malformed_plan, self._approval(malformed_plan), context)
        self.assertFalse(result["valid"])
        self.assertIn("ACTION_MALFORMED", result["errors"])

        approval["mutation_budget"] = {"max_actions": True}
        result = validate_approval(plan_bytes, approval, context)
        self.assertFalse(result["valid"])
        self.assertIn("APPROVAL_BUDGET_MALFORMED", result["errors"])

        plan = json.loads(plan_bytes)
        plan["mutation_budget"]["unexpected"] = 1
        extra_budget_plan = json.dumps(plan, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        result = validate_approval(extra_budget_plan, self._approval(extra_budget_plan), context)
        self.assertFalse(result["valid"])
        self.assertIn("PLAN_BUDGET_MALFORMED", result["errors"])

    def test_validator_does_not_advertise_unimplemented_mutation_capabilities(self):
        plan_bytes = self._plan_bytes(action_changes={"type": "MOVE"})

        result = validate_approval(plan_bytes, self._approval(plan_bytes), self._context())

        self.assertFalse(result["valid"])
        self.assertIn("ACTION_UNSUPPORTED_TYPE", result["errors"])

    def _fixture(self):
        plan_bytes = self._plan_bytes()
        return plan_bytes, self._approval(plan_bytes), self._context()

    def _plan_bytes(self, action_changes=None):
        action = {
            "action_id": "action-1", "affected_artifact_ids": ["art-a"],
            "affected_bytes": 100, "approval_required": True, "bundle_complete": True,
            "bundle_member_artifact_ids": ["art-a"], "case_collision": False,
            "destination_exists": False, "destination_path": "archive/repo-curator/plan-1/output.txt",
            "executable_in_supported_scope": True, "repository_mode": "GIT_WORKTREE",
            "same_filesystem": True, "source_external_symlink": False,
            "retention_closure_satisfied": True, "retention_evidence_ids": ["retention-1"],
            "source_path": "output.txt", "type": "ARCHIVE",
        }
        action.update(action_changes or {})
        return json.dumps({
            "action_candidates": [action], "decision_set_hash": "sha256:decisions",
            "effective_policy_hash": "sha256:policy", "plan_id": "plan-1",
            "mutation_budget": {"max_actions": 1, "max_affected_bytes": 100, "max_blast_radius": 1},
            "recommendation_ids": ["recommendation-1"],
            "repository_state_hash": "sha256:state", "schema_version": "repo-curator.plan.v1",
        }, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")

    def _approval(self, plan_bytes):
        return {
            "approval_id": "approval-1", "approval_schema_version": "repo-curator.approval.v1",
            "approved_action_ids": ["action-1"], "approved_plan_id": "plan-1",
            "approved_plan_sha256": "sha256:" + hashlib.sha256(plan_bytes).hexdigest(),
            "approved_recommendation_ids": ["recommendation-1"],
            "approving_actor": "reviewer", "approval_created_at": "2026-07-24T00:00:00Z",
            "decision_set_hash": "sha256:decisions", "effective_policy_hash": "sha256:policy",
            "repository_state_hash": "sha256:state",
            "mutation_budget": {"max_actions": 1, "max_affected_bytes": 100, "max_blast_radius": 1},
        }

    def _context(self):
        return {
            "decision_set_hash": "sha256:decisions", "effective_policy_hash": "sha256:policy",
            "repository_state_hash": "sha256:state",
        }


if __name__ == "__main__":
    unittest.main()
