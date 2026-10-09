# Datos de ejemplo congelados

Estos archivos (`eventos.json`, `fichas.jsonl`, `excluidas_idioma.json`) son la salida del
núcleo sobre los datos sintéticos de `backend/datos_ejemplo/`, **congelada** para que las
pruebas de la interfaz (`interfaz/tests/`) tengan siempre los mismos datos.

- El pipeline **no** escribe aquí: sus corridas de ejemplo van a `artefactos/ejemplo_corrida/`.
- Las fichas de este archivo están hechas por plantilla, así que ninguna queda bloqueada por
  el validador. Las pruebas de la interfaz dependen de eso.
- Si hace falta regenerarlos, avisar antes al equipo de la interfaz y correr sus pruebas
  (`python -m pytest` desde la raíz) después del cambio.
