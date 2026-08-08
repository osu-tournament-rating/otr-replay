# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`otr-replay` reproduces published o!TR player ratings for a point in time. Given a UTC
`--as-of` timestamp, it downloads the newest public database replica at or before that
time, imports it into a throwaway PostgreSQL container, runs the newest `otr-processor`
release available at that time, reconciles decay back to the replica timestamp, and
writes a CSV plus an audit `.metadata.json` to the working directory.

## Commands

Requires Python 3.14, uv, and (for the app and Docker tests) a running Docker daemon.

```sh
uv sync                          # install deps (use --frozen in CI)
uv run pytest                    # unit tests (Docker tests auto-skip)
uv run pytest tests/test_sql.py::test_name   # single test
uv run black --check .           # formatting (line length 100)
uv run ruff check .              # lint
uv run otr-replay --as-of 2026-06-27T23:59   # run the app
```

Docker-backed integration tests (spin up real PostgreSQL containers) are gated behind an
env var and run as a separate CI job:

```sh
OTR_REPLAY_DOCKER_TEST=1 uv run pytest tests/test_reconcile_docker.py
```

## Architecture

The code is a linear pipeline; `cli.main` parses `--as-of` and hands off to
`run.execute`, which orchestrates the stages:

- `discovery.py` — finds inputs on the network. Replicas are scraped from the anchor
  tags of `data.otr.stagec.net`'s index page (names like
  `otr-public-replica_<ISO8601>.gz`). The processor release is the intersection of
  GitHub releases and Docker Hub tags for `stagecodes/otr-processor`: a release is
  "usable at" `max(github published_at, docker tag pushed_at)`, and the newest stable
  `YYYY.MM.DD` tag usable at the cutoff wins. `_get` retries transient failures with
  backoff and raises on exhausted rate limits.
- `sandbox.py` — all Docker interaction via `subprocess` (no docker SDK). A
  `DockerSandbox` creates a run-labeled internal network, volume, and PostgreSQL
  container; imports the gunzipped dump by streaming into `docker exec psql`; runs the
  processor container pinned by image digest. Teardown removes everything by label and
  reports leftovers; it never raises.
- `sql.py` — the reconciliation transaction. The processor's final decay pass runs to
  the wall clock, so decay adjustments (types 1 and 3) past the replica timestamp are
  rolled back and ratings restored. It is fail-closed: any non-decay adjustment past the
  horizon, or any final rating disagreeing with its last adjustment, aborts with
  `RAISE EXCEPTION`. Counters are reported via `OTR_REPLAY_*=N` lines parsed from
  stdout.
- `output.py` — output discipline: paths are claimed up front with `touch(exist_ok=False)`
  (never overwrite), the CSV is written to a `.part` file and renamed after a row-count
  cross-check against the database, metadata is written atomically last.
- `console.py` — Rich-based UI. All user-visible progress goes through `Ui`; stages use
  its `step` / `transfer` / `stream` context managers.
- `models.py` — frozen dataclasses passed between stages, plus `ReplayError`.

## Conventions

- All error handling funnels through `ReplayError(phase, message, hint)`; `cli.main`
  maps it to exit code 1 (130 for interrupt, 3 for unexpected exceptions). Raise it with
  a phase name and an actionable hint rather than letting raw exceptions escape.
- Reproducibility and auditability drive the design: the replica's SHA-256 is verified
  against its published checksum before use, processor images are run by digest (not
  tag), outputs are never overwritten, and every input (replica, release, image digests,
  checksums, counters) is recorded in the `.metadata.json`.
- All timestamps are UTC everywhere — parsing, SQL (`SET LOCAL TIME ZONE 'UTC'`,
  `TZ=UTC`/`PGTZ=UTC` in the container), naming, and metadata. Offset-less timestamps
  from APIs are interpreted as UTC, never host-local.
- Database credentials only exist inside the sandbox; still, `sandbox.redact` scrubs
  them from anything surfaced in errors or logs.
- `pip`/`python` are never invoked directly — everything goes through `uv`. Formatting
  is black with ruff (`E,F,I,B,UP,SIM`), both at line length 100; a few argv lists use
  `# fmt: skip` to keep one-flag-per-line layout.
- Tests use fixtures in `tests/fixtures/` (saved HTML index, GitHub/Docker Hub JSON,
  seed schema) so unit tests never touch the network.
