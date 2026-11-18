# Verificacion de la Fase 2 (calles 3D)

- Archivo verificado: `mapa/blender/Baradero_mapa_3d.blend`.
- Blender: **5.2.4 LTS**, proceso headless separado del proceso de generacion.
- Escena: `Scene`; unidades metricas; `scale_length = 1.0`.
- Objetos generados: **145** (48 calzadas, 48 cordones, 49 veredas).
- Objetos originales de `BARA_DRIVE_CALLES`: **28**, sin modificaciones.
- Resultado: **23/23 controles aprobados**.

## Controles

| Control | Resultado |
| --- | --- |
| Coleccion raiz y carpetas CALLES / CORDONES / VEREDAS | OK |
| Objetos generados y separados de la fuente | OK |
| Cantidad de objetos por capa | OK (48 / 48 / 49) |
| Transformaciones identidad (sin rotacion, escala ni desplazamiento) | OK |
| Mallas con caras y materiales asignados | OK |
| Metadatos `bara_*` y CRS EPSG:32721 | OK |
| Cotas de cada capa | OK |
| Bordes abiertos | **0** de 53 794 aristas |
| Aristas no manifold | **0** |
| Area de calzada | 187 742.2 m2 (0.000 % de diferencia) |
| Area de cordon | 8 645.8 m2 (0.000 %) |
| Area de vereda | 100 315.1 m2 (0.000 %) |
| Huellas de los 28 objetos originales | Sin cambios |
| Vistas de control generadas | 6 imagenes |

Las areas se comparan contra las calculadas por Shapely antes del teselado y se
recalculan desde las caras superiores de las mallas guardadas.

## Vistas

- `docs/renders/calles_superior.png` — red completa.
- `docs/renders/calles_oblicua.png` — red completa en perspectiva.
- `docs/renders/calles_detalle_superior.png` — escala de manzana.
- `docs/renders/calles_detalle_oblicua.png` — escala de manzana en perspectiva.
- `docs/renders/calles_esquina_superior.png` — interseccion real del OSM.
- `docs/renders/calles_esquina_oblicua.png` — esquinas, cordones y veredas.

En las vistas de esquina se observa la calzada continua en el cruce, el cordon
de 0.15 m y la vereda de 2 m con esquinas redondeadas, sin bandas de vereda
cruzando la boca de la interseccion.

## Reproducir

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ejecutar_mapa.ps1
```

El detalle completo, control por control, esta en
`docs/verificacion_calles.json`.
