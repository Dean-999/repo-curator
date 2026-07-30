import unittest
from pathlib import Path


class EvaluationCiWorkflowTest(unittest.TestCase):
    def test_manual_workflow_verifies_and_retains_a_real_corpus_without_push_admission(self):
        workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "evaluate-corpus.yml").read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("repo_curator corpus-verify", workflow)
        self.assertIn("repo_curator evaluate", workflow)
        self.assertIn("actions/upload-artifact", workflow)
        self.assertIn('"$CORPUS_PATH"', workflow)
        self.assertIn("contents: read", workflow)


if __name__ == "__main__":
    unittest.main()
