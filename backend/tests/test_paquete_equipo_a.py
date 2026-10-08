"""
Integración con el paquete de datos del equipo A (ingesta.cargar_paquete).
Se salta si el repo no tiene la carpeta ingesta/ al lado de backend/.
"""

from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).parent.parent.parent
DATOS = RAIZ_REPO / 'datos'

pytestmark = pytest.mark.skipif(not (RAIZ_REPO / 'ingesta').exists() or not (DATOS / 'manifest.json').exists(),
                                reason='falta ingesta/ o datos/ del equipo A')


def test_carga_con_el_cargador_de_a_y_fecha_de_corte_del_manifest():
    from nucleo.pipeline import cargar_desde_paquete
    noticias, indicadores, sismos, fecha_corte = cargar_desde_paquete(DATOS)
    assert noticias and len(indicadores) > 0 and sismos
    assert fecha_corte and fecha_corte.endswith('Z')
    # Cada noticia sale con su fecha y su tipo (nunca una detección presentada como publicación)
    assert all(n['tipo_fecha'] in ('publicacion', 'deteccion', 'primera_aparicion') for n in noticias)
