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

`--as-of` expects a timestamp in this format: `YYYY-MM-DDTHH:MM[:SS]`. `:SS` is
optional, and the timestamp is always interpreted as UTC.

## Output

Two files are written to the working directory and never overwritten:

- `otr-replay_<timestamp>.csv` with the columns `osu_id`, `username`, `ruleset`,
  `rating`, and `volatility`. `<timestamp>` is the `--as-of` value, e.g.
  `otr-replay_20260627T235900Z.csv`.
- A matching `.metadata.json` which records the inputs — replica snapshot, processor release, image digests — plus checksums and reconciliation counts for auditing.

## License

MIT
