import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from otr_replay.models import (
    Reconciliation,
    Release,
    ReplayError,
    Replica,
    ReplicaRef,
    Report,
)
from otr_replay.output import build_metadata, claim, output_paths, write_atomic


def test_output_paths_name_the_requested_timestamp(tmp_path):
    csv, metadata = output_paths(
        requested=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        directory=tmp_path,
    )
    assert csv.name == "otr-replay_20260728T120000Z.csv"
    assert metadata.name == "otr-replay_20260728T120000Z.metadata.json"


def test_claim_refuses_existing_files(tmp_path):
    target = tmp_path / "out.csv"
    target.touch()
    with pytest.raises(ReplayError) as exc:
        claim(target)
    assert exc.value.phase == "output"


def test_metadata_has_no_credentials(tmp_path):
    ref = ReplicaRef(
        name="otr-public-replica_2026-07-28T11:45:01Z.gz",
        url="https://storage.googleapis.com/otr-public-replica/otr-public-replica_2026-07-28T11%3A45%3A01Z.gz",
        timestamp=datetime(2026, 7, 28, 11, 45, 1, tzinfo=UTC),
    )
    report = Report(
        requested_at=datetime(2026, 8, 1, tzinfo=UTC),
        replica=Replica(ref=ref, path=Path("/tmp/x.gz"), sha256="ab" * 32),
        release=Release(
            tag="2026.05.18",
            published_at=datetime(2026, 5, 18, 19, 56, 7, tzinfo=UTC),
            pushed_at=datetime(2026, 5, 18, 19, 59, 11, tzinfo=UTC),
            digest="sha256:" + "cd" * 32,
        ),
        reconciliation=Reconciliation(ratings_restored=10, adjustments_rolled_back=20),
        row_count=1234,
        started_at=datetime(2026, 8, 6, 1, 0, tzinfo=UTC),
        finished_at=datetime(2026, 8, 6, 1, 30, tzinfo=UTC),
        csv_path=tmp_path / "out.csv",
        metadata_path=tmp_path / "out.metadata.json",
        csv_sha256="ef" * 32,
        postgres_image="postgres@sha256:" + "12" * 32,
        source_commit="ab" * 20,
    )
    rendered = json.dumps(build_metadata(report))
    assert "password" not in rendered
    assert "adjustments_rolled_back" in rendered
    assert build_metadata(report)["output"]["csv_sha256"] == "ef" * 32


def test_write_atomic_replaces_claimed_file(tmp_path):
    target = tmp_path / "file.json"
    claim(target)
    write_atomic(target, "{}")
    assert target.read_text() == "{}"
    assert list(tmp_path.iterdir()) == [target]
