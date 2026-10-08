"""T10 · Sin internet durante la demo.

Esperado: funcionar con el snapshot y un fallback documentado.
"""

from pathlib import Path

import pytest
from conftest import cargar_json

from ingesta import cargar_paquete
from ingesta.carga import DIRECTORIO, NOTICIAS
from ingesta.comun import sha256_archivo

hay_snapshot = pytest.mark.skipif(
    not (DIRECTORIO / "manifest.json").exists(), reason="el snapshot real aún no se ha construido"
)


def test_la_carga_no_abre_ninguna_conexion(paquete_valido, sin_internet):
    paquete = cargar_paquete(paquete_valido)

    assert len(paquete.noticias) == 3
    assert len(paquete.indicadores) == 3
    assert len(paquete.eventos) == 2
    assert paquete.integro


def test_el_manifest_guarda_la_huella_de_cada_archivo(paquete_valido):
    manifest = cargar_json(paquete_valido / "manifest.json")

    for relativa, datos in manifest["archivos"].items():
        assert datos["sha256"] == sha256_archivo(paquete_valido / relativa)
        assert len(datos["sha256"]) == 64
    assert manifest["fecha_corte_UTC"].endswith("Z")


def test_un_archivo_alterado_se_detecta_y_la_demo_sigue(paquete_valido, sin_internet):
    ruta = paquete_valido / NOTICIAS
    ruta.write_text(ruta.read_text(encoding="utf-8").replace("Titular de prueba 1", "Titular cambiado"),
                    encoding="utf-8")

    paquete = cargar_paquete(paquete_valido)

    assert not paquete.integro
    assert any("no coincide con el SHA-256" in incidencia for incidencia in paquete.incidencias)
    assert len(paquete.noticias) == 3
    assert paquete.reporte["incidencias"] == paquete.incidencias


def test_un_archivo_ausente_no_tumba_la_demo(paquete_valido, sin_internet):
    (paquete_valido / "processed/indicadores.csv").unlink()

    paquete = cargar_paquete(paquete_valido)

    assert paquete.indicadores == []
    assert len(paquete.noticias) == 3
    assert any("Falta el archivo processed/indicadores.csv" in i for i in paquete.incidencias)


def test_sin_manifest_se_carga_pero_se_avisa(paquete_valido, sin_internet):
    (paquete_valido / "manifest.json").unlink()

    paquete = cargar_paquete(paquete_valido)

    assert len(paquete.noticias) == 3
    assert not paquete.integro
    assert "manifest.json" in paquete.incidencias[0]


def test_una_carpeta_vacia_devuelve_un_paquete_vacio(tmp_path, sin_internet):
    paquete = cargar_paquete(tmp_path)

    assert paquete.noticias == [] and paquete.indicadores == [] and paquete.eventos == []
    assert not paquete.integro


@hay_snapshot
def test_el_snapshot_real_carga_integro_y_sin_red(sin_internet):
    paquete = cargar_paquete()

    assert paquete.integro, paquete.incidencias
    assert len(paquete.noticias) >= 100
    assert paquete.reporte["noticias"]["de_tvn"] >= 20
    assert len(paquete.indicadores) == 6 * 6 * 15
    assert len(paquete.eventos) > 0
    assert all(Path(DIRECTORIO / relativa).exists() for relativa in paquete.manifest["archivos"])
