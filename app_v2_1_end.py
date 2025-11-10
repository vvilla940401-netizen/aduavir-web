import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN GENERAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.2", page_icon="🧭", layout="wide")

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =====================================
# ESTILOS CSS PERSONALIZADOS
# =====================================
st.markdown("""
    <style>
        body {
            background: linear-gradient(180deg, #f7f9fc 0%, #eef2f7 100%);
            font-family: 'Segoe UI', sans-serif;
        }
        .main {
            background-color: rgba(255, 255, 255, 0.95);
            padding: 25px 40px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        h1, h2, h3 {
            color: #003366;
            text-align: center;
        }
        .stTextInput>div>div>input {
            font-size: 18px;
            padding: 10px;
        }
        .stDataFrame {
            border-radius: 10px;
        }
        footer, .st-emotion-cache-czk5ss, .stDeployButton, header {
            visibility: hidden;
        }
        .watermark {
            position: fixed;
            bottom: 40%;
            right: 30%;
            opacity: 0.08;
            font-size: 120px;
            color: #003366;
            transform: rotate(-30deg);
            z-index: -1;
            user-select: none;
        }
    </style>
    <div class="watermark">ADUAVIR</div>
""", unsafe_allow_html=True)

# =====================================
# FUNCIONES
# =====================================
@st.cache_data
def load_catalog():
    """Carga el catálogo de errores y normaliza columnas"""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")
        df.columns = [re.sub(r'[^a-zA-Z0-9]', '', unicodedata.normalize('NFKD', str(c)).encode('ASCII', 'ignore').decode('ASCII')).lower() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"⚠️ No se pudo cargar el catálogo: {e}")
        return pd.DataFrame()

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def search_error(df, query):
    """Filtra coincidencias limitadas a 5 resultados relevantes"""
    q = normalize_text(query)
    if not q or df.empty:
        return df.iloc[0:0]

    candidate_cols = [c for c in df.columns if any(k in c for k in ("error", "descripcion", "solucion", "observac", "campo"))]
    mask = pd.Series([False] * len(df), index=df.index)
    for col in candidate_cols:
        mask |= df[col].astype(str).apply(normalize_text).str.contains(q, na=False, regex=False)
    results = df[mask].copy()
    return results.head(5)

# =====================================
# INTERFAZ
# =====================================
st.markdown("<h1>🧭 ADUAVIR 2.2 — Asistente Aduanal Inteligente</h1>", unsafe_allow_html=True)
st.markdown("<h3>Catálogo optimizado con búsqueda avanzada</h3>", unsafe_allow_html=True)

df_catalog = load_catalog()
if df_catalog.empty:
    st.error("⚠️ No se pudo cargar el catálogo. Verifica el archivo Excel.")
else:
    st.success("✅ Catálogo cargado correctamente.")

query = st.text_input("Ingrese el código o descripción del error:", placeholder="Ejemplo: tipo de cambio o campo 6")

if st.button("🔍 Buscar"):
    if not query.strip():
        st.warning("Por favor ingrese una descripción o código válido.")
    else:
        results = search_error(df_catalog, query)
        if not results.empty:
            st.markdown(f"### 🔎 Resultado para: **{query}**")
            
            # Mostrar solo las columnas principales
            cols_to_show = [c for c in results.columns if any(k in c for k in ("campo", "error", "descripcion", "solucion", "observac"))]
            safe_view = results[cols_to_show].head(5)
            
            st.dataframe(
                safe_view,
                height=350,
                use_container_width=True
            )
        else:
            st.warning("⚠️ No se encontraron coincidencias para tu búsqueda.")

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.2 — Catálogo y normativa inteligente")