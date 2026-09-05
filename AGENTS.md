# otr-replay agent guidance

Run commands from the repository root through `uv`; do not call `pip` or
`python` directly. First read `/home/stage/code/git/otr/AGENTS.md` and
`/home/stage/code/git/otr/.agents/WORKFLOW.md`. Python 3.14 is required. The app
and Docker tests need Docker.

The tool reproduces published ratings at a UTC `--as-of` time from the newest
eligible public replica and processor release. It writes a CSV and audit
`.metadata.json`. Never overwrite output. Record every replica, checksum,
release, image digest, and reconciliation counter. Treat every timestamp,
including an offset-less API value, as UTC.

## Commands

- `uv sync`; use `--frozen` in CI.
- `uv run otr-replay --as-of 2026-06-27T23:59` runs the application.
- `uv run pytest` runs unit tests.
- `OTR_REPLAY_DOCKER_TEST=1 uv run pytest tests/test_reconcile_docker.py` runs
  Docker reconciliation tests.
- `uv run black --check .` and `uv run ruff check .` check style. Preserve
  one-flag-per-line argument lists marked with `# fmt: skip`.

## Pipeline and invariants

- `discovery.py` selects the newest public replica and the newest stable
  `YYYY.MM.DD` processor release usable at the cutoff. Usable time is the later
  GitHub publication or Docker push time. Preserve retry and rate-limit failure.
- `sandbox.py` owns run-labeled Docker resources, streams imports, uses processor
  image digests, and removes only resources with its label. Teardown never hides
  the original error.
- `sql.py` reconciles in one fail-closed transaction. Roll back decay types `1`
  and `3` past the horizon; abort on other later adjustments or rating mismatch.
- `output.py` claims output paths atomically, writes CSV through `.part`, checks
  row count, and writes metadata last.
- `console.py` owns visible progress. `models.py` owns frozen dataclasses.
- Raise `ReplayError(phase, message, hint)` with an actionable hint. Exit `130`
  on interrupt, `3` on unexpected exception, and `1` for expected failure.
- Verify each replica SHA-256, run images by digest, redact database credentials,
  and keep unit tests offline with `tests/fixtures/`.
