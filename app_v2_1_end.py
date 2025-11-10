import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.3", page_icon="🧭", layout="wide")

# Carga variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# =====================================
# ESTILOS VISUALES
# =====================================
st.markdown(
    """
    <style>
    body {
        background-color: #f0f4f8;
        font-family: 'Segoe UI', sans-serif;
    }
    .main {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 25px;
        box-shadow: 0px 0px 12px rgba(0,0,0,0.08);
    }
    .titulo {
        background-color: #002b5c;
        color: white;
        padding: 18px;
        border-radius: 8px;
        text-align: center;
        font-size: 26px;
        font-weight: bold;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .subtitulo {
        color: #004b8d;
        font-size: 18px;
        margin-bottom: 25px;
        text-align: center;
    }
    .consulta {
        color: #002b5c;
        font-weight: bold;
        font-size: 16px;
        margin-top: 20px;
    }
    .watermark {
        position: fixed;
        bottom: 40%;
        right: 20%;
        opacity: 0.05;
        font-size: 100px;
        color: #003366;
        transform: rotate(-30deg);
        pointer-events: none;
        z-index: 0;
    }
    footer {visibility: hidden;}
    </style>
    <div class="titulo">🧭 ADUAVIR 2.1.3 — Asistente Aduanal Inteligente</div>
    <div class="subtitulo">Versión 2.1.3 | Interpretación de errores normativos</div>
    <div class="watermark">ADUAVIR</div>
    """,
    unsafe_allow_html=True
)

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================
@st.cache_data
def load_catalog():
    """Carga el catálogo de errores y normaliza encabezados."""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")
        def _norm_col(c):
            if not isinstance(c, str): c = str(c)
            s = unicodedata.normalize('NFKD', c.strip()).encode('ASCII', 'ignore').decode('ASCII')
            s = re.sub(r'[^a-zA-Z0-9]', '', s)
            return s.lower()
        df.columns = [_norm_col(c) for c in df.columns]
        return df
    except Exception as e:
        st.error(f"⚠️ No se pudo cargar el catálogo: {e}")
        return pd.DataFrame()

def normalize_text(text):
    if not isinstance(text, str): return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()

def search_error(df, query):
    """Filtra máximo 5 resultados relevantes."""
    q = normalize_text(query)
    if not q or df.empty:
        return df.iloc[0:0]
    cols = [c for c in df.columns if any(k in c for k in ("error", "descripcion", "solucion", "observacion", "campo"))]
    if not cols: return df.iloc[0:0]
    mask = pd.Series([False] * len(df), index=df.index)
    for col in cols:
        mask |= df[col].astype(str).apply(normalize_text).str.contains(q, na=False, regex=False)
    return df[mask].head(5)

# =====================================
# INTERFAZ DE USUARIO
# =====================================
with st.spinner("Cargando catálogo..."):
    df_catalog = load_catalog()

if df_catalog.empty:
    st.error("⚠️ No se pudo cargar el catálogo. Verifica el archivo Excel.")
else:
    st.success("✅ Catálogo cargado correctamente.")

query = st.text_input(
    "Ingrese el código o descripción del error:",
    placeholder="Ejemplo: línea de captura bloqueada o tipo de cambio incorrecto",
)

if st.button("🔍 Interpretar error"):
    if not query.strip():
        st.warning("Por favor ingrese una descripción válida.")
    else:
        results = search_error(df_catalog, query)

        if results is not None and not results.empty:
            st.markdown(f"<p class='consulta'>🔎 Consulta realizada: <b>{query}</b></p>", unsafe_allow_html=True)

            col_map = {
                "camporelacionado": "Campo Relacionado",
                "errordescripcion": "Error / Descripción",
                "solucion": "Solución",
                "observacion": "Observaciones"
            }
            cols_to_show = []
            for norm_col, display_name in col_map.items():
                for c in results.columns:
                    if norm_col in c:
                        cols_to_show.append((c, display_name))
                        break

            if cols_to_show:
                show_df = results[[c[0] for c in cols_to_show]]
                show_df.columns = [c[1] for c in cols_to_show]
                st.dataframe(show_df, use_container_width=True)
                st.info("🧩 Mostrando un máximo de 5 resultados relacionados con la consulta.")
            else:
                st.warning("⚠️ No se encontraron columnas esperadas en el catálogo.")
        else:
            st.warning("⚠️ No se encontró el error en el catálogo.")

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.3 — Solo catálogo y normativa")