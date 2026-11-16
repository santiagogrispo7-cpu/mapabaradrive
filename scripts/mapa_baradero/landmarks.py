"""Plaza Mitre y Delegacion Municipal de Baradero, reconstruidas desde fotos.

La geometria se apoya en el poligono OSM de Plaza Mitre (way 239949279) y en
la huella OSM de la Municipalidad (way 386834199, Av. San Martin 905). Las
formas, colores y detalles se estiman a partir de las fotografias locales:
referencias/plaza-mitre/*.jpg y referencias/delegacion/delegacion.jpg.

No se borra ni se modifica ninguna calle, vereda o edificio existente: todo se
agrega en BARA_LUGARES_REALES, con objetos etiquetados bara_realista=True.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely import affinity

from . import geometry
from .common import clear_generated, ensure_collection, make_material

ROOT_COLLECTION = "BARA_LUGARES_REALES"
PLAZA_OSM_ID = "239949279"
TOWNHALL_OSM_ID = "386834199"
CHURCH_OSM_ID = "448060697"

PLAZA_FOLDERS = ("PLAZA_MITRE", "DELEGACION", "CONTEXTO", "CAMARAS_REALES")


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------
def _materials(bpy):
    defs = {
        "grass": ("BARA_REAL_Cesped", (0.075, 0.19, 0.055), 0.95),
        "lawn": ("BARA_REAL_Cesped_Claro", (0.11, 0.28, 0.075), 0.94),
        "paving": ("BARA_REAL_Loseta_Salmon", (0.40, 0.32, 0.25), 0.88),
        "paving_light": ("BARA_REAL_Loseta_Clara", (0.52, 0.45, 0.36), 0.86),
        "stone": ("BARA_REAL_Piedra", (0.27, 0.26, 0.24), 0.82),
        "stone_light": ("BARA_REAL_Piedra_Clara", (0.42, 0.40, 0.36), 0.80),
        "white": ("BARA_REAL_Blanco_Monumento", (0.82, 0.81, 0.76), 0.72),
        "dark": ("BARA_REAL_Bronce_Negro", (0.018, 0.017, 0.015), 0.35, 0.65),
        "plaque": ("BARA_REAL_Placa", (0.55, 0.53, 0.48), 0.55, 0.15),
        "wood": ("BARA_REAL_Madera_Banco", (0.58, 0.52, 0.41), 0.75),
        "metal": ("BARA_REAL_Hierro_Negro", (0.025, 0.028, 0.030), 0.38, 0.65),
        "lamp": ("BARA_REAL_Luz_Calida", (0.95, 0.82, 0.48), 0.25, 0.0,
                 (1.0, 0.72, 0.32), 3.0),
        "jacaranda": ("BARA_REAL_Jacaranda", (0.32, 0.18, 0.58), 0.85),
        "jacaranda2": ("BARA_REAL_Jacaranda_Claro", (0.46, 0.29, 0.72), 0.85),
        "trunk": ("BARA_REAL_Tronco", (0.15, 0.105, 0.065), 0.92),
        "palm": ("BARA_REAL_Palmera", (0.26, 0.20, 0.10), 0.90),
        "frond": ("BARA_REAL_Hoja_Palmera", (0.07, 0.25, 0.055), 0.88),
        "leaf": ("BARA_REAL_Follaje", (0.055, 0.20, 0.045), 0.90),
        "cypress": ("BARA_REAL_Cipres", (0.035, 0.14, 0.045), 0.92),
        "bush": ("BARA_REAL_Arbusto", (0.075, 0.22, 0.055), 0.90),
        "flower": ("BARA_REAL_Cantero", (0.18, 0.10, 0.06), 0.92),
        "bin": ("BARA_REAL_Cesto", (0.055, 0.16, 0.08), 0.80),
        "stucco": ("BARA_REAL_Revoque_Crema", (0.78, 0.75, 0.66), 0.78),
        "stucco_white": ("BARA_REAL_Revoque_Blanco", (0.86, 0.84, 0.77), 0.72),
        "granite": ("BARA_REAL_Granito_Marron", (0.33, 0.255, 0.20), 0.70),
        "granite2": ("BARA_REAL_Granito_Oscuro", (0.24, 0.19, 0.15), 0.72),
        "glass": ("BARA_REAL_Vidrio_Azulado", (0.025, 0.055, 0.07), 0.16, 0.35),
        "glass_light": ("BARA_REAL_Vidrio_Claro", (0.16, 0.20, 0.20), 0.20, 0.25),
        "roof": ("BARA_REAL_Techo_Plano", (0.20, 0.20, 0.19), 0.88),
        "text": ("BARA_REAL_Letras_Negras", (0.012, 0.012, 0.010), 0.55),
        "white_text": ("BARA_REAL_Letras_Blancas", (0.94, 0.94, 0.91), 0.55),
        "blue": ("BARA_REAL_Azul_Escudo", (0.015, 0.18, 0.48), 0.55),
        "green": ("BARA_REAL_Verde_Escudo", (0.03, 0.38, 0.16), 0.55),
    }
    result = {}
    for key, (name, color, roughness, *rest) in defs.items():
        metallic = rest[0] if rest else 0.0
        emission = rest[1] if len(rest) > 1 else None
        strength = rest[2] if len(rest) > 2 else 0.0
        result[key] = make_material(
            bpy, name, color, roughness, metallic, emission, strength)
    return result


# ---------------------------------------------------------------------------
# Primitivas de malla
# ---------------------------------------------------------------------------
def _tag(obj, kind, **props):
    obj["bara_generated"] = True
    obj["bara_realista"] = True
    obj["bara_kind"] = kind
    obj["bara_phase"] = "realista_v2"
    for key, value in props.items():
        obj[f"bara_{key}"] = value
    return obj


def _mesh_object(bpy, name, vertices, faces, materials, indices, collection,
                 kind, **props):
    if not vertices or not faces:
        raise ValueError(f"{name}: geometria vacia")
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    for position, polygon in enumerate(mesh.polygons):
        polygon.material_index = indices[position] if position < len(indices) else 0
    mesh.validate(verbose=False, clean_customdata=True)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    for material in materials:
        obj.data.materials.append(material)
    _tag(obj, kind, **props)
    return obj


def _add_box(vertices, faces, indices, center, size, material_index, angle=0.0):
    cx, cy, cz = center
    sx, sy, sz = size
    c, s = math.cos(angle), math.sin(angle)
    local = ((-sx / 2, -sy / 2, -sz / 2), (sx / 2, -sy / 2, -sz / 2),
             (sx / 2, sy / 2, -sz / 2), (-sx / 2, sy / 2, -sz / 2),
             (-sx / 2, -sy / 2, sz / 2), (sx / 2, -sy / 2, sz / 2),
             (sx / 2, sy / 2, sz / 2), (-sx / 2, sy / 2, sz / 2))
    offset = len(vertices)
    for u, v, z in local:
        vertices.append((cx + u * c - v * s, cy + u * s + v * c, cz + z))
    for face in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                 (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        faces.append(tuple(offset + i for i in face))
        indices.append(material_index)


def _boxes_object(bpy, name, boxes, materials, collection, kind, **props):
    vertices, faces, indices = [], [], []
    for center, size, material_index, angle in boxes:
        _add_box(vertices, faces, indices, center, size, material_index, angle)
    return _mesh_object(bpy, name, vertices, faces, materials, indices,
                        collection, kind, **props)


def _polygon_object(bpy, name, polygons, z_bottom, z_top, material, collection,
                    kind, **props):
    vertices, faces, indices = [], [], []
    for polygon in polygons:
        if polygon is None or polygon.is_empty:
            continue
        for part in geometry.polygon_parts(polygon):
            if part.area <= 1e-6:
                continue
            part_vertices, part_faces = geometry.prism(
                part, z_bottom, z_top, 1e-9)
            offset = len(vertices)
            vertices.extend(part_vertices)
            faces.extend(tuple(i + offset for i in face) for face in part_faces)
            indices.extend([0] * len(part_faces))
    return _mesh_object(bpy, name, vertices, faces, [material], indices,
                        collection, kind, **props)


def _flat_polygon_y(bpy, name, points_xz, y, thickness, material, collection,
                    kind, transform=None, **props):
    """Poligono plano vertical (normal -Y), util para letreros y alas."""
    vertices, faces, indices = [], [], []
    half = thickness / 2
    for x, z in points_xz:
        vertices.append((x, y + half, z))
        vertices.append((x, y - half, z))
    count = len(points_xz)
    faces.append(tuple(range(0, 2 * count, 2)))
    faces.append(tuple(range(1, 2 * count, 2)))
    indices.extend([0, 0])
    for i in range(count):
        j = (i + 1) % count
        faces.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j))
        indices.append(0)
    if transform is not None:
        vertices = [transform(x, yy, z) for x, yy, z in vertices]
    return _mesh_object(bpy, name, vertices, faces, [material], indices,
                        collection, kind, **props)


def _disc_object(bpy, name, center, radius, z0, z1, material, collection,
                 kind, segments=32, **props):
    points = [Point(center).buffer(radius, resolution=segments // 4)]
    return _polygon_object(bpy, name, points, z0, z1, material, collection,
                           kind, **props)


# ---------------------------------------------------------------------------
# Arboles y mobiliario reutilizable
# ---------------------------------------------------------------------------
def _jacaranda_mesh(bpy, mats):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=8,
        radius1=0.24, radius2=0.14, depth=4.2,
        matrix=Matrix.Translation((0, 0, 2.1)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    blobs = (
        ((0, 0, 5.4), (2.3, 2.1, 1.9), 1),
        ((1.6, 0.3, 5.1), (1.7, 1.5, 1.5), 1),
        ((-1.5, -0.4, 5.2), (1.8, 1.6, 1.5), 1),
        ((0.3, 1.5, 5.0), (1.6, 1.5, 1.4), 2),
        ((-0.4, -1.5, 5.0), (1.5, 1.4, 1.3), 2),
        ((0.5, -0.2, 6.6), (1.5, 1.4, 1.2), 2),
    )
    for center, scale, material_index in blobs:
        existing = set(bm.faces)
        bmesh.ops.create_icosphere(
            bm, subdivisions=2, radius=1.0,
            matrix=Matrix.Translation(center) @ Matrix.Diagonal(
                (scale[0], scale[1], scale[2], 1.0)))
        for face in set(bm.faces) - existing:
            face.material_index = material_index
    for face in bm.faces:
        face.smooth = True
    mesh = bpy.data.meshes.new("BARA_REAL_JACARANDA_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["trunk"])
    mesh.materials.append(mats["jacaranda"])
    mesh.materials.append(mats["jacaranda2"])
    return mesh


def _palm_mesh(bpy, mats):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=8,
        radius1=0.34, radius2=0.17, depth=8.0,
        matrix=Matrix.Translation((0, 0, 4.0)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    # Corona de hojas: 9 palmas planas, con leve caida.
    for i in range(9):
        angle = math.tau * i / 9
        c, s = math.cos(angle), math.sin(angle)
        existing = set(bm.faces)
        verts = []
        for u, v, w in ((0.15, 0.0, 8.15), (2.9, 0.0, 7.95),
                        (3.7, 0.0, 7.25), (2.6, 0.0, 7.15),
                        (0.2, 0.0, 7.95)):
            verts.append(bm.verts.new((u * c - v * s, u * s + v * c, w)))
        face = bm.faces.new(verts)
        face.material_index = 1
    for face in bm.faces:
        face.smooth = True
    mesh = bpy.data.meshes.new("BARA_REAL_PALMERA_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["palm"])
    mesh.materials.append(mats["frond"])
    return mesh


def _round_tree_mesh(bpy, mats, material):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=8,
        radius1=0.26, radius2=0.16, depth=3.6,
        matrix=Matrix.Translation((0, 0, 1.8)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    for center, scale in (((0, 0, 4.5), (2.7, 2.7, 2.3)),
                          ((1.2, 0.4, 4.0), (1.8, 1.8, 1.6)),
                          ((-1.1, -0.5, 4.1), (1.7, 1.7, 1.5))):
        existing = set(bm.faces)
        bmesh.ops.create_icosphere(
            bm, subdivisions=2, radius=1.0,
            matrix=Matrix.Translation(center) @ Matrix.Diagonal(
                (scale[0], scale[1], scale[2], 1.0)))
        for face in set(bm.faces) - existing:
            face.material_index = 1
    for face in bm.faces:
        face.smooth = True
    mesh = bpy.data.meshes.new("BARA_REAL_ARBOL_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["trunk"])
    mesh.materials.append(material)
    return mesh


def _cypress_mesh(bpy, mats):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=10,
        radius1=0.28, radius2=0.12, depth=3.0,
        matrix=Matrix.Translation((0, 0, 1.5)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    for center, radius, depth in (((0, 0, 4.3), 1.25, 5.6),
                                  ((0, 0, 6.7), 0.75, 4.2)):
        existing = set(bm.faces)
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False, segments=10,
            radius1=radius, radius2=0.06, depth=depth,
            matrix=Matrix.Translation(center))
        for face in set(bm.faces) - existing:
            face.material_index = 1
    mesh = bpy.data.meshes.new("BARA_REAL_CIPRES_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["trunk"])
    mesh.materials.append(mats["cypress"])
    return mesh


def _shrub_mesh(bpy, mats):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_icosphere(
        bm, subdivisions=2, radius=1.0,
        matrix=Matrix.Translation((0, 0, 0.55)) @ Matrix.Diagonal(
            (0.8, 0.8, 0.55, 1.0)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    for face in bm.faces:
        face.smooth = True
    mesh = bpy.data.meshes.new("BARA_REAL_ARBUSTO_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["bush"])
    return mesh


def _bench_mesh(bpy, mats):
    vertices, faces, indices = [], [], []
    # Asiento: 4 tablas claras.
    for i in range(4):
        y = -0.30 + i * 0.17
        _add_box(vertices, faces, indices, (0, y, 0.46), (2.1, 0.13, 0.055), 0)
    # Respaldo inclinado, 3 tablas.
    for i in range(3):
        _add_box(vertices, faces, indices,
                 (0, 0.34 + i * 0.035, 0.68 + i * 0.19), (2.1, 0.07, 0.13), 0)
    # Patas y estructura metalica.
    for x in (-0.85, 0.85):
        _add_box(vertices, faces, indices, (x, 0, 0.24), (0.07, 0.56, 0.44), 1)
        _add_box(vertices, faces, indices, (x, 0.36, 0.58), (0.06, 0.06, 0.72), 1)
        _add_box(vertices, faces, indices, (x, 0, 0.47), (0.08, 0.62, 0.06), 1)
    mesh = bpy.data.meshes.new("BARA_REAL_BANCO_MESH")
    mesh.from_pydata(vertices, [], faces)
    for position, polygon in enumerate(mesh.polygons):
        polygon.material_index = indices[position]
    mesh.validate(verbose=False, clean_customdata=True)
    mesh.update(calc_edges=True)
    mesh.materials.append(mats["wood"])
    mesh.materials.append(mats["metal"])
    return mesh


def _lamp_mesh(bpy, mats):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=10,
        radius1=0.22, radius2=0.18, depth=0.45,
        matrix=Matrix.Translation((0, 0, 0.23)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=10,
        radius1=0.075, radius2=0.055, depth=3.35,
        matrix=Matrix.Translation((0, 0, 2.1)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    # Farol de cuatro caras con vidrio calido.
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=4,
        radius1=0.32, radius2=0.23, depth=0.72,
        matrix=Matrix.Translation((0, 0, 4.05)) @ Matrix.Rotation(
            math.radians(45), 4, "Z"))
    for face in set(bm.faces) - existing:
        face.material_index = 1
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=4,
        radius1=0.38, radius2=0.0, depth=0.22,
        matrix=Matrix.Translation((0, 0, 4.52)) @ Matrix.Rotation(
            math.radians(45), 4, "Z"))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    mesh = bpy.data.meshes.new("BARA_REAL_FAROL_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["metal"])
    mesh.materials.append(mats["lamp"])
    return mesh


def _bin_mesh(bpy, mats):
    import bmesh
    from mathutils import Matrix

    bm = bmesh.new()
    existing = set(bm.faces)
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=12,
        radius1=0.34, radius2=0.38, depth=0.9,
        matrix=Matrix.Translation((0, 0, 0.45)))
    for face in set(bm.faces) - existing:
        face.material_index = 0
    mesh = bpy.data.meshes.new("BARA_REAL_CESTO_MESH")
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(mats["bin"])
    return mesh


# ---------------------------------------------------------------------------
# Ubicacion OSM y geometria de la plaza
# ---------------------------------------------------------------------------
def _osm_points(osm, way_id):
    way = osm["ways"].get(str(way_id))
    if way is None:
        raise ValueError(f"No existe el way OSM {way_id}")
    points = []
    for ref in way["refs"]:
        node = osm["nodes"].get(ref)
        if node and "xy" in node:
            points.append(tuple(node["xy"]))
    if len(points) < 3:
        raise ValueError(f"El way OSM {way_id} no tiene geometria suficiente")
    return points


def _osm_polygon(osm, way_id):
    points = _osm_points(osm, way_id)
    if points[0] == points[-1]:
        points = points[:-1]
    polygon = geometry.clean(Polygon(points))
    if polygon.is_empty or polygon.area <= 0:
        raise ValueError(f"Poligono OSM invalido en {way_id}")
    return polygon


def _edge_angles(polygon):
    coords = list(polygon.exterior.coords)[:-1]
    edges = []
    for i, point in enumerate(coords):
        other = coords[(i + 1) % len(coords)]
        dx, dy = other[0] - point[0], other[1] - point[1]
        edges.append((math.hypot(dx, dy), dx, dy))
    length, dx, dy = max(edges, key=lambda item: item[0])
    return math.atan2(dy, dx), length


def _ray_end(center, angle, inner):
    direction = (math.cos(angle), math.sin(angle))
    far = (center.x + direction[0] * 400.0, center.y + direction[1] * 400.0)
    ray = LineString([(center.x, center.y), far])
    hits = ray.intersection(inner.boundary)
    if hits.is_empty:
        return None
    if hits.geom_type == "Point":
        candidates = [hits]
    else:
        candidates = list(hits.geoms)
    return max(candidates, key=lambda point: point.distance(center))


def _perimeter_samples(polygon, offset, spacing):
    coords = list(polygon.exterior.coords)[:-1]
    for i, a in enumerate(coords):
        b = coords[(i + 1) % len(coords)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        normal = (-dy / length, dx / length)
        probe = Point((a[0] + b[0]) / 2 + normal[0], (a[1] + b[1]) / 2 + normal[1])
        if not polygon.contains(probe):
            normal = (-normal[0], -normal[1])
        count = max(2, int(length / spacing))
        for j in range(count):
            t = (j + 0.5) / count
            x = a[0] + dx * t + normal[0] * offset
            y = a[1] + dy * t + normal[1] * offset
            yield Point(x, y), normal


# ---------------------------------------------------------------------------
# Construccion de la Plaza Mitre
# ---------------------------------------------------------------------------
def _build_plaza(bpy, config, osm, mats, collection, logger):
    options = config.get("landmarks", {})
    rng = random.Random(int(options.get("seed", 20261114)))
    plaza = _osm_polygon(osm, PLAZA_OSM_ID)
    center = plaza.centroid
    angle, side = _edge_angles(plaza)
    if plaza.area < 5000:
        raise ValueError(f"Plaza Mitre demasiado pequena: {plaza.area:.1f} m2")

    outer = geometry.clean(plaza.buffer(-0.35, join_style="mitre"))
    tree_inner = geometry.clean(outer.buffer(-9.0, join_style="mitre"))
    path_inner = geometry.clean(outer.buffer(-12.5, join_style="mitre"))
    if tree_inner.is_empty or path_inner.is_empty:
        raise ValueError("No se pudo insetar el perimetro de la plaza")
    belt = outer.difference(tree_inner)
    ring = tree_inner.difference(path_inner)

    min_span = min(outer.bounds[2] - outer.bounds[0], outer.bounds[3] - outer.bounds[1])
    circle_radius = min(float(options.get("plaza_circle_radius_m", 24.0)),
                        min_span * 0.27)
    circle = Point(center).buffer(circle_radius, resolution=64)

    # Base de cesped y cordon perimetral.
    base = _polygon_object(bpy, "PLAZA_MITRE_CESPED", [outer], 0.15, 0.18,
                           mats["grass"], collection, "plaza_cesped",
                           source_osm_way=PLAZA_OSM_ID)
    curb = _polygon_object(
        bpy, "PLAZA_MITRE_CORDON", [outer.difference(outer.buffer(-0.35))],
        0.0, 0.24, mats["stone_light"], collection, "plaza_cordon",
        source_osm_way=PLAZA_OSM_ID)

    # Senderos radiales: 8 direcciones, cuatro anchos hacia las esquinas.
    path_lines = []
    opening_lines = []
    path_parts = []
    for index in range(8):
        direction = angle + index * math.pi / 4.0
        end = _ray_end(center, direction, path_inner)
        if end is None:
            continue
        width = float(options.get("plaza_path_width_m", 3.2))
        if index % 2 == 1:
            width *= 1.38
        line = LineString([(center.x, center.y), (end.x, end.y)])
        path_lines.append(line)
        opening_end = _ray_end(center, direction, outer)
        if opening_end is not None:
            opening_lines.append(LineString(
                [(center.x, center.y), (opening_end.x, opening_end.y)]))
        ribbon = line.buffer(width / 2.0, cap_style="flat", join_style="mitre")
        part = geometry.clean(ribbon.intersection(path_inner))
        if not part.is_empty:
            path_parts.append(part)
    if not path_parts:
        raise ValueError("No se generaron senderos de la plaza")
    paving = geometry.clean(unary_union(path_parts + [circle]))
    paths_object = _polygon_object(
        bpy, "PLAZA_MITRE_SENDEROS", [paving], 0.18, 0.205, mats["paving"],
        collection, "plaza_sendero", source_osm_way=PLAZA_OSM_ID)
    ring_object = _polygon_object(
        bpy, "PLAZA_MITRE_PERIMETRO", [ring], 0.18, 0.205, mats["paving"],
        collection, "plaza_perimetro", source_osm_way=PLAZA_OSM_ID)

    # Anillo decorativo del centro.
    accent = Point(center).buffer(circle_radius + 0.15, resolution=64).difference(
        Point(center).buffer(circle_radius - 1.25, resolution=64))
    accent_object = _polygon_object(
        bpy, "PLAZA_MITRE_ANILLO", [accent], 0.205, 0.225,
        mats["paving_light"], collection, "plaza_anillo")

    # Arbolado perimetral de jacarandaes.
    jacaranda = _jacaranda_mesh(bpy, mats)
    placed = []
    tree_count = 0
    for point, normal in _perimeter_samples(outer, 4.3, 7.2):
        if any(point.distance(line) < 5.2 for line in opening_lines):
            continue
        if not belt.buffer(-0.8).contains(point):
            continue
        point = Point(point.x + rng.uniform(-1.0, 1.0),
                      point.y + rng.uniform(-1.0, 1.0))
        if not belt.contains(point):
            continue
        if any(point.distance(other) < 5.8 for other in placed):
            continue
        placed.append(point)
        tree_count += 1
        obj = bpy.data.objects.new(f"PLAZA_JACARANDA_{tree_count:02d}", jacaranda)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.18)
        obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        scale = rng.uniform(0.88, 1.18)
        obj.scale = (scale, scale, scale)
        _tag(obj, "plaza_arbol", source="foto_aerea_plaza", species="jacaranda")
    # Segunda fila, mas espaciada y hacia adentro.
    for point, normal in _perimeter_samples(outer, 6.7, 12.5):
        if any(point.distance(line) < 5.4 for line in opening_lines):
            continue
        if not belt.buffer(-0.8).contains(point):
            continue
        if any(point.distance(other) < 6.0 for other in placed):
            continue
        placed.append(point)
        tree_count += 1
        obj = bpy.data.objects.new(f"PLAZA_JACARANDA_{tree_count:02d}", jacaranda)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.18)
        obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        scale = rng.uniform(0.82, 1.05)
        obj.scale = (scale, scale, scale)
        _tag(obj, "plaza_arbol", source="foto_aerea_plaza", species="jacaranda")

    lawn = geometry.clean(path_inner.difference(paving))
    if lawn.is_empty:
        raise ValueError("La plaza quedo sin cesped interior")
    # Manchas de cesped claro para dar volumen y contraste.
    lawn_parts = [part for part in geometry.polygon_parts(lawn) if part.area > 20]
    lawn_object = _polygon_object(
        bpy, "PLAZA_MITRE_CESPED_INTERIOR", lawn_parts, 0.18, 0.20,
        mats["lawn"], collection, "plaza_cesped_interior")

    # Palmeras y arboles de copa en el interior.
    palm_mesh = _palm_mesh(bpy, mats)
    round_tree = _round_tree_mesh(bpy, mats, mats["leaf"])
    cypress = _cypress_mesh(bpy, mats)
    shrub = _shrub_mesh(bpy, mats)
    occupied = list(placed)

    def sample_in(geom, count, minimum, radius_min, radius_max, attempts=2400):
        result = []
        minx, miny, maxx, maxy = geom.bounds
        tries = 0
        while len(result) < count and tries < attempts:
            tries += 1
            candidate = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
            if not geom.contains(candidate):
                continue
            distance = candidate.distance(center)
            if not radius_min <= distance <= radius_max:
                continue
            if any(candidate.distance(line) < 2.8 for line in path_lines):
                continue
            if any(candidate.distance(other) < minimum for other in occupied):
                continue
            if any(candidate.distance(other) < minimum for other in result):
                continue
            result.append(candidate)
        return result

    palm_points = sample_in(lawn, int(options.get("plaza_palms", 12)), 7.0,
                            circle_radius + 3.0, circle_radius + 15.0)
    for index, point in enumerate(palm_points, start=1):
        obj = bpy.data.objects.new(f"PLAZA_PALMERA_{index:02d}", palm_mesh)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.18)
        obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        scale = rng.uniform(0.85, 1.15)
        obj.scale = (scale, scale, scale)
        _tag(obj, "plaza_arbol", source="foto_plaza_vereda", species="palmera")
    occupied.extend(palm_points)

    tree_points = sample_in(lawn, int(options.get("plaza_trees", 8)), 8.0,
                            circle_radius + 5.0, circle_radius + 19.0)
    for index, point in enumerate(tree_points, start=1):
        obj = bpy.data.objects.new(f"PLAZA_ARBOL_{index:02d}", round_tree)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.18)
        obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        scale = rng.uniform(0.75, 1.05)
        obj.scale = (scale, scale, scale)
        _tag(obj, "plaza_arbol", source="foto_plaza_vereda", species="arbol")
    occupied.extend(tree_points)

    cypress_points = sample_in(belt, 3, 7.0, 0.0, 999.0)
    for index, point in enumerate(cypress_points, start=1):
        obj = bpy.data.objects.new(f"PLAZA_CIPRES_{index:02d}", cypress)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.18)
        obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        scale = rng.uniform(0.9, 1.2)
        obj.scale = (scale, scale, scale)
        _tag(obj, "plaza_arbol", source="foto_condor", species="cipres")

    # Arbustos en los canteros cercanos al circulo.
    shrub_points = sample_in(lawn, int(options.get("plaza_shrubs", 22)), 3.0,
                             circle_radius + 1.8, circle_radius + 20.0)
    for index, point in enumerate(shrub_points, start=1):
        obj = bpy.data.objects.new(f"PLAZA_ARBUSTO_{index:02d}", shrub)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.18)
        obj.rotation_euler = (0, 0, rng.uniform(0, math.tau))
        scale = rng.uniform(0.65, 1.25)
        obj.scale = (scale, scale, scale)
        _tag(obj, "plaza_arbusto", source="foto_aerea_plaza")

    # Bancos alrededor del circulo y en el perimetro.
    bench_mesh = _bench_mesh(bpy, mats)
    bench_count = 0
    for index in range(8):
        a = angle + (index + 0.5) * math.pi / 4.0
        point = Point(center.x + math.cos(a) * (circle_radius + 3.2),
                      center.y + math.sin(a) * (circle_radius + 3.2))
        obj = bpy.data.objects.new(f"PLAZA_BANCO_{bench_count + 1:02d}", bench_mesh)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.21)
        obj.rotation_euler = (0, 0, a - math.pi / 2.0)
        _tag(obj, "plaza_banco", source="foto_aerea_plaza")
        bench_count += 1
    for index in range(8):
        a = angle + index * math.pi / 4.0
        end = _ray_end(center, a, tree_inner)
        if end is None:
            continue
        point = Point(center.x + math.cos(a) * (end.distance(center) - 2.0),
                      center.y + math.sin(a) * (end.distance(center) - 2.0))
        obj = bpy.data.objects.new(f"PLAZA_BANCO_{bench_count + 1:02d}", bench_mesh)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.21)
        obj.rotation_euler = (0, 0, a + math.pi / 2.0)
        _tag(obj, "plaza_banco", source="foto_plaza_vereda")
        bench_count += 1

    # Faroles ornamentales.
    lamp_mesh = _lamp_mesh(bpy, mats)
    lamp_count = 0
    for index in range(8):
        a = angle + index * math.pi / 4.0 + math.pi / 8.0
        point = Point(center.x + math.cos(a) * (circle_radius + 5.0),
                      center.y + math.sin(a) * (circle_radius + 5.0))
        obj = bpy.data.objects.new(f"PLAZA_FAROL_{lamp_count + 1:02d}", lamp_mesh)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.21)
        obj.rotation_euler = (0, 0, a)
        _tag(obj, "plaza_farol", source="foto_plaza_vereda")
        lamp_count += 1
    for index in range(8):
        a = angle + index * math.pi / 4.0 + math.pi / 8.0
        end = _ray_end(center, a, tree_inner)
        if end is None:
            continue
        distance = end.distance(center) - 2.2
        point = Point(center.x + math.cos(a) * distance,
                      center.y + math.sin(a) * distance)
        obj = bpy.data.objects.new(f"PLAZA_FAROL_{lamp_count + 1:02d}", lamp_mesh)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.21)
        obj.rotation_euler = (0, 0, a)
        _tag(obj, "plaza_farol", source="foto_plaza_vereda")
        lamp_count += 1

    # Cestos verdes como los de la foto de la vereda.
    bin_mesh = _bin_mesh(bpy, mats)
    for index in range(4):
        a = angle + index * math.pi / 2.0 + math.pi / 4.0
        point = Point(center.x + math.cos(a) * (circle_radius + 7.5),
                      center.y + math.sin(a) * (circle_radius + 7.5))
        obj = bpy.data.objects.new(f"PLAZA_CESTO_{index + 1:02d}", bin_mesh)
        collection.objects.link(obj)
        obj.location = (point.x, point.y, 0.21)
        _tag(obj, "plaza_cesto", source="foto_plaza_vereda")

    # Monumento al Condor.
    monument = _build_monument(bpy, center, angle, osm, mats, collection, logger)

    return {
        "polygon": plaza,
        "center": center,
        "angle": angle,
        "radius": circle_radius,
        "objects": {
            "base": base.name, "curb": curb.name, "paths": paths_object.name,
            "ring": ring_object.name, "accent": accent_object.name,
            "lawn": lawn_object.name, "monument": monument["object"],
            "condor": monument["condor"],
        },
        "trees": tree_count + len(palm_points) + len(tree_points) + len(cypress_points),
        "jacarandas": tree_count,
        "palms": len(palm_points),
        "green_trees": len(tree_points),
        "shrubs": len(shrub_points),
        "benches": bench_count,
        "lamps": lamp_count,
        "bins": 4,
    }


# ---------------------------------------------------------------------------
# Monumento al Condor
# ---------------------------------------------------------------------------
def _wing(sign, front_y):
    """Ala extendida, con leve diedro hacia arriba."""
    points = (
        (0.0, 0.20), (0.45, 0.52), (1.15, 0.56), (1.85, 0.26),
        (1.55, -0.12), (0.55, -0.24), (0.0, -0.16),
    )
    heights = (0.10, 0.25, 0.48, 0.62, 0.40, 0.14, 0.08)
    vertices, faces, indices = [], [], []
    for (x, y), z in zip(points, heights):
        vertices.append((sign * x, front_y + y, z + 0.06))
        vertices.append((sign * x, front_y + y, z - 0.06))
    count = len(points)
    faces.append(tuple(range(0, 2 * count, 2)))
    faces.append(tuple(range(1, 2 * count, 2)))
    indices.extend([0, 0])
    for i in range(count):
        j = (i + 1) % count
        faces.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j))
        indices.append(0)
    return vertices, faces, indices


def _build_monument(bpy, center, angle, osm, mats, collection, logger):
    import bmesh
    from mathutils import Matrix

    vertices, faces, indices = [], [], []
    # Tres escalones cuadrados de piedra, alineados con la plaza.
    for size, top in ((8.6, 0.23), (7.5, 0.45), (6.4, 0.67)):
        _add_box(vertices, faces, indices, (0, 0, top / 2.0),
                 (size, size, top), 0, angle)
    # Basa blanca y pedestal.
    _add_box(vertices, faces, indices, (0, 0, 1.13), (4.2, 4.2, 0.92), 1, angle)
    _add_box(vertices, faces, indices, (0, 0, 2.10), (3.5, 3.5, 1.15), 1, angle)
    # Fuste troncopiramidal.
    base_size, top_size = 1.95, 0.78
    z_base, z_top = 2.67, 9.22
    c, s = math.cos(angle), math.sin(angle)

    def local(u, v, z):
        return (u * c - v * s, u * s + v * c, z)

    offset = len(vertices)
    for u, v in ((-base_size / 2, -base_size / 2),
                 (base_size / 2, -base_size / 2),
                 (base_size / 2, base_size / 2),
                 (-base_size / 2, base_size / 2)):
        vertices.append(local(u, v, z_base))
    for u, v in ((-top_size / 2, -top_size / 2),
                 (top_size / 2, -top_size / 2),
                 (top_size / 2, top_size / 2),
                 (-top_size / 2, top_size / 2)):
        vertices.append(local(u, v, z_top))
    for i in range(4):
        j = (i + 1) % 4
        faces.append((offset + i, offset + j, offset + 4 + j, offset + 4 + i))
        indices.append(1)
    faces.append((offset + 4, offset + 5, offset + 6, offset + 7))
    indices.append(1)
    # Capitel.
    _add_box(vertices, faces, indices, (0, 0, 9.36), (1.15, 1.15, 0.28), 1, angle)
    # Placas en tres caras del pedestal.
    for normal_angle in (angle, angle + math.pi / 2, angle + math.pi):
        nx, ny = math.cos(normal_angle), math.sin(normal_angle)
        _add_box(vertices, faces, indices,
                 (nx * 1.78, ny * 1.78, 2.10),
                 (1.35, 0.05, 0.80), 2, normal_angle - math.pi / 2)
    monument = _mesh_object(
        bpy, "PLAZA_MONUMENTO_CONDOR", vertices, faces,
        [mats["stone"], mats["white"], mats["plaque"]], indices, collection,
        "plaza_monumento", source="foto_condor",
        notice="Reconstruccion aproximada del monumento al Condor desde fotografia")
    monument.location = (center.x, center.y, 0.18)

    # Condor: cuerpo, cabeza, pico, cola y alas desplegadas.
    condor_vertices, condor_faces, condor_indices = [], [], []
    bm = bmesh.new()
    bmesh.ops.create_icosphere(
        bm, subdivisions=2, radius=1.0,
        matrix=Matrix.Translation((0, 0, 0.52)) @ Matrix.Diagonal(
            (0.30, 0.52, 0.28, 1.0)))
    for face in bm.faces:
        face.material_index = 0
    bmesh.ops.create_icosphere(
        bm, subdivisions=1, radius=1.0,
        matrix=Matrix.Translation((0, 0.46, 0.72)) @ Matrix.Diagonal(
            (0.16, 0.18, 0.16, 1.0)))
    for face in bm.faces:
        face.material_index = 0
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=4,
        radius1=0.09, radius2=0.0, depth=0.22,
        matrix=Matrix.Translation((0, 0.64, 0.69))
        @ Matrix.Rotation(math.radians(90), 4, "X"))
    for face in bm.faces:
        face.material_index = 0
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=4,
        radius1=0.22, radius2=0.04, depth=0.55,
        matrix=Matrix.Translation((0, -0.44, 0.38))
        @ Matrix.Rotation(math.radians(-90), 4, "X"))
    for face in bm.faces:
        face.material_index = 0
    for sign in (-1, 1):
        wv, wf, wi = _wing(sign, 0.0)
        offset = len(condor_vertices)
        condor_vertices.extend(wv)
        condor_faces.extend(tuple(i + offset for i in face) for face in wf)
        condor_indices.extend(wi)
    body_mesh = bpy.data.meshes.new("BARA_REAL_CONDOR_BODY")
    bm.to_mesh(body_mesh)
    bm.free()
    body_offset = len(condor_vertices)
    condor_vertices.extend(tuple(v.co) for v in body_mesh.vertices)
    condor_faces.extend(tuple(body_offset + i for i in polygon.vertices)
                        for polygon in body_mesh.polygons)
    condor_indices.extend([0] * len(body_mesh.polygons))
    bpy.data.meshes.remove(body_mesh)
    condor = _mesh_object(
        bpy, "PLAZA_CONDOR", condor_vertices, condor_faces, [mats["dark"]],
        condor_indices, collection, "plaza_condor", source="foto_condor")
    # El condor mira hacia el acceso noroeste / delegacion.
    toward = Point(center.x - 40.0, center.y + 35.0)
    dx, dy = toward.x - center.x, toward.y - center.y
    length = math.hypot(dx, dy)
    rotation = math.atan2(-dx / length, dy / length)
    condor.location = (center.x, center.y, 9.68)
    condor.rotation_euler = (0, 0, rotation)
    return {"object": monument.name, "condor": condor.name}


# ---------------------------------------------------------------------------
# Delegacion Municipal
# ---------------------------------------------------------------------------
def _delegation_frame(plaza, osm):
    town = _osm_polygon(osm, TOWNHALL_OSM_ID)
    coords = list(town.exterior.coords)[:-1]
    candidates = []
    for i, a in enumerate(coords):
        b = coords[(i + 1) % len(coords)]
        length = math.dist(a, b)
        if length < 10.0:
            continue
        midpoint = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        candidates.append((midpoint.distance(plaza.exterior), length, a, b, midpoint))
    if not candidates:
        raise ValueError("No se encontro el frente de la Municipalidad en OSM")
    distance, length, a, b, midpoint = min(candidates, key=lambda item: item[0])
    dx, dy = b[0] - a[0], b[1] - a[1]
    norm = math.hypot(dx, dy)
    direction = (dx / norm, dy / norm)
    n1 = (-direction[1], direction[0])
    n2 = (direction[1], -direction[0])
    toward = Point(plaza.centroid.x - midpoint.x, plaza.centroid.y - midpoint.y)
    inward = n1 if (n1[0] * toward.x + n1[1] * toward.y) > 0 else n2
    return {
        "town": town, "front_a": a, "front_b": b, "front_mid": midpoint,
        "direction": direction, "inward": inward, "distance_plaza": distance,
        "front_length": length,
    }


def _text_object(bpy, name, body, size, material, collection, location,
                 rotation, kind="letrero", **props):
    curve = bpy.data.curves.new(name, type="FONT")
    curve.body = body
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.extrude = 0.008
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    obj.data.materials.append(material)
    _tag(obj, kind, **props)
    return obj


def _build_delegation(bpy, config, osm, plaza_doc, mats, collection, logger):
    options = config.get("landmarks", {})
    plaza = plaza_doc["polygon"]
    frame = _delegation_frame(plaza, osm)
    width = min(float(options.get("delegation_width_m", 32.0)),
                max(20.0, frame["front_length"] - 4.0))
    depth = float(options.get("delegation_depth_m", 13.0))
    height = float(options.get("delegation_height_m", 8.8))
    street_z = 0.15
    floor_z = float(options.get("delegation_floor_z_m", 0.90))

    inward = frame["inward"]
    front_mid = frame["front_mid"]
    center = Point(front_mid.x - inward[0] * depth / 2.0,
                   front_mid.y - inward[1] * depth / 2.0)
    theta = math.atan2(inward[0], -inward[1])

    def world(u, v, z):
        c, s = math.cos(theta), math.sin(theta)
        return (center.x + u * c - v * s, center.y + u * s + v * c, z)

    def box_local(boxes, u, v, z, size, material_index, extra_angle=0.0):
        boxes.append(((u, v, z), size, material_index, extra_angle))

    vertices, faces, indices = [], [], []

    # Cajas en coordenadas locales (u, v) de la Delegacion.
    def box(u, v, z, size, material_index, extra_angle=0.0):
        _add_box(vertices, faces, indices, world(u, v, z), size,
                 material_index, theta + extra_angle)

    # Cuerpo principal.
    box(0, 0, (floor_z + height) / 2.0, (width, depth, height - floor_z), 0)
    # Techo y parapeto.
    box(0, 0, height + 0.12, (width + 0.5, depth + 0.5, 0.24), 1)
    for (u, v, z, size) in (
            (0, -depth / 2 - 0.08, height + 0.35, (width + 0.7, 0.22, 0.5)),
            (0, depth / 2 + 0.08, height + 0.35, (width + 0.7, 0.22, 0.5)),
            (-width / 2 - 0.08, 0, height + 0.35, (0.22, depth + 0.5, 0.5)),
            (width / 2 + 0.08, 0, height + 0.35, (0.22, depth + 0.5, 0.5))):
        box(u, v, z, size, 1)

    # Base bajo el nivel de acceso.
    box(0, 0, (street_z + floor_z) / 2.0,
        (width + 0.3, depth + 0.2, floor_z - street_z), 1)

    # Pilastras de granito en la fachada.
    pier_positions = (-width / 2 + 1.0, -width / 2 + 7.0, -3.4, 3.4,
                      width / 2 - 7.0, width / 2 - 1.0)
    for u in pier_positions:
        box(u, -depth / 2 - 0.22, (floor_z + height) / 2.0,
            (1.0, 0.46, height - floor_z), 2)
    # Antepecho / banda horizontal superior.
    box(0, -depth / 2 - 0.18, height - 0.35, (width + 0.3, 0.5, 0.55), 3)

    # Vidrios de planta baja y planta alta, apenas delante del muro.
    y_front = -depth / 2 - 0.03
    ground_start, ground_top = floor_z + 0.10, 3.55
    upper_start, upper_top = 4.55, 7.15
    box(0, y_front, (ground_start + ground_top) / 2.0,
        (width - 2.1, 0.06, ground_top - ground_start), 4)
    box(0, y_front, (upper_start + upper_top) / 2.0,
        (width - 2.1, 0.06, upper_top - upper_start), 4)

    # Fachada: rehundido y puertas centrales de acceso.
    box(0, -depth / 2 + 0.35, 2.2, (6.0, 0.12, 2.6), 5)
    box(0, y_front - 0.04, 2.2, (5.2, 0.09, 2.5), 4)
    for u in (-1.3, 1.3):
        box(u, -depth / 2 - 0.05, 2.2, (0.08, 0.14, 2.5), 5)
    box(0, -depth / 2 + 0.02, 3.53, (6.4, 0.7, 0.12), 1)
    # Puertas laterales de vidrio.
    for u in (-width / 2 + 4.2, width / 2 - 4.2):
        box(u, y_front - 0.03, 2.2, (2.6, 0.07, 2.5), 4)
        box(u, -depth / 2 - 0.08, 2.2, (0.09, 0.08, 2.5), 5)

    # Divisiones blancas de las ventanas de planta alta.
    for u in (-width / 2 + 2.2 + i * 2.0 for i in range(15)):
        if -width / 2 + 1.0 < u < width / 2 - 1.0:
            box(u, y_front - 0.04, (upper_start + upper_top) / 2.0,
                (0.09, 0.10, upper_top - upper_start), 3)

    # Alero principal con letras.
    box(0, -depth / 2 - 0.62, 4.02, (width + 0.6, 1.1, 0.92), 1)
    box(0, -depth / 2 - 1.20, 4.02, (width + 0.4, 0.08, 0.52), 3)

    # Escalera amplia de cinco tramos.
    step_width = width - 8.0
    step_depth = 0.40
    step_rise = 0.15
    for i in range(5):
        top = street_z + (i + 1) * step_rise
        depth_i = (5 - i) * step_depth
        box(0, -depth / 2 - depth_i / 2.0, (street_z + top) / 2.0,
            (step_width, depth_i, top - street_z), 3)
    # Banda de granito rosado en el tercer escalon.
    box(0, -depth / 2 - 1.05, street_z + 0.47,
        (step_width, 0.10, 0.035), 6)
    # Chequeos laterales de la escalera.
    for u in (-step_width / 2 - 0.25, step_width / 2 + 0.25):
        box(u, -depth / 2 - 1.15, street_z + 0.60, (0.4, 2.5, 1.2), 1)

    # Rampa lateral izquierda y barandas.
    ramp_length = 5.2
    ramp_width = 1.5
    ramp_vertices = []
    ramp_faces = []
    ramp_indices = []
    # Prisma inclinado: cuatro puntos inferiores en el predio y cuatro superiores.
    c, s = math.cos(theta), math.sin(theta)

    def rw(u, v, z):
        return (center.x + u * c - v * s, center.y + u * s + v * c, z)

    x0 = -width / 2 + 0.9
    x1 = x0 + ramp_width
    y0 = -depth / 2 - ramp_length
    y1 = -depth / 2
    z0 = street_z
    z1 = floor_z
    for u, v, z in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)):
        ramp_vertices.append(rw(u, v, z))
    for u, v, z in ((x0, y0, z0 - 0.12), (x1, y0, z0 - 0.12),
                    (x1, y1, z1 - 0.12), (x0, y1, z1 - 0.12)):
        ramp_vertices.append(rw(u, v, z))
    for face in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                 (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        ramp_faces.append(face)
        ramp_indices.append(1)
    for u in (x0 - 0.05, x1 + 0.05):
        # Pasamanos superior inclinado.
        p0 = rw(u, y0, z0 + 0.95)
        p1 = rw(u, y1, z1 + 0.95)
        _add_box(vertices, faces, indices,
                 ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2,
                  (p0[2] + p1[2]) / 2),
                 (0.06, math.dist((p0[0], p0[1]), (p1[0], p1[1])), 0.06),
                 5, theta)
        for point in (p0, p1):
            _add_box(vertices, faces, indices, (point[0], point[1],
                     (z0 + z1) / 2 + 0.45), (0.05, 0.05, 0.9), 5)
    ramp = _mesh_object(
        bpy, "DELEGACION_RAMPA", ramp_vertices, ramp_faces,
        [mats["stucco_white"]], ramp_indices, collection, "delegacion_rampa")

    # Banderas blancas verticales sobre las ventanas superiores.
    for index in range(5):
        u = -10.5 + index * 5.25
        _add_box(vertices, faces, indices,
                 world(u, -depth / 2 - 0.22, 6.55), (0.32, 0.04, 1.35), 3, theta)

    # Volumen del edificio.
    building = _mesh_object(
        bpy, "DELEGACION_MUNICIPAL", vertices, faces,
        [mats["stucco"], mats["stucco_white"], mats["granite"],
         mats["stucco_white"], mats["glass"], mats["text"],
         mats["paving_light"]],
        indices, collection, "delegacion",
        source_osm_way=TOWNHALL_OSM_ID,
        source_photo="referencias/delegacion/delegacion.jpg",
        real_name="Municipalidad de Baradero",
        address="Av. San Martin 905, Baradero",
        width_m=round(width, 2), depth_m=round(depth, 2),
        height_m=round(height, 2), theta_rad=round(theta, 6),
        center_x=round(center.x, 3), center_y=round(center.y, 3),
        front_distance_plaza=round(frame["distance_plaza"], 2),
        notice=("Modelo aproximado de la Municipalidad de Baradero a partir de "
                "la fotografia local; no es un relevamiento metrico."))

    # Letrero principal sobre el alero.
    sign_y = -depth / 2 - 1.245
    main_location = world(5.2, sign_y, 4.02)
    _text_object(
        bpy, "DELEGACION_LETRERO_MUNICIPIO", "MUNICIPIO DE BARADERO",
        0.50, mats["text"], collection, main_location,
        (math.pi / 2, 0, theta), kind="delegacion_letrero",
        source_photo="referencias/delegacion/delegacion.jpg")
    # Escudo circular oscuro con anillo blanco, sobre el alero.
    logo_x = -11.8
    logo_vertices, logo_faces, logo_indices = [], [], []

    def add_disc(u0, v0, z0, radius, thickness, material_index, segments=40):
        start = len(logo_vertices)
        for layer in (-1.0, 1.0):
            for i in range(segments):
                a = math.tau * i / segments
                logo_vertices.append(world(
                    u0 + radius * math.cos(a),
                    v0 + layer * thickness / 2.0,
                    z0 + radius * math.sin(a)))
        logo_faces.append(tuple(start + i for i in range(segments)))
        logo_indices.append(material_index)
        logo_faces.append(tuple(start + segments + i for i in range(segments)))
        logo_indices.append(material_index)
        for i in range(segments):
            j = (i + 1) % segments
            logo_faces.append((start + i, start + j,
                               start + segments + j, start + segments + i))
            logo_indices.append(material_index)

    add_disc(logo_x, sign_y - 0.03, 4.02, 0.56, 0.08, 0)
    add_disc(logo_x, sign_y - 0.075, 4.02, 0.45, 0.06, 1)
    logo = _mesh_object(
        bpy, "DELEGACION_ESCUDO", logo_vertices, logo_faces,
        [mats["stucco_white"], mats["dark"]], logo_indices, collection,
        "delegacion_escudo")

    # Panel blanco "BARADERO" con onda azul y verde sobre el vidrio derecho.
    panel_x = 10.3
    panel_location = world(panel_x, -depth / 2 - 0.10, 2.05)
    panel_vertices, panel_faces, panel_indices = [], [], []
    _add_box(panel_vertices, panel_faces, panel_indices,
             (panel_location[0], panel_location[1], panel_location[2]),
             (6.0, 0.06, 2.2), 0, theta)
    panel = _mesh_object(
        bpy, "DELEGACION_PANEL_BARADERO", panel_vertices, panel_faces,
        [mats["stucco_white"]], panel_indices, collection,
        "delegacion_panel")
    _text_object(
        bpy, "DELEGACION_LETRERO_BARADERO", "BARADERO", 0.34,
        mats["text"], collection, world(panel_x, -depth / 2 - 0.16, 2.35),
        (math.pi / 2, 0, theta), kind="delegacion_letrero")
    # Onda estilizada.
    for index, (offset, material) in enumerate((
            (-0.18, mats["blue"]), (0.0, mats["green"]))):
        wave_vertices, wave_faces, wave_indices = [], [], []
        _add_box(wave_vertices, wave_faces, wave_indices,
                 world(panel_x + offset, -depth / 2 - 0.17, 1.55),
                 (1.8, 0.03, 0.12), 0, theta)
        wave = _mesh_object(
            bpy, f"DELEGACION_ONDA_{index + 1}", wave_vertices, wave_faces,
            [material], wave_indices, collection, "delegacion_onda")
        wave.rotation_euler[2] += math.radians(-8 + index * 16)

    # Banderas blancas verticales sobre las ventanas superiores: ya incorporadas
    # a la malla del edificio antes de crearla.

    # Macetas de entrada.
    box_vertices, box_faces, box_indices = [], [], []
    for u in (-3.5, 3.5):
        _add_box(box_vertices, box_faces, box_indices,
                 world(u, -depth / 2 - 1.8, floor_z + 0.25),
                 (0.7, 0.7, 0.5), 0, theta)
    planters = _mesh_object(
        bpy, "DELEGACION_MACETAS", box_vertices, box_faces,
        [mats["stucco_white"]], box_indices, collection, "delegacion_maceta")

    # Verja y arboles del entorno inmediato.
    _build_delegation_context(bpy, center, theta, width, depth, floor_z,
                              mats, collection, logger)

    return {
        "object": building.name,
        "center": center,
        "theta": theta,
        "width": width,
        "depth": depth,
        "height": height,
        "front_distance_plaza": frame["distance_plaza"],
        "osm_town_bounds": [round(value, 2) for value in frame["town"].bounds],
        "ramp": ramp.name,
        "logo": logo.name,
        "panel": panel.name,
        "planters": planters.name,
    }


def _build_delegation_context(bpy, center, theta, width, depth, floor_z,
                              mats, collection, logger):
    c, s = math.cos(theta), math.sin(theta)

    def world(u, v, z):
        return (center.x + u * c - v * s, center.y + u * s + v * c, z)

    # Explanada de acceso y vereda de hormigon.
    vertices, faces, indices = [], [], []
    _add_box(vertices, faces, indices,
             world(0, -depth / 2 - 4.5, 0.075),
             (width + 4.0, 9.0, 0.15), 0, theta)
    plaza = _mesh_object(
        bpy, "DELEGACION_EXPLANADA", vertices, faces, [mats["paving_light"]],
        indices, collection, "delegacion_explanada")

    # Dos parterres laterales y un arbol de copa a cada lado.
    tree_mesh = _round_tree_mesh(bpy, mats, mats["leaf"])
    for index, u in enumerate((-width / 2 - 4.0, width / 2 + 4.0), start=1):
        obj = bpy.data.objects.new(f"DELEGACION_ARBOL_{index:02d}", tree_mesh)
        collection.objects.link(obj)
        obj.location = world(u, -depth / 2 - 7.0, 0.15)
        obj.rotation_euler = (0, 0, theta)
        obj.scale = (0.85, 0.85, 0.85)
        _tag(obj, "delegacion_arbol", source="entorno_osm")
    # Cestos y faroles de vereda.
    bin_mesh = _bin_mesh(bpy, mats)
    for index, u in enumerate((-width / 2 - 2.0, width / 2 + 2.0), start=1):
        obj = bpy.data.objects.new(f"DELEGACION_CESTO_{index:02d}", bin_mesh)
        collection.objects.link(obj)
        obj.location = world(u, -depth / 2 - 3.0, 0.15)
        _tag(obj, "delegacion_cesto", source="foto_delegacion")
    return plaza


# ---------------------------------------------------------------------------
# Camaras y vista
# ---------------------------------------------------------------------------
def _setup_cameras(bpy, root, plaza_center, delegation, mats, logger):
    from mathutils import Vector

    scene = bpy.context.scene
    cameras = ensure_collection(bpy, "CAMARAS_REALES", root)

    def add_camera(name, location, target, lens, ortho=None):
        data = bpy.data.cameras.new(name)
        data.lens = lens
        data.clip_start = 0.2
        data.clip_end = 5000.0
        if ortho is not None:
            data.type = "ORTHO"
            data.ortho_scale = ortho
        obj = bpy.data.objects.new(name, data)
        cameras.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat(
            "-Z", "Y").to_euler()
        _tag(obj, "camara_realista", notice="Vista de la reconstruccion desde fotos")
        return obj

    dc = delegation["center"]
    theta = delegation["theta"]
    inward = (math.sin(theta), -math.cos(theta))
    facade_distance = delegation["depth"] / 2.0 + 32.0
    plaza = add_camera(
        "CAMARA_PLAZA",
        (plaza_center.x + 82.0, plaza_center.y - 108.0, 72.0),
        (plaza_center.x - 25.0, plaza_center.y + 18.0, 3.0), 32.0)
    front = add_camera(
        "CAMARA_DELEGACION",
        (dc.x + inward[0] * facade_distance,
         dc.y + inward[1] * facade_distance, 13.5),
        (dc.x, dc.y, 4.6), 30.0)
    monument = add_camera(
        "CAMARA_MONUMENTO",
        (plaza_center.x + 19.0, plaza_center.y - 23.0, 10.0),
        (plaza_center.x, plaza_center.y, 5.4), 42.0)
    aerial = add_camera(
        "CAMARA_PLAZA_AEREA",
        (plaza_center.x, plaza_center.y, 230.0),
        (plaza_center.x, plaza_center.y, 0.0), 50.0, ortho=150.0)
    scene.camera = plaza

    # Iluminacion de relleno suave para las fotos de control.
    lights = ensure_collection(bpy, "ILUMINACION_REAL", root)
    fill_data = bpy.data.lights.new("LUZ_REALISTA_RELLENO", type="AREA")
    fill_data.energy = 350.0
    fill_data.size = 40.0
    fill = bpy.data.objects.new("LUZ_REALISTA_RELLENO", fill_data)
    lights.objects.link(fill)
    fill.location = (plaza_center.x + 35.0, plaza_center.y - 45.0, 35.0)
    fill.rotation_euler = (math.radians(50), 0.0, math.radians(35))
    _tag(fill, "luz_realista", notice="Relleno para las vistas de control")

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
    logger.info("Camaras realistas creadas; camara activa: %s", plaza.name)
    return {"plaza": plaza.name, "delegacion": front.name,
            "monumento": monument.name, "aerea": aerial.name}


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def build(bpy, config, osm, logger):
    root_road = bpy.data.collections.get(config["root_collection"])
    if root_road is None:
        raise RuntimeError("Falta la coleccion del mapa existente")

    removed = clear_generated(bpy, ROOT_COLLECTION)
    if removed:
        logger.info("Se retiraron %d objetos de una corrida realista anterior", removed)
    root = ensure_collection(bpy, ROOT_COLLECTION, root_road)
    folders = {name: ensure_collection(bpy, name, root) for name in PLAZA_FOLDERS}
    mats = _materials(bpy)

    plaza_report = _build_plaza(
        bpy, config, osm, mats, folders["PLAZA_MITRE"], logger)
    delegation_report = _build_delegation(
        bpy, config, osm, plaza_report, mats, folders["DELEGACION"], logger)
    cameras = _setup_cameras(
        bpy, root, plaza_report["center"], delegation_report, mats, logger)

    root["bara_phase"] = "realista_v2"
    root["bara_notice"] = (
        "Plaza Mitre y Municipalidad reconstruidas de forma aproximada desde "
        "fotografias locales y geometria OSM. No es un relevamiento metrico.")
    root["bara_sources"] = (
        "referencias/plaza-mitre/{desdearriba,condor,iglesia,vereda,vereda2,vereda3}.jpg; "
        "referencias/delegacion/delegacion.jpg")
    plaza_report.pop("polygon", None)
    plaza_report["center"] = [round(plaza_report["center"].x, 2),
                              round(plaza_report["center"].y, 2)]
    delegation_report["center"] = [
        round(delegation_report["center"].x, 2),
        round(delegation_report["center"].y, 2)]
    report = {
        "phase": "realista_v2",
        "blender_version": bpy.app.version_string,
        "root_collection": ROOT_COLLECTION,
        "plaza": plaza_report,
        "delegation": delegation_report,
        "cameras": cameras,
        "source_photos": {
            "plaza": ["referencias/plaza-mitre/desdearriba.jpg",
                      "referencias/plaza-mitre/condor.jpg",
                      "referencias/plaza-mitre/iglesia.jpg",
                      "referencias/plaza-mitre/vereda.jpg",
                      "referencias/plaza-mitre/vereda2.jpg",
                      "referencias/plaza-mitre/vereda3.jpg"],
            "delegacion": ["referencias/delegacion/delegacion.jpg"],
        },
        "osm": {
            "plaza_way": PLAZA_OSM_ID,
            "townhall_way": TOWNHALL_OSM_ID,
            "church_way": CHURCH_OSM_ID,
            "townhall_address": "Av. San Martin 905, Baradero",
            "verified": ("La huella OSM de la Municipalidad esta a "
                         f"{delegation_report['front_distance_plaza']:.1f} m del "
                         "borde de Plaza Mitre y su frente mira a la plaza."),
        },
        "limitations": [
            "Modelo aproximado: las fotos no tienen escala ni mediciones.",
            "La Delegacion fotografiada es la Municipalidad de Baradero (Av. San Martin 905).",
            "Senderos, cantidad de arboles y detalles menores son estimaciones.",
            "No se modelaron personas, vehiculos, cables ni carteles transitorios.",
            "La iglesia de la foto queda como referencia visual; no se reconstruyo en esta etapa.",
            "No se modifico ni borro ninguna calle, vereda o edificio existente.",
        ],
    }
    logger.info(
        "Realista v2: plaza %d arboles, %d bancos, %d faroles; delegacion %.1f x %.1f m",
        plaza_report["trees"], plaza_report["benches"],
        plaza_report["lamps"], delegation_report["width"],
        delegation_report["depth"])
    return report
