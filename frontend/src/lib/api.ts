import { AlgorithmType, ElectionRecord, EventRecord } from './types';

const API_BASE = '/api';

export async function fetchClusterState() {
  const res = await fetch(`${API_BASE}/cluster/state`);
  return res.json();
}

export async function killNode(nodeId: number) {
  const res = await fetch(`${API_BASE}/cluster/kill/${nodeId}`, { method: 'POST' });
  return res.json();
}

export async function reviveNode(nodeId: number) {
  const res = await fetch(`${API_BASE}/cluster/revive/${nodeId}`, { method: 'POST' });
  return res.json();
}

export async function assassinateLeader() {
  const res = await fetch(`${API_BASE}/cluster/assassinate`, { method: 'POST' });
  return res.json();
}

export async function setAlgorithm(algorithm: AlgorithmType) {
  const res = await fetch(`${API_BASE}/cluster/algorithm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ algorithm }),
  });
  return res.json();
}

export async function setNetwork(delay: number, dropRate: number) {
  const res = await fetch(`${API_BASE}/cluster/network`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ delay, drop_rate: dropRate }),
  });
  return res.json();
}

export async function triggerElection(initiatorId?: number) {
  const res = await fetch(`${API_BASE}/cluster/election/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ initiator_id: initiatorId }),
  });
  return res.json();
}

export async function toggleChaos(enabled: boolean) {
  const res = await fetch(`${API_BASE}/cluster/chaos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  return res.json();
}

export async function fetchElections(): Promise<ElectionRecord[]> {
  const res = await fetch(`${API_BASE}/elections`);
  return res.json();
}

export async function fetchElectionEvents(electionId: string): Promise<EventRecord[]> {
  const res = await fetch(`${API_BASE}/elections/${electionId}/events`);
  return res.json();
}

export async function runBenchmark(rounds: number = 10, nodeCounts: number[] = [3, 5, 7]) {
  const res = await fetch(`${API_BASE}/benchmark/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rounds, node_counts: nodeCounts }),
  });
  return res.json();
}
