# Plan de implementación: Baradero 3D para Euro Truck Simulator 2

## Objetivo y límite inicial

Construir un primer tramo jugable de Baradero para un mod de Euro Truck Simulator 2 (ETS2), usando OpenCode para coordinar generación y validación de recursos 3D en Blender. El primer entregable es una zona acotada que pueda recorrerse dentro del juego; completar toda la ciudad es una fase posterior.

**Estado:** plan, no implementación. La escala del mapa, el tramo exacto y la versión compatible de las herramientas SCS se confirman en la fase 0. No se incluyen archivos del juego ni fuentes cartográficas sin licencia de redistribución.

## Ruta rápida

1. Probar una cadena mínima de exportación: Blender → SCS Blender Tools → Conversion Tools → recurso visible en el editor de mapas de ETS2.
2. Fijar un sistema de coordenadas y generar un tramo de referencia a partir de fuentes cartográficas con procedencia documentada.
3. Modelar terreno y objetos en Blender; construir la red vial jugable en el editor del juego.
4. Empaquetar el mod y recorrer el tramo dentro de ETS2, revisando registro, posiciones y rendimiento.

## Responsabilidades

| Componente | Responsabilidad | No hace |
| --- | --- | --- |
| OpenCode | Orquestar tareas, ejecutar scripts, inspeccionar resultados y registrar verificaciones. | Sustituir la inspección visual o la prueba dentro del juego. |
| Blender + scripts `bpy` | Modelar terreno, edificios y recursos visuales; exportar modelos compatibles cuando se valide el addon. | Generar por sí solo carreteras jugables o sectores finales. |
| SCS Blender Tools + Conversion Tools | Transformar recursos de Blender al formato requerido por el juego; versiones fijadas tras una prueba real. | Diseñar el mapa vial. |
| Editor de mapas de ETS2 | Colocar recursos, crear carreteras, conexiones, colisiones y sectores. | Reemplazar el archivo fuente editable de los modelos. |

La conexión MCP con Blender 5.2 LTS ya se observó en esta estación de trabajo. **No demuestra** que SCS Blender Tools funcione allí ni que el mismo MCP funcione en otra versión de Blender. La versión de autoría se decide mediante la prueba de extremo a extremo; si se necesita una versión anterior, los archivos maestros deben crearse en esa versión y no depender de abrir archivos más nuevos en ella. Si el MCP no admite esa versión, usar scripts `bpy` ejecutados por Blender en segundo plano.

## Fases y criterios de salida

### F0. Compatibilidad y alcance

- Confirmar versión objetivo de ETS2, tipo de mapa (independiente o extensión), escala y tramo de la primera entrega. Propuesta a evaluar: escala urbana 1:1 en un mapa independiente; no fijarla antes de comprobar restricciones del editor.
- Instalar o identificar una combinación compatible de Blender, SCS Blender Tools, Conversion Tools y editor de mapas. Registrar versiones y licencias.
- Crear y exportar un objeto de prueba con material; colocarlo y verlo en ETS2. Conservar los comandos, archivos y errores observados.
- **Salida:** objeto visible sin errores de conversión ni referencias faltantes. Si falla, detener el pipeline geográfico hasta resolver compatibilidad.

### F1. Proyecto reproducible y conexión OpenCode–Blender

- Organizar scripts, recursos fuente, salidas generadas y documentación; excluir cachés, binarios de herramientas y archivos del juego del repositorio.
- Construir funciones Python reutilizables tanto desde la sesión Blender controlada por OpenCode como desde `blender -b -P`, si ambas rutas resultan compatibles; de lo contrario, adoptar la ruta de segundo plano como interfaz principal.
- **Salida:** la misma entrada produce geometría y materiales equivalentes por las rutas habilitadas; una compilación limpia no depende de operaciones manuales no documentadas.

### F2. Base geográfica

- Obtener calles y huellas de edificios de OpenStreetMap y un modelo de elevación con cobertura y condiciones de uso verificadas. Conservar fuente, fecha, atribución y límites de redistribución.
- Convertir WGS84 a coordenadas métricas locales mediante una única transformación documentada; evaluar UTM 21S para Baradero y fijar origen, ejes y factor de escala solo después de comprobar puntos de referencia en el editor.
- **Salida:** al menos dos puntos de control y los límites del tramo coinciden entre datos, Blender y editor dentro de una tolerancia acordada antes de modelar en volumen.

### F3. Terreno y recursos visuales

- Generar terreno y costa recortados al tramo; crear edificios representativos a partir de huellas y alturas medidas o marcadas como estimadas.
- Preparar materiales y niveles de detalle según los requisitos comprobados de SCS; reutilizar recursos cuando reduzca trabajo y coste de renderizado.
- **Salida:** recursos convertibles, correctamente orientados y situados, sin materiales faltantes ni geometría rota; medir tamaño y rendimiento en la máquina objetivo.

### F4. Tramo jugable

- Dibujar carreteras, cruces y enlaces en el editor de ETS2; alinear los recursos visuales con la referencia geográfica.
- Probar conducción, colisiones, navegación y límites de sectores. No editar sectores binarios mediante un generador propio en esta primera entrega.
- **Salida:** recorrido completo por el tramo elegido sin bloqueos, huecos de terreno ni conexiones viales incorrectas.

### F5. Empaquetado y validación

- Preparar la estructura de mod y manifiesto que exija la versión objetivo del juego; generar un paquete instalable sin incluir datos de terceros no autorizados.
- Probar en un perfil aislado de ETS2 y revisar `game.log.txt`, carga de recursos, recorrido y métricas de rendimiento.
- **Salida:** paquete que carga y permite recorrer el tramo; documentar advertencias restantes, atribuciones, instrucciones de instalación y versiones compatibles.

## Estructura propuesta (se ajusta al repositorio real)

```text
data/raw/          fuentes descargadas, no distribuidas por defecto
data/derived/      datos normalizados y puntos de control
pipeline/          transformaciones, generación y exportación reproducible
blender/           fuentes editables y materiales
mod/               contenido autorizado del mod
docs/              decisiones, atribución y verificación
```

Las herramientas SCS, el juego, las credenciales y los datasets sin permiso de distribución permanecen fuera del control de versiones. El contenido de `build/` se genera y no se versiona salvo que una entrega concreta lo requiera.

## Decisiones pendientes antes de implementar

1. Confirmar si el objetivo es ETS2 y si el mapa será independiente o una extensión del mapa original.
2. Elegir tramo piloto y escala tras una prueba en el editor; 1:1 es una hipótesis para el casco urbano, no una compatibilidad demostrada.
3. Validar versiones reales del toolchain y la ruta de exportación con un recurso mínimo.
4. Confirmar fuentes cartográficas, atribución y permisos antes de distribuir datos o texturas derivadas.

El trabajo posterior avanza por entregables verificables: primero compatibilidad, después coordenadas, luego recursos y finalmente jugabilidad. Ninguna etapa posterior sustituye la prueba dentro del juego.
