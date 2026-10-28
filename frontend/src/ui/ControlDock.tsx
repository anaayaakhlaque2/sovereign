import { useState } from 'react';
import { Skull, Vote, Zap, Sliders, Play, RotateCcw } from 'lucide-react';
import { useClusterStore } from '../store/clusterStore';
import {
  assassinateLeader,
  setNetwork as apiSetNetwork,
  toggleChaos as apiToggleChaos,
  triggerElection,
} from '../lib/api';

export function ControlDock() {
  const chaos = useClusterStore((s) => s.chaos);
  const delay = useClusterStore((s) => s.delay);
  const dropRate = useClusterStore((s) => s.dropRate);
  const theme = useClusterStore((s) => s.theme);
  const isDay = theme === 'day';

  const [localDelay, setLocalDelay] = useState<number>(delay * 1000);
  const [localDrop, setLocalDrop] = useState<number>(dropRate * 100);
  const [showNetworkSliders, setShowNetworkSliders] = useState<boolean>(false);

  const handleAssassinate = async () => {
    try {
      await assassinateLeader();
    } catch (e) {
      console.error(e);
    }
  };

  const handleTriggerElection = async () => {
    try {
      await triggerElection();
    } catch (e) {
      console.error(e);
    }
  };

  const handleChaosToggle = async () => {
    try {
      await apiToggleChaos(!chaos);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNetworkApply = async (newDelayMs: number, newDropPercent: number) => {
    setLocalDelay(newDelayMs);
    setLocalDrop(newDropPercent);
    try {
      await apiSetNetwork(newDelayMs / 1000, newDropPercent / 100);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-30 pointer-events-auto flex flex-col items-center gap-2">
      {/* Expandable Network Fault Injection Bar */}
      {showNetworkSliders && (
        <div className="glass-dock rounded-xl px-5 py-3 flex items-center gap-6 text-xs shadow-xl animate-in fade-in slide-in-from-bottom-2">
          {/* Latency Slider */}
          <div className="flex items-center gap-3">
            <span className="text-slate-700 dark:text-[var(--mute)] font-semibold">Latency:</span>
            <input
              type="range"
              min="0"
              max="1000"
              step="50"
              value={localDelay}
              onChange={(e) => handleNetworkApply(Number(e.target.value), localDrop)}
              className="w-24 accent-[#e8c36a] cursor-pointer"
            />
            <span className="font-mono text-amber-800 dark:text-[var(--gold)] font-bold w-14">{localDelay} ms</span>
          </div>

          <div className="h-4 w-px bg-slate-300 dark:bg-white/20" />

          {/* Packet Drop Slider */}
          <div className="flex items-center gap-3">
            <span className="text-slate-700 dark:text-[var(--mute)] font-semibold">Drop Rate:</span>
            <input
              type="range"
              min="0"
              max="50"
              step="5"
              value={localDrop}
              onChange={(e) => handleNetworkApply(localDelay, Number(e.target.value))}
              className="w-24 accent-[#ff6b3d] cursor-pointer"
            />
            <span className="font-mono text-red-600 dark:text-[#ff6b3d] font-bold w-10">{localDrop}%</span>
          </div>
        </div>
      )}

      {/* Main Control Bar */}
      <div className="glass-dock rounded-2xl px-6 py-3 flex items-center gap-5 shadow-2xl">
        {/* Assassinate King */}
        <button
          onClick={handleAssassinate}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-r from-[#ff5a2a] via-[#e53935] to-[#b71c1c] text-white font-semibold text-xs shadow-lg shadow-[#ff5a2a]/30 hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
        >
          <Skull className="w-4 h-4" />
          <span>Assassinate King</span>
        </button>

        {/* Trigger Election */}
        <button
          onClick={handleTriggerElection}
          className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-gradient-to-r from-amber-400 via-amber-500 to-amber-600 text-slate-950 font-bold text-xs shadow-lg shadow-amber-500/30 hover:scale-105 active:scale-95 transition-all duration-200 cursor-pointer"
        >
          <Vote className="w-4 h-4" />
          <span>Hold Election</span>
        </button>

        {/* Chaos Mode Toggle */}
        <button
          onClick={handleChaosToggle}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-xs font-semibold border transition-all duration-200 cursor-pointer ${
            chaos
              ? 'bg-purple-600 text-white border-purple-400 shadow-lg shadow-purple-500/40 animate-pulse font-bold'
              : isDay
              ? 'bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700 shadow-sm font-semibold'
              : 'bg-[#10182f]/80 border-white/10 text-[#9aa3bd] hover:text-white'
          }`}
        >
          <Zap className="w-4 h-4 text-[#c77dff]" />
          <span>Chaos: {chaos ? 'ON' : 'OFF'}</span>
        </button>

        <div className="h-6 w-px bg-slate-300 dark:bg-white/15" />

        {/* Network Sliders Toggle */}
        <button
          onClick={() => setShowNetworkSliders(!showNetworkSliders)}
          className={`p-2 rounded-xl border transition-colors cursor-pointer ${
            showNetworkSliders
              ? 'bg-amber-400 text-slate-950 font-bold border-amber-500 shadow-sm'
              : isDay
              ? 'bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700 shadow-sm'
              : 'bg-[#0f162e]/80 border-white/10 text-[#9aa3bd] hover:text-white'
          }`}
          title="Network Delay and Drop Sliders"
        >
          <Sliders className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
