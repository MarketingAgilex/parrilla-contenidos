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
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "908d8f935b2c833aa436011b3d10e8c0").strip()
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


def get(url, version):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}", "Notion-Version": version})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def paginar(url, version):
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


def leer_fuentes(database_id):
    """Lee todas las fuentes de datos (pestañas) de la base y las une."""
    db = get(f"https://api.notion.com/v1/databases/{database_id}", "2025-09-03")
    fuentes = db.get("data_sources", [])
    print(f"Base {database_id}: última edición {db.get('last_edited_time')}; fuentes: " + ", ".join(f"{f.get('name')} ({f.get('id')})" for f in fuentes), file=sys.stderr)
    paginas = []
    for f in fuentes:
        filas = paginar(f"https://api.notion.com/v1/data_sources/{f['id']}/query", "2025-09-03")
        ult = max((p.get("last_edited_time", "") for p in filas), default="")
        print(f"  Fuente '{f.get('name')}': {len(filas)} filas, última fila editada {ult}", file=sys.stderr)
        if filas:
            props = filas[0].get("properties", {})
            print("  Columnas: " + ", ".join(f"{k} ({v.get('type')})" for k, v in props.items()), file=sys.stderr)
            fechas = [next((v for k, v in p.get("properties", {}).items() if v.get("type") == "date"), None) for p in filas]
            con = [x for x in fechas if x and x.get("date")]
            print(f"  Filas con fecha: {len(con)} de {len(filas)}. Ejemplo: {json.dumps(con[0] if con else fechas[0], ensure_ascii=False)[:300]}", file=sys.stderr)
        paginas.extend(filas)
    return paginas


def diagnostico():
    try:
        res = post("https://api.notion.com/v1/search", {"page_size": 50, "sort": {"direction": "descending", "timestamp": "last_edited_time"}}, "2025-09-03")
        for o in res.get("results", [])[:20]:
            t = o.get("title") or (o.get("properties", {}).get("title", {}) or {}).get("title") or []
            nombre = "".join(x.get("plain_text", "") for x in t) if isinstance(t, list) else str(t)
            print(f"  Visible: [{o.get('object')}] {nombre} · editado {o.get('last_edited_time')} · {o.get('id')}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        print(f"Diagnóstico falló: {e.code}", file=sys.stderr)


def leer_todo():
    diagnostico()
    try:
        return leer_fuentes(DATABASE_ID)
    except urllib.error.HTTPError as e:
        print(f"Lectura por fuentes falló: {e.code} {e.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
    # Respaldo: busca por nombre las bases que la conexión puede ver.
    intentos = []
    try:
        res = post("https://api.notion.com/v1/search", {"query": "PARRILLA", "filter": {"property": "object", "value": "database"}, "page_size": 50}, "2022-06-28")
        bases = res.get("results", [])
        titulo = lambda b: "".join(t.get("plain_text", "") for t in b.get("title", [])).upper()
        bases.sort(key=lambda b: ("PARRILLA DE CONTENIDOS" not in titulo(b), b.get("last_edited_time", "")), reverse=False)
        print("Bases visibles para la conexión: " + ", ".join(f"{titulo(b)} ({b['id']})" for b in bases), file=sys.stderr)
        for b in bases:
            if "PARRILLA" in titulo(b):
                intentos.append((f"https://api.notion.com/v1/databases/{b['id']}/query", "2022-06-28"))
                break
    except urllib.error.HTTPError as e:
        print(f"Búsqueda por nombre falló: {e.code} {e.read().decode('utf-8', 'replace')[:300]}", file=sys.stderr)
    intentos += [
        (f"https://api.notion.com/v1/databases/{DATABASE_ID}/query", "2022-06-28"),
        (f"https://api.notion.com/v1/data_sources/{DATA_SOURCE_ID}/query", "2025-09-03"),
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


def _clave(texto):
    import unicodedata
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).casefold().replace(" ", "").replace("/", "")


def valor(pagina, nombre):
    props = pagina.get("properties", {})
    p = props.get(nombre)
    if p is None:
        objetivo = _clave(nombre)
        p = next((v for k, v in props.items() if _clave(k) == objetivo), None)
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
