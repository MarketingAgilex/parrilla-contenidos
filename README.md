# Parrilla de contenidos · Ágilex

Tablero web de la parrilla de contenidos de marketing, publicado en GitHub Pages y alimentado automáticamente desde Notion.

## Cómo funciona

1. Cada hora, la tarea `.github/workflows/actualizar-parrilla.yml` ejecuta `scripts/actualizar_notion.py`.
2. El script lee la base **PARRILLA DE CONTENIDOS ÁGILEX** en Notion con el token guardado en el secreto `NOTION_TOKEN` y escribe `data.json`.
3. Si la parrilla cambió, la tarea guarda el nuevo `data.json` en el repositorio y GitHub Pages publica la versión actualizada en uno o dos minutos.
4. `index.html` lee `data.json` y calcula atrasadas y próximos 7 días con la fecha del día (hora de Colombia).

## Actualizar a mano

Pestaña **Actions** → **Actualizar parrilla desde Notion** → **Run workflow**.

## Si deja de actualizarse

- Revisa en **Actions** el último resultado: el mensaje explica si el token es inválido o la integración perdió acceso a la base.
- GitHub pausa las tareas programadas tras 60 días sin actividad en el repositorio. Si aparece el aviso, pulsa **Enable workflow** en Actions.
