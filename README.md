# otr-replay

`otr-replay` reproduces the osu! Tournament Rating (o!TR) player ratings as they were at a certain timestamp provided as input to this application.

Given a UTC timestamp, the program downloads the most recent public database
replica available at that time, imports it into a temporary PostgreSQL container,
runs the most recent `otr-processor` release available at that time, and writes
the resulting ratings to a CSV file. A reconciliation is also performed as described
in [our online documentation](https://docs.otr.stagec.net/Steps-to-Generate-Ratings#Decay-Reconciliation).

## Prerequisites

- [Docker](https://www.docker.com/get-started/)
- [uv](https://docs.astral.sh/uv/)

## Usage

Run the program from the repository root with the UTC timestamp at which the
tournament closed registrations, or another timestamp the ratings were taken from:

```sh
uv run otr-replay --as-of 2026-06-27T23:59
```

`--as-of` is the only argument. It expects a UTC timestamp in this format: `YYYY-MM-DDTHH:MM[:SS][Z]`. `:SS` and `Z` are optional.

## Output

Two files are written to the working directory and never overwritten:

- `otr-replay_asof-<timestamp>_snapshot-<replica>_processor-<release>.csv` with the
  columns `osu_id`, `username`, `ruleset`, `rating`, and `volatility`.
- A `.metadata.json` which records the inputs, checksums, and reconciliation counts for auditing.

## License

MIT
