import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { MeshComponent, MeshResponse } from "../../types/op3";

interface SceneManagerProps {
  meshData: MeshResponse | null;
  showStress?: boolean;
}

const SceneManager: React.FC<SceneManagerProps> = ({
  meshData,
  showStress = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const meshGroupRef = useRef<THREE.Group | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);

  // ---- Mount: scene, camera, renderer, lighting, animation loop -----
  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);
    scene.fog = new THREE.FogExp2(0x0d1117, 0.012);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(
      45, el.clientWidth / el.clientHeight, 0.1, 1000,
    );
    camera.position.set(30, 20, 30);
    camera.lookAt(0, -10, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    el.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, -5, 0);
    controlsRef.current = controls;

    scene.add(new THREE.AmbientLight(0x404060, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 1.0);
    dir.position.set(50, 50, 50);
    scene.add(dir);
    scene.add(new THREE.HemisphereLight(0x87ceeb, 0x8b7355, 0.3));

    scene.add(new THREE.GridHelper(100, 20, 0x444444, 0x333333));
    scene.add(new THREE.AxesHelper(8));

    const group = new THREE.Group();
    scene.add(group);
    meshGroupRef.current = group;

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      // Sea-surface bobbing
      const sea = scene.getObjectByName("sea_surface");
      if (sea) sea.position.y += Math.sin(performance.now() * 0.0007) * 0.005;
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      if (el.contains(renderer.domElement)) {
        el.removeChild(renderer.domElement);
      }
    };
  }, []);

  // ---- Update: rebuild meshes from server response ------------------
  useEffect(() => {
    const group = meshGroupRef.current;
    if (!group) return;

    // Tear down previous
    while (group.children.length > 0) {
      const child = group.children[0];
      group.remove(child);
      if ((child as THREE.Mesh).geometry) {
        (child as THREE.Mesh).geometry.dispose();
      }
      const mat = (child as THREE.Mesh).material as THREE.Material | undefined;
      if (mat) mat.dispose();
    }
    if (!meshData) return;

    Object.entries(meshData.components).forEach(([name, c]) => {
      buildComponent(group, name, c, showStress);
    });
  }, [meshData, showStress]);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%",
                                     minHeight: "400px" }} />
  );
};

function buildComponent(
  group: THREE.Group, name: string, c: MeshComponent, showStress: boolean,
) {
  if (c.type === "line") {
    const points = (c.points || []).map(
      (p) => new THREE.Vector3(p[0], p[1], p[2]),
    );
    const geom = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({
      color: new THREE.Color(...(c.color || [1, 1, 1]) as [number, number, number]),
      linewidth: c.linewidth || 1,
    });
    const line = new THREE.Line(geom, mat);
    line.name = name;
    group.add(line);
    return;
  }
  if (c.type === "water_plane") {
    const ext = c.extent || 100;
    const geom = new THREE.PlaneGeometry(ext, ext, 16, 16);
    geom.rotateX(-Math.PI / 2);
    const mat = new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(...(c.color || [0.1, 0.4, 0.8]) as [number, number, number]),
      transparent: true,
      opacity: c.opacity ?? 0.3,
      roughness: 0.1,
      metalness: 0.1,
    });
    const mesh = new THREE.Mesh(geom, mat);
    mesh.position.y = c.y_offset || 0;
    mesh.name = "sea_surface";
    group.add(mesh);
    return;
  }

  if (!c.vertices || !c.faces) return;
  const verts = new Float32Array(c.vertices.flat());
  const idx = new Uint32Array(c.faces.flat());
  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.BufferAttribute(verts, 3));
  geom.setIndex(new THREE.BufferAttribute(idx, 1));
  geom.computeVertexNormals();

  let material: THREE.Material;
  if (c.colors && showStress) {
    const cols = new Float32Array(c.colors.flat());
    geom.setAttribute("color", new THREE.BufferAttribute(cols, 3));
    material = new THREE.MeshPhongMaterial({
      vertexColors: true, side: THREE.DoubleSide,
    });
  } else {
    material = defaultMaterial(name);
  }

  const mesh = new THREE.Mesh(geom, material);
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
}

function defaultMaterial(name: string): THREE.Material {
  const palette: Record<string, [number, number, number, number, number]> = {
    // [r, g, b, roughness, metalness]
    lid:           [0x88 / 255, 0x88 / 255, 0x99 / 255, 0.4, 0.8],
    skirt_outer:   [0x77 / 255, 0x88 / 255, 0x99 / 255, 0.3, 0.9],
    anchor_body:   [0xb8 / 255, 0x73 / 255, 0x33 / 255, 0.3, 0.7],
    anchor_lid:    [0x88 / 255, 0x88 / 255, 0x99 / 255, 0.4, 0.8],
    padeye:        [1.0,        0.27,       0.27,       0.2, 0.5],
    soil_surface:  [0x8b / 255, 0x73 / 255, 0x55 / 255, 0.95, 0.0],
    scour_cavity:  [0x6b / 255, 0x53 / 255, 0x35 / 255, 0.95, 0.0],
    tower:         [0xdd / 255, 0xdd / 255, 0xdd / 255, 0.2, 0.8],
    nacelle:       [0xee / 255, 0xee / 255, 0xee / 255, 0.3, 0.5],
  };
  for (const [k, v] of Object.entries(palette)) {
    if (name.includes(k)) {
      return new THREE.MeshPhysicalMaterial({
        color: new THREE.Color(v[0], v[1], v[2]),
        roughness: v[3], metalness: v[4],
        side: THREE.DoubleSide,
      });
    }
  }
  return new THREE.MeshPhysicalMaterial({
    color: 0x999999, roughness: 0.5, metalness: 0.3, side: THREE.DoubleSide,
  });
}

export default SceneManager;
