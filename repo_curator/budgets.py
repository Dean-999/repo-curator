"""Bounded resource settings for safe repository audits."""

from dataclasses import dataclass


DEFAULT_MAX_FILE_BYTES = 33_554_432
MAX_MAX_FILE_BYTES = 268_435_456
DEFAULT_MAX_ARTIFACTS = 100_000
MAX_MAX_ARTIFACTS = 1_000_000
DEFAULT_MAX_DEPTH = 128
MAX_MAX_DEPTH = 512
DEFAULT_MAX_DIRECTORY_ENTRIES = 50_000
MAX_MAX_DIRECTORY_ENTRIES = 100_000
DEFAULT_MAX_TOTAL_HASH_BYTES = 1_073_741_824
MAX_MAX_TOTAL_HASH_BYTES = 68_719_476_736


@dataclass(frozen=True)
class AuditBudgets:
    """Immutable audit limits, validated before filesystem observation begins."""

    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_artifacts: int = DEFAULT_MAX_ARTIFACTS
    max_depth: int = DEFAULT_MAX_DEPTH
    max_directory_entries: int = DEFAULT_MAX_DIRECTORY_ENTRIES
    max_total_hash_bytes: int = DEFAULT_MAX_TOTAL_HASH_BYTES

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self._require_range(
            "max file bytes", self.max_file_bytes, 1, MAX_MAX_FILE_BYTES
        )
        self._require_range(
            "max artifacts", self.max_artifacts, 1, MAX_MAX_ARTIFACTS
        )
        self._require_range("max depth", self.max_depth, 0, MAX_MAX_DEPTH)
        self._require_range(
            "max directory entries",
            self.max_directory_entries,
            1,
            MAX_MAX_DIRECTORY_ENTRIES,
        )
        self._require_range(
            "max total hash bytes",
            self.max_total_hash_bytes,
            0,
            MAX_MAX_TOTAL_HASH_BYTES,
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "max_artifacts": self.max_artifacts,
            "max_depth": self.max_depth,
            "max_directory_entries": self.max_directory_entries,
            "max_file_bytes": self.max_file_bytes,
            "max_total_hash_bytes": self.max_total_hash_bytes,
        }

    @staticmethod
    def _require_range(name: str, value: int, minimum: int, maximum: int) -> None:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not minimum <= value <= maximum
        ):
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
