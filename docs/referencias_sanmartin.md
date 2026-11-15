# Avenida San Martin — observaciones previas al modelado

## Recorrido visual (7 archivos, no 6)

1. `patiodecomidas1.png`: detalle lateral del patio antes del cruce. Jardin,
   palmeras, mesas bajo cubierta, zocalo salmon y carteles. Se leen «CENA SHOW»,
   «SANDWICH» y «ASADO»; el nombre del comercio no se distingue con seguridad.
2. `av.sanmartin1.png`: aproximacion a Malabia, patio a la izquierda y local
   de techo inclinado al otro lado del cruce, a la derecha.
3. `esquinasemaforo.png`: esquina, placa SAN MARTIN 1100–1000 y flecha;
   enfrente cubierta plana alta, columnas y cerramiento oscuro.
4. `esquinasemaforo2.png`: vista complementaria desde Malabia. Semaforos
   amarillos, local de cubierta gris inclinada, vidriera y palmeras a la derecha
   del avance por San Martin. Cubierta plana del punto anterior a la izquierda.
5. `avsanmartin2.png`: pasada la esquina. Fachadas azules con arcos y pilastras
   claras a la izquierda; muro blanco, porton gris y edificio de balcones a la derecha.
6. `avsanmartin3.png`: avance por la cuadra. Casas bajas de revoque claro y
   piedra a la izquierda; edificio alto con balcones, comercio y palmera a la derecha.
7. `av.sanmartin.png`: mas adelante. A la izquierda edificio de dos plantas con
   balcon y negocios. A la derecha portal blanco ornamentado, jardin, fachada roja
   con toldos azules y molduras superiores. Los nombres no legibles no se completan.

La secuencia se infiere por continuidad de fachadas y acercamiento a la esquina,
no por los nombres de archivo. Las dos vistas de esquina no definen dos tramos.
`referencias/esquina-rodriguez` documenta otra esquina y no se usa para trasladar
fachadas a esta cuadra.

## Anclaje comprobado

- Eje Avenida San Martin: OSM way 228161668.
- Malabia: OSM way 228161407, nodo compartido 2367942995.
- Inicio: lat -33.808027, lon -59.5038352; XY local (-151.885922, -59.961532).
- El nodo de inicio esta etiquetado `highway=traffic_signals`.
- Proximo cruce hacia Plaza Mitre: Santa Maria de Oro, way 601167979,
  nodo 2367942960; lat -33.8070289, lon -59.5029681;
  XY (-74.294606, 52.695926).
- La direccion de numeracion decreciente esta respaldada por el cartel de la foto
  y la direccion provista por el usuario. Longitud entre ejes: aproximadamente 136.8 m.
- OSM confirma ejes y esquina, no los frentes de cada parcela. Los anchos,
  profundidades y alturas se estiman visualmente y se etiquetan como aproximados.
- No se cuenta con planos catastrales, fotos ortogonales, escala, ni vistas de todos
  los fondos. Solo se detallan superficies y elementos visibles; fondos son volumen
  de cierre aproximado. No se atribuyen alturas metricas exactas a las fotografias.

## Skills y recursos

Instalacion autorizada por el usuario: blender-modeler, materials,
vegetation-artist, godot-export (arjun988/blender-skills, commit
904f095d8f36a6e72adaebb08d07f884a074743d, MIT) y geo-sleuth
(Oldcircle/geo-sleuth, commit d56c35789565e9459f0663e860c470e98e9c30d1).
Se utilizan las pautas de modelado, observacion, evidencia OSM, PBR e instancias.
Las herramientas opcionales de geolocalizacion con instalaciones automaticas
no se ejecutan: el anclaje se calcula con el XML local y el Python ya disponible.
Se conservan las licencias originales junto a las skills.

Los modelos y texturas externos se obtienen de Poly Haven (CC0-1.0, permitido
uso comercial y redistribucion en videojuegos). URLs y checksums en
`mapa/recursos/sanmartin/licenses.json`. Las capturas se usan como referencia
visual; los materiales del modelo usan recursos CC0 y geometria propia.
