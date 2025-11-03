import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
from openai import OpenAI
import re

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.1", page_icon="🧠", layout="centered")
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

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
    """Busca coincidencias por código, texto o combinación numérica"""
    q = normalize_text(query)

    # Búsqueda por coincidencia parcial en columnas clave
    mask = (
        df["CODIGO"].astype(str).apply(normalize_text).str.contains(q, na=False)
        | df["Error / Descripción"].astype(str).apply(normalize_text).str.contains(q, na=False)
        | df["Clase"].astype(str).apply(normalize_text).str.contains(q, na=False)
        | df["Normativa / Registro"].astype(str).apply(normalize_text).str.contains(q, na=False)
    )

    results = df[mask]
    return results

def interpret_with_openai(query, base_context):
    """Consulta a OpenAI para generar una interpretación del error"""
    if not OPENAI_API_KEY:
        return "⚠️ No se encontró la clave OPENAI_API_KEY. No se puede usar la IA."
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = f"""
Eres un especialista en comercio exterior mexicano. Analiza el siguiente error o texto relacionado con validación o prevalidación aduanal.

Error o texto ingresado:
{query}

Base normativa de referencia (extracto):
{base_context[:2000]}

Responde con una explicación clara, técnica y profesional, citando fundamentos si los hay (RGCE, Anexo 22, VOCE).
"""
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            max_output_tokens=400,
        )
        return response.output_text.strip()
    except Exception as e:
        return f"⚠️ Ocurrió un error al consultar OpenAI: {e}"

@st.cache_data
def load_normative_snippets():
    """Carga extractos de documentos normativos"""
    base_text = ""
    data_dir = os.path.join(os.getcwd(), "data")
    for fname in os.listdir(data_dir):
        path = os.path.join(data_dir, fname)
        if os.path.isfile(path):
            base_text += f"\n=== {fname} ===\n"
            try:
                with open(path, "rb") as f:
                    content = f.read(100000)
                    base_text += f"[Fragmento cargado: {len(content)} bytes]"
            except Exception as e:
                base_text += f"[Error al leer {fname}: {e}]"
    return base_text

# =====================================
# INTERFAZ DE USUARIO
# =====================================
st.title("🧠 ADUAVIR 2.1.1 — Asistente Aduanal Inteligente")
st.markdown("Versión 2.1.1 | Búsqueda avanzada por código o texto | Catálogo enriquecido y razonamiento IA")

# Cargar catálogo y normativa
with st.spinner("Cargando catálogo y normativa..."):
    df_catalog = load_catalog()
    normative_context = load_normative_snippets()
st.success("✅ Catálogo y normativa cargados correctamente.")

# Entrada del usuario
query = st.text_input("Ingrese el código o descripción del error:", placeholder="Ejemplo: 2 3 500 2 o tipo de cambio")

if st.button("🔍 Interpretar error"):
    if not query.strip():
        st.warning("Por favor ingrese un código o descripción válida.")
    else:
        results = search_error(df_catalog, query)

        if not results.empty:
            st.success(f"🔎 Se encontraron {len(results)} coincidencias en el catálogo:")
            for idx, row in results.iterrows():
                st.markdown("---")
                st.markdown(f"**Código:** {row.get('CODIGO', '')}")
                st.markdown(f"**Clase:** {row.get('Clase', '')}")
                st.markdown(f"**Descripción:** {row.get('Error / Descripción', '')}")
                st.markdown(f"**Normativa / Registro:** {row.get('Normativa / Registro', '')}")
                st.markdown(f"**Solución / Recomendación:** {row.get('Solución / Recomendación', '')}")
                st.markdown(f"**Referencia Normativa:** {row.get('Referencia Normativa', '')}")
                st.markdown(f"**Criterio de Llenado:** {row.get('Criterio de Llenado', '')}")
                st.markdown(f"**Llenado / Observaciones:** {row.get('Llenado / Observaciones', '')}")
                st.markdown(f"**Razonamiento:** {row.get('RAZONAMIENTO', '')}")
        else:
            st.warning("⚠️ No se encontró el error en el catálogo. Consultando con la IA...")
            interpretation = interpret_with_openai(query, normative_context)
            st.markdown("### 💡 Interpretación generada por ADUAVIR IA")
            st.markdown(interpretation)

# =====================================
# PIE DE PÁGINA
# =====================================
st.markdown("---")
st.caption("Desarrollado por Vanessa Villa © 2025 | ADUAVIR v2.1.1 — Beta privada de prueba")