# Baradero 3D: Plaza Mitre y Municipalidad (aprox.)

- Generado con Blender **4.2.23 LTS**.
- Archivo de salida: `C:\Users\a22ma\OneDrive\Desktop\bara-drive\Mapa-Baradero\mapabaradrive\mapa\blender\Baradero_Realista_v2.blend`.
- Archivo base: `C:\Users\a22ma\OneDrive\Desktop\bara-drive\Mapa-Baradero\mapabaradrive\mapa\blender\Baradero_3D.blend`.
- Calles verificadas contra el OSM antes de construir: **28**; error maximo **0.000093 m**.

## Plaza Mitre

- Centro aproximado (UTM local): (-0.2, 60.5) m.
- Arboles: **54** (jacarandaes 31, palmeras 12, copa 8), arbustos 22.
- Bancos: **16**; faroles: **16**; cestos: 4.
- Monumento al Condor en el centro, con tres escalones de piedra y condor de alas abiertas.

## Municipalidad

- Huella OSM: way/386834199 (Av. San Martin 905).
- Dimensiones del volumen: **32.0 x 13.0 m**, alto **8.8 m**.
- Frente a **17.7 m** del borde de Plaza Mitre.
- Objetos: `DELEGACION_MUNICIPAL`, rampa `DELEGACION_RAMPA`, escudo `DELEGACION_ESCUDO`, panel `DELEGACION_PANEL_BARADERO`.

## Camaras

- plaza: `CAMARA_PLAZA`
- delegacion: `CAMARA_DELEGACION`
- monumento: `CAMARA_MONUMENTO`
- aerea: `CAMARA_PLAZA_AEREA`

## Fotografias usadas

- `referencias/plaza-mitre/desdearriba.jpg`
- `referencias/plaza-mitre/condor.jpg`
- `referencias/plaza-mitre/iglesia.jpg`
- `referencias/plaza-mitre/vereda.jpg`
- `referencias/plaza-mitre/vereda2.jpg`
- `referencias/plaza-mitre/vereda3.jpg`
- `referencias/delegacion/delegacion.jpg`

## Limitaciones

- Modelo aproximado: las fotos no tienen escala ni mediciones.
- La Delegacion fotografiada es la Municipalidad de Baradero (Av. San Martin 905).
- Senderos, cantidad de arboles y detalles menores son estimaciones.
- No se modelaron personas, vehiculos, cables ni carteles transitorios.
- La iglesia de la foto queda como referencia visual; no se reconstruyo en esta etapa.
- No se modifico ni borro ninguna calle, vereda o edificio existente.

## Verificacion de no destruccion

- La reconstruccion se agrega en `BARA_LUGARES_REALES`, hija de `BARA_MAPA_3D`.
- No se borro ninguna calle, cordon, vereda ni edificio provisional existente.
