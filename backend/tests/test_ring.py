"""
Unit tests for Ring Leader Election algorithm with mocked network.
"""
import pytest
from backend.protocol import AlgorithmType, Message, MessageType, NodeStatus
from backend.node.ring import RingElection


def test_ring_successors_ordering():
    peers = {1: 9001, 2: 9002, 3: 9003, 4: 9004}

    r1 = RingElection(1, lambda: peers, lambda *args: None, lambda *args: None)
    assert r1.get_ring_successors() == [2, 3, 4]

    r2 = RingElection(2, lambda: peers, lambda *args: None, lambda *args: None)
    assert r2.get_ring_successors() == [3, 4, 1]

    r4 = RingElection(4, lambda: peers, lambda *args: None, lambda *args: None)
    assert r4.get_ring_successors() == [1, 2, 3]


@pytest.mark.asyncio
async def test_ring_token_circuit_and_winner_election():
    state_changes = []
    sent_tokens = []

    async def fake_send(target: int, msg: Message) -> bool:
        sent_tokens.append((target, msg.model_copy(deep=True)))
        return True

    async def fake_on_state(status: NodeStatus, leader_id):
        state_changes.append((status, leader_id))

    peers = {1: 9001, 2: 9002, 3: 9003}
    ring = RingElection(
        node_id=1,
        get_peers=lambda: peers,
        send_message_to_node=fake_send,
        on_state_change=fake_on_state,
    )

    # 1. Start election from Node 1
    await ring.start_election()
    assert (NodeStatus.ELECTING, None) in state_changes
    assert len(sent_tokens) == 1
    target, msg = sent_tokens[0]
    assert target == 2
    assert msg.type == MessageType.RING_ELECTION
    assert msg.payload["alive"] == [1]

    # 2. Simulate token returning to Node 1 after passing 2 and 3
    returning_token = Message(
        type=MessageType.RING_ELECTION,
        from_node=3,
        to_node=1,
        election_id=msg.election_id,
        algorithm=AlgorithmType.RING,
        payload={
            "initiator": 1,
            "alive": [1, 2, 3],
        },
    )
    await ring.handle_election_token(returning_token)

    # Winner should be 3!
    assert (NodeStatus.FOLLOWER, 3) in state_changes or (NodeStatus.ALIVE, 3) in state_changes

    # Node 1 must have sent RING_COORDINATOR token to next neighbor (2)
    coord_tokens = [m for t, m in sent_tokens if m.type == MessageType.RING_COORDINATOR]
    assert len(coord_tokens) == 1
    assert coord_tokens[0].payload["leader"] == 3


@pytest.mark.asyncio
async def test_ring_dead_node_skipping():
    attempted_targets = []

    async def fake_send(target: int, msg: Message) -> bool:
        attempted_targets.append(target)
        # Node 2 is dead/unresponsive!
        if target == 2:
            return False
        # Node 3 is alive
        return True

    peers = {1: 9001, 2: 9002, 3: 9003}
    ring = RingElection(
        node_id=1,
        get_peers=lambda: peers,
        send_message_to_node=fake_send,
        on_state_change=lambda *args: None,
    )

    token = Message(
        type=MessageType.RING_ELECTION,
        from_node=1,
        to_node=0,
        election_id="e-test",
        algorithm=AlgorithmType.RING,
        payload={"initiator": 1, "alive": [1]},
    )

    success = await ring.forward_around_ring(token)
    assert success is True
    # Verify it tried 2 first, failed, then forwarded to 3
    assert attempted_targets == [2, 3]
