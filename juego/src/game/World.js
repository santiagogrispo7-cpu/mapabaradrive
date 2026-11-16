import * as THREE from 'three';

export function createWorld(scene, physics, RAPIER) {
  const group = new THREE.Group();
  group.name = 'Circuito provisional — no es el mapa de Baradero';
  scene.add(group);
  const obstacles = new Set();
  const cameraObstacles = [];
  const boxGeometry = new THREE.BoxGeometry(1, 1, 1);
  const materials = {
    grass: new THREE.MeshStandardMaterial({ color: '#8b9c78', roughness: 1 }),
    asphalt: new THREE.MeshStandardMaterial({ color: '#39434a', roughness: 0.95 }),
    sidewalk: new THREE.MeshStandardMaterial({ color: '#c9c5b8', roughness: 0.9 }),
    line: new THREE.MeshStandardMaterial({ color: '#eee9d7', roughness: 0.8 }),
    yellow: new THREE.MeshStandardMaterial({ color: '#edc970' }),
    dark: new THREE.MeshStandardMaterial({ color: '#243b42' }),
    glass: new THREE.MeshStandardMaterial({ color: '#547880', roughness: 0.32, metalness: 0.2 }),
    trunk: new THREE.MeshStandardMaterial({ color: '#77614a' }),
    foliage: new THREE.MeshStandardMaterial({ color: '#537c67', roughness: 1, flatShading: true }),
    orange: new THREE.MeshStandardMaterial({ color: '#e19b59' }),
  };
  function box(x, y, z, w, h, d, material, collision = false) {
    const mesh = new THREE.Mesh(boxGeometry, material);
    mesh.position.set(x, y, z);
    mesh.scale.set(w, h, d);
    mesh.castShadow = h > 0.2;
    mesh.receiveShadow = true;
    group.add(mesh);
    if (collision) {
      const collider = physics.createCollider(
        RAPIER.ColliderDesc.cuboid(w / 2, h / 2, d / 2)
          .setTranslation(x, y, z).setFriction(0.5).setRestitution(0),
      );
      obstacles.add(collider.handle);
      if (h > 2) cameraObstacles.push(mesh);
    }
    return mesh;
  }

  physics.createCollider(RAPIER.ColliderDesc.cuboid(125, 0.5, 125).setTranslation(0, -0.5, 0).setFriction(0.1));
  box(0, -0.1, 0, 250, 0.16, 250, materials.grass);

  // Dos ejes longitudinales y tres transversales. Rectángulos sin caras coplanares.
  for (const x of [-40, 40]) box(x, -0.015, 0, 12, 0.05, 180, materials.asphalt);
  for (const z of [-60, 0, 60]) {
    for (const [x, width] of [[-63, 34], [0, 68], [63, 34]]) {
      box(x, -0.015, z, width, 0.05, 12, materials.asphalt);
    }
  }

  // Pintura instanciada: una sola geometría y material para todas las marcas.
  const stripes = [];
  for (const x of [-40, 40]) {
    for (let z = -86; z <= 86; z += 7) {
      if ([-60, 0, 60].some((crossing) => Math.abs(z - crossing) < 9)) continue;
      stripes.push([x, 0.025, z, 0.16, 0.012, 3]);
    }
  }
  for (const z of [-60, 0, 60]) {
    for (let x = -76; x <= 76; x += 7) {
      if (Math.abs(Math.abs(x) - 40) < 9) continue;
      stripes.push([x, 0.025, z, 3, 0.012, 0.16]);
    }
  }
  const markings = new THREE.InstancedMesh(boxGeometry, materials.line, stripes.length);
  const dummy = new THREE.Object3D();
  stripes.forEach(([x, y, z, w, h, d], index) => {
    dummy.position.set(x, y, z);
    dummy.scale.set(w, h, d);
    dummy.updateMatrix();
    markings.setMatrixAt(index, dummy.matrix);
  });
  group.add(markings);

  const wallMaterials = ['#e7dbc7', '#d0b79a', '#cad1c5', '#668782'].map((color) =>
    new THREE.MeshStandardMaterial({ color, roughness: 0.9 }));
  const blocks = [
    [-14, 30, 24, 22, 8], [16, 30, 24, 22, 12],
    [-14, -30, 24, 22, 11], [16, -30, 24, 22, 7],
    [-66, 31, 19, 28, 10], [-66, -31, 19, 28, 7],
    [66, 31, 19, 28, 8], [66, -31, 19, 28, 13],
  ];
  const windowTransforms = [];
  blocks.forEach(([x, z, w, d, h], index) => {
    box(x, 0.12, z, w + 4, 0.24, d + 5, materials.sidewalk, true);
    box(x, h / 2 + 0.24, z, w, h, d, wallMaterials[index % wallMaterials.length], true);
    box(x, h + 0.35, z, w + 0.4, 0.25, d + 0.4, materials.line);
    for (const side of [-1, 1]) {
      for (let wx = -w / 2 + 2; wx < w / 2 - 1; wx += 4) {
        for (let wy = 2; wy < h - 1; wy += 3) {
          windowTransforms.push([x + wx, wy + 0.3, z + side * (d / 2 + 0.025)]);
        }
      }
    }
    box(x + w / 2 + 0.025, 1.6, z, 0.07, 2.8, 2.0, materials.dark);
    box(x - w / 2 - 0.025, 1.6, z, 0.07, 2.8, 2.0, materials.dark);
  });
  const windows = new THREE.InstancedMesh(boxGeometry, materials.glass, windowTransforms.length);
  windowTransforms.forEach(([x, y, z], index) => {
    dummy.position.set(x, y, z);
    dummy.scale.set(1.65, 1.3, 0.07);
    dummy.updateMatrix();
    windows.setMatrixAt(index, dummy.matrix);
  });
  windows.receiveShadow = true;
  group.add(windows);

  const leafGeometry = new THREE.IcosahedronGeometry(1, 1);
  for (const x of [-91, -51, 51, 91]) {
    for (const z of [-78, -47, -15, 15, 47, 78]) {
      box(x, 1.6, z, 0.5, 3.2, 0.5, materials.trunk, true);
      const crown = new THREE.Mesh(leafGeometry, materials.foliage);
      crown.position.set(x, 4.6, z);
      crown.scale.set(2.5, 3.1, 2.5);
      crown.castShadow = true;
      group.add(crown);
    }
  }

  // Barreras físicas delimitan el circuito y sirven para comprobar contactos.
  for (const z of [-94, 94]) {
    for (const x of [-40, 40]) {
      box(x, 0.6, z, 12, 1.2, 1, materials.sidewalk, true);
      for (let dx = -5; dx <= 5; dx += 2) box(x + dx, 0.65, z + (z > 0 ? -0.51 : 0.51), 1, 0.6, 0.04, materials.orange);
    }
  }
  for (const x of [-121, 121]) box(x, 1, 0, 1, 2, 242, materials.dark, true);
  for (const z of [-121, 121]) box(0, 1, z, 242, 2, 1, materials.dark, true);

  // Un cartel local, sin fuentes ni imágenes de Internet.
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#203b41'; ctx.fillRect(0, 0, 1024, 256);
  ctx.strokeStyle = '#c5f36b'; ctx.lineWidth = 6; ctx.strokeRect(16, 16, 992, 224);
  ctx.textAlign = 'center'; ctx.fillStyle = '#f3f5ec'; ctx.font = 'bold 94px sans-serif';
  ctx.fillText('BARA-DRIVE', 512, 125);
  ctx.fillStyle = '#c5f36b'; ctx.font = '34px sans-serif';
  ctx.fillText('CIRCUITO DE PRUEBAS  /  01', 512, 194);
  const sign = new THREE.Mesh(new THREE.PlaneGeometry(13, 3.25), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(canvas), side: THREE.DoubleSide }));
  sign.position.set(-40, 6, -86);
  group.add(sign);
  for (const x of [-47, -33]) box(x, 3, -86, 0.2, 6, 0.2, materials.dark);

  // Estacionamiento libre en el extremo sur.
  box(0, -0.015, 80, 44, 0.05, 22, materials.asphalt);
  for (let x = -20; x <= 20; x += 5) box(x, 0.025, 83, 0.12, 0.012, 8, materials.line);
  box(0, 0.025, 87, 40, 0.012, 0.12, materials.line);

  return { obstacles, cameraObstacles, group };
}
