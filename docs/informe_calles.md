# Fase 2: calles 3D

- Generado con Blender **5.2.4 LTS**.
- Vias de origen convertidas: **28**.
- Tesela: 256.0 m; CRS EPSG:32721; unidades en metros.
- Superficie total de calzada unida: 187742.2 m2.

## Capas

| Capa | Objetos | Area (m2) | Z inferior | Z superior | Material |
| --- | ---: | ---: | ---: | ---: | --- |
| CALZADA | 48 | 187742.2 | -0.17 | 0.01 | BARA_Asfalto |
| CORDON | 48 | 8645.8 | -0.17 | 0.15 | BARA_Cordon |
| VEREDA | 49 | 100315.1 | -0.17 | 0.15 | BARA_Hormigon |

## Vias

| Via | Nombre | Clase | Ancho (m) | Origen del ancho | Longitud (m) |
| --- | --- | --- | ---: | --- | ---: |
| 228161261 | René Simón | secondary | 8.00 | class_default | 896.1 |
| 228161262 | Malabia | secondary | 8.00 | class_default | 220.5 |
| 228161263 | Gascón | residential | 7.00 | class_default | 1456.6 |
| 228161264 | René Simón | secondary | 8.00 | class_default | 297.5 |
| 228161265 | Malabia | secondary | 8.00 | class_default | 434.8 |
| 228161407 | Malabia | secondary | 8.00 | class_default | 1015.7 |
| 228161408 | Darragueira | residential | 7.00 | class_default | 1455.5 |
| 228161596 | Cabrera | residential | 7.00 | class_default | 1694.3 |
| 228161597 | Boedo | residential | 7.00 | class_default | 1459.5 |
| 228161668 | Avenida San Martín | secondary | 8.00 | class_default | 2116.8 |
| 228161671 | Laprida | residential | 7.00 | class_default | 1125.0 |
| 228161673 | Anchorena | residential | 7.00 | class_default | 1122.2 |
| 228161712 | Sáenz | residential | 7.00 | class_default | 947.8 |
| 228162442 | Rodríguez | residential | 7.00 | class_default | 1132.4 |
| 228162453 | Thames | residential | 7.00 | class_default | 1630.8 |
| 228162456 | Gorriti | residential | 7.00 | class_default | 1042.7 |
| 228162645 | Bulnes | residential | 7.00 | class_default | 1440.7 |
| 228162649 | Paso | residential | 7.00 | class_default | 937.9 |
| 228163421 | Acevedo | residential | 7.00 | class_default | 582.1 |
| 239949320 | René Simón | secondary | 8.00 | class_default | 898.0 |
| 301191091 | Aráoz | residential | 7.00 | class_default | 1033.7 |
| 301191122 | Colombres | residential | 7.00 | class_default | 1354.9 |
| 311603187 | Rene Simon | secondary | 8.00 | class_default | 159.2 |
| 360897430 | Laprida | residential | 7.00 | class_default | 62.8 |
| 601167979 | Santa María de Oro | residential | 7.00 | class_default | 1446.5 |
| 601167985 | Castro Barros | residential | 7.00 | class_default | 465.6 |
| 635329950 |  | service | 4.00 | class_default | 106.3 |
| 685524802 | Avenida San Martín | secondary | 8.00 | class_default | 138.2 |

## Limitaciones

- Sin modelo digital de elevacion: todas las calles quedan a la misma cota relativa
- Anchos de calzada por clase, veredas y cordones son estimaciones configurables
- El OSM no incluye cordones ni veredas: se derivan del perimetro de la calzada
- Las bocas de las calles en el borde del extracto OSM reciben vereda de cierre
- Los objetos originales BARA_DRIVE_CALLES se conservan sin modificar

Los objetos originales de `BARA_DRIVE_CALLES` quedan intactos; la geometria nueva
vive en `BARA_MAPA_3D/CALLES`, `BARA_MAPA_3D/CORDONES` y `BARA_MAPA_3D/VEREDAS`.
