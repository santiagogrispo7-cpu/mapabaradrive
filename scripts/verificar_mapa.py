"""Entrada para Blender: verificacion independiente de las calles 3D.

Uso (Windows, consola):
  blender --background --factory-startup --python scripts\\verificar_mapa.py -- ^
    --file mapa/blender/Baradero_mapa_3d.blend

Escribe docs/verificacion_calles.json y vistas en docs/renders/.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mapa_baradero import common  # noqa: E402

common.add_dependency_path()

from mapa_baradero.verify import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
