import { create } from 'zustand';
import { ActiveTabType, AlgorithmType, CameraMode, ElectionRecord, LogEntry, NodeState, NodeStatusType, OrbMessage, ThemeType } from '../lib/types';

interface ClusterState {
  nodes: NodeState[];
  leader: number | null;
  algorithm: AlgorithmType;
  nodeCount: number;
  chaos: boolean;
  delay: number;
  dropRate: number;
  connected: boolean;
  cameraMode: CameraMode;
  theme: ThemeType;
  showHeartbeats: boolean;
  selectedNode: number | null;
  logs: LogEntry[];
  activeOrbs: OrbMessage[];
  elections: ElectionRecord[];
  activeTab: ActiveTabType;
  filterType: string;
  showLeftPanel: boolean;
  showRightPanel: boolean;
  showLanding: boolean;

  // Actions
  setConnected: (connected: boolean) => void;
  updateSnapshot: (data: any) => void;
  handleEvent: (evt: any) => void;
  handleConfigChange: (data: any) => void;
  setAlgorithm: (algo: AlgorithmType) => void;
  setCameraMode: (mode: CameraMode) => void;
  setTheme: (theme: ThemeType) => void;
  setShowHeartbeats: (show: boolean) => void;
  setSelectedNode: (id: number | null) => void;
  setActiveTab: (tab: ActiveTabType) => void;
  setFilterType: (filter: string) => void;
  setElections: (elections: ElectionRecord[]) => void;
  addOrb: (orb: OrbMessage) => void;
  removeOrb: (id: string) => void;
  clearLogs: () => void;
  toggleLeftPanel: () => void;
  toggleRightPanel: () => void;
  setLeftPanel: (show: boolean) => void;
  setRightPanel: (show: boolean) => void;
  setShowLanding: (show: boolean) => void;
}

const MESSAGE_COLORS: Record<string, string> = {
  ELECTION: '#ff6b3d', // Orange
  OK: '#22c55e', // Green
  COORDINATOR: '#e8c36a', // Gold
  RING_ELECTION: '#f97316', // Coral
  RING_COORDINATOR: '#eab308', // Bright gold
  HEARTBEAT: '#93c5fd', // Translucent blue
  HEARTBEAT_ACK: '#60a5fa',
};

export const useClusterStore = create<ClusterState>((set, get) => ({
  nodes: [],
  leader: null,
  algorithm: 'bully',
  nodeCount: 5,
  chaos: false,
  delay: 0,
  dropRate: 0,
  connected: false,
  cameraMode: 'auto-orbit',
  theme: 'day', // Light theme is DEFAULT per user request
  showHeartbeats: false,
  selectedNode: null,
  logs: [],
  activeOrbs: [],
  elections: [],
  activeTab: 'dashboard',
  filterType: 'ALL',
  showLeftPanel: false, // Hidden by default for clean, open 3D scene!
  showRightPanel: false, // Hidden by default
  showLanding: true, // Show landing page first per user request

  setConnected: (connected) => set({ connected }),

  updateSnapshot: (data) => {
    const rawNodes: NodeState[] = data.nodes || [];
    let safeLeader = data.leader || null;
    const lNode = rawNodes.find((n) => n.id === safeLeader);
    if (lNode && lNode.status === 'DEAD') {
      safeLeader = null;
    }
    set({
      nodes: rawNodes,
      leader: safeLeader,
      algorithm: data.algorithm || 'bully',
      nodeCount: data.node_count || 5,
      chaos: !!data.chaos,
      delay: data.delay || 0,
      dropRate: data.drop_rate || 0,
    });
  },

  handleConfigChange: (data) => {
    set((state) => ({
      algorithm: data.algorithm !== undefined ? data.algorithm : state.algorithm,
      nodeCount: data.node_count !== undefined ? data.node_count : state.nodeCount,
      chaos: data.chaos !== undefined ? data.chaos : state.chaos,
      delay: data.delay !== undefined ? data.delay : state.delay,
      dropRate: data.drop_rate !== undefined ? data.drop_rate : state.dropRate,
      nodes: data.nodes !== undefined ? data.nodes : state.nodes,
    }));
  },

  handleEvent: (evt) => {
    const { event_type, node_id, data, lamport, ts, leader } = evt;
    const timeStr = new Date(ts * 1000).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + Math.floor((ts % 1) * 1000).toString().padStart(3, '0');

    if (event_type === 'STATE_CHANGED' || event_type === 'LEADER_ELECTED') {
      const status: NodeStatusType = data.status;
      const leaderId = data.leader_id;

      set((state) => {
        const nextNodes = state.nodes.map((n) =>
          n.id === node_id
            ? { ...n, status: status || n.status, leader_id: leaderId !== undefined ? leaderId : n.leader_id }
            : n
        );

        let nextLeader = leader !== undefined ? leader : state.leader;
        // If current leader died, clear leader immediately!
        if (status === 'DEAD' && (state.leader === node_id || leaderId === null)) {
          nextLeader = null;
        }

        // Strict invariant: leader can NEVER be a DEAD node!
        const candLeaderNode = nextNodes.find((n) => n.id === nextLeader);
        if (candLeaderNode && candLeaderNode.status === 'DEAD') {
          nextLeader = null;
        }

        return {
          nodes: nextNodes,
          leader: nextLeader,
        };
      });

      const entry: LogEntry = {
        id: `${ts}-${Math.random()}`,
        ts,
        timeStr,
        lamport,
        from: node_id,
        to: node_id,
        type: event_type,
        text: `Node ${node_id} state ➔ ${status} ${leaderId ? `(Leader: ${leaderId})` : ''}`,
      };
      set((state) => ({ logs: [entry, ...state.logs].slice(0, 200) }));
    } else if (event_type === 'MESSAGE_SENT') {
      const mtype: string = data.type;
      const fromNode: number = data.from;
      const toNode: number = data.to;

      const color = MESSAGE_COLORS[mtype] || '#cfd8ff';
      const orb: OrbMessage = {
        id: `orb-${ts}-${Math.random()}`,
        from: fromNode,
        to: toNode,
        type: mtype,
        color,
        progress: 0,
        speed: mtype.includes('HEARTBEAT') ? 1.8 : 0.9,
        ts,
      };

      const entry: LogEntry = {
        id: `log-${ts}-${Math.random()}`,
        ts,
        timeStr,
        lamport,
        from: fromNode,
        to: toNode,
        type: mtype,
        text: `Node ${fromNode} ➔ Node ${toNode}: ${mtype} ${data.election_id ? `[${data.election_id.slice(-6)}]` : ''}`,
        election_id: data.election_id,
      };

      set((state) => {
        const isHeartbeat = mtype.includes('HEARTBEAT');
        const shouldAddOrb = !isHeartbeat || state.showHeartbeats;
        return {
          logs: [entry, ...state.logs].slice(0, 200),
          activeOrbs: shouldAddOrb ? [...state.activeOrbs, orb].slice(-40) : state.activeOrbs,
        };
      });
    }
  },

  setAlgorithm: (algorithm) => set({ algorithm }),
  setCameraMode: (cameraMode) => set({ cameraMode }),

  setTheme: (theme) => {
    set({ theme });
    if (theme === 'day') {
      document.documentElement.classList.add('theme-day');
      document.documentElement.classList.remove('theme-night');
    } else {
      document.documentElement.classList.add('theme-night');
      document.documentElement.classList.remove('theme-day');
    }
  },

  setShowHeartbeats: (showHeartbeats) => set({ showHeartbeats }),
  setSelectedNode: (selectedNode) => set({ selectedNode }),
  setActiveTab: (activeTab) => set({ activeTab }),
  setFilterType: (filterType) => set({ filterType }),
  setElections: (elections) => set({ elections }),

  addOrb: (orb) => set((state) => ({ activeOrbs: [...state.activeOrbs, orb] })),
  removeOrb: (id) => set((state) => ({ activeOrbs: state.activeOrbs.filter((o) => o.id !== id) })),
  clearLogs: () => set({ logs: [] }),

  toggleLeftPanel: () => set((state) => ({ showLeftPanel: !state.showLeftPanel })),
  toggleRightPanel: () => set((state) => ({ showRightPanel: !state.showRightPanel })),
  setLeftPanel: (showLeftPanel) => set({ showLeftPanel }),
  setRightPanel: (showRightPanel) => set({ showRightPanel }),
  setShowLanding: (showLanding) => set({ showLanding }),
}));
