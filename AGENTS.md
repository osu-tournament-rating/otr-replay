# otr-replay agent guidance

Run commands from the repository root through `uv`; never call `pip` or
`python` directly. Needs Python 3.14 and, for the app and Docker tests, a
running Docker daemon.

- Reproduces published o!TR ratings for a UTC `--as-of` time: downloads the
  newest public replica at or before it, imports it into a throwaway PostgreSQL
  container, runs the newest `otr-processor` release usable at that time,
  reconciles decay back to the replica timestamp, and writes a CSV plus an
  audit `.metadata.json`.
- Outputs are never overwritten. Every input (replica, checksum, release, image
  digests, counters) is recorded in the metadata.
- All timestamps are UTC everywhere. Offset-less API timestamps are UTC, never
  host-local.

## Commands

- `uv sync` (`--frozen` in CI); `uv run otr-replay --as-of 2026-06-27T23:59`.
- `uv run pytest`; Docker tests auto-skip unless
  `OTR_REPLAY_DOCKER_TEST=1 uv run pytest tests/test_reconcile_docker.py`.
- `uv run black --check .` and `uv run ruff check .` (line length 100, ruff
  `E,F,I,B,UP,SIM`). `# fmt: skip` keeps one-flag-per-line argv lists.

## Layout

`cli.main` parses `--as-of` and hands off to `run.execute`, a linear pipeline:

- `discovery.py` scrapes replicas from `data.otr.stagec.net`
  (`otr-public-replica_<ISO8601>.gz`) and picks the newest stable `YYYY.MM.DD`
  processor release usable at the cutoff, where usable-at is
  `max(github published_at, docker tag pushed_at)`. `_get` retries transient
  failures and raises on exhausted rate limits.
- `sandbox.py` drives Docker via `subprocess`: run-labeled network, volume, and
  PostgreSQL container; streams the dump into `docker exec psql`; runs the
  processor by image digest. Teardown removes by label and never raises.
- `sql.py` is the fail-closed reconciliation transaction: decay adjustments
  (types 1 and 3) past the replica timestamp are rolled back; any other
  adjustment past the horizon or rating/adjustment mismatch aborts. Counters
  are `OTR_REPLAY_*=N` lines on stdout.
- `output.py` claims paths with `touch(exist_ok=False)`, writes the CSV to a
  `.part` file, cross-checks the row count, then writes metadata last.
- `console.py` owns all user-visible progress via `Ui`. `models.py` holds the
  frozen dataclasses and `ReplayError`.

## Conventions

- Raise `ReplayError(phase, message, hint)` with an actionable hint; `cli.main`
  maps it to exit 1 (130 on interrupt, 3 on unexpected exceptions).
- Verify the replica SHA-256 against its published checksum; run images by
  digest, not tag.
- `sandbox.redact` scrubs database credentials from errors and logs.
- Unit tests use `tests/fixtures/` and never touch the network.
