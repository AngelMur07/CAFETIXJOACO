"""
wsgi.py
-------
Punto de entrada WSGI para despliegue en servidores web y hosting en la nube.
Compatible con Gunicorn, Waitress, PythonAnywhere, Render, Railway y cPanel (Passenger).
"""

from app import app

# 'application' es la referencia estándar requerida por servidores WSGI (Gunicorn, mod_wsgi, Passenger).
application = app

if __name__ == "__main__":
    app.run()
