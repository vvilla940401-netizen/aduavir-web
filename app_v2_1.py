import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI

# ============================================
# CONFIGURACIÓN INICIAL
# ============================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

st.set_page_config(
    page_title="ADUAVIR 2.1 — Asistente Aduanal Inteligente",
    layout="centered",
    page_icon="📘"
)

st.title("📘 ADUAVIR 2.1 — Asistente Aduanal Inteligente")
st.markdown("""
Bienvenido al **Asistente Virtual Aduanal Inteligente (ADUAVIR)**.  
Esta versión permite buscar **por código de error o por texto del mensaje**.  
Además, usa el **catálogo enriquecido** para ofrecer explicaciones completas y fundamentos normativos.
""")

# ============================================
# CARGA DEL CATÁLOGO
# ============================================
CATALOGO_PATH = os.path.join(os.path.dirname(__file__), "catalogo_errores_unificado.xlsx")

@st.cache_data(show_spinner=True)
def load_catalog():
    try:
        df = pd.read_excel(CATALOGO_PATH, dtype=str).fillna("")
        return df
    except Exception as e:
        st.error(f"⚠️ No se pudo cargar el catálogo de errores: {e}")
        return pd.DataFrame()

catalog = load_catalog()
if catalog.empty:
    st.stop()

st.success(f"✅ Catálogo cargado correctamente ({len(catalog)} errores disponibles).")

# ============================================
# PANEL DE CONSULTA
# ============================================
st.subheader("🔍 Buscar error por código o texto")
query = st.text_input("Ingrese el código o texto del error:", placeholder="Ejemplo: E1140, campo no válido, fracción incorrecta...")

if st.button("Analizar error"):
    if not query.strip():
        st.warning("Por favor, ingrese un código o texto de error válido.")
    else:
        # Normalizamos la búsqueda
        query_lower = query.strip().lower()

        # Filtrar por coincidencia de código o texto
        resultados = catalog[catalog.apply(lambda row: query_lower in row.astype(str).str.lower().to_string(), axis=1)]

        if resultados.empty:
            st.error("No se encontró ninguna coincidencia exacta en el catálogo. Se intentará una interpretación con IA.")
        else:
            st.success(f"🔎 Se encontraron {len(resultados)} coincidencias.")
            st.dataframe(resultados, use_container_width=True)

        # ============================================
        # INTERPRETACIÓN CON OPENAI
        # ============================================
        if not OPENAI_API_KEY:
            st.error("⚠️ No se encontró la clave OPENAI_API_KEY en el archivo .env.")
        else:
            client = OpenAI(api_key=OPENAI_API_KEY)

            # Usar primeros registros relevantes como contexto
            contexto = ""
            for _, row in resultados.head(3).iterrows():
                contexto += f"\nDescripción: {row.get('descripcion_error', '')}\n"
                contexto += f"Clase: {row.get('clase', '')}\n"
                contexto += f"Solución sugerida: {row.get('solucion_ejemplo', '')}\n"
                contexto += f"Referencia normativa: {row.get('referencia_normativa', '')}\n"
                contexto += f"Criterio de llenado: {row.get('criterio_llenado', '')}\n"
                contexto += f"Observaciones: {row.get('observaciones', '')}\n---\n"

            prompt = f"""
Eres un asistente experto en comercio exterior y normativa aduanal mexicana.
Analiza el siguiente error y proporciona una explicación profesional pero clara, 
citando el fundamento normativo cuando sea posible (RGCE, Anexo 22, VOCE o catálogos SAAI).

Consulta del usuario: {query}

Contexto del catálogo (fragmentos relevantes):
{contexto}
"""

            with st.spinner("Consultando ADUAVIR con IA..."):
                try:
                    response = client.responses.create(
                        model="gpt-4o-mini",
                        input=prompt,
                        max_output_tokens=600
                    )
                    st.markdown("### 🧭 Interpretación generada por ADUAVIR:")
                    st.markdown(response.output_text.strip())

                except Exception as e:
                    st.error(f"⚠️ Ocurrió un error al consultar OpenAI: {e}")

st.markdown("---")
st.caption("Versión 2.1 — Desarrollado por Vanessa Villa © 2025 | Beta privada de prueba")