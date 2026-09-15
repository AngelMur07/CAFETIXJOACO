"""
app.py
------
Servidor de CAFETIX JOACO.

El catálogo busca, filtra y ordena con Python.
Las demás páginas se muestran como HTML.

Cómo ejecutarlo:
    py -m pip install -r requirements.txt
    py app.py
    Abrir: http://localhost:5001/index.html

Todavía NO conectamos MySQL.
"""

from datetime import datetime, time
from pathlib import Path
from urllib.parse import quote
import webbrowser
from threading import Timer

from flask import Flask, render_template, request, send_from_directory, redirect, session

CARPETA = Path(__file__).resolve().parent
CARPETA_HTML = CARPETA / "html"
CARPETA_CSS = CARPETA / "css"
CARPETA_IMG = CARPETA / "img"

app = Flask(__name__, template_folder=str(CARPETA_HTML))
app.secret_key = "cafetix-joaco-estudiante"

# Productos de ejemplo. Más adelante vendrán de MySQL.
PRODUCTOS = [
    {"id": 1, "nombre": "Gaseosa negra", "precio": 3000, "cantidad": 18, "categoria": "bebidas", "imagen": "gaseosa-negra.svg", "destacado": True, "busqueda": "gaseosa negra coca-cola coca cola"},
    {"id": 2, "nombre": "Empanada", "precio": 2000, "cantidad": 15, "categoria": "comidas", "imagen": "empanada.svg", "destacado": True, "busqueda": "empanada"},
    {"id": 3, "nombre": "Dedo de bocadillo", "precio": 1500, "cantidad": 10, "categoria": "mecato", "imagen": "bocadillo.svg", "destacado": True, "busqueda": "dedo de bocadillo bocadillo"},
    {"id": 4, "nombre": "Jugo natural", "precio": 2500, "cantidad": 10, "categoria": "bebidas", "imagen": "jugo.svg", "destacado": False, "busqueda": "jugo natural"},
    {"id": 5, "nombre": "Gaseosa", "precio": 3000, "cantidad": 18, "categoria": "bebidas", "imagen": "gaseosa.svg", "destacado": False, "busqueda": "gaseosa"},
    {"id": 6, "nombre": "Café con leche", "precio": 2000, "cantidad": 20, "categoria": "bebidas", "imagen": "cafe.svg", "destacado": False, "busqueda": "cafe con leche café"},
    {"id": 7, "nombre": "Arepa con queso", "precio": 3500, "cantidad": 12, "categoria": "comidas", "imagen": "arepa.svg", "destacado": False, "busqueda": "arepa con queso"},
    {"id": 8, "nombre": "Perro caliente", "precio": 4500, "cantidad": 6, "categoria": "comidas", "imagen": "perro.svg", "destacado": False, "busqueda": "perro caliente"},
    {"id": 9, "nombre": "Desayuno completo", "precio": 6500, "cantidad": 4, "categoria": "desayunos", "imagen": "desayuno.svg", "destacado": False, "busqueda": "desayuno completo"},
    {"id": 10, "nombre": "Almuerzo del día", "precio": 8000, "cantidad": 0, "categoria": "almuerzos", "imagen": "almuerzo.svg", "destacado": False, "busqueda": "almuerzo del dia día"},
    {"id": 11, "nombre": "Pan con chocolate", "precio": 1500, "cantidad": 8, "categoria": "mecato", "imagen": "pan.svg", "destacado": False, "busqueda": "pan con chocolate"},
    {"id": 12, "nombre": "Galletas", "precio": 1500, "cantidad": 0, "categoria": "mecato", "imagen": "galletas.svg", "destacado": False, "busqueda": "galletas"},
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


def precio_en_texto(valor):
    return "$" + f"{int(valor):,}".replace(",", ".")


def preparar(producto):
    """Prepara el producto para mostrarlo en el HTML."""
    copia = dict(producto)
    copia["precio_texto"] = precio_en_texto(producto["precio"])
    copia["disponible"] = producto["cantidad"] > 0
    copia["estado"] = "Disponible" if producto["cantidad"] > 0 else "Agotado"
    nombre_cat = producto["categoria"]
    for item in CATEGORIAS:
        if item["id"] == producto["categoria"]:
            nombre_cat = item["nombre"]
    copia["categoria_nombre"] = nombre_cat
    return copia


def categorias_producto():
    return [item for item in CATEGORIAS if item["id"] != "todos"]


def imagenes_disponibles():
    carpeta = CARPETA_IMG / "productos"
    lista = []
    for archivo in sorted(carpeta.iterdir()):
        if archivo.is_file():
            lista.append(archivo.name)
    return lista


def buscar_producto(producto_id):
    for producto in PRODUCTOS:
        if producto["id"] == producto_id:
            return producto
    return None


def siguiente_id():
    mayor = 0
    for producto in PRODUCTOS:
        if producto["id"] > mayor:
            mayor = producto["id"]
    return mayor + 1


def validar_producto(nombre, categoria, precio_texto, cantidad_texto):
    if not nombre.strip():
        return "El nombre no puede estar vacío."
    ids_validos = [item["id"] for item in categorias_producto()]
    if categoria not in ids_validos:
        return "La categoría no es válida."
    try:
        precio = int(precio_texto)
    except ValueError:
        return "El precio debe ser mayor que 0."
    if precio <= 0:
        return "El precio debe ser mayor que 0."
    try:
        cantidad = int(cantidad_texto)
    except ValueError:
        return "Ingresa una cantidad válida."
    if cantidad < 0:
        return "Ingresa una cantidad válida."
    return ""


def descontar_inventario(producto_id, cantidad_comprada):
    """cantidad = cantidad - cantidad_comprada. Si llega a 0, el producto queda Agotado."""
    producto = buscar_producto(producto_id)
    if producto is None:
        return False
    nueva = producto["cantidad"] - cantidad_comprada
    if nueva < 0:
        nueva = 0
    producto["cantidad"] = nueva
    return True


def obtener_carrito():
    return list(session.get("carrito", []))


def guardar_carrito(items):
    session["carrito"] = items
    session.modified = True


def vaciar_carrito():
    session["carrito"] = []
    session.pop("paso_carrito", None)
    session.modified = True


def url_catalogo(aviso=""):
    """Vuelve al catálogo y conserva la búsqueda o el filtro que tenía el usuario."""
    buscar = request.form.get("buscar", "")
    categoria = request.form.get("categoria", "todos")
    orden = request.form.get("orden", "default")
    url = "/catalogo.html?categoria=" + quote(categoria)
    url = url + "&buscar=" + quote(buscar)
    url = url + "&orden=" + quote(orden)
    if aviso:
        url = url + "&aviso=" + quote(aviso)
    return url


def armar_lineas_carrito():
    """Arma el carrito con nombre, precio, subtotal y total. El cálculo es en Flask."""
    lineas = []
    total = 0
    for item in obtener_carrito():
        producto = buscar_producto(item["id"])
        if producto is None:
            continue
        cantidad = item["cantidad"]
        subtotal = producto["precio"] * cantidad
        total = total + subtotal
        lineas.append({
            "id": producto["id"],
            "nombre": producto["nombre"],
            "cantidad": cantidad,
            "precio": producto["precio"],
            "precio_texto": precio_en_texto(producto["precio"]),
            "subtotal": subtotal,
            "subtotal_texto": precio_en_texto(subtotal),
        })
    return lineas, total


def asignar_turno_cliente():
    """Da al comprador el siguiente número. No cambia el turno que llama el vendedor."""
    global ultimo_turno_asignado
    if ultimo_turno_asignado < turno_actual:
        ultimo_turno_asignado = turno_actual
    ultimo_turno_asignado = ultimo_turno_asignado + 1
    return ultimo_turno_asignado


def registrar_pedido(turno_cliente, lineas, total):
    """Guarda el pedido en memoria para el vendedor más adelante."""
    global siguiente_numero_pedido
    numero = siguiente_numero_pedido
    siguiente_numero_pedido = siguiente_numero_pedido + 1
    pedido = {
        "id": numero,
        "numero": "CJ-" + str(numero).zfill(3),
        "turno": turno_cliente,
        "productos": lineas,
        "total": total,
        "total_texto": precio_en_texto(total),
        "estado": "pendiente",
    }
    PEDIDOS.append(pedido)
    return pedido


ESTADOS_PEDIDO = {
    "pendiente": "Pendiente",
    "en_preparacion": "En preparación",
    "listo": "Listo",
    "entregado": "Entregado",
}

SIGUIENTE_ESTADO = {
    "pendiente": "en_preparacion",
    "en_preparacion": "listo",
    "listo": "entregado",
}

CLASE_ESTADO_PEDIDO = {
    "pendiente": "estado-pendiente",
    "en_preparacion": "estado-preparando",
    "listo": "estado-listo",
    "entregado": "estado-entregado",
}


def buscar_pedido(pedido_id):
    for pedido in PEDIDOS:
        if pedido["id"] == pedido_id:
            return pedido
    return None


def preparar_pedido_vista(pedido):
    """Prepara un pedido para mostrarlo en el panel del vendedor."""
    copia = dict(pedido)
    copia["estado_texto"] = ESTADOS_PEDIDO.get(pedido["estado"], "Pendiente")
    copia["estado_clase"] = CLASE_ESTADO_PEDIDO.get(pedido["estado"], "estado-pendiente")
    copia["siguiente_estado"] = SIGUIENTE_ESTADO.get(pedido["estado"], "")
    if copia["siguiente_estado"]:
        copia["siguiente_texto"] = ESTADOS_PEDIDO[copia["siguiente_estado"]]
    else:
        copia["siguiente_texto"] = ""
    return copia


def pedidos_para_vendedor():
    pendientes = []
    entregados = []
    for pedido in PEDIDOS:
        vista = preparar_pedido_vista(pedido)
        if pedido["estado"] == "entregado":
            entregados.append(vista)
        else:
            pendientes.append(vista)
    return pendientes, entregados


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


# Turno temporal. Más adelante este número se guardará en MySQL.
turno_actual = 1
ultimo_turno_asignado = 1

# Pedidos confirmados en memoria. El panel del vendedor los usará después.
PEDIDOS = []
siguiente_numero_pedido = 1

# Horarios de descanso de la cafetería.
HORARIOS_DESCANSO = [
    {"nombre": "Jornada mañana", "corto": "Mañana", "inicio": time(8, 35), "fin": time(9, 10), "texto": "8:35 AM - 9:10 AM"},
    {"nombre": "Jornada tarde", "corto": "Tarde", "inicio": time(15, 0), "fin": time(15, 30), "texto": "3:00 PM - 3:30 PM"},
    {"nombre": "Jornada noche", "corto": "Noche", "inicio": time(19, 45), "fin": time(20, 15), "texto": "7:45 PM - 8:15 PM"},
]

# Extensión temporal del descanso actual. Se borra al reiniciar Flask.
extension_hasta = None
extension_jornada = None

# Control manual del administrador o el vendedor. Vuelve a True al reiniciar Flask.
sistema_habilitado = True

MENSAJE_CERRADO = "El sistema de pedidos y turnos está disponible únicamente durante los horarios de descanso."
MENSAJE_DESHABILITADO = "El sistema de pedidos está deshabilitado."
MENSAJE_PEDIDOS_CERRADOS = "Los pedidos están cerrados en este momento."
MENSAJE_LOGIN_CARRITO = "Debes iniciar sesion para agregar productos al carrito"
MENSAJE_TURNOS_CERRADOS = "Los turnos están disponibles durante los horarios de descanso."

# Deja None para usar la hora real. Para probar, escribe por ejemplo time(8, 40) o time(10, 0).
HORA_PRUEBA = None


def a_minutos(hora):
    """Convierte una hora a minutos para compararla más fácil."""
    return hora.hour * 60 + hora.minute


def obtener_hora_actual():
    if HORA_PRUEBA is not None:
        return HORA_PRUEBA
    return datetime.now().time()


def hora_en_texto(hora):
    """Pasa una hora de Python a un texto como 9:10 AM."""
    horas = hora.hour
    minutos = hora.minute
    sufijo = "AM"
    if horas >= 12:
        sufijo = "PM"
    horas_12 = horas % 12
    if horas_12 == 0:
        horas_12 = 12
    return f"{horas_12}:{minutos:02d} {sufijo}"


def texto_a_hora(texto):
    """Lee una hora enviada por el formulario (HH:MM)."""
    try:
        partes = texto.strip().split(":")
        return time(int(partes[0]), int(partes[1]))
    except (ValueError, IndexError, AttributeError):
        return None


def jornada_siguiente(jornada):
    indice = HORARIOS_DESCANSO.index(jornada)
    if indice + 1 < len(HORARIOS_DESCANSO):
        return HORARIOS_DESCANSO[indice + 1]
    return None


def buscar_jornada(nombre):
    for jornada in HORARIOS_DESCANSO:
        if jornada["nombre"] == nombre:
            return jornada
    return None


def limpiar_extension_vencida(minutos_actuales):
    """Si ya pasó la hora de extensión, se cancela sola."""
    global extension_hasta, extension_jornada
    if extension_hasta is None:
            return
    if minutos_actuales > a_minutos(extension_hasta):
        extension_hasta = None
        extension_jornada = None


def extension_sigue_vigente(jornada, minutos_actuales):
    if extension_hasta is None or extension_jornada != jornada["nombre"]:
        return False
    inicio = a_minutos(jornada["inicio"])
    extra = a_minutos(extension_hasta)
    if not (inicio <= minutos_actuales <= extra):
        return False
    siguiente = jornada_siguiente(jornada)
    if siguiente and minutos_actuales >= a_minutos(siguiente["inicio"]):
        return False
    return True


def estado_descanso():
    """Revisa el horario normal y, si existe, la extensión del descanso."""
    hora = obtener_hora_actual()
    minutos_actuales = a_minutos(hora)
    limpiar_extension_vencida(minutos_actuales)

    for jornada in HORARIOS_DESCANSO:
        inicio = a_minutos(jornada["inicio"])
        fin = a_minutos(jornada["fin"])
        if inicio <= minutos_actuales <= fin:
            return armar_estado(jornada, True, False)

    for jornada in HORARIOS_DESCANSO:
        if extension_sigue_vigente(jornada, minutos_actuales):
            return armar_estado(jornada, True, True)

    return {
        "activo": False,
        "jornada": "",
        "jornada_corta": "",
        "horario_texto": "",
        "cierre_normal": "",
        "por_extension": False,
        "puede_extender": False,
    }


def armar_estado(jornada, activo, por_extension):
    horario = jornada["texto"]
    if por_extension and extension_hasta is not None:
        horario = jornada["texto"] + " (extendido hasta " + hora_en_texto(extension_hasta) + ")"
    return {
        "activo": activo,
        "jornada": jornada["nombre"],
        "jornada_corta": jornada["corto"],
        "horario_texto": horario,
        "cierre_normal": hora_en_texto(jornada["fin"]),
        "por_extension": por_extension,
        "puede_extender": activo,
    }


def sistema_pedidos_activo():
    """Activo solo si hay horario de descanso (o extensión) y habilitación manual."""
    horario_activo = estado_descanso()["activo"]
    if sistema_habilitado and horario_activo:
        return True
    return False


def datos_carrito_flotante():
    """Datos para mostrar el carrito flotante solo si ya hay productos."""
    cantidad = 0
    for item in obtener_carrito():
        cantidad = cantidad + item.get("cantidad", 0)
    return {
        "carrito_tiene_productos": cantidad > 0 and rol_actual() == "cliente",
        "carrito_cantidad": cantidad,
    }


def volver_al_panel():
    origen = request.form.get("origen", "")
    if origen == "vendedor":
        return redirect("/vendedor.html")
    return redirect("/administrador.html")


def datos_pagina_admin(aviso=""):
    """Datos para la sección de horario del administrador."""
    estado = estado_descanso()
    hora_guardada = ""
    texto_extension = ""
    if extension_hasta is not None:
        hora_guardada = f"{extension_hasta.hour:02d}:{extension_hasta.minute:02d}"
        texto_extension = hora_en_texto(extension_hasta)
    return {
        "horario_activo": estado["activo"],
        "sistema_activo": sistema_habilitado,
        "sistema_habilitado": sistema_habilitado,
        "jornada_corta": estado["jornada_corta"] or "Ninguno",
        "cierre_normal": estado["cierre_normal"] or "—",
        "puede_extender": estado["puede_extender"],
        "por_extension": estado["por_extension"],
        "hora_extension_valor": hora_guardada,
        "extension_texto": texto_extension,
        "aviso_horario": aviso,
        "sesion_iniciada": usuario_logueado(),
        "rol": rol_actual(),
        "pagina_actual": pagina_menu(),
    }


def descanso_en_curso():
    """Devuelve la jornada que está ocurriendo ahora, o None."""
    estado = estado_descanso()
    if not estado["activo"]:
        return None
    return buscar_jornada(estado["jornada"])


def usuario_logueado():
    """Sesión sencilla. Más adelante vendrá de MySQL."""
    return bool(session.get("sesion_iniciada"))


def rol_actual():
    return session.get("rol", "")


def pagina_menu():
    ruta = request.path.strip("/")
    if ruta in ("", "index.html"):
        return "inicio"
    return ruta.replace(".html", "")


def datos_sesion():
    return {
        "sesion_iniciada": usuario_logueado(),
        "rol": rol_actual(),
        "pagina_actual": pagina_menu(),
        "turno_actual": turno_actual,
        "sistema_habilitado": sistema_habilitado,
    }


def iniciar_sesion_rol(rol, nombre=""):
    session["sesion_iniciada"] = True
    session["rol"] = rol
    if nombre:
        session["nombre_usuario"] = nombre
    else:
        session["nombre_usuario"] = rol


def redirigir_si_no_autorizado(pagina):
    """Impide que un visitante entre a páginas de un rol escribiendo la dirección."""
    rol = rol_actual()
    if pagina in ("index", "catalogo", "login", "registro"):
        return None
    if pagina in ("carrito", "pago", "turno", "pqr", "encuesta", "gracias", "pqr-gracias"):
        if rol != "cliente":
            return redirect("/login.html")
        return None
    if pagina == "vendedor":
        if rol != "vendedor":
            return redirect("/login.html")
        return None
    if pagina == "administrador" or pagina.startswith("admin-"):
        if rol not in ("administrador", "superadmin"):
            return redirect("/login.html")
        return None
    if pagina.startswith("superadmin"):
        if rol != "superadmin":
            return redirect("/login.html")
        return None
    return None


def datos_pagina_cliente():
    """Datos que se envían a las páginas de pedido y turnos."""
    estado = estado_descanso()
    horario_activo = estado["activo"]
    if not sistema_habilitado:
        mensaje_cerrado = MENSAJE_DESHABILITADO
    else:
        mensaje_cerrado = MENSAJE_CERRADO
    datos = {
        "turno_actual": turno_actual,
        "horario_activo": horario_activo,
        "sistema_habilitado": sistema_habilitado,
        "sistema_activo": sistema_habilitado,
        "sistema_pedidos_activo": sistema_pedidos_activo(),
        "sesion_iniciada": usuario_logueado(),
        "rol": rol_actual(),
        "jornada_activa": estado["jornada"],
        "horario_texto": estado["horario_texto"],
        "mensaje_cerrado": mensaje_cerrado,
        "mensaje_turnos_cerrados": MENSAJE_TURNOS_CERRADOS,
        "hay_turno": session.get("ultimo_pedido") is not None,
        "pagina_actual": pagina_menu(),
    }
    datos.update(datos_carrito_flotante())
    return datos


# Mensajes de confirmación del formulario PQR. Todavía no se guardan en MySQL.
TIPOS_PQR = ("peticion", "queja", "reclamo", "felicitacion")
MENSAJES_PQR = {
    "peticion": "Tu petición ha sido enviada, la tomaremos en cuenta. Gracias.",
    "queja": "Tu queja ha sido enviada. La tendremos en cuenta para mejorar nuestro servicio. Gracias.",
    "reclamo": "Tu reclamo ha sido enviado. Revisaremos la situación y trabajaremos para mejorar. Gracias.",
    "felicitacion": "Tu felicitación ha sido recibida. Gracias por compartir tu opinión.",
}


def validar_pqr(tipo, nombre, mensaje):
    if tipo not in TIPOS_PQR:
        return "Por favor selecciona un tipo de PQR."
    if not (nombre or "").strip():
        return "Por favor escribe tu nombre."
    if not (mensaje or "").strip():
        return "Por favor escribe el mensaje."
    return ""


def datos_formulario_pqr(error="", tipo="", nombre="", mensaje=""):
    datos = datos_pagina_cliente()
    datos.update({
        "error": error,
        "tipo": tipo,
        "nombre": nombre,
        "mensaje_pqr": mensaje,
    })
    return datos


def mostrar_html(nombre_archivo):
    return render_template(nombre_archivo, **datos_pagina_cliente())


def mostrar_con_turno(nombre_archivo, extra=None):
    """Muestra una página HTML con el turno y el estado del horario."""
    datos = datos_pagina_cliente()
    if extra:
        datos.update(extra)
    return render_template(nombre_archivo, **datos)


@app.route("/")
@app.route("/index.html")
def inicio():
    return mostrar_html("index.html")


@app.route("/registro.html")
def registro():
    return mostrar_html("registro.html")


@app.route("/login.html", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nombre = request.form.get("usuario", "").strip()
        if not nombre:
            nombre = "Cliente"
        iniciar_sesion_rol("cliente", nombre)
        return redirect("/catalogo.html")
    return mostrar_html("login.html")


@app.route("/entrar-rol", methods=["POST"])
def entrar_rol():
    rol = request.form.get("rol", "")
    destinos = {
        "cliente": "/catalogo.html",
        "vendedor": "/vendedor.html",
        "administrador": "/administrador.html",
        "superadmin": "/superadmin.html",
    }
    if rol not in destinos:
        return redirect("/login.html")
    iniciar_sesion_rol(rol)
    return redirect(destinos[rol])


@app.route("/cerrar-sesion")
def cerrar_sesion():
    session.pop("sesion_iniciada", None)
    session.pop("nombre_usuario", None)
    session.pop("rol", None)
    return redirect("/index.html")


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
        aviso=request.args.get("aviso", ""),
        **datos_pagina_cliente(),
    )


@app.route("/agregar-al-carrito", methods=["POST"])
def agregar_al_carrito():
    if rol_actual() != "cliente":
        return redirect("/catalogo.html?aviso=" + quote(MENSAJE_LOGIN_CARRITO))
    if not sistema_pedidos_activo():
        return redirect("/catalogo.html?aviso=" + quote(MENSAJE_PEDIDOS_CERRADOS))
    try:
        producto_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect("/catalogo.html?aviso=" + quote("No se encontró el producto."))
    producto = buscar_producto(producto_id)
    if producto is None:
        return redirect("/catalogo.html?aviso=" + quote("No se encontró el producto."))
    if producto["cantidad"] <= 0:
        return redirect("/catalogo.html?aviso=" + quote("Este producto está agotado."))
    items = obtener_carrito()
    actual = 0
    linea = None
    for item in items:
        if item["id"] == producto_id:
            linea = item
            actual = item["cantidad"]
    nueva = actual + 1
    if nueva > producto["cantidad"]:
        return redirect("/catalogo.html?aviso=" + quote("Solo hay " + str(producto["cantidad"]) + " unidades disponibles."))
    if linea is None:
        items.append({"id": producto_id, "cantidad": 1})
    else:
        linea["cantidad"] = nueva
    guardar_carrito(items)
    return redirect(url_catalogo("Producto agregado al carrito."))


@app.route("/carrito.html")
def carrito():
    bloqueo = redirigir_si_no_autorizado("carrito")
    if bloqueo:
        return bloqueo
    session["paso_carrito"] = True
    session.modified = True
    lineas, total = armar_lineas_carrito()
    return mostrar_con_turno("carrito.html", {
        "items": lineas,
        "total_texto": precio_en_texto(total),
        "aviso": request.args.get("aviso", ""),
        "carrito_vacio": len(lineas) == 0,
    })


@app.route("/actualizar-carrito", methods=["POST"])
def actualizar_carrito():
    bloqueo = redirigir_si_no_autorizado("carrito")
    if bloqueo:
        return bloqueo
    if not sistema_pedidos_activo():
        return redirect("/carrito.html?aviso=" + quote(MENSAJE_PEDIDOS_CERRADOS))
    try:
        producto_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect("/carrito.html?aviso=" + quote("Ingresa una cantidad válida."))
    items = obtener_carrito()
    actual = 0
    linea = None
    for item in items:
        if item["id"] == producto_id:
            linea = item
            actual = item["cantidad"]
    if linea is None:
        return redirect("/carrito.html?aviso=" + quote("No se encontró el producto."))
    cambio = request.form.get("cambio", "")
    if cambio == "mas":
        cantidad = actual + 1
    elif cambio == "menos":
        cantidad = actual - 1
    else:
        try:
            cantidad = int(request.form.get("cantidad", ""))
        except ValueError:
            return redirect("/carrito.html?aviso=" + quote("Ingresa una cantidad válida."))
    if cantidad < 1:
        return redirect("/carrito.html?aviso=" + quote("La cantidad mínima es 1."))
    producto = buscar_producto(producto_id)
    if producto is None:
        return redirect("/carrito.html?aviso=" + quote("No se encontró el producto."))
    if cantidad > producto["cantidad"]:
        return redirect("/carrito.html?aviso=" + quote("Solo hay " + str(producto["cantidad"]) + " unidades disponibles."))
    linea["cantidad"] = cantidad
    guardar_carrito(items)
    return redirect("/carrito.html")


@app.route("/quitar-del-carrito", methods=["POST"])
def quitar_del_carrito():
    bloqueo = redirigir_si_no_autorizado("carrito")
    if bloqueo:
        return bloqueo
    if not sistema_pedidos_activo():
        return redirect("/carrito.html?aviso=" + quote(MENSAJE_PEDIDOS_CERRADOS))
    try:
        producto_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect("/carrito.html?aviso=" + quote("No se encontró el producto."))
    items = []
    for item in obtener_carrito():
        if item["id"] != producto_id:
            items.append(item)
    guardar_carrito(items)
    return redirect("/carrito.html?aviso=" + quote("El producto se quitó del carrito."))


@app.route("/pago.html")
def pago():
    bloqueo = redirigir_si_no_autorizado("pago")
    if bloqueo:
        return bloqueo
    if not session.get("paso_carrito"):
        return redirect("/carrito.html")
    lineas, total = armar_lineas_carrito()
    if not lineas:
        return redirect("/carrito.html")
    if not sistema_pedidos_activo():
        return redirect("/carrito.html?aviso=" + quote(MENSAJE_PEDIDOS_CERRADOS))
    return mostrar_con_turno("pago.html", {
        "items": lineas,
        "total_texto": precio_en_texto(total),
        "aviso": request.args.get("aviso", ""),
        "carrito_vacio": len(lineas) == 0,
    })


@app.route("/confirmar-pago", methods=["POST"])
def confirmar_pago():
    bloqueo = redirigir_si_no_autorizado("pago")
    if bloqueo:
        return bloqueo
    if not session.get("paso_carrito"):
        return redirect("/carrito.html")
    items = obtener_carrito()
    if not items:
        return redirect("/carrito.html?aviso=" + quote("El carrito está vacío."))
    if not sistema_pedidos_activo():
        return redirect("/carrito.html?aviso=" + quote(MENSAJE_PEDIDOS_CERRADOS))
    for item in items:
        producto = buscar_producto(item["id"])
        if producto is None:
            return redirect("/pago.html?aviso=" + quote("Un producto del carrito ya no está disponible."))
        if item["cantidad"] < 1:
            return redirect("/pago.html?aviso=" + quote("Ingresa una cantidad válida."))
        if producto["cantidad"] < item["cantidad"]:
            if producto["cantidad"] == 0:
                mensaje = producto["nombre"] + " está agotado."
            else:
                mensaje = "Solo hay " + str(producto["cantidad"]) + " unidades disponibles."
            return redirect("/pago.html?aviso=" + quote(mensaje))
    lineas, total = armar_lineas_carrito()
    for item in items:
        descontar_inventario(item["id"], item["cantidad"])
    turno_cliente = asignar_turno_cliente()
    pedido = registrar_pedido(turno_cliente, lineas, total)
    session["ultimo_pedido"] = pedido
    session.modified = True
    vaciar_carrito()
    return redirect("/turno.html")


@app.route("/turno.html")
def turno():
    bloqueo = redirigir_si_no_autorizado("turno")
    if bloqueo:
        return bloqueo
    ultimo = session.get("ultimo_pedido")
    if not ultimo:
        return redirect("/catalogo.html?aviso=" + quote("Debes completar el pago para consultar tu turno."))
    return mostrar_con_turno("turno.html", {
        "ultimo_pedido": ultimo,
    })


@app.route("/vendedor.html")
def vendedor():
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    aviso = request.args.get("turno", "")
    pendientes, entregados = pedidos_para_vendedor()
    return mostrar_con_turno(
        "vendedor.html",
        {
            "aviso_turno_cerrado": aviso == "cerrado",
            "aviso_sin_turnos": aviso == "sin-turnos",
            "aviso_pedido": request.args.get("aviso", ""),
            "pedidos_pendientes": pendientes,
            "pedidos_entregados": entregados,
            "hay_pedidos": len(PEDIDOS) > 0,
        },
    )


@app.route("/cambiar-estado-pedido", methods=["POST"])
def cambiar_estado_pedido():
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    try:
        pedido_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect("/vendedor.html?aviso=" + quote("No se encontró el pedido."))
    pedido = buscar_pedido(pedido_id)
    if pedido is None:
        return redirect("/vendedor.html?aviso=" + quote("No se encontró el pedido."))
    nuevo = request.form.get("estado", "")
    esperado = SIGUIENTE_ESTADO.get(pedido["estado"])
    if esperado is None or nuevo != esperado:
        return redirect("/vendedor.html?aviso=" + quote("El estado solicitado no es válido."))
    pedido["estado"] = nuevo
    return redirect("/vendedor.html")


@app.route("/siguiente-turno", methods=["GET", "POST"])
def siguiente_turno():
    """Avanza el turno actual solo si el sistema está realmente activo."""
    global turno_actual
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    if not sistema_pedidos_activo():
        return redirect("/vendedor.html?turno=cerrado")
    if turno_actual >= ultimo_turno_asignado:
        return redirect("/vendedor.html?turno=sin-turnos")
    turno_actual = turno_actual + 1
    return redirect("/vendedor.html")


@app.route("/administrador.html")
def administrador():
    bloqueo = redirigir_si_no_autorizado("administrador")
    if bloqueo:
        return bloqueo
    aviso = request.args.get("horario", "")
    return render_template("administrador.html", **datos_pagina_admin(aviso))


@app.route("/extender-horario", methods=["POST"])
def extender_horario():
    """Guarda una hora extra solo si hay un descanso en curso."""
    bloqueo = redirigir_si_no_autorizado("administrador")
    if bloqueo:
        return bloqueo
    global extension_hasta, extension_jornada
    jornada = descanso_en_curso()
    if jornada is None:
        return redirect("/administrador.html?horario=no-activo")
    nueva = texto_a_hora(request.form.get("hora_extension", ""))
    if nueva is None:
        return redirect("/administrador.html?horario=invalida")
    minutos_nueva = a_minutos(nueva)
    minutos_ahora = a_minutos(obtener_hora_actual())
    if minutos_nueva <= minutos_ahora:
        return redirect("/administrador.html?horario=invalida")
    if minutos_nueva <= a_minutos(jornada["fin"]):
        return redirect("/administrador.html?horario=invalida")
    siguiente = jornada_siguiente(jornada)
    if siguiente and minutos_nueva >= a_minutos(siguiente["inicio"]):
        return redirect("/administrador.html?horario=invalida")
    extension_hasta = nueva
    extension_jornada = jornada["nombre"]
    return redirect("/administrador.html?horario=ok")


@app.route("/cancelar-extension", methods=["POST"])
def cancelar_extension():
    bloqueo = redirigir_si_no_autorizado("administrador")
    if bloqueo:
        return bloqueo
    global extension_hasta, extension_jornada
    extension_hasta = None
    extension_jornada = None
    return redirect("/administrador.html?horario=cancelada")


@app.route("/admin-productos.html")
def admin_productos():
    bloqueo = redirigir_si_no_autorizado("admin-productos")
    if bloqueo:
        return bloqueo
    aviso = request.args.get("aviso", "")
    editar_id = request.args.get("editar", "")
    producto_editar = None
    if editar_id:
        try:
            producto_editar = buscar_producto(int(editar_id))
        except ValueError:
            producto_editar = None
    return render_template(
        "admin-productos.html",
        productos=[preparar(p) for p in PRODUCTOS],
        categorias_form=categorias_producto(),
        imagenes=imagenes_disponibles(),
        producto_editar=producto_editar,
        aviso=aviso,
        **datos_sesion(),
    )


@app.route("/agregar-producto", methods=["POST"])
def agregar_producto():
    nombre = request.form.get("nombre", "")
    categoria = request.form.get("categoria", "")
    precio_texto = request.form.get("precio", "")
    cantidad_texto = request.form.get("cantidad", "")
    imagen = request.form.get("imagen", "")
    error = validar_producto(nombre, categoria, precio_texto, cantidad_texto)
    if error:
        return redirect("/admin-productos.html?aviso=" + quote(error))
    if imagen not in imagenes_disponibles():
        imagen = "empanada.svg"
    PRODUCTOS.append({
        "id": siguiente_id(),
        "nombre": nombre.strip(),
        "precio": int(precio_texto),
        "cantidad": int(cantidad_texto),
        "categoria": categoria,
        "imagen": imagen,
        "destacado": False,
        "busqueda": sin_tildes(nombre.strip()),
    })
    return redirect("/admin-productos.html?aviso=" + quote("El producto fue agregado."))


@app.route("/editar-producto", methods=["POST"])
def editar_producto():
    try:
        producto_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect("/admin-productos.html?aviso=" + quote("No se encontró el producto."))
    producto = buscar_producto(producto_id)
    if producto is None:
        return redirect("/admin-productos.html?aviso=" + quote("No se encontró el producto."))
    nombre = request.form.get("nombre", "")
    categoria = request.form.get("categoria", "")
    precio_texto = request.form.get("precio", "")
    cantidad_texto = request.form.get("cantidad", "")
    imagen = request.form.get("imagen", "")
    error = validar_producto(nombre, categoria, precio_texto, cantidad_texto)
    if error:
        return redirect("/admin-productos.html?editar=" + str(producto_id) + "&aviso=" + quote(error))
    if imagen not in imagenes_disponibles():
        imagen = producto["imagen"]
    producto["nombre"] = nombre.strip()
    producto["categoria"] = categoria
    producto["precio"] = int(precio_texto)
    producto["cantidad"] = int(cantidad_texto)
    producto["imagen"] = imagen
    producto["busqueda"] = sin_tildes(nombre.strip())
    return redirect("/admin-productos.html?aviso=" + quote("El producto fue actualizado."))


@app.route("/admin-eliminar.html")
def admin_eliminar():
    bloqueo = redirigir_si_no_autorizado("admin-eliminar")
    if bloqueo:
        return bloqueo
    try:
        producto = buscar_producto(int(request.args.get("id", "0")))
    except ValueError:
        producto = None
    if producto is None:
        return redirect("/admin-productos.html?aviso=" + quote("No se encontró el producto."))
    return render_template("admin-eliminar.html", producto=preparar(producto), **datos_sesion())


@app.route("/eliminar-producto", methods=["POST"])
def eliminar_producto():
    try:
        producto_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect("/admin-productos.html?aviso=" + quote("No se encontró el producto."))
    producto = buscar_producto(producto_id)
    if producto is None:
        return redirect("/admin-productos.html?aviso=" + quote("No se encontró el producto."))
    PRODUCTOS.remove(producto)
    return redirect("/admin-productos.html?aviso=" + quote("El producto fue eliminado."))


@app.route("/admin-inventarios.html")
def admin_inventarios():
    bloqueo = redirigir_si_no_autorizado("admin-inventarios")
    if bloqueo:
        return bloqueo
    return render_template(
        "admin-inventarios.html",
        productos=[preparar(p) for p in PRODUCTOS],
        **datos_sesion(),
    )


@app.route("/encuesta.html")
def encuesta():
    bloqueo = redirigir_si_no_autorizado("encuesta")
    if bloqueo:
        return bloqueo
    return mostrar_html("encuesta.html")


@app.route("/gracias.html", methods=["GET", "POST"])
def gracias():
    bloqueo = redirigir_si_no_autorizado("gracias")
    if bloqueo:
        return bloqueo
    return mostrar_html("gracias.html")


@app.route("/pqr.html")
def pqr():
    bloqueo = redirigir_si_no_autorizado("pqr")
    if bloqueo:
        return bloqueo
    return render_template("pqr.html", **datos_formulario_pqr())


@app.route("/pqr-gracias.html", methods=["GET", "POST"])
def pqr_gracias():
    if request.method != "POST":
        return redirect("/pqr.html")
    tipo = request.form.get("tipo", "")
    nombre = request.form.get("nombre", "")
    mensaje = request.form.get("mensaje", "")
    error = validar_pqr(tipo, nombre, mensaje)
    if error:
        return render_template(
            "pqr.html",
            **datos_formulario_pqr(error, tipo, nombre.strip(), mensaje),
        )
    return render_template("pqr-gracias.html", mensaje=MENSAJES_PQR[tipo], **datos_pagina_cliente())


@app.route("/habilitar-sistema", methods=["POST"])
def habilitar_sistema():
    global sistema_habilitado
    if rol_actual() not in ("vendedor", "administrador", "superadmin"):
        return redirect("/login.html")
    sistema_habilitado = True
    return volver_al_panel()


@app.route("/deshabilitar-sistema", methods=["POST"])
def deshabilitar_sistema():
    global sistema_habilitado
    if rol_actual() not in ("vendedor", "administrador", "superadmin"):
        return redirect("/login.html")
    sistema_habilitado = False
    return volver_al_panel()


@app.route("/css/<path:archivo>")
def css(archivo):
    return send_from_directory(CARPETA_CSS, archivo)


@app.route("/img/<path:archivo>")
def imagenes(archivo):
    return send_from_directory(CARPETA_IMG, archivo)


@app.route("/<nombre>.html")
def otras_paginas(nombre):
    bloqueo = redirigir_si_no_autorizado(nombre)
    if bloqueo:
        return bloqueo
    if nombre == "catalogo":
        return catalogo()
    if nombre == "pqr":
        return pqr()
    if nombre == "pqr-gracias":
        return pqr_gracias()
    if nombre == "carrito":
        return carrito()
    if nombre == "pago":
        return pago()
    if nombre == "turno":
        return turno()
    if nombre == "vendedor":
        return vendedor()
    if nombre == "administrador":
        return administrador()
    if nombre == "admin-productos":
        return admin_productos()
    if nombre == "admin-inventarios":
        return admin_inventarios()
    if nombre == "admin-eliminar":
        return admin_eliminar()
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
    direccion = f"http://localhost:{puerto}/index.html"
    print("=" * 50)
    print("  CAFETIX JOACO")
    print("=" * 50)
    print(f"  Abre: {direccion}")
    print("  Presiona Ctrl+C para detener")
    print("=" * 50)
    Timer(1, lambda: webbrowser.open(direccion)).start()
    app.run(host="127.0.0.1", port=puerto, debug=True, use_reloader=False)
