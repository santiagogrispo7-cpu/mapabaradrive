import * as THREE from 'three';

export class Cameras {
  constructor(camera, car, obstacles) {
    this.camera = camera;
    this.car = car;
    this.obstacles = obstacles;
    this.mode = 'exterior';
    this.snap = true;
    this.desired = new THREE.Vector3();
    this.target = new THREE.Vector3();
    this.rayOrigin = new THREE.Vector3();
    this.rayDirection = new THREE.Vector3();
    this.raycaster = new THREE.Raycaster();
    this.hits = [];
  }

  toggle() {
    this.mode = this.mode === 'exterior' ? 'interior' : 'exterior';
    this.snap = true;
    return this.mode;
  }

  update(dt, state, elapsed) {
    this.car.updateMatrixWorld(true);
    if (state === 'menu') {
      this.desired.set(-7.5 + Math.sin(elapsed * 0.12) * 0.9, 4.2, -7.3);
      this.car.localToWorld(this.desired);
      this.target.copy(this.car.position);
      this.target.y += 0.5;
      this.camera.position.copy(this.desired);
      this.camera.lookAt(this.target);
      this.snap = true;
      return;
    }
    if (this.mode === 'interior') {
      this.desired.set(-0.39, 0.96, 0.32);
      this.target.set(-0.39, 0.90, -20);
      this.car.localToWorld(this.desired);
      this.car.localToWorld(this.target);
      this.camera.position.copy(this.desired);
      this.camera.lookAt(this.target);
    } else {
      this.desired.set(0, 3.6, 8);
      this.target.set(0, 0.9, -4);
      this.car.localToWorld(this.desired);
      this.car.localToWorld(this.target);
      this.rayOrigin.copy(this.car.position);
      this.rayOrigin.y += 1;
      this.avoidWalls(this.desired);
      if (this.snap) this.camera.position.copy(this.desired);
      else this.camera.position.lerp(this.desired, 1 - Math.exp(-7 * dt));
      this.avoidWalls(this.camera.position);
      this.camera.lookAt(this.target);
    }
    this.snap = false;
  }

  avoidWalls(position) {
    this.rayDirection.subVectors(position, this.rayOrigin);
    const distance = this.rayDirection.length();
    if (distance < 0.01) return;
    this.rayDirection.normalize();
    this.raycaster.set(this.rayOrigin, this.rayDirection);
    this.raycaster.far = distance;
    this.hits.length = 0;
    this.raycaster.intersectObjects(this.obstacles, false, this.hits);
    if (this.hits.length) position.copy(this.rayOrigin).addScaledVector(this.rayDirection, Math.max(0.2, this.hits[0].distance - 0.3));
  }
}
