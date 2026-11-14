# BARA-DRIVE — Mapa 3D de Baradero

Pipeline de Blender/GIS para convertir las calles importadas desde OpenStreetMap
en un entorno urbano 3D. **Estado actual: Fase 1 y Fase 2 implementadas y
verificadas.** La plaza y el resto del entorno no se generaron todavia.

## Requisitos

- Windows 10/11.
- **Blender 5.2** (probado con **5.2.4 LTS**). El Blender 4.2 que usa el
  addon MCP no es el objetivo del pipeline.
- Internet **solo** la primera vez, para instalar Shapely dentro de una carpeta
  aislada (`mapa/.deps/pyXY`). No se modifica el Python global.

## Comandos exactos (Windows)

Desde la raiz del repositorio, en PowerShell:

```powershell
# Opcion recomendada: localiza Blender, instala la dependencia y ejecuta todo.
powershell -ExecutionPolicy Bypass -File scripts\ejecutar_mapa.ps1
```

Si Blender 5.2 esta en una ruta distinta:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ejecutar_mapa.ps1 `
  -Blender "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
```

Pasos manuales equivalentes:

```powershell
$blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

# 1) Dependencia aislada (una vez por version de Python de Blender)
& $blender --background --factory-startup --python scripts\preparar_dependencias_mapa.py

# 2) Diagnostico + calles 3D + guardado del .blend nuevo
& $blender --background --factory-startup --python scripts\generar_mapa_baradero.py

# 3) Verificacion independiente + vistas de control
& $blender --background --factory-startup --python scripts\verificar_mapa.py
```

Solo diagnostico, sin generar geometria:

```powershell
& $blender --background --factory-startup --python scripts\generar_mapa_baradero.py -- --inspect-only
```

## Que hace cada fase

### Fase 1 — Inspeccion (implementada y ejecutada)

- Abre `mapa/blender/Baradero_mapa.blend` en modo headless.
- Comprueba escena, unidades (`scale_length = 1.0`), colecciones y objetos.
- Verifica que las 28 calles importadas sean mallas con caras y que su eje
  coincida con los nodos del OSM. Resultado medido: **error maximo 0.000093 m**.
- Confirma el CRS **EPSG:32721** y el origen lat/lon guardado en la coleccion.
- Escribe `docs/diagnostico_mapa.json` y `docs/diagnostico_mapa.md`.

### Fase 2 — Calles 3D (implementada, ejecutada y verificada)

- Toma el eje de cada calle de la propia malla original (promedio de sus dos
  bordes), por lo que **no se mueve ni se reescala ningun trazado**.
- Ancho de calzada: `width` de OSM > `lanes` (solo si ensancha) > valor
  configurable por clase `highway`.
- Une todas las calzadas con Shapely: los cruces quedan sin huecos ni
  solapamientos visibles.
- Deriva **cordones** y **veredas** de los buffers exteriores de esa union;
  las esquinas quedan redondeadas y no hay veredas cruzando las bocas de las
  intersecciones.
- Materiales PBR simples aptos para glTF: `BARA_Asfalto`, `BARA_Cordon`,
  `BARA_Hormigon`.
- Divide la red en teselas de 256 m para limitar el tamano de malla.
- Guarda en **`mapa/blender/Baradero_mapa_3d.blend`**. El original
  `Baradero_mapa.blend` y la coleccion `BARA_DRIVE_CALLES` no se modifican.

Resultado medido con la configuracion actual:

| Capa | Objetos | Area | Cota superior |
| --- | ---: | ---: | ---: |
| CALZADA | 48 | 187 742.2 m2 | +0.01 m |
| CORDON | 48 | 8 645.8 m2 | +0.15 m |
| VEREDA | 49 | 100 315.1 m2 | +0.15 m |

La verificacion independiente aprobo **23 controles**: colecciones, cantidades,
transformaciones identidad, materiales, cotas, areas, mallas cerradas
(0 bordes abiertos, 0 aristas no manifold) y objetos originales intactos.
Vistas: `docs/renders/calles_*.png`.

## Estructura

```
scripts/
  generar_mapa_baradero.py     entrada Blender: Fase 1 + Fase 2
  verificar_mapa.py            entrada Blender: verificacion + renders
  ejecutar_mapa.ps1            ejecutor Windows todo-en-uno
  preparar_dependencias_mapa.py instalador aislado de Shapely
  mapa_config.json             anchos, cotas, tesela, tolerancias
  mapa_baradero/
    common.py                  config, logs, materiales, colecciones, limpieza
    inspection.py              Fase 1 de solo lectura
    geometry.py                Shapely: cintas, buffers, triangulacion, prismas
    streets.py                 Fase 2: calzadas, cordones, veredas
    runner.py                  orquestacion y respaldos
    verify.py                  controles y vistas Workbench
docs/
  diagnostico_mapa.{json,md}
  informe_calles.{json,md}
  verificacion_calles.json
  renders/
mapa/
  blender/Baradero_mapa.blend      original (no se toca)
  blender/Baradero_mapa_3d.blend   resultado de la Fase 2
  .deps/                           Shapely aislado (ignorado por git)
  logs/                            logs y errores (ignorado por git)
backups/                           copias de seguridad del original
```

## Configuracion

Todo lo editable esta en `scripts/mapa_config.json`:

- `widths_m_estimated`: ancho por clase `highway`.
- `lane_width_m_estimated` y `road_edge_allowance_m_estimated`: solo se usan
  para calles con `lanes >= 2`; nunca angostan por debajo del valor de clase.
- `sidewalk_width_m_estimated`, `curb_width_m_estimated`,
  `curb_top_z_m`: veredas y cordones (estimados, el OSM no los trae).
- `tile_size_m`: tamano de tesela; 256 m por defecto.
- `road_top_z_m`, `road_bottom_z_m`: cotas relativas de la calzada.

Despues de cambiar valores, repetir los comandos: el pipeline elimina solo los
objetos etiquetados con `bara_generated` y vuelve a crearlos, sin duplicados.
Si encuentra objetos ajenos dentro de `BARA_MAPA_3D`, **se detiene** para no
borrar trabajo manual.

## Respaldos y repeticion

- El original se respalda como
  `backups/Baradero_mapa_original_<hash>.blend` (una vez por contenido).
- Si ya existe una salida, se conserva como
  `mapa/blender/Baradero_mapa_3d_trabajo_<fecha>.blend` antes de regenerar.
- El proceso siempre parte de `Baradero_mapa.blend`; el `.blend` de salida es
  un artefacto derivado. Para cambios manuales, guardar un archivo aparte.

## Limitaciones verificadas

- El OSM no tiene modelo digital de elevacion: todas las calles comparten la
  misma cota relativa. No se inventan pendientes.
- Anchos de calzada por clase, veredas, cordones y alturas son estimaciones
  configurables; no son relevantes de medicion.
- El extracto cubre el centro de Baradero, no toda la ciudad. Las vias se
  conservan completas hasta donde llegan sus nodos.
- En los bordes del extracto, las bocas de calle reciben una vereda de cierre.
- `BARA_DRIVE_CALLES` queda visible debajo de la calzada nueva (1 cm por
  debajo) como referencia; no se borra ni se mueve.

## Proxima fase: Plaza Mitre (no iniciada)

El OSM identifica `way/239949279` como Plaza Mitre, con poligonos interiores
`leisure=park`, pero **no aporta** diseno de senderos, canteros, bancos,
luminarias, arboles individuales ni dimensiones del monumento. Antes de
modelarla se necesita una fuente verificable (relevamiento, plano municipal o
imagenes georreferenciadas). No se avanzara a la plaza hasta contar con esos
datos y mientras las calles no esten validadas en el visor.
