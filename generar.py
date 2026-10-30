#!/usr/bin/env python3
"""
Genera las listas de charlas y cursos a partir de datos.xml.

    python3 generar.py

Reescribe lo que haya entre los marcadores
    <!-- auto:talks -->  ...  <!-- /auto:talks -->
en talks.html y teaching.html.  Todo lo demas de esas paginas queda
intacto, asi que se pueden seguir editando a mano.

Solo usa la libreria estandar de Python 3: no hay nada que instalar.
"""

import html
import sys
from datetime import date, timedelta
import xml.etree.ElementTree as ET
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DATOS = AQUI / "datos.xml"

# que seccion del xml va en que archivo
DESTINOS = {
    "talks": "talks.html",
    "minicourses": "talks.html",
    "courses": "teaching.html",
    "assistantships": "teaching.html",
    "conferences": "misc.html",
}

MESES_LARGOS = [""] + (
    "January February March April May June July August September "
    "October November December").split()

MESES = {m: m[:3] for m in MESES_LARGOS[1:]}


def esc(s):
    return html.escape(s or "", quote=True)


def texto(nodo, tag):
    hijo = nodo.find(tag)
    return (hijo.text or "").strip() if hijo is not None else ""


def enlaces(nodo):
    """<link label="PDF" href="..."/> -> [(etiqueta, url), ...]"""
    return [(e.get("label") or "Link", e.get("href") or "")
            for e in nodo.findall("link")]


def fila_meta(etiqueta, contenido):
    return f"<dt>{esc(etiqueta)}</dt>\n<dd>{contenido}</dd>" if contenido else ""


def entrada(insignia, titulo, filas, ancha=False, meta=""):
    """Una entrada plegable, igual que las de la pagina de research."""
    filas = [f for f in filas if f]
    cuerpo = "\n".join(filas)
    clase = "entry-num is-wide" if ancha else "entry-num"
    linea_meta = f'<span class="entry-meta">{esc(meta)}</span>' if meta else ""
    return f'''<details class="entry">
<summary>
<span class="entry-row">
<span class="{clase}">{esc(insignia)}</span>
<span class="entry-text"><span class="entry-title">{esc(titulo)}</span>{linea_meta}</span>
<span class="entry-chevron" aria-hidden="true">&#9654;</span>
</span>
</summary>
<div class="entry-body">
<dl class="meta">
{cuerpo}
</dl>
</div>
</details>'''


def por_anio(nodos, render):
    """Agrupa por el atributo year, respetando el orden del xml."""
    salida, anio_actual = [], None
    for n in nodos:
        anio = n.get("year", "")
        if anio != anio_actual:
            salida.append(f'<h3 class="subhead">{esc(anio)}</h3>')
            anio_actual = anio
        salida.append(render(n))
    return "\n\n".join(salida)


# ---------------------------------------------------------------- secciones

def tabla_talks(nodos):
    """Las charlas van en una tabla, no en entradas plegables.

    El atributo data-label de cada celda lo usa el css para apilar la
    tabla en pantallas angostas, donde no cabe en cuatro columnas."""
    filas = []
    for t in nodos:
        mes = MESES.get(t.get("month", ""), t.get("month", ""))
        fecha = f"{mes} {t.get('year', '')}".strip()
        ls = " ".join(f'<a href="{esc(u)}">{esc(l)}</a>' for l, u in enlaces(t))
        filas.append(
            "<tr>\n"
            f'<td class="col-date" data-label="Date">{esc(fecha)}</td>\n'
            f'<td class="col-title" data-label="Talk">{esc(texto(t, "title"))}</td>\n'
            f'<td class="col-where" data-label="Where">{esc(texto(t, "where"))}</td>\n'
            f'<td class="col-links" data-label="Slides">{ls}</td>\n'
            "</tr>"
        )
    cuerpo = "\n".join(filas)
    return f'''<div class="tabla-scroll">
<table class="tabla">
<thead>
<tr>
<th scope="col">Date</th>
<th scope="col">Talk</th>
<th scope="col">Where</th>
<th scope="col">Slides</th>
</tr>
</thead>
<tbody>
{cuerpo}
</tbody>
</table>
</div>'''


def render_minicourse(m):
    ev = m.find("event")
    nombre_ev = (ev.text or "").strip() if ev is not None else texto(m, "event")
    if ev is not None and ev.get("href"):
        evt = f'<a href="{esc(ev.get("href"))}">{esc(nombre_ev)}</a>'
    else:
        evt = esc(nombre_ev)
    ls = "".join(f'<a href="{esc(u)}">{esc(l)}</a> ' for l, u in enlaces(m))
    return entrada(
        m.get("year", ""),
        texto(m, "title"),
        [fila_meta("Event", evt),
         fila_meta("Where", esc(texto(m, "where"))),
         fila_meta("Notes", ls.strip())],
        ancha=True,
        # el mismo curso se ha dictado en varios eventos: sin esto, dos
        # entradas distintas se ven identicas cuando estan plegadas
        meta=nombre_ev,
    )


def render_course(c):
    ls = "".join(f'<a href="{esc(u)}">{esc(l)}</a> ' for l, u in enlaces(c))
    return entrada(
        c.get("term", ""),
        texto(c, "title"),
        [fila_meta("Program", esc(texto(c, "program"))),
         fila_meta("Page", ls.strip())],
        ancha=True,
    )


def render_assistantship(a):
    return entrada(
        a.get("term", ""),
        texto(a, "title"),
        [fila_meta("Program", esc(texto(a, "program"))),
         fila_meta("Details", esc(texto(a, "notes")))],
        ancha=True,
    )


def _fin_de(conf):
    """Ultimo dia del evento.  from='2026-10' vale hasta fin de octubre."""
    desde = conf.get("from", "")
    hasta = conf.get("to") or desde
    partes = [int(p) for p in hasta.split("-")]
    if len(partes) == 3:
        return date(*partes)
    y, m = partes[0], partes[1]
    return date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)


def _conferencia(c):
    titulo, href = texto(c, "title"), texto(c, "href")
    donde, fin = texto(c, "where"), _fin_de(c)
    enlace = f'<a href="{esc(href)}">{esc(titulo)}</a>' if href else esc(titulo)
    cola = ", ".join(x for x in (donde, f"{MESES_LARGOS[fin.month]} {fin.year}") if x)
    return (f'<li data-until="{fin.isoformat()}">'
            f"<b>{enlace}</b> "
            f'<span class="note">{esc(cola)}.</span></li>')


def listas_conferencias(nodos):
    """Dos listas: lo que viene y lo que ya paso.

    El reparto se hace con la fecha de hoy, pero ademas cada <li> lleva
    su fecha en data-until, para que el script de misc.html pueda
    recorregirlo en el navegador si la pagina lleva tiempo sin regenerar."""
    hoy = date.today()
    futuras = [c for c in nodos if _fin_de(c) >= hoy]
    pasadas = [c for c in nodos if _fin_de(c) < hoy]
    futuras.sort(key=_fin_de)                 # la mas proxima primero
    pasadas.sort(key=_fin_de, reverse=True)   # la mas reciente primero
    arma = lambda xs: "\n".join(_conferencia(c) for c in xs)
    return {
        "conferences-future": f'<ul class="linklist" id="future-events">\n'
                              f"{arma(futuras)}\n</ul>",
        "conferences-past": f'<ul class="linklist" id="past-events">\n'
                            f"{arma(pasadas)}\n</ul>",
    }


# cada seccion se arma entera con una de estas funciones
SECCIONES = {
    "conferences": listas_conferencias,
    "talks": tabla_talks,
    # son pocos y la insignia ya lleva el año: no hacen falta subtitulos
    "minicourses": lambda ns: "\n\n".join(render_minicourse(n) for n in ns),
    "courses": lambda ns: por_anio(ns, render_course),
    "assistantships": lambda ns: por_anio(ns, render_assistantship),
}


# ------------------------------------------------------------------ escribir

def reemplazar(archivo, nombre, html_nuevo):
    ruta = AQUI / archivo
    texto_pag = ruta.read_text(encoding="utf-8")
    ini, fin = f"<!-- auto:{nombre} -->", f"<!-- /auto:{nombre} -->"
    if ini not in texto_pag or fin not in texto_pag:
        sys.exit(f"ERROR: faltan los marcadores {ini} ... {fin} en {archivo}")
    antes = texto_pag.split(ini)[0]
    despues = texto_pag.split(fin, 1)[1]
    ruta.write_text(f"{antes}{ini}\n{html_nuevo}\n{fin}{despues}", encoding="utf-8")


def main():
    if not DATOS.exists():
        sys.exit(f"ERROR: no encuentro {DATOS}")
    raiz = ET.parse(DATOS).getroot()

    for nombre, archivo in DESTINOS.items():
        bloque = raiz.find(nombre)
        if bloque is None:
            print(f"  aviso: no hay seccion <{nombre}> en datos.xml")
            continue
        nodos = list(bloque)
        resultado = SECCIONES[nombre](nodos)
        if isinstance(resultado, dict):          # una seccion, varias regiones
            for region, trozo in resultado.items():
                reemplazar(archivo, region, trozo)
        else:
            reemplazar(archivo, nombre, resultado)
        print(f"  {nombre:16} {len(nodos):3} entradas -> {archivo}")

    print("listo.")


if __name__ == "__main__":
    main()
