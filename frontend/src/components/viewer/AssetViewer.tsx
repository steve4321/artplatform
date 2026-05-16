import React, { useState, useEffect, Suspense, useCallback } from 'react';
import { Canvas } from '@react-three/fiber';
import { useGLTF, OrbitControls, useAnimations, Environment } from '@react-three/drei';
import * as THREE from 'three';
import { WireframeToggle } from './WireframeToggle';
import { AnimationTimeline } from './AnimationTimeline';
import { ModelInfo } from './ModelInfo';

interface ModelMesh extends THREE.Object3D {
  isMesh?: boolean;
  geometry?: THREE.BufferGeometry;
  material?: THREE.Material | THREE.Material[];
}

interface AssetViewerProps {
  modelUrl: string;
  className?: string;
  autoPlay?: boolean;
}

interface ModelContentProps {
  url: string;
  autoPlay: boolean;
  wireframe: boolean;
  showSkeleton: boolean;
  onMetadata: (data: { polyCount: number; textureCount: number; boneCount: number; fileSize: string }) => void;
}

function ModelContent({ url, autoPlay, wireframe, showSkeleton, onMetadata }: ModelContentProps) {
  const { scene, animations } = useGLTF(url);
  const { actions, names } = useAnimations(animations, scene);
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const action = names.length > 0 ? actions[names[0]] : null;

  useEffect(() => {
    if (action) {
      const clip = action.getClip();
      if (clip) {
        setDuration(clip.duration);
      }
    }
  }, [action]);

  useEffect(() => {
    let animationFrameId: number;
    let lastTime = performance.now();

    const update = () => {
      if (isPlaying && action) {
        const now = performance.now();
        const delta = (now - lastTime) / 1000;
        lastTime = now;
        setCurrentTime((prev) => {
          const next = prev + delta;
          return next % duration;
        });
      }
      animationFrameId = requestAnimationFrame(update);
    };

    if (isPlaying) {
      action?.play();
      update();
    } else {
      action?.stop();
    }

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [isPlaying, action, duration]);

  useEffect(() => {
    if (action) {
      action.time = currentTime;
    }
  }, [currentTime, action]);

  useEffect(() => {
    scene.traverse((child) => {
      if ((child as ModelMesh).isMesh) {
        const mesh = child as ModelMesh;
        if (mesh.material) {
          if (Array.isArray(mesh.material)) {
            mesh.material.forEach((mat) => {
              if ('wireframe' in mat) mat.wireframe = wireframe;
            });
          } else {
            if ('wireframe' in mesh.material) (mesh.material as THREE.MeshStandardMaterial).wireframe = wireframe;
          }
        }
      }
    });
  }, [wireframe, scene]);

  useEffect(() => {
    let polyCount = 0;
    let textureCount = 0;

    scene.traverse((child) => {
      if ((child as ModelMesh).isMesh) {
        const mesh = child as ModelMesh;
        if (mesh.geometry) {
          const position = mesh.geometry.getAttribute('position');
          if (position) {
            polyCount += position.count / 3;
          }
        }
        if (mesh.material) {
          const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          mats.forEach((mat) => {
            if ('map' in mat && mat.map) textureCount++;
            if ('normalMap' in mat && mat.normalMap) textureCount++;
            if ('roughnessMap' in mat && mat.roughnessMap) textureCount++;
            if ('metalnessMap' in mat && mat.metalnessMap) textureCount++;
          });
        }
      }
    });

    onMetadata({
      polyCount: Math.round(polyCount),
      textureCount,
      boneCount: 0,
      fileSize: 'Calculating...',
    });
  }, [scene, onMetadata]);

  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  const handleSeek = useCallback((time: number) => {
    setCurrentTime(time);
    if (action) {
      action.time = time;
    }
  }, [action]);

  useEffect(() => {
    if (autoPlay && action) {
      setIsPlaying(true);
    }
  }, [autoPlay, action]);

  const skeletonHelper = showSkeleton && scene ? <primitive object={new THREE.SkeletonHelper(scene)} /> : null;

  return (
    <>
      <primitive object={scene} />
      {skeletonHelper}
      <OrbitControls makeDefault />
      <Environment preset="studio" />
      {names.length > 0 && (
        <group position={[0, -0.5, 0]}>
          <AnimationTimeline
            isPlaying={isPlaying}
            currentTime={currentTime}
            duration={duration}
            onPlayPause={togglePlay}
            onSeek={handleSeek}
          />
        </group>
      )}
    </>
  );
}

function LoadingSpinner() {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-gray-950/80">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-gray-400 text-sm">Loading model...</p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="absolute inset-0 flex items-center justify-center bg-gray-950/80">
      <div className="flex flex-col items-center gap-4 text-center p-6">
        <svg className="w-16 h-16 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
        <p className="text-red-400 font-medium">Failed to load model</p>
        <p className="text-gray-500 text-sm max-w-xs">{message}</p>
      </div>
    </div>
  );
}

export function AssetViewer({ modelUrl, className = '', autoPlay = false }: AssetViewerProps) {
  const [wireframe, setWireframe] = useState(false);
  const [showSkeleton, setShowSkeleton] = useState(false);
  const [autoRotate, setAutoRotate] = useState(false);
  const [metadata, setMetadata] = useState({ polyCount: 0, textureCount: 0, boneCount: 0, fileSize: 'N/A' });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleMetadata = useCallback((data: typeof metadata) => {
    setMetadata(data);
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
  }, [modelUrl]);

  const handleLoad = () => {
    setIsLoading(false);
  };

  const handleError = (err: Error) => {
    setError(err.message || 'Failed to load model');
    setIsLoading(false);
  };

  return (
    <div className={`relative bg-gray-950 rounded-xl overflow-hidden ${className}`}>
      {metadata.polyCount > 0 && (
        <ModelInfo
          polyCount={metadata.polyCount}
          textureCount={metadata.textureCount}
          boneCount={metadata.boneCount}
          fileSize={metadata.fileSize}
        />
      )}

      <Canvas
        camera={{ position: [0, 1.5, 3], fov: 50 }}
        className="w-full h-full"
        onCreated={handleLoad}
      >
        <color attach="background" args={['#0a0a0f']} />
        <ambientLight intensity={0.4} />
        <directionalLight position={[5, 5, 5]} intensity={1} />
        <directionalLight position={[-5, 3, -5]} intensity={0.5} />

        <Suspense fallback={null}>
          <ErrorBoundary onError={handleError}>
            <ModelContent
              url={modelUrl}
              autoPlay={autoPlay}
              wireframe={wireframe}
              showSkeleton={showSkeleton}
              onMetadata={handleMetadata}
            />
          </ErrorBoundary>
        </Suspense>

        <OrbitControls
          autoRotate={autoRotate}
          autoRotateSpeed={2}
          enableDamping
          dampingFactor={0.05}
          minDistance={0.5}
          maxDistance={20}
        />
      </Canvas>

      {isLoading && <LoadingSpinner />}
      {error && <ErrorState message={error} />}

      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2">
        <WireframeToggle isEnabled={wireframe} onToggle={setWireframe} />
        <button
          onClick={() => setShowSkeleton(!showSkeleton)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200 ${
            showSkeleton
              ? 'bg-purple-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
          }`}
          title="Toggle skeleton visualization"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z"
            />
          </svg>
          <span className="text-sm font-medium">Skeleton</span>
        </button>
        <button
          onClick={() => setAutoRotate(!autoRotate)}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-all duration-200 ${
            autoRotate
              ? 'bg-green-600 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
          }`}
          title="Toggle auto-rotate"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span className="text-sm font-medium">Auto-Rotate</span>
        </button>
      </div>
    </div>
  );
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode; onError: (error: Error) => void },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode; onError: (error: Error) => void }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    this.props.onError(error);
  }

  render() {
    if (this.state.hasError) {
      return null;
    }
    return this.props.children;
  }
}

export default AssetViewer;