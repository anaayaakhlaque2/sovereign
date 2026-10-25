"""
Unit tests for Heartbeat Failure Detector.
"""
import asyncio
import pytest
from backend.node.heartbeat import HeartbeatDetector


@pytest.mark.asyncio
async def test_heartbeat_leader_detects_no_failure_when_acking():
    sent_pings = []
    failed_calls = []

    async def fake_send_heartbeat(target_id: int) -> bool:
        sent_pings.append(target_id)
        return True

    async def fake_on_leader_failed():
        failed_calls.append(True)

    current_leader = 5
    detector = HeartbeatDetector(
        node_id=1,
        get_leader_id=lambda: current_leader,
        send_heartbeat=fake_send_heartbeat,
        on_leader_failed=fake_on_leader_failed,
        ping_interval=0.05,
        timeout=0.15,
    )

    detector.start()
    await asyncio.sleep(0.08)
    # Ack received
    detector.record_ack(5)
    await asyncio.sleep(0.08)
    detector.record_ack(5)

    await detector.stop()
    assert len(sent_pings) >= 1
    assert len(failed_calls) == 0


@pytest.mark.asyncio
async def test_heartbeat_triggers_leader_failed_on_timeout():
    failed_calls = []

    async def fake_send_heartbeat(target_id: int) -> bool:
        # Pings succeed in reaching network, but no ack comes back
        return True

    async def fake_on_leader_failed():
        failed_calls.append(True)

    detector = HeartbeatDetector(
        node_id=1,
        get_leader_id=lambda: 5,
        send_heartbeat=fake_send_heartbeat,
        on_leader_failed=fake_on_leader_failed,
        ping_interval=0.04,
        timeout=0.08,
    )

    detector.start()
    await asyncio.sleep(0.18)
    await detector.stop()

    assert len(failed_calls) >= 1
