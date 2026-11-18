import * as THREE from 'three';
import { createUI } from './ui.js';
import { createWorld } from './game/World.js';
import { createCarModel } from './game/CarModel.js';
import { Vehicle } from './game/Vehicle.js';
import { Input } from './game/Input.js';
import { Cameras } from './game/Cameras.js';
import { FIXED_STEP } from './game/config.js';
import './style.css';

const ui = createUI(document.getElementById('app'));
let disposeGame;

async function boot() {
  let state = 'menu';
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.domElement.setAttribute('aria-label', 'Vista del circuito y del automóvil');
  ui.byId('scene').appendChild(renderer.domElement);
  renderer.domElement.addEventListener('webglcontextlost', (event) => {
    event.preventDefault();
    state = 'paused';
    renderer.setAnimationLoop(null);
    ui.error(new Error('Se perdió el contexto gráfico. Cerrá otras aplicaciones 3D y volvé a intentar.'));
  });
  // Carga separada: el menú aparece antes de descargar/compilar el WASM local.
  const { default: RAPIER } = await import('@dimforge/rapier3d-compat');
  await RAPIER.init();

  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#b9d0d4');
  scene.fog = new THREE.Fog('#b9d0d4', 85, 225);
  const camera = new THREE.PerspectiveCamera(65, window.innerWidth / window.innerHeight, 0.04, 270);
  scene.add(new THREE.HemisphereLight('#e6f3ff', '#829576', 2.4));
  const sunlight = new THREE.DirectionalLight('#fff0d8', 3.1);
  sunlight.position.set(-38, 65, 25);
  sunlight.castShadow = true;
  sunlight.shadow.mapSize.set(1024, 1024);
  sunlight.shadow.camera.left = -45; sunlight.shadow.camera.right = 45;
  sunlight.shadow.camera.top = 45; sunlight.shadow.camera.bottom = -45;
  sunlight.shadow.camera.near = 1; sunlight.shadow.camera.far = 160;
  sunlight.shadow.normalBias = 0.035;
  sunlight.shadow.bias = -0.0001;
  scene.add(sunlight, sunlight.target);

  const physics = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  physics.timestep = FIXED_STEP;
  const environment = createWorld(scene, physics, RAPIER);
  const vehicle = new Vehicle(RAPIER, physics);
  const car = createCarModel();
  scene.add(car.group);
  const cameras = new Cameras(camera, car.group, environment.cameraObstacles);
  let accumulator = 0;
  let elapsed = 0;
  let previousTime;
  let collisionCooldown = 0;
  let disposed = false;

  function setState(next) {
    input.clear();
    accumulator = 0;
    previousTime = undefined;
    state = next;
    ui.state(next);
  }
  function reset() {
    vehicle.reset();
    input.clear();
    accumulator = 0;
    cameras.snap = true;
    ui.toast('Auto listo en el punto de salida.');
  }
  function toggleCamera() {
    if (state !== 'playing') return;
    ui.camera(cameras.toggle());
  }
  function pause() { if (state === 'playing') setState('paused'); }
  const input = new Input((code) => {
    if (code === 'Escape') {
      if (state === 'playing') pause();
      else if (state === 'paused') setState('playing');
    }
    if (code === 'KeyC') toggleCamera();
    if (code === 'KeyR' && state === 'playing') reset();
  }, () => state === 'playing');

  ui.byId('play').onclick = () => { vehicle.reset(); cameras.snap = true; setState('playing'); };
  ui.byId('pause-button').onclick = pause;
  ui.byId('resume').onclick = () => setState('playing');
  ui.byId('reset').onclick = () => { reset(); setState('playing'); };
  ui.byId('back-menu').onclick = () => { vehicle.reset(); setState('menu'); };
  ui.byId('camera-button').onclick = toggleCamera;
  const onBlur = () => { input.clear(); pause(); };
  const onVisibility = () => { if (document.hidden) onBlur(); };
  const onResize = () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  };
  window.addEventListener('blur', onBlur);
  document.addEventListener('visibilitychange', onVisibility);
  window.addEventListener('resize', onResize);
  // El foco permanece dentro del diálogo de pausa mientras está abierto.
  const trapFocus = (event) => {
    if (state !== 'paused' || event.key !== 'Tab') return;
    const buttons = [...ui.byId('pause').querySelectorAll('button')];
    const first = buttons[0]; const last = buttons.at(-1);
    if (event.shiftKey && document.activeElement === first) { last.focus(); event.preventDefault(); }
    else if (!event.shiftKey && document.activeElement === last) { first.focus(); event.preventDefault(); }
  };
  document.addEventListener('keydown', trapFocus);

  // La cámara del menú muestra el vehículo asentado antes de comenzar.
  for (let i = 0; i < 40; i++) {
    vehicle.beforeStep(FIXED_STEP); physics.step(); vehicle.afterStep();
  }
  scene.updateMatrixWorld(true);
  ui.ready();
  ui.state('menu');

  renderer.setAnimationLoop((time) => {
    if (disposed) return;
    try {
      const dt = previousTime === undefined ? 0 : Math.min((time - previousTime) / 1000, 0.1);
      previousTime = time;
      elapsed += dt;
      if (state === 'playing') {
        accumulator += dt;
        collisionCooldown = Math.max(0, collisionCooldown - dt);
        const controls = input.sample();
        // Máximo seis pasos por frame; una pestaña lenta no acumula física infinita.
        while (accumulator >= FIXED_STEP) {
          vehicle.beforeStep(FIXED_STEP, controls);
          physics.step();
          vehicle.afterStep();
          if (collisionCooldown === 0) {
            physics.contactPairsWith(vehicle.collider, (other) => {
              if (environment.obstacles.has(other.handle)) {
                ui.toast('Contacto con un obstáculo · Usá R si necesitás reiniciar.');
                collisionCooldown = 3;
              }
            });
          }
          accumulator -= FIXED_STEP;
        }
      }
      vehicle.syncVisual(car.group, state === 'playing' ? accumulator / FIXED_STEP : 1);
      car.animate(vehicle, state === 'playing' ? dt : 0);
      cameras.update(dt, state, elapsed);
      sunlight.position.set(car.group.position.x - 38, 65, car.group.position.z + 25);
      sunlight.target.position.copy(car.group.position);
      ui.update(vehicle);
      renderer.render(scene, camera);
    } catch (error) {
      renderer.setAnimationLoop(null);
      console.error(error);
      ui.error(error);
    }
  });

  // Solo en desarrollo: lectura de estado para diagnóstico, nunca un servidor remoto.
  if (import.meta.env.DEV) {
    window.__BARA_DRIVE__ = { snapshot: () => ({ state, position: { ...vehicle.body.translation() }, speed: vehicle.speedKmh, camera: cameras.mode }) };
  }
  disposeGame = () => {
    disposed = true;
    renderer.setAnimationLoop(null);
    input.dispose();
    window.removeEventListener('blur', onBlur);
    window.removeEventListener('resize', onResize);
    document.removeEventListener('visibilitychange', onVisibility);
    document.removeEventListener('keydown', trapFocus);
    physics.free();
    const geometries = new Set(); const materials = new Set(); const textures = new Set();
    scene.traverse((object) => {
      if (object.geometry) geometries.add(object.geometry);
      for (const material of Array.isArray(object.material) ? object.material : object.material ? [object.material] : []) {
        materials.add(material);
        if (material.map) textures.add(material.map);
      }
    });
    geometries.forEach((geometry) => geometry.dispose());
    materials.forEach((material) => material.dispose());
    textures.forEach((texture) => texture.dispose());
    renderer.dispose();
    renderer.domElement.remove();
    delete window.__BARA_DRIVE__;
  };
}

boot().catch((error) => { console.error(error); ui.error(error); });
if (import.meta.hot) import.meta.hot.dispose(() => disposeGame?.());
