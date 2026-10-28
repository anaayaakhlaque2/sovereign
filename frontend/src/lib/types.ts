export type NodeStatusType = 'FOLLOWER' | 'ALIVE' | 'DEAD' | 'ELECTING' | 'LEADER';
export type AlgorithmType = 'bully' | 'ring';
export type CameraMode = 'auto-orbit' | 'orbit' | 'follow-election' | 'top-down';
export type ActiveTabType = 'dashboard' | 'analytics' | 'replay';
export type ThemeType = 'night' | 'day';

export interface NodeState {
  id: number;
  port: number;
  status: NodeStatusType;
  leader_id: number | null;
  algorithm: AlgorithmType;
}

export interface OrbMessage {
  id: string;
  from: number;
  to: number;
  type: string;
  color: string;
  progress: number;
  speed: number;
  ts: number;
}

export interface LogEntry {
  id: string;
  ts: number;
  timeStr: string;
  lamport: number;
  from: number;
  to: number;
  type: string;
  text: string;
  election_id?: string;
}

export interface ElectionRecord {
  id: number;
  election_id: string;
  algorithm: string;
  node_count: number;
  initiator_id?: number;
  winner_id?: number;
  start_ts: number;
  end_ts?: number;
  duration_ms?: number;
  election_messages: number;
  heartbeat_messages: number;
  total_messages: number;
}

export interface EventRecord {
  id: number;
  election_id?: string;
  event_type: string;
  node_id: number;
  from_node?: number;
  to_node?: number;
  msg_type?: string;
  lamport: number;
  ts: number;
  details_json: string;
}
