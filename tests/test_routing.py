"""Tests for confidence-based routing decision logic."""

from src.schemas import make_routing_decision, RoutingDecision


def test_high_confidence_proceeds():
    assert make_routing_decision(0.95) == RoutingDecision.PROCEED


def test_medium_confidence_pending():
    assert make_routing_decision(0.5) == RoutingDecision.PENDING_REVIEW


def test_low_confidence_rejected():
    assert make_routing_decision(0.2) == RoutingDecision.REJECTED


def test_boundary_proceed():
    assert make_routing_decision(0.7) == RoutingDecision.PROCEED


def test_boundary_pending():
    assert make_routing_decision(0.3) == RoutingDecision.PENDING_REVIEW
