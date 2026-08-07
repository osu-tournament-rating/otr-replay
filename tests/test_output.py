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


def test_output_paths_name_the_instant_snapshot_and_release(tmp_path):
    csv, metadata = output_paths(
        instant=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        snapshot=datetime(2026, 7, 28, 11, 45, 1, tzinfo=UTC),
        tag="2026.05.18",
        directory=tmp_path,
    )
    assert csv.name == (
        "otr-replay_asof-20260728T120000Z_snapshot-20260728T114501Z_processor-2026.05.18.csv"
    )
    assert metadata.name == csv.name.replace(".csv", ".metadata.json")


def test_claim_refuses_existing_files(tmp_path):
    target = tmp_path / "out.csv"
    target.touch()
    with pytest.raises(ReplayError) as exc:
        claim(target)
    assert exc.value.phase == "output"


def test_metadata_has_disclaimer_and_no_credentials(tmp_path):
    ref = ReplicaRef(
        name="otr-public-replica_2026-07-28_11_45_01.gz",
        url="https://storage.googleapis.com/otr-public-replica/otr-public-replica_2026-07-28_11_45_01.gz",
        timestamp=datetime(2026, 7, 28, 11, 45, 1, tzinfo=UTC),
    )
    report = Report(
        requested_at=datetime(2026, 8, 1, tzinfo=UTC),
        instant=datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
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
    )
    rendered = json.dumps(build_metadata(report))
    assert "not an official o!TR record" in rendered
    assert "password" not in rendered
    assert "adjustments_rolled_back" in rendered


def test_write_atomic_replaces_claimed_file(tmp_path):
    target = tmp_path / "file.json"
    claim(target)
    write_atomic(target, "{}")
    assert target.read_text() == "{}"
    assert list(tmp_path.iterdir()) == [target]
