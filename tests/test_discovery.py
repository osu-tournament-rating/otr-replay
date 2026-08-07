import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from otr_replay.discovery import parse_index, select_release, select_replica
from otr_replay.models import ReplayError

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def replicas():
    return parse_index((FIXTURES / "index.html").read_text())


@pytest.fixture
def releases():
    return json.loads((FIXTURES / "releases.json").read_text())


@pytest.fixture
def tags():
    return json.loads((FIXTURES / "docker_tags.json").read_text())["results"]


def test_parse_index_reads_both_filename_eras_and_skips_companions(replicas):
    names = [ref.name for ref in replicas]
    assert names == [
        "otr-public-replica_2026-08-04_11_45_01.gz",
        "otr-public-replica_2026-07-28_11_45_01.gz",
        "otr-public-replica_2026-06-03_23_20_30.gz",
        "otr-public-replica_2026-05-28_00_00_29.gz",
        "otr-public-replica_2026-05-16_03_13_48.gz",
        "otr-public-replica_2026_05_12_11_50_01.gz",
        "otr-public-replica_2025_10_06_21_13_57.gz",
    ]
    assert replicas[0].timestamp == datetime(2026, 8, 4, 11, 45, 1, tzinfo=UTC)
    assert replicas[5].timestamp == datetime(2026, 5, 12, 11, 50, 1, tzinfo=UTC)
    assert replicas[0].url.startswith("https://storage.googleapis.com/otr-public-replica/")


def test_select_replica_picks_newest_at_or_before_instant(replicas):
    instant = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    assert select_replica(replicas, instant).name == "otr-public-replica_2026-07-28_11_45_01.gz"


def test_select_replica_includes_off_cadence_dumps(replicas):
    # A dump published late (Wednesday 23:20) must be picked for a later --as-of.
    cutoff = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
    assert select_replica(replicas, cutoff).name == "otr-public-replica_2026-06-03_23_20_30.gz"


def test_select_replica_fails_when_none_exist_before_instant(replicas):
    with pytest.raises(ReplayError) as exc:
        select_replica(replicas, datetime(2025, 1, 1, tzinfo=UTC))
    assert exc.value.phase == "discovery"


def test_select_release_requires_github_and_docker_and_usable_at(releases, tags):
    instant = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
    release = select_release(releases, tags, instant)
    # 2026.08.04 was pushed 23:45, after the instant, so 2026.08.03 wins.
    assert release.tag == "2026.08.03"
    assert release.image == (
        "stagecodes/otr-processor@"
        "sha256:ee6afe78229a90000000000000000000000000000000000000000000000000bb"
    )
    assert release.usable_at == datetime(2026, 8, 3, 23, 8, 19, 220696, tzinfo=UTC)


def test_select_release_ignores_github_only_and_non_stable_tags(releases, tags):
    # 2025.06.08 exists on GitHub only; prereleases and v1.0.0 never qualify.
    with pytest.raises(ReplayError) as exc:
        select_release(releases, tags, datetime(2026, 1, 1, tzinfo=UTC))
    assert "2026.05.18" in exc.value.hint


def test_select_release_picks_latest_usable(releases, tags):
    release = select_release(releases, tags, datetime(2026, 8, 5, 12, 0, tzinfo=UTC))
    assert release.tag == "2026.08.04"
