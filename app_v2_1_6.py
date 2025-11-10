import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.6", page_icon="🧭", layout="centered")

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================

@st.cache_data
def load_catalog():
    """Carga el catálogo y normaliza los encabezados para evitar errores por acentos o espacios."""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")
        def _norm_col(c):
            s = str(c).strip()
            s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
            s = re.sub(r'[^a-zA-Z0-9]', '', s).lower()
            return s
        df.columns = [_norm_col(c) for c in df.columns]
        return df
    except Exception as e:
        st.error(f"⚠️ No se pudo cargar el catálogo: {e}")
        return pd.DataFrame()

def normalize_text(text):
    """Quita acentos, símbolos y normaliza espacios."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def search_error(df, query):
    """Búsqueda flexible: acepta texto libre, números, y combinaciones."""
    if df.empty or not query.strip():
        return df.iloc[0:0]

    q = normalize_text(query)
    nums = re.findall(r"\d+", q)
    tokens = q.split()

    # columnas de interés
    possible_cols = [c for c in df.columns if any(k in c for k in [
        "codigo", "clase", "registro", "campo", "error", "descripcion", "solucion", "observaciones"
    ])]

    mask = pd.Series([False] * len(df), index=df.index)

    # 1️⃣ búsqueda por texto completo
    for col in possible_cols:
        mask |= df[col].astype(str).apply(normalize_text).str.contains(q, na=False)

    # 2️⃣ búsqueda por números sueltos
    for num in nums:
        for col in possible_cols:
            mask |= df[col].astype(str).str.contains(num, na=False, regex=False)

    # 3️⃣ búsqueda por tokens (palabras clave, como “igi”, “declared”, etc.)
    for token in tokens:
        for col in possible_cols:
            mask |= df[col].astype(str).apply(normalize_text).str.contains(token, na=False)

    results = df[mask]
    return results.head(5)

# =====================================
# INTERFAZ DE USUARIO
# =====================================
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-color: #f5f6fa;
    background-image: radial-gradient(circle at top left, #e3e8f0, #f5f6fa);
}
[data-testid="stHeader"] { background: none; }
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
.result-box {
    background-color: white;
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
}
h1, h4 { text-align: center; color: #003366; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🧭 ADUAVIR 2.1.6</h1>", unsafe_allow_html=True)
st.markdown("<h4>Su aliado en el cumplimiento</h4>", unsafe_allow_html=True)
st.markdown("---")

with st.spinner("Cargando catálogo..."):
    df_catalog = load_catalog()

if df_catalog.empty:
    st.error("⚠️ No se pudo cargar el catálogo. Verifica el archivo Excel.")
else:
    st.success("✅ Catálogo cargado correctamente.")

query = st.text_input(
    "Ingrese el código o descripción del error:",
    placeholder="Ejemplo: 1 3 353 6, registro 701 o tipo de cambio"
)

if st.button("🔍 Consultar error"):
    if not query.strip():
        st.warning("Por favor ingrese una búsqueda válida.")
    else:
        results = search_error(df_catalog, query)
        st.markdown("<div class='result-box'>", unsafe_allow_html=True)

        if not results.empty:
            st.markdown(f"### 🔎 Resultados para: **{query}**")
            st.write(f"Se encontraron **{len(results)} coincidencias** (máximo 5 mostradas).")

            columnas = ["camporelacionado", "errordescripcion", "solucion", "llenadoobservaciones"]
            columnas = [c for c in columnas if c in results.columns]

            if columnas:
                st.dataframe(results[columnas].reset_index(drop=True), use_container_width=True)
            else:
                st.warning("⚠️ No se encontraron las columnas esperadas en el catálogo.")
        else:
            st.warning("⚠️ No se encontró el error en el catálogo.")

        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.6 — Solo catálogo y normativa")