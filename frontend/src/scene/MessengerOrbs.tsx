import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useClusterStore } from '../store/clusterStore';

interface MessengerOrbsProps {
  nodePositions: Map<number, [number, number, number]>;
}

export function MessengerOrbs({ nodePositions }: MessengerOrbsProps) {
  const activeOrbs = useClusterStore((s) => s.activeOrbs);

  const orbsRef = useRef<Map<string, THREE.Group>>(new Map());

  useFrame((_, delta) => {
    const expired: string[] = [];

    activeOrbs.forEach((orb) => {
      orb.progress += delta * orb.speed;

      const group = orbsRef.current.get(orb.id);
      if (group) {
        const fromPos = nodePositions.get(orb.from);
        const toPos = nodePositions.get(orb.to);

        if (fromPos && toPos) {
          const t = Math.min(1, Math.max(0, orb.progress));
          // Parabolic arc interpolation
          const x = THREE.MathUtils.lerp(fromPos[0], toPos[0], t);
          const z = THREE.MathUtils.lerp(fromPos[2], toPos[2], t);
          const baseY = THREE.MathUtils.lerp(fromPos[1] + 1.2, toPos[1] + 1.2, t);
          const arc = Math.sin(t * Math.PI) * 1.5;
          const y = baseY + arc;

          group.position.set(x, y, z);
          const scale = Math.sin(t * Math.PI);
          group.scale.setScalar(Math.max(0.001, scale));
        }
      }

      if (orb.progress >= 1) {
        expired.push(orb.id);
      }
    });

    // Batch removal to eliminate multi-render spikes within a single frame
    if (expired.length > 0) {
      useClusterStore.setState((s) => ({
        activeOrbs: s.activeOrbs.filter((o) => !expired.includes(o.id)),
      }));
    }
  });

  return (
    <group>
      {activeOrbs.map((orb) => (
        <group
          key={orb.id}
          ref={(el) => {
            if (el) orbsRef.current.set(orb.id, el);
            else orbsRef.current.delete(orb.id);
          }}
        >
          {/* Glowing messenger core orb */}
          <mesh>
            <sphereGeometry args={[0.18, 12, 12]} />
            <meshBasicMaterial color={orb.color} />
          </mesh>
          {/* Outer volumetric halo (High performance additive blending, zero dynamic lights) */}
          <mesh>
            <sphereGeometry args={[0.38, 12, 12]} />
            <meshBasicMaterial
              color={orb.color}
              transparent
              opacity={0.45}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

interface RoadsProps {
  nodePositions: Map<number, [number, number, number]>;
  algorithm: string;
}

export function Roads({ nodePositions, algorithm }: RoadsProps) {
  const pairs = Array.from(nodePositions.entries());

  const geom = useMemo(() => {
    const points: THREE.Vector3[] = [];
    if (algorithm === 'ring') {
      pairs.forEach(([id, pos], i) => {
        const nextPos = pairs[(i + 1) % pairs.length][1];
        points.push(new THREE.Vector3(pos[0], 0.04, pos[2]));
        points.push(new THREE.Vector3(nextPos[0], 0.04, nextPos[2]));
      });
    } else {
      pairs.forEach(([idA, posA], i) => {
        pairs.slice(i + 1).forEach(([idB, posB]) => {
          points.push(new THREE.Vector3(posA[0], 0.04, posA[2]));
          points.push(new THREE.Vector3(posB[0], 0.04, posB[2]));
        });
      });
    }
    return new THREE.BufferGeometry().setFromPoints(points);
  }, [pairs, algorithm]);

  return (
    <lineSegments geometry={geom}>
      <lineBasicMaterial
        color="#e8c36a"
        transparent
        opacity={algorithm === 'ring' ? 0.35 : 0.15}
      />
    </lineSegments>
  );
}
