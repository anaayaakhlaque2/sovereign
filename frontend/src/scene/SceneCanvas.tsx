import { Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { useClusterStore } from '../store/clusterStore';
import { Island } from './Island';
import { Castle } from './Castle';
import { Crown } from './Crown';
import { MessengerOrbs, Roads } from './MessengerOrbs';
import { CameraRig } from './CameraRig';
import { Environment } from './Environment';

export function SceneCanvas() {
  const nodes = useClusterStore((s) => s.nodes);
  const leader = useClusterStore((s) => s.leader);
  const algorithm = useClusterStore((s) => s.algorithm);
  const theme = useClusterStore((s) => s.theme);
  const selectedNode = useClusterStore((s) => s.selectedNode);
  const setSelectedNode = useClusterStore((s) => s.setSelectedNode);

  const isNight = theme === 'night';
  const bgColor = isNight ? '#050810' : '#c8e2f8';
  const fogColor = isNight ? '#050810' : '#d7eaf9';

  // Circular layout of castles
  const nodeCount = nodes.length || 5;
  const radius = 5.8;

  const nodePositions = useMemo(() => {
    const map = new Map<number, [number, number, number]>();
    nodes.forEach((n, idx) => {
      const angle = (idx / nodeCount) * Math.PI * 2 + Math.PI / 2;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      map.set(n.id, [x, 0, z]);
    });
    return map;
  }, [nodes, nodeCount, radius]);

  // Effective leader: a leader MUST exist and be strictly ALIVE!
  const leaderNode = nodes.find((n) => n.id === leader);
  const isLeaderAlive = leaderNode && leaderNode.status !== 'DEAD';
  const effectiveLeader = isLeaderAlive ? leader : null;
  const leaderPosition = effectiveLeader ? nodePositions.get(effectiveLeader) || null : null;

  return (
    <div
      className="w-full h-full relative"
      onClick={() => setSelectedNode(null)}
    >
      <Canvas
        shadows
        camera={{ position: [0, 10, 18], fov: 50 }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      >
        <color attach="background" args={[bgColor]} />
        <fogExp2 attach="fog" args={[fogColor, isNight ? 0.024 : 0.016]} />

        <Suspense fallback={null}>
          <Environment />
          <Island radius={8.8} />
          <Roads nodePositions={nodePositions} algorithm={algorithm} />

          {/* Castles: a dead castle is NEVER leader */}
          {nodes.map((n) => {
            const pos = nodePositions.get(n.id) || [0, 0, 0];
            const isThisLeader = effectiveLeader === n.id && n.status !== 'DEAD';
            return (
              <Castle
                key={n.id}
                node={n}
                position={pos}
                isSelected={selectedNode === n.id}
                isLeader={isThisLeader}
              />
            );
          })}

          {/* Floating Crown: swoops to king if alive; ascends to kingdom center if king is dead / crown vacant */}
          <Crown targetPosition={leaderPosition} hasLeader={!!effectiveLeader} />

          {/* Messenger Orbs */}
          <MessengerOrbs nodePositions={nodePositions} />

          {/* Camera Controller */}
          <CameraRig leaderPos={leaderPosition} />
        </Suspense>
      </Canvas>
    </div>
  );
}
