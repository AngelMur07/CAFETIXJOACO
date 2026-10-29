# CAFETIX JOACO â€” Entrega AcadÃ©mica (Grado 11)

**Sistema Digital de GestiÃ³n de Ventas para la CafeterÃ­a Institucional**
**InstituciÃ³n Educativa JosÃ© JoaquÃ­n FlÃ³rez HernÃ¡ndez (JJFH)**
IbaguÃ©, Tolima â€” Colombia (2026)

---

### Autores
- **Angel Mur**
- **Anais Fierro**
- **Tatiana Rodriguez**
- **David Saavedra**

### Aviso de Derechos de Autor y Uso AcadÃ©mico
> **Â© 2026 CAFETIX JOACO. Todos los derechos reservados.**
> **Uso acadÃ©mico:** Copia entregada exclusivamente para revisiÃ³n, sustentaciÃ³n y evaluaciÃ³n del proyecto de Grado 11.
> La entrega de esta copia al docente evaluador no transfiere la propiedad intelectual ni los derechos de autor morales o patrimoniales del software. Para mÃ¡s detalles consulte el archivo [`DERECHOS_DE_AUTOR.txt`](DERECHOS_DE_AUTOR.txt).

---

## TecnologÃ­as y Arquitectura

- **Backend:** Python 3.12 + Flask
- **Frontend:** HTML5 semÃ¡ntico + CSS3 puro
- **Base de Datos:** MySQL / MariaDB (motor InnoDB, codificaciÃ³n `utf8mb4`)
- **Entorno Local:** XAMPP (Apache/MySQL) o MariaDB local
- **RestricciÃ³n TÃ©cnica:** **0 % JavaScript** (no utiliza archivos `.js`, no requiere etiquetas `<script>` ni eventos de cliente; toda la interactividad opera por formularios estÃ¡ndar, validaciones de servidor y hojas de estilo CSS).

---

## Requisitos de EjecuciÃ³n

En el computador donde se evaluarÃ¡ el aplicativo se requiere:

1. **Python 3.12** (o 3.10+) con el gestor de paquetes **pip**.
2. **XAMPP** u otro servidor local con servicio **MySQL** activo en el puerto 3306.
3. Navegador web moderno (Chrome, Edge, Firefox).

---

## GuÃ­a RÃ¡pida de InstalaciÃ³n y Puesta en Marcha

### Paso 1: Configurar la Base de Datos en MySQL (XAMPP)

1. Abra el **Panel de Control de XAMPP** e inicie el servicio **MySQL**.
2. Abra **phpMyAdmin** en el navegador (`http://localhost/phpmyadmin/`) o su cliente SQL favorito.
3. Cree una base de datos nueva vacÃ­a con el nombre exacto:
   ```text
   cafetix_joaco
   ```
   *(Cotejamiento recomendado: `utf8mb4_general_ci`).*
4. Importe el archivo limpio de instalaciÃ³n:
   ```text
   cafetix_joaco.sql
   ```
   *Este archivo crea las 10 tablas del sistema, los 6 grupos de categorÃ­as, el catÃ¡logo de 20 productos y las 3 cuentas internas de demostraciÃ³n. No incluye datos personales ni pedidos residuales.*

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

### Paso 3: ParÃ¡metros de ConexiÃ³n a la Base de Datos

Por defecto, la aplicaciÃ³n se conecta automÃ¡ticamente con las credenciales tÃ­picas de XAMPP:
- **Host:** `127.0.0.1`
- **Puerto:** `3306`
- **Usuario:** `root`
- **ContraseÃ±a:** *(vacÃ­a)*
- **Base de datos:** `cafetix_joaco`

Si su entorno local utiliza una contraseÃ±a de MySQL distinta, puede definir variables de entorno antes de ejecutar:
- En PowerShell:
  ```text
  $env:CAFETIX_DB_PASSWORD="su_contraseÃ±a"
  ```
- En CMD:
  ```text
  set CAFETIX_DB_PASSWORD=su_contraseÃ±a
  ```

### Paso 4: Iniciar el Servidor Web

En la misma terminal, ejecute:

```text
py app.py
```
*(o `python app.py`)*

La consola confirmarÃ¡ el inicio del servicio:
```text
 * Running on http://127.0.0.1:5001/
```

Abra en su navegador la URL:
```text
http://localhost:5001/
```

---

## Cuentas de Acceso para DemostraciÃ³n

El script `cafetix_joaco.sql` incluye los siguientes usuarios internos preconfigurados para evaluaciÃ³n acadÃ©mica (con contraseÃ±as protegidas mediante hash criptogrÃ¡fico Werkzeug/scrypt):

| Rol | Usuario | ContraseÃ±a DemostraciÃ³n | CÃ©dula / Documento | Funcionalidad Principal |
| :--- | :--- | :--- | :--- | :--- |
| **Vendedor** | `Vendedor` | `Vendedor2026` | `1000000003` | GestiÃ³n de cola de pedidos, confirmaciÃ³n de pagos en efectivo/transferencia y aperturas temporales de turno. |
| **Administrador** | `Administrador` | `Administrador2026` | `1000000002` | GestiÃ³n de catÃ¡logo de productos, inventario, reportes de ventas, respuesta a PQR y control de horarios. |
| **Superadmin** | `Superadmin` | `Superadmin2026` | `1000000001` | Control total del sistema, administraciÃ³n de usuarios y cambio de roles de personal. |

*(Para probar la experiencia del **Cliente**, puede registrar un usuario nuevo desde la pantalla de Registro o iniciar sesiÃ³n libremente).*

---

## Roles y Funcionalidades del Sistema

1. **Visitante (pÃºblico):**
   - VisualizaciÃ³n del menÃº de bienvenida e informaciÃ³n institucional de la cafeterÃ­a JJFH.
   - ExploraciÃ³n del catÃ¡logo de productos con filtrado por categorÃ­as.
   - MÃ³dulos de inicio de sesiÃ³n y registro de clientes.

2. **Cliente (estudiante / docente):**
   - CatÃ¡logo interactivo con carrito de compra persistente (server-side).
   - Checkout con selecciÃ³n de mÃ©todo de pago (Efectivo o Transferencia QR Nequi).
   - GeneraciÃ³n automÃ¡tica de turno y token de compra.
   - Historial personal de pedidos en "Mis Compras".
   - RadicaciÃ³n de PQRS (Peticiones, Quejas, Reclamos y Sugerencias).
   - Diligenciamiento de la encuesta de satisfacciÃ³n del servicio.

3. **Vendedor:**
   - Panel de control operativo de pedidos pendientes y en preparaciÃ³n.
   - ValidaciÃ³n y confirmaciÃ³n de cobros en caja.
   - Llamado de turnos y control de entregas.
   - ExtensiÃ³n o habilitaciÃ³n temporal de turnos fuera de horario habitual.

4. **Administrador:**
   - GestiÃ³n integral del catÃ¡logo de productos (crear, editar, ocultar/desactivar y eliminar).
   - Control de inventario fÃ­sico (existencias y valores totales en bodega).
   - Bandeja de gestiÃ³n y respuesta a PQRS.
   - GeneraciÃ³n de reportes detallados de ventas por rangos de fecha y mÃ©tricas de desempeÃ±o.
   - Control de jornadas operativas (maÃ±ana, tarde, noche) y habilitaciÃ³n/bloqueo del sistema.

5. **Superadministrador:**
   - MÃ³dulo exclusivo de gestiÃ³n de usuarios: modificaciÃ³n de datos, cambio de rol (Cliente, Vendedor, Administrador, Superadmin) y estados de cuenta (Activo/Inactivo).
   - AuditorÃ­a y supervisiÃ³n global de operaciones.

---

## Estructura de Archivos del Proyecto Entregable

```text
CAFETIX_JOACO_ENTREGA_ACADEMICA/
â”œâ”€â”€ app.py                      # Controlador principal, rutas y lÃ³gica del servidor Flask
â”œâ”€â”€ wsgi.py                     # Punto de entrada WSGI para despliegue en servidor
â”œâ”€â”€ requirements.txt            # Dependencias oficiales de Python
â”œâ”€â”€ cafetix_joaco.sql           # Esquema e inicializaciÃ³n limpia de MySQL
â”œâ”€â”€ DERECHOS_DE_AUTOR.txt       # TÃ©rminos legales de autorÃ­a y uso acadÃ©mico
â”œâ”€â”€ README.md                   # DocumentaciÃ³n y manual de instalaciÃ³n
â”œâ”€â”€ .gitignore                  # Exclusiones de Git para privacidad
â”œâ”€â”€ html/                       # 31 plantillas HTML (con pie de pÃ¡gina de derechos de autor)
â”‚   â”œâ”€â”€ pie.html                # Plantilla compartida del pie de pÃ¡gina con autorÃ­a
â”‚   â”œâ”€â”€ menu.html               # Barra de navegaciÃ³n institucional
â”‚   â”œâ”€â”€ index.html, catalogo.html, carrito.html, pago.html, turno.html ...
â”‚   â””â”€â”€ administrador.html, vendedor.html, superadmin.html ...
â”œâ”€â”€ css/                        # 6 hojas de estilo CSS modulares (0% JavaScript)
â”‚   â”œâ”€â”€ style.css               # Estilos globales, tipografÃ­a, variables y footer
â”‚   â”œâ”€â”€ cliente.css, vendedor.css, admin.css, superadmin.css, paneles.css
â””â”€â”€ img/                        # FotografÃ­as de productos, logos JJFH e iconos vectoriales SVG
    â””â”€â”€ iconos/                 # Biblioteca SVG institucional
```

---

## Cumplimiento de Restricciones TÃ©cnicas

- **Cero JavaScript (0% JS):** El aplicativo funciona Ã­ntegramente mediante peticiones HTTP estÃ¡ndar (GET/POST), redirecciones de Flask, sesiones seguras en cookies encriptadas y renderizado con Jinja2.
- **Seguridad y Privacidad:** No se incluyen credenciales reales de producciÃ³n, archivos `.env`, copias de seguridad de datos personales ni llaves privadas. Las cuentas de demostraciÃ³n utilizan credenciales acadÃ©micas predeterminadas.
- **Persistencia Confiable:** Toda la data crÃ­tica (pedidos, ventas, usuarios, inventario) se gestiona de forma transaccional sobre MySQL InnoDB.
