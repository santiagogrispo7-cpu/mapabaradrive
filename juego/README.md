# BARA-DRIVE · Prototipo jugable 0.1

Videojuego de conducción 3D con **Three.js, JavaScript, Vite y Rapier 3D**.
Esta etapa implementa el vehículo y un circuito provisional. **El escenario no
representa todavía Baradero ni utiliza las calles OSM del repositorio.**

## Probar en Windows

En esta computadora, hacer doble clic en **`iniciar.cmd`**. El script reconoce la
copia portátil de Node preparada para el desarrollo y abre el navegador en
`http://127.0.0.1:5173`. Dejar la consola abierta mientras se juega.

En otra computadora, instalar **Node.js 24 LTS** (mínimo soportado por el proyecto:
22.12), abrir una terminal en `juego` y ejecutar:

```sh
npm ci
npm run dev
```

Abrir **http://127.0.0.1:5173**, esperar «Motor listo» y presionar
**EMPEZAR A CONDUCIR**. Se necesita un navegador actualizado con WebGL 2 y
aceleración gráfica. Edge está probado por la suite automatizada.

`npm ci` necesita Internet la primera vez. El escenario, materiales, fuentes del
sistema y física WASM se cargan localmente; no se consultan mapas ni CDN al jugar.

**Este prototipo todavía usa un servidor local de Vite.** No es aún un `.exe`
independiente. El empaquetado con Electron corresponde a una etapa posterior.
No se necesita Blender para ejecutar o compilar el juego.

## Controles

| Tecla | Acción |
|---|---|
| W / ↑ | Acelerar hacia adelante; frenar si se está retrocediendo |
| S / ↓ | Frenar y, al bajar la velocidad, activar marcha atrás |
| A / D o ← / → | Girar a izquierda / derecha |
| Espacio | Frenar sin activar marcha atrás |
| C | Alternar cámara exterior e interior |
| R | Volver al punto de salida y detener el auto |
| Esc | Pausar / continuar |

El juego se pausa al perder el foco o cambiar de pestaña y limpia las teclas
presionadas, evitando que el auto siga acelerando. La cámara interior incluye
volante animado y un tablero con velocidad; el HUD también muestra km/h y marcha.

## Compilar y comprobar

```sh
npm test
npm run build
npm run preview
```

La compilación queda en `dist/`. La previsualización está en
**http://127.0.0.1:4173**. No abrir `dist/index.html` con doble clic: los módulos
JavaScript necesitan un origen HTTP local en esta etapa. `dist/` y `node_modules/`
son salidas regenerables y están ignorados por Git. `package-lock.json` fija las
versiones instaladas.

Pruebas de navegador (después de compilar, con los puertos 5173 y 4173 libres):

```sh
npm run test:e2e
```

Usan Microsoft Edge mediante Playwright; no descargan un navegador adicional.
En otro sistema, ajustar `channel` en `playwright.config.js` al navegador
disponible. La suite inicia y detiene sus propios servidores.

Las pruebas de física comprueban aceleración, frenado, reversa, giro, colisión real
con un muro y reinicio. Las pruebas de navegador comprueban teclado, movimiento,
cámaras, pausa, pérdida de foco, ausencia de recursos externos en la compilación
y un mensaje de error recuperable cuando falta WebGL. Las capturas se guardan en
`test-results/`.

## Estructura

```text
juego/
  src/
    main.js             Inicio, bucle de juego y estados menú/juego/pausa
    ui.js               Menú, HUD, avisos y diálogo de pausa
    style.css           Interfaz adaptable sin fuentes externas
    game/
      config.js         Escala, punto de salida y parámetros del auto
      Vehicle.js        Cuerpo físico y control de conducción
      CarModel.js       Modelo visual, ruedas, interior y tablero
      World.js          Escenario provisional y colisiones estáticas
      Cameras.js        Cámaras interior/exterior y obstrucciones
      Input.js          Teclado y acciones
  tests/
    vehicle.test.js     Pruebas de Rapier sin renderer
    browser/            Pruebas de integración en navegador
```

## Decisiones de estabilidad y rendimiento

- Unidades: metros, segundos y kilogramos; Y arriba y frente del auto hacia −Z.
- Rapier avanza a **60 pasos físicos por segundo**, separado del renderizado e
  interpolado. Se limita la recuperación de frames lentos a seis pasos por frame.
- El vehículo es un cuerpo dinámico con CCD, impulsos de motor/freno y agarre
  lateral. No se mueve atravesando colliders mediante cambios de posición.
- Conducción **arcade**: inclinación longitudinal y lateral bloqueadas para un
  circuito plano. Las ruedas son visuales; todavía no hay suspensión ni simulación
  automotriz avanzada. Los parámetros están centralizados en `config.js`.
- Colisiones simplificadas, geometrías/materiales compartidos, marcas viales y
  ventanas instanciadas, pixel ratio máximo de 1.5 y un solo mapa de sombras de 1024 px.
- Física WASM cargada en un archivo separado para mostrar el menú antes de que
  termine de inicializar el motor.
- Recursos propios generados por código; ninguna textura o modelo remoto.
- Cámaras con interpolación; la exterior evita atravesar los edificios.
- En desarrollo, `window.__BARA_DRIVE__.snapshot()` permite inspeccionar estado,
  posición y velocidad. Esa interfaz no se publica en la compilación final.

## Próxima etapa

Integrar OSM mediante sectores y metadatos, conservando el generador y las fuentes
existentes del repositorio. Al pasar de Blender (Z arriba) a Three.js (Y arriba),
aplicar una única conversión de ejes y conservar la escala métrica. Después:
semáforos, infracciones, modos de prueba, volante/pedales y empaquetado Electron.

Los límites, señales decorativas y edificios del circuito actual son de prueba.
Todavía no existe un sistema de infracciones ni un mapa completo de la ciudad.
