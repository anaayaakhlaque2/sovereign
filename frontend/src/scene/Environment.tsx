import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useClusterStore } from '../store/clusterStore';

export function Environment() {
  const theme = useClusterStore((s) => s.theme);
  const isNight = theme === 'night';

  const starsRef = useRef<THREE.Points>(null);
  const firefliesRef = useRef<THREE.Points>(null);
  const cloudsRef = useRef<THREE.Group>(null);

  // Generate star field
  const starPositions = useMemo(() => {
    const coords = new Float32Array(2200 * 3);
    for (let i = 0; i < 2200; i++) {
      const radius = 60 + Math.random() * 80;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      coords[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      coords[i * 3 + 1] = radius * Math.cos(phi);
      coords[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    }
    return coords;
  }, []);

  // Generate fireflies
  const fireflyCount = 90;
  const fireflyPositions = useMemo(() => {
    const coords = new Float32Array(fireflyCount * 3);
    for (let i = 0; i < fireflyCount; i++) {
      coords[i * 3] = (Math.random() - 0.5) * 18;
      coords[i * 3 + 1] = 0.5 + Math.random() * 5.0;
      coords[i * 3 + 2] = (Math.random() - 0.5) * 18;
    }
    return coords;
  }, []);

  // Low poly drifting clouds for Day mode
  const clouds = useMemo(() => {
    const list: [number, number, number, number][] = [];
    for (let i = 0; i < 9; i++) {
      const angle = (i / 9) * Math.PI * 2;
      const r = 18 + Math.random() * 10;
      const y = 8 + Math.random() * 6;
      list.push([Math.cos(angle) * r, y, Math.sin(angle) * r, 1.2 + Math.random() * 1.5]);
    }
    return list;
  }, []);

  useFrame((_, delta) => {
    if (starsRef.current && isNight) {
      starsRef.current.rotation.y += delta * 0.015;
    }
    if (firefliesRef.current) {
      const pos = firefliesRef.current.geometry.attributes.position;
      for (let i = 0; i < fireflyCount; i++) {
        let y = pos.getY(i) + delta * (0.2 + (i % 5) * 0.06);
        if (y > 6.0) y = 0.5;
        pos.setY(i, y);
      }
      pos.needsUpdate = true;
    }
    if (cloudsRef.current) {
      cloudsRef.current.rotation.y += delta * 0.02;
    }
  });

  return (
    <group>
      {/* Background Starfield (Visible at Night) */}
      {isNight && (
        <points ref={starsRef}>
          <bufferGeometry>
            <bufferAttribute
              attach="attributes-position"
              args={[starPositions, 3]}
            />
          </bufferGeometry>
          <pointsMaterial
            size={0.65}
            color="#cfd8ff"
            transparent
            opacity={0.85}
            sizeAttenuation
          />
        </points>
      )}

      {/* Floating Fireflies */}
      <points ref={firefliesRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            args={[fireflyPositions, 3]}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.14}
          color={isNight ? '#ffe3a1' : '#f59e0b'}
          transparent
          opacity={isNight ? 0.8 : 0.4}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>

      {/* Drifting Clouds (Visible in Day) */}
      {!isNight && (
        <group ref={cloudsRef}>
          {clouds.map(([x, y, z, s], idx) => (
            <group key={idx} position={[x, y, z]} scale={[s, s * 0.6, s]}>
              <mesh position={[0, 0, 0]}>
                <sphereGeometry args={[1.4, 7, 7]} />
                <meshStandardMaterial color="#ffffff" roughness={0.9} flatShading />
              </mesh>
              <mesh position={[1.1, -0.2, 0]}>
                <sphereGeometry args={[1.0, 6, 6]} />
                <meshStandardMaterial color="#f0f7ff" roughness={0.9} flatShading />
              </mesh>
              <mesh position={[-1.0, -0.2, 0.2]}>
                <sphereGeometry args={[1.0, 6, 6]} />
                <meshStandardMaterial color="#f0f7ff" roughness={0.9} flatShading />
              </mesh>
            </group>
          ))}
        </group>
      )}

      {/* Sun / Moon Lighting */}
      <ambientLight
        color={isNight ? '#7888bb' : '#e0e7ff'}
        intensity={isNight ? 1.25 : 1.45}
      />

      <directionalLight
        position={isNight ? [16, 26, 16] : [20, 28, 15]}
        intensity={isNight ? 2.4 : 2.8}
        color={isNight ? '#fff2d4' : '#fff8ea'}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-bias={-0.0001}
      />

      {/* Main Overhead Spotlight for All Castles (Requested by user - no shadow map to preserve 60 FPS) */}
      <spotLight
        position={[0, 24, 0]}
        target-position={[0, 0, 0]}
        angle={0.78}
        penumbra={0.7}
        intensity={isNight ? 4.5 : 2.0}
        color={isNight ? '#ffe9b8' : '#ffffff'}
      />

      {/* Cross-Angled Perimeter Spotlights for Castles in Night Theme */}
      {isNight && (
        <>
          <spotLight
            position={[12, 18, 12]}
            angle={0.75}
            penumbra={0.8}
            intensity={3.2}
            color="#ffe2a3"
          />
          <spotLight
            position={[-12, 18, -12]}
            angle={0.75}
            penumbra={0.8}
            intensity={2.8}
            color="#8ab4f8"
          />
          <spotLight
            position={[0, 16, -16]}
            angle={0.75}
            penumbra={0.8}
            intensity={2.6}
            color="#ffd98c"
          />
        </>
      )}

      {/* Cool Rim Lighting */}
      <pointLight
        position={[-15, 8, -15]}
        color={isNight ? '#6fb3ff' : '#93c5fd'}
        intensity={isNight ? 1.6 : 1.0}
        distance={60}
      />

      {/* Warm Kingdom Core Light */}
      <pointLight
        position={[0, 5, 0]}
        color={isNight ? '#ffd88a' : '#fef3c7'}
        intensity={isNight ? 1.4 : 0.8}
        distance={30}
      />
    </group>
  );
}
