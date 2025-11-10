import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.4", page_icon="🧭", layout="centered")

# Carga variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================

@st.cache_data
def load_catalog():
    """Carga el catálogo de errores unificado y normaliza encabezados."""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")
        def _norm_col(c):
            if not isinstance(c, str):
                c = str(c)
            s = unicodedata.normalize('NFKD', c).encode('ASCII', 'ignore').decode('ASCII')
            s = re.sub(r'[^a-zA-Z0-9]', '', s).lower()
            return s
        df.columns = [_norm_col(c) for c in df.columns]
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
    """Busca coincidencias flexibles por texto o formato numérico."""
    if df.empty or not query.strip():
        return df.iloc[0:0]

    q = normalize_text(query)
    if not q:
        return df.iloc[0:0]

    # Extrae posibles números (ej. 1 3 353 6)
    nums = re.findall(r"\d+", q)

    # columnas que pueden contener la información
    cols = df.columns
    possible_cols = [c for c in cols if any(k in c for k in ["codigo", "clase", "registro", "campo", "error", "descripcion", "solucion", "observaciones"])]

    mask = pd.Series([False] * len(df), index=df.index)

    # Búsqueda por texto general
    for col in possible_cols:
        try:
            mask |= df[col].astype(str).apply(normalize_text).str.contains(q, regex=False, na=False)
        except Exception:
            pass

    # Búsqueda por números (combinaciones 1 3 353 6)
    if nums:
        for num in nums:
            for col in possible_cols:
                try:
                    mask |= df[col].astype(str).str.contains(num, regex=False, na=False)
                except Exception:
                    pass

    results = df[mask]
    return results.head(5)  # máximo 5 resultados

# =====================================
# INTERFAZ DE USUARIO
# =====================================
# Fondo con estilo CSS
page_bg = """
<style>
[data-testid="stAppViewContainer"] {
    background-color: #f5f6fa;
}
[data-testid="stHeader"] {
    background: none;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
.result-box {
    background-color: white;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0px 4px 8px rgba(0,0,0,0.1);
}
h1, h2, h3, h4 {
    text-align: center;
    color: #003366;
}
</style>
"""
st.markdown(page_bg, unsafe_allow_html=True)

# Título principal
st.markdown("<h1>🧭 ADUAVIR 2.1.4</h1>", unsafe_allow_html=True)
st.markdown("<h4>Su aliado en el cumplimiento</h4>", unsafe_allow_html=True)
st.markdown("---")

with st.spinner("Cargando catálogo y normativa..."):
    df_catalog = load_catalog()

if df_catalog.empty:
    st.error("⚠️ No se pudo cargar el catálogo. Verifica el archivo Excel.")
else:
    st.success("✅ Catálogo cargado correctamente.")

# Campo de búsqueda
query = st.text_input(
    "Ingrese el código o descripción del error:",
    placeholder="Ejemplo: 1 3 353 6 o tipo de cambio",
)

if st.button("🔍 Consultar error"):
    if not query.strip():
        st.warning("Por favor ingrese un código o descripción válida.")
    else:
        results = search_error(df_catalog, query)

        st.markdown("<div class='result-box'>", unsafe_allow_html=True)

        if results is not None and not results.empty:
            st.markdown(f"### 🔎 Resultados para: **{query}**")
            st.write(f"Se encontraron **{len(results)} coincidencias** (máximo 5 mostradas).")

            # Mostrar solo columnas clave
            columnas = ["camporelacionado", "errordescripcion", "solucion", "llenadoobservaciones"]
            columnas = [c for c in columnas if c in results.columns]

            if columnas:
                show_df = results[columnas].reset_index(drop=True)
                st.dataframe(show_df, use_container_width=True, hide_index=True)
            else:
                st.warning("⚠️ No se encontraron columnas esperadas en el catálogo.")
        else:
            st.warning("⚠️ No se encontró el error en el catálogo.")

        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.4 — Solo catálogo y normativa")