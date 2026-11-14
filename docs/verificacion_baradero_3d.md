# Verificacion Baradero 3D

- Archivo: `Baradero_3D.blend`; Blender **4.2.23 LTS**.
- Resultado: **APROBADO** (37/37 comprobaciones).
- Edificios PROVISIONALES: **21** en **7** manzanas.
- Calzadas: 48; cordones: 48; veredas: 49.
- Arboles: 14; postes: 14; senales: 6.

## Comprobaciones

| Resultado | Comprobacion | Detalle |
| --- | --- | --- |
| OK | Coleccion raiz BARA_MAPA_3D |  |
| OK | Escala de escena 1.0 | 1.0 |
| OK | Calles OSM de origen intactas | 28 vias con osm_way_id |
| OK | Coleccion CALLES |  |
| OK | Coleccion CORDONES |  |
| OK | Coleccion VEREDAS |  |
| OK | Coleccion TERRENO |  |
| OK | Coleccion EDIFICIOS |  |
| OK | Coleccion VEGETACION |  |
| OK | Coleccion ILUMINACION |  |
| OK | Coleccion SEÑALES |  |
| OK | Coleccion CAMARAS |  |
| OK | Calzadas 3D presentes | 48 objetos |
| OK | Cordones presentes | 48 objetos |
| OK | Veredas presentes | 49 objetos |
| OK | Superficie de asfalto > 10000 m2 | 187742 m2 |
| OK | Superficie de vereda > 10000 m2 | 100315 m2 |
| OK | Terreno base |  |
| OK | Al menos 15 edificios provisionales | 21 edificios |
| OK | Todos los edificios se nombran PROVISIONAL | sin prefijo: [] |
| OK | Aviso de edificio no real en cada objeto | 0 sin aviso |
| OK | Edificios con ventanas, puertas y techo | ventanas=189, puertas=21, techos=108; fallas=[] |
| OK | Edificios con base a nivel de terreno | [] |
| OK | Edificios repartidos en al menos 5 manzanas | 7 manzanas: [1, 2, 3, 4, 5, 6, 7] |
| OK | Al menos 5 manzanas detectadas | 70 manzanas |
| OK | Cada edificio dentro de una manzana | fuera: [] |
| OK | Edificios no invaden calzada ni vereda | invaden: [] |
| OK | Edificios sin superposicion entre si | [] |
| OK | Arboles generados | 14 arboles |
| OK | Postes de luz generados | 14 postes |
| OK | Senales de transito generadas | 6 senales |
| OK | Camara principal |  |
| OK | Camara asignada a la escena |  |
| OK | Camara en perspectiva | PERSP |
| OK | Luz solar |  |
| OK | Vista 3D guardada en perspectiva/camara | 10 areas |
| OK | Sombreado material guardado | 10 areas |

## Renders

- `docs\renders\baradero3d_camara.png` (1169348 bytes)
- `docs\renders\baradero3d_planta.png` (1110271 bytes)
- `docs\renders\baradero3d_calle.png` (798688 bytes)
- `docs\renders\baradero3d_camara_eevee.png` (1149633 bytes)

Los edificios PROVISIONAL_* son volumetricos de prueba, no edificios reales de Baradero.
