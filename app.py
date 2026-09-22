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

MySQL (XAMPP): conexión básica disponible.
Categorías y productos se cargan desde MySQL al iniciar.
"""

from datetime import datetime, time
from pathlib import Path
from urllib.parse import quote
import secrets
import webbrowser
from threading import Timer

import mysql.connector
from flask import Flask, render_template, request, send_from_directory, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash

CARPETA = Path(__file__).resolve().parent
CARPETA_HTML = CARPETA / "html"
CARPETA_CSS = CARPETA / "css"
CARPETA_IMG = CARPETA / "img"

app = Flask(__name__, template_folder=str(CARPETA_HTML))
app.secret_key = "cafetix-joaco-estudiante"


def obtener_conexion():
    """Abre una conexión sencilla a MySQL/MariaDB (XAMPP local)."""
    return mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="",
        database="cafetix_joaco",
    )


def probar_conexion_mysql():
    """Prueba SELECT de solo lectura. No modifica datos ni el flujo del sitio."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM tbl_productos")
        cantidad = cursor.fetchone()[0]
        print("Conexión MySQL correcta")
        print("Productos encontrados:", cantidad)
        return True
    except mysql.connector.Error as error:
        print("No se pudo conectar a MySQL.")
        print("Revisa que XAMPP tenga MySQL iniciado y que exista la base cafetix_joaco.")
        print("Detalle:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def sin_tildes(texto):
    texto = texto.lower()
    for original, nuevo in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        texto = texto.replace(original, nuevo)
    return texto


# Filtros públicos del catálogo (desayunos/almuerzos quedan en MySQL pero no se muestran).
CATEGORIAS_FILTRO_PUBLICO = ("bebidas", "comidas", "mecato", "recien-preparadas")


def cargar_categorias_desde_bd():
    """Lee tbl_categorias y agrega el filtro 'todos' solo en Python.

    Solo incluye los filtros públicos del catálogo.
    Devuelve None si MySQL falla (para no vaciar la caché en recargas).
    """
    lista = [{"id": "todos", "nombre": "Todos"}]
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT Cat_Codigo, Cat_Nombre_Categoria
            FROM tbl_categorias
            WHERE Cat_Estado = 'Activo'
            ORDER BY Cat_Id_Categoria ASC
            """
        )
        for fila in cursor.fetchall():
            codigo = fila["Cat_Codigo"]
            if codigo not in CATEGORIAS_FILTRO_PUBLICO:
                continue
            lista.append({
                "id": codigo,
                "nombre": fila["Cat_Nombre_Categoria"],
            })
        print("Categorías cargadas desde MySQL:", len(lista) - 1)
        return lista
    except mysql.connector.Error as error:
        print("No fue posible cargar categorías desde MySQL. Verifique XAMPP/MySQL.")
        print("Detalle:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def cargar_productos_desde_bd():
    """Lee tbl_productos y las convierte a la estructura que usa Flask.

    Devuelve None si MySQL falla (para no vaciar la caché en recargas).
    """
    lista = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                p.Prod_Id_Producto,
                p.Prod_cod_producto,
                p.Prod_Nombre_Producto,
                p.Prod_Precio,
                p.Prod_Cant_est,
                p.Prod_Imagen,
                p.Prod_Destacado,
                p.Prod_Disponible,
                c.Cat_Codigo,
                c.Cat_Nombre_Categoria
            FROM tbl_productos AS p
            INNER JOIN tbl_categorias AS c
                ON p.Prod_Id_Categoria = c.Cat_Id_Categoria
            WHERE p.Prod_Disponible IS NULL
               OR p.Prod_Disponible <> 'No disponible'
            ORDER BY p.Prod_Id_Producto ASC
            """
        )
        for fila in cursor.fetchall():
            nombre = fila["Prod_Nombre_Producto"]
            categoria = fila["Cat_Codigo"]
            precio = int(fila["Prod_Precio"])
            cantidad = int(fila["Prod_Cant_est"] or 0)
            imagen = (fila["Prod_Imagen"] or "").strip() or "empanada.svg"
            destacado = int(fila["Prod_Destacado"] or 0) == 1
            lista.append({
                "id": int(fila["Prod_Id_Producto"]),
                "codigo": fila["Prod_cod_producto"] or "",
                "nombre": nombre,
                "precio": precio,
                "cantidad": cantidad,
                "categoria": categoria,
                "nombre_categoria": fila["Cat_Nombre_Categoria"] or categoria,
                "imagen": imagen,
                "destacado": destacado,
                "disponible_admin": fila["Prod_Disponible"] or "",
                "busqueda": sin_tildes(
                    nombre + " " + categoria + " " + (fila["Cat_Nombre_Categoria"] or "")
                ),
            })
        print("Productos cargados desde MySQL:", len(lista))
        return lista
    except mysql.connector.Error as error:
        print("No fue posible cargar productos desde MySQL. Verifique XAMPP/MySQL.")
        print("Detalle:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


# Categorías y productos se cargan desde MySQL (misma estructura que antes).
_categorias_inicio = cargar_categorias_desde_bd()
CATEGORIAS = _categorias_inicio if _categorias_inicio is not None else [
    {"id": "todos", "nombre": "Todos"}
]
_productos_inicio = cargar_productos_desde_bd()
PRODUCTOS = _productos_inicio if _productos_inicio is not None else []


def recargar_categorias():
    """Sincroniza CATEGORIAS con tbl_categorias (mantiene 'todos' virtual)."""
    nuevas = cargar_categorias_desde_bd()
    if nuevas is None:
        print("Se mantienen las categorías en caché (falló la lectura de MySQL).")
        return False
    CATEGORIAS.clear()
    CATEGORIAS.extend(nuevas)
    return True


def recargar_productos():
    """Sincroniza PRODUCTOS (y categorías) con MySQL.

    Si MySQL falla, no vacía la caché: evita un catálogo vacío por un fallo puntual.
    """
    if not recargar_categorias():
        print("Se mantienen los productos en caché (falló la lectura de categorías).")
        return False
    nuevos = cargar_productos_desde_bd()
    if nuevos is None:
        print("Se mantienen los productos en caché (falló la lectura de MySQL).")
        return False
    PRODUCTOS.clear()
    PRODUCTOS.extend(nuevos)
    return True


def obtener_id_categoria(codigo):
    """Convierte Cat_Codigo (ej. bebidas) a Cat_Id_Categoria."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT Cat_Id_Categoria FROM tbl_categorias WHERE Cat_Codigo = %s",
            (codigo,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return int(fila[0])
    except mysql.connector.Error as error:
        print("Error al buscar categoría:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def generar_codigo_producto():
    """Genera un código único tipo CAF-001 a partir de los CAF-### existentes."""
    conexion = None
    cursor = None
    mayor = 0
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT Prod_cod_producto FROM tbl_productos")
        for (codigo,) in cursor.fetchall():
            texto = (codigo or "").strip().upper()
            if texto.startswith("CAF-") and texto[4:].isdigit():
                numero = int(texto[4:])
                if numero > mayor:
                    mayor = numero
    except mysql.connector.Error as error:
        print("Error al generar código de producto:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return "CAF-" + str(mayor + 1).zfill(3)


def texto_disponibilidad(cantidad):
    if cantidad > 0:
        return "Disponible"
    return "Agotado"


def precio_en_texto(valor):
    return "$" + f"{int(valor):,}".replace(",", ".")


def preparar(producto):
    """Prepara el producto para mostrarlo en el HTML."""
    copia = dict(producto)
    copia["precio_texto"] = precio_en_texto(producto["precio"])
    copia["disponible"] = producto["cantidad"] > 0
    copia["estado"] = "Disponible" if producto["cantidad"] > 0 else "Agotado"
    if producto.get("nombre_categoria"):
        copia["categoria_nombre"] = producto["nombre_categoria"]
    else:
        nombre_cat = producto["categoria"]
        for item in CATEGORIAS:
            if item["id"] == producto["categoria"]:
                nombre_cat = item["nombre"]
        copia["categoria_nombre"] = nombre_cat
    if not (copia.get("imagen") or "").strip():
        copia["imagen"] = "empanada.svg"
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


def _actualizar_stock_en_cursor(cursor, items):
    """Aplica los descuentos de stock usando un cursor abierto. Sin commit."""
    for item in items:
        producto_id = int(item["id"])
        cantidad = int(item["cantidad"])
        if cantidad < 1:
            return False
        cursor.execute(
            """
            UPDATE tbl_productos
            SET Prod_Cant_est = Prod_Cant_est - %s,
                Prod_Valor_Tot = Prod_Precio * (Prod_Cant_est - %s),
                Prod_Disponible = CASE
                    WHEN (Prod_Cant_est - %s) > 0 THEN 'Disponible'
                    ELSE 'Agotado'
                END
            WHERE Prod_Id_Producto = %s
              AND Prod_Cant_est >= %s
              AND (Prod_Disponible IS NULL OR Prod_Disponible <> 'No disponible')
            """,
            (cantidad, cantidad, cantidad, producto_id, cantidad),
        )
        if cursor.rowcount != 1:
            return False
    return True


def descontar_inventario_compra(items):
    """
    Descuenta el stock de todos los ítems del carrito en una sola transacción.
    Si alguno falla, hace ROLLBACK y no deja descuentos parciales.
    """
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        if not _actualizar_stock_en_cursor(cursor, items):
            conexion.rollback()
            return False
        conexion.commit()
        recargar_productos()
        return True
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al descontar inventario:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def descontar_inventario(producto_id, cantidad_comprada):
    """Descuenta stock persistido en MySQL (un producto)."""
    return descontar_inventario_compra([{"id": producto_id, "cantidad": cantidad_comprada}])


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


def registrar_pedido(turno_cliente, lineas, total, pedido_id=None, turno_id=None):
    """Guarda el pedido en memoria para el vendedor (IDs reales de MySQL si existen)."""
    global siguiente_numero_pedido
    if pedido_id is None:
        numero = siguiente_numero_pedido
        siguiente_numero_pedido = siguiente_numero_pedido + 1
    else:
        numero = int(pedido_id)
        if numero >= siguiente_numero_pedido:
            siguiente_numero_pedido = numero + 1
    pedido = {
        "id": numero,
        "numero": "CJ-" + str(numero).zfill(3),
        "turno": turno_cliente,
        "turno_id": turno_id,
        "productos": lineas,
        "total": total,
        "total_texto": precio_en_texto(total),
        "estado": "pendiente",
    }
    PEDIDOS.append(pedido)
    return pedido


def confirmar_compra_en_bd(items, lineas, total, usuario_id):
    """
    En una sola transacción:
    - descuenta inventario
    - inserta turno, pedido, detalles y venta con Usu_Id_Usuario real
    Devuelve (pedido_id, turno_id, numero_turno) o None si falla.
    """
    if usuario_id is None:
        return None
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        if not _actualizar_stock_en_cursor(cursor, items):
            conexion.rollback()
            return None

        ahora = datetime.now()
        fecha = ahora.date()
        hora = ahora.time().replace(microsecond=0)

        cursor.execute("SELECT COALESCE(MAX(Tur_Numero_Turno), 0) FROM tbl_turnos")
        max_numero = int(cursor.fetchone()[0] or 0)
        base = max_numero
        if base < turno_actual:
            base = turno_actual
        numero_turno = base + 1

        cursor.execute(
            """
            INSERT INTO tbl_turnos (
                Tur_Id_Usuario, Tur_Numero_Turno, Tur_Fecha,
                Tur_Hora_Solicitud, Tur_Estado_Turno
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (usuario_id, numero_turno, fecha, hora, "Pendiente"),
        )
        turno_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO tbl_pedidos (
                Ped_Id_Usuario, Ped_Id_Turno, Ped_Fecha_Pedido,
                Ped_Estado_Pedido, Ped_Total_Pedido
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (usuario_id, turno_id, fecha, "pendiente", total),
        )
        pedido_id = cursor.lastrowid
        for linea in lineas:
            cursor.execute(
                """
                INSERT INTO tbl_detallepedido (
                    Det_Id_Pedido, Det_Id_Producto, Det_Cantidad,
                    Det_Precio_Unitario, Det_Subtotal
                ) VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    pedido_id,
                    linea["id"],
                    linea["cantidad"],
                    linea["precio"],
                    linea["subtotal"],
                ),
            )
        cursor.execute(
            """
            INSERT INTO tbl_ventas (
                Ven_Id_Pedido, Ven_Fecha_Venta, Ven_Total_Venta,
                Ven_Metodo_Pago, Ven_Estado_Pago, Ven_Id_Usuario
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (pedido_id, fecha, total, "QR", "Confirmado", usuario_id),
        )
        conexion.commit()
        recargar_productos()
        return (int(pedido_id), int(turno_id), int(numero_turno))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al confirmar compra en MySQL:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def actualizar_estado_pedido_bd(pedido_id, nuevo_estado):
    """Persiste Ped_Estado_Pedido en MySQL."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_pedidos
            SET Ped_Estado_Pedido = %s
            WHERE Ped_Id_Pedido = %s
            """,
            (nuevo_estado, pedido_id),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return False
        conexion.commit()
        return True
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al actualizar estado del pedido:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


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
    cargar_pedidos_desde_bd()
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
    cargar_pedidos_desde_bd()
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
    """Aplica búsqueda, categoría y orden sobre PRODUCTOS (caché de MySQL)."""
    lista = list(PRODUCTOS)
    texto = sin_tildes((buscar or "").strip())
    categoria = (categoria or "todos").strip() or "todos"
    orden = (orden or "default").strip() or "default"

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


# Turnos: números visibles (no confundir con Tur_Id_Turno de MySQL).
turno_actual = 1
ultimo_turno_asignado = 1


def sincronizar_contadores_turno_desde_bd():
    """Alinea turno_actual y ultimo_turno_asignado con tbl_turnos."""
    global turno_actual, ultimo_turno_asignado
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT COALESCE(MAX(Tur_Numero_Turno), 0) FROM tbl_turnos")
        max_asignado = int(cursor.fetchone()[0] or 0)
        if max_asignado > 0:
            ultimo_turno_asignado = max_asignado
        else:
            ultimo_turno_asignado = 1
        cursor.execute(
            """
            SELECT COALESCE(MAX(Tur_Numero_Turno), 0)
            FROM tbl_turnos
            WHERE Tur_Estado_Turno = 'Atendido'
            """
        )
        max_atendido = int(cursor.fetchone()[0] or 0)
        if max_atendido > 0:
            turno_actual = max_atendido
        else:
            turno_actual = 1
        print(
            "Turnos sincronizados desde MySQL:",
            "actual=", turno_actual,
            "ultimo_asignado=", ultimo_turno_asignado,
        )
    except mysql.connector.Error as error:
        print("No fue posible sincronizar turnos desde MySQL:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def marcar_turno_atendido(numero_turno):
    """Marca un turno visible como Atendido en MySQL."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_turnos
            SET Tur_Estado_Turno = %s
            WHERE Tur_Numero_Turno = %s
              AND Tur_Estado_Turno = %s
            """,
            ("Atendido", numero_turno, "Pendiente"),
        )
        conexion.commit()
        return True
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al marcar turno atendido:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


sincronizar_contadores_turno_desde_bd()

# Caché en memoria del panel vendedor; se recarga desde MySQL al consultar.
PEDIDOS = []
siguiente_numero_pedido = 1


def cargar_pedidos_desde_bd():
    """Reconstruye PEDIDOS desde MySQL para que el vendedor no pierda datos al reiniciar."""
    global PEDIDOS, siguiente_numero_pedido
    lista = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                p.Ped_Id_Pedido,
                p.Ped_Estado_Pedido,
                p.Ped_Total_Pedido,
                p.Ped_Id_Turno,
                t.Tur_Numero_Turno
            FROM tbl_pedidos AS p
            LEFT JOIN tbl_turnos AS t
                ON p.Ped_Id_Turno = t.Tur_Id_Turno
            ORDER BY p.Ped_Id_Pedido ASC
            """
        )
        filas = cursor.fetchall()
        max_id = 0
        for fila in filas:
            pedido_id = int(fila["Ped_Id_Pedido"])
            if pedido_id > max_id:
                max_id = pedido_id
            cursor.execute(
                """
                SELECT
                    d.Det_Id_Producto,
                    d.Det_Cantidad,
                    d.Det_Precio_Unitario,
                    d.Det_Subtotal,
                    pr.Prod_Nombre_Producto
                FROM tbl_detallepedido AS d
                LEFT JOIN tbl_productos AS pr
                    ON d.Det_Id_Producto = pr.Prod_Id_Producto
                WHERE d.Det_Id_Pedido = %s
                ORDER BY d.Det_Id_Detalle_Pedido ASC
                """,
                (pedido_id,),
            )
            lineas = []
            for det in cursor.fetchall():
                precio = int(det["Det_Precio_Unitario"] or 0)
                subtotal = int(det["Det_Subtotal"] or 0)
                lineas.append(
                    {
                        "id": int(det["Det_Id_Producto"] or 0),
                        "nombre": det["Prod_Nombre_Producto"] or "Producto",
                        "cantidad": int(det["Det_Cantidad"] or 0),
                        "precio": precio,
                        "precio_texto": precio_en_texto(precio),
                        "subtotal": subtotal,
                        "subtotal_texto": precio_en_texto(subtotal),
                    }
                )
            total = int(fila["Ped_Total_Pedido"] or 0)
            numero_turno = int(fila["Tur_Numero_Turno"] or 0)
            lista.append(
                {
                    "id": pedido_id,
                    "numero": "CJ-" + str(pedido_id).zfill(3),
                    "turno": numero_turno,
                    "turno_id": fila["Ped_Id_Turno"],
                    "productos": lineas,
                    "total": total,
                    "total_texto": precio_en_texto(total),
                    "estado": (fila["Ped_Estado_Pedido"] or "pendiente"),
                }
            )
        PEDIDOS = lista
        siguiente_numero_pedido = max_id + 1 if max_id > 0 else 1
    except mysql.connector.Error as error:
        print("No fue posible cargar pedidos desde MySQL:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


cargar_pedidos_desde_bd()

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


def obtener_token_csrf():
    """Token CSRF en session (no se guarda en MySQL ni en logs)."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verificar_token_csrf():
    """Compara el token del formulario con el de session de forma segura."""
    enviado = request.form.get("csrf_token", "")
    esperado = session.get("csrf_token", "")
    if not enviado or not esperado:
        return False
    return secrets.compare_digest(str(enviado), str(esperado))


def usuario_logueado():
    """Sesión autenticada con usuario de MySQL."""
    return bool(session.get("sesion_iniciada") and session.get("usuario_id"))


def rol_actual():
    return session.get("rol", "")


def usuario_id_actual():
    return session.get("usuario_id")


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
        "nombre_usuario": session.get("nombre_usuario", ""),
    }


def obtener_id_rol(nombre_rol):
    """Obtiene Rol_Id_Rol desde tbl_roles por nombre."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT Rol_Id_Rol FROM tbl_roles WHERE Rol_Nombre_Rol = %s",
            (nombre_rol,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return int(fila[0])
    except mysql.connector.Error as error:
        print("Error al buscar rol:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def buscar_usuario_por_login(usuario):
    """Busca usuario y rol en MySQL para autenticación."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.Usu_Id_Usuario,
                u.Usu_Nombre,
                u.Usu_Apellido,
                u.Usu_Usuario,
                u.Usu_Contrasena,
                u.Usu_Estado,
                r.Rol_Nombre_Rol
            FROM tbl_usuarios AS u
            INNER JOIN tbl_roles AS r
                ON u.Usu_Id_Rol = r.Rol_Id_Rol
            WHERE u.Usu_Usuario = %s
            """,
            (usuario,),
        )
        return cursor.fetchone()
    except mysql.connector.Error as error:
        print("Error al buscar usuario:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def existe_nombre_usuario(usuario):
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT Usu_Id_Usuario FROM tbl_usuarios WHERE Usu_Usuario = %s",
            (usuario,),
        )
        return cursor.fetchone() is not None
    except mysql.connector.Error as error:
        print("Error al verificar usuario:", error)
        return True
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def separar_nombre_apellido(nombre_completo):
    texto = (nombre_completo or "").strip()
    if not texto:
        return "", ""
    partes = texto.split(None, 1)
    nombre = partes[0]
    apellido = partes[1] if len(partes) > 1 else "-"
    return nombre[:70], apellido[:70]


def validar_login_entrada(usuario, contrasena):
    """Validación previa al acceso. No revela si el usuario existe."""
    if not usuario:
        return "Escribe tu usuario."
    if len(usuario) > 70:
        return "Usuario o contraseña incorrectos."
    if contrasena is None or contrasena == "":
        return "Escribe tu contraseña."
    return None


def validar_documento_registro(documento):
    """Valida documento del formulario. No se guarda en MySQL todavía."""
    texto = (documento or "").strip()
    if not texto:
        return "Escribe tu documento."
    if not texto.isdigit():
        return "El documento solo debe contener números."
    if len(texto) < 5 or len(texto) > 15:
        return "El documento debe tener entre 5 y 15 dígitos."
    return None


def validar_correo_registro(correo):
    """Valida correo del formulario. No se guarda en MySQL todavía."""
    texto = (correo or "").strip()
    if not texto:
        return "Escribe tu correo electrónico."
    if len(texto) > 100:
        return "El correo es demasiado largo."
    if texto.count("@") != 1:
        return "Escribe un correo electrónico válido."
    local, dominio = texto.split("@")
    if not local or not dominio or "." not in dominio:
        return "Escribe un correo electrónico válido."
    return None


def validar_registro_entrada(nombre_completo, documento, correo, usuario, contrasena):
    """Validaciones de registro. Documento y correo no se persisten."""
    nombre_texto = (nombre_completo or "").strip()
    if not nombre_texto:
        return "Escribe tu nombre completo."
    if len(nombre_texto) > 140:
        return "El nombre es demasiado largo."
    error_doc = validar_documento_registro(documento)
    if error_doc:
        return error_doc
    error_correo = validar_correo_registro(correo)
    if error_correo:
        return error_correo
    usuario_texto = (usuario or "").strip()
    if not usuario_texto:
        return "Elige un nombre de usuario."
    if len(usuario_texto) > 70:
        return "El usuario no puede superar 70 caracteres."
    if len(usuario_texto) < 3:
        return "El usuario debe tener al menos 3 caracteres."
    if contrasena is None or contrasena == "":
        return "Crea una contraseña."
    if len(contrasena) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    return None


def iniciar_sesion_usuario(usuario_id, usuario, nombre, rol):
    session["sesion_iniciada"] = True
    session["usuario_id"] = int(usuario_id)
    session["usuario"] = usuario
    session["nombre"] = nombre
    session["nombre_usuario"] = nombre
    session["rol"] = rol


def destino_por_rol(rol):
    destinos = {
        "cliente": "/catalogo.html",
        "vendedor": "/vendedor.html",
        "administrador": "/administrador.html",
        "superadmin": "/superadmin.html",
    }
    return destinos.get(rol, "/login.html")


def redirigir_si_no_autorizado(pagina):
    """Impide que un visitante entre a páginas de un rol escribiendo la dirección."""
    rol = rol_actual()
    if pagina in ("index", "catalogo", "login", "registro"):
        return None
    if pagina in ("carrito", "pago", "turno", "pqr", "encuesta", "gracias", "pqr-gracias"):
        if rol != "cliente" or not usuario_id_actual():
            return redirect("/login.html")
        return None
    if pagina == "vendedor":
        if rol != "vendedor" or not usuario_id_actual():
            return redirect("/login.html")
        return None
    if pagina == "administrador" or pagina.startswith("admin-"):
        if rol not in ("administrador", "superadmin") or not usuario_id_actual():
            return redirect("/login.html")
        return None
    if pagina.startswith("superadmin"):
        if rol != "superadmin" or not usuario_id_actual():
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
        "csrf_token": obtener_token_csrf(),
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


@app.route("/registro.html", methods=["GET", "POST"])
def registro():
    if request.method != "POST":
        return mostrar_html("registro.html")
    if not verificar_token_csrf():
        return render_template(
            "registro.html",
            aviso="La solicitud no es válida. Vuelve a intentar el registro.",
            **datos_pagina_cliente(),
        )
    nombre_completo = request.form.get("nombre", "")
    documento = request.form.get("documento", "")
    correo = request.form.get("correo", "")
    usuario = request.form.get("usuario", "").strip()
    contrasena = request.form.get("contrasena", "")
    datos_form = {
        "valor_nombre": nombre_completo,
        "valor_documento": documento,
        "valor_correo": correo,
        "valor_usuario": usuario,
    }
    error = validar_registro_entrada(
        nombre_completo, documento, correo, usuario, contrasena
    )
    if error:
        return render_template(
            "registro.html",
            aviso=error,
            **datos_form,
            **datos_pagina_cliente(),
        )
    nombre, apellido = separar_nombre_apellido(nombre_completo)
    if not nombre:
        return render_template(
            "registro.html",
            aviso="Escribe tu nombre completo.",
            **datos_form,
            **datos_pagina_cliente(),
        )
    if existe_nombre_usuario(usuario):
        return render_template(
            "registro.html",
            aviso="Ese usuario ya existe. Elige otro nombre de usuario.",
            **datos_form,
            **datos_pagina_cliente(),
        )
    id_rol = obtener_id_rol("cliente")
    if id_rol is None:
        return render_template(
            "registro.html",
            aviso="No se encontró el rol cliente en MySQL.",
            **datos_form,
            **datos_pagina_cliente(),
        )
    # documento y correo se validan arriba pero no se insertan (sin columnas en BD).
    hash_clave = generate_password_hash(contrasena)
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO tbl_usuarios (
                Usu_Id_Rol, Usu_Nombre, Usu_Apellido,
                Usu_Usuario, Usu_Contrasena, Usu_Estado
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (id_rol, nombre, apellido, usuario, hash_clave, "Activo"),
        )
        conexion.commit()
        return redirect("/login.html?aviso=" + quote("Cuenta creada. Ya puedes iniciar sesión."))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al registrar usuario:", error)
        return render_template(
            "registro.html",
            aviso="No se pudo registrar el usuario. Intenta de nuevo.",
            **datos_form,
            **datos_pagina_cliente(),
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


@app.route("/login.html", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not verificar_token_csrf():
            return render_template(
                "login.html",
                aviso="La solicitud no es válida. Vuelve a intentar iniciar sesión.",
                **datos_pagina_cliente(),
            )
        usuario = request.form.get("usuario", "").strip()
        contrasena = request.form.get("contrasena", "")
        error_entrada = validar_login_entrada(usuario, contrasena)
        if error_entrada:
            return render_template(
                "login.html",
                aviso=error_entrada,
                **datos_pagina_cliente(),
            )
        fila = buscar_usuario_por_login(usuario)
        if fila is None:
            return render_template(
                "login.html",
                aviso="Usuario o contraseña incorrectos.",
                **datos_pagina_cliente(),
            )
        if (fila.get("Usu_Estado") or "") != "Activo":
            return render_template(
                "login.html",
                aviso="Tu cuenta no está activa.",
                **datos_pagina_cliente(),
            )
        if not check_password_hash(fila["Usu_Contrasena"], contrasena):
            return render_template(
                "login.html",
                aviso="Usuario o contraseña incorrectos.",
                **datos_pagina_cliente(),
            )
        nombre_mostrar = (fila["Usu_Nombre"] + " " + fila["Usu_Apellido"]).strip()
        iniciar_sesion_usuario(
            fila["Usu_Id_Usuario"],
            fila["Usu_Usuario"],
            nombre_mostrar,
            fila["Rol_Nombre_Rol"],
        )
        return redirect(destino_por_rol(fila["Rol_Nombre_Rol"]))
    return render_template(
        "login.html",
        aviso=request.args.get("aviso", ""),
        **datos_pagina_cliente(),
    )


@app.route("/entrar-rol", methods=["POST"])
def entrar_rol():
    # Ya no se permite elegir rol sin autenticación real.
    return redirect("/login.html?aviso=" + quote("Debes iniciar sesión con un usuario registrado."))


@app.route("/cerrar-sesion")
def cerrar_sesion():
    session.pop("sesion_iniciada", None)
    session.pop("usuario_id", None)
    session.pop("usuario", None)
    session.pop("nombre", None)
    session.pop("nombre_usuario", None)
    session.pop("rol", None)
    session.pop("csrf_token", None)
    return redirect("/index.html")


@app.route("/catalogo.html")
def catalogo():
    # Siempre sincronizar con MySQL: evita catálogo vacío si al arrancar falló la BD.
    recargar_productos()
    buscar = request.args.get("buscar", "")
    categoria = request.args.get("categoria", "todos") or "todos"
    orden = request.args.get("orden", "default") or "default"
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
    if rol_actual() != "cliente" or not usuario_id_actual():
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
    if rol_actual() != "cliente" or not usuario_id_actual():
        return redirect("/login.html")
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
    resultado = confirmar_compra_en_bd(items, lineas, total, usuario_id_actual())
    if resultado is None:
        return redirect("/pago.html?aviso=" + quote("No se pudo confirmar el pago. Revisa el inventario disponible."))
    pedido_id, turno_id, numero_turno = resultado
    global ultimo_turno_asignado
    if numero_turno > ultimo_turno_asignado:
        ultimo_turno_asignado = numero_turno
    pedido = registrar_pedido(
        numero_turno,
        lineas,
        total,
        pedido_id=pedido_id,
        turno_id=turno_id,
    )
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
    if not actualizar_estado_pedido_bd(pedido_id, nuevo):
        return redirect("/vendedor.html?aviso=" + quote("No se pudo actualizar el estado en MySQL."))
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
    marcar_turno_atendido(turno_actual)
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
    id_categoria = obtener_id_categoria(categoria)
    if id_categoria is None:
        return redirect("/admin-productos.html?aviso=" + quote("La categoría no es válida."))
    precio = int(precio_texto)
    cantidad = int(cantidad_texto)
    codigo = generar_codigo_producto()
    valor_tot = precio * cantidad
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO tbl_productos (
                Prod_cod_producto, Prod_Id_Categoria, Prod_Nombre_Producto,
                Prod_Precio, Prod_Disponible, Prod_Cant_est, Prod_Valor_Tot,
                Prod_Imagen, Prod_Destacado
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                codigo,
                id_categoria,
                nombre.strip(),
                precio,
                texto_disponibilidad(cantidad),
                cantidad,
                valor_tot,
                imagen,
                0,
            ),
        )
        conexion.commit()
        recargar_productos()
        return redirect("/admin-productos.html?aviso=" + quote("El producto fue agregado."))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al agregar producto:", error)
        return redirect("/admin-productos.html?aviso=" + quote("No se pudo agregar el producto en MySQL."))
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


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
    id_categoria = obtener_id_categoria(categoria)
    if id_categoria is None:
        return redirect("/admin-productos.html?editar=" + str(producto_id) + "&aviso=" + quote("La categoría no es válida."))
    precio = int(precio_texto)
    cantidad = int(cantidad_texto)
    valor_tot = precio * cantidad
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_productos
            SET Prod_Id_Categoria = %s,
                Prod_Nombre_Producto = %s,
                Prod_Precio = %s,
                Prod_Cant_est = %s,
                Prod_Valor_Tot = %s,
                Prod_Imagen = %s,
                Prod_Disponible = %s
            WHERE Prod_Id_Producto = %s
              AND (Prod_Disponible IS NULL OR Prod_Disponible <> 'No disponible')
            """,
            (
                id_categoria,
                nombre.strip(),
                precio,
                cantidad,
                valor_tot,
                imagen,
                texto_disponibilidad(cantidad),
                producto_id,
            ),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return redirect("/admin-productos.html?aviso=" + quote("No se encontró el producto."))
        conexion.commit()
        recargar_productos()
        return redirect("/admin-productos.html?aviso=" + quote("El producto fue actualizado."))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al editar producto:", error)
        return redirect("/admin-productos.html?aviso=" + quote("No se pudo actualizar el producto en MySQL."))
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


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
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        # Baja lógica: evita romper futuras relaciones con detallepedido.
        cursor.execute(
            """
            UPDATE tbl_productos
            SET Prod_Disponible = 'No disponible'
            WHERE Prod_Id_Producto = %s
            """,
            (producto_id,),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return redirect("/admin-productos.html?aviso=" + quote("No se encontró el producto."))
        conexion.commit()
        recargar_productos()
        return redirect("/admin-productos.html?aviso=" + quote("El producto fue desactivado."))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al desactivar producto:", error)
        return redirect("/admin-productos.html?aviso=" + quote("No se pudo desactivar el producto en MySQL."))
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


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
    direccion_local = f"http://localhost:{puerto}/index.html"
    print("=" * 50)
    print("  CAFETIX JOACO")
    print("=" * 50)
    print(f"  Local:   {direccion_local}")
    print(f"  Network: http://0.0.0.0:{puerto}/index.html")
    print("  (usa la IP de tu PC en la LAN, ej. http://192.168.x.x:5001)")
    print("  Presiona Ctrl+C para detener")
    print("=" * 50)
    probar_conexion_mysql()
    Timer(1, lambda: webbrowser.open(direccion_local)).start()
    app.run(host="0.0.0.0", port=puerto, debug=True, use_reloader=False)
