'use client';

import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const CYAN = '#22d3c5';
const INDIGO = '#6769ff';
const VIOLET = '#8f5cff';

function DocumentCard() {
  const group = useRef<THREE.Group>(null);
  const lines = useMemo(
    () => [0.42, 0.3, 0.18, 0.06, -0.06, -0.18, -0.3].map((y, i) => ({ y, w: i === 0 ? 0.4 : 0.62 - (i % 3) * 0.12 })),
    [],
  );

  useFrame(({ clock, pointer }) => {
    if (!group.current) return;
    const t = clock.getElapsedTime();
    group.current.position.y = Math.sin(t * 0.9) * 0.08;
    group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, -0.35 + pointer.x * 0.35, 0.05);
    group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, 0.08 - pointer.y * 0.2, 0.05);
  });

  return (
    <group ref={group}>
      <mesh>
        <boxGeometry args={[1, 1.3, 0.04]} />
        <meshPhysicalMaterial color="#0f172a" metalness={0.2} roughness={0.15} transmission={0.6} thickness={0.4} transparent opacity={0.85} />
      </mesh>
      <mesh position={[0, 0, 0.022]}>
        <planeGeometry args={[1, 1.3]} />
        <meshBasicMaterial color={INDIGO} transparent opacity={0.08} />
      </mesh>
      {lines.map(({ y, w }, i) => (
        <mesh key={i} position={[-0.38 + w / 2, y, 0.03]}>
          <boxGeometry args={[w, 0.035, 0.01]} />
          <meshStandardMaterial
            color={i === 3 ? CYAN : '#cbd5e1'}
            emissive={i === 3 ? CYAN : '#334155'}
            emissiveIntensity={i === 3 ? 1.6 : 0.3}
          />
        </mesh>
      ))}
      <mesh position={[0, 0.06 - 0.12, 0.031]}>
        <planeGeometry args={[0.86, 0.12]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.12} />
      </mesh>
    </group>
  );
}

function ShieldCore() {
  const core = useRef<THREE.Mesh>(null);
  const ringA = useRef<THREE.Mesh>(null);
  const ringB = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (core.current) {
      core.current.rotation.x += delta * 0.25;
      core.current.rotation.y += delta * 0.35;
    }
    if (ringA.current) ringA.current.rotation.z += delta * 0.4;
    if (ringB.current) ringB.current.rotation.z -= delta * 0.25;
  });

  return (
    <group position={[0.95, 0.55, -0.4]}>
      <mesh ref={core}>
        <icosahedronGeometry args={[0.26, 1]} />
        <meshStandardMaterial color={VIOLET} emissive={VIOLET} emissiveIntensity={0.9} wireframe />
      </mesh>
      <mesh ref={ringA} rotation={[Math.PI / 2.4, 0, 0]}>
        <torusGeometry args={[0.42, 0.008, 16, 120]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.8} />
      </mesh>
      <mesh ref={ringB} rotation={[Math.PI / 1.7, 0.4, 0]}>
        <torusGeometry args={[0.52, 0.006, 16, 120]} />
        <meshBasicMaterial color={INDIGO} transparent opacity={0.7} />
      </mesh>
    </group>
  );
}

function Orbit() {
  const ref = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.3;
  });
  return (
    <group ref={ref} rotation={[0.35, 0, 0.1]}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.25, 0.004, 8, 200]} />
        <meshBasicMaterial color="#94a3b8" transparent opacity={0.25} />
      </mesh>
      {[0, 2.1, 4.2].map((a, i) => (
        <mesh key={i} position={[Math.cos(a) * 1.25, 0, Math.sin(a) * 1.25]}>
          <sphereGeometry args={[0.045, 16, 16]} />
          <meshStandardMaterial color={[CYAN, INDIGO, VIOLET][i]} emissive={[CYAN, INDIGO, VIOLET][i]} emissiveIntensity={2} />
        </mesh>
      ))}
    </group>
  );
}

function Particles({ count = 420 }: { count?: number }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    let seed = 7;
    const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < count; i++) {
      const r = 1.6 + rand() * 1.6;
      const theta = rand() * Math.PI * 2;
      const phi = Math.acos(2 * rand() - 1);
      arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6;
      arr[i * 3 + 2] = r * Math.cos(phi) - 1;
    }
    return arr;
  }, [count]);

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.04;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.018} color="#c7d2fe" transparent opacity={0.7} sizeAttenuation depthWrite={false} />
    </points>
  );
}

export default function WelcomeScene() {
  const reducedMotion =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  return (
    <Canvas
      camera={{ position: [0, 0, 3.4], fov: 42 }}
      dpr={[1, 1.75]}
      gl={{ alpha: true, antialias: true, powerPreference: 'low-power' }}
      frameloop={reducedMotion ? 'demand' : 'always'}
      style={{ background: 'transparent' }}
    >
      <ambientLight intensity={0.5} />
      <pointLight position={[2, 2, 3]} intensity={18} color={CYAN} />
      <pointLight position={[-2.5, -1, 2]} intensity={12} color={VIOLET} />
      <Particles />
      <Orbit />
      <DocumentCard />
      <ShieldCore />
    </Canvas>
  );
}
