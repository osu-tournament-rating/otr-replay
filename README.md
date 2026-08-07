# otr-replay

`otr-replay` reproduces the osu! Tournament Rating (o!TR) player ratings that were
published at a chosen point in time. It automates the documented rating-generation
procedure end to end so the osu! Tournament Committee can independently verify the
ratings a tournament used, without credentials.

Given a UTC timestamp, the program resolves the effective rating instant (the most
recent Tuesday 12:00 UTC at or before the timestamp, when o!TR ratings actually
changed), downloads the matching public database replica, imports it into a
temporary PostgreSQL container, runs the matching `otr-processor` release, and
writes the resulting ratings to a CSV file. Because historical processor releases
apply rating decay up to the moment they run, the program then removes the decay
adjustments fabricated past the instant and restores the exact values they
recorded; it never recomputes any rating mathematics, and it aborts without output
if anything other than decay follows the instant.

## Prerequisites

- [Docker](https://www.docker.com/get-started/)
- [uv](https://docs.astral.sh/uv/)

## Usage

Run the program from the repository root with the UTC timestamp at which the
tournament closed registrations, or another timestamp the ratings were taken from:

```sh
uv run otr-replay --as-of 2026-06-27T23:59Z
```

`--as-of` is the only argument. It accepts `YYYY-MM-DDTHH:MM[:SS][Z]` and always
means UTC.

## Output

Two files are written to the working directory and never overwritten:

- `otr-replay_asof-<instant>_snapshot-<replica>_processor-<release>.csv` with the
  columns `osu_id`, `username`, `ruleset`, `rating`, and `volatility`.
- A `.metadata.json` sidecar recording the inputs, checksums, and reconciliation
  counts for auditing.

A replay is a reproduction, not an official o!TR record. Credit
[osu! Tournament Rating (o!TR)](https://otr.stagec.net/) and follow the
[dataset terms](https://data.otr.stagec.net/) when sharing output.

## License

MIT
