"""Verificador de Baradero_Realista_v2.blend (Blender 4.2, proceso aparte).

Uso:
  "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe" ^
    --background --factory-startup --python scripts\\verificar_baradero_realista_v2.py

No modifica ni guarda el archivo verificado.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mapa_baradero import common  # noqa: E402

common.add_dependency_path()

from mapa_baradero.verify_realista import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
