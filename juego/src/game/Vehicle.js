import { Quaternion, Vector3 } from 'three';
import { EMPTY_INPUT, SPAWN, VEHICLE } from './config.js';

/** Control arcade: cuerpo dinámico real y agarre lateral. Sin teletransportar el auto.
 * Roll/pitch bloqueados deliberadamente para este circuito plano; no es un modelo
 * de suspensión. Los impulsos y contactos los resuelve Rapier a 60 Hz.
 */
export class Vehicle {
  constructor(RAPIER, world) {
    this.world = world;
    this.RAPIER = RAPIER;
    this.body = world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic()
        .setTranslation(SPAWN.x, SPAWN.y, SPAWN.z)
        .setLinearDamping(0.08)
        .setAngularDamping(4)
        .setCcdEnabled(true)
        .setCanSleep(false),
    );
    this.body.setEnabledRotations(false, true, false, true);
    this.collider = world.createCollider(
      RAPIER.ColliderDesc.cuboid(0.91, 0.50, 2.04)
        .setMass(VEHICLE.mass)
        .setFriction(0.08)
        .setRestitution(0),
      this.body,
    );
    this.steering = 0;
    this.braking = false;
    this.previousPosition = new Vector3();
    this.position = new Vector3();
    this.previousRotation = new Quaternion();
    this.rotation = new Quaternion();
    this.forward = new Vector3();
    this.right = new Vector3();
    this.velocity = new Vector3();
    this.ray = new RAPIER.Ray({ x: 0, y: 0, z: 0 }, { x: 0, y: -1, z: 0 });
    this.reset();
  }

  get signedSpeed() {
    this.forward.set(0, 0, -1).applyQuaternion(this.body.rotation());
    return this.velocity.copy(this.body.linvel()).dot(this.forward);
  }

  get speedKmh() { return Math.abs(this.signedSpeed) * 3.6; }

  beforeStep(dt, input = EMPTY_INPUT) {
    this.previousPosition.copy(this.position);
    this.previousRotation.copy(this.rotation);
    const rotation = this.body.rotation();
    this.forward.set(0, 0, -1).applyQuaternion(rotation);
    this.right.set(1, 0, 0).applyQuaternion(rotation);
    this.velocity.copy(this.body.linvel());
    const speed = this.velocity.dot(this.forward);
    const sideways = this.velocity.dot(this.right);
    const position = this.body.translation();
    this.ray.origin = position;
    const grounded = this.world.castRay(
      this.ray, 0.68, true, undefined, undefined, this.collider, this.body,
    ) !== null;

    // Menor ángulo a alta velocidad para evitar giros bruscos con el teclado.
    const steeringLimit = VEHICLE.steeringAngle / (1 + Math.abs(speed) * 0.055);
    const targetSteering = input.steer * steeringLimit;
    this.steering += (targetSteering - this.steering) * (1 - Math.exp(-8 * dt));
    this.braking = input.brake || (input.reverse && speed > 0.6)
      || (input.throttle && speed < -0.6);
    if (!grounded) return;

    let drive = 0;
    if (!this.braking) {
      if (input.throttle && !input.reverse && speed < VEHICLE.maxForwardSpeed) {
        drive = VEHICLE.engineForce * Math.max(0, 1 - Math.max(0, speed) / VEHICLE.maxForwardSpeed);
      } else if (input.reverse && !input.throttle && speed > -VEHICLE.maxReverseSpeed) {
        drive = -VEHICLE.reverseForce * Math.max(0, 1 - Math.max(0, -speed) / VEHICLE.maxReverseSpeed);
      }
    }
    const mass = this.body.mass();
    const maxStopImpulse = Math.abs(speed) * mass;
    const drag = Math.min(maxStopImpulse, (95 + 0.65 * speed * speed) * dt);
    const brake = this.braking ? Math.min(maxStopImpulse, VEHICLE.brakeForce * dt) : 0;
    const longitudinal = drive * dt - Math.sign(speed) * Math.min(maxStopImpulse, drag + brake);
    const lateral = -sideways * mass * Math.min(1, VEHICLE.lateralGrip * dt);
    this.body.applyImpulse({
      x: this.forward.x * longitudinal + this.right.x * lateral,
      y: 0,
      z: this.forward.z * longitudinal + this.right.z * lateral,
    }, true);
    const yawRate = (speed / VEHICLE.wheelbase) * Math.tan(this.steering);
    const currentYaw = this.body.angvel().y;
    this.body.setAngvel({ x: 0, y: currentYaw + (yawRate - currentYaw) * Math.min(1, dt * 12), z: 0 }, true);
  }

  afterStep() {
    this.position.copy(this.body.translation());
    this.rotation.copy(this.body.rotation());
    if (this.position.y < -8 || !Number.isFinite(this.position.lengthSq())) this.reset();
  }

  syncVisual(group, alpha) {
    group.position.lerpVectors(this.previousPosition, this.position, alpha);
    group.quaternion.slerpQuaternions(this.previousRotation, this.rotation, alpha);
  }

  reset() {
    this.body.setTranslation(SPAWN, true);
    this.body.setRotation({ x: 0, y: 0, z: 0, w: 1 }, true);
    this.body.setLinvel({ x: 0, y: 0, z: 0 }, true);
    this.body.setAngvel({ x: 0, y: 0, z: 0 }, true);
    this.body.resetForces(true);
    this.body.resetTorques(true);
    this.position.copy(SPAWN);
    this.previousPosition.copy(SPAWN);
    this.rotation.identity();
    this.previousRotation.identity();
    this.steering = 0;
    this.braking = false;
  }
}
