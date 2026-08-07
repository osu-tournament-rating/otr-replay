# otr-replay

`otr-replay` reproduces the osu! Tournament Rating (o!TR) player ratings that were
published at a chosen point in time. It automates the documented rating-generation
procedure end to end so the osu! Tournament Committee can independently verify the
ratings a tournament used, without credentials.

Given a UTC timestamp, the program downloads the most recent public database
replica available at that time, imports it into a temporary PostgreSQL container,
runs the most recent `otr-processor` release available at that time, and writes
the resulting ratings to a CSV file. Because historical processor releases apply
rating decay up to the moment they run, the program then removes the decay
adjustments fabricated after the replica was created and restores the exact
values they recorded; it never recomputes any rating mathematics, and it aborts
without output if anything other than decay follows the replica timestamp.

## Prerequisites

- [Docker](https://www.docker.com/get-started/)
- [uv](https://docs.astral.sh/uv/)

## Usage

Run the program from the repository root with the UTC timestamp at which the
tournament closed registrations, or another timestamp the ratings were taken from:

```sh
uv run otr-replay --as-of 2026-06-27T23:59
```

`--as-of` is the only argument. It accepts `YYYY-MM-DDTHH:MM[:SS][Z]` and always
means UTC.

## Output

Two files are written to the working directory and never overwritten:

- `otr-replay_asof-<timestamp>_snapshot-<replica>_processor-<release>.csv` with the
  columns `osu_id`, `username`, `ruleset`, `rating`, and `volatility`.
- A `.metadata.json` sidecar recording the inputs, checksums, and reconciliation
  counts for auditing.

## License

MIT
