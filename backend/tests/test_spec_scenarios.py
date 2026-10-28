"""
Comprehensive Test Suite for Sovereign Leader Election Scenarios T1 - T7.
Tests run on real Node instances communicating over real TCP sockets.
"""
import asyncio
import pytest
from typing import Dict, List
from backend.node.node import Node
from backend.protocol import AlgorithmType, ControlAction, NodeStatus


async def make_cluster(
    count: int,
    base_port: int,
    algo: AlgorithmType = AlgorithmType.BULLY,
    heartbeat_interval: float = 0.5,
    heartbeat_timeout: float = 1.2,
    ok_timeout: float = 0.4,
    coordinator_timeout: float = 1.5,
) -> Dict[int, Node]:
    ports = {i: base_port + i for i in range(1, count + 1)}
    nodes: Dict[int, Node] = {}
    for nid, port in ports.items():
        node = Node(
            node_id=nid,
            port=port,
            peers=ports,
            algorithm=algo,
            heartbeat_interval=heartbeat_interval,
            heartbeat_timeout=heartbeat_timeout,
            ok_timeout=ok_timeout,
            coordinator_timeout=coordinator_timeout,
        )
        nodes[nid] = node
        await node.start()
    return nodes


async def stop_cluster(nodes: Dict[int, Node]) -> None:
    for node in list(nodes.values()):
        await node.stop()


def assert_exactly_one_leader(nodes: Dict[int, Node], expected_leader: int) -> None:
    alive_nodes = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
    leader_nodes = [n for n in alive_nodes if n.status == NodeStatus.LEADER]
    assert len(leader_nodes) == 1, f"Expected exactly 1 leader node, found {len(leader_nodes)}: {[n.node_id for n in leader_nodes]}"
    assert leader_nodes[0].node_id == expected_leader, f"Leader node is {leader_nodes[0].node_id}, expected {expected_leader}"

    for n in alive_nodes:
        assert n.leader_id == expected_leader, f"Node {n.node_id} has leader_id={n.leader_id}, expected {expected_leader}"
        if n.node_id != expected_leader:
            assert n.status == NodeStatus.FOLLOWER, f"Node {n.node_id} has status={n.status}, expected FOLLOWER"


# =============================================================================
# T1: leader 5 crashes, both algorithms, winner is 4, exactly one leader.
# =============================================================================
@pytest.mark.asyncio
async def test_t1_leader_5_crashes_both_algorithms():
    # --- Part A: BULLY ---
    bully_nodes = await make_cluster(count=5, base_port=21100, algo=AlgorithmType.BULLY)
    try:
        # Establish node 5 as leader
        await bully_nodes[5]._on_state_change(NodeStatus.LEADER, 5)
        for nid in range(1, 5):
            await bully_nodes[nid]._on_state_change(NodeStatus.FOLLOWER, 5)

        # Crash leader 5
        await bully_nodes[5]._handle_control({"action": ControlAction.KILL.value})
        assert bully_nodes[5].status == NodeStatus.DEAD

        # Node 1 starts election
        await bully_nodes[1].trigger_election()

        # Wait for election to converge
        for _ in range(50):
            alive = [n for n in bully_nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and bully_nodes[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert_exactly_one_leader(bully_nodes, expected_leader=4)
    finally:
        await stop_cluster(bully_nodes)

    # --- Part B: RING ---
    ring_nodes = await make_cluster(count=5, base_port=21200, algo=AlgorithmType.RING)
    try:
        # Establish node 5 as leader
        await ring_nodes[5]._on_state_change(NodeStatus.LEADER, 5)
        for nid in range(1, 5):
            await ring_nodes[nid]._on_state_change(NodeStatus.FOLLOWER, 5)

        # Crash leader 5
        await ring_nodes[5]._handle_control({"action": ControlAction.KILL.value})
        assert ring_nodes[5].status == NodeStatus.DEAD

        # Node 1 starts election
        await ring_nodes[1].trigger_election()

        # Wait for election to converge
        for _ in range(50):
            alive = [n for n in ring_nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and ring_nodes[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert_exactly_one_leader(ring_nodes, expected_leader=4)
    finally:
        await stop_cluster(ring_nodes)


# =============================================================================
# T2: crash 5 then 4, winner is 3.
# =============================================================================
@pytest.mark.asyncio
async def test_t2_crash_5_then_4_winner_is_3():
    nodes = await make_cluster(count=5, base_port=21300, algo=AlgorithmType.BULLY)
    try:
        # Crash 5 then 4
        await nodes[5]._handle_control({"action": ControlAction.KILL.value})
        await nodes[4]._handle_control({"action": ControlAction.KILL.value})
        assert nodes[5].status == NodeStatus.DEAD
        assert nodes[4].status == NodeStatus.DEAD

        # Trigger election from Node 1
        await nodes[1].trigger_election()

        for _ in range(50):
            alive = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 3 for n in alive) and nodes[3].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert_exactly_one_leader(nodes, expected_leader=3)
    finally:
        await stop_cluster(nodes)


# =============================================================================
# T3: two initiators at once, still one leader.
# =============================================================================
@pytest.mark.asyncio
async def test_t3_two_initiators_at_once_still_one_leader():
    # Test on Ring mode where concurrent initiators must drop lower initiator tokens (Rule 5)
    nodes = await make_cluster(count=5, base_port=21400, algo=AlgorithmType.RING)
    try:
        await nodes[5]._handle_control({"action": ControlAction.KILL.value})

        # Nodes 1 and 2 start election simultaneously
        await asyncio.gather(
            nodes[1].trigger_election(),
            nodes[2].trigger_election(),
        )

        for _ in range(60):
            alive = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and nodes[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert_exactly_one_leader(nodes, expected_leader=4)
    finally:
        await stop_cluster(nodes)


# =============================================================================
# T4: leader crashes during an election, election restarts, one leader.
# =============================================================================
@pytest.mark.asyncio
async def test_t4_leader_crashes_during_election_restarts():
    nodes = await make_cluster(
        count=5,
        base_port=21500,
        algo=AlgorithmType.BULLY,
        ok_timeout=0.3,
        coordinator_timeout=0.8,
    )
    try:
        # Node 5 is dead initially
        await nodes[5]._handle_control({"action": ControlAction.KILL.value})

        # Node 1 starts election
        await nodes[1].trigger_election()
        await asyncio.sleep(0.15)

        # In the middle of election, crash Node 4!
        await nodes[4]._handle_control({"action": ControlAction.KILL.value})

        # Coordinator timeout or failure recovery triggers restart
        for _ in range(60):
            alive = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 3 for n in alive) and nodes[3].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert_exactly_one_leader(nodes, expected_leader=3)
    finally:
        await stop_cluster(nodes)


# =============================================================================
# T5: revive node 5 in Bully mode, node 5 becomes leader again.
# =============================================================================
@pytest.mark.asyncio
async def test_t5_revive_node_5_in_bully_mode():
    nodes = await make_cluster(count=5, base_port=21600, algo=AlgorithmType.BULLY)
    try:
        # Crash 5, node 4 becomes leader
        await nodes[5]._handle_control({"action": ControlAction.KILL.value})
        await nodes[1].trigger_election()

        for _ in range(50):
            alive = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and nodes[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert nodes[4].status == NodeStatus.LEADER

        # Revive node 5 -> Rule R7: starts election in Bully mode and takes over
        await nodes[5]._handle_control({"action": ControlAction.REVIVE.value})

        for _ in range(50):
            alive = [n for n in nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 5 for n in alive) and nodes[5].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        assert_exactly_one_leader(nodes, expected_leader=5)
    finally:
        await stop_cluster(nodes)


# =============================================================================
# T6: message counts match the exact specification numbers.
# Setup: 5 nodes, node 5 crashed, node 1 is the only initiator.
# Bully: ELECTION delivered 6, OK 6, COORDINATOR 3. Delivered total 15.
#        Attempts to dead node 5 are 4 ELECTION + 1 COORDINATOR. Winner: node 4.
# Ring:  RING_ELECTION 4 hops, RING_COORDINATOR 4 hops. Delivered total 8.
#        Winner: node 4.
# =============================================================================
@pytest.mark.asyncio
async def test_t6_message_counts_match_specification():
    # --- Bully Message Count ---
    bully_nodes = await make_cluster(
        count=5,
        base_port=21700,
        algo=AlgorithmType.BULLY,
        heartbeat_interval=100.0,  # disable heartbeat interference during count test
        heartbeat_timeout=100.0,
        ok_timeout=0.5,
        coordinator_timeout=2.0,
    )
    try:
        # Crash node 5
        await bully_nodes[5]._handle_control({"action": ControlAction.KILL.value})
        for n in bully_nodes.values():
            n.sent_messages.clear()

        # Node 1 is the ONLY initiator
        await bully_nodes[1].bully.start_election()

        # Wait for election to complete
        for _ in range(50):
            alive = [n for n in bully_nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and bully_nodes[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        # Wait for all connection attempts to complete (including 1.0s TCP timeout to dead node)
        await asyncio.sleep(1.3)
        assert_exactly_one_leader(bully_nodes, expected_leader=4)

        # Aggregate sent messages across all nodes
        all_sent = []
        for n in bully_nodes.values():
            all_sent.extend(n.sent_messages)

        delivered_election = [m for m in all_sent if m["type"] == "ELECTION" and m["delivered"]]
        delivered_ok = [m for m in all_sent if m["type"] == "OK" and m["delivered"]]
        delivered_coord = [m for m in all_sent if m["type"] == "COORDINATOR" and m["delivered"]]
        failed_attempts_to_5 = [m for m in all_sent if m["to"] == 5 and not m["delivered"]]

        assert len(delivered_election) == 6, f"Expected 6 delivered ELECTION, got {len(delivered_election)}: {delivered_election}"
        assert len(delivered_ok) == 6, f"Expected 6 delivered OK, got {len(delivered_ok)}: {delivered_ok}"
        assert len(delivered_coord) == 3, f"Expected 3 delivered COORDINATOR, got {len(delivered_coord)}: {delivered_coord}"
        total_delivered = len(delivered_election) + len(delivered_ok) + len(delivered_coord)
        assert total_delivered == 15, f"Expected total 15 delivered messages, got {total_delivered}"

        # Attempts to dead node 5: 4 ELECTION + 1 COORDINATOR = 5
        election_to_5 = [m for m in failed_attempts_to_5 if m["type"] == "ELECTION"]
        coord_to_5 = [m for m in failed_attempts_to_5 if m["type"] == "COORDINATOR"]
        assert len(election_to_5) == 4, f"Expected 4 ELECTION attempts to dead node 5, got {len(election_to_5)}"
        assert len(coord_to_5) == 1, f"Expected 1 COORDINATOR attempt to dead node 5, got {len(coord_to_5)}"
        assert len(failed_attempts_to_5) == 5
    finally:
        await stop_cluster(bully_nodes)

    # --- Ring Message Count ---
    ring_nodes = await make_cluster(
        count=5,
        base_port=21800,
        algo=AlgorithmType.RING,
        heartbeat_interval=100.0,
        heartbeat_timeout=100.0,
    )
    try:
        # Crash node 5
        await ring_nodes[5]._handle_control({"action": ControlAction.KILL.value})
        for n in ring_nodes.values():
            n.sent_messages.clear()

        # Node 1 is the ONLY initiator
        await ring_nodes[1].ring.start_election()

        for _ in range(50):
            alive = [n for n in ring_nodes.values() if n.status != NodeStatus.DEAD]
            if all(n.leader_id == 4 for n in alive) and ring_nodes[4].status == NodeStatus.LEADER:
                break
            await asyncio.sleep(0.1)

        await asyncio.sleep(1.3)
        assert_exactly_one_leader(ring_nodes, expected_leader=4)

        all_sent_ring = []
        for n in ring_nodes.values():
            all_sent_ring.extend(n.sent_messages)

        delivered_ring_elec = [m for m in all_sent_ring if m["type"] == "RING_ELECTION" and m["delivered"]]
        delivered_ring_coord = [m for m in all_sent_ring if m["type"] == "RING_COORDINATOR" and m["delivered"]]
        failed_to_5 = [m for m in all_sent_ring if m["to"] == 5 and not m["delivered"]]

        assert len(delivered_ring_elec) == 4, f"Expected 4 RING_ELECTION hops, got {len(delivered_ring_elec)}"
        assert len(delivered_ring_coord) == 4, f"Expected 4 RING_COORDINATOR hops, got {len(delivered_ring_coord)}"
        total_ring_delivered = len(delivered_ring_elec) + len(delivered_ring_coord)
        assert total_ring_delivered == 8, f"Expected 8 delivered Ring messages (2(N-1)), got {total_ring_delivered}"
        assert len(failed_to_5) >= 1, f"Expected at least 1 failed attempt to dead node 5, got {len(failed_to_5)}"
    finally:
        await stop_cluster(ring_nodes)


# =============================================================================
# T7: 3, 5, 7 and 9 nodes, Bully count above Ring count for N>=5.
# =============================================================================
@pytest.mark.asyncio
async def test_t7_scaling_counts_bully_above_ring_for_n_ge_5():
    sizes = [3, 5, 7, 9]
    base_port = 22000

    results = {}

    for n in sizes:
        # Ring delivered count: 2*(n - 1)
        # Bully delivered count: (n-1)*(n-2)/2 (ELECTION) + (n-1)*(n-2)/2 (OK) + (n-2) (COORDINATOR)
        # For N=3: Ring = 4, Bully = 1 + 1 + 1 = 3
        # For N=5: Ring = 8, Bully = 6 + 6 + 3 = 15 (Bully > Ring)
        # For N=7: Ring = 12, Bully = 15 + 15 + 5 = 35 (Bully > Ring)
        # For N=9: Ring = 16, Bully = 28 + 28 + 7 = 63 (Bully > Ring)

        # Test Bully for size n
        b_cluster = await make_cluster(
            count=n,
            base_port=base_port,
            algo=AlgorithmType.BULLY,
            heartbeat_interval=100.0,
            heartbeat_timeout=100.0,
            ok_timeout=0.3,
            coordinator_timeout=1.0,
        )
        base_port += 20
        try:
            # Kill highest node n
            await b_cluster[n]._handle_control({"action": ControlAction.KILL.value})
            for node in b_cluster.values():
                node.sent_messages.clear()

            # Node 1 initiates
            await b_cluster[1].bully.start_election()
            for _ in range(50):
                if b_cluster[n - 1].status == NodeStatus.LEADER:
                    break
                await asyncio.sleep(0.08)
            await asyncio.sleep(0.2)

            bully_delivered = sum(
                len([m for m in node.sent_messages if m["delivered"]]) for node in b_cluster.values()
            )
        finally:
            await stop_cluster(b_cluster)

        # Test Ring for size n
        r_cluster = await make_cluster(
            count=n,
            base_port=base_port,
            algo=AlgorithmType.RING,
            heartbeat_interval=100.0,
            heartbeat_timeout=100.0,
        )
        base_port += 20
        try:
            # Kill highest node n
            await r_cluster[n]._handle_control({"action": ControlAction.KILL.value})
            for node in r_cluster.values():
                node.sent_messages.clear()

            # Node 1 initiates
            await r_cluster[1].ring.start_election()
            for _ in range(50):
                if r_cluster[n - 1].status == NodeStatus.LEADER:
                    break
                await asyncio.sleep(0.08)
            await asyncio.sleep(0.2)

            ring_delivered = sum(
                len([m for m in node.sent_messages if m["delivered"]]) for node in r_cluster.values()
            )
        finally:
            await stop_cluster(r_cluster)

        results[n] = {"bully": bully_delivered, "ring": ring_delivered}
        print(f"Size N={n}: Bully={bully_delivered}, Ring={ring_delivered}")

        # Assert for N >= 5 that Bully count is strictly above Ring count!
        if n >= 5:
            assert bully_delivered > ring_delivered, f"For N={n}: expected Bully ({bully_delivered}) > Ring ({ring_delivered})"
