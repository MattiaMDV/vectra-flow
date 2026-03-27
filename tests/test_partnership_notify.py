"""Tests for vectra_flow.partnership_notify module."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vectra_flow.asset_scout import ScoutedAsset
from vectra_flow.partnership_notify import (
    FREE_PERIOD_DAYS,
    MIN_FEE_RATE,
    PartnershipProposal,
    compute_fee_rate,
    create_proposal,
    create_proposals,
    write_proposals,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scouted_asset(**kwargs) -> ScoutedAsset:
    defaults = dict(
        name="TEST",
        source_url="https://old.reddit.com/r/CryptoMoonShots/",
        source_platform="reddit",
        snippet="Undervalued hidden gem token $TEST looking for partners.",
        score=0.65,
        tickers=["TEST"],
        project_urls=["https://testtoken.io"],
    )
    defaults.update(kwargs)
    return ScoutedAsset(**defaults)


# ---------------------------------------------------------------------------
# compute_fee_rate
# ---------------------------------------------------------------------------


def test_fee_rate_zero_during_free_period() -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=FREE_PERIOD_DAYS - 1)
    assert compute_fee_rate(start, now=now) == 0.0


def test_fee_rate_positive_after_free_period() -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=FREE_PERIOD_DAYS)
    rate = compute_fee_rate(start, now=now)
    assert rate == pytest.approx(MIN_FEE_RATE)


def test_fee_rate_uses_base_rate() -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=FREE_PERIOD_DAYS + 5)
    assert compute_fee_rate(start, now=now, base_rate=0.20) == pytest.approx(0.20)


def test_fee_rate_defaults_to_now() -> None:
    # Partnership started more than FREE_PERIOD_DAYS ago — should return base rate
    old_start = datetime.now(timezone.utc) - timedelta(days=FREE_PERIOD_DAYS + 10)
    rate = compute_fee_rate(old_start)
    assert rate == pytest.approx(MIN_FEE_RATE)


# ---------------------------------------------------------------------------
# create_proposal
# ---------------------------------------------------------------------------


def test_create_proposal_returns_proposal() -> None:
    asset = _make_scouted_asset()
    proposal = create_proposal(asset)
    assert isinstance(proposal, PartnershipProposal)


def test_create_proposal_asset_name_copied() -> None:
    asset = _make_scouted_asset(name="GEMCOIN")
    proposal = create_proposal(asset)
    assert proposal.asset_name == "GEMCOIN"


def test_create_proposal_source_url_copied() -> None:
    asset = _make_scouted_asset()
    proposal = create_proposal(asset)
    assert proposal.source_url == asset.source_url


def test_create_proposal_fee_rate_equals_min() -> None:
    asset = _make_scouted_asset()
    proposal = create_proposal(asset)
    assert proposal.fee_rate == pytest.approx(MIN_FEE_RATE)


def test_create_proposal_outreach_message_is_string() -> None:
    asset = _make_scouted_asset()
    proposal = create_proposal(asset)
    assert isinstance(proposal.outreach_message, str)
    assert len(proposal.outreach_message) > 0


def test_create_proposal_message_mentions_asset_name() -> None:
    asset = _make_scouted_asset(name="AWESOMECOIN")
    proposal = create_proposal(asset)
    assert "AWESOMECOIN" in proposal.outreach_message


def test_create_proposal_message_mentions_free_period() -> None:
    asset = _make_scouted_asset()
    proposal = create_proposal(asset)
    assert str(FREE_PERIOD_DAYS) in proposal.outreach_message


def test_create_proposal_message_mentions_fee_rate() -> None:
    asset = _make_scouted_asset()
    proposal = create_proposal(asset)
    assert "15" in proposal.outreach_message  # 15%


def test_create_proposal_free_period_ends_14_days_from_now() -> None:
    asset = _make_scouted_asset()
    proposal = create_proposal(asset)
    created = datetime.fromisoformat(proposal.created_at)
    free_end = datetime.fromisoformat(proposal.free_period_ends_at)
    delta = (free_end - created).days
    assert delta == FREE_PERIOD_DAYS


def test_create_proposal_project_url_in_message() -> None:
    asset = _make_scouted_asset(project_urls=["https://myproject.io"])
    proposal = create_proposal(asset)
    assert proposal.outreach_message.count("https://myproject.io") >= 1


def test_create_proposal_falls_back_to_source_url_when_no_project_url() -> None:
    asset = _make_scouted_asset(project_urls=[])
    proposal = create_proposal(asset)
    assert asset.source_url in proposal.outreach_message


# ---------------------------------------------------------------------------
# create_proposals (batch)
# ---------------------------------------------------------------------------


def test_create_proposals_returns_list() -> None:
    assets = [_make_scouted_asset(name=f"TOKEN{i}") for i in range(3)]
    proposals = create_proposals(assets)
    assert len(proposals) == 3


def test_create_proposals_preserves_order() -> None:
    names = ["ALPHA", "BETA", "GAMMA"]
    assets = [_make_scouted_asset(name=n) for n in names]
    proposals = create_proposals(assets)
    assert [p.asset_name for p in proposals] == names


def test_create_proposals_empty_input() -> None:
    assert create_proposals([]) == []


# ---------------------------------------------------------------------------
# write_proposals
# ---------------------------------------------------------------------------


def test_write_proposals_creates_three_files(tmp_path: Path) -> None:
    proposals = [create_proposal(_make_scouted_asset())]
    paths = write_proposals(proposals, out_dir=tmp_path)
    assert len(paths) == 3
    for p in paths:
        assert p.exists()


def test_write_proposals_json_valid(tmp_path: Path) -> None:
    proposals = [create_proposal(_make_scouted_asset(name="JSONTEST"))]
    write_proposals(proposals, out_dir=tmp_path)
    data = json.loads((tmp_path / "notifications.json").read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["asset_name"] == "JSONTEST"


def test_write_proposals_markdown_starts_with_heading(tmp_path: Path) -> None:
    proposals = [create_proposal(_make_scouted_asset())]
    write_proposals(proposals, out_dir=tmp_path)
    md = (tmp_path / "notifications.md").read_text(encoding="utf-8")
    assert md.startswith("# Vectra-Flow")


def test_write_proposals_txt_contains_outreach(tmp_path: Path) -> None:
    proposals = [create_proposal(_make_scouted_asset(name="TXTTEST"))]
    write_proposals(proposals, out_dir=tmp_path)
    txt = (tmp_path / "notifications.txt").read_text(encoding="utf-8")
    assert "TXTTEST" in txt


def test_write_proposals_creates_out_dir(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested"
    proposals = [create_proposal(_make_scouted_asset())]
    write_proposals(proposals, out_dir=nested)
    assert nested.exists()


def test_write_proposals_empty_list(tmp_path: Path) -> None:
    paths = write_proposals([], out_dir=tmp_path)
    assert len(paths) == 3
    data = json.loads((tmp_path / "notifications.json").read_text(encoding="utf-8"))
    assert data == []


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_free_period_days_is_14() -> None:
    assert FREE_PERIOD_DAYS == 14


def test_min_fee_rate_is_15_percent() -> None:
    assert MIN_FEE_RATE == pytest.approx(0.15)
