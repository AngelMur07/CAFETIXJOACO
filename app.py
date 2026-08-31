"""
CAFETIX JOACO - Servidor local para ver el sitio
Este archivo solo abre las páginas HTML. Todavía no usa base de datos.

Uso:
  1. Abre la carpeta del proyecto
  2. Ejecuta: py app.py
  3. El navegador se abre en: http://localhost:8000/html/index.html
"""

import http.server
import socketserver
import os
import webbrowser
from threading import Timer

PUERTO = 8000

# Cambiar al directorio del proyecto
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Si alguien entra a la raíz, lo lleva a la página de inicio
        if self.path == "/" or self.path == "/index.html":
            self.send_response(302)
            self.send_header("Location", "/html/index.html")
            self.end_headers()
            return
        return super().do_GET()


print("=" * 50)
print("  CAFETIX JOACO - Servidor local")
print("=" * 50)
print(f"  Abre tu navegador en: http://localhost:{PUERTO}/html/index.html")
print("  Presiona Ctrl+C para detener el servidor")
print("=" * 50)

Timer(1, lambda: webbrowser.open(f"http://localhost:{PUERTO}/html/index.html")).start()

with socketserver.TCPServer(("", PUERTO), Handler) as httpd:
    httpd.serve_forever()
