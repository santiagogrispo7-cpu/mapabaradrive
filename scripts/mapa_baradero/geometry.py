"""Geometría 2D/3D pura, sin bpy, para poder probarla por separado."""
from __future__ import annotations

import math

from shapely import constrained_delaunay_triangles
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union
from shapely.validation import make_valid


def polygon_parts(geometry):
    """Extrae polígonos válidos de cualquier resultado GEOS."""
    if geometry is None or geometry.is_empty:
        return
    if isinstance(geometry, Polygon):
        yield geometry
    elif isinstance(geometry, MultiPolygon):
        yield from geometry.geoms
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygon_parts(part)


def clean(geometry):
    if geometry is None or geometry.is_empty:
        return Polygon()
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    return geometry


def line_length(points):
    from shapely.geometry import LineString
    if len(points) < 2:
        return 0.0
    return float(LineString(points).length)


def ribbon(points, width):
    """Superficie de calzada centrada exactamente en el eje OSM."""
    from shapely.geometry import LineString
    if len(points) < 2:
        raise ValueError("Vía con menos de dos nodos")
    line = LineString(points)
    if line.length <= 1e-6:
        raise ValueError("Vía de longitud cero")
    return line.buffer(width / 2.0, cap_style="flat", join_style="mitre", mitre_limit=4.0)


def tiled(geometry, tile_size):
    """Divide por celdas alineadas al origen UTM; no reescala coordenadas."""
    geometry = clean(geometry)
    if geometry.is_empty:
        return
    minx, miny, maxx, maxy = geometry.bounds
    for ix in range(math.floor(minx / tile_size), math.floor(maxx / tile_size) + 1):
        for iy in range(math.floor(miny / tile_size), math.floor(maxy / tile_size) + 1):
            cell = box(ix * tile_size, iy * tile_size, (ix + 1) * tile_size, (iy + 1) * tile_size)
            for polygon in polygon_parts(clean(geometry.intersection(cell))):
                if polygon.area > 0:
                    yield f"{ix:+04d}_{iy:+04d}", polygon


def triangulate(polygon, min_area=1e-9):
    """Triangulación restringida de Delaunay, filtrada y validada."""
    result = constrained_delaunay_triangles(polygon)
    triangles = []
    footprint = polygon.buffer(1e-9)
    for candidate in polygon_parts(result):
        if candidate.area <= min_area:
            continue
        if not footprint.covers(candidate.representative_point()):
            continue
        triangles.append(candidate)
    if not triangles:
        raise ValueError("La triangulación no produjo triángulos")
    covered = sum(candidate.area for candidate in triangles)
    if abs(covered - polygon.area) > max(1e-3, polygon.area * 1e-3):
        raise ValueError(
            f"La triangulación no cubre el polígono: {covered:.6f} de {polygon.area:.6f} m2")
    return triangles


def prism(polygon, z_bottom, z_top, min_area=1e-9):
    """Malla cerrada de un polígono extruido verticalmente.

    Devuelve (vertices, caras). La orientación se recalcula después con bmesh;
    aquí alcanza con una topología cerrada y sin duplicados.
    """
    if z_top <= z_bottom:
        raise ValueError("Altura de extrusión inválida")
    index = {}
    vertices = []
    faces = []

    def vertex(x, y, z):
        key = (round(x, 4), round(y, 4), round(z, 4))
        if key not in index:
            index[key] = len(vertices)
            vertices.append((x, y, z))
        return index[key]

    triangles = triangulate(polygon, min_area)
    for triangle in triangles:
        coordinates = list(triangle.exterior.coords)[:3]
        top = [vertex(x, y, z_top) for x, y in coordinates]
        bottom = [vertex(x, y, z_bottom) for x, y in coordinates]
        faces.append(tuple(top))
        faces.append(tuple(reversed(bottom)))
    # Las paredes se derivan del borde de la triangulacion, no del anillo
    # original: la triangulacion restringida puede omitir nodos colineales y
    # entonces las paredes del anillo no coincidirian con las caras superior
    # e inferior (mallas abiertas).
    edge_use = {}
    for triangle in triangles:
        coordinates = list(triangle.exterior.coords)[:3]
        ring = [vertex(x, y, z_top) for x, y in coordinates]
        for position in range(3):
            a, b = ring[position], ring[(position + 1) % 3]
            key = (a, b) if a < b else (b, a)
            edge_use[key] = edge_use.get(key, 0) + 1
    for (a, b), uses in edge_use.items():
        if uses != 1:
            continue
        (ax, ay, _), (bx, by, _) = vertices[a], vertices[b]
        faces.append((vertex(ax, ay, z_bottom), vertex(bx, by, z_bottom),
                      vertex(bx, by, z_top), vertex(ax, ay, z_top)))
    return vertices, faces


def union(geometries):
    """Unión robusta; elimina solapamientos entre calzadas."""
    parts = [clean(g) for g in geometries if g is not None and not g.is_empty]
    if not parts:
        return Polygon()
    return clean(unary_union(parts))


def area(geometry):
    return float(geometry.area) if geometry is not None and not geometry.is_empty else 0.0
