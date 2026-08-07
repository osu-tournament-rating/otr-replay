"""Finds and fetches the public replica and the processor release."""

import hashlib
import os
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx

from otr_replay.models import Release, ReplayError, Replica, ReplicaRef

DATA_SITE = "https://data.otr.stagec.net/"
RELEASES_URL = "https://api.github.com/repos/osu-tournament-rating/otr-processor/releases"
TAGS_URL = "https://hub.docker.com/v2/repositories/stagecodes/otr-processor/tags"

_REPLICA_NAME = re.compile(
    r"^otr-public-replica_(\d{4})([-_])(\d{2})\2(\d{2})_(\d{2})_(\d{2})_(\d{2})\.gz$"
)
_STABLE_TAG = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href" and value)


def parse_replica_timestamp(name: str) -> datetime | None:
    match = _REPLICA_NAME.match(name)
    if match is None:
        return None
    year, _, month, day, hour, minute, second = match.groups()
    try:
        return datetime(*map(int, (year, month, day, hour, minute, second)), tzinfo=UTC)
    except ValueError:
        return None


def parse_index(html: str) -> list[ReplicaRef]:
    parser = _Anchors()
    parser.feed(html)
    refs = []
    for href in parser.hrefs:
        name = href.rsplit("/", 1)[-1]
        timestamp = parse_replica_timestamp(name)
        if timestamp is not None:
            refs.append(ReplicaRef(name=name, url=href, timestamp=timestamp))
    return sorted(refs, key=lambda ref: ref.timestamp, reverse=True)


def select_replica(refs: Sequence[ReplicaRef], instant: datetime) -> ReplicaRef:
    eligible = [ref for ref in refs if ref.timestamp <= instant]
    if not eligible:
        oldest = min((ref.timestamp for ref in refs), default=None)
        raise ReplayError(
            "discovery",
            f"no public replica exists at or before {instant:%Y-%m-%dT%H:%M:%SZ}",
            (
                f"The oldest published replica is dated {oldest:%Y-%m-%dT%H:%M:%SZ}; "
                "choose a later --as-of."
                if oldest
                else "The public replica index is empty."
            ),
        )
    return eligible[0]


def discover_replicas(client: httpx.Client) -> list[ReplicaRef]:
    refs = parse_index(_get(client, DATA_SITE).text)
    if not refs:
        raise ReplayError("discovery", f"no replicas found at {DATA_SITE}")
    return refs


def fetch_releases(client: httpx.Client) -> list[dict]:
    headers = {"accept": "application/vnd.github+json", "x-github-api-version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["authorization"] = f"Bearer {token}"
    releases: list[dict] = []
    url: str | None = f"{RELEASES_URL}?per_page=100"
    for _ in range(10):
        if url is None:
            break
        response = _get(client, url, headers=headers)
        if (
            response.status_code in (403, 429)
            and response.headers.get("x-ratelimit-remaining") == "0"
        ):
            raise ReplayError(
                "discovery",
                "the GitHub API rate limit is exhausted",
                "Wait for the limit to reset or set GITHUB_TOKEN to raise it.",
            )
        if response.status_code != 200:
            raise ReplayError("discovery", f"GitHub returned HTTP {response.status_code}")
        releases.extend(response.json())
        url = response.links.get("next", {}).get("url")
    return releases


def fetch_tags(client: httpx.Client) -> list[dict]:
    tags: list[dict] = []
    url: str | None = f"{TAGS_URL}?page_size=100"
    for _ in range(10):
        if url is None:
            break
        payload = _get(client, url).json()
        tags.extend(payload["results"])
        url = payload.get("next")
    return tags


def select_release(releases: list[dict], tags: list[dict], instant: datetime) -> Release:
    pushed: dict[str, tuple[datetime, str]] = {
        tag["name"]: (_parse_utc(tag["tag_last_pushed"]), tag["digest"])
        for tag in tags
        if tag.get("tag_status", "active") == "active" and tag.get("digest")
    }
    candidates = []
    for entry in releases:
        tag = entry["tag_name"]
        if entry["draft"] or entry["prerelease"] or not _STABLE_TAG.match(tag) or tag not in pushed:
            continue
        pushed_at, digest = pushed[tag]
        candidates.append(
            Release(
                tag=tag,
                published_at=_parse_utc(entry["published_at"]),
                pushed_at=pushed_at,
                digest=digest,
            )
        )
    usable = [release for release in candidates if release.usable_at <= instant]
    if not usable:
        earliest = min(candidates, key=lambda release: release.usable_at, default=None)
        raise ReplayError(
            "discovery",
            f"no processor release is usable at {instant:%Y-%m-%dT%H:%M:%SZ}",
            (
                f"The earliest usable release is {earliest.tag} "
                f"(usable {earliest.usable_at:%Y-%m-%dT%H:%M:%SZ}); choose a later --as-of."
                if earliest
                else "No stable processor release exists on both GitHub and Docker Hub."
            ),
        )
    return max(usable, key=lambda release: release.tag)


def download_replica(
    client: httpx.Client,
    ref: ReplicaRef,
    dest_dir: Path,
    on_chunk: Callable[[int, int], None],
) -> Replica:
    path = dest_dir / ref.name
    digest = hashlib.sha256()
    downloaded = 0
    try:
        with client.stream("GET", ref.url) as response:
            _raise_for_status(response, ref.url)
            total = int(response.headers.get("content-length", 0))
            with path.open("wb") as file:
                for chunk in response.iter_bytes(1 << 16):
                    file.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    on_chunk(downloaded, total)
    except httpx.HTTPError as err:
        raise ReplayError("download", f"downloading {ref.name} failed: {err}") from err
    expected = _fetch_checksum(client, ref)
    if digest.hexdigest() != expected:
        raise ReplayError(
            "download",
            f"SHA-256 mismatch for {ref.name}",
            f"Expected {expected}, calculated {digest.hexdigest()}. Retry the run.",
        )
    return Replica(ref=ref, path=path, sha256=digest.hexdigest())


def _fetch_checksum(client: httpx.Client, ref: ReplicaRef) -> str:
    try:
        response = client.get(f"{ref.url}.sha256")
    except httpx.HTTPError as err:
        raise ReplayError(
            "download", f"fetching the checksum for {ref.name} failed: {err}"
        ) from err
    if response.status_code != 200:
        raise ReplayError(
            "download",
            f"no SHA-256 checksum is published for {ref.name}",
            "This replica cannot be verified; choose an --as-of covered by a "
            "checksummed replica.",
        )
    line = response.text.strip()
    match = re.match(r"^([0-9a-f]{64})\s+\*?(\S+)$", line)
    if match is None or match.group(2) != ref.name:
        raise ReplayError("download", f"unrecognized checksum file for {ref.name}")
    return match.group(1)


def _get(client: httpx.Client, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
    try:
        response = client.get(url, headers=headers)
    except httpx.HTTPError as err:
        raise ReplayError("discovery", f"request to {url} failed: {err}") from err
    if response.status_code != 200 and not (
        url.startswith(RELEASES_URL) and response.status_code in (403, 429)
    ):
        raise ReplayError("discovery", f"{url} returned HTTP {response.status_code}")
    return response


def _raise_for_status(response: httpx.Response, url: str) -> None:
    if response.status_code != 200:
        raise ReplayError("download", f"{url} returned HTTP {response.status_code}")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
