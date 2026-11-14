"""Verificacion independiente de Baradero_Realista_v2.blend.

Abre el archivo guardado en un proceso Blender aparte y comprueba:
  - que la escena base (calles, cordones, veredas, edificios) siga intacta;
  - que Plaza Mitre y la Municipalidad existan, con sus elementos;
  - que la Municipalidad este frente a la plaza y fuera de la calzada;
  - que las camaras y el estado de vista esten guardados;
  - renders de control.

No guarda el .blend verificado.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from . import common, inspection


def _resolve(path):
    path = Path(path)
    return path if path.is_absolute() else (common.ROOT / path)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Verificador de Baradero Realista v2")
    parser.add_argument("--config", default="scripts/mapa_config.json")
    parser.add_argument("--file", default="mapa/blender/Baradero_Realista_v2.blend")
    parser.add_argument("--out", default="docs/verificacion_baradero_realista_v2.json")
    parser.add_argument("--renders", default="docs/renders")
    parser.add_argument("--no-render", action="store_true")
    argv = argv if argv is not None else sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return parser.parse_args(argv)


class Checks:
    def __init__(self):
        self.items = []

    def add(self, name, passed, detail=""):
        self.items.append({"name": name, "passed": bool(passed), "detail": detail})
        return passed

    @property
    def failed(self):
        return [item for item in self.items if not item["passed"]]


BASE_COLLECTIONS = {
    "CALLES": 48,
    "CORDONES": 48,
    "VEREDAS": 49,
    "EDIFICIOS": 21,
    "VEGETACION": 14,
    "SEÑALES": 6,
}

PLAZA_REQUIRED = (
    "PLAZA_MITRE_CESPED", "PLAZA_MITRE_CORDON", "PLAZA_MITRE_SENDEROS",
    "PLAZA_MITRE_PERIMETRO", "PLAZA_MITRE_CESPED_INTERIOR",
    "PLAZA_MONUMENTO_CONDOR", "PLAZA_CONDOR",
)

CAMERAS_REQUIRED = (
    "CAMARA_PLAZA", "CAMARA_DELEGACION", "CAMARA_MONUMENTO",
    "CAMARA_PLAZA_AEREA",
)


def _mesh_center(obj):
    if not obj.data.vertices:
        return None
    total_x = sum(v.co.x for v in obj.data.vertices)
    total_y = sum(v.co.y for v in obj.data.vertices)
    total_z = sum(v.co.z for v in obj.data.vertices)
    count = len(obj.data.vertices)
    return (total_x / count + obj.location.x,
            total_y / count + obj.location.y,
            total_z / count + obj.location.z)


def _delegation_footprint(obj):
    from shapely.geometry import Polygon
    from shapely import affinity

    width = float(obj.get("bara_width_m", 32.0))
    depth = float(obj.get("bara_depth_m", 13.0))
    theta = float(obj.get("bara_theta_rad", 0.0))
    x = float(obj.get("bara_center_x", obj.location.x))
    y = float(obj.get("bara_center_y", obj.location.y))
    polygon = Polygon([
        (-width / 2, -depth / 2), (width / 2, -depth / 2),
        (width / 2, depth / 2), (-width / 2, depth / 2)])
    polygon = affinity.rotate(polygon, math.degrees(theta), origin=(0, 0))
    return affinity.translate(polygon, x, y)


def _road_union(osm, config, near, radius=120.0):
    from shapely.geometry import Point
    from shapely.ops import unary_union

    ribbons = []
    for way in osm["ways"].values():
        tags = way["tags"]
        if "highway" not in tags:
            continue
        points = []
        for ref in way["refs"]:
            node = osm["nodes"].get(ref)
            if node and "xy" in node:
                points.append(tuple(node["xy"]))
        if len(points) < 2:
            continue
        if not any(Point(p).distance(Point(near)) < radius for p in points):
            continue
        from . import geometry as geometry_module
        width = float(config["widths_m_estimated"].get(
            tags["highway"], config["widths_m_estimated"]["residential"]))
        try:
            ribbons.append(geometry_module.ribbon(points, width))
        except ValueError:
            continue
    return unary_union(ribbons) if ribbons else None


def render_previews(bpy, folder, logger):
    folder.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except TypeError:
            pass
    try:
        scene.eevee.taa_render_samples = 8
    except Exception:
        pass
    scene.render.resolution_x = 960
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    paths = []
    for name, suffix in (("CAMARA_PLAZA", "plaza"),
                         ("CAMARA_DELEGACION", "delegacion"),
                         ("CAMARA_MONUMENTO", "monumento")):
        camera = bpy.data.objects.get(name)
        if camera is None:
            continue
        scene.camera = camera
        path = folder / f"verificacion_realista_{suffix}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        paths.append(str(path))
        logger.info("Render %s: %s", name, path)
    return paths


def verify(args, logger):
    import bpy
    from shapely.geometry import Point

    checks = Checks()
    target = _resolve(args.file)
    checks.add("archivo_existe", target.is_file(), str(target))
    if not target.is_file():
        raise FileNotFoundError(f"No existe el archivo a verificar: {target}")

    config = common.load_config(_resolve(args.config))
    osm_path = _resolve(config["osm"])
    osm = inspection.load_osm(osm_path)
    source = None
    origin_east = origin_north = 0.0

    logger.info("Abriendo %s", target)
    bpy.ops.wm.open_mainfile(filepath=str(target))
    scene = bpy.context.scene
    report, _, _ = inspection.inspect(bpy, config, osm_path)
    checks.add("archivo_abre", True, f"Blender {bpy.app.version_string}")
    source = bpy.data.collections.get(config["source_collection"])
    if source is not None:
        origin_east = float(source["origin_easting_m"])
        origin_north = float(source["origin_northing_m"])
    for node in osm["nodes"].values():
        east, north = inspection.utm21s(node["lon"], node["lat"])
        node["xy"] = (east - origin_east, north - origin_north)

    root = bpy.data.collections.get(config["root_collection"])
    checks.add("coleccion_raiz", root is not None, config["root_collection"])

    # --- Escena base intacta -------------------------------------------------
    for name, expected in BASE_COLLECTIONS.items():
        collection = bpy.data.collections.get(name)
        count = len(collection.objects) if collection else 0
        checks.add(f"base_{name.lower()}", count == expected,
                   f"esperados {expected}, encontrados {count}")
    checks.add("base_total", len(scene.objects) >= 257,
               f"{len(scene.objects)} objetos en la escena")

    # --- Colecciones nuevas --------------------------------------------------
    real_root = bpy.data.collections.get("BARA_LUGARES_REALES")
    checks.add("coleccion_realista", real_root is not None, "BARA_LUGARES_REALES")
    if real_root is None:
        raise RuntimeError("No existe BARA_LUGARES_REALES")
    children = {child.name for child in real_root.children}
    for name in ("PLAZA_MITRE", "DELEGACION", "CONTEXTO",
                 "CAMARAS_REALES", "ILUMINACION_REAL"):
        checks.add(f"subcoleccion_{name.lower()}", name in children, name)
    checks.add("hija_del_mapa", real_root.name in
               {child.name for child in root.children} if root else False,
               "BARA_LUGARES_REALES cuelga de BARA_MAPA_3D")

    new_objects = list(common.generated_objects(real_root))
    checks.add("objetos_nuevos", len(new_objects) > 60, f"{len(new_objects)} objetos")
    bad_flags = [obj.name for obj in new_objects
                 if not obj.get("bara_generated") or not obj.get("bara_realista")]
    checks.add("etiquetas_realista", not bad_flags, str(bad_flags[:5]))

    # --- Plaza Mitre ---------------------------------------------------------
    for name in PLAZA_REQUIRED:
        checks.add(f"plaza_{name.lower()}", bpy.data.objects.get(name) is not None, name)

    plaza_osm = osm["ways"].get(config["plaza_osm_way_id"])
    plaza_points = [tuple(osm["nodes"][ref]["xy"]) for ref in plaza_osm["refs"]]
    if plaza_points[0] == plaza_points[-1]:
        plaza_points = plaza_points[:-1]
    from shapely.geometry import Polygon
    plaza_polygon = Polygon(plaza_points)
    plaza_center = plaza_polygon.centroid

    base = bpy.data.objects.get("PLAZA_MITRE_CESPED")
    if base is not None:
        center = _mesh_center(base)
        distance = math.dist(center[:2], (plaza_center.x, plaza_center.y))
        checks.add("plaza_centrada_en_osm", distance < 3.0,
                   f"desvio {distance:.2f} m")
    monument = bpy.data.objects.get("PLAZA_MONUMENTO_CONDOR")
    if monument is not None:
        distance = math.dist((monument.location.x, monument.location.y),
                             (plaza_center.x, plaza_center.y))
        z_top = max(v.co.z for v in monument.data.vertices) + monument.location.z
        checks.add("monumento_en_centro", distance < 1.0,
                   f"desvio {distance:.2f} m")
        checks.add("monumento_alto", z_top > 8.0, f"altura {z_top:.2f} m")
    condor = bpy.data.objects.get("PLAZA_CONDOR")
    if condor is not None:
        z_top = max(v.co.z for v in condor.data.vertices) + condor.location.z
        checks.add("condor_sobre_monumento", z_top > 9.5, f"cota {z_top:.2f} m")

    kinds = {}
    for obj in new_objects:
        kinds[obj.get("bara_kind")] = kinds.get(obj.get("bara_kind"), 0) + 1
    checks.add("arboles_plaza", kinds.get("plaza_arbol", 0) >= 20,
               f"{kinds.get('plaza_arbol', 0)} arboles")
    checks.add("bancos_plaza", kinds.get("plaza_banco", 0) >= 8,
               f"{kinds.get('plaza_banco', 0)} bancos")
    checks.add("faroles_plaza", kinds.get("plaza_farol", 0) >= 8,
               f"{kinds.get('plaza_farol', 0)} faroles")
    checks.add("cestos_plaza", kinds.get("plaza_cesto", 0) >= 2,
               f"{kinds.get('plaza_cesto', 0)} cestos")
    checks.add("materiales_plaza", all(
        bpy.data.objects[name].data.materials for name in PLAZA_REQUIRED
        if bpy.data.objects.get(name) is not None and
        bpy.data.objects[name].type == "MESH"),
        "todos los objetos de la plaza tienen material")

    # --- Municipalidad -------------------------------------------------------
    townhall = bpy.data.objects.get("DELEGACION_MUNICIPAL")
    checks.add("delegacion_existe", townhall is not None and townhall.type == "MESH",
               "DELEGACION_MUNICIPAL")
    if townhall is not None:
        width = float(townhall.get("bara_width_m", 0.0))
        depth = float(townhall.get("bara_depth_m", 0.0))
        height = float(townhall.get("bara_height_m", 0.0))
        checks.add("delegacion_dimensiones",
                   30.0 <= width <= 36.0 and 10.0 <= depth <= 16.0
                   and 7.0 <= height <= 11.0,
                   f"{width:.1f} x {depth:.1f} x {height:.1f} m")
        checks.add("delegacion_osm", townhall.get("bara_source_osm_way") == "386834199",
                   "way/386834199")
        checks.add("delegacion_direccion",
                   "San Martin 905" in str(townhall.get("bara_address", "")),
                   str(townhall.get("bara_address")))
        footprint = _delegation_footprint(townhall)
        distance = footprint.distance(plaza_polygon)
        stored = float(townhall.get("bara_front_distance_plaza", -1.0))
        checks.add("delegacion_frente_a_plaza", 5.0 < distance < 40.0,
                   f"{distance:.2f} m del borde de la plaza (informe {stored:.2f} m)")
        checks.add("delegacion_fuera_de_plaza", not footprint.intersects(plaza_polygon),
                   "la huella no invade Plaza Mitre")
        roads = _road_union(osm, config, (
            float(townhall.get("bara_center_x", townhall.location.x)),
            float(townhall.get("bara_center_y", townhall.location.y))))
        if roads is not None:
            overlap = footprint.intersection(roads).area
            checks.add("delegacion_fuera_de_calzada", overlap < 1.0,
                       f"solape con calzadas {overlap:.2f} m2")
        else:
            checks.add("delegacion_fuera_de_calzada", False, "no se pudo evaluar")
        checks.add("delegacion_fachada", all(
            bpy.data.objects.get(name) is not None for name in (
                "DELEGACION_RAMPA", "DELEGACION_ESCUDO",
                "DELEGACION_PANEL_BARADERO", "DELEGACION_LETRERO_MUNICIPIO")),
            "rampa, escudo, panel y letrero")

    # --- Camaras y vista -----------------------------------------------------
    for name in CAMERAS_REQUIRED:
        checks.add(f"camara_{name.lower()}", bpy.data.objects.get(name) is not None, name)
    checks.add("camara_activa",
               scene.camera is not None and scene.camera.name == "CAMARA_PLAZA",
               scene.camera.name if scene.camera else "sin camara")

    camera_view = False
    material_shading = False
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            try:
                if space.region_3d.view_perspective == "CAMERA":
                    camera_view = True
            except AttributeError:
                pass
            try:
                if space.shading.type == "MATERIAL":
                    material_shading = True
            except AttributeError:
                pass
    checks.add("vista_camara_guardada", camera_view, "VIEW_3D en modo camara")
    checks.add("vista_material_guardada", material_shading, "sombreado MATERIAL")

    # --- Renders de control --------------------------------------------------
    if not args.no_render:
        renders = render_previews(bpy, _resolve(args.renders), logger)
        checks.add("renders_generados",
                   len(renders) == 3 and all(Path(path).is_file() for path in renders),
                   ", ".join(Path(path).name for path in renders))
    else:
        renders = []

    output = _resolve(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verified_file": str(target),
        "blender_version": bpy.app.version_string,
        "scene": scene.name,
        "objects_total": len(scene.objects),
        "base_collections": {
            name: len(bpy.data.collections[name].objects)
            for name in BASE_COLLECTIONS if name in bpy.data.collections},
        "realistic_objects": len(new_objects),
        "objects_by_kind": kinds,
        "cameras": {name: bpy.data.objects[name].location[:]
                    for name in CAMERAS_REQUIRED if name in bpy.data.objects},
        "renders": renders,
        "checks": checks.items,
        "passed": not checks.failed,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    for item in checks.items:
        logger.info("%s %s%s", "OK  " if item["passed"] else "FALLA",
                    item["name"], f" ({item['detail']})" if item["detail"] else "")
    if checks.failed:
        raise RuntimeError(f"{len(checks.failed)} verificaciones fallaron")
    logger.info("Verificacion completa: %d controles aprobados", len(checks.items))
    return payload


def run(argv=None):
    logger = None
    try:
        args = parse_args(argv)
        logger, log_path = common.setup_logging(
            "verificacion_realista", common.ROOT / "mapa" / "logs")
        logger.info("Argumentos: %s", vars(args))
        verify(args, logger)
        logger.info("Log: %s", log_path)
        return 0
    except Exception:
        import traceback
        trace = traceback.format_exc()
        print(trace, file=sys.stderr)
        try:
            from datetime import datetime
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = common.ROOT / "mapa" / "logs" / f"error_verificacion_realista_{stamp}.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(trace, encoding="utf-8")
        except Exception:
            pass
        return 1
