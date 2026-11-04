"""Lee la parrilla de contenidos de Notion y la guarda en data.json para el tablero.

Se ejecuta desde GitHub Actions (.github/workflows/actualizar-parrilla.yml).
Necesita el secreto NOTION_TOKEN (token de una integración interna de Notion
conectada a la base "PARRILLA DE CONTENIDOS ÁGILEX").
Solo usa la librería estándar de Python.
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "1a67e73023f4836cbf76819d122b1863").strip()
DATA_SOURCE_ID = os.environ.get("NOTION_DATA_SOURCE_ID", "8fd7e730-23f4-8356-8a72-87349b91cf22").strip()
SALIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json")


def post(url, body, version):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Notion-Version": version,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def leer_todo():
    # Primero la API actual (data sources); si no está disponible, la API clásica de bases de datos.
    intentos = [
        (f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query", "2025-09-03"),
        (f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", "2022-06-28"),
    ]
    ultimo_error = None
    for url, version in intentos:
        try:
            paginas, cursor = [], None
            while True:
                body = {"page_size": 100}
                if cursor:
                    body["start_cursor"] = cursor
                res = post(url, body, version)
                paginas.extend(res.get("results", []))
                if not res.get("has_more"):
                    return paginas
                cursor = res.get("next_cursor")
        except urllib.error.HTTPError as e:
            ultimo_error = f"{e.code} {e.read().decode('utf-8', 'replace')[:400]}"
            print(f"Intento con {url} falló: {ultimo_error}", file=sys.stderr)
    sys.exit(
        "No se pudo leer la parrilla en Notion. Revisa que el secreto NOTION_TOKEN sea correcto "
        "y que la integración esté conectada a la base (··· → Conexiones). Detalle: " + str(ultimo_error)
    )


def valor(pagina, nombre):
    p = pagina.get("properties", {}).get(nombre)
    if not p:
        return None
    t = p.get("type")
    v = p.get(t)
    if t in ("title", "rich_text"):
        texto = "".join(x.get("plain_text", "") for x in (v or [])).strip()
        return texto or None
    if t in ("select", "status"):
        return v.get("name") if v else None
    if t == "multi_select":
        return [o.get("name") for o in (v or []) if o.get("name")]
    if t == "date":
        return v.get("start", "")[:10] if v and v.get("start") else None
    if t in ("url", "number", "checkbox"):
        return v
    return None


def lista(x):
    return x if isinstance(x, list) else []


def main():
    if not TOKEN:
        sys.exit("Falta el secreto NOTION_TOKEN en GitHub (Settings → Secrets and variables → Actions).")

    piezas = []
    for pg in leer_todo():
        if pg.get("archived") or pg.get("in_trash"):
            continue
        nombre = valor(pg, "Video")
        if not nombre:
            continue
        piezas.append({
            "id": pg.get("id"),
            "url": pg.get("url"),
            "pieza": nombre,
            "fecha": valor(pg, "Fecha publicación"),
            "estado": valor(pg, "Status"),
            "formato": valor(pg, "Tipo"),
            "categorias": lista(valor(pg, "Categoria")),
            "redes": lista(valor(pg, "Red Social")),
            "paises": lista(valor(pg, "País")),
            "marca": valor(pg, "Marca / Cuenta"),
            "servicios": lista(valor(pg, "Servicio")),
            "etapa": valor(pg, "Etapa embudo"),
            "tiene_referencia": 1 if valor(pg, "Referencia") else 0,
            "tiene_link": 1 if valor(pg, "Link publicación") else 0,
            "alcance": valor(pg, "Alcance"),
            "interacciones": valor(pg, "Interacciones"),
            "leads": valor(pg, "Leads / mensajes"),
        })

    piezas.sort(key=lambda r: (r["fecha"] is None, r["fecha"] or "", r["pieza"].lower()))

    anterior = None
    if os.path.exists(SALIDA):
        try:
            with open(SALIDA, encoding="utf-8") as f:
                anterior = json.load(f)
        except Exception:
            anterior = None

    if anterior and anterior.get("piezas") == piezas:
        print(f"Sin cambios en la parrilla ({len(piezas)} piezas).")
        return

    salida = {
        "actualizado": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "fuente": "Notion · PARRILLA DE CONTENIDOS ÁGILEX",
        "piezas": piezas,
    }
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    print(f"data.json actualizado: {len(piezas)} piezas.")


if __name__ == "__main__":
    main()
