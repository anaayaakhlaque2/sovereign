import { X, Crown, Skull, Heart, Vote, Activity } from 'lucide-react';
import { useClusterStore } from '../store/clusterStore';
import { killNode, reviveNode, triggerElection } from '../lib/api';

export function NodeDetailCard() {
  const selectedNodeId = useClusterStore((s) => s.selectedNode);
  const setSelectedNode = useClusterStore((s) => s.setSelectedNode);
  const nodes = useClusterStore((s) => s.nodes);
  const leader = useClusterStore((s) => s.leader);

  if (selectedNodeId === null) return null;

  const node = nodes.find((n) => n.id === selectedNodeId);
  if (!node) return null;

  const isLeader = leader === node.id;
  const isDead = node.status === 'DEAD';

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      className="fixed top-24 left-1/2 -translate-x-1/2 z-40 glass-panel rounded-2xl p-5 w-84 shadow-2xl border border-[#e8c36a]/40 animate-in fade-in zoom-in-95 pointer-events-auto"
    >
      <div className="flex items-center justify-between pb-3 border-b border-black/10 dark:border-white/10 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 dark:bg-[#141b36] border border-[#e8c36a]/40 flex items-center justify-center font-cinzel font-bold text-sm text-[var(--gold)]">
            {node.id}
          </div>
          <div>
            <h3 className="font-cinzel font-bold text-sm text-[var(--gold)]">
              Castle Node {node.id}
            </h3>
            <span className="text-[10px] text-[var(--mute)]">OS TCP Process</span>
          </div>
        </div>

        <button
          onClick={() => setSelectedNode(null)}
          className="p-1 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 text-[var(--mute)] hover:text-[var(--ink)]"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="space-y-2 text-xs mb-4">
        <div className="flex justify-between py-1 border-b border-black/5 dark:border-white/5">
          <span className="text-[var(--mute)]">Status</span>
          <span
            className={`font-semibold uppercase ${
              isLeader
                ? 'text-[var(--gold)]'
                : node.status === 'ELECTING'
                ? 'text-[#6fb3ff]'
                : isDead
                ? 'text-[#ff6b3d]'
                : 'text-emerald-500'
            }`}
          >
            {isLeader ? 'SOVEREIGN LEADER' : node.status}
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-black/5 dark:border-white/5">
          <span className="text-[var(--mute)]">TCP Port</span>
          <span className="font-mono text-[var(--ink)]">{node.port}</span>
        </div>
        <div className="flex justify-between py-1 border-b border-black/5 dark:border-white/5">
          <span className="text-[var(--mute)]">Current Sovereign</span>
          <span className="font-semibold text-[var(--gold)]">
            {node.leader_id ? `Node ${node.leader_id}` : 'None (Electing)'}
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-black/5 dark:border-white/5">
          <span className="text-[var(--mute)]">Algorithm In Use</span>
          <span className="font-mono text-[var(--ink)] uppercase">{node.algorithm}</span>
        </div>
      </div>

      <div className="flex gap-2">
        {isDead ? (
          <button
            onClick={() => reviveNode(node.id)}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-600 dark:text-emerald-300 font-medium text-xs transition-colors"
          >
            <Heart className="w-3.5 h-3.5" />
            <span>Revive Node</span>
          </button>
        ) : (
          <button
            onClick={() => killNode(node.id)}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-[#ff6b3d]/20 hover:bg-[#ff6b3d]/30 border border-[#ff6b3d]/40 text-[#ff6b3d] font-medium text-xs transition-colors"
          >
            <Skull className="w-3.5 h-3.5" />
            <span>Crash Castle</span>
          </button>
        )}

        <button
          onClick={() => triggerElection(node.id)}
          disabled={isDead}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-[#e8c36a]/20 hover:bg-[#e8c36a]/30 border border-[#e8c36a]/40 text-[var(--gold)] font-medium text-xs disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <Vote className="w-3.5 h-3.5" />
          <span>Hold Election</span>
        </button>
      </div>
    </div>
  );
}
