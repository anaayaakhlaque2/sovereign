"""
Unit tests for Bully Leader Election algorithm with mocked network.
"""
import asyncio
import pytest
from backend.protocol import AlgorithmType, Message, MessageType, NodeStatus
from backend.node.bully import BullyElection


@pytest.mark.asyncio
async def test_bully_highest_node_wins_immediately():
    state_changes = []

    async def fake_send(msg: Message) -> bool:
        return True

    async def fake_broadcast(msg: Message, targets):
        pass

    async def fake_on_state(status: NodeStatus, leader_id):
        state_changes.append((status, leader_id))

    # Cluster of nodes 1, 2, 3. Testing on node 3 (the highest)
    peers = {1: 9001, 2: 9002, 3: 9003}
    bully = BullyElection(
        node_id=3,
        get_peers=lambda: peers,
        send_message=fake_send,
        broadcast_message=fake_broadcast,
        on_state_change=fake_on_state,
        ok_timeout=0.1,
        coordinator_timeout=0.2,
    )

    await bully.start_election()
    # Node 3 has no higher peers, so it transitions to ELECTING then directly to LEADER
    assert (NodeStatus.LEADER, 3) in state_changes


@pytest.mark.asyncio
async def test_bully_lower_node_times_out_when_higher_unresponsive():
    broadcast_messages = []
    state_changes = []

    async def fake_send(msg: Message) -> bool:
        return True

    async def fake_broadcast(msg: Message, targets):
        broadcast_messages.append((msg, targets))

    async def fake_on_state(status: NodeStatus, leader_id):
        state_changes.append((status, leader_id))

    # Node 2 starts election, Node 3 is known but won't reply OK
    peers = {1: 9001, 2: 9002, 3: 9003}
    bully = BullyElection(
        node_id=2,
        get_peers=lambda: peers,
        send_message=fake_send,
        broadcast_message=fake_broadcast,
        on_state_change=fake_on_state,
        ok_timeout=0.08,
        coordinator_timeout=0.2,
    )

    await bully.start_election()
    assert (NodeStatus.ELECTING, None) in state_changes

    # Wait for OK timeout
    await asyncio.sleep(0.15)

    # Node 2 should have declared itself leader
    assert (NodeStatus.LEADER, 2) in state_changes
    # And broadcast COORDINATOR to peer 1 and 3
    coord_broadcast = [m for m, targets in broadcast_messages if m.type == MessageType.COORDINATOR]
    assert len(coord_broadcast) == 1
    assert coord_broadcast[0].payload["leader"] == 2


@pytest.mark.asyncio
async def test_bully_higher_node_replies_ok_and_takes_over():
    sent_messages = []
    state_changes = []

    async def fake_send(msg: Message) -> bool:
        sent_messages.append(msg)
        return True

    async def fake_broadcast(msg: Message, targets):
        pass

    async def fake_on_state(status: NodeStatus, leader_id):
        state_changes.append((status, leader_id))

    peers = {1: 9001, 2: 9002}
    bully = BullyElection(
        node_id=2,
        get_peers=lambda: peers,
        send_message=fake_send,
        broadcast_message=fake_broadcast,
        on_state_change=fake_on_state,
        ok_timeout=0.1,
        coordinator_timeout=0.2,
    )

    # Node 2 receives ELECTION from lower Node 1
    incoming_election = Message(
        type=MessageType.ELECTION,
        from_node=1,
        to_node=2,
        election_id="e-test-1",
        algorithm=AlgorithmType.BULLY,
        payload={"initiator": 1},
    )

    await bully.handle_election_message(incoming_election)

    # Node 2 must have sent OK to Node 1
    ok_msgs = [m for m in sent_messages if m.type == MessageType.OK]
    assert len(ok_msgs) == 1
    assert ok_msgs[0].to_node == 1

    # Node 2 also starts its own election and becomes LEADER because it's the highest
    assert (NodeStatus.LEADER, 2) in state_changes


@pytest.mark.asyncio
async def test_bully_higher_node_rejects_lower_coordinator():
    state_changes = []

    async def fake_send(msg: Message) -> bool:
        return True

    async def fake_broadcast(msg: Message, targets):
        pass

    async def fake_on_state(status: NodeStatus, leader_id):
        state_changes.append((status, leader_id))

    peers = {1: 9001, 2: 9002, 3: 9003}
    bully = BullyElection(
        node_id=3,
        get_peers=lambda: peers,
        send_message=fake_send,
        broadcast_message=fake_broadcast,
        on_state_change=fake_on_state,
        ok_timeout=0.08,
        coordinator_timeout=0.2,
    )

    # Node 1 sends COORDINATOR claiming to be leader
    coord_msg = Message(
        type=MessageType.COORDINATOR,
        from_node=1,
        to_node=3,
        algorithm=AlgorithmType.BULLY,
        payload={"leader": 1},
    )
    await bully.handle_coordinator_message(coord_msg)
    # Give async task a brief moment to execute start_election and declare leadership
    await asyncio.sleep(0.05)
    # Node 3 must have rejected Node 1, bullied, and declared itself LEADER
    assert (NodeStatus.LEADER, 3) in state_changes
