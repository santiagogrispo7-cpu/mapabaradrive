// Metros, segundos, kilogramos. Three/Rapier: Y arriba, frente del auto -Z.
export const FIXED_STEP = 1 / 60;
export const SPAWN = { x: -40, y: 0.57, z: 40 };
export const VEHICLE = Object.freeze({
  mass: 1150,
  wheelbase: 2.55,
  engineForce: 8200,
  reverseForce: 5100,
  brakeForce: 15500,
  maxForwardSpeed: 36,
  maxReverseSpeed: 8,
  steeringAngle: 0.52,
  lateralGrip: 9,
});

export const EMPTY_INPUT = Object.freeze({ throttle: false, reverse: false, brake: false, steer: 0 });
