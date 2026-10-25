import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface CrownProps {
  targetPosition: [number, number, number] | null;
  hasLeader: boolean;
}

export function Crown({ targetPosition, hasLeader }: CrownProps) {
  const groupRef = useRef<THREE.Group>(null);
  const currentPos = useRef(new THREE.Vector3(0, 8, 0));

  // Spikes for crown rim
  const spikes = useMemo(() => {
    const list: [number, number, number][] = [];
    for (let i = 0; i < 5; i++) {
      const angle = (i / 5) * Math.PI * 2;
      list.push([Math.cos(angle) * 0.42, 0.35, Math.sin(angle) * 0.42]);
    }
    return list;
  }, []);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    const t = state.clock.getElapsedTime();

    // Determine target vector
    let target = new THREE.Vector3(0, 7.2, 0);
    if (targetPosition && hasLeader) {
      target = new THREE.Vector3(
        targetPosition[0],
        targetPosition[1] + 3.9 + Math.sin(t * 2) * 0.15,
        targetPosition[2]
      );
    } else {
      // Crown lifts cleanly off and hovers in the center sky awaiting coronation
      target = new THREE.Vector3(0, 7.2 + Math.sin(t * 1.5) * 0.35, 0);
    }

    // Smoothly fly towards target position
    currentPos.current.lerp(target, delta * 3.8);
    groupRef.current.position.copy(currentPos.current);

    // Continuous majestic rotation
    groupRef.current.rotation.y += delta * 1.2;

    // Scale slightly when vacant
    const targetScale = hasLeader ? 1.0 : 0.75;
    groupRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), delta * 4);
  });

  return (
    <group ref={groupRef} position={[0, 6, 0]}>
      {/* Crown Base Rim */}
      <mesh>
        <cylinderGeometry args={[0.42, 0.35, 0.3, 16, 1, true]} />
        <meshStandardMaterial
          color="#e8c36a"
          emissive="#ffbe3b"
          emissiveIntensity={0.8}
          roughness={0.25}
          metalness={0.8}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Golden Crown Spikes */}
      {spikes.map(([x, y, z], idx) => (
        <group key={idx} position={[x, y, z]}>
          <mesh>
            <coneGeometry args={[0.08, 0.35, 6]} />
            <meshStandardMaterial
              color="#ffe3a1"
              emissive="#e8c36a"
              emissiveIntensity={0.9}
              roughness={0.2}
              metalness={0.85}
            />
          </mesh>
          <mesh position={[0, 0.22, 0]}>
            <sphereGeometry args={[0.045, 8, 8]} />
            <meshStandardMaterial color="#ffffff" emissive="#ffdd77" emissiveIntensity={1.2} />
          </mesh>
        </group>
      ))}

      {/* Ascending Celestial Light Beam */}
      {hasLeader && (
        <mesh position={[0, -2.5, 0]}>
          <cylinderGeometry args={[0.08, 0.55, 6.0, 16, 1, true]} />
          <meshBasicMaterial
            color="#ffd88a"
            transparent
            opacity={0.16}
            blending={THREE.AdditiveBlending}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      )}

      {/* Point light illuminating the crown and sovereign tower */}
      <pointLight color="#ffe3a1" intensity={2.5} distance={7} />
    </group>
  );
}
