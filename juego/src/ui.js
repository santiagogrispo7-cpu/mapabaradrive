const roadIcon = `<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 27 12 5h8l5 22H7Z" fill="currentColor"/><path d="M16 8v5m0 4v5" stroke="#14272b" stroke-width="2"/></svg>`;

export function createUI(root) {
  root.innerHTML = `
    <div id="scene" aria-label="Escenario 3D de conducción"></div>
    <section id="menu" class="menu" aria-labelledby="menu-title">
      <header class="menu-header">
        <a class="brand" href="#" aria-label="BARA-DRIVE, inicio">${roadIcon}<span>BARA<span class="brand-dash">—</span>DRIVE</span></a>
        <span class="build-tag"><i></i> PROTOTIPO JUGABLE <b>0.1</b></span>
      </header>
      <div class="menu-content">
        <div class="eyebrow"><span class="tiny-line"></span> BARADERO, BUENOS AIRES</div>
        <h1 id="menu-title">Tu próximo<br>recorrido<br><em>empieza acá.</em></h1>
        <p class="intro">Tomá el volante. Conocé el auto.<br>Una nueva forma de recorrer nuestra ciudad.</p>
        <button id="play" class="button primary" disabled><span id="play-label">PREPARANDO MOTOR…</span><span aria-hidden="true">↗</span></button>
        <p id="loading-label" class="loading-status" role="status">Cargando escenario y física local</p>
        <div class="scenario-note"><span class="note-symbol">01</span><p><strong>Circuito de pruebas</strong><br>Escenario provisional · El mapa real llegará en la próxima etapa.</p></div>
      </div>
      <aside class="controls-card" aria-label="Controles del vehículo">
        <div class="card-heading"><span>ANTES DE SALIR</span><span class="pill">TECLADO</span></div>
        <h2>Todo bajo control.</h2>
        <div class="control-row"><span>Acelerar</span><span><kbd>W</kbd> <small>/</small> <kbd>↑</kbd></span></div>
        <div class="control-row"><span>Frenar / marcha atrás</span><span><kbd>S</kbd> <small>/</small> <kbd>↓</kbd></span></div>
        <div class="control-row"><span>Dirección</span><span><kbd>A</kbd> <kbd>D</kbd> <small>/</small> <kbd>←</kbd> <kbd>→</kbd></span></div>
        <div class="control-row"><span>Freno</span><kbd class="wide-key">ESPACIO</kbd></div>
        <div class="control-divider"></div>
        <div class="secondary-keys"><span><kbd>C</kbd> Cámara</span><span><kbd>R</kbd> Reiniciar</span><span><kbd>ESC</kbd> Pausa</span></div>
      </aside>
      <footer class="menu-footer"><span>HECHO PARA RECORRER.</span><span>3D EN TIEMPO REAL <span class="footer-dot">·</span> RECURSOS LOCALES</span></footer>
    </section>

    <section id="hud" class="hud" hidden aria-label="Instrumentos de conducción">
      <div class="hud-top">
        <div class="location-card"><span class="location-dot"></span><div><strong>CIRCUITO DE PRUEBAS</strong><span>Modo libre · escenario provisional</span></div></div>
        <div class="top-actions"><button id="camera-button" class="glass-button" aria-label="Cambiar cámara"><span id="camera-label">EXTERIOR</span><kbd>C</kbd></button><button id="pause-button" class="glass-button" aria-label="Pausar juego">Ⅱ <kbd>ESC</kbd></button></div>
      </div>
      <div class="compass"><span id="heading">N</span><i></i><span>RUMBO</span></div>
      <div id="toast" class="toast" role="status" aria-live="polite" hidden></div>
      <div class="hud-bottom">
        <div class="drive-tip"><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd><span>Conducir</span><span class="tip-separator">/</span><kbd>R</kbd><span>Reiniciar</span></div>
        <div class="speedometer"><div class="speed-meta"><span>VELOCIDAD</span><span id="gear" class="gear">N</span></div><div class="speed-line"><strong id="speed">00</strong><span>km/h</span></div><div class="speed-track"><div id="speed-fill"></div></div><div class="speed-footer"><span id="drive-status">LISTO PARA SALIR</span><span class="status-dot"></span></div></div>
        <div class="session-tag"><strong>BARA—DRIVE</strong><span>PROTOTIPO 0.1</span></div>
      </div>
    </section>

    <section id="pause" class="modal-overlay" hidden aria-labelledby="pause-title" role="dialog" aria-modal="true">
      <div class="pause-card"><span class="eyebrow">TOMATE UN MOMENTO</span><h2 id="pause-title">Recorrido<br>en pausa.</h2><p>El auto te espera donde lo dejaste.</p>
      <button id="resume" class="button primary">CONTINUAR <span>↗</span></button>
      <button id="reset" class="button secondary">REINICIAR POSICIÓN <span>↺</span></button>
      <button id="back-menu" class="text-button">Volver al menú principal</button>
      <div class="pause-controls"><b>W / ↑</b> acelerar · <b>S / ↓</b> frenar y retroceder<br><b>A D / ← →</b> girar · <b>Espacio</b> frenar<br><b>C</b> cámara · <b>R</b> reiniciar · <b>Esc</b> continuar</div></div>
    </section>
    <section id="error" class="modal-overlay" hidden role="alert"><div class="pause-card"><span class="eyebrow">NO SE PUDO INICIAR</span><h2>Revisemos<br>el motor.</h2><p id="error-message"></p><button id="reload" class="button primary">VOLVER A INTENTAR <span>↗</span></button></div></section>
  `;
  const byId = (id) => document.getElementById(id);
  let toastTimeout;
  const speed = byId('speed');
  const gear = byId('gear');
  const fill = byId('speed-fill');
  const status = byId('drive-status');
  const heading = byId('heading');
  let lastSpeed = -1;
  let lastGear = '';
  let lastStatus = '';
  let lastHeading = '';
  byId('reload').addEventListener('click', () => window.location.reload());
  root.querySelector('.brand').addEventListener('click', (event) => event.preventDefault());

  return {
    byId,
    ready() {
      byId('play').disabled = false;
      byId('play-label').textContent = 'EMPEZAR A CONDUCIR';
      byId('loading-label').textContent = 'Motor listo. Tu recorrido puede empezar.';
    },
    state(next) {
      root.dataset.state = next;
      byId('menu').hidden = next !== 'menu';
      byId('hud').hidden = next === 'menu';
      byId('pause').hidden = next !== 'paused';
      byId('hud').inert = next === 'paused';
      if (next === 'paused') byId('resume').focus();
      else if (next === 'menu') byId('play').focus();
      else document.activeElement?.blur();
    },
    camera(mode) {
      root.dataset.camera = mode;
      byId('camera-label').textContent = mode === 'interior' ? 'INTERIOR' : 'EXTERIOR';
    },
    update(vehicle) {
      const kmh = Math.round(vehicle.speedKmh);
      if (kmh !== lastSpeed) {
        speed.textContent = String(kmh).padStart(2, '0');
        fill.style.transform = `scaleX(${Math.min(1, kmh / 130)})`;
        lastSpeed = kmh;
      }
      const direction = vehicle.signedSpeed;
      const nextGear = Math.abs(direction) < 0.2 ? 'N' : direction < 0 ? 'R' : 'D';
      if (nextGear !== lastGear) { gear.textContent = nextGear; lastGear = nextGear; }
      const nextStatus = vehicle.braking ? 'FRENANDO' : kmh < 1 ? 'LISTO PARA SALIR' : nextGear === 'R' ? 'MARCHA ATRÁS' : 'EN RECORRIDO';
      if (nextStatus !== lastStatus) { status.textContent = nextStatus; lastStatus = nextStatus; }
      const q = vehicle.rotation;
      const yaw = Math.atan2(2 * (q.w * q.y + q.x * q.z), 1 - 2 * (q.y * q.y + q.z * q.z));
      const compass = ['N', 'NO', 'O', 'SO', 'S', 'SE', 'E', 'NE'];
      const nextHeading = compass[((Math.round(yaw / (Math.PI / 4)) % 8) + 8) % 8];
      if (nextHeading !== lastHeading) { heading.textContent = nextHeading; lastHeading = nextHeading; }
    },
    toast(message) {
      clearTimeout(toastTimeout);
      byId('toast').textContent = message;
      byId('toast').hidden = false;
      toastTimeout = setTimeout(() => { byId('toast').hidden = true; }, 2500);
    },
    error(error) {
      byId('error').hidden = false;
      byId('error-message').textContent = `No pudimos cargar el escenario 3D. Verificá que el navegador tenga aceleración gráfica habilitada. Detalle: ${error.message}`;
      byId('menu').inert = true;
      byId('hud').inert = true;
      byId('reload').focus();
    },
  };
}
