"""Verificacion independiente de Baradero_3D.blend (Blender 4.2, headless).

Comprueba que existan calles 3D, al menos 5 manzanas con edificios y 15
edificios PROVISIONALES dentro de las manzanas y fuera de la calzada/vereda,
ademas de arboles, postes, senales, terreno, camara y vista en perspectiva.
Genera docs/verificacion_baradero_3d.json/.md y renders de control.

Uso:
  blender.exe --background --factory-startup --python scripts\\verificar_baradero_3d.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mapa_baradero import common  # noqa: E402

common.add_dependency_path()

from mapa_baradero import inspection, streets  # noqa: E402

ROOT = common.ROOT
BLEND = ROOT / "mapa" / "blender" / "Baradero_3D.blend"
CONFIG = ROOT / "scripts" / "mapa_config.json"
RENDERS = ROOT / "docs" / "renders"


def main():
    import bpy
    from mathutils import Vector
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union
    from shapely import wkt

    checks = []

    def check(name, condition, detail=""):
        checks.append({"check": name, "passed": bool(condition), "detail": detail})
        print(("OK  " if condition else "FAIL") + f" {name}" + (f" :: {detail}" if detail else ""))
        return bool(condition)

    if not BLEND.is_file():
        raise SystemExit(f"No existe {BLEND}")
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    config = common.load_config(CONFIG)
    osm_path = ROOT / config["osm"]
    osm = inspection.load_osm(osm_path)
    east, north = inspection.utm21s(
        float(bpy.data.collections[config["source_collection"]]["origin_lon"]),
        float(bpy.data.collections[config["source_collection"]]["origin_lat"]))
    for node in osm["nodes"].values():
        e, n = inspection.utm21s(node["lon"], node["lat"])
        node["xy"] = (e - east, n - north)

    root = bpy.data.collections.get(config["root_collection"])
    check("Coleccion raiz BARA_MAPA_3D", root is not None)
    check("Escala de escena 1.0", abs(scene.unit_settings.scale_length - 1.0) < 1e-9,
          f"{scene.unit_settings.scale_length}")
    source = bpy.data.collections.get(config["source_collection"])
    source_ways = sum(1 for obj in source.objects if obj.get("osm_way_id")) if source else 0
    check("Calles OSM de origen intactas", source is not None and source_ways == 28,
          f"{source_ways} vias con osm_way_id")

    if root is None:
        raise SystemExit("Falta la coleccion raiz; no se puede continuar")

    folders = {name: bpy.data.collections.get(name) for name in
               ("CALLES", "CORDONES", "VEREDAS", "TERRENO", "EDIFICIOS",
                "VEGETACION", "ILUMINACION", "SEÑALES", "CAMARAS")}
    for name, collection in folders.items():
        check(f"Coleccion {name}", collection is not None)

    calzadas = [o for o in folders["CALLES"].objects if o.get("bara_layer") == "CALZADA"] \
        if folders["CALLES"] else []
    cordones = list(folders["CORDONES"].objects) if folders["CORDONES"] else []
    veredas = list(folders["VEREDAS"].objects) if folders["VEREDAS"] else []
    check("Calzadas 3D presentes", len(calzadas) >= 10, f"{len(calzadas)} objetos")
    check("Cordones presentes", len(cordones) >= 10, f"{len(cordones)} objetos")
    check("Veredas presentes", len(veredas) >= 10, f"{len(veredas)} objetos")
    asphalt_area = sum(float(o.get("bara_area_m2", 0.0)) for o in calzadas)
    sidewalk_area = sum(float(o.get("bara_area_m2", 0.0)) for o in veredas)
    check("Superficie de asfalto > 10000 m2", asphalt_area > 10000, f"{asphalt_area:.0f} m2")
    check("Superficie de vereda > 10000 m2", sidewalk_area > 10000, f"{sidewalk_area:.0f} m2")

    ground = bpy.data.objects.get("TERRENO_BASE")
    check("Terreno base", ground is not None and ground.type == "MESH")

    buildings = [o for o in folders["EDIFICIOS"].objects if o.get("bara_provisional")] \
        if folders["EDIFICIOS"] else []
    check("Al menos 15 edificios provisionales", len(buildings) >= 15,
          f"{len(buildings)} edificios")
    missing_name = [o.name for o in buildings if "PROVISIONAL" not in o.name]
    check("Todos los edificios se nombran PROVISIONAL",
          not missing_name, f"sin prefijo: {missing_name[:3]}")
    missing_notice = [o.name for o in buildings if "no es un edificio real" not in str(o.get("bara_notice", ""))]
    check("Aviso de edificio no real en cada objeto", not missing_notice,
          f"{len(missing_notice)} sin aviso")

    bad_geom = []
    bad_materials = []
    windows_total = doors_total = roofs_total = 0
    for obj in buildings:
        mesh = obj.data
        polygons = list(mesh.polygons)
        if not polygons or len(mesh.materials) < 4:
            bad_geom.append(obj.name)
            continue
        by_material = {}
        for polygon in polygons:
            by_material[polygon.material_index] = by_material.get(polygon.material_index, 0) + 1
        windows = by_material.get(2, 0)
        doors = by_material.get(3, 0)
        roofs = by_material.get(1, 0)
        windows_total += windows
        doors_total += doors
        roofs_total += roofs
        if windows < 1 or doors < 1 or roofs < 1:
            bad_materials.append(f"{obj.name}(v={windows},p={doors},t={roofs})")
        if len([v for v in mesh.vertices if abs(v.co.z) < 0.01]) < 4:
            bad_geom.append(obj.name)
    check("Edificios con ventanas, puertas y techo", not bad_materials,
          f"ventanas={windows_total}, puertas={doors_total}, techos={roofs_total}; "
          f"fallas={bad_materials[:3]}")
    check("Edificios con base a nivel de terreno", not bad_geom, f"{bad_geom[:3]}")

    # Manzanas y encaje de las plantas: se recalculan desde los ejes OSM.
    ways, _ = streets.collect_ways(bpy, config, osm)
    merged = unary_union([LineString(w["_points"]) for w in ways.values()])
    blocks = [p for p in polygonize(merged) if p.is_valid and p.area >= 250.0]
    block_ids = sorted({int(o.get("bara_block_id", 0)) for o in buildings})
    check("Edificios repartidos en al menos 5 manzanas", len(block_ids) >= 5,
          f"{len(block_ids)} manzanas: {block_ids}")
    check("Al menos 5 manzanas detectadas", len(blocks) >= 5, f"{len(blocks)} manzanas")

    corridor = unary_union([w["surface"] for w in ways.values()]).buffer(
        float(config["curb_width_m_estimated"]) + float(config["sidewalk_width_m_estimated"]) + 0.25,
        join_style="round", resolution=12)
    outside_blocks, into_streets, overlaps = [], [], []
    for obj in buildings:
        footprint = wkt.loads(obj["bara_footprint_wkt"])
        if not any(block.buffer(0.05).covers(footprint) for block in blocks):
            outside_blocks.append(obj.name)
        distance = footprint.distance(corridor)
        if distance < 0.5:
            into_streets.append(f"{obj.name}:{distance:.2f}m")
        for other in buildings:
            if other.name <= obj.name:
                continue
            other_footprint = wkt.loads(other["bara_footprint_wkt"])
            if footprint.distance(other_footprint) < 0.5:
                overlaps.append(f"{obj.name}/{other.name}")
    check("Cada edificio dentro de una manzana", not outside_blocks,
          f"fuera: {outside_blocks[:3]}")
    check("Edificios no invaden calzada ni vereda", not into_streets,
          f"invaden: {into_streets[:3]}")
    check("Edificios sin superposicion entre si", not overlaps, f"{overlaps[:3]}")

    trees = list(folders["VEGETACION"].objects) if folders["VEGETACION"] else []
    lamps = [o for o in folders["ILUMINACION"].objects if o.type == "MESH"] \
        if folders["ILUMINACION"] else []
    signs = list(folders["SEÑALES"].objects) if folders["SEÑALES"] else []
    check("Arboles generados", len(trees) >= 5, f"{len(trees)} arboles")
    check("Postes de luz generados", len(lamps) >= 3, f"{len(lamps)} postes")
    check("Senales de transito generadas", len(signs) >= 3, f"{len(signs)} senales")

    camera = bpy.data.objects.get("CAMARA_PRINCIPAL")
    check("Camara principal", camera is not None and camera.type == "CAMERA")
    check("Camara asignada a la escena", scene.camera is not None and scene.camera.name == "CAMARA_PRINCIPAL")
    check("Camara en perspectiva", camera is not None and camera.data.type == "PERSP",
          camera.data.type if camera else "sin camara")
    sun = bpy.data.objects.get("SOL")
    check("Luz solar", sun is not None and sun.type == "LIGHT")

    camera_views = material_views = 0
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            if getattr(space, "region_3d", None) is not None and \
                    space.region_3d.view_perspective in {"CAMERA", "PERSP"}:
                camera_views += 1
            if getattr(space, "shading", None) is not None and space.shading.type == "MATERIAL":
                material_views += 1
    check("Vista 3D guardada en perspectiva/camara", camera_views >= 1, f"{camera_views} areas")
    check("Sombreado material guardado", material_views >= 1, f"{material_views} areas")

    # Renders de control (no se guarda el .blend).
    RENDERS.mkdir(parents=True, exist_ok=True)
    renders = []
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.render.engine = "BLENDER_WORKBENCH"
        shading = scene.display.shading
        shading.light = "STUDIO"
        shading.color_type = "MATERIAL"
        shading.show_shadows = True
        shading.show_cavity = True
        scene.display.render_aa = "8"
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
    except (AttributeError, TypeError) as exc:
        print(f"Workbench no configurable: {exc}")

    def render(path):
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        renders.append({"file": str(path.relative_to(ROOT)),
                        "bytes": path.stat().st_size if path.exists() else 0})
        print(f"Render: {path}")

    if camera is not None:
        render(RENDERS / "baradero3d_camara.png")

    zone = scene.get("bara_urban_center") or [scene.camera.location.x, scene.camera.location.y]
    xs, ys = [], []
    for obj in buildings:
        footprint = wkt.loads(obj["bara_footprint_wkt"])
        minx, miny, maxx, maxy = footprint.bounds
        xs.extend((minx, maxx))
        ys.extend((miny, maxy))
    span = max(max(xs) - min(xs), max(ys) - min(ys), 220.0)
    top_data = bpy.data.cameras.new("TEMP_TOP")
    top_data.type = "ORTHO"
    top_data.ortho_scale = span * 1.5
    top_data.clip_end = 5000.0
    top = bpy.data.objects.new("TEMP_TOP", top_data)
    scene.collection.objects.link(top)
    top.location = (float(zone[0]), float(zone[1]), 600.0)
    top.rotation_euler = (0.0, 0.0, 0.0)
    old_camera = scene.camera
    scene.camera = top
    render(RENDERS / "baradero3d_planta.png")
    scene.camera = old_camera

    first = buildings[0]
    footprint = wkt.loads(first["bara_footprint_wkt"])
    bx, by = footprint.centroid.x, footprint.centroid.y
    street_data = bpy.data.cameras.new("TEMP_STREET")
    street_data.lens = 24.0
    street_data.clip_end = 3000.0
    street = bpy.data.objects.new("TEMP_STREET", street_data)
    scene.collection.objects.link(street)
    street.location = (bx - 24.0, by - 34.0, 2.4)
    target = Vector((bx, by, 4.0))
    street.rotation_euler = (target - street.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = street
    render(RENDERS / "baradero3d_calle.png")
    scene.camera = old_camera

    # Vista final con el motor guardado en el archivo (EEVEE Next).
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
        scene.eevee.taa_render_samples = 32
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
        render(RENDERS / "baradero3d_camara_eevee.png")
    except (AttributeError, TypeError) as exc:
        print(f"EEVEE no disponible para la vista final: {exc}")

    passed = all(item["passed"] for item in checks)
    report = {
        "file": str(BLEND),
        "blender_version": bpy.app.version_string,
        "verified_at": datetime.now().isoformat(timespec="seconds"),
        "passed": passed,
        "checks_total": len(checks),
        "checks_passed": sum(1 for c in checks if c["passed"]),
        "checks": checks,
        "counts": {
            "source_ways": source_ways,
            "calzadas": len(calzadas),
            "cordones": len(cordones),
            "veredas": len(veredas),
            "blocks_found": len(blocks),
            "blocks_with_buildings": len(block_ids),
            "buildings_provisional": len(buildings),
            "windows": windows_total,
            "doors": doors_total,
            "roof_faces": roofs_total,
            "trees": len(trees),
            "lamps": len(lamps),
            "signs": len(signs),
            "asphalt_m2": round(asphalt_area, 1),
            "sidewalk_m2": round(sidewalk_area, 1),
        },
        "renders": renders,
        "notice": "Los edificios PROVISIONAL_* son volumetricos de prueba, no edificios reales de Baradero.",
    }
    out_json = ROOT / "docs" / "verificacion_baradero_3d.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# Verificacion Baradero 3D", "",
          f"- Archivo: `{BLEND.name}`; Blender **{bpy.app.version_string}**.",
          f"- Resultado: **{'APROBADO' if passed else 'FALLIDO'}** "
          f"({report['checks_passed']}/{report['checks_total']} comprobaciones).",
          f"- Edificios PROVISIONALES: **{len(buildings)}** en **{len(block_ids)}** manzanas.",
          f"- Calzadas: {len(calzadas)}; cordones: {len(cordones)}; veredas: {len(veredas)}.",
          f"- Arboles: {len(trees)}; postes: {len(lamps)}; senales: {len(signs)}.",
          "", "## Comprobaciones", "",
          "| Resultado | Comprobacion | Detalle |", "| --- | --- | --- |"]
    for item in checks:
        md.append(f"| {'OK' if item['passed'] else 'FALLA'} | {item['check']} | {item['detail']} |")
    md.extend(["", "## Renders", ""])
    md.extend(f"- `{item['file']}` ({item['bytes']} bytes)" for item in renders)
    md.extend(["", report["notice"], ""])
    (ROOT / "docs" / "verificacion_baradero_3d.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
