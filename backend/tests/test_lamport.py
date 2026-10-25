"""
Unit tests for Lamport Logical Clock.
Verifies monotonicity and causal ordering.
"""
from backend.protocol import LamportClock


def test_lamport_clock_initialization():
    clock = LamportClock()
    assert clock.value == 0
    clock_custom = LamportClock(10)
    assert clock_custom.value == 10


def test_lamport_clock_tick():
    clock = LamportClock()
    assert clock.tick() == 1
    assert clock.tick() == 2
    assert clock.value == 2


def test_lamport_clock_update_with_lower_timestamp():
    clock = LamportClock(10)
    # Received message with timestamp 5 -> clock should be max(10, 5) + 1 = 11
    updated = clock.update(5)
    assert updated == 11
    assert clock.value == 11


def test_lamport_clock_update_with_higher_timestamp():
    clock = LamportClock(5)
    # Received message with timestamp 20 -> clock should be max(5, 20) + 1 = 21
    updated = clock.update(20)
    assert updated == 21
    assert clock.value == 21


def test_causal_ordering_across_three_nodes():
    c1 = LamportClock()
    c2 = LamportClock()
    c3 = LamportClock()

    # Node 1 sends message to Node 2
    t1 = c1.tick()  # 1
    t2 = c2.update(t1)  # max(0, 1) + 1 = 2

    # Node 2 sends message to Node 3
    t2_send = c2.tick()  # 3
    t3 = c3.update(t2_send)  # max(0, 3) + 1 = 4

    assert t1 < t2 < t2_send < t3
