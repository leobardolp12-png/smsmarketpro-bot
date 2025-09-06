# bot/utils/__init__.py

# ==========================
# Funciones temporales para que Render no falle al importar
# ==========================

def calculate_total(*args, **kwargs):
    """
    Función temporal para calcular totales.
    Reemplaza con tu lógica real más adelante.
    """
    return 0

def generate_captcha_options(*args, **kwargs):
    """
    Función temporal para generar opciones de captcha.
    Reemplaza con tu lógica real más adelante.
    """
    return ["1", "2", "3"]

# ==========================
# Si tienes otras utilidades, también puedes agregarlas aquí
# from .otros_modulos import funcion_x
# ==========================
# bot/utils/__init__.py
from .calculate import calculate_total
from .captcha import generate_captcha_options
from .formatting import format_currency
