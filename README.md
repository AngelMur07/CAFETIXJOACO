# CAFETIX JOACO — Entrega Académica (Grado 11)

**Sistema Digital de Gestión de Ventas para la Cafetería Institucional**
**Institución Educativa José Joaquín Flórez Hernández (JJFH)**
Ibagué, Tolima — Colombia (2026)

---

### Autores
- **Angel Mur**
- **Anais Fierro**
- **Tatiana Rodriguez**
- **David Saavedra**

### Aviso de Derechos de Autor y Uso Académico
> **© 2026 CAFETIX JOACO. Todos los derechos reservados.**
> **Uso académico:** Copia entregada exclusivamente para revisión, sustentación y evaluación del proyecto de Grado 11.
> La entrega de esta copia al docente evaluador no transfiere la propiedad intelectual ni los derechos de autor morales o patrimoniales del software. Para más detalles consulte el archivo [`DERECHOS_DE_AUTOR.txt`](DERECHOS_DE_AUTOR.txt).

---

## Tecnologías y Arquitectura

- **Backend:** Python 3.12 + Flask
- **Frontend:** HTML5 semántico + CSS3 puro
- **Base de Datos:** MySQL / MariaDB (motor InnoDB, codificación `utf8mb4`)
- **Entorno Local:** XAMPP (Apache/MySQL) o MariaDB local
- **Restricción Técnica:** **0 % JavaScript** (no utiliza archivos `.js`, no requiere etiquetas `<script>` ni eventos de cliente; toda la interactividad opera por formularios estándar, validaciones de servidor y hojas de estilo CSS).

---

## Requisitos de Ejecución

En el computador donde se evaluará el aplicativo se requiere:

1. **Python 3.12** (o 3.10+) con el gestor de paquetes **pip**.
2. **XAMPP** u otro servidor local con servicio **MySQL** activo en el puerto 3306.
3. Navegador web moderno (Chrome, Edge, Firefox).

---

## Guía Rápida de Instalación y Puesta en Marcha

### Paso 1: Configurar la Base de Datos en MySQL (XAMPP)

1. Abra el **Panel de Control de XAMPP** e inicie el servicio **MySQL**.
2. Abra **phpMyAdmin** en el navegador (`http://localhost/phpmyadmin/`) o su cliente SQL favorito.
3. Cree una base de datos nueva vacía con el nombre exacto:
   ```text
   cafetix_joaco
   ```
   *(Cotejamiento recomendado: `utf8mb4_general_ci`).*
4. Importe el archivo limpio de instalación:
   ```text
   cafetix_joaco.sql
   ```
   *Este archivo crea las 11 tablas del sistema, los 6 grupos de categorías, el catálogo de 20 productos y las 3 cuentas internas de demostración. No incluye datos personales ni pedidos residuales.*

### Paso 2: Instalar Dependencias de Python

Abra una consola o terminal (CMD o PowerShell) en la carpeta `CAFETIX_JOACO_ENTREGA_ACADEMICA` y ejecute:

```text
py -m pip install -r requirements.txt
```

O si su sistema utiliza el comando `python`:

```text
python -m pip install -r requirements.txt
```

*(Las dependencias principales son `Flask` y `mysql-connector-python`).*

### Paso 3: Parámetros de Conexión a la Base de Datos

Por defecto, la aplicación se conecta automáticamente con las credenciales típicas de XAMPP:
- **Host:** `127.0.0.1`
- **Puerto:** `3306`
- **Usuario:** `root`
- **Contraseña:** *(vacía)*
- **Base de datos:** `cafetix_joaco`

Si su entorno local utiliza una contraseña de MySQL distinta, puede definir variables de entorno antes de ejecutar:
- En PowerShell:
  ```text
  $env:CAFETIX_DB_PASSWORD="su_contraseña"
  ```
- En CMD:
  ```text
  set CAFETIX_DB_PASSWORD=su_contraseña
  ```

### Paso 4: Iniciar el Servidor Web

En la misma terminal, ejecute:

```text
py app.py
```
*(o `python app.py`)*

La consola confirmará el inicio del servicio:
```text
 * Running on http://127.0.0.1:5001/
```

Abra en su navegador la URL:
```text
http://localhost:5001/
```

---

## Cuentas de Acceso para Demostración

El script `cafetix_joaco.sql` incluye los siguientes usuarios internos preconfigurados para evaluación académica (con contraseñas protegidas mediante hash criptográfico Werkzeug/scrypt):

| Rol | Usuario | Contraseña Demostración | Cédula / Documento | Funcionalidad Principal |
| :--- | :--- | :--- | :--- | :--- |
| **Vendedor** | `Vendedor` | `Privada (consultar al equipo del proyecto)` | `1000000003` | Gestión de cola de pedidos, confirmación de pagos en efectivo/transferencia y aperturas temporales de turno. |
| **Administrador** | `Administrador` | `Privada (consultar al equipo del proyecto)` | `1000000002` | Gestión de catálogo de productos, inventario, reportes de ventas, respuesta a PQR y control de horarios. |
| **Superadmin** | `Superadmin` | `Privada (consultar al equipo del proyecto)` | `1000000001` | Control total del sistema, administración de usuarios y cambio de roles de personal. |

*(Para probar la experiencia del **Cliente**, puede registrar un usuario nuevo desde la pantalla de Registro o iniciar sesión libremente).*

---

## Roles y Funcionalidades del Sistema

1. **Visitante (público):**
   - Visualización del menú de bienvenida e información institucional de la cafetería JJFH.
   - Exploración del catálogo de productos con filtrado por categorías.
   - Módulos de inicio de sesión y registro de clientes.

2. **Cliente (estudiante / docente):**
   - Catálogo interactivo con carrito de compra persistente (server-side).
   - Checkout con selección de método de pago (Efectivo o Transferencia QR Nequi).
   - Generación automática de turno y token de compra.
   - Historial personal de pedidos en "Mis Compras".
   - Radicación de PQRS (Peticiones, Quejas, Reclamos y Sugerencias).
   - Diligenciamiento de la encuesta de satisfacción del servicio.

3. **Vendedor:**
   - Panel de control operativo de pedidos pendientes y en preparación.
   - Validación y confirmación de cobros en caja.
   - Llamado de turnos y control de entregas.
   - Extensión o habilitación temporal de turnos fuera de horario habitual.

4. **Administrador:**
   - Gestión integral del catálogo de productos (crear, editar, ocultar/desactivar y eliminar).
   - Control de inventario físico (existencias y valores totales en bodega).
   - Bandeja de gestión y respuesta a PQRS.
   - Generación de reportes detallados de ventas por rangos de fecha y métricas de desempeño.
   - Control de jornadas operativas (mañana, tarde, noche) y habilitación/bloqueo del sistema.

5. **Superadministrador:**
   - Módulo exclusivo de gestión de usuarios: modificación de datos, cambio de rol (Cliente, Vendedor, Administrador, Superadmin) y estados de cuenta (Activo/Inactivo).
   - Auditoría y supervisión global de operaciones.

---

## Estructura de Archivos del Proyecto Entregable

```text
CAFETIXJOACO/
├── app.py                      # Controlador principal, rutas y lógica del servidor Flask
├── wsgi.py                     # Punto de entrada WSGI para despliegue en servidor
├── requirements.txt            # Dependencias oficiales de Python
├── cafetix_joaco.sql           # Esquema e inicialización limpia de MySQL
├── DERECHOS_DE_AUTOR.txt       # Términos legales de autoría y uso académico
├── README.md                   # Documentación y manual de instalación
├── .gitignore                  # Exclusiones de Git para privacidad
├── html/                       # 31 plantillas HTML (con pie de página de derechos de autor)
│   ├── pie.html                # Plantilla compartida del pie de página con autoría
│   ├── menu.html               # Barra de navegación institucional
│   ├── index.html, catalogo.html, carrito.html, pago.html, turno.html ...
│   └── administrador.html, vendedor.html, superadmin.html ...
├── css/                        # 6 hojas de estilo CSS modulares (0% JavaScript)
│   ├── style.css               # Estilos globales, tipografía, variables y footer
│   ├── cliente.css, vendedor.css, admin.css, superadmin.css, paneles.css
└── img/                        # Fotografías de productos, logos JJFH e iconos vectoriales SVG
    └── iconos/                 # Biblioteca SVG institucional
```

---

## Cumplimiento de Restricciones Técnicas

- **Cero JavaScript (0% JS):** El aplicativo funciona íntegramente mediante peticiones HTTP estándar (GET/POST), redirecciones de Flask, sesiones de Flask protegidas mediante cookies firmadas y renderizado con Jinja2.
- **Seguridad y Privacidad:** No se incluyen credenciales reales de producción, archivos `.env`, copias de seguridad de datos personales ni llaves privadas. Las cuentas de demostración utilizan credenciales académicas predeterminadas.
- **Persistencia Confiable:** Toda la data crítica (pedidos, ventas, usuarios, inventario) se gestiona de forma transaccional sobre MySQL InnoDB.


---

## Despliegue en hosting: Render + Aiven

CAFETIX JOACO puede ejecutarse localmente con XAMPP o alojarse en internet mediante Render y una base de datos MySQL administrada por Aiven. La configuración de hosting es independiente de la instalación local.

### 1. Preparar la base de datos en Aiven

1. Crear o utilizar un servicio MySQL en Aiven.
2. Crear la base de datos llamada `cafetix_joaco`.
3. Importar el archivo `cafetix_joaco.sql` en esa base de datos.
4. Comprobar que estén presentes las 11 tablas, los 20 productos, las categorías, los roles y las cuentas internas.
5. Descargar el certificado CA de Aiven y conservarlo de forma privada.

**Importante:** la base de datos de Aiven es independiente de la base de datos local de XAMPP. No es necesario eliminar ni modificar la base de datos local para utilizar el hosting.

### 2. Crear el servicio web en Render

Conectar el repositorio de GitHub y seleccionar la rama `hosting-render`.

Configuración de referencia:

| Campo | Valor |
| --- | --- |
| Entorno | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn wsgi:application --workers 1 --threads 4` |

Render proporciona automáticamente la variable `PORT`. El archivo `wsgi.py` expone la aplicación Flask mediante `application`.

Se utiliza un solo worker porque algunos controles operativos temporales del proyecto se mantienen en la memoria del proceso. Los cuatro hilos permiten atender varias solicitudes compartiendo ese estado.

### 3. Configurar las variables de entorno

En la configuración del servicio web de Render, agregar estas variables:

| Variable | Valor o descripción |
| --- | --- |
| `CAFETIX_SECRET_KEY` | Clave privada y segura para las sesiones de Flask. |
| `CAFETIX_DB_HOST` | Host MySQL proporcionado por Aiven. |
| `CAFETIX_DB_PORT` | Puerto MySQL proporcionado por Aiven. |
| `CAFETIX_DB_USER` | Usuario de conexión de Aiven. |
| `CAFETIX_DB_PASSWORD` | Contraseña de conexión de Aiven. |
| `CAFETIX_DB_NAME` | `cafetix_joaco` |
| `CAFETIX_DB_SSL_CA` | `/etc/secrets/ca.pem` |
| `CAFETIX_DB_SSL_VERIFY_IDENTITY` | Verificación de identidad del servidor; por defecto está activada. |

Los valores de conexión se consultan en el panel privado de Aiven. Las contraseñas y la clave de sesión deben introducirse directamente en Render, nunca en este README ni en archivos públicos del repositorio.

### 4. Configurar el certificado SSL

Aiven requiere una conexión segura mediante SSL.

1. En Render, abrir la sección **Secret Files** del servicio web.
2. Crear un archivo secreto con el nombre `ca.pem`.
3. Pegar el contenido del certificado CA descargado desde Aiven.
4. Establecer como ruta del archivo:

   `/etc/secrets/ca.pem`

5. Configurar la variable `CAFETIX_DB_SSL_CA` con esa misma ruta.

La aplicación utiliza el certificado para establecer la conexión segura y verificar la identidad del servidor. El certificado no debe subirse al repositorio público ni incluirse en el ZIP académico.

### 5. Comprobar el despliegue

Después de guardar la configuración:

1. Revisar los registros de Render para comprobar que la aplicación inicia sin errores.
2. Abrir la dirección pública asignada por Render.
3. Comprobar Inicio y Catálogo como visitante.
4. Probar el registro e inicio de sesión de un cliente.
5. Revisar el carrito, el pago mediante transferencia con QR y la generación del turno.
6. Comprobar los paneles de Vendedor, Administrador y Superadmin.
7. Confirmar que los pedidos y demás datos se guardan en Aiven.

Si la aplicación no logra conectarse a Aiven, revisar el host, puerto, usuario, contraseña, nombre de la base de datos, certificado CA y las reglas de acceso de red del servicio.

### 6. Mantener separados los entornos

- **Local:** `py app.py`, XAMPP y la base de datos local `cafetix_joaco`.
- **Hosting:** Gunicorn, Render y la base de datos MySQL de Aiven.
- **Configuración privada:** contraseñas, claves de sesión y certificado CA. No deben publicarse en GitHub.

La configuración de hosting no reemplaza ni elimina la instalación local. Ambos entornos pueden mantenerse de forma independiente.

---

## Nota sobre las cuentas de demostración

Las cuentas internas incluidas en el SQL se conservan para la presentación y evaluación académica del proyecto. Son credenciales temporales de demostración y no deben utilizarse como cuentas definitivas en un servicio real.
