import streamlit as st
import pandas as pd
import os
import re
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.3", page_icon="🧭", layout="centered")

# Carga variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # 🔑 clave ahora solo desde .env o entorno de Render

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================
@st.cache_data
def load_catalog():
    """Carga el catálogo de errores unificado"""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")
        df.columns = [c.strip() for c in df.columns]  # Limpia espacios
        return df
    except Exception as e:
        st.error(f"⚠️ No se pudo cargar el catálogo: {e}")
        return pd.DataFrame()

def normalize_text(text):
    """Normaliza texto para comparación flexible"""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def search_error(df, query):
    """Busca coincidencias por código, clase, registro, campo o texto general"""
    q = normalize_text(query)

    # Extraer números y palabras clave
    codigo = clase = registro = campo = None
    patterns = {
        "codigo": r"codigo\s*(\d+)",
        "clase": r"clase\s*(\d+)",
        "registro": r"registro\s*(\d+)",
        "campo": r"campo\s*(\d+)"
    }
    for key, pat in patterns.items():
        m = re.search(pat, q)
        if m:
            if key == "codigo": codigo = m.group(1)
            elif key == "clase": clase = m.group(1)
            elif key == "registro": registro = m.group(1)
            elif key == "campo": campo = m.group(1)

    # Filtrado inicial por columnas
    mask = pd.Series([True] * len(df))
    if codigo: mask &= df["CODIGO"].astype(str) == codigo
    if clase: mask &= df["Clase"].astype(str) == clase
    if registro: mask &= df["Normativa / Registro"].astype(str) == registro
    if campo: mask &= df["Campo Relacionado"].astype(str) == campo

    # Si no se encuentra nada con filtros numéricos, búsqueda por texto
    if not mask.any():
        mask = (
            df["CODIGO"].astype(str).apply(normalize_text).str.contains(q, na=False)
            | df["Error / Descripción"].astype(str).apply(normalize_text).str.contains(q, na=False)
            | df["Clase"].astype(str).apply(normalize_text).str.contains(q, na=False)
            | df["Normativa / Registro"].astype(str).apply(normalize_text).str.contains(q, na=False)
            | df["Campo Relacionado"].astype(str).apply(normalize_text).str.contains(q, na=False)
        )

    return df[mask]

@st.cache_data
def load_normative_snippets():
    """Carga fragmentos de documentos normativos"""
    base_text = ""
    data_dir = os.path.join(os.getcwd(), "data")
    if os.path.exists(data_dir):
        for fname in os.listdir(data_dir):
            path = os.path.join(data_dir, fname)
            if os.path.isfile(path):
                base_text += f"\n# === {fname} ===\n"
                try:
                    with open(path, "rb") as f:
                        content = f.read(80000)
                        base_text += f"[Fragmento cargado: {len(content)} bytes]"
                except Exception as e:
                    base_text += f"[Error al leer {fname}: {e}]"
    return base_text

def highlight_matches(row, query):
    """Resalta los campos que coinciden con la consulta"""
    q = normalize_text(query)
    def highlight_cell(val):
        val_norm = normalize_text(str(val))
        if val_norm and q and q in val_norm:
            return f"background-color: #FFFACD"  # amarillo claro
        return ""
    return row.apply(highlight_cell)

# =====================================
# INTERFAZ DE USUARIO
# =====================================
st.title("🧭 ADUAVIR 2.1.3 — Asistente Aduanal Inteligente")
st.markdown("Versión 2.1.3 | Catálogo enriquecido con búsqueda avanzada")

with st.spinner("Cargando catálogo y normativa..."):
    df_catalog = load_catalog()
    normative_context = load_normative_snippets()
st.success("✅ Catálogo y normativa cargados correctamente.")

query = st.text_input(
    "Ingrese el código o descripción del error:",
    placeholder="Ejemplo: 2 3 500 2 o tipo de cambio",
)

if st.button("🔍 Interpretar error"):
    if not query.strip():
        st.warning("Por favor ingrese un código o descripción válida.")
    else:
        results = search_error(df_catalog, query)

        if not results.empty:
            st.success(f"🔎 Se encontraron {len(results)} coincidencias:")

            display_columns = [
                "CODIGO",
                "Clase",
                "Normativa / Registro",
                "Campo Relacionado",
                "Error / Descripción",
                "Solución",
                "Ejemplo / Referencia",
                "Criterio Relacionado",
                "Llenado / Observaciones",
            ]

            # Resaltado de coincidencias
            styled_df = results[display_columns].reset_index(drop=True).style.apply(highlight_matches, query=query, axis=1)
            st.dataframe(styled_df)
        else:
            st.warning("⚠️ No se encontró el error en el catálogo.")

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.3 — Solo catálogo y normativa")