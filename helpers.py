import pandas as pd

# Simulación de catálogos locales (más adelante conectaremos los reales)
catalog_saai = {
    "E001": "Error en estructura del pedimento. Revisar formato de campos obligatorios.",
    "E045": "Clave de aduana inexistente o incorrecta.",
    "S120": "Error sintáctico en bloque de datos de contribuciones.",
}

def interpret_error(code: str):
    code = code.strip().upper()
    if code in catalog_saai:
        return f"📘 {catalog_saai[code]}"
    else:
        return "⚠️ Código no encontrado en catálogo SAAI/Sintáctico. Revisar Anexo 22 o VOCE."