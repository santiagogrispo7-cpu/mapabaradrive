"""Entrada para Blender: Fase 1 + Fase 2 (calles 3D).

Uso (Windows, consola):
  blender --background --factory-startup --python scripts\\generar_mapa_baradero.py -- ^
    --source mapa/blender/Baradero_mapa.blend ^
    --output mapa/blender/Baradero_mapa_3d.blend

Solo diagnostico:
  ... --python scripts\\generar_mapa_baradero.py -- --inspect-only
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mapa_baradero import common  # noqa: E402

common.add_dependency_path()

from mapa_baradero.runner import run_entry  # noqa: E402

if __name__ == "__main__":
    sys.exit(run_entry("generar_mapa"))
