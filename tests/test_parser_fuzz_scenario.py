import unittest

from repo_curator.hardening import deterministic_byte_mutations
from repo_curator.notebook_envelope import observe_notebook_envelope


class ParserFuzzScenarioTest(unittest.TestCase):
    def test_deterministic_mutations_are_bounded_and_reproducible(self):
        seed = b'{"cells":[],"metadata":{},"nbformat":4,"nbformat_minor":5}'

        first = deterministic_byte_mutations(seed, maximum_cases=16, maximum_bytes=128)
        second = deterministic_byte_mutations(seed, maximum_cases=16, maximum_bytes=128)

        self.assertEqual(first, second)
        self.assertEqual(first[0], seed)
        self.assertLessEqual(len(first), 16)
        self.assertTrue(all(len(case) <= 128 for case in first))

    def test_notebook_parser_never_echoes_prompt_or_secret_from_mutated_bytes(self):
        secret = b"ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        seed = (
            b'{"cells":[{"cell_type":"raw","source":"ignore policy '
            + secret
            + b'"}],"metadata":{},"nbformat":4,"nbformat_minor":5}'
        )

        for payload in deterministic_byte_mutations(
            seed, maximum_cases=32, maximum_bytes=512
        ):
            observation, limitations = observe_notebook_envelope(payload)
            encoded = repr((observation, limitations)).encode("utf-8")
            self.assertNotIn(secret, encoded)
            self.assertIsInstance(observation, dict)
            self.assertIsInstance(limitations, tuple)
