# Diagnostico del mapa BARA-DRIVE

- Archivo inspeccionado: `C:\Users\a22ma\OneDrive\Desktop\bara-drive\Mapa-Baradero\mapabaradrive\mapa\blender\Baradero_mapa.blend`.
- Blender: **5.2.4 LTS**. APIs usadas presentes en 4.2 y 5.2.
- Escena: 54 objetos; colecciones: BARA_DRIVE_CALLES, Collection, Prueba_Baradero.
- Calles verificadas contra el OSM: **28**.
- Error maximo del eje respecto del OSM: **0.000093 m**.
- CRS: **EPSG:32721**; origen lat/lon: -33.80752, -59.50218.
- Escala: 1.0 m por unidad; X este UTM; Y norte de cuadrícula UTM; Z arriba.
- OSM: 446 nodos, 28 vias highway, 5 edificios.
- Plaza Mitre: way/239949279.
- Arboles individuales: 0; bancos: 0; luminarias: 0.

## Limitaciones verificadas

- OSM del centro, no toda la ciudad
- Sin modelo digital de elevación: cota relativa Z=0
- Anchos de calzada/vereda y altura de cordón estimados configurables
- No inferir superficies, mobiliario o monumentos de Plaza Mitre de sus nombres o polígonos

El JSON asociado incluye transformaciones, firmas y topologia de cada objeto.
