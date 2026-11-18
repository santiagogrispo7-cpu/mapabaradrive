"""Fase 2: calzadas, cordones y veredas derivadas de los ejes OSM importados.

El eje de cada calzada se obtiene de la propia malla original (promedio de los
dos bordes por nodo), no de una reconstruccion: la geometria queda exactamente
donde estaba. El ancho sale de `width`, luego de `lanes` y, en su defecto, del
valor configurable por clase `highway`. Los cruces se resuelven con la union de
las cintas; no se agregan conexiones que no existan en el OSM.

Las veredas y cordones se obtienen de los buffers exteriores de esa union, de
modo que las esquinas siguen el perimetro real de la red y no hay veredas
cruzando las bocas de las intersecciones.
"""
from __future__ import annotations

import re
from collections import defaultdict

from . import geometry
from .common import clear_generated, ensure_collection, materials

LAYER_NAMES = ("CALZADA", "CORDON", "VEREDA")
LAYER_FOLDERS = {"CALZADA": "CALLES", "CORDON": "CORDONES", "VEREDA": "VEREDAS"}


def parse_metres(value):
    """Acepta `7`, `7.5`, `7,5` y `7 m`; cualquier otra forma se ignora."""
    if value is None:
        return None
    text = str(value).strip().lower().replace(",", ".")
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(m|meters?|metres?)?", text)
    if not match:
        return None
    number = float(match.group(1))
    return number if number > 0 else None


def road_width(tags, config):
    """Ancho de calzada y su procedencia, sin inventar datos faltantes."""
    explicit = parse_metres(tags.get("width"))
    if explicit is not None:
        return explicit, "osm:width"
    highway = tags.get("highway", "")
    defaults = config["widths_m_estimated"]
    if highway not in defaults:
        raise ValueError(
            f"Clase highway sin ancho configurado: {highway!r}. "
            "Agregar widths_m_estimated o excluirla explicitamente en mapa_config.json")
    base = float(defaults[highway])
    lanes = parse_metres(tags.get("lanes"))
    if lanes is not None and lanes >= 2:
        # `lanes` se usa como minimo: un valor menor no angosta la clase.
        candidate = lanes * float(config["lane_width_m_estimated"]) + \
            2.0 * float(config["road_edge_allowance_m_estimated"])
        if candidate > base:
            return candidate, "osm:lanes"
    return base, "class_default"


def _centreline(obj, unit_scale, tolerance=1e-4):
    """Promedio de cada par de vertices de borde de la malla importada."""
    if obj.type != "MESH":
        raise ValueError(f"La via {obj.name} no es una malla")
    vertices = obj.data.vertices
    if len(vertices) < 4 or len(vertices) % 2:
        raise ValueError(
            f"La via {obj.name} no tiene el formato de dos bordes por nodo "
            f"({len(vertices)} vertices)")
    points = []
    for index in range(0, len(vertices), 2):
        left = obj.matrix_world @ vertices[index].co
        right = obj.matrix_world @ vertices[index + 1].co
        x = (left.x + right.x) * 0.5 * unit_scale
        y = (left.y + right.y) * 0.5 * unit_scale
        if not points or abs(x - points[-1][0]) > tolerance or abs(y - points[-1][1]) > tolerance:
            points.append((x, y))
    if len(points) < 2:
        raise ValueError(f"La via {obj.name} quedo con menos de dos nodos utiles")
    return points


def collect_ways(bpy, config, osm):
    """Lee las 28 (o las que haya) vias importadas y arma sus superficies."""
    scene = bpy.context.scene
    unit_scale = float(scene.unit_settings.scale_length)
    if abs(unit_scale - 1.0) > 1e-9:
        raise ValueError(
            f"scale_length={unit_scale}: el pipeline no reescala la escena. "
            "Ajustar a 1.0 o adaptar la conversion de unidades")
    source = bpy.data.collections.get(config["source_collection"])
    if source is None:
        raise ValueError(f"No existe la coleccion fuente {config['source_collection']}")

    ways = {}
    skipped = []
    for obj in list(source.objects):
        way_id = str(obj.get("osm_way_id", "") or "")
        if not way_id:
            skipped.append({"object": obj.name, "reason": "sin osm_way_id"})
            continue
        way = osm["ways"].get(way_id)
        if way is None:
            raise ValueError(f"La via importada {way_id} ({obj.name}) no esta en el OSM")
        tags = way["tags"]
        if "highway" not in tags:
            skipped.append({"object": obj.name, "way_id": way_id, "reason": "sin highway"})
            continue
        points = _centreline(obj, unit_scale)
        width, width_source = road_width(tags, config)
        surface = geometry.clean(geometry.ribbon(points, width))
        if surface.is_empty or surface.area <= config["min_polygon_area_m2"]:
            raise ValueError(f"La superficie de {obj.name} ({way_id}) quedo vacia")
        ways[way_id] = {
            "way_id": way_id,
            "object": obj.name,
            "name": tags.get("name", ""),
            "highway": tags.get("highway", ""),
            "lanes": tags.get("lanes"),
            "width_m": round(width, 3),
            "width_source": width_source,
            "length_m": round(geometry.line_length(points), 3),
            "node_count": len(points),
            "surface": surface,
            "_points": points,
        }
    if not ways:
        raise ValueError("No se encontro ninguna calzada importada para generar")
    return ways, skipped


def _layer_geometries(roads, config, logger):
    """Calzada, cordon y vereda como tres solidos sin superposicion."""
    curb_width = float(config["curb_width_m_estimated"])
    sidewalk_width = float(config["sidewalk_width_m_estimated"])
    resolution = int(config.get("buffer_resolution", 12))
    overlap = float(config["curb_overlap_m"])

    def buffer_of(shape, distance):
        return geometry.clean(
            shape.buffer(distance, join_style="round", resolution=resolution))

    road = geometry.clean(roads)
    curb_outer = buffer_of(road, curb_width)
    curb_inner = buffer_of(road, -overlap)
    curb = geometry.clean(curb_outer.difference(curb_inner))
    sidewalk_outer = buffer_of(road, curb_width + sidewalk_width)
    sidewalk = geometry.clean(sidewalk_outer.difference(curb_outer))
    logger.info(
        "Areas calculadas: calzada %.1f m2, cordon %.1f m2, vereda %.1f m2",
        geometry.area(road), geometry.area(curb), geometry.area(sidewalk))
    return {"CALZADA": road, "CORDON": curb, "VEREDA": sidewalk}


def _mesh_from_polygons(bpy, name, collection, polygons, z_bottom, z_top,
                        material, layer, tile, min_area, vertices_hint=None):
    vertices = []
    faces = []
    for polygon in polygons:
        part_vertices, part_faces = geometry.prism(polygon, z_bottom, z_top, min_area)
        offset = len(vertices)
        vertices.extend(part_vertices)
        faces.extend(tuple(index + offset for index in face) for face in part_faces)
    if not faces:
        return None
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=False, clean_customdata=True)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    obj["bara_generated"] = True
    obj["bara_phase"] = 2
    obj["bara_layer"] = layer
    obj["bara_tile"] = tile
    obj["bara_crs"] = "EPSG:32721"
    obj["bara_units"] = "m"
    obj["bara_z_top_m"] = float(z_top)
    obj["bara_area_m2"] = float(sum(p.area for p in polygons))
    if vertices_hint:
        obj["bara_source_way_count"] = int(vertices_hint)
    return obj


def build(bpy, config, osm, logger):
    """Genera los tres estratos, agrupados por tesela, sin duplicar al repetir."""
    removed = clear_generated(bpy, config["root_collection"])
    if removed:
        logger.info("Se retiraron %d objetos generados en una corrida anterior", removed)

    scene = bpy.context.scene
    root = ensure_collection(bpy, config["root_collection"], scene.collection)
    folders = {layer: ensure_collection(bpy, folder, root)
               for layer, folder in LAYER_FOLDERS.items()}
    root["bara_crs"] = "EPSG:32721"
    root["bara_units"] = "m"
    root["bara_phase"] = 2

    ways, skipped = collect_ways(bpy, config, osm)
    roads = geometry.union([way["surface"] for way in ways.values()])
    if roads.is_empty:
        raise ValueError("La union de calzadas quedo vacia")
    layers = _layer_geometries(roads, config, logger)

    palette = materials(bpy)
    specs = {
        "CALZADA": (float(config["road_bottom_z_m"]), float(config["road_top_z_m"]),
                    palette["BARA_Asfalto"]),
        "CORDON": (float(config["road_bottom_z_m"]), float(config["curb_top_z_m"]),
                   palette["BARA_Cordon"]),
        "VEREDA": (float(config["road_bottom_z_m"]), float(config["sidewalk_top_z_m"]),
                   palette["BARA_Hormigon"]),
    }
    tile_size = float(config["tile_size_m"])
    min_area = float(config["min_polygon_area_m2"])
    report_layers = {}
    for layer in LAYER_NAMES:
        z_bottom, z_top, material = specs[layer]
        groups = defaultdict(list)
        for tile, polygon in geometry.tiled(layers[layer], tile_size):
            if polygon.area >= min_area:
                groups[tile].append(polygon)
        names = []
        layer_area = 0.0
        for tile in sorted(groups):
            name = f"{layer}_{tile}"
            obj = _mesh_from_polygons(
                bpy, name, folders[layer], groups[tile], z_bottom, z_top,
                material, layer, tile, min_area, vertices_hint=len(ways))
            if obj is None:
                continue
            names.append(obj.name)
            layer_area += float(obj["bara_area_m2"])
        report_layers[layer] = {
            "objects": len(names),
            "tiles": sorted(groups),
            "area_m2": round(layer_area, 3),
            "z_top_m": z_top,
            "z_bottom_m": z_bottom,
            "material": material.name,
        }
        logger.info("Capa %s: %d objetos, %.1f m2", layer, len(names), layer_area)

    way_report = []
    for way in ways.values():
        way_report.append({key: value for key, value in way.items()
                           if key not in ("surface", "_points")})
        way_report[-1]["surface_area_m2"] = round(float(way["surface"].area), 3)
    report = {
        "phase": 2,
        "generated_by": "scripts/mapa_baradero/streets.py",
        "blender_version": bpy.app.version_string,
        "source_blend": bpy.data.filepath,
        "crs": "EPSG:32721",
        "axes": "X este UTM; Y norte de cuadricula UTM; Z arriba",
        "units": "metros (scale_length=1)",
        "source_collection": config["source_collection"],
        "root_collection": config["root_collection"],
        "source_ways": len(ways),
        "skipped_source_objects": skipped,
        "ways": sorted(way_report, key=lambda item: item["way_id"]),
        "layers": report_layers,
        "road_union_area_m2": round(geometry.area(roads), 3),
        "tile_size_m": tile_size,
        "dimensions_m_estimated": {
            "sidewalk_width": config["sidewalk_width_m_estimated"],
            "curb_width": config["curb_width_m_estimated"],
            "curb_height": config["curb_top_z_m"],
            "lane_width": config["lane_width_m_estimated"],
            "road_edge_allowance": config["road_edge_allowance_m_estimated"],
            "class_widths": config["widths_m_estimated"],
        },
        "limitations": [
            "Sin modelo digital de elevacion: todas las calles quedan a la misma cota relativa",
            "Anchos de calzada por clase, veredas y cordones son estimaciones configurables",
            "El OSM no incluye cordones ni veredas: se derivan del perimetro de la calzada",
            "Las bocas de las calles en el borde del extracto OSM reciben vereda de cierre",
            "Los objetos originales BARA_DRIVE_CALLES se conservan sin modificar",
        ],
    }
    return report
