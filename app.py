"""
CAFETIX JOACO - Servidor local (Día 1)
Ejecuta este archivo desde Visual Studio Code para ver el sitio web.

Uso:
  1. Abre la carpeta del proyecto en VS Code
  2. Ejecuta: py app.py
  3. Abre el navegador en: http://localhost:8000
"""

import http.server
import socketserver
import os
import webbrowser
from threading import Timer

# Puerto del servidor local
PUERTO = 8000

# Cambiar al directorio del proyecto
os.chdir(os.path.dirname(os.path.abspath(__file__)))

Handler = http.server.SimpleHTTPRequestHandler

print("=" * 50)
print("  CAFETIX JOACO - Servidor local")
print("=" * 50)
print(f"  Abre tu navegador en: http://localhost:{PUERTO}")
print("  Presiona Ctrl+C para detener el servidor")
print("=" * 50)

# Abrir el navegador automáticamente después de 1 segundo
Timer(1, lambda: webbrowser.open(f"http://localhost:{PUERTO}")).start()

with socketserver.TCPServer(("", PUERTO), Handler) as httpd:
    httpd.serve_forever()
