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

from datetime import datetime, time, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit, urlunsplit
import os
import secrets
import webbrowser
from threading import Lock, Timer

import mysql.connector
from flask import Flask, render_template, request, send_from_directory, redirect, session, abort, g, url_for
from werkzeug.security import generate_password_hash, check_password_hash

CARPETA = Path(__file__).resolve().parent
CARPETA_HTML = CARPETA / "html"
CARPETA_CSS = CARPETA / "css"
CARPETA_IMG = CARPETA / "img"
CARPETA_PRIVADA = ".cafetix"
NOMBRE_ARCHIVO_SECRET_KEY = "secret_key"
NOMBRE_ARCHIVO_SECRET_KEY_LEGACY = ".cafetix_secret_key"


def _leer_clave_local(ruta):
    try:
        return ruta.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""


def _guardar_clave_local(ruta, clave):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(clave + "\n", encoding="utf-8")


def obtener_secret_key(carpeta=None):
    """Prioridad: CAFETIX_SECRET_KEY / SECRET_KEY, luego .cafetix/secret_key persistente."""
    entorno = (os.environ.get("CAFETIX_SECRET_KEY") or os.environ.get("SECRET_KEY") or "").strip()
    if entorno:
        return entorno

    base = carpeta or CARPETA
    destino = base / CARPETA_PRIVADA / NOMBRE_ARCHIVO_SECRET_KEY
    if destino.is_file():
        local = _leer_clave_local(destino)
        if local:
            return local

    legacy = base / NOMBRE_ARCHIVO_SECRET_KEY_LEGACY
    if legacy.is_file():
        anterior = _leer_clave_local(legacy)
        if anterior:
            _guardar_clave_local(destino, anterior)
            try:
                legacy.unlink()
            except OSError:
                pass
            return anterior

    clave = secrets.token_hex(32)
    _guardar_clave_local(destino, clave)
    return clave


app = Flask(__name__, template_folder=str(CARPETA_HTML))
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.secret_key = obtener_secret_key()


@app.context_processor
def inyectar_datos_usuario_global():
    return {
        "nombre_usuario": session.get("nombre_usuario", ""),
        "sesion_iniciada": usuario_logueado(),
        "rol": rol_actual(),
        "tiene_columna_costo": columna_costo_existe(),
    }


def entero_desde_entorno(nombre, respaldo):
    """Lee un entero de una variable de entorno. Si falta o no es válido, usa el respaldo."""
    texto = (os.environ.get(nombre) or "").strip()
    if not texto:
        return respaldo
    try:
        return int(texto)
    except ValueError:
        return respaldo


def debug_desde_entorno():
    """Debug solo si CAFETIX_DEBUG es 1, true, yes u on. Por defecto queda apagado."""
    valor = (os.environ.get("CAFETIX_DEBUG") or "").strip().lower()
    return valor in ("1", "true", "yes", "on")


def _resolver_ruta_ssl_ca(ruta):
    """Resuelve la ruta del certificado CA, admitiendo rutas absolutas o relativas al proyecto."""
    if not ruta:
        return ""
    p = Path(ruta)
    if p.is_file():
        return str(p.resolve())
    p_proyecto = CARPETA / ruta
    if p_proyecto.is_file():
        return str(p_proyecto.resolve())
    return str(p)


def _aplicar_configuracion_ssl(config, query_params=None):
    """Aplica opciones SSL a la configuración de MySQL de forma segura.

    Variables de entorno soportadas:
      - CAFETIX_DB_SSL_CA o MYSQL_SSL_CA: ruta al archivo de certificado CA (.pem).
      - CAFETIX_DB_SSL o CAFETIX_DB_SSL_MODE: activación explícita de SSL.
      - CAFETIX_DB_SSL_VERIFY_IDENTITY: verificación de host (por defecto True).
      - Parámetro ssl_ca, ssl-ca, ssl_mode o ssl-mode en DATABASE_URL.

    Comportamiento:
      - Si se proporciona un certificado CA existente: se activa ssl_ca, ssl_verify_cert=True
        y ssl_verify_identity=True según las opciones de mysql-connector-python.
      - Si se especifica una ruta inexistente: se lanza FileNotFoundError claro y seguro.
      - Si se solicita SSL explícitamente sin indicar CA: se lanza ValueError explicativo.
      - Si no se configura SSL: no se modifica config, garantizando compatibilidad con XAMPP local.
    """
    qp = query_params or {}
    ruta_ca_raw = (
        os.environ.get("CAFETIX_DB_SSL_CA")
        or os.environ.get("MYSQL_SSL_CA")
        or qp.get("ssl_ca")
        or qp.get("ssl-ca")
        or ""
    ).strip()

    ssl_mode_raw = (
        os.environ.get("CAFETIX_DB_SSL_MODE")
        or qp.get("ssl-mode")
        or qp.get("ssl_mode")
        or ""
    ).strip().upper()

    ssl_forzado = (
        (os.environ.get("CAFETIX_DB_SSL") or "").strip().lower() in ("1", "true", "yes", "on")
        or ssl_mode_raw in ("REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY")
    )

    if not ruta_ca_raw:
        if ssl_forzado:
            raise ValueError(
                "Se configuró SSL para MySQL (CAFETIX_DB_SSL / CAFETIX_DB_SSL_MODE), "
                "pero no se especificó la ruta del certificado CA (CAFETIX_DB_SSL_CA). "
                "Para conectarse con seguridad a Aiven se requiere el archivo de certificado CA oficial."
            )
        # Sin SSL: conservar funcionamiento normal de XAMPP local
        return

    ruta_ca_resuelta = _resolver_ruta_ssl_ca(ruta_ca_raw)
    if not Path(ruta_ca_resuelta).is_file():
        raise FileNotFoundError(
            f"El archivo de certificado CA para MySQL no existe o no se puede leer: '{ruta_ca_raw}'"
        )

    config["ssl_ca"] = ruta_ca_resuelta
    config["ssl_verify_cert"] = True

    # Verificación de identidad del host (habilitada por defecto, configurable)
    verify_identity_env = os.environ.get("CAFETIX_DB_SSL_VERIFY_IDENTITY", "").strip().lower()
    if verify_identity_env in ("0", "false", "no", "off"):
        config["ssl_verify_identity"] = False
    else:
        config["ssl_verify_identity"] = True


def _configuracion_mysql():
    """Obtiene los parámetros de conexión a MySQL.
    Soporta DATABASE_URL/MYSQL_URL, variables CAFETIX_DB_*, variables estándar de hosting (MYSQL*),
    soporte SSL opcional con verificación de CA, y valores por defecto locales de XAMPP.
    """
    url_db = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL") or ""
    if url_db.startswith("mysql://") or url_db.startswith("mysql+mysqlconnector://"):
        partes = urlsplit(url_db)
        config = {
            "host": partes.hostname or "127.0.0.1",
            "user": unquote(partes.username) if partes.username is not None else "root",
            "password": unquote(partes.password) if partes.password is not None else "",
            "database": unquote((partes.path or "").lstrip("/")) or "cafetix_joaco",
            "port": partes.port or 3306,
        }
        query_params = dict(parse_qsl(partes.query))
    else:
        config = {
            "host": os.environ.get("CAFETIX_DB_HOST") or os.environ.get("MYSQLHOST") or os.environ.get("DB_HOST") or "127.0.0.1",
            "user": os.environ.get("CAFETIX_DB_USER") or os.environ.get("MYSQLUSER") or os.environ.get("DB_USER") or "root",
            "password": os.environ.get("CAFETIX_DB_PASSWORD") or os.environ.get("MYSQLPASSWORD") or os.environ.get("DB_PASSWORD") or "",
            "database": os.environ.get("CAFETIX_DB_NAME") or os.environ.get("MYSQLDATABASE") or os.environ.get("DB_NAME") or "cafetix_joaco",
            "port": entero_desde_entorno("CAFETIX_DB_PORT", entero_desde_entorno("MYSQLPORT", entero_desde_entorno("DB_PORT", 3306))),
        }
        query_params = {}

    _aplicar_configuracion_ssl(config, query_params)
    return config


def obtener_conexion():
    """Abre una conexión a MySQL/MariaDB. XAMPP local si no hay variables de entorno."""
    return mysql.connector.connect(**_configuracion_mysql())


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
    except (mysql.connector.Error, FileNotFoundError, ValueError) as error:
        print("No se pudo conectar a MySQL.")
        return False
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


def cargar_categorias_desde_bd():
    """Lee tbl_categorias y agrega el filtro 'todos' solo en Python.

    Solo incluye las categorías activas que tengan al menos un producto disponible en MySQL.
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
            SELECT DISTINCT
                c.Cat_Codigo,
                c.Cat_Nombre_Categoria,
                c.Cat_Id_Categoria
            FROM tbl_categorias AS c
            INNER JOIN tbl_productos AS p
                ON p.Prod_Id_Categoria = c.Cat_Id_Categoria
            WHERE c.Cat_Estado = 'Activo'
              AND (p.Prod_Disponible IS NULL OR p.Prod_Disponible <> 'No disponible')
            ORDER BY c.Cat_Id_Categoria ASC
            """
        )
        for fila in cursor.fetchall():
            codigo = fila["Cat_Codigo"]
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
            imagen = (fila["Prod_Imagen"] or "").strip()
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


def codigos_categorias_activas():
    """Códigos de categorías con productos disponibles (sin incluir 'todos')."""
    return tuple(cat["id"] for cat in CATEGORIAS if cat.get("id") and cat["id"] != "todos")


class _CategoriasFiltroProxy:
    def __contains__(self, item):
        return item in codigos_categorias_activas()

    def __iter__(self):
        return iter(codigos_categorias_activas())

    def __len__(self):
        return len(codigos_categorias_activas())

    def __repr__(self):
        return repr(codigos_categorias_activas())


CATEGORIAS_FILTRO_PUBLICO = _CategoriasFiltroProxy()


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
        copia["imagen"] = ""
    return copia


def categorias_producto():
    return [item for item in CATEGORIAS if item["id"] != "todos"]


EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".webp")
# Archivos de interfaz en img/; no son fotografías de productos del catálogo.
IMAGENES_INTERFAZ = {
    "cafeteria-institucional.jpg",
    "favicon.png",
    "fondo-administrador.png",
    "fondo-catalogo.png",
    "fondo-superadmin.png",
    "fondo-vendedor.png",
    "login-left-background.png",
    "login-page-background.png",
    "login-right-background.png",
    "logo-jjfh-transparente.png",
    "logo.png",
    "qr-demo.svg",
    "qr-nequi-pago.jpg",
}


def _nombre_archivo_imagen_seguro(nombre):
    """Acepta solo un nombre de archivo, sin rutas ni .. ."""
    texto = (nombre or "").strip()
    if not texto or texto in (".", ".."):
        return False
    if "/" in texto or "\\" in texto:
        return False
    if Path(texto).name != texto:
        return False
    return Path(texto).suffix.lower() in EXTENSIONES_IMAGEN


def valor_imagen_seguro(valor):
    """Valores compatibles con el catálogo: ../foto.jpg o icono.svg."""
    texto = (valor or "").strip()
    if texto.startswith("../"):
        return _nombre_archivo_imagen_seguro(texto[3:])
    return _nombre_archivo_imagen_seguro(texto)


def imagenes_disponibles():
    """Fotografías de img/ guardadas como ../archivo.jpg, igual que en MySQL."""
    lista = []
    if not CARPETA_IMG.is_dir():
        return lista
    for archivo in sorted(CARPETA_IMG.iterdir()):
        if not archivo.is_file():
            continue
        if archivo.suffix.lower() not in EXTENSIONES_IMAGEN:
            continue
        if archivo.name in IMAGENES_INTERFAZ:
            continue
        if not _nombre_archivo_imagen_seguro(archivo.name):
            continue
        lista.append("../" + archivo.name)
    return lista


def imagenes_para_formulario(imagen_actual=""):
    """Lista del selector. Si el producto ya tiene imagen, esa opción queda disponible."""
    lista = list(imagenes_disponibles())
    actual = (imagen_actual or "").strip()
    if actual and actual not in lista and valor_imagen_seguro(actual) and not _archivo_es_interfaz(actual):
        lista.insert(0, actual)
    return lista


def _archivo_es_interfaz(valor):
    texto = (valor or "").strip()
    if texto.startswith("../"):
        texto = texto[3:]
    return Path(texto).name in IMAGENES_INTERFAZ


def imagen_catalogo_permitida(valor):
    if _archivo_es_interfaz(valor):
        return False
    return valor in imagenes_disponibles()


def src_imagen_producto(valor):
    """Ruta de una foto que está en img/. Vacía si el producto no tiene imagen."""
    texto = (valor or "").strip()
    nombre = texto[3:] if texto.startswith("../") else texto
    if not _nombre_archivo_imagen_seguro(nombre) or _archivo_es_interfaz(nombre):
        return ""
    if (CARPETA_IMG / nombre).is_file():
        return "../img/" + nombre
    return ""


def imagen_para_guardar(valor):
    """None si no hay imagen. False si el nombre no corresponde a un archivo de img/."""
    texto = (valor or "").strip()
    if not texto:
        return None
    if imagen_catalogo_permitida(texto):
        return texto
    return False


def buscar_producto(producto_id):
    for producto in PRODUCTOS:
        if producto["id"] == producto_id:
            return producto
    return None


MAX_NOMBRE_PRODUCTO = 100
MENSAJE_NOMBRE_PRODUCTO_VACIO = "El nombre no puede estar vacío."
MENSAJE_NOMBRE_PRODUCTO_LARGO = "El nombre puede tener máximo 100 caracteres."


def validar_producto(nombre, categoria, precio_texto, cantidad_texto):
    nombre_limpio = (nombre or "").strip()
    if not nombre_limpio:
        return MENSAJE_NOMBRE_PRODUCTO_VACIO
    if len(nombre_limpio) > MAX_NOMBRE_PRODUCTO:
        return MENSAJE_NOMBRE_PRODUCTO_LARGO
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


MAX_BUSQUEDA_CATALOGO = 80
MENSAJE_BUSQUEDA_LARGA = "La búsqueda puede tener máximo 80 caracteres."


def categoria_catalogo_valida(valor):
    """Solo acepta filtros públicos del catálogo o 'todos'."""
    texto = (valor or "todos").strip() or "todos"
    if texto == "todos":
        return "todos"
    if texto in CATEGORIAS_FILTRO_PUBLICO:
        return texto
    return "todos"


def buscar_catalogo_valido(valor):
    """Limpia la búsqueda pública. Vacío = sin filtro. Más de 80 → None."""
    texto = (valor or "").replace("\x00", "").strip()
    if not texto:
        return ""
    if len(texto) > MAX_BUSQUEDA_CATALOGO:
        return None
    return texto


def ancla_id_producto(producto, prefijo="producto"):
    """Ancla estable por código real o, si falta, por ID numérico."""
    codigo = (producto.get("codigo") or "").strip()
    if codigo and all(caracter.isalnum() or caracter in "-_" for caracter in codigo):
        sufijo = codigo
    else:
        sufijo = str(int(producto.get("id") or 0))
    return prefijo + "-" + sufijo


def ancla_catalogo_valida(valor):
    """Solo permite fragmentos internos producto-* o destacado-*."""
    texto = (valor or "").strip()
    prefijo = None
    for candidato in ("producto-", "destacado-"):
        if texto.startswith(candidato):
            prefijo = candidato
            break
    if prefijo is None or len(texto) > 48:
        return ""
    sufijo = texto[len(prefijo):]
    if not sufijo:
        return ""
    if not all(caracter.isalnum() or caracter in "-_" for caracter in sufijo):
        return ""
    return texto


def producto_con_ancla(producto, prefijo="producto"):
    """Copia de lectura para la plantilla. No altera el caché de PRODUCTOS."""
    copia = dict(producto)
    copia["ancla"] = ancla_id_producto(producto, prefijo)
    return copia


def url_catalogo(aviso=""):
    """Vuelve al catálogo conservando filtros válidos y, si existe, el ancla del producto."""
    buscar = buscar_catalogo_valido(request.form.get("buscar", "")) or ""
    categoria = categoria_catalogo_valida(request.form.get("categoria", "todos"))
    orden = orden_catalogo_valido(request.form.get("orden", "default"))
    parametros = {
        "categoria": categoria,
        "buscar": buscar,
        "orden": orden,
    }
    if aviso:
        parametros["aviso"] = aviso
    fragmento = ancla_catalogo_valida(request.form.get("ancla", ""))
    if fragmento:
        return url_for("catalogo", _anchor=fragmento, **parametros)
    return url_for("catalogo", **parametros)


def ancla_id_pedido(pedido_id):
    """Ancla estable por Ped_Id_Pedido. Vacía si el id no es válido."""
    try:
        numero = int(pedido_id)
    except (TypeError, ValueError):
        return ""
    if numero < 1:
        return ""
    return "pedido-" + str(numero)


def ancla_vendedor_valida(valor):
    """Solo permite #pedidos o #pedido-<id numérico>."""
    texto = (valor or "").strip()
    if texto == "pedidos":
        return "pedidos"
    if not texto.startswith("pedido-") or len(texto) > 32:
        return ""
    sufijo = texto[7:]
    if not sufijo.isdigit():
        return ""
    if int(sufijo) < 1:
        return ""
    return "pedido-" + str(int(sufijo))


def url_vendedor(aviso="", fragmento="", turno=""):
    """Vuelve al panel Vendedor con aviso interno y ancla segura."""
    parametros = {}
    if aviso:
        parametros["aviso"] = aviso
    if turno:
        parametros["turno"] = turno
    ancla = ancla_vendedor_valida(fragmento)
    if ancla:
        return url_for("vendedor", _anchor=ancla, **parametros)
    return url_for("vendedor", **parametros)


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
    """Siguiente número en memoria: 1, 2, 3...

    La compra no llama esta función. El número que ve el cliente se guarda
    en tbl_turnos dentro de la misma transacción, con _insertar_turno_unico.
    """
    global ultimo_turno_asignado
    ultimo_turno_asignado = ultimo_turno_asignado + 1
    return ultimo_turno_asignado


def registrar_pedido(turno_cliente, lineas, total, pedido_id=None, turno_id=None, metodo_pago="No registrado", estado_pago="No registrado"):
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
        "metodo_pago": metodo_pago or "No registrado",
        "estado_pago": estado_pago or "No registrado",
    }
    PEDIDOS.append(pedido)
    return pedido


METODOS_PAGO = ("Nequi", "Efectivo")


def estado_pago_segun_metodo(metodo_pago):
    if metodo_pago in ("Nequi", "Efectivo"):
        return "Pendiente"
    return None


MYSQL_ER_DUP_ENTRY = 1062
LOCK_NUMERO_TURNO = "cafetix_tur_numero"


def _es_duplicado_mysql(error, nombre_indice):
    """True si MySQL/MariaDB rechazó un UNIQUE concreto (errno 1062)."""
    if getattr(error, "errno", None) != MYSQL_ER_DUP_ENTRY:
        return False
    return nombre_indice in str(error)


def _obtener_lock_mysql(cursor, nombre, espera=10):
    cursor.execute("SELECT GET_LOCK(%s, %s)", (nombre, espera))
    fila = cursor.fetchone()
    return fila is not None and fila[0] == 1


def _liberar_lock_mysql(cursor, nombre):
    try:
        cursor.execute("SELECT RELEASE_LOCK(%s)", (nombre,))
        cursor.fetchone()
    except mysql.connector.Error:
        pass


def _pedido_por_token_y_usuario(cursor, token_compra, usuario_id):
    """
    Busca el pedido de esa clave de idempotencia.
    Devuelve (pedido_id, turno_id, numero_turno), 'ajeno' o None.
    """
    cursor.execute(
        """
        SELECT
            p.Ped_Id_Pedido,
            p.Ped_Id_Turno,
            p.Ped_Id_Usuario,
            t.Tur_Numero_Turno
        FROM tbl_pedidos AS p
        INNER JOIN tbl_turnos AS t
            ON t.Tur_Id_Turno = p.Ped_Id_Turno
        WHERE p.Ped_Token_Compra = %s
        """,
        (token_compra,),
    )
    fila = cursor.fetchone()
    if fila is None:
        return None
    if int(fila[2] or 0) != int(usuario_id):
        return "ajeno"
    return (int(fila[0]), int(fila[1]), int(fila[3] or 0))


def _siguiente_numero_turno(cursor):
    """Siguiente número según MySQL: MAX + 1. Si no hay turnos, el primero es 1.

    No se compara con el número del indicador. Ese número es el que atiende
    el vendedor; el del pedido sale solo de tbl_turnos.
    """
    cursor.execute("SELECT COALESCE(MAX(Tur_Numero_Turno), 0) FROM tbl_turnos")
    max_numero = int(cursor.fetchone()[0] or 0)
    return max_numero + 1


def _insertar_turno_unico(cursor, usuario_id, fecha, hora):
    """
    Asigna Tur_Numero_Turno con GET_LOCK + MAX+1.
    UNIQUE en BD es la garantía final; si hay colisión, reintenta.
    """
    if not _obtener_lock_mysql(cursor, LOCK_NUMERO_TURNO):
        return None
    try:
        intentos = 0
        while intentos < 8:
            numero_turno = _siguiente_numero_turno(cursor)
            try:
                cursor.execute(
                    """
                    INSERT INTO tbl_turnos (
                        Tur_Id_Usuario, Tur_Numero_Turno, Tur_Fecha,
                        Tur_Hora_Solicitud, Tur_Estado_Turno
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (usuario_id, numero_turno, fecha, hora, "Pendiente"),
                )
                return (int(cursor.lastrowid), int(numero_turno))
            except mysql.connector.Error as error:
                if _es_duplicado_mysql(error, "uq_tur_numero_turno") or _es_duplicado_mysql(error, "Tur_Numero_Turno"):
                    intentos = intentos + 1
                    continue
                raise
        return None
    finally:
        _liberar_lock_mysql(cursor, LOCK_NUMERO_TURNO)


def _leer_producto_para_compra(cursor, producto_id):
    """Lee precio, stock y disponibilidad actuales. FOR UPDATE en la transacción."""
    cursor.execute(
        """
        SELECT
            Prod_Id_Producto,
            Prod_Nombre_Producto,
            Prod_Precio,
            Prod_Cant_est,
            Prod_Disponible
        FROM tbl_productos
        WHERE Prod_Id_Producto = %s
        FOR UPDATE
        """,
        (producto_id,),
    )
    return cursor.fetchone()


def _lineas_compra_desde_mysql(cursor, items):
    """Arma líneas y total con precios de tbl_productos. None si no se puede confirmar."""
    lineas = []
    total = 0
    for item in items:
        producto_id = int(item["id"])
        cantidad = int(item["cantidad"])
        if cantidad < 1:
            return None
        fila = _leer_producto_para_compra(cursor, producto_id)
        if fila is None:
            return None
        disponible = (fila[4] or "").strip()
        if disponible == "No disponible":
            return None
        precio = int(fila[2] or 0)
        if precio <= 0:
            return None
        stock = int(fila[3] or 0)
        if stock < cantidad:
            return None
        subtotal = precio * cantidad
        total = total + subtotal
        lineas.append({
            "id": int(fila[0]),
            "nombre": fila[1] or "Producto",
            "cantidad": cantidad,
            "precio": precio,
            "precio_texto": precio_en_texto(precio),
            "subtotal": subtotal,
            "subtotal_texto": precio_en_texto(subtotal),
        })
    if not lineas:
        return None
    return lineas, total


def confirmar_compra_en_bd(items, usuario_id, metodo_pago, token_compra=None):
    """
    En una sola transacción:
    - lee precio y stock actuales de MySQL
    - descuenta inventario
    - inserta turno, pedido (con Ped_Token_Compra), detalles y venta
    Devuelve (pedido_id, turno_id, numero_turno, ya_existia, lineas, total) o None.
    """
    if usuario_id is None:
        return None
    token = (token_compra or "").strip()
    if not token or len(token) > 128:
        return None
    estado_pago = estado_pago_segun_metodo(metodo_pago)
    if metodo_pago not in METODOS_PAGO or estado_pago is None:
        return None
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()

        existente = _pedido_por_token_y_usuario(cursor, token, usuario_id)
        if existente == "ajeno":
            return None
        if existente is not None:
            return (existente[0], existente[1], existente[2], True, None, None)

        armado = _lineas_compra_desde_mysql(cursor, items)
        if armado is None:
            conexion.rollback()
            return None
        lineas, total = armado

        if not _actualizar_stock_en_cursor(cursor, items):
            conexion.rollback()
            return None

        ahora = datetime.now()
        fecha = ahora.date()
        hora = ahora.time().replace(microsecond=0)

        asignado = _insertar_turno_unico(cursor, usuario_id, fecha, hora)
        if asignado is None:
            conexion.rollback()
            return None
        turno_id, numero_turno = asignado

        try:
            cursor.execute(
                """
                INSERT INTO tbl_pedidos (
                    Ped_Id_Usuario, Ped_Id_Turno, Ped_Fecha_Pedido,
                    Ped_Estado_Pedido, Ped_Total_Pedido, Ped_Token_Compra
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (usuario_id, turno_id, fecha, "pendiente", total, token),
            )
        except mysql.connector.Error as error:
            if _es_duplicado_mysql(error, "uq_ped_token_compra") or _es_duplicado_mysql(error, "Ped_Token_Compra"):
                conexion.rollback()
                recuperado = _pedido_por_token_y_usuario(cursor, token, usuario_id)
                if recuperado == "ajeno" or recuperado is None:
                    return None
                return (recuperado[0], recuperado[1], recuperado[2], True, None, None)
            raise
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
            (pedido_id, fecha, total, metodo_pago, estado_pago, usuario_id),
        )
        conexion.commit()
        recargar_productos()
        return (int(pedido_id), int(turno_id), int(numero_turno), False, lineas, total)
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


MENSAJE_PEDIDO_YA_ACTUALIZADO = "El pedido ya fue actualizado. Revisa su estado actual."


def actualizar_estado_pedido_bd(pedido_id, nuevo_estado, estado_actual):
    """Persiste Ped_Estado_Pedido solo si el pedido sigue en estado_actual."""
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
              AND LOWER(TRIM(Ped_Estado_Pedido)) = LOWER(TRIM(%s))
            """,
            ((nuevo_estado or "").strip().lower(), pedido_id, (estado_actual or "").strip().lower()),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return "conflicto"
        conexion.commit()
        return "ok"
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al actualizar estado del pedido:", error)
        return "error"
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
ESTADOS_PEDIDO_ACTIVOS = ("pendiente", "en_preparacion", "listo")

CATEGORIA_PREPARACION = "recien-preparadas"


def producto_requiere_preparacion(cat_codigo):
    return (cat_codigo or "") == CATEGORIA_PREPARACION


def siguiente_estado_pedido(estado, requiere_preparacion):
    """Siguiente estado según tipo de productos. No usa el valor enviado por el navegador."""
    est = (estado or "").strip().lower()
    if est == "pendiente":
        if requiere_preparacion:
            return "en_preparacion"
        return "listo"
    if est == "en_preparacion":
        return "listo"
    if est == "listo":
        return "entregado"
    return ""


def entrega_bloqueada_por_pago(pedido):
    """Bloquea la entrega si el pago está pendiente (efectivo o transferencia QR)."""
    pago = (pedido.get("estado_pago") or "").strip().lower()
    metodo = (pedido.get("metodo_pago") or "").strip().lower()
    return pago == "pendiente" and (
        metodo in ("nequi", "efectivo", "transferencia con qr")
        or pedido.get("metodo_pago") in METODOS_PAGO
    )


def entrega_bloqueada_por_efectivo(pedido):
    """Mantiene compatibilidad con código existente."""
    return entrega_bloqueada_por_pago(pedido)


def consultar_pedidos_bloqueantes_turno(numero_turno):
    """
    Retorna la lista de pedidos asociados a numero_turno que impiden avanzar:
    aquellos cuyo estado no es 'entregado' o cuyo pago sigue 'Pendiente'.
    """
    cargar_pedidos_desde_bd()
    bloqueantes = []
    for p in PEDIDOS:
        if int(p.get("turno") or 0) == int(numero_turno):
            estado = (p.get("estado") or "").strip().lower()
            pago = (p.get("estado_pago") or "").strip().lower()
            metodo = (p.get("metodo_pago") or "").strip().lower()
            if estado != "entregado" or (pago == "pendiente" and (metodo in ("nequi", "efectivo", "transferencia con qr") or p.get("metodo_pago") in METODOS_PAGO)):
                bloqueantes.append(p)
    return bloqueantes


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
    metodo_raw = pedido.get("metodo_pago") or "No registrado"
    copia["metodo_pago"] = metodo_raw
    copia["metodo_pago_texto"] = "Transferencia con QR" if metodo_raw == "Nequi" else metodo_raw
    copia["estado_pago"] = pedido.get("estado_pago") or "No registrado"
    copia["puede_confirmar_efectivo"] = (
        metodo_raw == "Efectivo" and copia["estado_pago"] == "Pendiente"
    )
    copia["puede_confirmar_transferencia"] = (
        metodo_raw == "Nequi" and copia["estado_pago"] == "Pendiente"
    )
    requiere = bool(pedido.get("requiere_preparacion"))
    copia["requiere_preparacion"] = requiere
    if requiere:
        copia["tipo_productos"] = "Requiere preparación"
        copia["tipo_productos_clase"] = "badge-preparacion"
    else:
        copia["tipo_productos"] = "Productos listos"
        copia["tipo_productos_clase"] = "badge-listos"
    siguiente = siguiente_estado_pedido(pedido.get("estado"), requiere)
    bloquea_entrega = siguiente == "entregado" and entrega_bloqueada_por_pago(copia)
    copia["aviso_entrega_efectivo"] = bloquea_entrega and metodo_raw == "Efectivo"
    copia["aviso_entrega_transferencia"] = bloquea_entrega and metodo_raw == "Nequi"
    copia["aviso_entrega_pago"] = bloquea_entrega
    if siguiente and not bloquea_entrega:
        copia["siguiente_estado"] = siguiente
        copia["siguiente_texto"] = ESTADOS_PEDIDO[siguiente]
    else:
        copia["siguiente_estado"] = ""
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


def texto_pago_consulta(valor):
    texto = (valor or "").strip()
    if not texto or texto == "No registrado":
        return "Sin información"
    if texto == "Nequi":
        return "Transferencia con QR"
    return texto


def pedidos_para_admin():
    """Consulta de pedidos para el administrador. No cambia estados."""
    cargar_pedidos_desde_bd()
    lista = []
    for pedido in PEDIDOS:
        vista = preparar_pedido_vista(pedido)
        fecha = pedido.get("fecha")
        if hasattr(fecha, "strftime"):
            vista["fecha"] = fecha.strftime("%d/%m/%Y")
        elif fecha:
            vista["fecha"] = str(fecha)
        else:
            vista["fecha"] = "—"
        vista["fecha_orden"] = fecha or datetime.min.date()
        vista["estudiante"] = pedido.get("estudiante") or "Usuario no disponible"
        vista["turno"] = pedido.get("turno") or "—"
        lineas = []
        for item in pedido.get("productos") or []:
            lineas.append(str(item.get("cantidad", 0)) + " " + (item.get("nombre") or "Producto"))
        vista["productos_texto"] = ", ".join(lineas) if lineas else "Sin productos"
        vista["metodo_pago"] = texto_pago_consulta(vista.get("metodo_pago"))
        vista["estado_pago"] = texto_pago_consulta(vista.get("estado_pago"))
        lista.append(vista)
    lista.sort(key=lambda item: (item["fecha_orden"], item.get("id") or 0), reverse=True)
    return lista


# Opciones válidas del selector de orden del catálogo.
ORDENES_CATALOGO = ("default", "precio-asc", "precio-desc", "nombre-asc", "nombre-desc")


def orden_catalogo_valido(valor):
    """Acepta solo las opciones del selector; cualquier otra vuelve al orden predeterminado."""
    valor = (valor or "").strip()
    if valor in ORDENES_CATALOGO:
        return valor
    return "default"


ESTADOS_FILTRO_ADMIN = ("todos", "disponible", "agotado")
MAX_BUSQUEDA_ADMIN = 80


def categoria_filtro_admin_valida(valor):
    """Solo acepta códigos reales de categoría o el valor por defecto 'todas'."""
    texto = (valor or "").strip().lower()
    if not texto or texto in ("todas", "todos"):
        return "todas"
    ids_validos = {item["id"] for item in categorias_producto()}
    if texto in ids_validos:
        return texto
    return "todas"


def estado_filtro_admin_valido(valor):
    """Solo acepta todos / disponible / agotado. Cualquier otro valor se ignora."""
    texto = (valor or "").strip().lower()
    if texto in ESTADOS_FILTRO_ADMIN:
        return texto
    return "todos"


def buscar_filtro_admin(valor):
    """Limpia el texto de búsqueda. No se usa en SQL."""
    texto = (valor or "").replace("\x00", "").strip()
    if len(texto) > MAX_BUSQUEDA_ADMIN:
        texto = texto[:MAX_BUSQUEDA_ADMIN]
    return texto


def leer_filtros_admin():
    """Lee y normaliza los GET de Productos e Inventarios."""
    categoria = categoria_filtro_admin_valida(request.args.get("categoria", "todas"))
    estado = estado_filtro_admin_valido(request.args.get("estado", "todos"))
    buscar = buscar_filtro_admin(request.args.get("q", ""))
    return {
        "filtro_categoria": categoria,
        "filtro_estado": estado,
        "filtro_q": buscar,
        "hay_filtros": categoria != "todas" or estado != "todos" or bool(buscar),
    }


ESTADOS_PAGO_FILTRO = ("Confirmado", "Pendiente")


def valor_filtro_whitelist(valor, permitidos, default="todos"):
    """Acepta un valor de la lista o su etiqueta; cualquier otro vuelve a default."""
    texto = (valor or "").strip()
    if not texto or texto.lower() in ("todos", "todas"):
        return default
    if texto in permitidos:
        return texto
    for permitido in permitidos:
        if texto.lower() == str(permitido).lower():
            return permitido
    return default


def estado_pedido_filtro_valido(valor):
    texto = (valor or "").strip()
    if not texto or texto.lower() in ("todos", "todas"):
        return "todos"
    if texto in ESTADOS_PEDIDO:
        return texto
    for codigo, etiqueta in ESTADOS_PEDIDO.items():
        if texto.lower() == etiqueta.lower() or texto.lower() == codigo.lower():
            return codigo
    return "todos"


def leer_filtros_pedidos():
    estado = estado_pedido_filtro_valido(request.args.get("estado", "todos"))
    metodo = valor_filtro_whitelist(request.args.get("metodo", "todos"), METODOS_PAGO)
    pago = valor_filtro_whitelist(request.args.get("pago", "todos"), ESTADOS_PAGO_FILTRO)
    buscar = buscar_filtro_admin(request.args.get("q", ""))
    return {
        "filtro_estado": estado,
        "filtro_metodo": metodo,
        "filtro_pago": pago,
        "filtro_q": buscar,
        "hay_filtros": estado != "todos" or metodo != "todos" or pago != "todos" or bool(buscar),
    }


def campos_filtro_pedidos(filtros):
    estados = [{"id": "todos", "nombre": "Todos"}]
    for codigo, etiqueta in ESTADOS_PEDIDO.items():
        estados.append({"id": codigo, "nombre": etiqueta})
    metodos = [{"id": "todos", "nombre": "Todos"}]
    for metodo in METODOS_PAGO:
        metodos.append({"id": metodo, "nombre": metodo})
    pagos = [{"id": "todos", "nombre": "Todos"}]
    for estado in ESTADOS_PAGO_FILTRO:
        pagos.append({"id": estado, "nombre": estado})
    return [
        {
            "name": "estado",
            "label": "Estado del pedido",
            "valor": filtros["filtro_estado"],
            "opciones": estados,
        },
        {
            "name": "metodo",
            "label": "Método de pago",
            "valor": filtros["filtro_metodo"],
            "opciones": metodos,
        },
        {
            "name": "pago",
            "label": "Estado de pago",
            "valor": filtros["filtro_pago"],
            "opciones": pagos,
        },
    ]


def filtrar_pedidos_admin(pedidos, estado="todos", metodo="todos", pago="todos", buscar=""):
    """Filtro de lectura. No cambia pedidos, pagos ni stock."""
    estado = estado_pedido_filtro_valido(estado)
    metodo = valor_filtro_whitelist(metodo, METODOS_PAGO)
    pago = valor_filtro_whitelist(pago, ESTADOS_PAGO_FILTRO)
    buscar = buscar_filtro_admin(buscar)
    lista = list(pedidos)
    if estado != "todos":
        lista = [p for p in lista if p.get("estado") == estado]
    if metodo != "todos":
        lista = [p for p in lista if p.get("metodo_pago") == metodo]
    if pago != "todos":
        lista = [p for p in lista if p.get("estado_pago") == pago]
    if buscar:
        texto = sin_tildes(buscar)
        coincidencias = []
        for pedido in lista:
            numero = sin_tildes(str(pedido.get("numero") or ""))
            pedido_id = str(pedido.get("id") or "")
            estudiante = sin_tildes(str(pedido.get("estudiante") or ""))
            if texto in numero or texto in estudiante or texto == pedido_id:
                coincidencias.append(pedido)
        lista = coincidencias
    return lista


def leer_filtros_pqr():
    tipo = valor_filtro_whitelist(request.args.get("tipo", "todos"), TIPOS_PQR)
    estado = valor_filtro_whitelist(request.args.get("estado", "todos"), ESTADOS_PQR)
    buscar = buscar_filtro_admin(request.args.get("q", ""))
    return {
        "filtro_tipo": tipo,
        "filtro_estado": estado,
        "filtro_q": buscar,
        "hay_filtros": tipo != "todos" or estado != "todos" or bool(buscar),
    }


def campos_filtro_pqr(filtros):
    tipos = [{"id": "todos", "nombre": "Todos"}]
    for codigo in TIPOS_PQR:
        tipos.append({"id": codigo, "nombre": TIPOS_PQR_TEXTO.get(codigo, codigo)})
    estados = [{"id": "todos", "nombre": "Todos"}]
    for estado in ESTADOS_PQR:
        estados.append({"id": estado, "nombre": estado})
    return [
        {
            "name": "tipo",
            "label": "Tipo",
            "valor": filtros["filtro_tipo"],
            "opciones": tipos,
        },
        {
            "name": "estado",
            "label": "Estado",
            "valor": filtros["filtro_estado"],
            "opciones": estados,
        },
    ]


def filtrar_pqr_admin(pqrs, tipo="todos", estado="todos", buscar=""):
    """Filtro de lectura sobre PQR ya cargadas. No escribe en MySQL."""
    tipo = valor_filtro_whitelist(tipo, TIPOS_PQR)
    estado = valor_filtro_whitelist(estado, ESTADOS_PQR)
    buscar = buscar_filtro_admin(buscar)
    lista = list(pqrs)
    if tipo != "todos":
        lista = [item for item in lista if item.get("tipo") == tipo]
    if estado != "todos":
        lista = [item for item in lista if item.get("estado") == estado]
    if buscar:
        texto = sin_tildes(buscar)
        coincidencias = []
        for item in lista:
            campos = (
                str(item.get("id") or ""),
                item.get("estudiante") or "",
                item.get("documento") or "",
                item.get("asunto") or "",
                item.get("mensaje") or "",
            )
            if any(texto in sin_tildes(str(campo)) for campo in campos):
                coincidencias.append(item)
        lista = coincidencias
    return lista


def filtrar_productos_admin(categoria="todas", estado="todos", buscar=""):
    """Filtro de lectura sobre la caché PRODUCTOS. No escribe en MySQL ni cambia stock."""
    categoria = categoria_filtro_admin_valida(categoria)
    estado = estado_filtro_admin_valido(estado)
    buscar = buscar_filtro_admin(buscar)
    lista = list(PRODUCTOS)
    if buscar:
        texto = sin_tildes(buscar)
        lista = [p for p in lista if texto in sin_tildes(p.get("nombre", ""))]
    if categoria != "todas":
        lista = [p for p in lista if p.get("categoria") == categoria]
    if estado == "disponible":
        lista = [p for p in lista if p.get("cantidad", 0) > 0]
    elif estado == "agotado":
        lista = [p for p in lista if p.get("cantidad", 0) <= 0]
    return [preparar(p) for p in lista]


def filtrar_productos(buscar="", categoria="todos", orden="default"):
    """Aplica búsqueda, categoría y orden sobre productos de categorías públicas."""
    lista = [p for p in PRODUCTOS if p.get("categoria") in CATEGORIAS_FILTRO_PUBLICO]
    texto = sin_tildes((buscar or "").strip())
    categoria = categoria_catalogo_valida(categoria)
    orden = orden_catalogo_valido(orden)

    if texto:
        lista = [p for p in lista if texto in sin_tildes(p["busqueda"])]
    if categoria != "todos":
        lista = [p for p in lista if p["categoria"] == categoria]
    if orden == "precio-asc":
        lista.sort(key=lambda p: p["precio"])
    elif orden == "precio-desc":
        lista.sort(key=lambda p: p["precio"], reverse=True)
    elif orden == "nombre-asc":
        # sin_tildes ya pasa a minúsculas, así el alfabeto no depende de mayúsculas ni acentos.
        lista.sort(key=lambda p: sin_tildes(p["nombre"]))
    elif orden == "nombre-desc":
        lista.sort(key=lambda p: sin_tildes(p["nombre"]), reverse=True)
    return [preparar(p) for p in lista]


# Tarjetas que muestra la sección "Productos destacados" del catálogo.
MAX_DESTACADOS = 3


def ids_mas_comprados():
    """IDs de producto ordenados por unidades compradas, de mayor a menor.

    Solo cuentan los pedidos cuya venta tiene el pago confirmado, así el efectivo
    todavía por cobrar no suma. SQL fijo de solo lectura, sin datos del usuario.
    Ante un fallo de MySQL devuelve [] para no romper el catálogo.
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
                d.Det_Id_Producto AS id_producto,
                COALESCE(SUM(d.Det_Cantidad), 0) AS cantidad
            FROM tbl_detallepedido AS d
            INNER JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = d.Det_Id_Pedido
            INNER JOIN tbl_productos AS pr
                ON d.Det_Id_Producto = pr.Prod_Id_Producto
            WHERE v.Ven_Estado_Pago = 'Confirmado'
            GROUP BY d.Det_Id_Producto, pr.Prod_Nombre_Producto
            ORDER BY cantidad DESC, pr.Prod_Nombre_Producto ASC, d.Det_Id_Producto ASC
            """
        )
        for fila in cursor.fetchall():
            lista.append(int(fila["id_producto"]))
    except mysql.connector.Error as error:
        print("Error al consultar los productos más comprados:", error)
        return []
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lista


def obtener_destacados():
    """Los productos más comprados, como máximo MAX_DESTACADOS.

    Se resuelven contra PRODUCTOS, que ya deja fuera los dados de baja
    ('No disponible'); los agotados sí aparecen y la tarjeta los marca sola.
    """
    destacados = []
    for producto_id in ids_mas_comprados():
        producto = buscar_producto(producto_id)
        if producto is None:
            continue
        if producto.get("categoria") not in CATEGORIAS_FILTRO_PUBLICO:
            continue
        destacados.append(preparar(producto))
        if len(destacados) == MAX_DESTACADOS:
            break
    return destacados


# Turnos: números visibles (no confundir con Tur_Id_Turno de MySQL).
# turno_actual es el que muestra el indicador. Empieza en 1 aunque nadie haya pedido.
# ultimo_turno_asignado es el mayor número ya guardado. En 0 significa que tbl_turnos está vacía.
turno_actual = 1
ultimo_turno_asignado = 0
_lock_siguiente_turno = Lock()

MENSAJE_TURNO_YA_ACTUALIZADO = "El turno ya fue actualizado. Revisa el turno actual."
MENSAJE_TURNO_SIN_PENDIENTE = "No hay un turno pendiente para avanzar."
MENSAJE_TURNO_ERROR = "No se pudo actualizar el turno. Intenta de nuevo."


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
        ultimo_turno_asignado = max_asignado
        cursor.execute(
            """
            SELECT COALESCE(MAX(Tur_Numero_Turno), 0)
            FROM tbl_turnos
            WHERE Tur_Estado_Turno = 'Atendido'
            """
        )
        max_atendido = int(cursor.fetchone()[0] or 0)
        cursor.execute(
            """
            SELECT MIN(Tur_Numero_Turno)
            FROM tbl_turnos
            WHERE Tur_Estado_Turno = 'Pendiente'
            """
        )
        fila_pendiente = cursor.fetchone()
        min_pendiente = int(fila_pendiente[0]) if fila_pendiente and fila_pendiente[0] is not None else 0
        if min_pendiente > 0:
            turno_actual = min_pendiente
        elif max_atendido > 0:
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


def cargar_estado_operativo_desde_bd():
    """Lee tbl_config_operativa y restaura las variables operativas al arrancar Flask.

    Comportamiento seguro ante fallos:
    - Si la tabla no existe (error 1146): avisa y conserva los defaults de Python.
      No afirma que el estado está persistido.
    - Si MySQL está desconectado: avisa y conserva los defaults SIN habilitar pedidos
      de forma automática. sistema_habilitado queda en True (default) porque no se
      puede saber el estado real; el admin debe verificar al reconectar.
    - Si la extensión restaurada ya venció: limpiar_extension_vencida() la cancela
      en el primer request que evalúe el horario.
    """
    global sistema_habilitado, bloqueo_administrativo
    global extension_hasta, extension_jornada, extension_fecha, extension_autor
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM tbl_config_operativa WHERE conf_id = 1"
        )
        fila = cursor.fetchone()
        if fila is None:
            # La tabla existe pero está vacía: situación anómala; conservar defaults.
            print(
                "[CAFETIX] tbl_config_operativa está vacía. "
                "Usando valores por defecto (sistema habilitado, sin extensión)."
            )
            return
        sistema_habilitado = bool(fila["sistema_habilitado"])
        bloqueo_administrativo = bool(fila["bloqueo_admin"])
        # TIME en mysql-connector llega como datetime.timedelta; convertir a datetime.time.
        ext_hasta_raw = fila["extension_hasta"]
        if ext_hasta_raw is not None:
            if hasattr(ext_hasta_raw, "seconds"):
                # timedelta → time
                total = int(ext_hasta_raw.total_seconds())
                horas, resto = divmod(total, 3600)
                minutos, segundos = divmod(resto, 60)
                extension_hasta = time(horas % 24, minutos, segundos)
            else:
                # Ya es un datetime.time
                extension_hasta = ext_hasta_raw
        else:
            extension_hasta = None
        extension_jornada = fila["extension_jornada"]
        extension_fecha = fila["extension_fecha"]   # datetime.date o None
        extension_autor = fila["extension_autor"]
        print(
            "[CAFETIX] Estado operativo restaurado desde MySQL: "
            f"sistema_habilitado={sistema_habilitado}, "
            f"bloqueo_admin={bloqueo_administrativo}, "
            f"extension_hasta={extension_hasta}"
        )
    except mysql.connector.Error as error:
        if error.errno == 1146:  # Table doesn't exist
            print(
                "[CAFETIX] AVISO: tbl_config_operativa no existe en la base de datos. "
                "El estado operativo NO se persistirá entre reinicios. "
                "Importa el archivo cafetix_joaco.sql actualizado para habilitar la persistencia."
            )
        else:
            print(
                "[CAFETIX] No fue posible leer tbl_config_operativa:", error,
                "— Se usan los valores por defecto (sistema_habilitado=True, sin bloqueo, sin extensión)."
            )
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def guardar_estado_operativo_en_bd():
    """Persiste en MySQL el estado actual de las 6 variables operativas.

    Se llama después de cualquier cambio real en esas variables.
    Si MySQL falla, registra el error pero NO revierte el cambio en memoria:
    el sistema sigue operando con el estado correcto en RAM; el riesgo de
    discrepancia solo aparece si hay un reinicio antes de que MySQL vuelva.
    """
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_config_operativa
            SET sistema_habilitado = %s,
                bloqueo_admin      = %s,
                extension_hasta    = %s,
                extension_jornada  = %s,
                extension_fecha    = %s,
                extension_autor    = %s
            WHERE conf_id = 1
            """,
            (
                int(sistema_habilitado),
                int(bloqueo_administrativo),
                extension_hasta,    # datetime.time o None → MySQL TIME
                extension_jornada,  # str o None
                extension_fecha,    # datetime.date o None
                extension_autor,    # str o None
            ),
        )
        if cursor.rowcount == 0:
            # La fila conf_id=1 no existe: la tabla existe pero está vacía.
            print(
                "[CAFETIX] AVISO: No se encontró la fila de configuración en "
                "tbl_config_operativa (conf_id=1). El estado no se guardó. "
                "Importa el SQL actualizado."
            )
        else:
            conexion.commit()
    except mysql.connector.Error as error:
        if error.errno == 1146:
            print(
                "[CAFETIX] AVISO: tbl_config_operativa no existe. "
                "Importa cafetix_joaco.sql actualizado para persistencia completa."
            )
        else:
            print("[CAFETIX] No se pudo guardar el estado operativo en MySQL:", error)
        if conexion is not None:
            try:
                conexion.rollback()
            except Exception:
                pass
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def marcar_turno_atendido(numero_turno):
    """
    Marca un turno visible como Atendido en tbl_turnos.
    Devuelve 'ok' si se actualizó, 'ya_atendido' si ya estaba Atendido, 'inexistente' o 'error'.
    """
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
        if cursor.rowcount == 1:
            conexion.commit()
            return "ok"
        conexion.rollback()
        cursor.execute(
            "SELECT Tur_Estado_Turno FROM tbl_turnos WHERE Tur_Numero_Turno = %s",
            (numero_turno,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return "inexistente"
        if (fila[0] or "").strip().lower() == "atendido":
            return "ya_atendido"
        return "conflicto"
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al marcar turno atendido:", error)
        return "error"
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def obtener_proximo_turno_pendiente(numero_turno_referencia=0):
    """Retorna el menor Tur_Numero_Turno pendiente mayor al de referencia."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT MIN(Tur_Numero_Turno)
            FROM tbl_turnos
            WHERE Tur_Numero_Turno > %s
              AND Tur_Estado_Turno = 'Pendiente'
            """,
            (numero_turno_referencia,),
        )
        fila = cursor.fetchone()
        if fila and fila[0] is not None:
            return int(fila[0])
        return None
    except mysql.connector.Error as error:
        print("Error al consultar próximo turno pendiente:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def marcar_turno_de_pedido_atendido(pedido_id):
    """Marca como 'Atendido' en tbl_turnos el turno del pedido si no quedan más pedidos pendientes en ese turno."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT Ped_Id_Turno FROM tbl_pedidos WHERE Ped_Id_Pedido = %s",
            (pedido_id,),
        )
        fila = cursor.fetchone()
        if not fila or not fila[0]:
            return
        turno_id = fila[0]
        cursor.execute(
            """
            SELECT COUNT(*) FROM tbl_pedidos
            WHERE Ped_Id_Turno = %s
              AND LOWER(TRIM(Ped_Estado_Pedido)) != 'entregado'
            """,
            (turno_id,),
        )
        pendientes = cursor.fetchone()[0]
        if pendientes == 0:
            cursor.execute(
                """
                UPDATE tbl_turnos
                SET Tur_Estado_Turno = 'Atendido'
                WHERE Tur_Id_Turno = %s
                  AND Tur_Estado_Turno = 'Pendiente'
                """,
                (turno_id,),
            )
            conexion.commit()
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al sincronizar turno atendido desde pedido:", error)
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
                p.Ped_Fecha_Pedido,
                p.Ped_Estado_Pedido,
                p.Ped_Total_Pedido,
                p.Ped_Id_Turno,
                t.Tur_Numero_Turno,
                v.Ven_Metodo_Pago,
                v.Ven_Estado_Pago,
                u.Usu_Nombre,
                u.Usu_Apellido
            FROM tbl_pedidos AS p
            LEFT JOIN tbl_turnos AS t
                ON p.Ped_Id_Turno = t.Tur_Id_Turno
            LEFT JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = p.Ped_Id_Pedido
            LEFT JOIN tbl_usuarios AS u
                ON p.Ped_Id_Usuario = u.Usu_Id_Usuario
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
                    pr.Prod_Nombre_Producto,
                    c.Cat_Codigo
                FROM tbl_detallepedido AS d
                LEFT JOIN tbl_productos AS pr
                    ON d.Det_Id_Producto = pr.Prod_Id_Producto
                LEFT JOIN tbl_categorias AS c
                    ON pr.Prod_Id_Categoria = c.Cat_Id_Categoria
                WHERE d.Det_Id_Pedido = %s
                ORDER BY d.Det_Id_Detalle_Pedido ASC
                """,
                (pedido_id,),
            )
            lineas = []
            requiere_preparacion = False
            for det in cursor.fetchall():
                precio = int(det["Det_Precio_Unitario"] or 0)
                subtotal = int(det["Det_Subtotal"] or 0)
                cat_codigo = det.get("Cat_Codigo") or ""
                if producto_requiere_preparacion(cat_codigo):
                    requiere_preparacion = True
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
            estudiante = (
                (fila.get("Usu_Nombre") or "") + " " + (fila.get("Usu_Apellido") or "")
            ).strip()
            if not estudiante:
                estudiante = "Usuario no disponible"
            lista.append(
                {
                    "id": pedido_id,
                    "numero": "CJ-" + str(pedido_id).zfill(3),
                    "fecha": fila.get("Ped_Fecha_Pedido"),
                    "turno": numero_turno,
                    "turno_id": fila["Ped_Id_Turno"],
                    "estudiante": estudiante,
                    "productos": lineas,
                    "total": total,
                    "total_texto": precio_en_texto(total),
                    "estado": (fila["Ped_Estado_Pedido"] or "pendiente"),
                    "metodo_pago": fila["Ven_Metodo_Pago"] or "No registrado",
                    "estado_pago": fila["Ven_Estado_Pago"] or "No registrado",
                    "requiere_preparacion": requiere_preparacion,
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

# Extensión temporal del descanso o apertura extraordinaria. Se borra al reiniciar Flask.
EXTENSION_EXTRAORDINARIA = "extraordinaria"
extension_hasta = None
extension_jornada = None
extension_fecha = None

# Quién inició la apertura vigente. El Vendedor solo puede cancelar las suyas.
AUTOR_VENDEDOR = "vendedor"
AUTOR_ADMIN = "administrador"
extension_autor = None

# Control manual del administrador o el vendedor. Vuelve a True al reiniciar Flask.
sistema_habilitado = True

# Marca que el cierre manual lo hizo Administrador/Superadmin.
# Mientras esté en True el Vendedor no puede volver a habilitar. Se borra al reiniciar Flask.
bloqueo_administrativo = False

# Restaurar el estado operativo desde MySQL (sobreescribe los defaults de arriba si la tabla existe).
cargar_estado_operativo_desde_bd()

MENSAJE_CERRADO = "El sistema de pedidos y turnos está disponible únicamente durante los horarios de descanso."
MENSAJE_DESHABILITADO = "El sistema de pedidos está deshabilitado."
MENSAJE_PEDIDOS_CERRADOS = "Los pedidos están cerrados en este momento."
MENSAJE_LOGIN_CARRITO = "Debes iniciar sesión para agregar productos al carrito."
MENSAJE_TURNOS_CERRADOS = "Los turnos están disponibles durante los horarios de descanso."
MENSAJE_BLOQUEO_ADMIN = "Los turnos fueron deshabilitados por administración."
MENSAJE_FUERA_DE_HORARIO = (
    "El control manual quedó habilitado, pero los turnos siguen inactivos porque"
    " estamos fuera del horario de descanso. Usa la apertura temporal para abrir ahora."
)
MENSAJE_HORA_INVALIDA = (
    "La hora no es válida. Debe ser una hora posterior a la actual y del mismo día."
)
MENSAJE_SIN_APERTURA_VENDEDOR = (
    "No hay ninguna apertura temporal tuya vigente. Las aperturas de administración"
    " solo puede cancelarlas el Administrador."
)
MENSAJE_PAGO_EFECTIVO_OK = "Pago en efectivo confirmado."
MENSAJE_PAGO_TRANSFERENCIA_OK = "Transferencia con QR confirmada correctamente."


def tipo_aviso(texto):
    """Clasifica un aviso ya existente para el estilo visual. No cambia reglas."""
    t = (texto or "").strip()
    if not t:
        return "info"
    bajo = t.lower()
    if (
        "no se pudo" in bajo
        or "no pudimos" in bajo
        or "no se encontró" in bajo
        or "no se pueden" in bajo
        or "no es válida" in bajo
        or "no es válido" in bajo
        or "no se puede modificar" in bajo
        or "no se puede cambiar" in bajo
    ):
        return "error"
    exitos = (
        "cuenta creada",
        "el producto se quitó del carrito.",
        "pago en efectivo confirmado.",
        "el producto fue agregado.",
        "el producto fue actualizado.",
        "el producto fue desactivado.",
        "el horario fue extendido.",
        "la apertura extraordinaria quedó",
        "la extensión fue cancelada.",
        "la apertura temporal fue cancelada.",
        "el estado de la pqr fue actualizado.",
        "cliente desactivado correctamente.",
        "cliente activado correctamente.",
        "ya respondiste la encuesta",
        "tu pedido ya quedó registrado",
    )
    if any(bajo.startswith(marca) or marca in bajo for marca in exitos):
        return "exito"
    infos = (
        "no hay ",
        "no encontramos",
        "aún no ",
        "tu carrito está vacío",
        "el carrito está vacío",
        "no se encontraron",
    )
    if any(bajo.startswith(marca) or marca in bajo for marca in infos):
        return "info"
    avisos = (
        "debes ",
        "los pedidos están cerrados",
        "el sistema de pedidos",
        "los turnos",
        "podrás responder",
        "solo hay ",
        "está agotado",
        "confirma el pago",
        "fuera del horario",
        "cierre administrativo",
        "el pedido ya fue",
        "el turno ya fue",
        "la búsqueda puede",
    )
    if any(marca in bajo for marca in avisos):
        return "aviso"
    return "error"


app.jinja_env.globals["tipo_aviso"] = tipo_aviso
app.jinja_env.globals["src_imagen_producto"] = src_imagen_producto

def a_minutos(hora):
    """Convierte una hora a minutos para compararla más fácil."""
    return hora.hour * 60 + hora.minute


def obtener_hora_actual():
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


def limpiar_variables_extension():
    """Deja la extensión o apertura extraordinaria en estado vacío."""
    global extension_hasta, extension_jornada, extension_fecha, extension_autor
    extension_hasta = None
    extension_jornada = None
    extension_fecha = None
    extension_autor = None
    guardar_estado_operativo_en_bd()


def limpiar_extension_vencida(minutos_actuales):
    """Si ya pasó la hora de extensión, o cambió el día en apertura extraordinaria, se cancela sola."""
    if extension_hasta is None:
        return
    if extension_jornada == EXTENSION_EXTRAORDINARIA:
        if extension_fecha != datetime.now().date():
            limpiar_variables_extension()
            return
        if minutos_actuales > a_minutos(extension_hasta):
            limpiar_variables_extension()
        return
    if minutos_actuales > a_minutos(extension_hasta):
        limpiar_variables_extension()


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

    if (
        extension_jornada == EXTENSION_EXTRAORDINARIA
        and extension_hasta is not None
    ):
        texto_cierre = hora_en_texto(extension_hasta)
        return {
            "activo": True,
            "jornada": "Apertura extraordinaria",
            "jornada_corta": "Apertura extraordinaria",
            "horario_texto": "Apertura extraordinaria hasta " + texto_cierre,
            "cierre_normal": texto_cierre,
            "por_extension": True,
            "puede_extender": True,
        }

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


def accion_habilitar_util_admin():
    """El Administrador puede habilitar si eso cambia el interruptor o levanta el bloqueo."""
    return (not sistema_habilitado) or bloqueo_administrativo


def accion_deshabilitar_util_admin():
    """El Administrador puede deshabilitar si eso apaga el interruptor o marca el bloqueo.

    Permite el cierre preventivo: sirve aunque el estado efectivo ya sea inactivo.
    """
    return sistema_habilitado or (not bloqueo_administrativo)


def datos_carrito_flotante():
    """Datos para mostrar el carrito flotante del cliente."""
    cantidad = 0
    for item in obtener_carrito():
        cantidad = cantidad + item.get("cantidad", 0)
    es_cliente = rol_actual() == "cliente"
    return {
        "mostrar_carrito_flotante": es_cliente,
        "carrito_tiene_productos": cantidad > 0 and es_cliente,
        "carrito_cantidad": cantidad,
    }


def volver_al_panel():
    origen = request.form.get("origen", "")
    if origen == "vendedor":
        return redirect("/vendedor.html")
    return redirect("/administrador.html")


UMBRAL_BAJO_INVENTARIO = 5


def fecha_actual_consulta():
    return datetime.now().date()


def ventas_del_dia():
    """Suma Ven_Total_Venta de la fecha actual. 0 si no hay ventas."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(Ven_Total_Venta), 0)
            FROM tbl_ventas
            WHERE Ven_Fecha_Venta = %s
            """,
            (fecha_actual_consulta(),),
        )
        fila = cursor.fetchone()
        return int(fila[0] or 0)
    except mysql.connector.Error as error:
        print("Error al consultar ventas del día:", error)
        return 0
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def pedidos_del_dia():
    """Cuenta pedidos con Ped_Fecha_Pedido igual a hoy. 0 si no hay."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM tbl_pedidos
            WHERE Ped_Fecha_Pedido = %s
            """,
            (fecha_actual_consulta(),),
        )
        fila = cursor.fetchone()
        return int(fila[0] or 0)
    except mysql.connector.Error as error:
        print("Error al consultar pedidos del día:", error)
        return 0
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def pqr_del_dia():
    """Cuenta PQR cuya fecha corresponde al día actual."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM tbl_pqr
            WHERE DATE(Pqr_Fecha) = %s
            """,
            (fecha_actual_consulta(),),
        )
        fila = cursor.fetchone()
        return int(fila[0] or 0)
    except mysql.connector.Error as error:
        print("Error al consultar PQR del día:", error)
        return 0
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def producto_mas_pedido():
    """Producto con mayor suma de Det_Cantidad. Sin datos si no hay detalles."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT
                pr.Prod_Nombre_Producto,
                SUM(d.Det_Cantidad) AS total_cantidad
            FROM tbl_detallepedido AS d
            INNER JOIN tbl_productos AS pr
                ON d.Det_Id_Producto = pr.Prod_Id_Producto
            GROUP BY pr.Prod_Id_Producto, pr.Prod_Nombre_Producto
            ORDER BY total_cantidad DESC, pr.Prod_Id_Producto ASC
            LIMIT 1
            """
        )
        fila = cursor.fetchone()
        if not fila or not fila[0]:
            return "Sin datos"
        return fila[0]
    except mysql.connector.Error as error:
        print("Error al consultar producto más pedido:", error)
        return "Sin datos"
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def ventas_por_categoria():
    """Totales reales por categoría solo de pedidos con venta asociada."""
    lista = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                c.Cat_Nombre_Categoria AS categoria,
                COALESCE(SUM(d.Det_Cantidad), 0) AS cantidad,
                COALESCE(SUM(d.Det_Subtotal), 0) AS total
            FROM tbl_detallepedido AS d
            INNER JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = d.Det_Id_Pedido
            INNER JOIN tbl_productos AS pr
                ON d.Det_Id_Producto = pr.Prod_Id_Producto
            INNER JOIN tbl_categorias AS c
                ON pr.Prod_Id_Categoria = c.Cat_Id_Categoria
            GROUP BY c.Cat_Id_Categoria, c.Cat_Nombre_Categoria
            ORDER BY total DESC, c.Cat_Nombre_Categoria ASC
            """
        )
        for fila in cursor.fetchall():
            lista.append(
                {
                    "categoria": fila["categoria"] or "Sin categoría",
                    "cantidad": int(fila["cantidad"] or 0),
                    "total_texto": precio_en_texto(fila["total"] or 0),
                }
            )
    except mysql.connector.Error as error:
        print("Error al consultar ventas por categoría:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lista


def total_pedidos():
    """Cuenta todos los pedidos registrados."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM tbl_pedidos")
        fila = cursor.fetchone()
        return int(fila[0] or 0)
    except mysql.connector.Error as error:
        print("Error al consultar total de pedidos:", error)
        return 0
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def movimiento_productos_vendidos():
    """Productos con al menos una unidad en pedidos que tienen venta."""
    lista = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                pr.Prod_Id_Producto,
                pr.Prod_Nombre_Producto AS nombre,
                SUM(d.Det_Cantidad) AS cantidad
            FROM tbl_detallepedido AS d
            INNER JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = d.Det_Id_Pedido
            INNER JOIN tbl_productos AS pr
                ON d.Det_Id_Producto = pr.Prod_Id_Producto
            GROUP BY pr.Prod_Id_Producto, pr.Prod_Nombre_Producto
            ORDER BY cantidad DESC, pr.Prod_Id_Producto ASC
            """
        )
        for fila in cursor.fetchall():
            cantidad = int(fila["cantidad"] or 0)
            if cantidad < 1:
                continue
            lista.append(
                {
                    "nombre": fila["nombre"] or "Producto",
                    "cantidad": cantidad,
                }
            )
    except mysql.connector.Error as error:
        print("Error al consultar movimiento de productos vendidos:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lista


def resumen_movimiento_productos():
    """Deriva más/menos vendido y rankings desde una sola lista real."""
    movimiento = movimiento_productos_vendidos()
    if not movimiento:
        return {
            "mas_vendido": "Sin datos",
            "menos_vendido": "Sin datos",
            "ranking_superior": [],
            "ranking_inferior": [],
        }
    inferior = list(reversed(movimiento[-3:]))
    return {
        "mas_vendido": movimiento[0]["nombre"],
        "menos_vendido": movimiento[-1]["nombre"],
        "ranking_superior": movimiento[:3],
        "ranking_inferior": inferior,
    }


def lunes_viernes_semana_actual():
    hoy = fecha_actual_consulta()
    lunes = hoy - timedelta(days=hoy.weekday())
    viernes = lunes + timedelta(days=4)
    return lunes, viernes


def ventas_semana_actual():
    """Ventas lunes a viernes de la semana actual. Días sin ventas = 0."""
    lunes, viernes = lunes_viernes_semana_actual()
    nombres = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes")
    por_fecha = {}
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT Ven_Fecha_Venta, COALESCE(SUM(Ven_Total_Venta), 0)
            FROM tbl_ventas
            WHERE Ven_Fecha_Venta >= %s
              AND Ven_Fecha_Venta <= %s
            GROUP BY Ven_Fecha_Venta
            """,
            (lunes, viernes),
        )
        for fila in cursor.fetchall():
            fecha = fila[0]
            por_fecha[fecha] = int(fila[1] or 0)
    except mysql.connector.Error as error:
        print("Error al consultar ventas de la semana:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()

    dias = []
    for indice, nombre in enumerate(nombres):
        fecha = lunes + timedelta(days=indice)
        total = por_fecha.get(fecha, 0)
        dias.append(
            {
                "nombre": nombre,
                "total": total,
                "total_texto": precio_en_texto(total),
            }
        )
    mayor = 0
    for dia in dias:
        if dia["total"] > mayor:
            mayor = dia["total"]
    for dia in dias:
        if mayor == 0:
            dia["porcentaje"] = 0
            dia["es_maximo"] = False
        else:
            dia["porcentaje"] = int(round((dia["total"] / mayor) * 100))
            dia["es_maximo"] = dia["total"] == mayor
    return dias


def ventas_total_semana():
    """Suma Ven_Total_Venta de lunes a domingo de la semana actual."""
    hoy = fecha_actual_consulta()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(Ven_Total_Venta), 0)
            FROM tbl_ventas
            WHERE Ven_Fecha_Venta >= %s
              AND Ven_Fecha_Venta <= %s
            """,
            (lunes, domingo),
        )
        fila = cursor.fetchone()
        return int(fila[0] or 0)
    except mysql.connector.Error as error:
        print("Error al consultar ventas de la semana:", error)
        return 0
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def productos_vendidos_reporte():
    """Top de productos vendidos con cantidad y subtotal real. Solo con venta."""
    lista = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                pr.Prod_Nombre_Producto AS nombre,
                SUM(d.Det_Cantidad) AS cantidad,
                COALESCE(SUM(d.Det_Subtotal), 0) AS total
            FROM tbl_detallepedido AS d
            INNER JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = d.Det_Id_Pedido
            INNER JOIN tbl_productos AS pr
                ON d.Det_Id_Producto = pr.Prod_Id_Producto
            GROUP BY pr.Prod_Id_Producto, pr.Prod_Nombre_Producto
            ORDER BY cantidad DESC, pr.Prod_Id_Producto ASC
            LIMIT 5
            """
        )
        for fila in cursor.fetchall():
            lista.append(
                {
                    "nombre": fila["nombre"] or "Producto",
                    "cantidad": int(fila["cantidad"] or 0),
                    "total_texto": precio_en_texto(fila["total"] or 0),
                }
            )
    except mysql.connector.Error as error:
        print("Error al consultar productos vendidos:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lista


def unidades_vendidas():
    """Suma Det_Cantidad de líneas asociadas a una venta."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(d.Det_Cantidad), 0)
            FROM tbl_detallepedido AS d
            INNER JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = d.Det_Id_Pedido
            """
        )
        fila = cursor.fetchone()
        return int(fila[0] or 0)
    except mysql.connector.Error as error:
        print("Error al consultar unidades vendidas:", error)
        return 0
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def columna_costo_existe():
    """Verifica de forma segura en MySQL si la columna Prod_Costo existe en tbl_productos."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute("SHOW COLUMNS FROM tbl_productos LIKE 'Prod_Costo'")
        return cursor.fetchone() is not None
    except mysql.connector.Error:
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


NOMBRES_MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
)


def calcular_informe_utilidad(args=None):
    """Calcula ingresos, costo de productos vendidos, utilidad y margen para Día, Mes o Año.

    Solo incluye ventas válidas confirmadas (Ven_Estado_Pago = 'Confirmado').
    Si no existe la columna Prod_Costo o los costos están vacíos, no inventa datos
    ni muestra utilidades ficticias.
    """
    if args is None:
        args = {}
    tipo_periodo = (args.get("periodo_utilidad") or "dia").strip().lower()
    if tipo_periodo not in ("dia", "mes", "anio"):
        tipo_periodo = "dia"

    hoy = fecha_actual_consulta()
    fecha_filtro = (args.get("fecha_utilidad") or str(hoy)).strip()
    try:
        datetime.strptime(fecha_filtro, "%Y-%m-%d")
    except ValueError:
        fecha_filtro = str(hoy)

    mes_filtro_num = args.get("mes_utilidad")
    try:
        mes_filtro_int = int(mes_filtro_num) if mes_filtro_num else hoy.month
        if not (1 <= mes_filtro_int <= 12):
            mes_filtro_int = hoy.month
    except (ValueError, TypeError):
        mes_filtro_int = hoy.month

    anio_filtro_num = args.get("anio_utilidad")
    try:
        anio_filtro_int = int(anio_filtro_num) if anio_filtro_num else hoy.year
        if not (2020 <= anio_filtro_int <= 2035):
            anio_filtro_int = hoy.year
    except (ValueError, TypeError):
        anio_filtro_int = hoy.year

    if tipo_periodo == "dia":
        condicion_fecha = "v.Ven_Fecha_Venta = %s"
        params_fecha = [fecha_filtro]
        texto_periodo = f"Día: {fecha_filtro}"
    elif tipo_periodo == "mes":
        condicion_fecha = "MONTH(v.Ven_Fecha_Venta) = %s AND YEAR(v.Ven_Fecha_Venta) = %s"
        params_fecha = [mes_filtro_int, anio_filtro_int]
        nombre_mes = NOMBRES_MESES[mes_filtro_int - 1]
        texto_periodo = f"Mes: {nombre_mes} de {anio_filtro_int}"
    else:
        condicion_fecha = "YEAR(v.Ven_Fecha_Venta) = %s"
        params_fecha = [anio_filtro_int]
        texto_periodo = f"Año: {anio_filtro_int}"

    tiene_columna_costo = columna_costo_existe()

    if tiene_columna_costo:
        col_costo = "pr.Prod_Costo"
        group_costo = ", pr.Prod_Costo"
    else:
        col_costo = "NULL AS Prod_Costo"
        group_costo = ""

    sql = f"""
        SELECT
            pr.Prod_Id_Producto,
            pr.Prod_Nombre_Producto,
            pr.Prod_Precio,
            {col_costo},
            COALESCE(SUM(d.Det_Cantidad), 0) AS total_cantidad,
            COALESCE(SUM(d.Det_Subtotal), 0) AS total_ingresos
        FROM tbl_detallepedido AS d
        INNER JOIN tbl_ventas AS v
            ON v.Ven_Id_Pedido = d.Det_Id_Pedido
        INNER JOIN tbl_productos AS pr
            ON d.Det_Id_Producto = pr.Prod_Id_Producto
        WHERE v.Ven_Estado_Pago = 'Confirmado'
          AND {condicion_fecha}
        GROUP BY pr.Prod_Id_Producto, pr.Prod_Nombre_Producto, pr.Prod_Precio {group_costo}
        ORDER BY total_ingresos DESC, pr.Prod_Nombre_Producto ASC
    """

    lista_productos = []
    total_ingresos = 0
    total_costo = 0.0
    costos_disponibles = False
    costos_incompletos = False

    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(sql, tuple(params_fecha))
        for fila in cursor.fetchall():
            cantidad = int(fila["total_cantidad"] or 0)
            ingresos_prod = int(fila["total_ingresos"] or 0)
            precio_prod = int(fila["Prod_Precio"] or 0)
            costo_prod_raw = fila.get("Prod_Costo")
            total_ingresos += ingresos_prod

            if costo_prod_raw is not None:
                costo_u = float(costo_prod_raw)
                utilidad_u = float(precio_prod) - costo_u
                costo_total_prod = costo_u * cantidad
                utilidad_total_prod = float(ingresos_prod) - costo_total_prod
                margen_prod = (utilidad_total_prod / float(ingresos_prod) * 100.0) if ingresos_prod > 0 else 0.0
                total_costo += costo_total_prod
                costos_disponibles = True

                costo_u_texto = precio_en_texto(int(costo_u))
                utilidad_u_texto = precio_en_texto(int(utilidad_u))
                costo_tot_texto = precio_en_texto(int(costo_total_prod))
                utilidad_tot_texto = precio_en_texto(int(utilidad_total_prod))
                margen_prod_texto = f"{margen_prod:.1f} %"
            else:
                costos_incompletos = True
                costo_u_texto = "No asignado"
                utilidad_u_texto = "No disponible"
                costo_tot_texto = "No disponible"
                utilidad_tot_texto = "No disponible"
                margen_prod_texto = "No disponible"

            lista_productos.append(
                {
                    "id": fila["Prod_Id_Producto"],
                    "nombre": fila["Prod_Nombre_Producto"] or "Producto",
                    "cantidad": cantidad,
                    "precio_texto": precio_en_texto(precio_prod),
                    "costo_unitario_texto": costo_u_texto,
                    "utilidad_unitaria_texto": utilidad_u_texto,
                    "ingresos_texto": precio_en_texto(ingresos_prod),
                    "costo_total_texto": costo_tot_texto,
                    "utilidad_total_texto": utilidad_tot_texto,
                    "margen_texto": margen_prod_texto,
                    "tiene_costo": costo_prod_raw is not None,
                }
            )
    except mysql.connector.Error as error:
        print("Error al calcular informe de utilidad:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()

    if len(lista_productos) == 0:
        costo_total_texto = precio_en_texto(0)
        utilidad_total_texto = precio_en_texto(0)
        margen_utilidad_texto = "No disponible"
    elif costos_disponibles and not costos_incompletos:
        utilidad_total_num = float(total_ingresos) - total_costo
        if total_ingresos > 0:
            margen_num = (utilidad_total_num / float(total_ingresos)) * 100.0
            margen_utilidad_texto = f"{margen_num:.1f} %"
        else:
            margen_utilidad_texto = "No disponible"
        costo_total_texto = precio_en_texto(int(total_costo))
        utilidad_total_texto = precio_en_texto(int(utilidad_total_num))
    elif costos_disponibles and costos_incompletos:
        costo_total_texto = "Incompleto (faltan costos)"
        utilidad_total_texto = "No disponible"
        margen_utilidad_texto = "No disponible"
    else:
        costo_total_texto = "No registrado en BD"
        utilidad_total_texto = "No disponible"
        margen_utilidad_texto = "No disponible"

    productos_sin_costo = [p["nombre"] for p in lista_productos if not p["tiene_costo"]]

    return {
        "tipo_periodo": tipo_periodo,
        "fecha_filtro": fecha_filtro,
        "mes_filtro": mes_filtro_int,
        "anio_filtro": anio_filtro_int,
        "texto_periodo": texto_periodo,
        "ingresos_texto": precio_en_texto(total_ingresos),
        "ingresos_valor": total_ingresos,
        "costo_total_texto": costo_total_texto,
        "utilidad_total_texto": utilidad_total_texto,
        "margen_utilidad_texto": margen_utilidad_texto,
        "tiene_columna_costo": tiene_columna_costo,
        "costos_disponibles": costos_disponibles,
        "costos_incompletos": costos_incompletos,
        "productos_sin_costo": productos_sin_costo,
        "productos": lista_productos,
        "hay_ventas": len(lista_productos) > 0,
        "meses_opciones": [
            {"numero": i + 1, "nombre": NOMBRES_MESES[i]} for i in range(12)
        ],
        "anios_opciones": [2024, 2025, 2026, 2027],
    }


def datos_dashboard_superadmin():
    movimiento = resumen_movimiento_productos()
    datos = datos_sesion()
    datos.update(
        {
            "ventas_dia_texto": precio_en_texto(ventas_del_dia()),
            "total_pedidos": total_pedidos(),
            "producto_mas_vendido": movimiento["mas_vendido"],
            "producto_menos_vendido": movimiento["menos_vendido"],
            "ranking_superior": movimiento["ranking_superior"],
            "ranking_inferior": movimiento["ranking_inferior"],
            "ventas_semana": ventas_semana_actual(),
        }
    )
    return datos


def cargar_usuarios_con_roles():
    """Lista usuarios reales con su rol. No incluye contraseña ni hash."""
    lista = []
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
                u.Usu_Documento,
                u.Usu_Estado,
                r.Rol_Nombre_Rol
            FROM tbl_usuarios AS u
            LEFT JOIN tbl_roles AS r
                ON u.Usu_Id_Rol = r.Rol_Id_Rol
            ORDER BY r.Rol_Nombre_Rol ASC, u.Usu_Nombre ASC, u.Usu_Id_Usuario ASC
            """
        )
        for fila in cursor.fetchall():
            nombre = (fila.get("Usu_Nombre") or "").strip()
            apellido = (fila.get("Usu_Apellido") or "").strip()
            if apellido:
                nombre_completo = (nombre + " " + apellido).strip()
            else:
                nombre_completo = nombre
            if not nombre_completo:
                nombre_completo = "Usuario no disponible"
            documento = (fila.get("Usu_Documento") or "").strip()
            estado = (fila.get("Usu_Estado") or "").strip()
            lista.append(
                {
                    "id": int(fila["Usu_Id_Usuario"]),
                    "nombre": nombre_completo,
                    "usuario": fila.get("Usu_Usuario") or "—",
                    "documento": documento or "—",
                    "documento_busqueda": documento,
                    "rol": fila.get("Rol_Nombre_Rol") or "Sin rol",
                    "estado": estado or "—",
                }
            )
    except mysql.connector.Error as error:
        print("Error al cargar usuarios:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lista


def conteos_usuarios_por_rol(lista):
    conteos = {
        "total": len(lista),
        "cliente": 0,
        "vendedor": 0,
        "administrador": 0,
        "superadmin": 0,
    }
    for item in lista:
        rol = (item.get("rol") or "").strip()
        if rol in conteos:
            conteos[rol] += 1
    return conteos


ROLES_USUARIO_FILTRO = ("cliente", "vendedor", "administrador", "superadmin")
ROLES_USUARIO_TEXTO = {
    "cliente": "Cliente",
    "vendedor": "Vendedor",
    "administrador": "Administrador",
    "superadmin": "Superadmin",
}
ESTADOS_USUARIO_FILTRO = ("Activo", "Inactivo")


def leer_filtros_usuarios():
    rol = valor_filtro_whitelist(request.args.get("rol", "todos"), ROLES_USUARIO_FILTRO)
    estado = valor_filtro_whitelist(request.args.get("estado", "todos"), ESTADOS_USUARIO_FILTRO)
    buscar = buscar_filtro_admin(request.args.get("q", ""))
    return {
        "filtro_rol": rol,
        "filtro_estado": estado,
        "filtro_q": buscar,
        "hay_filtros": rol != "todos" or estado != "todos" or bool(buscar),
    }


def campos_filtro_usuarios(filtros):
    roles = [{"id": "todos", "nombre": "Todos"}]
    for codigo in ROLES_USUARIO_FILTRO:
        roles.append({"id": codigo, "nombre": ROLES_USUARIO_TEXTO[codigo]})
    estados = [{"id": "todos", "nombre": "Todos"}]
    for estado in ESTADOS_USUARIO_FILTRO:
        estados.append({"id": estado, "nombre": estado})
    return [
        {
            "name": "rol",
            "label": "Rol",
            "valor": filtros["filtro_rol"],
            "opciones": roles,
        },
        {
            "name": "estado",
            "label": "Estado",
            "valor": filtros["filtro_estado"],
            "opciones": estados,
        },
    ]


def filtrar_usuarios_admin(usuarios, rol="todos", estado="todos", buscar=""):
    """Filtro de lectura. No escribe en MySQL ni cambia usuarios."""
    rol = valor_filtro_whitelist(rol, ROLES_USUARIO_FILTRO)
    estado = valor_filtro_whitelist(estado, ESTADOS_USUARIO_FILTRO)
    buscar = buscar_filtro_admin(buscar)
    lista = list(usuarios)
    if rol != "todos":
        lista = [item for item in lista if item.get("rol") == rol]
    if estado != "todos":
        lista = [item for item in lista if item.get("estado") == estado]
    if buscar:
        texto = sin_tildes(buscar)
        coincidencias = []
        for item in lista:
            campos = (
                item.get("nombre") or "",
                item.get("usuario") or "",
                item.get("documento_busqueda") or "",
            )
            if any(texto in sin_tildes(str(campo)) for campo in campos):
                coincidencias.append(item)
        lista = coincidencias
    return lista


def datos_panel_usuarios_superadmin():
    lista = cargar_usuarios_con_roles()
    filtros = leer_filtros_usuarios()
    datos = datos_sesion()
    datos.update(
        {
            "usuarios": filtrar_usuarios_admin(
                lista,
                filtros["filtro_rol"],
                filtros["filtro_estado"],
                filtros["filtro_q"],
            ),
            "conteos_usuarios": conteos_usuarios_por_rol(lista),
            "filtro_accion": "superadmin-usuarios.html",
            "filtros_campos": campos_filtro_usuarios(filtros),
            "filtro_buscar_label": "Buscar usuario",
            "filtro_buscar_placeholder": "Nombre, usuario o documento",
            "aviso": request.args.get("aviso", ""),
        }
    )
    datos.update(filtros)
    return datos


MENSAJE_CLIENTE_DESACTIVADO = "Cliente desactivado correctamente."
MENSAJE_CLIENTE_ACTIVADO = "Cliente activado correctamente."
MENSAJE_USUARIO_INTERNO_ESTADO = "No se puede modificar el estado de un usuario interno."
MENSAJE_USUARIO_NO_ENCONTRADO = "No se encontró el usuario."
MENSAJE_ESTADO_USUARIO_INVALIDO = "El estado del usuario no se puede cambiar."


def consultar_rol_y_estado_usuario(usuario_id):
    """Lee rol y estado reales. No incluye contraseña ni documento."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.Usu_Id_Usuario AS id,
                u.Usu_Estado AS estado,
                r.Rol_Nombre_Rol AS rol
            FROM tbl_usuarios AS u
            LEFT JOIN tbl_roles AS r
                ON u.Usu_Id_Rol = r.Rol_Id_Rol
            WHERE u.Usu_Id_Usuario = %s
            """,
            (usuario_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return {
            "id": int(fila["id"]),
            "estado": (fila.get("estado") or "").strip(),
            "rol": (fila.get("rol") or "").strip(),
        }
    except mysql.connector.Error as error:
        print("Error al consultar rol y estado del usuario:", error)
        return None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def actualizar_estado_cliente_bd(usuario_id, nuevo_estado):
    """UPDATE de Usu_Estado solo si el usuario es cliente. No toca otros campos."""
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_usuarios AS u
            INNER JOIN tbl_roles AS r
                ON u.Usu_Id_Rol = r.Rol_Id_Rol
            SET u.Usu_Estado = %s
            WHERE u.Usu_Id_Usuario = %s
              AND r.Rol_Nombre_Rol = %s
            """,
            (nuevo_estado, usuario_id, "cliente"),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return False
        conexion.commit()
        return True
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al actualizar el estado del cliente:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


CUENTA_ACTIVA = "activa"
CUENTA_INACTIVA = "inactiva"
CUENTA_INEXISTENTE = "inexistente"
CUENTA_ERROR_BD = "error_bd"

MENSAJE_CUENTA_INACTIVA = "Tu cuenta no está activa."
MENSAJE_SESION_INVALIDA = "Tu sesión ya no es válida. Inicia sesión de nuevo."
MENSAJE_VERIFICAR_CUENTA = "No pudimos verificar tu cuenta en este momento. Intenta nuevamente."


def clasificar_estado_usuario(usuario_id):
    """
    Distingue Activo, Inactivo, usuario inexistente y fallo real de MySQL.
    No interpreta un error de BD como cuenta inactiva.
    """
    if usuario_id is None:
        return CUENTA_INEXISTENTE
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT Usu_Estado FROM tbl_usuarios WHERE Usu_Id_Usuario = %s",
            (usuario_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return CUENTA_INEXISTENTE
        if (fila[0] or "").strip() == "Activo":
            return CUENTA_ACTIVA
        return CUENTA_INACTIVA
    except mysql.connector.Error as error:
        print("Error al verificar estado del usuario:", error)
        return CUENTA_ERROR_BD
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def estado_usuario_en_bd(usuario_id):
    """Estado persistido. None si no existe. False si MySQL no respondió."""
    clase = clasificar_estado_usuario(usuario_id)
    if clase == CUENTA_ERROR_BD:
        return False
    if clase == CUENTA_INEXISTENTE:
        return None
    if clase == CUENTA_ACTIVA:
        return "Activo"
    return "Inactivo"


def redirigir_si_cuenta_no_activa(destino_si_bd_falla=None):
    """Cierra la sesión solo si MySQL confirma Inactivo o usuario inexistente."""
    if not usuario_id_actual():
        return None
    clase = clasificar_estado_usuario(usuario_id_actual())
    if clase == CUENTA_ACTIVA:
        return None
    if clase == CUENTA_ERROR_BD:
        if destino_si_bd_falla:
            return redirect(url_interna_con_aviso(destino_si_bd_falla, MENSAJE_VERIFICAR_CUENTA))
        return None
    session.clear()
    if clase == CUENTA_INEXISTENTE:
        return redirect("/login.html?aviso=" + quote(MENSAJE_SESION_INVALIDA))
    return redirect("/login.html?aviso=" + quote(MENSAJE_CUENTA_INACTIVA))


def redirigir_si_cliente_desactivado(destino_si_bd_falla=None):
    """6J en páginas públicas: solo revalida si la sesión es de cliente."""
    if rol_actual() != "cliente" or not usuario_id_actual():
        return None
    return redirigir_si_cuenta_no_activa(destino_si_bd_falla)


def destino_verificacion_cuenta(pagina):
    """POST vuelve al panel. GET protegido usa index para no ciclar si MySQL sigue caído."""
    if request.method != "POST":
        return "/index.html"
    destinos = {
        "vendedor": "/vendedor.html",
        "administrador": "/administrador.html",
        "admin-productos": "/admin-productos.html",
        "admin-eliminar": "/admin-eliminar.html",
        "admin-inventarios": "/admin-inventarios.html",
        "admin-pedidos": "/admin-pedidos.html",
        "admin-reportes": "/admin-reportes.html",
        "admin-pqr": "/admin-pqr.html",
        "superadmin": "/superadmin.html",
        "superadmin-productos": "/superadmin-productos.html",
        "superadmin-usuarios": "/superadmin-usuarios.html",
        "superadmin-reportes": "/superadmin-reportes.html",
        "superadmin-pqr": "/superadmin-pqr.html",
    }
    return destinos.get(pagina, "/index.html")


def url_superadmin_usuarios(aviso=""):
    """Vuelve al listado conservando filtros GET ya validados."""
    rol = valor_filtro_whitelist(
        request.form.get("volver_rol", request.args.get("rol", "todos")),
        ROLES_USUARIO_FILTRO,
    )
    estado = valor_filtro_whitelist(
        request.form.get("volver_estado", request.args.get("estado", "todos")),
        ESTADOS_USUARIO_FILTRO,
    )
    buscar = buscar_filtro_admin(
        request.form.get("volver_q", request.args.get("q", ""))
    )
    partes = []
    if rol != "todos":
        partes.append("rol=" + quote(rol))
    if estado != "todos":
        partes.append("estado=" + quote(estado))
    if buscar:
        partes.append("q=" + quote(buscar))
    if aviso:
        partes.append("aviso=" + quote(aviso))
    if not partes:
        return "/superadmin-usuarios.html"
    return "/superadmin-usuarios.html?" + "&".join(partes)


def productos_disponibles_activos():
    """Misma base que catálogo/admin: PRODUCTOS activos con stock > 0."""
    total = 0
    for producto in PRODUCTOS:
        if int(producto.get("cantidad") or 0) > 0:
            total += 1
    return total


def alertas_bajo_inventario():
    """Productos activos con stock > 0 y <= umbral, de menor a mayor."""
    lista = []
    for producto in PRODUCTOS:
        cantidad = int(producto.get("cantidad") or 0)
        if cantidad > 0 and cantidad <= UMBRAL_BAJO_INVENTARIO:
            lista.append(
                {
                    "nombre": producto.get("nombre") or "Producto",
                    "cantidad": cantidad,
                }
            )
    lista.sort(key=lambda item: (item["cantidad"], item["nombre"]))
    return lista


def datos_pagina_admin(aviso=""):
    """Datos para la sección de horario del administrador."""
    estado = estado_descanso()
    hora_guardada = ""
    texto_extension = ""
    if extension_hasta is not None:
        hora_guardada = f"{extension_hasta.hour:02d}:{extension_hasta.minute:02d}"
        texto_extension = hora_en_texto(extension_hasta)
    alertas = alertas_bajo_inventario()
    pedidos_abiertos = sistema_pedidos_activo()
    extraordinaria = estado.get("jornada_corta") == "Apertura extraordinaria"
    if not sistema_habilitado:
        pedidos_causa_texto = "Los pedidos están cerrados por el control general."
    elif pedidos_abiertos and extraordinaria:
        pedidos_causa_texto = "Los pedidos están disponibles mediante una apertura extraordinaria."
    elif pedidos_abiertos:
        pedidos_causa_texto = "Los pedidos están disponibles en la franja de descanso actual."
    else:
        pedidos_causa_texto = (
            "Los pedidos están cerrados porque actualmente estás fuera de una franja de descanso."
        )
    if sistema_habilitado:
        control_general_ayuda = (
            "Permite que los pedidos se activen automáticamente durante las franjas habilitadas."
        )
    else:
        control_general_ayuda = (
            "Impide que los pedidos se activen, incluso durante una franja de descanso."
        )
    return {
        "horario_activo": estado["activo"],
        "sistema_activo": sistema_habilitado,
        "sistema_habilitado": sistema_habilitado,
        # Estado efectivo (horario + interruptor manual): es el que se muestra en pantalla.
        "sistema_pedidos_activo": pedidos_abiertos,
        # Control general: el Administrador lo maneja aparte del estado efectivo para
        # poder hacer un cierre preventivo aunque ahora mismo ya esté todo inactivo.
        "control_manual_texto": "Habilitado" if sistema_habilitado else "Deshabilitado",
        "pedidos_estado_texto": "ABIERTOS" if pedidos_abiertos else "CERRADOS",
        "control_general_texto": "HABILITADO" if sistema_habilitado else "DESHABILITADO",
        "pedidos_causa_texto": pedidos_causa_texto,
        "control_general_ayuda": control_general_ayuda,
        "bloqueo_administrativo": bloqueo_administrativo,
        "puede_habilitar": accion_habilitar_util_admin(),
        "puede_deshabilitar": accion_deshabilitar_util_admin(),
        "jornada_corta": estado["jornada_corta"] or "Ninguno",
        "cierre_normal": estado["cierre_normal"] or "—",
        "puede_extender": estado["puede_extender"],
        "por_extension": estado["por_extension"],
        "hora_extension_valor": hora_guardada,
        "extension_texto": texto_extension,
        "aviso_horario": aviso,
        "turno_actual": turno_actual,
        "sesion_iniciada": usuario_logueado(),
        "rol": rol_actual(),
        "nombre_usuario": session.get("nombre_usuario", ""),
        "pagina_actual": pagina_menu(),
        "ventas_dia_texto": precio_en_texto(ventas_del_dia()),
        "productos_disponibles": productos_disponibles_activos(),
        "productos_bajo_inventario": len(alertas),
        "pedidos_dia": pedidos_del_dia(),
        "alertas_inventario": alertas,
        "csrf_token": obtener_token_csrf(),
    }


def descanso_en_curso():
    """Devuelve la jornada que está ocurriendo ahora, o None."""
    estado = estado_descanso()
    if not estado["activo"]:
        return None
    return buscar_jornada(estado["jornada"])


def aplicar_extension_horario(texto_hora, autor):
    """Valida la hora y aplica extensión del descanso o apertura extraordinaria.

    La usan el Administrador (/extender-horario) y el Vendedor (/abrir-turnos-temporal),
    así la validación de la hora vive en un solo lugar. El autor queda guardado para
    saber después quién puede cancelarla.
    Devuelve "ok", "ok-extraordinaria" o "invalida". Solo toca las variables de extensión.
    """
    global extension_hasta, extension_jornada, extension_fecha, extension_autor
    nueva = texto_a_hora(texto_hora)
    if nueva is None:
        return "invalida"
    minutos_nueva = a_minutos(nueva)
    # Al comparar minutos del mismo día, una hora posterior a la actual nunca cruza medianoche.
    if minutos_nueva <= a_minutos(obtener_hora_actual()):
        return "invalida"
    jornada = descanso_en_curso()
    if jornada is None:
        extension_hasta = nueva
        extension_jornada = EXTENSION_EXTRAORDINARIA
        extension_fecha = datetime.now().date()
        extension_autor = autor
        guardar_estado_operativo_en_bd()
        return "ok-extraordinaria"
    if minutos_nueva <= a_minutos(jornada["fin"]):
        return "invalida"
    siguiente = jornada_siguiente(jornada)
    if siguiente and minutos_nueva >= a_minutos(siguiente["inicio"]):
        return "invalida"
    extension_hasta = nueva
    extension_jornada = jornada["nombre"]
    extension_fecha = None
    extension_autor = autor
    guardar_estado_operativo_en_bd()
    return "ok"


def apertura_vendedor_vigente():
    """True si sigue viva una apertura temporal iniciada por el Vendedor.

    Consulta estado_descanso() primero para que una apertura ya vencida se limpie sola
    y no se ofrezca cancelar algo que ya expiró.
    """
    estado_descanso()
    return extension_hasta is not None and extension_autor == AUTOR_VENDEDOR


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


MENSAJE_CSRF = "La solicitud no es válida. Vuelve a intentar."
MENSAJE_TOKEN_COMPRA = "No se pudo confirmar el pago. Vuelve a abrir el pago e inténtalo de nuevo."
MENSAJE_COMPRA_YA_REGISTRADA = "Tu pedido ya quedó registrado. Revisa tu turno."

# Tokens de compra ya usados en ESTE proceso. No sustituye una tabla MySQL:
# otro worker o un reinicio no comparte este conjunto.
_tokens_compra_usados = set()
_locks_compra_usuario = {}
_locks_compra_guarda = Lock()


def _lock_compra_usuario(usuario_id):
    """Serializa confirmar-pago del mismo cliente en este proceso."""
    clave = int(usuario_id)
    with _locks_compra_guarda:
        candado = _locks_compra_usuario.get(clave)
        if candado is None:
            candado = Lock()
            _locks_compra_usuario[clave] = candado
        return candado


def obtener_token_compra():
    """Token de un solo uso para la intención de pago. No reemplaza CSRF."""
    token = session.get("token_compra")
    if token and token not in _tokens_compra_usados:
        return token
    token = secrets.token_urlsafe(32)
    session["token_compra"] = token
    session.modified = True
    return token


def token_compra_ya_usado(token):
    if not token:
        return False
    if token in _tokens_compra_usados:
        return True
    return session.get("token_compra_usado") == token


def marcar_token_compra_usado(token):
    """Consume el token solo después de una compra persistida."""
    if token:
        _tokens_compra_usados.add(token)
        session["token_compra_usado"] = token
    session.pop("token_compra", None)
    session.modified = True


def verificar_token_compra():
    """Compara el token del formulario con el de la intención actual."""
    enviado = request.form.get("token_compra", "")
    esperado = session.get("token_compra", "")
    if not enviado or not esperado:
        return False
    if enviado in _tokens_compra_usados:
        return False
    return secrets.compare_digest(str(enviado), str(esperado))


def url_interna_con_aviso(destino, aviso):
    """Agrega aviso a una ruta interna sin romper query existente. No abre sitios externos."""
    destino = (destino or "").strip()
    if not destino.startswith("/") or destino.startswith("//"):
        destino = "/index.html"
    partes = urlsplit(destino)
    if partes.scheme or partes.netloc:
        partes = urlsplit("/index.html")
    params = [(clave, valor) for clave, valor in parse_qsl(partes.query, keep_blank_values=True) if clave != "aviso"]
    params.append(("aviso", aviso))
    return urlunsplit(("", "", partes.path or "/index.html", urlencode(params), partes.fragment))


def redirigir_si_csrf_invalido(destino):
    """Detiene el POST si el token CSRF falta o no coincide. No modifica datos."""
    if verificar_token_csrf():
        return None
    return redirect(url_interna_con_aviso(destino, MENSAJE_CSRF))


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
        "sistema_pedidos_activo": sistema_pedidos_activo(),
        "nombre_usuario": session.get("nombre_usuario", ""),
        "csrf_token": obtener_token_csrf(),
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
        raise
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


def existe_documento_usuario(documento):
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT Usu_Id_Usuario FROM tbl_usuarios WHERE Usu_Documento = %s",
            (documento,),
        )
        return cursor.fetchone() is not None
    except mysql.connector.Error as error:
        print("Error al verificar documento:", error)
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
    """Valida el documento del cliente. Se guarda como texto, no como número."""
    if not documento or not str(documento).strip():
        return "Escribe tu documento."
    texto = str(documento)
    if not all(c in "0123456789" for c in texto):
        return "El documento solo debe contener números."
    if len(texto) > 10:
        return "El documento debe tener máximo 10 números."
    if len(texto) < 5:
        return "El documento debe tener al menos 5 dígitos."
    return None


def validar_contrasena_registro(contrasena, confirmar_contrasena):
    """Reglas de contraseña del registro. Flask es la fuente de seguridad."""
    if contrasena is None or contrasena == "":
        return "Crea una contraseña."
    if len(contrasena) < 8:
        return "La contraseña debe tener mínimo 8 caracteres."
    if len(contrasena) > 20:
        return "La contraseña no puede superar los 20 caracteres."
    if not any(c.isupper() for c in contrasena):
        return "La contraseña debe incluir al menos una letra mayúscula."
    if not any(c.islower() for c in contrasena):
        return "La contraseña debe incluir al menos una letra minúscula."
    if not any(c.isdigit() for c in contrasena):
        return "La contraseña debe incluir al menos un número."
    # Cualquier carácter que no sea letra ni número cuenta como símbolo.
    if not any(not c.isalnum() for c in contrasena):
        return "La contraseña debe incluir al menos un símbolo."
    if confirmar_contrasena is None or confirmar_contrasena == "":
        return "Confirma tu contraseña."
    if contrasena != confirmar_contrasena:
        return "Las contraseñas no coinciden."
    return None


def validar_registro_entrada(nombre, apellido, usuario, contrasena, confirmar_contrasena):
    """Validaciones de registro de cliente."""
    nombre_texto = (nombre or "").strip()
    if not nombre_texto:
        return "Escribe tu nombre."
    if len(nombre_texto) > 70:
        return "El nombre no puede superar 70 caracteres."
    apellido_texto = (apellido or "").strip()
    if not apellido_texto:
        return "Escribe tu apellido."
    if len(apellido_texto) > 70:
        return "El apellido no puede superar 70 caracteres."
    usuario_texto = (usuario or "").strip()
    if not usuario_texto:
        return "Elige un nombre de usuario."
    if len(usuario_texto) > 70:
        return "El usuario no puede superar 70 caracteres."
    if len(usuario_texto) < 3:
        return "El usuario debe tener al menos 3 caracteres."
    return validar_contrasena_registro(contrasena, confirmar_contrasena)


def iniciar_sesion_usuario(usuario_id, usuario, nombre, rol):
    """Guarda la identidad nueva. Si cambia de usuario, limpia datos ajenos.

    No se llama si el login falló: así una contraseña incorrecta no destruye
    la sesión válida que ya existía.
    """
    usuario_id = int(usuario_id)
    anterior_id = None
    if session.get("sesion_iniciada"):
        try:
            anterior_id = int(session.get("usuario_id") or 0) or None
        except (TypeError, ValueError):
            anterior_id = None
    if anterior_id is not None and anterior_id != usuario_id:
        session.clear()
    session["sesion_iniciada"] = True
    session["usuario_id"] = usuario_id
    session["usuario"] = usuario
    session["nombre"] = nombre
    session["nombre_usuario"] = nombre
    session["rol"] = rol
    obtener_token_csrf()


def destino_por_rol(rol):
    destinos = {
        "cliente": "/index.html",
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
    if pagina in ("carrito", "pago", "turno", "pqr", "encuesta", "gracias", "pqr-gracias", "mis-compras"):
        if rol != "cliente" or not usuario_id_actual():
            return redirect("/login.html")
        destino_bd = None
        if request.method == "POST":
            destinos_post = {
                "carrito": "/carrito.html",
                "pago": "/pago.html",
                "turno": "/turno.html",
                "pqr": "/pqr.html",
                "pqr-gracias": "/pqr.html",
                "encuesta": "/encuesta.html",
                "gracias": "/gracias.html",
                "mis-compras": "/mis-compras.html",
            }
            destino_bd = destinos_post.get(pagina)
        bloqueo_inactivo = redirigir_si_cliente_desactivado(destino_bd)
        if bloqueo_inactivo:
            return bloqueo_inactivo
        return None
    if pagina == "vendedor":
        if rol != "vendedor" or not usuario_id_actual():
            return redirect("/login.html")
        return redirigir_si_cuenta_no_activa(destino_verificacion_cuenta(pagina))
    if pagina == "administrador" or pagina.startswith("admin-"):
        if rol not in ("administrador", "superadmin") or not usuario_id_actual():
            return redirect("/login.html")
        return redirigir_si_cuenta_no_activa(destino_verificacion_cuenta(pagina))
    if pagina.startswith("superadmin"):
        if rol != "superadmin" or not usuario_id_actual():
            return redirect("/login.html")
        return redirigir_si_cuenta_no_activa(destino_verificacion_cuenta(pagina))
    return None


def consultar_pedido_activo_cliente(usuario_id):
    """SELECT del pedido activo más reciente del Cliente. No escribe en MySQL."""
    if usuario_id is None:
        return None
    try:
        cache = getattr(g, "_pedido_activo_cliente", None)
        if cache is not None and cache.get("usuario_id") == int(usuario_id):
            return cache.get("fila")
    except RuntimeError:
        cache = None
    conexion = None
    cursor = None
    fila = None
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
                t.Tur_Id_Turno,
                t.Tur_Numero_Turno,
                v.Ven_Metodo_Pago,
                v.Ven_Estado_Pago
            FROM tbl_pedidos AS p
            INNER JOIN tbl_turnos AS t
                ON p.Ped_Id_Turno = t.Tur_Id_Turno
            LEFT JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = p.Ped_Id_Pedido
            WHERE p.Ped_Id_Usuario = %s
              AND p.Ped_Estado_Pedido IN (%s, %s, %s)
            ORDER BY p.Ped_Fecha_Pedido DESC, p.Ped_Id_Pedido DESC
            LIMIT 1
            """,
            (int(usuario_id),) + ESTADOS_PEDIDO_ACTIVOS,
        )
        fila = cursor.fetchone()
    except mysql.connector.Error as error:
        print("Error al consultar el turno activo del cliente:", error)
        fila = None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    try:
        g._pedido_activo_cliente = {"usuario_id": int(usuario_id), "fila": fila}
    except RuntimeError:
        pass
    return fila


def cargar_lineas_pedido_cliente(pedido_id):
    """SELECT de detalle para mostrar Mi turno. No escribe."""
    lineas = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
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
            (int(pedido_id),),
        )
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
    except mysql.connector.Error as error:
        print("Error al consultar el detalle del turno del cliente:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lineas


def consultar_ultimo_pedido_cliente(usuario_id):
    """Busca primero si hay un pedido activo. Si no, busca el último pedido (entregado o cualquiera)."""
    activo = consultar_pedido_activo_cliente(usuario_id)
    if activo is not None:
        return activo
    if usuario_id is None:
        return None
    conexion = None
    cursor = None
    fila = None
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
                t.Tur_Id_Turno,
                t.Tur_Numero_Turno,
                v.Ven_Metodo_Pago,
                v.Ven_Estado_Pago
            FROM tbl_pedidos AS p
            INNER JOIN tbl_turnos AS t
                ON p.Ped_Id_Turno = t.Tur_Id_Turno
            LEFT JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = p.Ped_Id_Pedido
            WHERE p.Ped_Id_Usuario = %s
            ORDER BY p.Ped_Fecha_Pedido DESC, p.Ped_Id_Pedido DESC
            LIMIT 1
            """,
            (int(usuario_id),),
        )
        fila = cursor.fetchone()
    except mysql.connector.Error as error:
        print("Error al consultar el último pedido del cliente:", error)
        fila = None
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return fila


def consultar_pedidos_cliente(usuario_id):
    """Retorna el historial completo de pedidos del cliente autenticado, sin duplicar ni exponer datos ajenos."""
    if usuario_id is None:
        return []
    pedidos = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                p.Ped_Id_Pedido,
                p.Ped_Fecha_Pedido,
                p.Ped_Estado_Pedido,
                p.Ped_Total_Pedido,
                p.Ped_Id_Turno,
                t.Tur_Numero_Turno,
                v.Ven_Metodo_Pago,
                v.Ven_Estado_Pago
            FROM tbl_pedidos AS p
            INNER JOIN tbl_turnos AS t
                ON p.Ped_Id_Turno = t.Tur_Id_Turno
            LEFT JOIN tbl_ventas AS v
                ON v.Ven_Id_Pedido = p.Ped_Id_Pedido
            WHERE p.Ped_Id_Usuario = %s
            ORDER BY p.Ped_Fecha_Pedido DESC, p.Ped_Id_Pedido DESC
            """,
            (int(usuario_id),),
        )
        for fila in cursor.fetchall():
            pedido_id = int(fila["Ped_Id_Pedido"])
            total = int(fila["Ped_Total_Pedido"] or 0)
            fecha_val = fila["Ped_Fecha_Pedido"]
            fecha_str = fecha_val.strftime("%d/%m/%Y") if hasattr(fecha_val, "strftime") else str(fecha_val or "")
            pedidos.append(
                {
                    "id": pedido_id,
                    "numero": "CJ-" + str(pedido_id).zfill(3),
                    "fecha": fecha_str,
                    "turno": int(fila["Tur_Numero_Turno"] or 0),
                    "productos": cargar_lineas_pedido_cliente(pedido_id),
                    "total": total,
                    "total_texto": precio_en_texto(total),
                    "estado": (fila["Ped_Estado_Pedido"] or "pendiente"),
                    "estado_texto": ESTADOS_PEDIDO.get(fila["Ped_Estado_Pedido"] or "pendiente", "Pendiente"),
                    "estado_clase": CLASE_ESTADO_PEDIDO.get(fila["Ped_Estado_Pedido"] or "pendiente", "estado-pendiente"),
                    "metodo_pago": "Transferencia con QR" if fila["Ven_Metodo_Pago"] == "Nequi" else (fila["Ven_Metodo_Pago"] or "No registrado"),
                    "estado_pago": fila["Ven_Estado_Pago"] or "No registrado",
                }
            )
    except mysql.connector.Error as error:
        print("Error al consultar compras del cliente:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return pedidos


def obtener_turno_activo_cliente(usuario_id=None):
    """Prepara el último pedido activo (o recién entregado) del Cliente autenticado. None si no hay."""
    if usuario_id is None:
        usuario_id = usuario_id_actual()
    if usuario_id is None or rol_actual() != "cliente":
        return None
    fila = consultar_ultimo_pedido_cliente(usuario_id)
    if fila is None:
        return None
    pedido_id = int(fila["Ped_Id_Pedido"])
    total = int(fila["Ped_Total_Pedido"] or 0)
    return {
        "id": pedido_id,
        "numero": "CJ-" + str(pedido_id).zfill(3),
        "turno": int(fila["Tur_Numero_Turno"] or 0),
        "turno_id": int(fila["Tur_Id_Turno"] or fila["Ped_Id_Turno"] or 0),
        "productos": cargar_lineas_pedido_cliente(pedido_id),
        "total": total,
        "total_texto": precio_en_texto(total),
        "estado": (fila["Ped_Estado_Pedido"] or "pendiente"),
        "estado_texto": ESTADOS_PEDIDO.get(fila["Ped_Estado_Pedido"] or "pendiente", "Pendiente"),
        "estado_clase": CLASE_ESTADO_PEDIDO.get(fila["Ped_Estado_Pedido"] or "pendiente", "estado-pendiente"),
        "metodo_pago": fila["Ven_Metodo_Pago"] or "No registrado",
        "estado_pago": fila["Ven_Estado_Pago"] or "No registrado",
    }


def cliente_tiene_turno_activo():
    """True si el Cliente autenticado tiene un pedido aún no entregado."""
    if rol_actual() != "cliente" or not usuario_id_actual():
        return False
    return consultar_pedido_activo_cliente(usuario_id_actual()) is not None


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
        "mensaje_pedidos_cerrados": MENSAJE_PEDIDOS_CERRADOS,
        "mensaje_turnos_cerrados": MENSAJE_TURNOS_CERRADOS,
        "hay_turno": cliente_tiene_turno_activo(),
        "pagina_actual": pagina_menu(),
        "csrf_token": obtener_token_csrf(),
        "mostrar_invitacion_encuesta": mostrar_invitacion_encuesta(),
        "nombre_usuario": session.get("nombre_usuario", ""),
    }
    datos.update(datos_carrito_flotante())
    return datos


TIPOS_PQR = ("peticion", "queja", "reclamo", "felicitacion")
TIPOS_PQR_TEXTO = {
    "peticion": "Petición",
    "queja": "Queja",
    "reclamo": "Reclamo",
    "felicitacion": "Felicitación",
}
ESTADOS_PQR = ("Pendiente", "Revisada", "Resuelta")
MENSAJES_PQR = {
    "peticion": "Tu petición ha sido enviada, la tomaremos en cuenta. Gracias.",
    "queja": "Tu queja ha sido enviada. La tendremos en cuenta para mejorar nuestro servicio. Gracias.",
    "reclamo": "Tu reclamo ha sido enviado. Revisaremos la situación y trabajaremos para mejorar. Gracias.",
    "felicitacion": "Tu felicitación ha sido recibida. Gracias por compartir tu opinión.",
}


MAX_ASUNTO_PQR = 100
MAX_MENSAJE_PQR = 1000
MENSAJE_PQR_ASUNTO_VACIO = "Escribe el asunto de tu PQR."
MENSAJE_PQR_ASUNTO_LARGO = "El asunto no puede superar 100 caracteres."
MENSAJE_PQR_MENSAJE_VACIO = "Por favor escribe el mensaje."
MENSAJE_PQR_MENSAJE_LARGO = "El mensaje no puede superar 1000 caracteres."


def validar_pqr(tipo, asunto, mensaje):
    if tipo not in TIPOS_PQR:
        return "Por favor selecciona un tipo de PQR."
    asunto_limpio = (asunto or "").strip()
    if not asunto_limpio:
        return MENSAJE_PQR_ASUNTO_VACIO
    if len(asunto_limpio) > MAX_ASUNTO_PQR:
        return MENSAJE_PQR_ASUNTO_LARGO
    mensaje_limpio = (mensaje or "").strip()
    if not mensaje_limpio:
        return MENSAJE_PQR_MENSAJE_VACIO
    if len(mensaje_limpio) > MAX_MENSAJE_PQR:
        return MENSAJE_PQR_MENSAJE_LARGO
    return ""


def datos_formulario_pqr(error="", tipo="", asunto="", mensaje=""):
    datos = datos_pagina_cliente()
    datos.update({
        "error": error,
        "tipo": tipo,
        "asunto": asunto,
        "mensaje_pqr": mensaje,
        "nombre_usuario": session.get("nombre_usuario", ""),
    })
    return datos


def guardar_pqr(usuario_id, tipo, asunto, mensaje):
    """Inserta una PQR del cliente autenticado. Devuelve True si se guardó."""
    if usuario_id is None:
        return False
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO tbl_pqr (
                Pqr_Id_Usuario, Pqr_Tipo, Pqr_Asunto,
                Pqr_Mensaje, Pqr_Fecha, Pqr_Estado
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                int(usuario_id),
                tipo,
                asunto or None,
                mensaje,
                datetime.now(),
                "Pendiente",
            ),
        )
        conexion.commit()
        return True
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al guardar PQR:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def clase_estado_pqr(estado):
    if estado == "Pendiente":
        return "estado-pendiente"
    if estado == "Revisada":
        return "estado-preparando"
    if estado == "Resuelta":
        return "estado-listo"
    return "estado-pendiente"


def cargar_pqr_desde_bd():
    """Lista PQR reales con nombre y documento del usuario, si existe."""
    lista = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                p.Pqr_Id_Pqr,
                p.Pqr_Tipo,
                p.Pqr_Asunto,
                p.Pqr_Mensaje,
                p.Pqr_Fecha,
                p.Pqr_Estado,
                u.Usu_Nombre,
                u.Usu_Apellido,
                u.Usu_Documento
            FROM tbl_pqr AS p
            LEFT JOIN tbl_usuarios AS u
                ON p.Pqr_Id_Usuario = u.Usu_Id_Usuario
            ORDER BY p.Pqr_Fecha DESC, p.Pqr_Id_Pqr DESC
            """
        )
        for fila in cursor.fetchall():
            nombre = ((fila["Usu_Nombre"] or "") + " " + (fila["Usu_Apellido"] or "")).strip()
            if not nombre:
                nombre = "Usuario no disponible"
            documento = fila["Usu_Documento"] or "—"
            fecha = fila["Pqr_Fecha"]
            lista.append(
                {
                    "id": int(fila["Pqr_Id_Pqr"]),
                    "tipo": fila["Pqr_Tipo"] or "",
                    "tipo_texto": TIPOS_PQR_TEXTO.get(fila["Pqr_Tipo"], fila["Pqr_Tipo"] or ""),
                    "asunto": fila["Pqr_Asunto"] or "—",
                    "mensaje": fila["Pqr_Mensaje"] or "",
                    "fecha": fecha.strftime("%d/%m/%Y %H:%M") if fecha else "—",
                    "estado": fila["Pqr_Estado"] or "Pendiente",
                    "estado_clase": clase_estado_pqr(fila["Pqr_Estado"] or "Pendiente"),
                    "estudiante": nombre,
                    "documento": documento,
                }
            )
    except mysql.connector.Error as error:
        print("Error al cargar PQR:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lista


def conteos_pqr(lista):
    conteos = {
        "total": len(lista),
        "pendiente": 0,
        "revisada": 0,
        "resuelta": 0,
        "peticion": 0,
        "queja": 0,
        "reclamo": 0,
        "felicitacion": 0,
    }
    for item in lista:
        estado = (item.get("estado") or "").lower()
        if estado == "pendiente":
            conteos["pendiente"] += 1
        elif estado == "revisada":
            conteos["revisada"] += 1
        elif estado == "resuelta":
            conteos["resuelta"] += 1
        tipo = item.get("tipo") or ""
        if tipo in conteos:
            conteos[tipo] += 1
    return conteos


def actualizar_estado_pqr_bd(pqr_id, estado):
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_pqr
            SET Pqr_Estado = %s
            WHERE Pqr_Id_Pqr = %s
            """,
            (estado, pqr_id),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return False
        conexion.commit()
        return True
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al actualizar estado de PQR:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def datos_panel_pqr(aviso="", filtro_accion="admin-pqr.html"):
    lista = cargar_pqr_desde_bd()
    filtros = leer_filtros_pqr()
    datos = datos_sesion()
    datos.update(
        {
            "pqrs": filtrar_pqr_admin(
                lista,
                filtros["filtro_tipo"],
                filtros["filtro_estado"],
                filtros["filtro_q"],
            ),
            "conteos_pqr": conteos_pqr(lista),
            "estados_pqr": ESTADOS_PQR,
            "aviso_pqr": aviso,
            "filtro_accion": filtro_accion,
            "filtros_campos": campos_filtro_pqr(filtros),
            "filtro_buscar_label": "Buscar",
            "filtro_buscar_placeholder": "Estudiante, documento o asunto",
        }
    )
    datos.update(filtros)
    return datos


def volver_panel_pqr():
    if rol_actual() == "superadmin":
        return "/superadmin-pqr.html"
    return "/admin-pqr.html"


CALIFICACIONES_ENCUESTA = (1, 2, 3, 4, 5)
COMENTARIO_ENCUESTA_MAX = 1000
MENSAJE_ENCUESTA_YA_RESPONDIDA = "Ya respondiste la encuesta. Gracias por tu opinión."
MENSAJE_ENCUESTA_SIN_COMPRA = "Podrás responder la encuesta después de realizar una compra."


def usuario_tiene_compra_confirmada(usuario_id):
    """True si el usuario tiene al menos una venta con pago Confirmado.

    Solo lectura. El efectivo pendiente no cuenta; Nequi sí, porque nace Confirmado.
    """
    if usuario_id is None:
        return False
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT Ven_Id_Venta
            FROM tbl_ventas
            WHERE Ven_Id_Usuario = %s
              AND Ven_Estado_Pago = 'Confirmado'
            LIMIT 1
            """,
            (int(usuario_id),),
        )
        return cursor.fetchone() is not None
    except mysql.connector.Error as error:
        print("Error al consultar compras confirmadas:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def encuesta_pospuesta_en_sesion():
    return bool(session.get("encuesta_pospuesta"))


def mostrar_invitacion_encuesta():
    """La invitación solo sale a un Cliente con compra confirmada, sin encuesta y sin 'Ahora no'."""
    if rol_actual() != "cliente":
        return False
    usuario_id = usuario_id_actual()
    if usuario_id is None:
        return False
    if encuesta_pospuesta_en_sesion():
        return False
    if existe_encuesta_usuario(usuario_id):
        return False
    return usuario_tiene_compra_confirmada(usuario_id)


def calificacion_encuesta(valor):
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None
    if numero not in CALIFICACIONES_ENCUESTA:
        return None
    return numero


def validar_encuesta(experiencia, facilidad, comentario):
    if calificacion_encuesta(experiencia) is None:
        return "Selecciona una calificación de experiencia entre 1 y 5."
    if calificacion_encuesta(facilidad) is None:
        return "Selecciona una calificación de facilidad entre 1 y 5."
    if len((comentario or "").strip()) > COMENTARIO_ENCUESTA_MAX:
        return "El comentario no puede superar 1000 caracteres."
    return ""


def existe_encuesta_usuario(usuario_id):
    if usuario_id is None:
        return False
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT Enc_Id_Encuesta FROM tbl_encuestas WHERE Enc_Id_Usuario = %s",
            (int(usuario_id),),
        )
        return cursor.fetchone() is not None
    except mysql.connector.Error as error:
        print("Error al consultar encuesta del usuario:", error)
        return True
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def guardar_encuesta(usuario_id, experiencia, facilidad, comentario):
    if usuario_id is None:
        return False
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            INSERT INTO tbl_encuestas (
                Enc_Id_Usuario, Enc_Experiencia, Enc_Facilidad,
                Enc_Comentario, Enc_Fecha
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                int(usuario_id),
                experiencia,
                facilidad,
                comentario or None,
                datetime.now(),
            ),
        )
        conexion.commit()
        return True
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al guardar encuesta:", error)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


def cargar_encuestas_desde_bd():
    lista = []
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                e.Enc_Id_Encuesta,
                e.Enc_Experiencia,
                e.Enc_Facilidad,
                e.Enc_Comentario,
                e.Enc_Fecha,
                u.Usu_Nombre,
                u.Usu_Apellido
            FROM tbl_encuestas AS e
            LEFT JOIN tbl_usuarios AS u
                ON e.Enc_Id_Usuario = u.Usu_Id_Usuario
            ORDER BY e.Enc_Fecha DESC, e.Enc_Id_Encuesta DESC
            """
        )
        for fila in cursor.fetchall():
            nombre = ((fila["Usu_Nombre"] or "") + " " + (fila["Usu_Apellido"] or "")).strip()
            if not nombre:
                nombre = "Usuario no disponible"
            fecha = fila["Enc_Fecha"]
            lista.append(
                {
                    "id": int(fila["Enc_Id_Encuesta"]),
                    "experiencia": fila["Enc_Experiencia"],
                    "facilidad": fila["Enc_Facilidad"],
                    "comentario": fila["Enc_Comentario"] or "—",
                    "fecha": fecha.strftime("%d/%m/%Y %H:%M") if fecha else "—",
                    "estudiante": nombre,
                }
            )
    except mysql.connector.Error as error:
        print("Error al cargar encuestas:", error)
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()
    return lista


def resumen_encuestas(lista):
    total = len(lista)
    if total == 0:
        return {
            "total": 0,
            "promedio_experiencia": "Sin respuestas",
            "promedio_facilidad": "Sin respuestas",
        }
    suma_exp = 0
    suma_fac = 0
    for item in lista:
        suma_exp += int(item["experiencia"] or 0)
        suma_fac += int(item["facilidad"] or 0)
    return {
        "total": total,
        "promedio_experiencia": str(round(suma_exp / total, 1)),
        "promedio_facilidad": str(round(suma_fac / total, 1)),
    }


def datos_panel_encuestas():
    lista = cargar_encuestas_desde_bd()
    datos = datos_sesion()
    datos.update(
        {
            "encuestas": lista,
            "resumen_encuesta": resumen_encuestas(lista),
        }
    )
    return datos


def datos_reportes_superadmin(args=None):
    """Encuestas reales más indicadores de negocio reales e informe de utilidad para Superadmin Reportes."""
    if args is None:
        try:
            args = request.args
        except RuntimeError:
            args = {}
    datos = datos_panel_encuestas()
    datos.update(
        {
            "ventas_dia_texto": precio_en_texto(ventas_del_dia()),
            "ventas_semana_texto": precio_en_texto(ventas_total_semana()),
            "cantidad_pedidos": total_pedidos(),
            "unidades_vendidas": unidades_vendidas(),
            "productos_vendidos": productos_vendidos_reporte(),
            "informe_utilidad": calcular_informe_utilidad(args),
        }
    )
    return datos


def datos_reportes_admin(args=None):
    """Encuestas reales más indicadores de negocio reales e informe de utilidad para Admin Reportes."""
    if args is None:
        try:
            args = request.args
        except RuntimeError:
            args = {}
    datos = datos_panel_encuestas()
    producto = producto_mas_pedido()
    datos.update(
        {
            "ventas_dia_texto": precio_en_texto(ventas_del_dia()),
            "pedidos_dia": pedidos_del_dia(),
            "producto_mas_pedido": producto,
            "pqr_dia": pqr_del_dia(),
            "ventas_categoria": ventas_por_categoria(),
            "informe_utilidad": calcular_informe_utilidad(args),
        }
    )
    return datos


def datos_formulario_encuesta(error="", experiencia="", facilidad="", comentario=""):
    datos = datos_pagina_cliente()
    datos.update(
        {
            "error": error,
            "experiencia": str(experiencia or ""),
            "facilidad": str(facilidad or ""),
            "comentario": comentario,
            "encuesta_respondida": existe_encuesta_usuario(usuario_id_actual()),
            "mensaje_encuesta": MENSAJE_ENCUESTA_YA_RESPONDIDA,
        }
    )
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
    bloqueo = redirigir_si_cliente_desactivado()
    if bloqueo:
        return bloqueo
    datos = datos_pagina_cliente()
    datos["aviso"] = request.args.get("aviso", "")
    return render_template("index.html", **datos)


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
    nombre = (request.form.get("nombre") or "").strip()
    apellido = (request.form.get("apellido") or "").strip()
    usuario = (request.form.get("usuario") or "").strip()
    contrasena = request.form.get("contrasena", "")
    confirmar_contrasena = request.form.get("confirmar_contrasena", "")
    datos_form = {
        "valor_nombre": nombre,
        "valor_apellido": apellido,
        "valor_usuario": usuario,
    }
    error = validar_registro_entrada(
        nombre, apellido, usuario, contrasena, confirmar_contrasena
    )
    if error:
        return render_template(
            "registro.html",
            aviso=error,
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
            aviso="No se pudo completar el registro. Intenta de nuevo.",
            **datos_form,
            **datos_pagina_cliente(),
        )
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
                Usu_Usuario, Usu_Contrasena, Usu_Estado, Usu_Documento
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (id_rol, nombre, apellido, usuario, hash_clave, "Activo", None),
        )
        conexion.commit()
        return redirect("/login.html?aviso=" + quote("Cuenta creada. Ya puedes iniciar sesión."))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al registrar usuario:", error)
        if getattr(error, "errno", None) == 1062:
            aviso_dup = "Ese usuario ya existe. Elige otro nombre de usuario."
            detalle = str(error)
            if "Usu_Documento" in detalle:
                aviso_dup = "El documento ya se encuentra registrado."
            return render_template(
                "registro.html",
                aviso=aviso_dup,
                **datos_form,
                **datos_pagina_cliente(),
            )
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
        try:
            fila = buscar_usuario_por_login(usuario)
        except mysql.connector.Error:
            return render_template(
                "login.html",
                aviso="No se pudo iniciar sesión. Revisa que MySQL esté en ejecución e intenta de nuevo.",
                **datos_pagina_cliente(),
            )
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


@app.route("/cerrar-sesion", methods=["POST"])
def cerrar_sesion():
    bloqueo_csrf = redirigir_si_csrf_invalido("/index.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    session.clear()
    return redirect("/index.html")


@app.route("/catalogo.html")
def catalogo():
    bloqueo = redirigir_si_cliente_desactivado()
    if bloqueo:
        return bloqueo
    # Siempre sincronizar con MySQL: evita catálogo vacío si al arrancar falló la BD.
    recargar_productos()
    buscar_texto = (request.args.get("buscar", "") or "").replace("\x00", "").strip()
    aviso = request.args.get("aviso", "")
    if len(buscar_texto) > MAX_BUSQUEDA_CATALOGO:
        aviso = aviso or MENSAJE_BUSQUEDA_LARGA
        buscar = buscar_texto
        buscar_filtro = ""
    else:
        buscar = buscar_texto
        buscar_filtro = buscar_texto
    categoria = categoria_catalogo_valida(request.args.get("categoria", "todos"))
    orden = orden_catalogo_valido(request.args.get("orden", "default"))
    return render_template(
        "catalogo.html",
        productos=[producto_con_ancla(item) for item in filtrar_productos(buscar_filtro, categoria, orden)],
        destacados=[producto_con_ancla(item, "destacado") for item in obtener_destacados()],
        categorias=CATEGORIAS,
        buscar=buscar,
        categoria=categoria,
        orden=orden,
        aviso=aviso,
        **datos_pagina_cliente(),
    )


@app.route("/agregar-al-carrito", methods=["POST"])
def agregar_al_carrito():
    if rol_actual() != "cliente" or not usuario_id_actual():
        return redirect(url_catalogo(MENSAJE_LOGIN_CARRITO))
    bloqueo_inactivo = redirigir_si_cliente_desactivado("/catalogo.html")
    if bloqueo_inactivo:
        return bloqueo_inactivo
    bloqueo_csrf = redirigir_si_csrf_invalido("/catalogo.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    if not sistema_pedidos_activo():
        return redirect(url_catalogo(MENSAJE_PEDIDOS_CERRADOS))
    try:
        producto_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect(url_catalogo("No se encontró el producto."))
    producto = buscar_producto(producto_id)
    if producto is None:
        return redirect(url_catalogo("No se encontró el producto."))
    if producto["cantidad"] <= 0:
        return redirect(url_catalogo("Este producto está agotado."))
    items = obtener_carrito()
    actual = 0
    linea = None
    for item in items:
        if item["id"] == producto_id:
            linea = item
            actual = item["cantidad"]
    nueva = actual + 1
    if nueva > producto["cantidad"]:
        return redirect(url_catalogo("Solo hay " + str(producto["cantidad"]) + " unidades disponibles."))
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
    bloqueo_csrf = redirigir_si_csrf_invalido("/carrito.html")
    if bloqueo_csrf:
        return bloqueo_csrf
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
    bloqueo_csrf = redirigir_si_csrf_invalido("/carrito.html")
    if bloqueo_csrf:
        return bloqueo_csrf
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
        "token_compra": obtener_token_compra(),
    })


@app.route("/confirmar-pago", methods=["POST"])
def confirmar_pago():
    bloqueo = redirigir_si_no_autorizado("pago")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/pago.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    if rol_actual() != "cliente" or not usuario_id_actual():
        return redirect("/login.html")
    token_enviado = request.form.get("token_compra", "")
    with _lock_compra_usuario(usuario_id_actual()):
        if token_compra_ya_usado(token_enviado):
            return redirect("/turno.html?aviso=" + quote(MENSAJE_COMPRA_YA_REGISTRADA))
        if not verificar_token_compra():
            return redirect("/pago.html?aviso=" + quote(MENSAJE_TOKEN_COMPRA))
        if not session.get("paso_carrito"):
            return redirect("/carrito.html")
        items = obtener_carrito()
        if not items:
            return redirect("/carrito.html?aviso=" + quote("El carrito está vacío."))
        if not sistema_pedidos_activo():
            return redirect("/carrito.html?aviso=" + quote(MENSAJE_PEDIDOS_CERRADOS))
        metodo_pago = (request.form.get("metodo_pago") or "").strip()
        if metodo_pago not in METODOS_PAGO:
            return redirect("/pago.html?aviso=" + quote("Selecciona un método de pago válido."))
        for item in items:
            if item["cantidad"] < 1:
                return redirect("/pago.html?aviso=" + quote("Ingresa una cantidad válida."))
        resultado = confirmar_compra_en_bd(
            items, usuario_id_actual(), metodo_pago, token_enviado
        )
        if resultado is None:
            return redirect("/pago.html?aviso=" + quote("No se pudo confirmar el pago. Revisa el inventario disponible."))
        marcar_token_compra_usado(token_enviado)
        pedido_id, turno_id, numero_turno, ya_existia, lineas, total = resultado
        global ultimo_turno_asignado
        if numero_turno > ultimo_turno_asignado:
            ultimo_turno_asignado = numero_turno
        pedido = None
        for candidato in PEDIDOS:
            if candidato.get("id") == int(pedido_id):
                pedido = candidato
                break
        if pedido is None and lineas is not None:
            pedido = registrar_pedido(
                numero_turno,
                lineas,
                total,
                pedido_id=pedido_id,
                turno_id=turno_id,
                metodo_pago=metodo_pago,
                estado_pago=estado_pago_segun_metodo(metodo_pago),
            )
        session["ultimo_pedido"] = pedido
        session.modified = True
        vaciar_carrito()
        if ya_existia:
            return redirect("/turno.html?aviso=" + quote(MENSAJE_COMPRA_YA_REGISTRADA))
        return redirect("/turno.html")


@app.route("/turno.html")
def turno():
    bloqueo = redirigir_si_no_autorizado("turno")
    if bloqueo:
        return bloqueo
    ultimo = obtener_turno_activo_cliente()
    return mostrar_con_turno("turno.html", {
        "ultimo_pedido": ultimo,
        "aviso": request.args.get("aviso", ""),
    })


@app.route("/mis-compras.html")
def mis_compras():
    bloqueo = redirigir_si_no_autorizado("mis-compras")
    if bloqueo:
        return bloqueo
    compras = consultar_pedidos_cliente(usuario_id_actual())
    return mostrar_con_turno("mis-compras.html", {
        "compras": compras,
        "aviso": request.args.get("aviso", ""),
    })


@app.route("/vendedor.html")
def vendedor():
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    sincronizar_contadores_turno_desde_bd()
    aviso = request.args.get("turno", "")
    pendientes, entregados = pedidos_para_vendedor()
    estado = estado_descanso()
    efectivo = sistema_pedidos_activo()
    return mostrar_con_turno(
        "vendedor.html",
        {
            "aviso_turno_cerrado": aviso == "cerrado",
            "aviso_sin_turnos": aviso == "sin-turnos",
            "aviso_pedido": request.args.get("aviso", ""),
            "pedidos_pendientes": pendientes,
            "pedidos_entregados": entregados,
            "hay_pedidos": len(PEDIDOS) > 0,
            "bloqueo_administrativo": bloqueo_administrativo,
            "mensaje_bloqueo_admin": MENSAJE_BLOQUEO_ADMIN,
            # Sin franja horaria abierta el interruptor no basta: se ofrece la apertura temporal.
            "mostrar_apertura_temporal": not estado["activo"] and not bloqueo_administrativo,
            "puede_habilitar": not efectivo and not bloqueo_administrativo,
            "puede_deshabilitar": efectivo,
            "apertura_texto": hora_en_texto(extension_hasta) if extension_hasta else "",
            "por_extension": estado["por_extension"],
            # Solo la apertura que inició el propio Vendedor se le ofrece cancelar.
            "apertura_vendedor": extension_autor == AUTOR_VENDEDOR and extension_hasta is not None,
        },
    )


@app.route("/confirmar-pago-efectivo", methods=["POST"])
def confirmar_pago_efectivo():
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/vendedor.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    try:
        pedido_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect(url_vendedor(aviso="No se encontró el pedido.", fragmento="pedidos"))
    if pedido_id < 1:
        return redirect(url_vendedor(aviso="No se encontró el pedido.", fragmento="pedidos"))
    ancla = ancla_id_pedido(pedido_id)
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_ventas
            SET Ven_Estado_Pago = 'Confirmado'
            WHERE Ven_Id_Pedido = %s
              AND LOWER(TRIM(Ven_Metodo_Pago)) = 'efectivo'
              AND LOWER(TRIM(Ven_Estado_Pago)) = 'pendiente'
            """,
            (pedido_id,),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return redirect(url_vendedor(aviso="No se pudo confirmar el pago en efectivo.", fragmento=ancla))
        conexion.commit()
        return redirect(url_vendedor(aviso=MENSAJE_PAGO_EFECTIVO_OK, fragmento=ancla))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al confirmar pago en efectivo:", error)
        return redirect(url_vendedor(aviso="No se pudo confirmar el pago en efectivo.", fragmento=ancla))
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


@app.route("/confirmar-pago-transferencia", methods=["POST"])
def confirmar_pago_transferencia():
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/vendedor.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    try:
        pedido_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect(url_vendedor(aviso="No se encontró el pedido.", fragmento="pedidos"))
    if pedido_id < 1:
        return redirect(url_vendedor(aviso="No se encontró el pedido.", fragmento="pedidos"))
    ancla = ancla_id_pedido(pedido_id)
    conexion = None
    cursor = None
    try:
        conexion = obtener_conexion()
        cursor = conexion.cursor()
        cursor.execute(
            """
            UPDATE tbl_ventas
            SET Ven_Estado_Pago = 'Confirmado'
            WHERE Ven_Id_Pedido = %s
              AND LOWER(TRIM(Ven_Metodo_Pago)) IN ('nequi', 'transferencia con qr')
              AND LOWER(TRIM(Ven_Estado_Pago)) = 'pendiente'
            """,
            (pedido_id,),
        )
        if cursor.rowcount != 1:
            conexion.rollback()
            return redirect(url_vendedor(aviso="No se pudo confirmar la transferencia QR.", fragmento=ancla))
        conexion.commit()
        return redirect(url_vendedor(aviso=MENSAJE_PAGO_TRANSFERENCIA_OK, fragmento=ancla))
    except mysql.connector.Error as error:
        if conexion is not None:
            conexion.rollback()
        print("Error al confirmar transferencia QR:", error)
        return redirect(url_vendedor(aviso="No se pudo confirmar la transferencia QR.", fragmento=ancla))
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


@app.route("/cambiar-estado-pedido", methods=["POST"])
def cambiar_estado_pedido():
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/vendedor.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    try:
        pedido_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect(url_vendedor(aviso="No se encontró el pedido.", fragmento="pedidos"))
    pedido = buscar_pedido(pedido_id)
    if pedido is None:
        return redirect(url_vendedor(aviso="No se encontró el pedido.", fragmento="pedidos"))
    ancla = ancla_id_pedido(pedido_id)
    requiere = bool(pedido.get("requiere_preparacion"))
    esperado = siguiente_estado_pedido(pedido.get("estado"), requiere)
    if not esperado:
        return redirect(url_vendedor(aviso="El estado solicitado no es válido.", fragmento=ancla))
    if esperado == "entregado" and entrega_bloqueada_por_pago(pedido):
        if (pedido.get("metodo_pago") or "").strip().lower() == "efectivo":
            mensaje_bloqueo = "Confirma el pago en efectivo antes de entregar el pedido."
        else:
            mensaje_bloqueo = "Verifica el comprobante y confirma la transferencia QR antes de entregar el pedido."
        return redirect(
            url_vendedor(
                aviso=mensaje_bloqueo,
                fragmento=ancla,
            )
        )
    resultado = actualizar_estado_pedido_bd(pedido_id, esperado, pedido.get("estado"))
    if resultado == "conflicto":
        return redirect(url_vendedor(aviso=MENSAJE_PEDIDO_YA_ACTUALIZADO, fragmento=ancla))
    if resultado != "ok":
        return redirect(url_vendedor(aviso="No se pudo actualizar el estado del pedido. Intenta de nuevo.", fragmento=ancla))
    pedido["estado"] = esperado
    if esperado == "entregado":
        marcar_turno_de_pedido_atendido(pedido_id)
        sincronizar_contadores_turno_desde_bd()
        return redirect(url_vendedor(fragmento="pedidos"))
    return redirect(url_vendedor(fragmento=ancla))


@app.route("/siguiente-turno", methods=["POST"])
def siguiente_turno():
    """Avanza al siguiente turno disponible previa validación de pedidos del turno actual."""
    global turno_actual, ultimo_turno_asignado
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/vendedor.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    if not sistema_pedidos_activo():
        return redirect("/vendedor.html?turno=cerrado")

    with _lock_siguiente_turno:
        sincronizar_contadores_turno_desde_bd()

        # 1. Validar si el turno actual tiene pedidos pendientes por entregar o cobrar
        bloqueantes = consultar_pedidos_bloqueantes_turno(turno_actual)
        if bloqueantes:
            p = bloqueantes[0]
            estado_p = (p.get("estado") or "").strip().lower()
            pago_p = (p.get("estado_pago") or "").strip().lower()
            if pago_p == "pendiente":
                motivo = "tiene el pago pendiente de confirmación"
            elif estado_p != "entregado":
                motivo = "aún no ha sido marcado como entregado"
            else:
                motivo = "está pendiente de entrega"
            mensaje = (
                f"No puedes avanzar al siguiente turno: el pedido {p.get('numero', '')} "
                f"del turno {turno_actual} {motivo}."
            )
            return redirect(url_vendedor(aviso=mensaje))

        # 2. El turno actual está completado (o no tenía pedidos). Asegurar que quede marcado Atendido en BD
        res_marcar = marcar_turno_atendido(turno_actual)
        if res_marcar == "error":
            return redirect(url_vendedor(aviso=MENSAJE_TURNO_ERROR))

        # 3. Buscar el próximo turno pendiente en MySQL
        proximo = obtener_proximo_turno_pendiente(turno_actual)
        if proximo is not None:
            turno_actual = proximo
            return redirect("/vendedor.html")

        # 4. No hay más turnos pendientes en la cola
        sincronizar_contadores_turno_desde_bd()
        return redirect(url_vendedor(aviso=f"Turno {turno_actual} atendido. No hay más turnos en espera."))


@app.route("/administrador.html")
def administrador():
    bloqueo = redirigir_si_no_autorizado("administrador")
    if bloqueo:
        return bloqueo
    aviso = request.args.get("horario", "")
    return render_template("administrador.html", **datos_pagina_admin(aviso))


@app.route("/extender-horario", methods=["POST"])
def extender_horario():
    """Extiende el descanso en curso o abre de forma extraordinaria hasta una hora futura de hoy."""
    bloqueo = redirigir_si_no_autorizado("administrador")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/administrador.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    resultado = aplicar_extension_horario(request.form.get("hora_extension", ""), AUTOR_ADMIN)
    return redirect("/administrador.html?horario=" + resultado)


@app.route("/cancelar-extension", methods=["POST"])
def cancelar_extension():
    bloqueo = redirigir_si_no_autorizado("administrador")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/administrador.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    limpiar_variables_extension()
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
    filtros = leer_filtros_admin()
    return render_template(
        "admin-productos.html",
        productos=filtrar_productos_admin(
            filtros["filtro_categoria"],
            filtros["filtro_estado"],
            filtros["filtro_q"],
        ),
        categorias_form=categorias_producto(),
        imagenes=imagenes_para_formulario(
            producto_editar["imagen"] if producto_editar else ""
        ),
        producto_editar=producto_editar,
        aviso=aviso,
        filtro_accion="admin-productos.html",
        **filtros,
        **datos_sesion(),
    )


@app.route("/agregar-producto", methods=["POST"])
def agregar_producto():
    bloqueo = redirigir_si_no_autorizado("admin-productos")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/admin-productos.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    nombre = request.form.get("nombre", "")
    categoria = request.form.get("categoria", "")
    precio_texto = request.form.get("precio", "")
    cantidad_texto = request.form.get("cantidad", "")
    imagen = request.form.get("imagen", "")
    error = validar_producto(nombre, categoria, precio_texto, cantidad_texto)
    if error:
        return redirect("/admin-productos.html?aviso=" + quote(error))
    imagen_guardar = imagen_para_guardar(imagen)
    if imagen_guardar is False:
        return redirect("/admin-productos.html?aviso=" + quote("La imagen no es válida."))
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
                imagen_guardar,
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
        return redirect("/admin-productos.html?aviso=" + quote("No se pudo agregar el producto. Intenta de nuevo."))
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and conexion.is_connected():
            conexion.close()


@app.route("/editar-producto", methods=["POST"])
def editar_producto():
    bloqueo = redirigir_si_no_autorizado("admin-productos")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/admin-productos.html")
    if bloqueo_csrf:
        return bloqueo_csrf
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
        return redirect("/admin-productos.html?editar=" + str(producto_id) + "&aviso=" + quote(error) + "#formulario-producto")
    imagen_guardar = imagen_para_guardar(imagen)
    if imagen_guardar is False:
        actual = (producto.get("imagen") or "").strip()
        imagen_guardar = actual if imagen_catalogo_permitida(actual) else None
    id_categoria = obtener_id_categoria(categoria)
    if id_categoria is None:
        return redirect("/admin-productos.html?editar=" + str(producto_id) + "&aviso=" + quote("La categoría no es válida.") + "#formulario-producto")
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
                imagen_guardar,
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
        return redirect("/admin-productos.html?aviso=" + quote("No se pudo actualizar el producto. Intenta de nuevo."))
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
    bloqueo = redirigir_si_no_autorizado("admin-productos")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/admin-productos.html")
    if bloqueo_csrf:
        return bloqueo_csrf
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
        return redirect("/admin-productos.html?aviso=" + quote("No se pudo desactivar el producto. Intenta de nuevo."))
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
    filtros = leer_filtros_admin()
    return render_template(
        "admin-inventarios.html",
        productos=filtrar_productos_admin(
            filtros["filtro_categoria"],
            filtros["filtro_estado"],
            filtros["filtro_q"],
        ),
        categorias_form=categorias_producto(),
        filtro_accion="admin-inventarios.html",
        **filtros,
        **datos_sesion(),
    )


@app.route("/admin-pedidos.html")
def admin_pedidos():
    bloqueo = redirigir_si_no_autorizado("admin-pedidos")
    if bloqueo:
        return bloqueo
    filtros = leer_filtros_pedidos()
    return render_template(
        "admin-pedidos.html",
        pedidos=filtrar_pedidos_admin(
            pedidos_para_admin(),
            filtros["filtro_estado"],
            filtros["filtro_metodo"],
            filtros["filtro_pago"],
            filtros["filtro_q"],
        ),
        filtro_accion="admin-pedidos.html",
        filtros_campos=campos_filtro_pedidos(filtros),
        filtro_buscar_label="Buscar",
        filtro_buscar_placeholder="Pedido o estudiante",
        **filtros,
        **datos_sesion(),
    )


@app.route("/encuesta.html", methods=["GET", "POST"])
def encuesta():
    bloqueo = redirigir_si_no_autorizado("encuesta")
    if bloqueo:
        return bloqueo
    if not usuario_tiene_compra_confirmada(usuario_id_actual()):
        return redirect("/index.html?aviso=" + quote(MENSAJE_ENCUESTA_SIN_COMPRA))
    if request.method != "POST":
        return render_template("encuesta.html", **datos_formulario_encuesta())
    if not verificar_token_csrf():
        return render_template(
            "encuesta.html",
            **datos_formulario_encuesta(MENSAJE_CSRF),
        )

    experiencia = request.form.get("experiencia", "")
    facilidad = request.form.get("facilidad", "")
    comentario = (request.form.get("comentario", "") or "").strip()

    if existe_encuesta_usuario(usuario_id_actual()):
        return render_template("encuesta.html", **datos_formulario_encuesta())

    error = validar_encuesta(experiencia, facilidad, comentario)
    if error:
        return render_template(
            "encuesta.html",
            **datos_formulario_encuesta(error, experiencia, facilidad, comentario),
        )

    if not guardar_encuesta(
        usuario_id_actual(),
        calificacion_encuesta(experiencia),
        calificacion_encuesta(facilidad),
        comentario,
    ):
        if existe_encuesta_usuario(usuario_id_actual()):
            return render_template("encuesta.html", **datos_formulario_encuesta())
        return render_template(
            "encuesta.html",
            **datos_formulario_encuesta(
                "No se pudo enviar la encuesta. Intenta de nuevo.",
                experiencia,
                facilidad,
                comentario,
            ),
        )
    return redirect("/gracias.html")


@app.route("/posponer-encuesta", methods=["POST"])
def posponer_encuesta():
    """Guarda en sesión que el Cliente no quiere ver la invitación ahora."""
    bloqueo = redirigir_si_no_autorizado("encuesta")
    if bloqueo:
        return bloqueo
    origen = request.form.get("origen", "")
    destino = "/turno.html" if origen == "turno" else "/index.html"
    bloqueo_csrf = redirigir_si_csrf_invalido(destino)
    if bloqueo_csrf:
        return bloqueo_csrf
    session["encuesta_pospuesta"] = True
    session.modified = True
    return redirect(destino)


@app.route("/gracias.html", methods=["GET", "POST"])
def gracias():
    bloqueo = redirigir_si_no_autorizado("gracias")
    if bloqueo:
        return bloqueo
    if request.method == "POST" and not verificar_token_csrf():
        return mostrar_html("gracias.html")
    return mostrar_html("gracias.html")


@app.route("/superadmin.html")
def superadmin():
    bloqueo = redirigir_si_no_autorizado("superadmin")
    if bloqueo:
        return bloqueo
    return render_template("superadmin.html", **datos_dashboard_superadmin())


@app.route("/superadmin-productos.html")
def superadmin_productos():
    bloqueo = redirigir_si_no_autorizado("superadmin-productos")
    if bloqueo:
        return bloqueo
    return redirect("/admin-productos.html")


@app.route("/superadmin-usuarios.html")
def superadmin_usuarios():
    bloqueo = redirigir_si_no_autorizado("superadmin-usuarios")
    if bloqueo:
        return bloqueo
    return render_template("superadmin-usuarios.html", **datos_panel_usuarios_superadmin())


@app.route("/cambiar-estado-cliente", methods=["POST"])
def cambiar_estado_cliente():
    bloqueo = redirigir_si_no_autorizado("superadmin-usuarios")
    if bloqueo:
        return bloqueo
    if not verificar_token_csrf():
        return redirect(url_superadmin_usuarios(MENSAJE_CSRF))
    try:
        usuario_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect(url_superadmin_usuarios(MENSAJE_USUARIO_NO_ENCONTRADO))
    objetivo = consultar_rol_y_estado_usuario(usuario_id)
    if objetivo is None:
        return redirect(url_superadmin_usuarios(MENSAJE_USUARIO_NO_ENCONTRADO))
    if objetivo["rol"] != "cliente":
        return redirect(url_superadmin_usuarios(MENSAJE_USUARIO_INTERNO_ESTADO))
    if objetivo["estado"] == "Activo":
        nuevo_estado = "Inactivo"
        aviso = MENSAJE_CLIENTE_DESACTIVADO
    elif objetivo["estado"] == "Inactivo":
        nuevo_estado = "Activo"
        aviso = MENSAJE_CLIENTE_ACTIVADO
    else:
        return redirect(url_superadmin_usuarios(MENSAJE_ESTADO_USUARIO_INVALIDO))
    if not actualizar_estado_cliente_bd(usuario_id, nuevo_estado):
        return redirect(url_superadmin_usuarios(MENSAJE_USUARIO_NO_ENCONTRADO))
    return redirect(url_superadmin_usuarios(aviso))


@app.route("/admin-reportes.html")
def admin_reportes():
    bloqueo = redirigir_si_no_autorizado("admin-reportes")
    if bloqueo:
        return bloqueo
    return render_template("admin-reportes.html", **datos_reportes_admin(request.args))


@app.route("/superadmin-reportes.html")
def superadmin_reportes():
    bloqueo = redirigir_si_no_autorizado("superadmin-reportes")
    if bloqueo:
        return bloqueo
    return render_template("superadmin-reportes.html", **datos_reportes_superadmin(request.args))


@app.route("/pqr.html")
def pqr():
    bloqueo = redirigir_si_no_autorizado("pqr")
    if bloqueo:
        return bloqueo
    return render_template("pqr.html", **datos_formulario_pqr())


@app.route("/pqr-gracias.html", methods=["GET", "POST"])
def pqr_gracias():
    bloqueo = redirigir_si_no_autorizado("pqr-gracias")
    if bloqueo:
        return bloqueo
    if request.method != "POST":
        return redirect("/pqr.html")
    if not verificar_token_csrf():
        return render_template(
            "pqr.html",
            **datos_formulario_pqr(MENSAJE_CSRF),
        )
    tipo = request.form.get("tipo", "")
    asunto = (request.form.get("asunto", "") or "").strip()
    mensaje = (request.form.get("mensaje", "") or "").strip()
    error = validar_pqr(tipo, asunto, mensaje)
    if error:
        return render_template(
            "pqr.html",
            **datos_formulario_pqr(error, tipo, asunto, mensaje),
        )
    if not guardar_pqr(usuario_id_actual(), tipo, asunto, mensaje):
        return render_template(
            "pqr.html",
            **datos_formulario_pqr(
                "No se pudo enviar la PQR. Intenta de nuevo.",
                tipo,
                asunto,
                mensaje,
            ),
        )
    return render_template("pqr-gracias.html", mensaje=MENSAJES_PQR[tipo], **datos_pagina_cliente())


@app.route("/admin-pqr.html")
def admin_pqr():
    bloqueo = redirigir_si_no_autorizado("admin-pqr")
    if bloqueo:
        return bloqueo
    return render_template(
        "admin-pqr.html",
        **datos_panel_pqr(request.args.get("aviso", ""), "admin-pqr.html"),
    )


@app.route("/superadmin-pqr.html")
def superadmin_pqr():
    bloqueo = redirigir_si_no_autorizado("superadmin-pqr")
    if bloqueo:
        return bloqueo
    return render_template(
        "superadmin-pqr.html",
        **datos_panel_pqr(request.args.get("aviso", ""), "superadmin-pqr.html"),
    )


@app.route("/actualizar-estado-pqr", methods=["POST"])
def actualizar_estado_pqr():
    bloqueo = redirigir_si_no_autorizado("admin-pqr")
    if bloqueo:
        return bloqueo
    destino = volver_panel_pqr()
    bloqueo_csrf = redirigir_si_csrf_invalido(destino)
    if bloqueo_csrf:
        return bloqueo_csrf
    try:
        pqr_id = int(request.form.get("id", "0"))
    except ValueError:
        return redirect(destino + "?aviso=" + quote("No se encontró la PQR."))
    estado = (request.form.get("estado", "") or "").strip()
    if estado not in ESTADOS_PQR:
        return redirect(destino + "?aviso=" + quote("El estado solicitado no es válido."))
    if pqr_id < 1 or not actualizar_estado_pqr_bd(pqr_id, estado):
        return redirect(destino + "?aviso=" + quote("No se pudo actualizar el estado de la PQR."))
    return redirect(destino + "?aviso=" + quote("El estado de la PQR fue actualizado."))


@app.route("/habilitar-sistema", methods=["POST"])
def habilitar_sistema():
    global sistema_habilitado, bloqueo_administrativo
    rol = rol_actual()
    if rol not in ("vendedor", "administrador", "superadmin"):
        return redirect("/login.html")
    destino = "/vendedor.html" if request.form.get("origen", "") == "vendedor" else "/administrador.html"
    bloqueo_cuenta = redirigir_si_cuenta_no_activa(destino)
    if bloqueo_cuenta:
        return bloqueo_cuenta
    bloqueo_csrf = redirigir_si_csrf_invalido(destino)
    if bloqueo_csrf:
        return bloqueo_csrf
    if rol == "vendedor":
        # Una acción administrativa prevalece: el Vendedor no puede revertirla.
        if bloqueo_administrativo:
            return redirect("/vendedor.html?aviso=" + quote(MENSAJE_BLOQUEO_ADMIN))
        # El botón solo se ofrece cuando el estado efectivo está inactivo.
        if sistema_pedidos_activo():
            return redirect("/vendedor.html")
        sistema_habilitado = True
        guardar_estado_operativo_en_bd()
        if sistema_pedidos_activo():
            return redirect("/vendedor.html")
        # Fuera de horario el interruptor no basta: se explica y se ofrece la apertura temporal.
        return redirect("/vendedor.html?aviso=" + quote(MENSAJE_FUERA_DE_HORARIO))
    # Administrador y Superadmin: además de encender el interruptor, levantan el bloqueo.
    if not accion_habilitar_util_admin():
        return volver_al_panel()
    sistema_habilitado = True
    bloqueo_administrativo = False
    guardar_estado_operativo_en_bd()
    return volver_al_panel()


@app.route("/deshabilitar-sistema", methods=["POST"])
def deshabilitar_sistema():
    global sistema_habilitado, bloqueo_administrativo
    rol = rol_actual()
    if rol not in ("vendedor", "administrador", "superadmin"):
        return redirect("/login.html")
    destino = "/vendedor.html" if request.form.get("origen", "") == "vendedor" else "/administrador.html"
    bloqueo_cuenta = redirigir_si_cuenta_no_activa(destino)
    if bloqueo_cuenta:
        return bloqueo_cuenta
    bloqueo_csrf = redirigir_si_csrf_invalido(destino)
    if bloqueo_csrf:
        return bloqueo_csrf
    if rol == "vendedor":
        # Solo tiene sentido cerrar si ahora mismo hay algo abierto.
        if not sistema_pedidos_activo():
            return redirect("/vendedor.html")
        sistema_habilitado = False
        guardar_estado_operativo_en_bd()
        return redirect("/vendedor.html")
    # Administrador y Superadmin: cierre manual que además bloquea al Vendedor.
    # Sirve como cierre preventivo aunque el estado efectivo ya sea inactivo.
    if not accion_deshabilitar_util_admin():
        return volver_al_panel()
    sistema_habilitado = False
    bloqueo_administrativo = True
    guardar_estado_operativo_en_bd()
    return volver_al_panel()


@app.route("/abrir-turnos-temporal", methods=["POST"])
def abrir_turnos_temporal():
    """Apertura temporal del Vendedor. Reutiliza la validación de /extender-horario."""
    global sistema_habilitado
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/vendedor.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    if bloqueo_administrativo:
        return redirect("/vendedor.html?aviso=" + quote(MENSAJE_BLOQUEO_ADMIN))
    resultado = aplicar_extension_horario(request.form.get("hora_extension", ""), AUTOR_VENDEDOR)
    if resultado == "invalida":
        return redirect("/vendedor.html?aviso=" + quote(MENSAJE_HORA_INVALIDA))
    # La apertura solo se nota si el interruptor manual está encendido.
    sistema_habilitado = True
    guardar_estado_operativo_en_bd()
    return redirect(
        "/vendedor.html?aviso="
        + quote("Los turnos quedaron abiertos hasta " + hora_en_texto(extension_hasta) + ".")
    )


@app.route("/cancelar-apertura-temporal", methods=["POST"])
def cancelar_apertura_temporal():
    """Cancela solo la apertura temporal que inició el Vendedor.

    No toca el interruptor manual ni el bloqueo administrativo: para eso está
    "Deshabilitar turnos". Las aperturas administrativas se cancelan desde
    /cancelar-extension, que sigue siendo exclusiva del Administrador.
    """
    bloqueo = redirigir_si_no_autorizado("vendedor")
    if bloqueo:
        return bloqueo
    bloqueo_csrf = redirigir_si_csrf_invalido("/vendedor.html")
    if bloqueo_csrf:
        return bloqueo_csrf
    if not apertura_vendedor_vigente():
        return redirect("/vendedor.html?aviso=" + quote(MENSAJE_SIN_APERTURA_VENDEDOR))
    limpiar_variables_extension()
    return redirect(
        "/vendedor.html?aviso=" + quote("La apertura temporal fue cancelada.")
    )


@app.route("/css/<path:archivo>")
def css(archivo):
    return send_from_directory(CARPETA_CSS, archivo, max_age=0)


@app.route("/img/<path:archivo>")
def imagenes(archivo):
    return send_from_directory(CARPETA_IMG, archivo)


HTML_NO_DIRECTO = frozenset((
    "menu",
    "pie",
    "carrito-flotante",
    "indicador-turno",
    "panel",
    "pedido",
    "aviso",
    "icono",
    "filtros-panel",
))


def nombre_html_permitido(nombre):
    """Solo un nombre de archivo simple, sin rutas ni .. ."""
    if not nombre:
        return False
    for caracter in nombre:
        if not (caracter.isalnum() or caracter == "-"):
            return False
    return True


@app.route("/<nombre>.html")
def otras_paginas(nombre):
    if not nombre_html_permitido(nombre) or nombre in HTML_NO_DIRECTO:
        abort(404)
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
    if nombre == "superadmin":
        return superadmin()
    if nombre == "superadmin-productos":
        return superadmin_productos()
    if nombre == "superadmin-usuarios":
        return superadmin_usuarios()
    if nombre == "admin-productos":
        return admin_productos()
    if nombre == "admin-inventarios":
        return admin_inventarios()
    if nombre == "admin-pedidos":
        return admin_pedidos()
    if nombre == "admin-eliminar":
        return admin_eliminar()
    if nombre == "encuesta":
        return encuesta()
    if nombre == "gracias":
        return gracias()
    if nombre == "admin-reportes":
        return admin_reportes()
    if nombre == "superadmin-reportes":
        return superadmin_reportes()
    if nombre == "admin-pqr":
        return admin_pqr()
    if nombre == "superadmin-pqr":
        return superadmin_pqr()
    abort(404)


@app.route("/html/<nombre>.html")
def pagina_en_html(nombre):
    if nombre == "catalogo":
        return catalogo()
    return otras_paginas(nombre)


if __name__ == "__main__":
    puerto = entero_desde_entorno("CAFETIX_PORT", entero_desde_entorno("PORT", 5001))
    host = os.environ.get("CAFETIX_HOST") or "0.0.0.0"
    modo_debug = debug_desde_entorno()
    direccion_local = f"http://localhost:{puerto}/index.html"
    print("=" * 50)
    print("  CAFETIX JOACO")
    print("=" * 50)
    print(f"  Local:   {direccion_local}")
    print(f"  Network: http://{host}:{puerto}/index.html")
    print("  (usa la IP de tu PC en la LAN, ej. http://192.168.x.x:5001)")
    print("  Presiona Ctrl+C para detener")
    print("=" * 50)
    probar_conexion_mysql()
    abrir_navegador = (
        os.environ.get("CAFETIX_NO_BROWSER", "").lower() not in ("1", "true", "yes")
        and not os.environ.get("PORT")
        and not os.environ.get("RENDER")
        and not os.environ.get("PYTHONANYWHERE_DOMAIN")
    )
    if abrir_navegador:
        try:
            Timer(1, lambda: webbrowser.open(direccion_local)).start()
        except Exception:
            pass
    app.run(host=host, port=puerto, debug=modo_debug, use_reloader=False)
