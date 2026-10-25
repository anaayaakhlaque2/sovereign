import { useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { useClusterStore } from '../store/clusterStore';

interface CameraRigProps {
  leaderPos: [number, number, number] | null;
}

export function CameraRig({ leaderPos }: CameraRigProps) {
  const cameraMode = useClusterStore((s) => s.cameraMode);
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();

  useFrame((_, delta) => {
    if (!controlsRef.current) return;

    if (cameraMode === 'top-down') {
      camera.position.lerp(new THREE.Vector3(0, 22, 0.01), delta * 4);
      controlsRef.current.target.lerp(new THREE.Vector3(0, 0, 0), delta * 4);
      controlsRef.current.update();
    } else if (cameraMode === 'follow-election' && leaderPos) {
      const targetPos = new THREE.Vector3(
        leaderPos[0] * 1.5,
        leaderPos[1] + 5.5,
        leaderPos[2] * 1.5
      );
      camera.position.lerp(targetPos, delta * 3);
      controlsRef.current.target.lerp(new THREE.Vector3(...leaderPos), delta * 3);
      controlsRef.current.update();
    }
  });

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.06}
      autoRotate={cameraMode === 'auto-orbit'}
      autoRotateSpeed={0.8}
      maxPolarAngle={cameraMode === 'top-down' ? Math.PI / 2 : Math.PI / 2.05}
      minDistance={6}
      maxDistance={35}
    />
  );
}
