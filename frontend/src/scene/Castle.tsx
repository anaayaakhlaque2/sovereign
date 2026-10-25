import { useRef, useMemo, useEffect } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { NodeState } from '../lib/types';
import { useClusterStore } from '../store/clusterStore';

interface CastleProps {
  node: NodeState;
  position: [number, number, number];
  isSelected: boolean;
  isLeader: boolean;
}

function CastleBillboard({ id, isLeader, isDead, isNight }: { id: number; isLeader: boolean; isDead: boolean; isNight: boolean }) {
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.clearRect(0, 0, 256, 128);

    // Number text
    ctx.font = '900 82px Georgia, serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    if (isNight) {
      // Night Mode: Bright luminescent numbers with glowing aura
      ctx.fillStyle = isDead ? '#ff6b3d' : isLeader ? '#ffe3a1' : '#eef1fa';
      ctx.shadowColor = isLeader
        ? 'rgba(232, 195, 106, 0.95)'
        : isDead
        ? 'rgba(255, 107, 61, 0.9)'
        : 'rgba(111, 179, 255, 0.7)';
      ctx.shadowBlur = 16;
      ctx.fillText(String(id), 128, 52);

      if (isLeader) {
        ctx.font = 'bold 22px Georgia, serif';
        ctx.fillStyle = '#e8c36a';
        ctx.shadowBlur = 8;
        ctx.fillText('SOVEREIGN', 128, 102);
      }
    } else {
      // Light Mode (Per user request: make numbering clearly visible BLACK!)
      // Add a crisp white halo stroke so the solid black number pops with 100% clarity
      ctx.lineWidth = 7;
      ctx.strokeStyle = '#ffffff';
      ctx.shadowColor = 'rgba(255, 255, 255, 0.9)';
      ctx.shadowBlur = 8;
      ctx.strokeText(String(id), 128, 52);

      ctx.fillStyle = isDead ? '#dc2626' : '#000000';
      ctx.fillText(String(id), 128, 52);

      if (isLeader) {
        ctx.font = '900 24px Georgia, serif';
        ctx.lineWidth = 5;
        ctx.strokeStyle = '#ffffff';
        ctx.strokeText('SOVEREIGN', 128, 102);
        ctx.fillStyle = '#78350f'; // Rich dark amber/gold
        ctx.fillText('SOVEREIGN', 128, 102);
      }
    }

    const tex = new THREE.CanvasTexture(canvas);
    tex.needsUpdate = true;
    return tex;
  }, [id, isLeader, isDead, isNight]);

  useEffect(() => {
    return () => {
      texture?.dispose();
    };
  }, [texture]);

  if (!texture) return null;

  return (
    <sprite position={[0, 4.35, 0]} scale={[2.6, 1.3, 1]}>
      <spriteMaterial map={texture} transparent depthWrite={false} />
    </sprite>
  );
}

export function Castle({ node, position, isSelected, isLeader }: CastleProps) {
  const groupRef = useRef<THREE.Group>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const flagRef = useRef<THREE.Mesh>(null);

  const theme = useClusterStore((s) => s.theme);
  const isNight = theme === 'night';
  const setSelectedNode = useClusterStore((s) => s.setSelectedNode);

  const isDead = node.status === 'DEAD';
  const isElecting = node.status === 'ELECTING';

  // Corner turrets positions
  const cornerTurrets = useMemo(() => [
    [-0.55, 0.55] as [number, number],
    [0.55, 0.55] as [number, number],
    [0.55, -0.55] as [number, number],
    [-0.55, -0.55] as [number, number],
  ], []);

  // Merlons (crenellations) along parapet
  const merlons = useMemo(() => {
    const list: [number, number, number][] = [];
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      list.push([Math.cos(a) * 0.7, 2.25, Math.sin(a) * 0.7]);
    }
    return list;
  }, []);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    const t = state.clock.getElapsedTime();

    // Collapse tilt animation when dead
    const targetTilt = isDead ? 0.38 : 0;
    const targetY = position[1] + (isDead ? -0.45 : Math.sin(t * 1.5 + node.id) * 0.05);

    groupRef.current.rotation.z = THREE.MathUtils.damp(groupRef.current.rotation.z, targetTilt, 4, delta);
    groupRef.current.position.y = THREE.MathUtils.damp(groupRef.current.position.y, targetY, 4, delta);

    // Waving flag
    if (flagRef.current) {
      flagRef.current.rotation.y = Math.sin(t * 4 + node.id) * 0.35;
    }

    // Electing ring pulse
    if (ringRef.current) {
      if (isElecting) {
        const pulse = 0.6 + Math.sin(t * 8) * 0.4;
        ringRef.current.scale.setScalar(1 + pulse * 0.25);
        (ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.45 + pulse * 0.4;
      } else if (isLeader) {
        ringRef.current.scale.setScalar(1.25);
        (ringRef.current.material as THREE.MeshBasicMaterial).opacity = 0.65;
      } else {
        ringRef.current.scale.setScalar(1);
        (ringRef.current.material as THREE.MeshBasicMaterial).opacity = isDead ? 0.05 : 0.22;
      }
    }
  });

  // Realistic, well-lit color palette in both Day and Night modes
  const stoneColor = isDead
    ? '#3a1a1a'
    : isLeader
    ? isNight ? '#e2e8f0' : '#f8fafc'
    : isSelected
    ? isNight ? '#5b70aa' : '#cbd5e1'
    : isNight ? '#485c96' : '#94a3b8';

  const stoneEmissive = isDead
    ? '#4a1008'
    : isLeader
    ? isNight ? '#4a5b98' : '#e2e8f0'
    : isNight ? '#263462' : '#334155';

  const roofColor = isDead
    ? '#4a1814'
    : isLeader
    ? '#e8c36a'
    : isElecting
    ? '#ff7849'
    : isNight ? '#5b74ff' : '#1e3a8a';

  const roofEmissive = isDead
    ? '#6b180d'
    : isLeader
    ? '#ffd88a'
    : isElecting
    ? '#ff4500'
    : isNight ? '#384ee0' : '#0f172a';

  const ringColor = isDead ? '#ff3a1a' : isLeader ? '#e8c36a' : isElecting ? '#6fb3ff' : '#4a6baf';

  return (
    <group
      ref={groupRef}
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        setSelectedNode(node.id);
      }}
      onPointerOver={() => (document.body.style.cursor = 'pointer')}
      onPointerOut={() => (document.body.style.cursor = 'default')}
    >
      {/* Warm candlelight glow emanating from castle windows and towers */}
      <pointLight
        position={[0, 1.8, 0]}
        color={isDead ? '#ff3a1a' : isLeader ? '#ffe3a1' : '#ffd98c'}
        intensity={isNight ? 1.8 : 0.8}
        distance={4.8}
      />

      {/* 1. Stepped Stone Foundation Plinth */}
      <mesh position={[0, 0.12, 0]} receiveShadow>
        <cylinderGeometry args={[1.3, 1.45, 0.24, 8]} />
        <meshStandardMaterial
          color={isNight ? '#2c375c' : '#64748b'}
          roughness={0.8}
          metalness={0.15}
          flatShading
        />
      </mesh>

      {/* 2. Main Fortified Octagonal Keep Tower */}
      <mesh position={[0, 1.05, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.82, 0.95, 1.65, 8]} />
        <meshStandardMaterial
          color={stoneColor}
          emissive={stoneEmissive}
          emissiveIntensity={isNight ? 0.7 : 0.4}
          roughness={0.7}
          metalness={0.2}
          flatShading
        />
      </mesh>

      {/* 3. 4 Corner Bartizan Turrets */}
      {cornerTurrets.map(([cx, cz], idx) => (
        <group key={idx} position={[cx, 1.25, cz]}>
          <mesh castShadow>
            <cylinderGeometry args={[0.2, 0.16, 1.4, 6]} />
            <meshStandardMaterial color={stoneColor} roughness={0.7} flatShading />
          </mesh>
          <mesh position={[0, 0.85, 0]} castShadow>
            <coneGeometry args={[0.24, 0.5, 6]} />
            <meshStandardMaterial color={roofColor} emissive={roofEmissive} emissiveIntensity={0.6} flatShading />
          </mesh>
        </group>
      ))}

      {/* 4. Arched Wooden Entrance Portal with Iron Portcullis */}
      <mesh position={[0, 0.5, 0.93]}>
        <boxGeometry args={[0.38, 0.65, 0.08]} />
        <meshStandardMaterial color="#2d1b0c" roughness={0.8} />
      </mesh>
      {/* Stone Arch Frame */}
      <mesh position={[0, 0.85, 0.94]}>
        <boxGeometry args={[0.48, 0.12, 0.08]} />
        <meshStandardMaterial color="#475569" roughness={0.7} />
      </mesh>

      {/* 5. Battlements & Merlons */}
      <mesh position={[0, 2.05, 0]} castShadow>
        <cylinderGeometry args={[0.92, 0.82, 0.35, 8]} />
        <meshStandardMaterial color={stoneColor} roughness={0.7} flatShading />
      </mesh>
      {merlons.map(([mx, my, mz], idx) => (
        <mesh key={idx} position={[mx, my, mz]} castShadow>
          <boxGeometry args={[0.18, 0.22, 0.12]} />
          <meshStandardMaterial color={stoneColor} roughness={0.7} />
        </mesh>
      ))}

      {/* 6. Pointed Gothic Windows with Warm Candlelight */}
      <mesh position={[0, 1.45, 0.88]}>
        <boxGeometry args={[0.16, 0.36, 0.04]} />
        <meshBasicMaterial color={isDead ? '#330e0a' : '#fef08a'} />
      </mesh>
      <mesh position={[0.84, 1.45, 0]} rotation={[0, Math.PI / 2, 0]}>
        <boxGeometry args={[0.16, 0.36, 0.04]} />
        <meshBasicMaterial color={isDead ? '#330e0a' : '#fef08a'} />
      </mesh>
      <mesh position={[-0.84, 1.45, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <boxGeometry args={[0.16, 0.36, 0.04]} />
        <meshBasicMaterial color={isDead ? '#330e0a' : '#fef08a'} />
      </mesh>

      {/* 7. High Conical Spire Roof */}
      <mesh position={[0, 2.9, 0]} castShadow>
        <coneGeometry args={[0.78, 1.35, 8]} />
        <meshStandardMaterial
          color={roofColor}
          emissive={roofEmissive}
          emissiveIntensity={isLeader ? 1.0 : 0.65}
          roughness={0.4}
          metalness={isLeader ? 0.65 : 0.25}
          flatShading
        />
      </mesh>

      {/* 8. Spire Finial & Royal Waving Flag */}
      {!isDead && (
        <group position={[0, 3.6, 0]}>
          {/* Bronze Flagpole */}
          <mesh position={[0, 0.25, 0]}>
            <cylinderGeometry args={[0.02, 0.02, 0.55, 6]} />
            <meshStandardMaterial color="#d4af37" metalness={0.8} roughness={0.3} />
          </mesh>
          {/* Waving Fabric Banner */}
          <mesh ref={flagRef} position={[0.16, 0.38, 0]}>
            <boxGeometry args={[0.3, 0.18, 0.015]} />
            <meshStandardMaterial
              color={isLeader ? '#e8c36a' : '#3b82f6'}
              emissive={isLeader ? '#ffd88a' : '#1d4ed8'}
              emissiveIntensity={0.6}
            />
          </mesh>
        </group>
      )}

      {/* 9. Ground Aura Ring */}
      <mesh ref={ringRef} position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.35, 1.7, 40]} />
        <meshBasicMaterial
          color={ringColor}
          transparent
          opacity={0.3}
          blending={THREE.AdditiveBlending}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>

      {/* 10. Castle ID Billboard */}
      <CastleBillboard id={node.id} isLeader={isLeader} isDead={isDead} isNight={isNight} />
    </group>
  );
}
