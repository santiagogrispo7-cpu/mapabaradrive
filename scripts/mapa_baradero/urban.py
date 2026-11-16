"""Entorno urbano de prueba para Baradero: manzanas, edificios, arbolado y mobiliario.

Los edificios generados aqui son PROVISIONALES: no representan construcciones
reales de Baradero. Solo se usan para poblar una zona de prueba con volumenes,
fachadas, ventanas, puertas y techos. El OSM no aporta alturas ni uso de esos
lotes, asi que dimensiones y colores son estimados y configurables.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polygonize, unary_union
from shapely.wkt import dumps as wkt_dumps

from . import geometry, streets
from .common import clear_generated, ensure_collection, make_material

URBAN_FOLDERS = (
    "TERRENO", "EDIFICIOS", "VEGETACION", "ILUMINACION", "SEÑALES", "CAMARAS",
)

FACADE_SPECS = (
    ("BARA_Fachada_Arena", (0.62, 0.51, 0.35)),
    ("BARA_Fachada_Terracota", (0.47, 0.20, 0.13)),
    ("BARA_Fachada_Celeste", (0.36, 0.50, 0.58)),
    ("BARA_Fachada_Crema", (0.72, 0.68, 0.56)),
    ("BARA_Fachada_Oliva", (0.34, 0.38, 0.22)),
    ("BARA_Fachada_Rosa", (0.60, 0.34, 0.34)),
)

BUILDING_TYPES = ("casa_1p", "casa_2p", "comercio")


def _palette(bpy):
    palette = {name: make_material(bpy, name, color, 0.82)
               for name, color in FACADE_SPECS}
    palette.update({
        "roof": make_material(bpy, "BARA_Techo_Pizarra", (0.075, 0.085, 0.10), 0.88),
        "tile": make_material(bpy, "BARA_Techo_Teja", (0.31, 0.11, 0.07), 0.85),
        "glass": make_material(bpy, "BARA_Vidrio", (0.055, 0.095, 0.13), 0.18, 0.25),
        "door": make_material(bpy, "BARA_Madera", (0.20, 0.105, 0.045), 0.72),
        "ground": make_material(bpy, "BARA_Terreno", (0.115, 0.155, 0.085), 0.95),
        "trunk": make_material(bpy, "BARA_Tronco", (0.14, 0.075, 0.035), 0.9),
        "leaf": make_material(bpy, "BARA_Follaje", (0.085, 0.26, 0.09), 0.86),
        "metal": make_material(bpy, "BARA_Metal", (0.055, 0.06, 0.065), 0.42, 0.75),
        "light": make_material(bpy, "BARA_Luz", (0.92, 0.83, 0.56), 0.3,
                               emission=(1.0, 0.82, 0.42), emission_strength=2.0),
        "red": make_material(bpy, "BARA_Senal_Rojo", (0.52, 0.025, 0.02), 0.55),
        "white": make_material(bpy, "BARA_Senal_Blanco", (0.88, 0.88, 0.86), 0.6),
    })
    return palette


def _rotated_rect(cx, cy, width, depth, angle):
    c, s = math.cos(angle), math.sin(angle)
    points = []
    for u, v in ((-width / 2, -depth / 2), (width / 2, -depth / 2),
                 (width / 2, depth / 2), (-width / 2, depth / 2)):
        points.append((cx + u * c - v * s, cy + u * s + v * c))
    return Polygon(points)


def _block_angle(polygon):
    rectangle = polygon.minimum_rotated_rectangle
    coords = list(rectangle.exterior.coords)
    edges = [(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
             for i in range(4)]
    dx, dy = max(edges, key=lambda edge: edge[0] ** 2 + edge[1] ** 2)
    angle = math.atan2(dy, dx)
    while angle > math.pi / 2:
        angle -= math.pi
    while angle <= -math.pi / 2:
        angle += math.pi
    return angle


def _centreline_blocks(ways):
    lines = [LineString(way["_points"]) for way in ways.values()
             if len(way["_points"]) >= 2]
    if not lines:
        raise ValueError("No hay ejes de calle para calcular manzanas")
    merged = unary_union(lines)
    return [polygon for polygon in polygonize(merged)
            if polygon.is_valid and polygon.area >= 250.0]


def _plaza_polygon(osm, config):
    way = osm["ways"].get(str(config.get("plaza_osm_way_id", "")))
    if not way:
        return None
    points = []
    for ref in way["refs"]:
        node = osm["nodes"].get(ref)
        if node and "xy" in node:
            points.append(tuple(node["xy"]))
    if len(points) < 3:
        return None
    polygon = Polygon(points)
    return polygon if polygon.is_valid and polygon.area > 0 else None


def _select_blocks(ways, osm, config, logger):
    options = config.get("urban_test", {})
    setback = float(options.get("setback_m", 8.0))
    roads_bbox = unary_union([way["surface"] for way in ways.values()]).bounds
    center = Point(((roads_bbox[0] + roads_bbox[2]) / 2,
                    (roads_bbox[1] + roads_bbox[3]) / 2))
    plaza = _plaza_polygon(osm, config)
    candidates = []
    for block in _centreline_blocks(ways):
        if block.area < 450 or block.area > 26000:
            continue
        if plaza is not None:
            overlap = block.intersection(plaza.buffer(1.0)).area
            if overlap > block.area * 0.15:
                logger.info("Manzana de Plaza Mitre excluida de edificios (%.0f m2)", block.area)
                continue
        inner = block.buffer(-setback)
        inner_parts = list(geometry.polygon_parts(inner))
        if not inner_parts or max(part.area for part in inner_parts) < 120:
            continue
        distance = block.centroid.distance(center)
        candidates.append((distance, -block.area, block))
    candidates.sort(key=lambda item: (item[0], item[1]))
    if len(candidates) < 5:
        raise ValueError(
            f"Solo se encontraron {len(candidates)} manzanas cerradas; se necesitan 5")
    logger.info("Manzanas candidatas: %d (se usaran hasta %d)",
                len(candidates), int(options.get("max_blocks", 12)))
    return [block for _, _, block in candidates], center


def _place_buildings(blocks, corridor, config, rng, logger):
    options = config.get("urban_test", {})
    setback = float(options.get("setback_m", 8.0))
    target = int(options.get("target_buildings", 20))
    minimum = int(options.get("min_buildings", 15))
    max_per_block = int(options.get("max_per_block", 3))
    max_blocks = int(options.get("max_blocks", 12))
    placements = []
    used = []
    for block in blocks[:max_blocks]:
        if len(placements) >= target:
            break
        inner_parts = list(geometry.polygon_parts(block.buffer(-setback)))
        if not inner_parts:
            continue
        inner = max(inner_parts, key=lambda part: part.area)
        if inner.area < 120:
            continue
        angle = _block_angle(inner)
        safe = inner.buffer(-0.6)
        if safe.is_empty:
            continue
        local_count = 0
        attempts = 0
        while local_count < max_per_block and attempts < 400:
            attempts += 1
            minx, miny, maxx, maxy = safe.bounds
            x = rng.uniform(minx, maxx)
            y = rng.uniform(miny, maxy)
            if not safe.contains(Point(x, y)):
                continue
            width = rng.uniform(9.0, 13.5)
            depth = rng.uniform(8.0, 10.5)
            footprint = _rotated_rect(x, y, width, depth, angle)
            if not safe.contains(footprint):
                continue
            if footprint.distance(corridor) < 1.2:
                continue
            if any(footprint.distance(item["footprint"]) < 3.0 for item in placements):
                continue
            index = len(placements) + 1
            if index % 7 == 0:
                kind = "comercio"
            elif index % 2 == 0:
                kind = "casa_2p"
            else:
                kind = "casa_1p"
            placements.append({
                "index": index,
                "kind": kind,
                "center": (x, y),
                "width": width,
                "depth": depth,
                "angle": angle,
                "footprint": footprint,
                "block": block,
                "block_id": len(used) + 1,
            })
            local_count += 1
        if local_count:
            used.append(block)
    if len(placements) < minimum:
        raise ValueError(
            f"Solo se pudieron ubicar {len(placements)} edificios; se requieren {minimum}")
    logger.info("Edificios provisionales ubicados: %d en %d manzanas",
                len(placements), len(used))
    return placements, used


def _add_face(vertices, faces, materials, points, material_index):
    offset = len(vertices)
    vertices.extend(points)
    faces.append(tuple(range(offset, offset + len(points))))
    materials.append(material_index)


def _building_object(bpy, placement, palette, collection):
    index = placement["index"]
    kind = placement["kind"]
    width = placement["width"]
    depth = placement["depth"]
    angle = placement["angle"]
    cx, cy = placement["center"]
    floors = 2 if kind == "casa_2p" else 1
    height = 4.2 if kind == "comercio" else 3.2 * floors
    facade = palette[FACADE_SPECS[index % len(FACADE_SPECS)][0]]
    roof = palette["roof"] if kind == "comercio" else palette["tile"]

    c, s = math.cos(angle), math.sin(angle)
    vertices = []
    faces = []
    materials = []

    def world(u, v, z):
        return (cx + u * c - v * s, cy + u * s + v * c, z)

    corners = ((-width / 2, -depth / 2), (width / 2, -depth / 2),
               (width / 2, depth / 2), (-width / 2, depth / 2))
    bottom = [world(u, v, 0.0) for u, v in corners]
    top = [world(u, v, height) for u, v in corners]
    _add_face(vertices, faces, materials, (bottom[3], bottom[2], bottom[1], bottom[0]), 0)
    _add_face(vertices, faces, materials, (bottom[0], bottom[1], top[1], top[0]), 0)
    _add_face(vertices, faces, materials, (bottom[1], bottom[2], top[2], top[1]), 0)
    _add_face(vertices, faces, materials, (bottom[2], bottom[3], top[3], top[2]), 0)
    _add_face(vertices, faces, materials, (bottom[3], bottom[0], top[0], top[3]), 0)
    _add_face(vertices, faces, materials, (top[0], top[1], top[2], top[3]), 0)

    def window(side, u0, u1, z0, z1, offset=0.035):
        if side in ("front", "back"):
            v = -depth / 2 - offset if side == "front" else depth / 2 + offset
            points = (world(u0, v, z0), world(u1, v, z0),
                      world(u1, v, z1), world(u0, v, z1))
        else:
            u = -width / 2 - offset if side == "left" else width / 2 + offset
            points = (world(u, u0, z0), world(u, u1, z0),
                      world(u, u1, z1), world(u, u0, z1))
        _add_face(vertices, faces, materials, points, 2)

    def door(u0, u1):
        v = -depth / 2 - 0.04
        _add_face(vertices, faces, materials,
                  (world(u0, v, 0.03), world(u1, v, 0.03),
                   world(u1, v, 2.15), world(u0, v, 2.15)), 3)

    per_floor = 2 if width < 12 else 3
    for floor in range(floors):
        z0 = floor * 3.2 + 1.05
        z1 = z0 + 1.1
        if kind == "comercio" and floor == 0:
            window("front", -width / 2 + 1.0, -1.0, 0.55, 2.55)
            door(0.35, 1.5)
            continue
        for i in range(per_floor):
            u = -width / 2 + (i + 1) * width / (per_floor + 1)
            window("front", u - 0.55, u + 0.55, z0, z1)
            window("back", u - 0.55, u + 0.55, z0, z1)
        for side in ("left", "right"):
            window(side, -1.0, 1.0, z0, z1)
    if kind != "comercio":
        door(-0.6, 0.6)

    if kind == "comercio":
        overhang = 0.28
        slab = [world(u, v, height) for u, v in (
            (-width / 2 - overhang, -depth / 2 - overhang),
            (width / 2 + overhang, -depth / 2 - overhang),
            (width / 2 + overhang, depth / 2 + overhang),
            (-width / 2 - overhang, depth / 2 + overhang))]
        slab_top = [(x, y, z + 0.30) for x, y, z in slab]
        _add_face(vertices, faces, materials, (slab[0], slab[1], slab[2], slab[3]), 1)
        _add_face(vertices, faces, materials, (slab_top[3], slab_top[2],
                                              slab_top[1], slab_top[0]), 1)
        for i in range(4):
            j = (i + 1) % 4
            _add_face(vertices, faces, materials,
                      (slab[i], slab[j], slab_top[j], slab_top[i]), 1)
    else:
        overhang = 0.35
        eave = [world(u, v, height) for u, v in (
            (-width / 2 - overhang, -depth / 2 - overhang),
            (width / 2 + overhang, -depth / 2 - overhang),
            (width / 2 + overhang, depth / 2 + overhang),
            (-width / 2 - overhang, depth / 2 + overhang))]
        ridge_height = height + max(1.0, min(1.6, depth * 0.16))
        ridge = [world(-width / 2 - overhang, 0, ridge_height),
                 world(width / 2 + overhang, 0, ridge_height)]
        _add_face(vertices, faces, materials, (eave[0], eave[1], ridge[1], ridge[0]), 1)
        _add_face(vertices, faces, materials, (eave[2], eave[3], ridge[0], ridge[1]), 1)
        _add_face(vertices, faces, materials, (eave[0], ridge[0], eave[3]), 1)
        _add_face(vertices, faces, materials, (eave[1], eave[2], ridge[1]), 1)
        _add_face(vertices, faces, materials, (eave[3], eave[2], eave[1], eave[0]), 1)

    name = f"PROVISIONAL_EDIF_{index:02d}_{kind}"
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for position, polygon in enumerate(mesh.polygons):
        if position < len(materials):
            polygon.material_index = materials[position]
    mesh.validate(verbose=False, clean_customdata=True)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    for material in (facade, roof, palette["glass"], palette["door"]):
        obj.data.materials.append(material)
    obj["bara_generated"] = True
    obj["bara_provisional"] = True
    obj["bara_label"] = "PROVISIONAL"
    obj["bara_kind"] = kind
    obj["bara_floors"] = floors
    obj["bara_height_m"] = round(height + (1.2 if kind != "comercio" else 0.3), 2)
    obj["bara_block_id"] = placement["block_id"]
    obj["bara_footprint_m2"] = round(placement["footprint"].area, 2)
    obj["bara_footprint_wkt"] = wkt_dumps(placement["footprint"], rounding_precision=3)
    obj["bara_angle_deg"] = round(math.degrees(angle), 2)
    obj["bara_notice"] = "Edificio de prueba: no es un edificio real de Baradero"
    return obj


def _tree_mesh(bpy, palette):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8,
                          radius1=0.20, radius2=0.13, depth=2.8,
                          matrix=Matrix.Translation((0, 0, 1.4)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    existing = set(bm.faces)
    bmesh.ops.create_icosphere(
        bm, subdivisions=2, radius=1.0,
        matrix=Matrix.Translation((0, 0, 4.25)) @ Matrix.Diagonal((1.75, 1.75, 1.55, 1.0)))
    for face in set(bm.faces) - existing:
        face.material_index = 1
    for face in bm.faces:
        face.smooth = True
    mesh = bpy.data.meshes.new("BARA_ARBOL_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(palette["trunk"])
    mesh.materials.append(palette["leaf"])
    return mesh


def _lamp_mesh(bpy, palette):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8,
                          radius1=0.10, radius2=0.065, depth=5.2,
                          matrix=Matrix.Translation((0, 0, 2.6)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    existing = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8,
                          radius1=0.055, radius2=0.045, depth=1.0,
                          matrix=Matrix.Translation((0.45, 0, 5.15))
                          @ Matrix.Rotation(math.radians(90), 4, "Y"))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    existing = set(bm.faces)
    bmesh.ops.create_cube(
        bm, size=1.0,
        matrix=Matrix.Translation((0.95, 0, 5.02))
        @ Matrix.Diagonal((0.52, 0.28, 0.18, 1.0)))
    for face in set(bm.faces) - existing:
        face.material_index = 1
    mesh = bpy.data.meshes.new("BARA_POSTE_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(palette["metal"])
    mesh.materials.append(palette["light"])
    return mesh


def _sign_mesh(bpy, palette):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8,
                          radius1=0.055, radius2=0.045, depth=2.5,
                          matrix=Matrix.Translation((0, 0, 1.25)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    existing = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8,
                          radius1=0.47, radius2=0.47, depth=0.035,
                          matrix=Matrix.Translation((0, 0, 2.55))
                          @ Matrix.Rotation(math.radians(90), 4, "X"))
    for face in set(bm.faces) - existing:
        face.material_index = 2
    existing = set(bm.faces)
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=8,
                          radius1=0.39, radius2=0.39, depth=0.02,
                          matrix=Matrix.Translation((0, -0.03, 2.55))
                          @ Matrix.Rotation(math.radians(90), 4, "X"))
    for face in set(bm.faces) - existing:
        face.material_index = 1
    mesh = bpy.data.meshes.new("BARA_SENAL_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(palette["metal"])
    mesh.materials.append(palette["red"])
    mesh.materials.append(palette["white"])
    return mesh


def _sample_points(polygon, count, rng, minimum_distance, existing):
    if polygon is None or polygon.is_empty:
        return []
    minx, miny, maxx, maxy = polygon.bounds
    points = []
    attempts = 0
    while len(points) < count and attempts < 800:
        attempts += 1
        candidate = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if not polygon.contains(candidate):
            continue
        if any(candidate.distance(other) < minimum_distance for other in existing):
            continue
        if any(candidate.distance(other) < minimum_distance for other in points):
            continue
        points.append(candidate)
    return points


def _sidewalk_ring(block):
    outer = block.buffer(-4.4)
    inner = block.buffer(-5.6)
    if outer.is_empty or inner.is_empty:
        return None
    return geometry.clean(outer.difference(inner))


def _place_trees(bpy, blocks, palette, collection, rng, logger):
    options = {}
    mesh = _tree_mesh(bpy, palette)
    count = 0
    for block in blocks:
        ring = _sidewalk_ring(block)
        candidates = _sample_points(ring, 2, rng, 7.0, [])
        for point in candidates:
            count += 1
            obj = bpy.data.objects.new(f"ARBOL_{count:02d}", mesh)
            collection.objects.link(obj)
            scale = rng.uniform(0.82, 1.18)
            obj.location = (point.x, point.y, 0.15)
            obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
            obj.scale = (scale, scale, scale)
            obj["bara_generated"] = True
            obj["bara_kind"] = "arbol"
            obj["bara_provisional"] = True
    logger.info("Arboles generados: %d", count)
    return count


def _place_lamps(bpy, blocks, palette, collection, rng, logger, tree_points):
    mesh = _lamp_mesh(bpy, palette)
    count = 0
    placed = []
    for block in blocks:
        ring = _sidewalk_ring(block)
        candidates = _sample_points(ring, 2, rng, 10.0, placed + tree_points)
        for point in candidates:
            count += 1
            placed.append(point)
            obj = bpy.data.objects.new(f"POSTE_{count:02d}", mesh)
            collection.objects.link(obj)
            obj.location = (point.x, point.y, 0.15)
            obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
            obj["bara_generated"] = True
            obj["bara_kind"] = "poste_luz"
            obj["bara_provisional"] = True
    logger.info("Postes de luz generados: %d", count)
    return count


def _junction_nodes(osm, center, radius=280.0):
    uses = Counter(ref for way in osm["ways"].values() if "highway" in way["tags"]
                   for ref in way["refs"])
    nodes = []
    for ref, count in uses.items():
        if count < 2:
            continue
        node = osm["nodes"].get(ref)
        if not node or "xy" not in node:
            continue
        point = Point(node["xy"])
        if point.distance(center) <= radius:
            nodes.append((point.distance(center), point))
    nodes.sort(key=lambda item: item[0])
    return [point for _, point in nodes]


def _place_signs(bpy, blocks, osm, center, palette, collection, logger):
    mesh = _sign_mesh(bpy, palette)
    count = 0
    for node in _junction_nodes(osm, center)[:8]:
        target = min(blocks, key=lambda block: block.exterior.distance(node))
        nearest = target.exterior.interpolate(target.exterior.project(node))
        inward = target.representative_point()
        direction = Point(inward.x - nearest.x, inward.y - nearest.y)
        length = math.hypot(direction.x, direction.y)
        if length <= 0.01:
            continue
        sign_point = Point(nearest.x + direction.x / length * 5.0,
                           nearest.y + direction.y / length * 5.0)
        if not target.contains(sign_point):
            continue
        dx, dy = node.x - sign_point.x, node.y - sign_point.y
        angle = math.atan2(dx, -dy)
        count += 1
        obj = bpy.data.objects.new(f"SENAL_{count:02d}", mesh)
        collection.objects.link(obj)
        obj.location = (sign_point.x, sign_point.y, 0.15)
        obj.rotation_euler = (0, 0, angle)
        obj["bara_generated"] = True
        obj["bara_kind"] = "senal_transito"
        obj["bara_provisional"] = True
        if count >= 6:
            break
    logger.info("Senales de transito generadas: %d", count)
    return count


def _ground(bpy, ways, palette, collection):
    bounds = unary_union([way["surface"] for way in ways.values()]).bounds
    margin = 80.0
    minx, miny = bounds[0] - margin, bounds[1] - margin
    maxx, maxy = bounds[2] + margin, bounds[3] + margin
    mesh = bpy.data.meshes.new("TERRENO_BASE")
    mesh.from_pydata([(minx, miny, -0.02), (maxx, miny, -0.02),
                      (maxx, maxy, -0.02), (minx, maxy, -0.02)], [],
                     [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new("TERRENO_BASE", mesh)
    collection.objects.link(obj)
    obj.data.materials.append(palette["ground"])
    obj["bara_generated"] = True
    obj["bara_kind"] = "terreno"
    obj["bara_provisional"] = True
    return obj


def _setup_view(bpy, root, center, span, palette, logger):
    from mathutils import Vector

    scene = bpy.context.scene
    cameras = ensure_collection(bpy, "CAMARAS", root)
    lights = ensure_collection(bpy, "ILUMINACION", root)

    camera_data = bpy.data.cameras.new("CAMARA_PRINCIPAL")
    camera = bpy.data.objects.new("CAMARA_PRINCIPAL", camera_data)
    cameras.objects.link(camera)
    target = Vector((center.x, center.y, 3.0))
    camera.location = target + Vector((span * 0.34, -span * 0.50, span * 0.22))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 30.0
    camera_data.clip_start = 0.2
    camera_data.clip_end = max(6000.0, span * 12.0)
    scene.camera = camera

    sun_data = bpy.data.lights.new("SOL", type="SUN")
    sun_data.energy = 3.2
    sun_data.angle = math.radians(3.0)
    sun = bpy.data.objects.new("SOL", sun_data)
    lights.objects.link(sun)
    sun.location = (center.x - span * 0.4, center.y - span * 0.5, span * 1.2)
    sun.rotation_euler = (math.radians(52), 0.0, math.radians(35))

    for obj in (camera, sun):
        obj["bara_generated"] = True
        obj["bara_kind"] = "camara" if obj is camera else "sol"

    world = scene.world or bpy.data.worlds.new("BARA_Mundo")
    scene.world = world
    world.use_nodes = True
    background = next((node for node in world.node_tree.nodes
                       if node.type == "BACKGROUND"), None)
    if background is not None:
        background.inputs[0].default_value = (0.42, 0.58, 0.76, 1.0)
        background.inputs[1].default_value = 0.9

    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.film_transparent = False
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    scene["bara_proyecto"] = "BARA-DRIVE - mapa de prueba"
    scene["bara_aviso_edificios"] = (
        "Los edificios con prefijo PROVISIONAL_ son volumetricos de prueba; "
        "no representan edificios reales de Baradero.")
    scene["bara_urban_center"] = [round(center.x, 3), round(center.y, 3)]

    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            try:
                space.shading.type = "MATERIAL"
            except (AttributeError, TypeError):
                pass
            try:
                space.region_3d.view_perspective = "CAMERA"
            except (AttributeError, TypeError):
                pass
    logger.info("Camara y vista de perspectiva configuradas")
    return camera


def build(bpy, config, osm, logger):
    root = bpy.data.collections.get(config["root_collection"])
    if root is None:
        raise RuntimeError("Primero debe generarse la Fase 2 (colecciones de calles)")

    for folder in URBAN_FOLDERS:
        clear_generated(bpy, folder)
    folders = {name: ensure_collection(bpy, name, root) for name in URBAN_FOLDERS}
    ensure_collection(bpy, "REFERENCIAS_OSM", root)

    options = config.get("urban_test", {})
    rng = random.Random(int(options.get("seed", 20261114)))
    palette = _palette(bpy)
    ways, _ = streets.collect_ways(bpy, config, osm)

    ground = _ground(bpy, ways, palette, folders["TERRENO"])
    blocks, center = _select_blocks(ways, osm, config, logger)
    road_union = geometry.union([way["surface"] for way in ways.values()])
    corridor = geometry.clean(
        road_union.buffer(float(config["curb_width_m_estimated"])
                          + float(config["sidewalk_width_m_estimated"]) + 0.3,
                          join_style="round", resolution=12))
    placements, used_blocks = _place_buildings(blocks, corridor, config, rng, logger)
    building_objects = []
    for placement in placements:
        building_objects.append(
            _building_object(bpy, placement, palette, folders["EDIFICIOS"]))

    tree_count = _place_trees(bpy, used_blocks, palette, folders["VEGETACION"],
                              rng, logger)
    tree_points = [Point(obj.location.x, obj.location.y)
                   for obj in folders["VEGETACION"].objects]
    lamp_count = _place_lamps(bpy, used_blocks, palette, folders["ILUMINACION"],
                              rng, logger, tree_points)
    sign_count = _place_signs(bpy, used_blocks, osm, center, palette,
                              folders["SEÑALES"], logger)

    bounds = [building["footprint"].bounds for building in placements]
    minx = min(item[0] for item in bounds)
    miny = min(item[1] for item in bounds)
    maxx = max(item[2] for item in bounds)
    maxy = max(item[3] for item in bounds)
    span = max(maxx - minx, maxy - miny, 220.0)
    zone_center = Point(((minx + maxx) / 2, (miny + maxy) / 2))
    camera = _setup_view(bpy, root, zone_center, span, palette, logger)

    root["bara_phase"] = "urban_test"
    root["bara_provisional"] = True
    blocks_report = []
    for index, block in enumerate(used_blocks, start=1):
        blocks_report.append({
            "block_id": index,
            "area_m2": round(block.area, 2),
            "centroid": [round(block.centroid.x, 2), round(block.centroid.y, 2)],
            "wkt": wkt_dumps(block, rounding_precision=3),
            "buildings": sum(1 for item in placements if item["block_id"] == index),
        })
    report = {
        "phase": "urban_test",
        "notice": "Edificios PROVISIONALES de prueba; no son edificios reales de Baradero.",
        "blender_version": bpy.app.version_string,
        "source_ways": len(ways),
        "seed": int(options.get("seed", 20261114)),
        "setback_from_centerline_m": float(options.get("setback_m", 8.0)),
        "centreline_blocks_found": len(blocks),
        "blocks_used": len(used_blocks),
        "block_details": blocks_report,
        "buildings": len(building_objects),
        "building_types": dict(Counter(item["kind"] for item in placements)),
        "buildings_detail": [{
            "name": obj.name,
            "type": obj["bara_kind"],
            "floors": obj["bara_floors"],
            "height_m": obj["bara_height_m"],
            "block_id": obj["bara_block_id"],
            "footprint_m2": obj["bara_footprint_m2"],
            "footprint_wkt": obj["bara_footprint_wkt"],
            "provisional": True,
        } for obj in building_objects],
        "trees": tree_count,
        "lamps": lamp_count,
        "signs": sign_count,
        "ground_object": ground.name,
        "camera": camera.name,
        "camera_location": [round(value, 2) for value in camera.location],
        "view_span_m": round(span, 2),
        "limitations": [
            "Los edificios son volumetricos de prueba, sin correspondencia con construcciones reales",
            "Alturas, colores, techos y aberturas son estimados",
            "El OSM no aporta retiros, medianeras ni uso del suelo",
            "No se modelo la Plaza Mitre en esta etapa",
        ],
    }
    logger.info(
        "Entorno: %d edificios en %d manzanas, %d arboles, %d postes, %d senales",
        len(building_objects), len(used_blocks), tree_count, lamp_count, sign_count)
    return report
