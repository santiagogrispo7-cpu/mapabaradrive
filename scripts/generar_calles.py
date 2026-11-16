"""BARA-DRIVE: calles OSM reales, sin dependencias externas.

Ejecutar en Python de Blender. API para MCP: prepare(), build_batch(), finish().
Ejecutar como script principal procesa todos los lotes después del respaldo.
No reutiliza ni borra colecciones existentes: cambiar COLLECTION_NAME para otra
importación. Los extremos fuera de <bounds> se conservan completos.

Proyección WGS84 / UTM 21S (EPSG:32721), serie Transversa de Mercator de Snyder
hasta A^6. Origen fijo: lat=-33.807520, lon=-59.502180. X = este UTM relativo,
Y = norte de cuadrícula UTM relativo; Z = arriba. La orientación y escala son
las de UTM, sin rotaciones ni reescalados estéticos. Coordenadas en metros,
convertidas a unidades Blender usando el scale_length existente.

Las superficies son cintas planas con uniones a inglete, una malla por vía.
Los cruces se superponen con el mismo material; no se hace una unión booleana
de la red ni se crean conectores que no figuren en el OSM. Sin elevación OSM,
se usa Z=0. No es una reconstrucción topográfica ni de anchos relevados.
"""

from collections import Counter
from datetime import datetime
from pathlib import Path
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OSM_PATH = ROOT / "datos_osm" / "baradero_centro.osm"
COLLECTION_NAME = "BARA_DRIVE_CALLES"
REPORT_PATH = ROOT / "docs" / "informe_generacion_calles.json"
ORIGIN_LAT = -33.807520
ORIGIN_LON = -59.502180
BATCH_SIZE = 6
DEFAULT_WIDTHS_M = {
    "motorway": 12.0, "motorway_link": 5.0,
    "trunk": 10.0, "trunk_link": 5.0,
    "primary": 9.0, "primary_link": 5.0,
    "secondary": 8.0, "secondary_link": 5.0,
    "tertiary": 7.0, "tertiary_link": 5.0,
    "unclassified": 7.0, "residential": 7.0,
    "living_street": 5.0, "service": 4.0,
}
LANE_WIDTH_M = 3.25
EDGE_ALLOWANCE_M = 0.50  # Por lado, cuando se estima mediante lanes.
MAX_MITER_RATIO = 4.0
SURFACE_Z_M = 0.0
ASPHALT_RGBA = (0.055, 0.060, 0.065, 1.0)
_SESSION = None


def utm21s(lon, lat):
    """WGS84 lon/lat en grados -> este/norte en metros, UTM 21 Sur."""
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise ValueError("Coordenadas no finitas")
    if not (-60.0 <= lon <= -54.0 and -80.0 <= lat <= 0.0):
        raise ValueError("Coordenadas fuera del dominio UTM 21 Sur")
    a, e2, k0 = 6378137.0, 0.0066943799901413165, 0.9996
    phi = math.radians(lat)
    ep2 = e2 / (1.0 - e2)
    n = a / math.sqrt(1.0 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    aa = math.cos(phi) * math.radians(lon + 57.0)
    m = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
        - 35 * e2**3 / 3072 * math.sin(6 * phi)
    )
    east = 500000 + k0 * n * (
        aa + (1 - t + c) * aa**3 / 6
        + (5 - 18 * t + t*t + 72 * c - 58 * ep2) * aa**5 / 120
    )
    north = 10000000 + k0 * (
        m + n * math.tan(phi) * (
            aa*aa / 2 + (5 - t + 9 * c + 4 * c*c) * aa**4 / 24
            + (61 - 58 * t + t*t + 600 * c - 330 * ep2) * aa**6 / 720
        )
    )
    return east, north


def tags_of(element):
    return {tag.get("k"): tag.get("v") for tag in element.findall("tag")}


def width_for(tags):
    """Prioridad: width explícito > lanes > ancho provisional por highway."""
    warnings = []
    if "width" in tags:
        match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(m|ft)?\s*", tags["width"])
        if match:
            value = float(match[1].replace(",", "."))
            value *= 0.3048 if match[2] == "ft" else 1.0
            if value > 0:
                return value, "width", warnings
        warnings.append("width no interpretable; se usa estimación")
    if "lanes" in tags:
        try:
            lanes = int(tags["lanes"])
            if lanes > 0:
                return lanes * LANE_WIDTH_M + 2 * EDGE_ALLOWANCE_M, "lanes_estimado", warnings
        except ValueError:
            pass
        warnings.append("lanes no interpretable; se usa categoría")
    return DEFAULT_WIDTHS_M[tags["highway"]], "highway_estimado", warnings


def road_surface(points, width):
    """Dos vértices por nodo; el punto medio conserva exactamente el eje OSM."""
    closed = points[0] == points[-1]
    points = points[:-1] if closed else points
    if len(points) < (3 if closed else 2):
        raise ValueError("Trazado insuficiente")
    normals = []
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        p, q = points[i], points[(i + 1) % len(points)]
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            raise ValueError("Segmento de longitud cero")
        normals.append((-dy / length, dx / length))
    verts, faces, warnings = [], [], []
    half = width / 2
    for i, (x, y) in enumerate(points):
        if not closed and i == 0:
            ox, oy = (v * half for v in normals[0])
        elif not closed and i == len(points) - 1:
            ox, oy = (v * half for v in normals[-1])
        else:
            previous, following = normals[i - 1], normals[i % len(normals)]
            sx, sy = previous[0] + following[0], previous[1] + following[1]
            denominator = sx * following[0] + sy * following[1]
            if denominator < 1e-8:
                raise ValueError("Giro de 180 grados; requiere tratamiento específico")
            ox, oy = half * sx / denominator, half * sy / denominator
            ratio = math.hypot(ox, oy) / half
            if ratio > MAX_MITER_RATIO:
                ox *= MAX_MITER_RATIO / ratio
                oy *= MAX_MITER_RATIO / ratio
                warnings.append(f"Inglete limitado en nodo {i}")
        verts.extend([(x + ox, y + oy, SURFACE_Z_M), (x - ox, y - oy, SURFACE_Z_M)])
    for i in range(count):
        j = (i + 1) % len(points)
        # Triángulos con normales +Z; no depende de triangulación de n-gons.
        faces.extend([(2*i, 2*i+1, 2*j+1), (2*i, 2*j+1, 2*j)])
    for face in faces:
        p, q, r = [verts[i] for i in face]
        if (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0]) <= 1e-8:
            raise ValueError("Superficie invertida o degenerada en curva estrecha")
    return verts, faces, warnings


def analyze():
    """Preflight íntegro, sin escribir archivos ni cambiar Blender."""
    root = ET.parse(OSM_PATH).getroot()
    if root.tag != "osm" or root.get("version") != "0.6":
        raise ValueError("Se requiere XML OSM 0.6")
    origin = utm21s(ORIGIN_LON, ORIGIN_LAT)
    nodes = {}
    for element in root.findall("node"):
        east, north = utm21s(float(element.get("lon")), float(element.get("lat")))
        if element.get("id") in nodes:
            raise ValueError("ID de nodo duplicado")
        nodes[element.get("id")] = (east - origin[0], north - origin[1])
    roads, omitted = [], []
    highway_count = 0
    seen_ids = set()
    for way in root.findall("way"):
        way_id, tags = way.get("id"), tags_of(way)
        if way_id in seen_ids:
            raise ValueError("ID de vía duplicado")
        seen_ids.add(way_id)
        if "highway" not in tags:
            omitted.append({"id": way_id, "reason": "sin_highway"})
            continue
        highway_count += 1
        if tags["highway"] not in DEFAULT_WIDTHS_M or tags.get("area") == "yes":
            omitted.append({"id": way_id, "reason": "highway_no_vehicular_o_area"})
            continue
        access = next((tags[k] for k in ("motorcar", "motor_vehicle", "vehicle", "access") if k in tags), None)
        if access in {"no", "agricultural", "forestry"}:
            omitted.append({"id": way_id, "reason": "acceso_vehicular_restringido"})
            continue
        if tags.get("bridge", "no") != "no" or tags.get("tunnel", "no") != "no" or tags.get("layer", "0") != "0":
            raise ValueError(f"Vía {way_id}: requiere alturas para un cruce a distinto nivel")
        refs = [nd.get("ref") for nd in way.findall("nd")]
        if len(refs) < 2 or any(ref not in nodes for ref in refs):
            raise ValueError(f"Vía {way_id}: faltan nodos")
        points = [nodes[ref] for ref in refs]
        width, source, warnings = width_for(tags)
        verts, faces, geometry_warnings = road_surface(points, width)
        roads.append({
            "id": way_id, "tags": tags, "node_ids": refs, "points": points,
            "width_m": width, "width_source": source,
            "vertices": verts, "faces": faces,
            "length_m": math.fsum(math.dist(p, q) for p, q in zip(points, points[1:])),
            "warnings": warnings + geometry_warnings,
        })
    if not roads:
        raise ValueError("No se encontraron vías vehiculares utilizables")
    return {
        "roads": roads, "omitted": omitted, "nodes": len(nodes),
        "total_ways": len(seen_ids), "highway_ways": highway_count,
        "origin_utm_m": origin,
        "osm_sha256": hashlib.sha256(OSM_PATH.read_bytes()).hexdigest(),
    }


def scene_fingerprint(bpy):
    """Firma del trabajo previo para verificar que se conserva."""
    objects = {}
    for obj in bpy.context.scene.objects:
        geometry = None
        if obj.type == "MESH":
            geometry = (
                [tuple(v.co) for v in obj.data.vertices],
                [tuple(p.vertices) for p in obj.data.polygons],
            )
        objects[obj.name] = {
            "matrix": [list(row) for row in obj.matrix_world],
            "data": obj.data.name if obj.data else None,
            "geometry": geometry,
            "materials": [s.material.name if s.material else None for s in obj.material_slots],
            "collections": sorted(c.name for c in obj.users_collection),
            "hidden": [obj.hide_viewport, obj.hide_render, obj.hide_get()],
        }
    collections = {
        c.name: {"objects": sorted(o.name for o in c.objects),
                 "children": sorted(child.name for child in c.children),
                 "hidden": [c.hide_viewport, c.hide_render]}
        for c in bpy.data.collections
    }
    return {"objects": objects, "collections": collections,
            "unit_scale": bpy.context.scene.unit_settings.scale_length}


def prepare():
    """Valida, respalda la escena anterior y prepara la colección nueva."""
    import bpy
    global _SESSION
    if _SESSION is not None:
        raise RuntimeError("Ya hay una sesión en este módulo")
    if bpy.data.collections.get(COLLECTION_NAME):
        raise RuntimeError(f"Ya existe {COLLECTION_NAME}; no se modificará")
    data = analyze()
    before = scene_fingerprint(bpy)
    backup = None
    if len(bpy.context.scene.objects):
        backup_dir = ROOT / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / ("antes_calles_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)
        if not backup.is_file() or backup.stat().st_size == 0:
            raise RuntimeError("No se pudo verificar la copia de seguridad")
    collection = bpy.data.collections.new(COLLECTION_NAME)
    bpy.context.scene.collection.children.link(collection)
    collection["source_osm"] = str(OSM_PATH)
    collection["source_sha256"] = data["osm_sha256"]
    collection["crs"] = "EPSG:32721"
    collection["origin_lat"] = ORIGIN_LAT
    collection["origin_lon"] = ORIGIN_LON
    collection["origin_easting_m"], collection["origin_northing_m"] = data["origin_utm_m"]
    collection["axes"] = "X este UTM; Y norte de cuadrícula UTM; Z arriba"
    collection["width_defaults_m"] = json.dumps(DEFAULT_WIDTHS_M)
    collection["backup_path"] = str(backup) if backup else ""
    collection["surface_note"] = "Asfalto provisional uniforme; conservar surface original en osm_tags"
    collection["junctions"] = "Cintas superpuestas; sin unión booleana"
    material = bpy.data.materials.new("BARA_DRIVE_Asfalto")
    material.use_nodes = True
    shader = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    shader.inputs["Base Color"].default_value = ASPHALT_RGBA
    shader.inputs["Roughness"].default_value = 0.92
    material.diffuse_color = ASPHALT_RGBA
    _SESSION = {
        "data": data, "before": before, "backup": str(backup) if backup else None,
        "collection": collection, "material": material,
        "scale": bpy.context.scene.unit_settings.scale_length,
        "processed": [], "errors": [], "stopped": False,
    }
    return {"backup": _SESSION["backup"], "ready": len(data["roads"]),
            "omitted": len(data["omitted"]), "origin_utm_m": data["origin_utm_m"]}


def build_batch(count=BATCH_SIZE):
    """Construye un lote y se detiene inmediatamente si aparece un error."""
    import bpy
    s = _SESSION
    if s is None or s["stopped"]:
        raise RuntimeError("Sesión no preparada o detenida por error")
    if not isinstance(count, int) or not 1 <= count <= BATCH_SIZE:
        raise ValueError(f"El lote debe tener entre 1 y {BATCH_SIZE} vías")
    created = []
    start = len(s["processed"])
    for road in s["data"]["roads"][start:start + count]:
        try:
            name = f"Calle_{road['id']}_{road['tags'].get('name', 'Servicio')}"
            points, scale = road["points"], s["scale"]
            cx = math.fsum(p[0] for p in points) / len(points)
            cy = math.fsum(p[1] for p in points) / len(points)
            vertices = [((x-cx)/scale, (y-cy)/scale, z/scale) for x,y,z in road["vertices"]]
            mesh = bpy.data.meshes.new(name + "_Mesh")
            mesh.from_pydata(vertices, [], road["faces"])
            mesh.update()
            if mesh.validate():
                raise RuntimeError("Blender detectó geometría inválida")
            obj = bpy.data.objects.new(name, mesh)
            s["collection"].objects.link(obj)
            obj.location = (cx/scale, cy/scale, 0)
            mesh.materials.append(s["material"])
            obj["osm_way_id"] = road["id"]
            obj["osm_tags"] = json.dumps(road["tags"], ensure_ascii=False)
            obj["osm_node_ids"] = json.dumps(road["node_ids"])
            obj["width_m"] = road["width_m"]
            obj["width_source"] = road["width_source"]
            obj["length_m"] = road["length_m"]
            obj["warnings"] = json.dumps(road["warnings"], ensure_ascii=False)
            s["processed"].append({"id": road["id"], "object": obj.name,
                "name": road["tags"].get("name"), "highway": road["tags"]["highway"],
                "width_m": road["width_m"], "width_source": road["width_source"],
                "length_m": round(road["length_m"], 3), "vertices": len(mesh.vertices),
                "triangles": len(mesh.polygons), "warnings": road["warnings"]})
            created.append(obj.name)
        except Exception as exc:
            s["errors"].append({"way_id": road["id"], "error": str(exc)})
            s["stopped"] = True
            raise
    bpy.context.view_layer.update()
    return {"created": created, "processed": len(s["processed"]),
            "remaining": len(s["data"]["roads"]) - len(s["processed"]), "errors": s["errors"]}


def finish():
    """Comprueba ejes, mallas y conservación del trabajo previo; escribe informe."""
    import bpy
    from mathutils import Vector
    s = _SESSION
    if s is None or s["stopped"] or len(s["processed"]) != len(s["data"]["roads"]):
        raise RuntimeError("La generación no está completa")
    after = scene_fingerprint(bpy)
    for category in ("objects", "collections"):
        for name, value in s["before"][category].items():
            if after[category].get(name) != value:
                raise RuntimeError(f"Se alteró trabajo previo: {category}/{name}")
    if after["unit_scale"] != s["before"]["unit_scale"]:
        raise RuntimeError("Cambió la escala de la escena")
    max_error = 0.0
    for road, record in zip(s["data"]["roads"], s["processed"]):
        obj = bpy.data.objects[record["object"]]
        if list(obj.users_collection) != [s["collection"]]:
            raise RuntimeError("Objeto vinculado a una colección inesperada")
        if len(obj.data.vertices) != len(road["vertices"]) or len(obj.data.polygons) != len(road["faces"]):
            raise RuntimeError("Conteo de geometría incorrecto")
        for i, point in enumerate(road["points"][:len(obj.data.vertices)//2]):
            midpoint = (obj.data.vertices[2*i].co + obj.data.vertices[2*i+1].co) / 2
            world = obj.matrix_world @ midpoint
            error = (world * s["scale"] - Vector((*point, SURFACE_Z_M))).length
            max_error = max(max_error, error)
        if any(p.area <= 0 or p.normal.z < 0.99 for p in obj.data.polygons):
            raise RuntimeError("Triángulo degenerado o normal invertida")
    if max_error > 0.001:
        raise RuntimeError(f"Desviación del eje mayor a 1 mm: {max_error}")
    data = s["data"]
    report = {
        "source": str(OSM_PATH), "source_sha256": data["osm_sha256"],
        "collection": COLLECTION_NAME, "backup": s["backup"],
        "projection": "WGS84 / UTM zone 21S (EPSG:32721), Snyder series",
        "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON,
                   "easting_m": data["origin_utm_m"][0], "northing_m": data["origin_utm_m"][1]},
        "axes": "X este UTM; Y norte de cuadrícula UTM; Z arriba",
        "width_configuration": {"highway": DEFAULT_WIDTHS_M, "lane_width_m": LANE_WIDTH_M,
                                "edge_allowance_per_side_m": EDGE_ALLOWANCE_M},
        "total_osm_ways": data["total_ways"], "highway_ways": data["highway_ways"],
        "processed": len(s["processed"]), "omitted": len(data["omitted"]),
        "omitted_by_reason": dict(Counter(r["reason"] for r in data["omitted"])),
        "omitted_details": data["omitted"], "errors": s["errors"],
        "existing_scene_preserved": True, "max_centerline_error_m": max_error,
        "objects": len(s["collection"].objects),
        "vertices": sum(r["vertices"] for r in s["processed"]),
        "triangles": sum(r["triangles"] for r in s["processed"]),
        "roads": s["processed"],
        "notes": ["Sin recorte de vías al bounds del archivo", "Anchos provisionales salvo width explícito",
                  "Superficie plana Z=0; sin datos de elevación", "Cruces superpuestos, sin unión booleana",
                  "Material asfalto uniforme solicitado; surface original conservado en osm_tags"],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    s["collection"]["report_path"] = str(REPORT_PATH)
    s["collection"]["generation_complete"] = True
    return {k: v for k, v in report.items() if k not in {"roads", "omitted_details", "width_configuration"}}


if __name__ == "__main__":
    print(json.dumps(prepare(), ensure_ascii=False))
    while len(_SESSION["processed"]) < len(_SESSION["data"]["roads"]):
        print(json.dumps(build_batch(), ensure_ascii=False))
    print(json.dumps(finish(), ensure_ascii=False, indent=2))
