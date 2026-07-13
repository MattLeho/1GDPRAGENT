# Task 3 synthetic acceptance corpus

This directory contains small, invented records used only for deterministic
Task 3 acceptance tests.  No fixture contains real personal data.

`corpus.json` is the scenario manifest.  Files under `snapshots/`, `duplicates/`,
and `file_truth/` are byte-level inputs used to prove snapshot, hashing,
canonicalisation, malformed-input, and file-type-truth behaviour.  Archive
fixtures are described in the manifest and assembled in a temporary directory
by the test so that repository fixtures remain compact and reviewable.
