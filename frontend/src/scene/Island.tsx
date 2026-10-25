import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useClusterStore } from '../store/clusterStore';

interface IslandProps {
  radius?: number;
}

export function Island({ radius = 9.2 }: IslandProps) {
  const theme = useClusterStore((s) => s.theme);
  const isNight = theme === 'night';
  const debrisRef = useRef<THREE.Group>(null);

  // Pre-generate random tree positions around island interior
  const trees = useMemo(() => {
    const list: [number, number, number, number][] = [];
    for (let i = 0; i < 28; i++) {
      const angle = Math.random() * Math.PI * 2;
      const dist = 1.0 + Math.random() * (radius - 4.4);
      const scale = 0.75 + Math.random() * 0.5;
      list.push([Math.cos(angle) * dist, 0.35, Math.sin(angle) * dist, scale]);
    }
    return list;
  }, [radius]);

  // Floating debris / small islands orbiting the main kingdom
  const debris = useMemo(() => {
    const list: [number, number, number, number][] = [];
    for (let i = 0; i < 7; i++) {
      const a = (i / 7) * Math.PI * 2;
      const r = radius + 2.5 + Math.random() * 2.2;
      const y = -1.2 + (Math.random() - 0.5) * 2;
      const s = 0.4 + Math.random() * 0.4;
      list.push([Math.cos(a) * r, y, Math.sin(a) * r, s]);
    }
    return list;
  }, [radius]);

  useFrame((_, delta) => {
    if (debrisRef.current) {
      debrisRef.current.rotation.y += delta * 0.04;
    }
  });

  const grassColor = isNight ? '#0d1838' : '#2d6a4f';
  const grassEmissive = isNight ? '#060b1e' : '#143825';
  const rockColor = isNight ? '#080d1e' : '#475569';

  return (
    <group position={[0, -0.6, 0]}>
      {/* Top Plateau Grass Terrace */}
      <mesh receiveShadow position={[0, 0, 0]}>
        <cylinderGeometry args={[radius, radius * 0.82, 1.2, 54]} />
        <meshStandardMaterial
          color={grassColor}
          emissive={grassEmissive}
          emissiveIntensity={0.6}
          roughness={0.8}
          metalness={0.1}
          flatShading
        />
      </mesh>

      {/* Rock Strata Middle Layer */}
      <mesh receiveShadow position={[0, -0.9, 0]}>
        <cylinderGeometry args={[radius * 0.82, radius * 0.68, 1.0, 48]} />
        <meshStandardMaterial
          color={rockColor}
          roughness={0.9}
          metalness={0.15}
          flatShading
        />
      </mesh>

      {/* Floating Island Inverted Stalactite Cone Base */}
      <mesh position={[0, -5.2, 0]} rotation={[Math.PI, 0, 0]}>
        <coneGeometry args={[radius * 0.68, 8.5, 36, 2, true]} />
        <meshStandardMaterial
          color={rockColor}
          roughness={0.95}
          metalness={0.1}
          flatShading
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Golden Rune Border Ring around kingdom edge */}
      <mesh position={[0, 0.62, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <torusGeometry args={[radius, 0.065, 12, 110]} />
        <meshStandardMaterial
          color="#e8c36a"
          emissive="#ffbe3b"
          emissiveIntensity={isNight ? 0.9 : 0.6}
          roughness={0.25}
          metalness={0.85}
        />
      </mesh>

      {/* Inner Cobblestone Road Ring */}
      <mesh position={[0, 0.61, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[radius * 0.58, radius * 0.625, 72]} />
        <meshBasicMaterial
          color="#e8c36a"
          transparent
          opacity={isNight ? 0.22 : 0.4}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* Orbiting Rock Debris */}
      <group ref={debrisRef}>
        {debris.map(([x, y, z, s], idx) => (
          <mesh key={idx} position={[x, y, z]} scale={[s, s * 1.3, s]}>
            <dodecahedronGeometry args={[1, 0]} />
            <meshStandardMaterial color={rockColor} roughness={0.9} flatShading />
          </mesh>
        ))}
      </group>

      {/* Low-Poly Pine Trees */}
      {trees.map(([x, y, z, s], idx) => (
        <group key={idx} position={[x, y, z]} scale={[s, s, s]}>
          {/* Trunk */}
          <mesh position={[0, 0.4, 0]} castShadow>
            <cylinderGeometry args={[0.07, 0.12, 0.8, 5]} />
            <meshStandardMaterial color="#3e2723" roughness={0.9} />
          </mesh>
          {/* Layer 1 foliage */}
          <mesh position={[0, 1.05, 0]} castShadow>
            <coneGeometry args={[0.48, 1.1, 5]} />
            <meshStandardMaterial
              color={isNight ? '#102824' : '#1b4332'}
              emissive={isNight ? '#071614' : '#081c15'}
              roughness={0.7}
              flatShading
            />
          </mesh>
          {/* Layer 2 foliage */}
          <mesh position={[0, 1.65, 0]} castShadow>
            <coneGeometry args={[0.36, 0.95, 5]} />
            <meshStandardMaterial
              color={isNight ? '#163832' : '#2d6a4f'}
              emissive={isNight ? '#0a211d' : '#143628'}
              roughness={0.7}
              flatShading
            />
          </mesh>
          {/* Layer 3 foliage */}
          <mesh position={[0, 2.15, 0]} castShadow>
            <coneGeometry args={[0.24, 0.75, 5]} />
            <meshStandardMaterial
              color={isNight ? '#204e46' : '#40916c'}
              roughness={0.7}
              flatShading
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}
