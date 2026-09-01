"""
app.py
------
Servidor de CAFETIX JOACO.

El catálogo busca, filtra y ordena con Python.
Las demás páginas se muestran como HTML.

Cómo ejecutarlo:
  py -m pip install Flask
  py app.py
  Abrir: http://localhost:5001/catalogo.html

Todavía NO conectamos MySQL.
"""

from pathlib import Path
import webbrowser
from threading import Timer

from flask import Flask, render_template, request, send_from_directory

CARPETA = Path(__file__).resolve().parent
CARPETA_HTML = CARPETA / "html"
CARPETA_CSS = CARPETA / "css"
CARPETA_IMG = CARPETA / "img"

app = Flask(__name__, template_folder=str(CARPETA_HTML))

# Productos de ejemplo. Más adelante vendrán de MySQL.
PRODUCTOS = [
    {"nombre": "Gaseosa negra", "precio": 3000, "cantidad": 18, "categoria": "bebidas", "imagen": "gaseosa-negra.svg", "destacado": True, "busqueda": "gaseosa negra coca-cola coca cola"},
    {"nombre": "Empanada", "precio": 2000, "cantidad": 15, "categoria": "comidas", "imagen": "empanada.svg", "destacado": True, "busqueda": "empanada"},
    {"nombre": "Dedo de bocadillo", "precio": 1500, "cantidad": 10, "categoria": "mecato", "imagen": "bocadillo.svg", "destacado": True, "busqueda": "dedo de bocadillo bocadillo"},
    {"nombre": "Jugo natural", "precio": 2500, "cantidad": 10, "categoria": "bebidas", "imagen": "jugo.svg", "destacado": False, "busqueda": "jugo natural"},
    {"nombre": "Gaseosa", "precio": 3000, "cantidad": 18, "categoria": "bebidas", "imagen": "gaseosa.svg", "destacado": False, "busqueda": "gaseosa"},
    {"nombre": "Café con leche", "precio": 2000, "cantidad": 20, "categoria": "bebidas", "imagen": "cafe.svg", "destacado": False, "busqueda": "cafe con leche café"},
    {"nombre": "Arepa con queso", "precio": 3500, "cantidad": 12, "categoria": "comidas", "imagen": "arepa.svg", "destacado": False, "busqueda": "arepa con queso"},
    {"nombre": "Perro caliente", "precio": 4500, "cantidad": 6, "categoria": "comidas", "imagen": "perro.svg", "destacado": False, "busqueda": "perro caliente"},
    {"nombre": "Desayuno completo", "precio": 6500, "cantidad": 4, "categoria": "desayunos", "imagen": "desayuno.svg", "destacado": False, "busqueda": "desayuno completo"},
    {"nombre": "Almuerzo del día", "precio": 8000, "cantidad": 0, "categoria": "almuerzos", "imagen": "almuerzo.svg", "destacado": False, "busqueda": "almuerzo del dia día"},
    {"nombre": "Pan con chocolate", "precio": 1500, "cantidad": 8, "categoria": "mecato", "imagen": "pan.svg", "destacado": False, "busqueda": "pan con chocolate"},
    {"nombre": "Galletas", "precio": 1500, "cantidad": 0, "categoria": "mecato", "imagen": "galletas.svg", "destacado": False, "busqueda": "galletas"},
]

CATEGORIAS = [
    {"id": "todos", "nombre": "Todos"},
    {"id": "bebidas", "nombre": "Bebidas"},
    {"id": "comidas", "nombre": "Comidas"},
    {"id": "desayunos", "nombre": "Desayunos"},
    {"id": "almuerzos", "nombre": "Almuerzos"},
    {"id": "mecato", "nombre": "Mecato"},
]


def sin_tildes(texto):
    texto = texto.lower()
    for original, nuevo in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        texto = texto.replace(original, nuevo)
    return texto


def preparar(producto):
    """Prepara el producto para mostrarlo en el HTML."""
    copia = dict(producto)
    copia["precio_texto"] = "$" + f"{producto['precio']:,}".replace(",", ".")
    copia["disponible"] = producto["cantidad"] > 0
    nombre_cat = producto["categoria"]
    for item in CATEGORIAS:
        if item["id"] == producto["categoria"]:
            nombre_cat = item["nombre"]
    copia["categoria_nombre"] = nombre_cat
    return copia


def filtrar_productos(buscar="", categoria="todos", orden="default"):
    """Aplica búsqueda, categoría y orden. Sin MySQL todavía."""
    lista = list(PRODUCTOS)
    texto = sin_tildes((buscar or "").strip())
    categoria = categoria or "todos"
    orden = orden or "default"

    if texto:
        lista = [p for p in lista if texto in sin_tildes(p["busqueda"])]
    if categoria != "todos":
        lista = [p for p in lista if p["categoria"] == categoria]
    if orden == "precio-asc":
        lista.sort(key=lambda p: p["precio"])
    elif orden == "precio-desc":
        lista.sort(key=lambda p: p["precio"], reverse=True)
    return [preparar(p) for p in lista]


def obtener_destacados():
    return [preparar(p) for p in PRODUCTOS if p.get("destacado")]


def mostrar_html(nombre_archivo):
    return send_from_directory(CARPETA_HTML, nombre_archivo)


@app.route("/")
@app.route("/index.html")
def inicio():
    return mostrar_html("index.html")


@app.route("/registro.html")
def registro():
    return mostrar_html("registro.html")


@app.route("/login.html", methods=["GET", "POST"])
def login():
    return mostrar_html("login.html")


@app.route("/catalogo.html")
def catalogo():
    buscar = request.args.get("buscar", "")
    categoria = request.args.get("categoria", "todos")
    orden = request.args.get("orden", "default")
    return render_template(
        "catalogo.html",
        productos=filtrar_productos(buscar, categoria, orden),
        destacados=obtener_destacados(),
        categorias=CATEGORIAS,
        buscar=buscar,
        categoria=categoria,
        orden=orden,
    )


@app.route("/carrito.html")
def carrito():
    return mostrar_html("carrito.html")


@app.route("/pago.html")
def pago():
    return mostrar_html("pago.html")


@app.route("/turno.html")
def turno():
    return mostrar_html("turno.html")


@app.route("/css/<path:archivo>")
def css(archivo):
    return send_from_directory(CARPETA_CSS, archivo)


@app.route("/img/<path:archivo>")
def imagenes(archivo):
    return send_from_directory(CARPETA_IMG, archivo)


@app.route("/<nombre>.html")
def otras_paginas(nombre):
    if nombre == "catalogo":
        return catalogo()
    archivo = f"{nombre}.html"
    if (CARPETA_HTML / archivo).is_file():
        return mostrar_html(archivo)
    return "Página no encontrada", 404


@app.route("/html/<nombre>.html")
def pagina_en_html(nombre):
    if nombre == "catalogo":
        return catalogo()
    return otras_paginas(nombre)


if __name__ == "__main__":
    puerto = 5001
    direccion = f"http://localhost:{puerto}/catalogo.html"
    print("=" * 50)
    print("  CAFETIX JOACO")
    print("=" * 50)
    print(f"  Abre: {direccion}")
    print("  Presiona Ctrl+C para detener")
    print("=" * 50)
    Timer(1, lambda: webbrowser.open(direccion)).start()
    app.run(host="127.0.0.1", port=puerto, debug=True, use_reloader=False)
