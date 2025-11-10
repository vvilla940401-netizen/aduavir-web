import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.3", page_icon="🧭", layout="centered")

# Carga variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Clave solo desde .env o Render

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================

@st.cache_data
def load_catalog():
    """Carga el catálogo de errores unificado y normaliza encabezados."""
    try:
        df = pd.read_excel("catalogo_errores_unificado.xlsx", dtype=str).fillna("")

        # Normalizar nombres de columna
        def _norm_col(c):
            if not isinstance(c, str):
                c = str(c)
            s = c.strip()
            s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')  # quitar acentos
            s = re.sub(r'[^a-zA-Z0-9]', '', s)
            return s.lower()

        original_cols = list(df.columns)
        df.columns = [_norm_col(c) for c in df.columns]
        df._original_columns = original_cols
        return df
    except Exception as e:
        st.error(f"⚠️ No se pudo cargar el catálogo: {e}")
        return pd.DataFrame()


def normalize_text(text):
    """Normaliza texto para comparación flexible."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9áéíóúñü\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def search_error(df, query):
    """Busca coincidencias por texto libre."""
    q = normalize_text(query)
    if not q:
        return df.iloc[0:0]

    # columnas relevantes
    possible_cols = [c for c in df.columns if any(k in c for k in ("error", "descripcion", "solucion", "observacion", "campo"))]

    if not possible_cols:
        return df.iloc[0:0]

    mask = pd.Series([False] * len(df))
    for col in possible_cols:
        mask |= df[col].astype(str).apply(normalize_text).str.contains(q, na=False, regex=False)

    return df[mask]


# =====================================
# INTERFAZ DE USUARIO
# =====================================
st.markdown(
    """
    <style>
        body {background-color: #f4f6fa;}
        .main {background-color: white; border-radius: 10px; padding: 20px;}
        h1 {color: #003366;}
        footer {visibility: hidden;}
        .consulta {color: #003366; font-weight: bold; font-size: 16px;}
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🧭 ADUAVIR 2.1.3 — Asistente Aduanal Inteligente")
st.markdown("Versión 2.1.3 | Búsqueda de errores con interpretación asistida")

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
            # Mostrar solo las 5 coincidencias más relevantes
            limited_results = results.head(5).copy()

            # Mapeo de columnas normalizadas → nombres para mostrar
            col_map = {
                "camporelacionado": "Campo Relacionado",
                "errordescripcion": "Error / Descripción",
                "solucion": "Solución",
                "observacion": "Observaciones"
            }

            # Buscar las columnas disponibles
            cols_to_display = []
            for norm_col, display_name in col_map.items():
                for c in results.columns:
                    if norm_col in c:
                        cols_to_display.append((c, display_name))
                        break

            if cols_to_display:
                show_df = limited_results[[c[0] for c in cols_to_display]]
                show_df.columns = [c[1] for c in cols_to_display]

                st.markdown(f"<p class='consulta'>🔍 Consulta realizada: <b>{query}</b></p>", unsafe_allow_html=True)
                st.success(f"Se encontraron {len(results)} coincidencias. Mostrando las 5 más relevantes:")

                st.dataframe(show_df, use_container_width=True)
            else:
                st.warning("⚠️ No se encontraron columnas esperadas (Campo, Descripción, Solución, Observaciones).")
        else:
            st.warning("⚠️ No se encontró el error en el catálogo.")

st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.3 — Solo catálogo y normativa")