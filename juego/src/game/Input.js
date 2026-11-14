const DRIVING_KEYS = new Set([
  'KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space',
]);

export class Input {
  constructor(onAction, isDriving) {
    this.keys = new Set();
    this.onAction = onAction;
    this.isDriving = isDriving;
    this.handleDown = (event) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (DRIVING_KEYS.has(event.code) && this.isDriving()) event.preventDefault();
      if (this.isDriving()) this.keys.add(event.code);
      if (!event.repeat && ['KeyC', 'KeyR', 'Escape'].includes(event.code)) {
        this.onAction(event.code);
      }
    };
    this.handleUp = (event) => this.keys.delete(event.code);
    window.addEventListener('keydown', this.handleDown);
    window.addEventListener('keyup', this.handleUp);
  }

  sample() {
    const has = (...codes) => codes.some((code) => this.keys.has(code));
    return {
      throttle: has('KeyW', 'ArrowUp'),
      reverse: has('KeyS', 'ArrowDown'),
      brake: has('Space'),
      steer: Number(has('KeyA', 'ArrowLeft')) - Number(has('KeyD', 'ArrowRight')),
    };
  }

  clear() { this.keys.clear(); }

  dispose() {
    window.removeEventListener('keydown', this.handleDown);
    window.removeEventListener('keyup', this.handleUp);
  }
}
