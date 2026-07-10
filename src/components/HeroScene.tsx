import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useTheme } from "./ThemeProvider.jsx";

function BlueprintEdges({ color }: { color: string }) {
  const geometry = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(3.35, 4.7, 0.08)), []);
  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color={color} transparent opacity={0.8} />
    </lineSegments>
  );
}

function DocumentMonolith({ light }: { light: boolean }) {
  const sculpture = useRef<THREE.Group>(null);
  const scanner = useRef<THREE.Mesh>(null);
  const paper = light ? "#fefdf9" : "#d9d1c4";
  const graphite = light ? "#262421" : "#312e2a";
  const line = light ? "#282522" : "#eee8dc";

  useFrame((state, delta) => {
    if (sculpture.current) {
      sculpture.current.rotation.y += delta * 0.055;
      sculpture.current.rotation.x = -0.08 + Math.sin(state.clock.elapsedTime * 0.22) * 0.025;
    }
    if (scanner.current) {
      scanner.current.position.y = Math.sin(state.clock.elapsedTime * 0.62) * 2.05;
    }
  });

  return (
    <group ref={sculpture} rotation={[-0.08, -0.4, 0.025]}>
      <mesh position={[0.42, -0.35, -0.62]}>
        <boxGeometry args={[3.55, 4.95, 0.62]} />
        <meshStandardMaterial color={graphite} roughness={0.72} metalness={0.16} />
      </mesh>

      {[0, 1, 2, 3, 4].map((page) => (
        <group key={page} position={[page * -0.18, page * 0.09, page * 0.22]}>
          <mesh>
            <boxGeometry args={[3.35, 4.7, 0.08]} />
            <meshStandardMaterial color={paper} roughness={0.86} metalness={0.02} />
          </mesh>
          <BlueprintEdges color={page === 0 ? "#b7472f" : line} />
        </group>
      ))}

      {[1.25, 0.72, 0.18, -0.36, -0.9].map((y, index) => (
        <mesh key={y} position={[-0.35, y, 0.93]}>
          <boxGeometry args={[index === 4 ? 1.45 : 2.18 - index * 0.08, 0.035, 0.018]} />
          <meshBasicMaterial color={index === 2 ? "#3a7dff" : line} transparent opacity={index === 2 ? 1 : 0.58} />
        </mesh>
      ))}

      <mesh ref={scanner} position={[0, -1.8, 1.02]}>
        <boxGeometry args={[3.75, 0.035, 0.02]} />
        <meshBasicMaterial color="#c9ff47" />
      </mesh>

      <group position={[-2.35, 0, 0]}>
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[0.025, 6.2, 0.025]} />
          <meshBasicMaterial color="#3a7dff" transparent opacity={0.7} />
        </mesh>
        {[-2.6, -1.3, 0, 1.3, 2.6].map((y) => (
          <mesh key={y} position={[0, y, 0]}>
            <boxGeometry args={[0.26, 0.018, 0.018]} />
            <meshBasicMaterial color="#3a7dff" />
          </mesh>
        ))}
      </group>
    </group>
  );
}

export default function HeroScene() {
  const { theme } = useTheme();
  const light = theme === "light";

  return (
    <div className="hero-scene" aria-hidden="true">
      <Canvas
        camera={{ position: [0, 0.1, 8], fov: 34 }}
        dpr={[1, 1.5]}
        gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
      >
        <ambientLight intensity={light ? 2.5 : 1.45} />
        <directionalLight position={[4, 6, 5]} intensity={light ? 3.2 : 2.6} color={light ? "#fffdf6" : "#f1ddc7"} />
        <directionalLight position={[-5, -2, 3]} intensity={light ? 1.2 : 1.8} color="#3a7dff" />
        <DocumentMonolith light={light} />
      </Canvas>
    </div>
  );
}
