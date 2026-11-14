import * as THREE from 'three';

export function createCarModel() {
  const group = new THREE.Group();
  const paint = new THREE.MeshStandardMaterial({ color: '#dce4db', roughness: 0.36, metalness: 0.35 });
  const trim = new THREE.MeshStandardMaterial({ color: '#1c2b30', roughness: 0.7 });
  const interior = new THREE.MeshStandardMaterial({ color: '#27343a', roughness: 0.95 });
  const glass = new THREE.MeshStandardMaterial({ color: '#9fc6cd', transparent: true, opacity: 0.18, roughness: 0.15, depthWrite: false, side: THREE.DoubleSide });
  const metal = new THREE.MeshStandardMaterial({ color: '#aebabc', metalness: 0.65, roughness: 0.35 });
  const red = new THREE.MeshStandardMaterial({ color: '#9b292c', emissive: '#ff332a', emissiveIntensity: 0.25 });
  const headlight = new THREE.MeshStandardMaterial({ color: '#fff3c7', emissive: '#fff3c7', emissiveIntensity: 0.4 });
  const geometry = new THREE.BoxGeometry(1, 1, 1);
  function part(w, h, d, x, y, z, material) {
    const mesh = new THREE.Mesh(geometry, material);
    mesh.scale.set(w, h, d); mesh.position.set(x, y, z);
    mesh.castShadow = true; mesh.receiveShadow = true;
    group.add(mesh);
    return mesh;
  }
  part(1.8, 0.48, 4.05, 0, 0.02, 0, paint);
  part(1.76, 0.10, 3.9, 0, -0.27, 0, trim);
  part(1.75, 0.23, 1.25, 0, 0.34, -1.36, paint);
  part(1.75, 0.24, 0.7, 0, 0.35, 1.64, paint);
  part(1.68, 0.10, 1.82, 0, 1.27, 0.20, paint);
  for (const x of [-0.79, 0.79]) {
    for (const z of [-0.68, 1.05]) part(0.08, 0.92, 0.09, x, 0.82, z, paint);
    part(0.05, 0.73, 1.64, x, 0.83, 0.20, glass);
    part(0.08, 0.8, 0.07, x, 0.82, 0.44, trim);
    part(0.21, 0.15, 0.32, x * 1.25, 0.66, -0.46, paint);
    part(0.24, 0.04, 0.04, x * 1.13, 0.25, 0.4, metal);
  }
  part(1.48, 0.71, 0.025, 0, 0.85, 1.05, glass);
  // Parabrisas frontal abierto para una cámara interior nítida y sin reflejos falsos.
  part(1.52, 0.21, 0.40, 0, 0.49, -0.55, interior);
  for (const x of [-0.39, 0.39]) {
    part(0.56, 0.20, 0.56, x, 0.18, 0.27, interior);
    part(0.56, 0.62, 0.17, x, 0.55, 0.53, interior);
    part(0.34, 0.20, 0.12, x, 0.94, 0.55, interior);
  }
  part(0.23, 0.32, 0.62, 0, 0.20, -0.08, trim);
  part(1.64, 0.13, 0.10, 0, -0.04, -2.05, trim);
  part(1.64, 0.13, 0.10, 0, -0.04, 2.05, trim);
  for (const x of [-0.65, 0.65]) {
    part(0.40, 0.14, 0.035, x, 0.18, -2.04, headlight);
    part(0.40, 0.17, 0.035, x, 0.18, 2.04, red);
  }

  const wheelGeometry = new THREE.CylinderGeometry(0.34, 0.34, 0.25, 16);
  const wheelMaterial = new THREE.MeshStandardMaterial({ color: '#182126', roughness: 0.98 });
  const rimGeometry = new THREE.CylinderGeometry(0.21, 0.21, 0.26, 12);
  const wheels = [];
  for (const z of [-1.30, 1.25]) {
    for (const x of [-0.88, 0.88]) {
      const pivot = new THREE.Group();
      pivot.position.set(x, -0.16, z);
      const spin = new THREE.Group();
      const tire = new THREE.Mesh(wheelGeometry, wheelMaterial);
      const rim = new THREE.Mesh(rimGeometry, metal);
      tire.rotation.z = Math.PI / 2; rim.rotation.z = Math.PI / 2;
      tire.castShadow = true;
      spin.add(tire, rim); pivot.add(spin); group.add(pivot);
      wheels.push({ pivot, spin, front: z < 0 });
    }
  }
  const steeringWheel = new THREE.Group();
  steeringWheel.position.set(-0.39, 0.72, -0.40);
  steeringWheel.rotation.x = -0.25;
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.17, 0.022, 8, 24), trim);
  const spoke = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.035, 0.04), metal);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.05, 12), trim);
  hub.rotation.x = Math.PI / 2;
  steeringWheel.add(ring, spoke, hub);
  group.add(steeringWheel);

  const dashboardCanvas = document.createElement('canvas');
  dashboardCanvas.width = 256; dashboardCanvas.height = 128;
  const context = dashboardCanvas.getContext('2d');
  const dashboardTexture = new THREE.CanvasTexture(dashboardCanvas);
  part(0.44, 0.24, 0.11, -0.39, 0.73, -0.66, interior);
  const dashboard = new THREE.Mesh(new THREE.PlaneGeometry(0.33, 0.16), new THREE.MeshBasicMaterial({ map: dashboardTexture }));
  dashboard.position.set(-0.39, 0.74, -0.595);
  group.add(dashboard);
  let displayedSpeed = -1;
  let spinAngle = 0;

  function animate(vehicle, dt) {
    spinAngle = (spinAngle - vehicle.signedSpeed * dt / 0.34) % (Math.PI * 2);
    wheels.forEach(({ pivot, spin, front }) => {
      pivot.rotation.y = front ? vehicle.steering : 0;
      spin.rotation.x = spinAngle;
    });
    steeringWheel.rotation.z = vehicle.steering * 2.5;
    red.emissiveIntensity = vehicle.braking ? 2.5 : 0.25;
    const speed = Math.round(vehicle.speedKmh);
    if (speed !== displayedSpeed) {
      context.fillStyle = '#10262b'; context.fillRect(0, 0, 256, 128);
      context.fillStyle = '#c5f36b'; context.textAlign = 'center'; context.font = 'bold 78px monospace';
      context.fillText(String(speed).padStart(2, '0'), 128, 82);
      context.font = '22px sans-serif'; context.fillText('km/h', 128, 114);
      dashboardTexture.needsUpdate = true;
      displayedSpeed = speed;
    }
  }
  return { group, animate };
}
