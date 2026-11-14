"""Inspección de solo lectura. No requiere Shapely ni modifica la escena."""
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from generar_calles import utm21s


def tags(element):
    return {tag.get("k"): tag.get("v") for tag in element.findall("tag")}


def load_osm(path):
    root = ET.parse(path).getroot()
    if root.tag != "osm":
        raise ValueError("La entrada no es XML OSM")
    nodes = {n.get("id"): {"lat": float(n.get("lat")), "lon": float(n.get("lon")),
                          "tags": tags(n)} for n in root.findall("node")}
    ways = {w.get("id"): {"id": w.get("id"), "tags": tags(w),
                         "refs": [n.get("ref") for n in w.findall("nd")]}
            for w in root.findall("way")}
    missing = {key: [ref for ref in w["refs"] if ref not in nodes]
               for key, w in ways.items() if any(ref not in nodes for ref in w["refs"])}
    if missing:
        raise ValueError(f"Referencias OSM incompletas: {missing}")
    return {"nodes": nodes, "ways": ways, "relations": root.findall("relation"),
            "bounds": root.find("bounds").attrib if root.find("bounds") is not None else None,
            "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def mesh_signature(obj):
    """Detecta cambios manuales, también de topología, UV y materiales."""
    content = {"type": obj.type, "matrix": [list(row) for row in obj.matrix_world]}
    if obj.type == "MESH":
        content.update(vertices=[list(v.co) for v in obj.data.vertices],
                       faces=[list(p.vertices) for p in obj.data.polygons],
                       edges=[list(e.vertices) for e in obj.data.edges],
                       materials=[m.name if m else None for m in obj.data.materials])
    elif obj.type == "CURVE":
        content["splines"] = [[list(p.co) for p in s.bezier_points] if s.bezier_points
                              else [list(p.co) for p in s.points] for s in obj.data.splines]
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def inspect(bpy, config, osm_path):
    scene = bpy.context.scene
    source = bpy.data.collections.get(config["source_collection"])
    if source is None:
        raise ValueError("No se encontró la colección fuente; indicar source_collection en la configuración")
    if source.get("crs") != "EPSG:32721":
        raise ValueError("No hay metadatos UTM 21S verificables. No se adivinará el CRS")
    origin_lat, origin_lon = float(source["origin_lat"]), float(source["origin_lon"])
    east, north = utm21s(origin_lon, origin_lat)
    for key, computed in [("origin_easting_m", east), ("origin_northing_m", north)]:
        if abs(float(source[key]) - computed) > 0.001:
            raise ValueError("El origen geográfico no coincide con el origen métrico guardado")
    scale = scene.unit_settings.scale_length
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Escala inválida")
    osm = load_osm(osm_path)
    for node in osm["nodes"].values():
        e, n = utm21s(node["lon"], node["lat"])
        node["xy"] = (e - east, n - north)
    objects = []
    max_error = 0.0
    matched = set()
    for obj in scene.objects:
        entry = {"name": obj.name, "type": obj.type, "collections": [c.name for c in obj.users_collection],
                 "location": list(obj.location), "rotation_euler": list(obj.rotation_euler),
                 "scale": list(obj.scale), "matrix_world": [list(row) for row in obj.matrix_world],
                 "dimensions_m": [v * scale for v in obj.dimensions], "signature": mesh_signature(obj)}
        if obj.type == "MESH":
            entry.update(vertices=len(obj.data.vertices), edges=len(obj.data.edges), faces=len(obj.data.polygons))
            entry["geometry"] = "surface_mesh" if obj.data.polygons else "edge_lines"
        elif obj.type == "CURVE":
            entry.update(geometry="curve", splines=len(obj.data.splines), bevel_depth=obj.data.bevel_depth)
        way_id = str(obj.get("osm_way_id", ""))
        entry["osm_way_id"] = way_id or None
        if way_id and obj in list(source.objects):
            if way_id not in osm["ways"]:
                raise ValueError(f"La fuente OSM no contiene la vía importada {way_id}")
            refs = osm["ways"][way_id]["refs"]
            # Formato del importador existente: dos bordes simétricos por nodo.
            if obj.type != "MESH" or len(obj.data.vertices) != 2 * len(refs):
                raise ValueError(f"No se puede verificar automáticamente el eje de {obj.name}; se requiere adaptar el lector")
            errors = []
            for i, ref in enumerate(refs):
                p = obj.matrix_world @ ((obj.data.vertices[2*i].co + obj.data.vertices[2*i+1].co) / 2)
                x, y = osm["nodes"][ref]["xy"]
                errors.append(math.dist((p.x*scale, p.y*scale, p.z*scale), (x, y, 0)))
            error = max(errors)
            max_error = max(max_error, error)
            entry["alignment_error_m"] = error
            matched.add(way_id)
        objects.append(entry)
    if not matched or max_error > config["alignment_tolerance_m"]:
        raise ValueError(f"La fuente OSM no coincide con la escena (error {max_error} m)")
    roadways = [w for w in osm["ways"].values() if "highway" in w["tags"]]
    plaza = osm["ways"].get(config["plaza_osm_way_id"])
    report = {
        "blender_version": bpy.app.version_string,
        "compatibility": "APIs comunes de 4.2 y 5.2. Probado solo en la versión registrada en este informe.",
        "source_blend": bpy.data.filepath, "scene": scene.name,
        "units": {"system": scene.unit_settings.system, "scale_length": scale},
        "crs": "EPSG:32721", "origin": {"lat": origin_lat, "lon": origin_lon, "easting_m": east, "northing_m": north},
        "axes": "X este UTM; Y norte de cuadrícula UTM; Z arriba",
        "objects": objects,
        "collections": [{"name": c.name, "objects": [o.name for o in c.objects],
                         "children": [child.name for child in c.children]} for c in bpy.data.collections],
        "osm": {"path": str(osm_path), "sha256": osm["sha256"], "bounds": osm["bounds"],
                "nodes": len(osm["nodes"]), "ways": len(osm["ways"]), "relations": len(osm["relations"]),
                "roads": len(roadways), "highway_classes": dict(Counter(w["tags"]["highway"] for w in roadways)),
                "buildings": sum(w["tags"].get("building", "no") != "no" for w in osm["ways"].values()),
                "plaza": plaza,
                "traffic_signals": sum(n["tags"].get("highway") == "traffic_signals" for n in osm["nodes"].values()),
                "trees": sum(n["tags"].get("natural") == "tree" for n in osm["nodes"].values()),
                "benches": sum(n["tags"].get("amenity") == "bench" for n in osm["nodes"].values()),
                "street_lamps": sum(n["tags"].get("highway") == "street_lamp" for n in osm["nodes"].values())},
        "alignment": {"matched_ways": len(matched), "max_error_m": max_error},
        "limitations": ["OSM del centro, no toda la ciudad", "Sin modelo digital de elevación: cota relativa Z=0",
                        "Anchos de calzada/vereda y altura de cordón estimados configurables",
                        "No inferir superficies, mobiliario o monumentos de Plaza Mitre de sus nombres o polígonos"]}
    return report, osm, matched


def markdown(report):
    return f'''# Diagnóstico del mapa BARA-DRIVE

- Archivo inspeccionado: `{report['source_blend']}`.
- Blender conectado: **{report['blender_version']}**. No se comprobó ejecución en 5.2.
- Escena: {len(report['objects'])} objetos; colecciones: {', '.join(c['name'] for c in report['collections'])}.
- Calles verificadas: **{report['alignment']['matched_ways']} mallas con caras**, no curvas ni líneas sueltas.
- Máxima diferencia de los ejes frente al OSM: **{report['alignment']['max_error_m']:.6f} m**.
- CRS: **{report['crs']}**; origen lat/lon: {report['origin']['lat']}, {report['origin']['lon']}.
- Escala: {report['units']['scale_length']} metros por unidad; {report['axes']}.
- OSM: {report['osm']['nodes']} nodos, {report['osm']['roads']} vías highway y {report['osm']['buildings']} edificios.
- Plaza Mitre: way/{report['osm']['plaza']['id'] if report['osm']['plaza'] else 'NO ENCONTRADA'}.
- Árboles individuales: {report['osm']['trees']}; bancos: {report['osm']['benches']}; luminarias: {report['osm']['street_lamps']}.

## Limitaciones verificadas

''' + "\n".join(f"- {line}" for line in report["limitations"]) + "\n\nEl JSON asociado incluye todas las transformaciones, firmas y topologías originales.\n"
