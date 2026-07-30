# Use locked, committed, hash-chained mutation transactions

Archive, quarantine, and rollback use one repository-scoped exclusive lock and
one strict `repo-curator.apply-journal.v2` event format. Every event binds the
exact plan and approval hashes, includes the previous event hash, and is
validated as a contiguous sequence. A successful apply ends with
`TRANSACTION_COMMITTED`; uncommitted or malformed journals require recovery.

Namespace operations follow an explicit durability order: write and fsync the
intent journal, create the destination and fsync its directory, create and
fsync provenance and its directory, remove the source and fsync its directory,
then append and fsync the verified and commit events. Rollback requires the
original plan bytes and approval, preserves provenance in a durable receipt,
and journals per-action boundaries.

This borrows transaction, lock, and commit-marker ideas from
[BorgBackup](https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html).
The local journal is described as append-written, not append-only: `O_APPEND`
is not an authority boundary. A stronger append-only claim would require a
separately authorized service or detached receipt, following the credential
separation documented by
[restic](https://restic.readthedocs.io/en/latest/060_forget.html#security-considerations-in-append-only-mode).
