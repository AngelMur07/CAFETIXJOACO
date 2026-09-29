# CAFETIX JOACO

Sistema web de la cafetería escolar de la Institución Educativa José Joaquín Flórez Hernández. Permite consultar productos, realizar pedidos, pagar, asignar turnos y administrar la cafetería.

## Tecnologías

- Python
- Flask
- HTML
- CSS
- MySQL / MariaDB
- XAMPP

Este proyecto no utiliza JavaScript.

## Requisitos

En el computador de destino se necesita:

- Python 3.12
- pip
- XAMPP u otro servidor MySQL/MariaDB compatible

El proyecto se verificó con Python 3.12.10. No es obligatorio usar exactamente esa microversión.

## 1. Preparar MySQL

1. Inicie MySQL desde el panel de XAMPP.
2. Abra phpMyAdmin o un cliente MySQL.
3. Cree una base de datos vacía llamada exactamente:

   `cafetix_joaco`

   No use `cafetixjoaco`.
4. Importe el archivo `cafetix_joaco.sql` dentro de esa base.

El SQL de entrega incluye:

- 10 tablas
- 20 productos
- 4 roles
- 3 usuarios internos

No incluye clientes, pedidos, ventas, turnos, PQR ni encuestas de prueba.

## 2. Instalar dependencias

Abra una terminal en la carpeta `CAFETIXJOACO` y ejecute:

```text
py -m pip install -r requirements.txt
```

Si el comando `py` no existe:

```text
python -m pip install -r requirements.txt
```

Las dependencias del proyecto son Flask y mysql-connector-python.

## 3. Configuración de MySQL

Si no se definen variables de entorno, Flask usa valores compatibles con XAMPP local:

| Variable | Valor por defecto |
| --- | --- |
| `CAFETIX_DB_HOST` | `127.0.0.1` |
| `CAFETIX_DB_USER` | `root` |
| `CAFETIX_DB_PASSWORD` | vacía |
| `CAFETIX_DB_NAME` | `cafetix_joaco` |
| `CAFETIX_DB_PORT` | `3306` |

Solo cambie estas variables si su MySQL no usa esa configuración.

## 4. Clave de sesión (opcional)

`CAFETIX_SECRET_KEY` es opcional. Si existe y no está vacía, Flask la usa siempre.

Si no existe, CAFETIX crea automáticamente una clave local privada en `.cafetix/secret_key` y la reutiliza en los siguientes arranques. Así se conservan sesión, carrito y tokens entre `Ctrl+C` y `py app.py`.

Esa carpeta es configuración local de este computador. No la comparta, no la suba a Git y no la incluya en el ZIP de entrega. En otro PC, si `.cafetix/` no viene, se genera una clave propia al primer arranque.

Si quiere forzar una clave, puede definir la variable (no use este texto en un servidor real):

CMD:

```text
set CAFETIX_SECRET_KEY=una_clave_local_segura
```

PowerShell:

```text
$env:CAFETIX_SECRET_KEY="una_clave_local_segura"
```

No es necesario crear un archivo `.env`.

## 5. Ejecutar

Desde la carpeta `CAFETIXJOACO`:

```text
py app.py
```

Si `py` no existe:

```text
python app.py
```

El puerto por defecto es 5001. Abra:

http://localhost:5001/

Si definió `CAFETIX_PORT`, use ese puerto.

## Cuentas de demostración

Estas cuentas internas vienen en el SQL de entrega:

| Rol | Usuario | Contraseña | Documento |
| --- | --- | --- | --- |
| Vendedor | Vendedor | Vendedor2026 | 1000000003 |
| Administrador | Administrador | Administrador2026 | 1000000002 |
| Superadmin | Superadmin | Superadmin2026 | 1000000001 |

Son credenciales académicas de demostración.

## Estructura básica

```text
CAFETIXJOACO/
├── app.py
├── requirements.txt
├── cafetix_joaco.sql
├── README.md
├── html/
├── css/
└── img/
```

## Funcionamiento general

- **Visitante:** consulta Inicio y Catálogo, puede registrarse o iniciar sesión.
- **Cliente:** consulta el catálogo, arma el pedido, paga, obtiene turno, consulta Mi turno, envía PQR y responde la encuesta contextual.
- **Vendedor:** gestiona pedidos y confirma pagos en efectivo. Puede abrir turnos de forma temporal.
- **Administrador:** gestiona productos, inventario, pedidos, PQR y reportes. Puede habilitar, deshabilitar o extender el horario.
- **Superadmin:** incluye las funciones administrativas y la gestión de usuarios.

## Horarios y controles operativos

Los pedidos dependen de las franjas horarias del sistema y de controles operativos (habilitar/deshabilitar, extensión o apertura temporal por roles autorizados).

Las aperturas temporales, las extensiones y algunos controles operativos viven en la memoria del servidor. Al reiniciar Flask vuelven a su estado inicial.

Eso no borra productos, usuarios, pedidos, ventas ni turnos guardados en MySQL.
