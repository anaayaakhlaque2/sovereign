import { Crown, Heart, Skull, Vote, X, ShieldAlert } from 'lucide-react';
import { useClusterStore } from '../store/clusterStore';
import { killNode, reviveNode, triggerElection } from '../lib/api';

export function NodeListPanel() {
  const nodes = useClusterStore((s) => s.nodes);
  const leader = useClusterStore((s) => s.leader);
  const selectedNode = useClusterStore((s) => s.selectedNode);
  const setSelectedNode = useClusterStore((s) => s.setSelectedNode);
  const showLeftPanel = useClusterStore((s) => s.showLeftPanel);
  const toggleLeftPanel = useClusterStore((s) => s.toggleLeftPanel);
  const setLeftPanel = useClusterStore((s) => s.setLeftPanel);

  const aliveCount = nodes.filter((n) => n.status !== 'DEAD').length;

  const handleKill = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      await killNode(id);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRevive = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      await reviveNode(id);
    } catch (err) {
      console.error(err);
    }
  };

  const handleTrigger = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    try {
      await triggerElection(id);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <>
      {/* Floating Toggle Button on Left (ONLY visible when panel is closed, completely preventing overlap!) */}
      {!showLeftPanel && (
        <div className="fixed left-6 top-24 z-30 pointer-events-auto">
          <button
            onClick={toggleLeftPanel}
            className="flex items-center gap-2.5 px-4 py-2.5 rounded-2xl glass-panel shadow-lg hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
            title="Open Castle Processes Panel"
          >
            <span className="text-base">🏰</span>
            <span className="font-cinzel font-bold text-xs text-[var(--gold)] tracking-wider">
              Castles
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/40">
              {aliveCount}/{nodes.length}
            </span>
          </button>
        </div>
      )}

      {/* Slide-out Drawer Panel */}
      {showLeftPanel && (
        <aside className="fixed left-6 top-24 bottom-28 w-80 glass-panel rounded-2xl p-4 flex flex-col z-30 pointer-events-auto shadow-2xl animate-in fade-in slide-in-from-left-4 duration-200">
          {/* Panel Header with integrated title, status badge and close button (NO OVERLAP!) */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-white/10 mb-3 shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-lg">🏰</span>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-cinzel font-bold text-sm text-amber-800 dark:text-[var(--gold)] tracking-wider uppercase">
                    Kingdom Castles
                  </h2>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-500/40">
                    {aliveCount}/{nodes.length} ALIVE
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 dark:text-[var(--mute)] font-medium">Independent TCP OS Processes</span>
              </div>
            </div>
            <button
              onClick={() => setLeftPanel(false)}
              className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 text-slate-500 dark:text-[var(--mute)] hover:text-slate-900 dark:hover:text-[var(--ink)] transition-colors cursor-pointer"
              title="Close panel"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {nodes.map((n) => {
              const isSelected = selectedNode === n.id;
              const isLeader = leader === n.id;
              const isDead = n.status === 'DEAD';
              const isElecting = n.status === 'ELECTING';

              return (
                <div
                  key={n.id}
                  onClick={() => setSelectedNode(n.id)}
                  className={`p-3 rounded-xl border transition-all duration-200 cursor-pointer ${
                    isSelected
                      ? 'bg-amber-50 dark:bg-amber-500/15 border-amber-500 shadow-md ring-1 ring-amber-400'
                      : 'bg-white dark:bg-[#0c1224] border-slate-200 dark:border-white/10 hover:border-amber-400/50 shadow-sm'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`w-7 h-7 rounded-lg flex items-center justify-center font-cinzel font-bold text-xs ${
                          isLeader
                            ? 'bg-gradient-to-br from-amber-400 to-amber-500 text-slate-950 shadow-md shadow-amber-500/30'
                            : isDead
                            ? 'bg-red-100 text-red-700 dark:bg-[#2a1212] dark:text-[#ff6b3d] border border-red-300 dark:border-[#ff6b3d]/40'
                            : 'bg-slate-100 text-slate-800 dark:bg-[#151c34] dark:text-[var(--ink)] border border-slate-300 dark:border-white/10'
                        }`}
                      >
                        {isLeader ? <Crown className="w-3.5 h-3.5" /> : n.id}
                      </div>
                      <div>
                        <div className="font-bold text-xs text-slate-900 dark:text-white">Node {n.id}</div>
                        <div className="text-[10px] text-slate-500 dark:text-[var(--mute)] font-medium">Port {n.port}</div>
                      </div>
                    </div>

                    {/* Status Badge */}
                    <span
                      className={`text-[9px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                        isLeader
                          ? 'bg-amber-100 text-amber-800 border-amber-400 dark:bg-[#e8c36a]/25 dark:border-[#e8c36a] dark:text-[var(--gold)]'
                          : isElecting
                          ? 'bg-sky-100 text-sky-700 border-sky-400 dark:bg-[#6fb3ff]/25 dark:border-[#6fb3ff] dark:text-[#6fb3ff] animate-pulse'
                          : isDead
                          ? 'bg-red-100 text-red-700 border-red-300 dark:bg-[#ff6b3d]/25 dark:border-[#ff6b3d] dark:text-[#ff6b3d]'
                          : 'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-500/20 dark:border-emerald-500/50 dark:text-emerald-300'
                      }`}
                    >
                      {isLeader ? 'LEADER' : n.status}
                    </span>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-end gap-1.5 pt-2 border-t border-slate-200/60 dark:border-white/5">
                    {isDead ? (
                      <button
                        onClick={(e) => handleRevive(e, n.id)}
                        title="Revive Node"
                        className="px-2.5 py-1 rounded-md bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-500/20 dark:hover:bg-emerald-500/30 border border-emerald-300 dark:border-emerald-500/40 text-emerald-700 dark:text-emerald-300 text-[10px] font-semibold flex items-center gap-1 transition-colors cursor-pointer"
                      >
                        <Heart className="w-3 h-3" />
                        <span>Revive</span>
                      </button>
                    ) : (
                      <button
                        onClick={(e) => handleKill(e, n.id)}
                        title="Kill / Crash Node"
                        className="px-2.5 py-1 rounded-md bg-red-50 hover:bg-red-100 dark:bg-[#ff6b3d]/20 dark:hover:bg-[#ff6b3d]/30 border border-red-300 dark:border-[#ff6b3d]/40 text-red-600 dark:text-[#ff6b3d] text-[10px] font-semibold flex items-center gap-1 transition-colors cursor-pointer"
                      >
                        <Skull className="w-3 h-3" />
                        <span>Crash</span>
                      </button>
                    )}

                    <button
                      onClick={(e) => handleTrigger(e, n.id)}
                      disabled={isDead}
                      title="Trigger Election from this node"
                      className="px-2.5 py-1 rounded-md bg-sky-50 hover:bg-sky-100 dark:bg-[#6fb3ff]/20 dark:hover:bg-[#6fb3ff]/30 border border-sky-300 dark:border-[#6fb3ff]/40 text-sky-700 dark:text-[#6fb3ff] text-[10px] font-semibold flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer"
                    >
                      <Vote className="w-3 h-3" />
                      <span>Elect</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>
      )}
    </>
  );
}
