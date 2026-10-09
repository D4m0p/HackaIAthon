"""Ayudas compartidas por las pruebas de la interfaz."""

REVISORA = "Persona de Prueba"


def caso_con(aplicacion, **condiciones):
    """Primer caso de la bandeja que cumple todas las condiciones dadas."""
    return next(fila for fila in aplicacion.bandeja()
                if all(fila[clave] == valor for clave, valor in condiciones.items()))
