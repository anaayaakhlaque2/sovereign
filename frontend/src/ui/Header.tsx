import { Crown, Sun, Moon, Radio, BookOpen } from 'lucide-react';
import { useClusterStore } from '../store/clusterStore';
import { setAlgorithm as apiSetAlgorithm, triggerElection } from '../lib/api';
import { ActiveTabType, AlgorithmType, CameraMode } from '../lib/types';

export function Header() {
  const nodes = useClusterStore((s) => s.nodes);
  const leader = useClusterStore((s) => s.leader);
  const agreed = useClusterStore((s) => s.agreed);
  const algorithm = useClusterStore((s) => s.algorithm);
  const setStoreAlgorithm = useClusterStore((s) => s.setAlgorithm);
  const connected = useClusterStore((s) => s.connected);
  const cameraMode = useClusterStore((s) => s.cameraMode);
  const setCameraMode = useClusterStore((s) => s.setCameraMode);
  const theme = useClusterStore((s) => s.theme);
  const setTheme = useClusterStore((s) => s.setTheme);
  const activeTab = useClusterStore((s) => s.activeTab);
  const setActiveTab = useClusterStore((s) => s.setActiveTab);
  const showHeartbeats = useClusterStore((s) => s.showHeartbeats);
  const setShowHeartbeats = useClusterStore((s) => s.setShowHeartbeats);
  const setShowLanding = useClusterStore((s) => s.setShowLanding);

  const leaderNode = nodes.find((n) => n.id === leader);
  const isLeaderAlive = leaderNode && leaderNode.status !== 'DEAD';
  const effectiveLeader = (agreed && isLeaderAlive) ? leader : null;

  const handleAlgorithmChange = async (algo: AlgorithmType) => {
    // 1. Instantly update store for immediate UI response
    setStoreAlgorithm(algo);
    // 2. Transmit to backend cluster and elect under new algorithm every time
    try {
      await apiSetAlgorithm(algo);
      await triggerElection();
    } catch (e) {
      console.error('Failed to set algorithm:', e);
    }
  };

  const isDay = theme === 'day';

  return (
    <header className="fixed top-0 left-0 right-0 z-30 flex items-center justify-between px-6 py-3.5 bg-gradient-to-b from-[var(--bg)] via-[var(--bg)]/80 to-transparent pointer-events-auto transition-colors duration-300">
      {/* Brand & Crest */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#ffe3a1] via-[#e8c36a] to-[#996b1b] p-0.5 shadow-lg shadow-[#e8c36a]/30 flex items-center justify-center">
          <div className="w-full h-full bg-[#0a1022] rounded-[10px] flex items-center justify-center">
            <Crown className="w-5 h-5 text-[#ffe3a1]" />
          </div>
        </div>
        <div>
          <span className="font-cinzel font-bold text-xl tracking-[0.18em] text-[var(--gold)] drop-shadow-[0_2px_10px_rgba(232,195,106,0.3)]">
            SOVEREIGN
          </span>
          <div className="text-[10px] tracking-wider text-[var(--mute)] uppercase font-semibold">
            Distributed Leader Election
          </div>
        </div>
      </div>

      {/* Center: Current King Banner & Algorithm Switcher */}
      <div className="flex items-center gap-4">
        {/* Sovereign Leader Status Pill */}
        <div className="flex items-center gap-2.5 px-4 py-1.5 rounded-full glass-panel shadow-md">
          <div className={`w-2.5 h-2.5 rounded-full ${effectiveLeader ? 'bg-amber-500 animate-pulse shadow-[0_0_8px_rgba(245,158,11,0.8)]' : 'bg-red-500 animate-ping'}`} />
          <span className="text-xs uppercase tracking-wider text-slate-600 dark:text-[var(--mute)] font-medium">Sovereign:</span>
          <span className="font-cinzel font-bold text-sm text-amber-800 dark:text-[var(--gold)]">
            {effectiveLeader ? `Node ${effectiveLeader}` : 'Electing...'}
          </span>
        </div>

        {/* Algorithm Switcher */}
        <div className="flex p-1 rounded-full glass-panel">
          <button
            type="button"
            onClick={() => handleAlgorithmChange('bully')}
            className={`px-4 py-1.5 text-xs font-semibold rounded-full transition-all duration-200 cursor-pointer ${
              algorithm === 'bully'
                ? 'bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 shadow-md font-bold scale-[1.02]'
                : 'text-slate-600 dark:text-[var(--mute)] hover:text-slate-950 dark:hover:text-[var(--ink)]'
            }`}
          >
            Bully Algorithm
          </button>
          <button
            type="button"
            onClick={() => handleAlgorithmChange('ring')}
            className={`px-4 py-1.5 text-xs font-semibold rounded-full transition-all duration-200 cursor-pointer ${
              algorithm === 'ring'
                ? 'bg-gradient-to-r from-amber-400 to-amber-500 text-slate-950 shadow-md font-bold scale-[1.02]'
                : 'text-slate-600 dark:text-[var(--mute)] hover:text-slate-950 dark:hover:text-[var(--ink)]'
            }`}
          >
            Ring Algorithm
          </button>
        </div>

        {/* Navigation Tabs (Kingdom, Analytics, Replay + 3D Story) */}
        <div className="flex items-center gap-1 glass-panel rounded-full p-1 text-xs font-medium">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`px-3.5 py-1 rounded-full transition-all cursor-pointer ${
              activeTab === 'dashboard'
                ? isDay ? 'bg-amber-400 text-slate-950 font-bold shadow-sm' : 'bg-white/20 text-white font-bold'
                : 'text-slate-600 dark:text-[var(--mute)] hover:text-slate-950 dark:hover:text-[var(--ink)] font-medium'
            }`}
          >
            Kingdom
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`px-3.5 py-1 rounded-full transition-all cursor-pointer ${
              activeTab === 'analytics'
                ? isDay ? 'bg-amber-400 text-slate-950 font-bold shadow-sm' : 'bg-white/20 text-white font-bold'
                : 'text-slate-600 dark:text-[var(--mute)] hover:text-slate-950 dark:hover:text-[var(--ink)] font-medium'
            }`}
          >
            Analytics
          </button>
          <button
            onClick={() => setActiveTab('replay')}
            className={`px-3.5 py-1 rounded-full transition-all cursor-pointer ${
              activeTab === 'replay'
                ? isDay ? 'bg-amber-400 text-slate-950 font-bold shadow-sm' : 'bg-white/20 text-white font-bold'
                : 'text-slate-600 dark:text-[var(--mute)] hover:text-slate-950 dark:hover:text-[var(--ink)] font-medium'
            }`}
          >
            Replay
          </button>

          <div className="h-4 w-px bg-slate-300 dark:bg-white/20 mx-0.5" />

          {/* 3D Story / Landing Page button */}
          <button
            onClick={() => setShowLanding(true)}
            title="View 3D Story & Architecture Landing Page"
            className="flex items-center gap-1 px-3 py-1 rounded-full text-slate-600 dark:text-[var(--mute)] hover:text-amber-700 dark:hover:text-white transition-all cursor-pointer font-medium"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Story</span>
          </button>
        </div>
      </div>

      {/* Right Controls: Camera, Theme, Heartbeats, Connection */}
      <div className="flex items-center gap-2.5">
        {/* Camera Mode Selector */}
        <select
          value={cameraMode}
          onChange={(e) => setCameraMode(e.target.value as CameraMode)}
          className="glass-panel text-xs text-[var(--ink)] rounded-full px-3 py-1.5 outline-none hover:border-[var(--gold)] cursor-pointer"
        >
          <option value="auto-orbit" className="bg-white dark:bg-[#0b1020] text-slate-800 dark:text-white">Auto Orbit</option>
          <option value="orbit" className="bg-white dark:bg-[#0b1020] text-slate-800 dark:text-white">Free Orbit</option>
          <option value="follow-election" className="bg-white dark:bg-[#0b1020] text-slate-800 dark:text-white">Follow Sovereign</option>
          <option value="top-down" className="bg-white dark:bg-[#0b1020] text-slate-800 dark:text-white">Top-Down Diagram</option>
        </select>

        {/* Heartbeats Toggle */}
        <button
          onClick={() => setShowHeartbeats(!showHeartbeats)}
          title={showHeartbeats ? 'Hide Heartbeat particles' : 'Show Heartbeat particles'}
          className={`p-2 rounded-full border transition-all ${
            showHeartbeats
              ? 'bg-[#6fb3ff]/20 border-[#6fb3ff] text-[#6fb3ff]'
              : 'glass-panel text-[var(--mute)] hover:text-[var(--ink)]'
          }`}
        >
          <Radio className="w-4 h-4" />
        </button>

        {/* Theme Toggle (Light / Dark) */}
        <button
          onClick={() => setTheme(isDay ? 'night' : 'day')}
          title={isDay ? 'Switch to Dark Royal Mode' : 'Switch to Light Day Mode'}
          className="p-2 rounded-full glass-panel text-[var(--gold)] hover:scale-105 active:scale-95 transition-all"
        >
          {isDay ? <Sun className="w-4 h-4 text-[#b48312]" /> : <Moon className="w-4 h-4 text-[#ffe3a1]" />}
        </button>

        {/* Connection status indicator */}
        <div
          title={connected ? 'WebSocket connected to cluster' : 'Reconnecting to Gateway...'}
          className="flex items-center gap-1.5 px-3 py-1 rounded-full glass-panel text-xs"
        >
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-rose-500 animate-pulse'}`} />
          <span className="text-[11px] text-[var(--mute)]">{connected ? 'Live' : 'Offline'}</span>
        </div>
      </div>
    </header>
  );
}
