"""Orquestacion de fases en un Blender headless. Sin logica de geometria."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path

from . import common, inspection, streets, urban


def _resolve(path):
    path = Path(path)
    return path if path.is_absolute() else (common.ROOT / path)


def parse_args(argv, default_output="mapa/blender/Baradero_mapa_3d.blend",
               default_source="mapa/blender/Baradero_mapa.blend"):
    parser = argparse.ArgumentParser(description="Generador del mapa 3D BARA-DRIVE")
    parser.add_argument("--config", default="scripts/mapa_config.json")
    parser.add_argument("--source", default=default_source)
    parser.add_argument("--output", default=default_output)
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--skip-backup", action="store_true")
    argv = argv if argv is not None else sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    return parser.parse_args(argv)


def backup(bpy, source, logger):
    """Copia de seguridad del archivo base, una vez por hash."""
    source = Path(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    folder = common.ROOT / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{source.stem}_original_{digest}.blend"
    if target.exists():
        logger.info("El respaldo original ya existe: %s", target)
        return target
    shutil.copy2(source, target)
    logger.info("Respaldo del original: %s", target)
    return target


def backup_existing_output(output, logger):
    """Antes de pisar una salida previa, la conserva con fecha."""
    output = Path(output)
    if not output.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = output.with_name(f"{output.stem}_trabajo_{stamp}.blend")
    shutil.copy2(output, target)
    logger.info("Respaldo de la salida previa: %s", target)
    return target


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, payload):
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def diagnostic_markdown(report):
    lines = [
        "# Diagnostico del mapa BARA-DRIVE",
        "",
        f"- Archivo inspeccionado: `{report['source_blend']}`.",
        f"- Blender: **{report['blender_version']}**. APIs usadas presentes en 4.2 y 5.2.",
        f"- Escena: {len(report['objects'])} objetos; colecciones: "
        + ", ".join(c["name"] for c in report["collections"]) + ".",
        f"- Calles verificadas contra el OSM: **{report['alignment']['matched_ways']}**.",
        f"- Error maximo del eje respecto del OSM: **{report['alignment']['max_error_m']:.6f} m**.",
        f"- CRS: **{report['crs']}**; origen lat/lon: "
        f"{report['origin']['lat']}, {report['origin']['lon']}.",
        f"- Escala: {report['units']['scale_length']} m por unidad; {report['axes']}.",
        f"- OSM: {report['osm']['nodes']} nodos, {report['osm']['roads']} vias highway, "
        f"{report['osm']['buildings']} edificios.",
        f"- Plaza Mitre: way/{report['osm']['plaza']['id'] if report['osm']['plaza'] else 'NO ENCONTRADA'}.",
        f"- Arboles individuales: {report['osm']['trees']}; bancos: {report['osm']['benches']}; "
        f"luminarias: {report['osm']['street_lamps']}.",
        "",
        "## Limitaciones verificadas",
        "",
    ]
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    lines.append("El JSON asociado incluye transformaciones, firmas y topologia de cada objeto.")
    lines.append("")
    return "\n".join(lines)


def streets_markdown(report):
    rows = [
        "| Via | Nombre | Clase | Ancho (m) | Origen del ancho | Longitud (m) |",
        "| --- | --- | --- | ---: | --- | ---: |",
    ]
    for way in report["ways"]:
        rows.append(
            f"| {way['way_id']} | {way['name']} | {way['highway']} | "
            f"{way['width_m']:.2f} | {way['width_source']} | {way['length_m']:.1f} |")
    layers = [
        "| Capa | Objetos | Area (m2) | Z inferior | Z superior | Material |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for name, layer in report["layers"].items():
        layers.append(
            f"| {name} | {layer['objects']} | {layer['area_m2']:.1f} | "
            f"{layer['z_bottom_m']:.2f} | {layer['z_top_m']:.2f} | {layer['material']} |")
    return "\n".join([
        "# Fase 2: calles 3D",
        "",
        f"- Generado con Blender **{report['blender_version']}**.",
        f"- Vias de origen convertidas: **{report['source_ways']}**.",
        f"- Tesela: {report['tile_size_m']} m; CRS {report['crs']}; unidades en metros.",
        f"- Superficie total de calzada unida: {report['road_union_area_m2']:.1f} m2.",
        "",
        "## Capas",
        "",
        *layers,
        "",
        "## Vias",
        "",
        *rows,
        "",
        "## Limitaciones",
        "",
        *[f"- {item}" for item in report["limitations"]],
        "",
        "Los objetos originales de `BARA_DRIVE_CALLES` quedan intactos; la geometria nueva",
        "vive en `BARA_MAPA_3D/CALLES`, `BARA_MAPA_3D/CORDONES` y `BARA_MAPA_3D/VEREDAS`.",
        "",
    ])


def generate(args, logger):
    import bpy

    config_path = _resolve(args.config)
    source = _resolve(args.source)
    output = _resolve(args.output)
    if not source.is_file():
        raise FileNotFoundError(f"No existe el .blend de origen: {source}")
    if source.resolve() == output.resolve():
        raise ValueError("La salida no puede ser el mismo archivo que la entrada")
    config = common.load_config(config_path)
    osm_path = _resolve(config["osm"])
    if not osm_path.is_file():
        raise FileNotFoundError(f"Falta el extracto OSM: {osm_path}")

    logger.info("Abriendo %s", source)
    bpy.ops.wm.open_mainfile(filepath=str(source))

    report, osm, matched = inspection.inspect(bpy, config, osm_path)
    report["generated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json(common.ROOT / "docs" / "diagnostico_mapa.json", report)
    write_text(common.ROOT / "docs" / "diagnostico_mapa.md", diagnostic_markdown(report))
    logger.info(
        "Fase 1: %d calles verificadas, error maximo %.6f m, OSM %s",
        len(matched), report["alignment"]["max_error_m"], osm_path.name)

    if args.inspect_only:
        logger.info("--inspect-only: no se genera geometria")
        return report

    if not args.skip_backup:
        backup(bpy, source, logger)
    backup_existing_output(output, logger)

    logger.info("Generando Fase 2 en memoria")
    streets_report = streets.build(bpy, config, osm, logger)
    streets_report["output_blend"] = str(output)
    streets_report["source_blend"] = str(source)
    streets_report["generated_at"] = datetime.now().isoformat(timespec="seconds")
    streets_report["source_sha256"] = report["osm"]["sha256"]

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    logger.info("Guardado: %s", output)
    write_json(common.ROOT / "docs" / "informe_calles.json", streets_report)
    write_text(common.ROOT / "docs" / "informe_calles.md", streets_markdown(streets_report))
    logger.info("Fase 2 completa: %s", json.dumps(
        {name: layer["objects"] for name, layer in streets_report["layers"].items()}))
    return streets_report


def urban_markdown(report):
    lines = [
        "# Baradero 3D: zona urbana de prueba",
        "",
        f"- Generado con Blender **{report['blender_version']}**.",
        f"- Vias de origen usadas: **{report['source_ways']}**.",
        f"- Manzanas cerradas detectadas: **{report['centreline_blocks_found']}**; "
        f"usadas para edificios: **{report['blocks_used']}**.",
        f"- Edificios **PROVISIONALES**: **{report['buildings']}** "
        f"({', '.join(f'{k}: {v}' for k, v in report['building_types'].items())}).",
        f"- Arboles: {report['trees']}; postes de luz: {report['lamps']}; "
        f"senales: {report['signs']}.",
        f"- Camara: `{report['camera']}` en {report['camera_location']}; "
        f"campo visual de {report['view_span_m']} m.",
        "",
        "## Aviso",
        "",
        report["notice"],
        "",
        "## Limitaciones",
        "",
        *[f"- {item}" for item in report["limitations"]],
        "",
        "## Manzanas",
        "",
        "| Manzana | Area (m2) | Edificios | Centro |",
        "| ---: | ---: | ---: | --- |",
    ]
    for block in report["block_details"]:
        lines.append(
            f"| {block['block_id']} | {block['area_m2']:.1f} | {block['buildings']} | "
            f"({block['centroid'][0]:.0f}, {block['centroid'][1]:.0f}) |")
    lines.extend([
        "",
        "## Edificios provisionales",
        "",
        "| Objeto | Tipo | Plantas | Alto (m) | Manzana | Planta (m2) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ])
    for item in report["buildings_detail"]:
        lines.append(
            f"| {item['name']} | {item['type']} | {item['floors']} | "
            f"{item['height_m']} | {item['block_id']} | {item['footprint_m2']} |")
    lines.append("")
    return "\n".join(lines)


def generate_urban(args, logger):
    """Calles 3D + zona urbana provisional, guardada en Baradero_3D.blend."""
    import bpy

    config_path = _resolve(args.config)
    source = _resolve(args.source)
    output = _resolve(args.output)
    if not source.is_file():
        raise FileNotFoundError(f"No existe el .blend de origen: {source}")
    if source.resolve() == output.resolve():
        raise ValueError("La salida no puede ser el mismo archivo que la entrada")
    config = common.load_config(config_path)
    osm_path = _resolve(config["osm"])
    if not osm_path.is_file():
        raise FileNotFoundError(f"Falta el extracto OSM: {osm_path}")

    logger.info("Abriendo %s", source)
    bpy.ops.wm.open_mainfile(filepath=str(source))

    report, osm, matched = inspection.inspect(bpy, config, osm_path)
    logger.info(
        "Calles verificadas: %d; error maximo %.6f m; OSM %s",
        len(matched), report["alignment"]["max_error_m"], osm_path.name)

    if not args.skip_backup:
        backup(bpy, source, logger)
    backup_existing_output(output, logger)

    streets_report = streets.build(bpy, config, osm, logger)
    urban_report = urban.build(bpy, config, osm, logger)

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    logger.info("Guardado: %s", output)

    urban_report["output_blend"] = str(output)
    urban_report["source_blend"] = str(source)
    urban_report["generated_at"] = datetime.now().isoformat(timespec="seconds")
    urban_report["source_sha256"] = report["osm"]["sha256"]
    urban_report["streets"] = {
        name: layer["objects"] for name, layer in streets_report["layers"].items()}
    write_json(common.ROOT / "docs" / "informe_baradero_3d.json", urban_report)
    write_text(common.ROOT / "docs" / "informe_baradero_3d.md", urban_markdown(urban_report))
    logger.info(
        "Zona urbana completa: %d edificios provisionales, %d arboles, %d postes, %d senales",
        urban_report["buildings"], urban_report["trees"],
        urban_report["lamps"], urban_report["signs"])
    return urban_report


def realista_markdown(report):
    plaza = report["plaza"]
    delegation = report["delegation"]
    lines = [
        "# Baradero 3D: Plaza Mitre y Municipalidad (aprox.)",
        "",
        f"- Generado con Blender **{report['blender_version']}**.",
        f"- Archivo de salida: `{report['output_blend']}`.",
        f"- Archivo base: `{report['source_blend']}`.",
        f"- Calles verificadas contra el OSM antes de construir: **{report['osm_alignment']['matched_ways']}**; "
        f"error maximo **{report['osm_alignment']['max_error_m']:.6f} m**.",
        "",
        "## Plaza Mitre",
        "",
        f"- Centro aproximado (UTM local): ({plaza['center'][0]:.1f}, {plaza['center'][1]:.1f}) m.",
        f"- Arboles: **{plaza['trees']}** (jacarandaes {plaza['jacarandas']}, "
        f"palmeras {plaza['palms']}, copa {plaza['green_trees']}), "
        f"arbustos {plaza['shrubs']}.",
        f"- Bancos: **{plaza['benches']}**; faroles: **{plaza['lamps']}**; cestos: {plaza['bins']}.",
        f"- Monumento al Condor en el centro, con tres escalones de piedra y condor de alas abiertas.",
        "",
        "## Municipalidad",
        "",
        f"- Huella OSM: way/{report['osm']['townhall_way']} (Av. San Martin 905).",
        f"- Dimensiones del volumen: **{delegation['width']:.1f} x {delegation['depth']:.1f} m**, "
        f"alto **{delegation['height']:.1f} m**.",
        f"- Frente a **{delegation['front_distance_plaza']:.1f} m** del borde de Plaza Mitre.",
        f"- Objetos: `{delegation['object']}`, rampa `{delegation['ramp']}`, "
        f"escudo `{delegation['logo']}`, panel `{delegation['panel']}`.",
        "",
        "## Camaras",
        "",
    ]
    for key, name in report["cameras"].items():
        lines.append(f"- {key}: `{name}`")
    lines.extend([
        "",
        "## Fotografias usadas",
        "",
        *[f"- `{path}`" for path in report["source_photos"]["plaza"]],
        *[f"- `{path}`" for path in report["source_photos"]["delegacion"]],
        "",
        "## Limitaciones",
        "",
        *[f"- {item}" for item in report["limitations"]],
        "",
        "## Verificacion de no destruccion",
        "",
        "- La reconstruccion se agrega en `BARA_LUGARES_REALES`, hija de `BARA_MAPA_3D`.",
        "- No se borro ninguna calle, cordon, vereda ni edificio provisional existente.",
        "",
    ])
    return "\n".join(lines)


def generate_realista(args, logger):
    """Plaza Mitre + Municipalidad sobre la escena 3D existente."""
    import bpy
    from . import landmarks

    config_path = _resolve(args.config)
    source = _resolve(args.source)
    output = _resolve(args.output)
    if not source.is_file():
        raise FileNotFoundError(f"No existe el .blend de origen: {source}")
    if source.resolve() == output.resolve():
        raise ValueError("La salida no puede ser el mismo archivo que la entrada")
    config = common.load_config(config_path)
    osm_path = _resolve(config["osm"])
    if not osm_path.is_file():
        raise FileNotFoundError(f"Falta el extracto OSM: {osm_path}")

    logger.info("Abriendo %s", source)
    bpy.ops.wm.open_mainfile(filepath=str(source))

    base_report, osm, matched = inspection.inspect(bpy, config, osm_path)
    logger.info(
        "Base verificada: %d calles, error maximo %.6f m; OSM %s",
        len(matched), base_report["alignment"]["max_error_m"], osm_path.name)

    if not args.skip_backup:
        backup(bpy, source, logger)
    backup_existing_output(output, logger)

    landmarks_report = landmarks.build(bpy, config, osm, logger)
    landmarks_report["output_blend"] = str(output)
    landmarks_report["source_blend"] = str(source)
    landmarks_report["generated_at"] = datetime.now().isoformat(timespec="seconds")
    landmarks_report["source_sha256"] = base_report["osm"]["sha256"]
    landmarks_report["osm_alignment"] = {
        "matched_ways": len(matched),
        "max_error_m": base_report["alignment"]["max_error_m"],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    logger.info("Guardado: %s", output)
    write_json(common.ROOT / "docs" / "informe_baradero_realista_v2.json", landmarks_report)
    write_text(common.ROOT / "docs" / "informe_baradero_realista_v2.md",
               realista_markdown(landmarks_report))
    logger.info(
        "Realista v2 completa: %d arboles, %d bancos, %d faroles, delegacion %.1f x %.1f m",
        landmarks_report["plaza"]["trees"], landmarks_report["plaza"]["benches"],
        landmarks_report["plaza"]["lamps"], landmarks_report["delegation"]["width"],
        landmarks_report["delegation"]["depth"])
    return landmarks_report


def run_realista_entry(name):
    logger = None
    try:
        args = parse_args(
            sys.argv,
            default_output="mapa/blender/Baradero_Realista_v2.blend",
            default_source="mapa/blender/Baradero_3D.blend")
        logger, log_path = common.setup_logging(name, common.ROOT / "mapa" / "logs")
        logger.info("Argumentos: %s", vars(args))
        generate_realista(args, logger)
        logger.info("Proceso terminado; log: %s", log_path)
        return 0
    except SystemExit:
        raise
    except Exception:
        trace = traceback.format_exc()
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_path = common.ROOT / "mapa" / "logs" / f"error_{name}_{stamp}.log"
            write_text(error_path, trace)
            if logger:
                logger.error("Fallo registrado en %s", error_path)
        except Exception:
            pass
        print(trace, file=sys.stderr)
        return 1


def run_urban_entry(name):
    logger = None
    try:
        args = parse_args(sys.argv, default_output="mapa/blender/Baradero_3D.blend")
        logger, log_path = common.setup_logging(name, common.ROOT / "mapa" / "logs")
        logger.info("Argumentos: %s", vars(args))
        generate_urban(args, logger)
        logger.info("Proceso terminado; log: %s", log_path)
        return 0
    except SystemExit:
        raise
    except Exception:
        trace = traceback.format_exc()
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_path = common.ROOT / "mapa" / "logs" / f"error_{name}_{stamp}.log"
            write_text(error_path, trace)
            if logger:
                logger.error("Fallo registrado en %s", error_path)
        except Exception:
            pass
        print(trace, file=sys.stderr)
        return 1


def run_entry(name, generate_report=True):
    """Envuelve la ejecucion, registra errores y devuelve un codigo de salida."""
    logger = None
    try:
        args = parse_args(sys.argv)
        logger, log_path = common.setup_logging(name, common.ROOT / "mapa" / "logs")
        logger.info("Argumentos: %s", vars(args))
        generate(args, logger)
        logger.info("Proceso terminado; log: %s", log_path)
        return 0
    except SystemExit:
        raise
    except Exception:
        trace = traceback.format_exc()
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_path = common.ROOT / "mapa" / "logs" / f"error_{name}_{stamp}.log"
            write_text(error_path, trace)
            if logger:
                logger.error("Fallo registrado en %s", error_path)
        except Exception:
            pass
        print(trace, file=sys.stderr)
        return 1
