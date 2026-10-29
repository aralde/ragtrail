# Cómo arrancar la sesión

```bash
mkdir ragtrail && cd ragtrail
# copia aquí CLAUDE.md, PLAN.md y este KICKOFF.md
git init
claude
```

Pega esto como primer mensaje en Claude Code:

---

Este repo es **ragtrail**, una librería MIT en Python que cachea las trayectorias de recuperación de un agente RAG (el camino de búsquedas y nodos que llevó a una respuesta citada, nunca la respuesta) y las reutiliza en preguntas parecidas, invalidándolas por hash de contenido. Lee `CLAUDE.md` y `PLAN.md` completos antes de tocar nada.

Empieza por **M0**:
1. Repite en 3–5 líneas los criterios de aceptación de M0 y lista los archivos que vas a crear.
2. Verifica que `ragtrail` siga libre en PyPI. Si está tomado, para y avísame.
3. Haz el scaffold, los modelos, el protocolo `TrajectoryStore`, `SQLiteStore` con el layout de claves de `CLAUDE.md`, los tests y el CI.
4. Corre `uv run ruff check . && uv run mypy src && uv run pytest`, marca los checkboxes en `PLAN.md` y haz commit.

Cuando M0 pase, muéstrame un resumen corto y sigue con M1 y M2 sin esperar, salvo que una decisión no esté cubierta en `CLAUDE.md` y sea difícil de revertir. Las decisiones pequeñas anótalas en `docs/decisions.md`.

No toques AWS ni Azure hasta M6/M7, y nunca despliegues sin avisarme antes.

---

Cuando tengas el repo en GitHub (`aralde/ragtrail`), agrega el remoto y haz push después de cada hito.
