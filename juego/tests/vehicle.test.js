import { test } from 'node:test';
import assert from 'node:assert/strict';
import RAPIER from '@dimforge/rapier3d-compat';
import { Vehicle } from '../src/game/Vehicle.js';
import { EMPTY_INPUT, FIXED_STEP, SPAWN } from '../src/game/config.js';

await RAPIER.init();

function fixture(t) {
  const world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  world.timestep = FIXED_STEP;
  world.createCollider(RAPIER.ColliderDesc.cuboid(500, 0.5, 500).setTranslation(0, -0.5, 0).setFriction(0.1));
  const car = new Vehicle(RAPIER, world);
  t.after(() => world.free());
  const step = (seconds, controls = {}) => {
    const input = { ...EMPTY_INPUT, ...controls };
    for (let i = 0; i < Math.round(seconds / FIXED_STEP); i++) {
      car.beforeStep(FIXED_STEP, input);
      world.step();
      car.afterStep();
    }
  };
  step(1);
  return { world, car, step };
}

test('el auto se apoya en el suelo y acelera hacia su frente (-Z)', (t) => {
  const { car, step } = fixture(t);
  assert.ok(car.position.y > 0.45 && car.position.y < 0.6);
  step(3, { throttle: true });
  assert.ok(car.signedSpeed > 8, `velocidad ${car.signedSpeed}`);
  assert.ok(car.position.z < SPAWN.z - 12);
  assert.ok(Math.abs(car.position.x - SPAWN.x) < 0.1);
});

test('Espacio detiene el auto sin activar marcha atrás', (t) => {
  const { car, step } = fixture(t);
  step(3, { throttle: true });
  step(3, { brake: true });
  assert.ok(Math.abs(car.signedSpeed) < 0.1);
  assert.ok(car.position.y > 0.4);
});

test('S primero frena y luego permite retroceder; W vuelve a avanzar', (t) => {
  const { car, step } = fixture(t);
  step(2, { throttle: true });
  const forwardSpeed = car.signedSpeed;
  step(0.3, { reverse: true });
  assert.ok(car.signedSpeed < forwardSpeed && car.signedSpeed > 0);
  step(4, { reverse: true });
  assert.ok(car.signedSpeed < -2);
  step(3, { throttle: true });
  assert.ok(car.signedSpeed > 2);
});

test('la dirección cambia el rumbo y el agarre mantiene el auto estable', (t) => {
  const { car, step } = fixture(t);
  step(1.5, { throttle: true });
  step(2, { throttle: true, steer: 1 });
  assert.ok(car.position.x < SPAWN.x - 2, `posición X ${car.position.x}`);
  assert.ok(Math.abs(car.rotation.y) > 0.1);
  assert.ok(Math.abs(car.rotation.x) < 0.001 && Math.abs(car.rotation.z) < 0.001);
});

test('un obstáculo sólido detiene el auto incluso manteniendo acelerador', (t) => {
  const { world, car, step } = fixture(t);
  const wall = world.createCollider(RAPIER.ColliderDesc.cuboid(30, 3, 0.5).setTranslation(SPAWN.x, 3, 8));
  step(9, { throttle: true });
  assert.ok(car.position.z > 10, `atravesó el muro: Z=${car.position.z}`);
  assert.ok(car.speedKmh < 1, `no se detuvo: ${car.speedKmh}`);
  let contact = false;
  world.contactPairsWith(car.collider, (other) => { if (other.handle === wall.handle) contact = true; });
  assert.ok(contact, 'Rapier no registró contacto con el muro');
});

test('reiniciar limpia movimiento, giro y transformación', (t) => {
  const { car, step } = fixture(t);
  step(2, { throttle: true, steer: -1 });
  car.reset();
  assert.ok(Math.abs(car.position.x - SPAWN.x) < 1e-5);
  assert.ok(Math.abs(car.position.z - SPAWN.z) < 1e-5);
  assert.equal(car.speedKmh, 0);
  assert.equal(car.steering, 0);
  assert.equal(car.rotation.w, 1);
  step(1);
  assert.ok(Math.abs(car.position.z - SPAWN.z) < 0.02);
});
