import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from dotenv import load_dotenv

# =====================================
# CONFIGURACIÓN INICIAL
# =====================================
st.set_page_config(page_title="ADUAVIR 2.1.7", page_icon="🧭", layout="wide")

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# -------------------------------------
# CONFIG: credenciales (usuario compartido)
# -------------------------------------
SINGLE_USER = {"user": "aduavir_admin", "password": "aduavir2025"}

# Ruta del catálogo corregido (asegúrate de subirlo al repo)
CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
# Logo en assets
LOGO_PATH = "assets/logo_aduavir.png"

# =====================================
# ESTILOS Y HEADER
# =====================================
st.markdown("""
<style>
:root { --main-blue: #003366; --muted: #4b6b8a; }
.header {
  display:flex; align-items:center; gap:18px; padding:8px 0;
}
.header img { height:72px; border-radius:6px; }
.app-title { color:var(--main-blue); font-size:24px; margin:0; }
.app-sub { color:var(--muted); margin:0; font-size:14px; }
.block { background: rgba(255,255,255,0.98); padding:18px; border-radius:12px; box-shadow:0 6px 18px rgba(0,0,0,0.06); }
[data-testid="stAppViewContainer"] { background-color:#f5f6fa; }
.watermark {
  position: fixed; bottom: 28%; right: 22%; opacity:0.06; z-index:0; font-size:160px; color: #003366; transform: rotate(-30deg);
}
.result-card { background:#fff; padding:14px; border-radius:10px; margin-bottom:12px; }
.small-muted { color:#7b8a9a; font-size:13px; }
</style>
""", unsafe_allow_html=True)

# header with logo (only show if logo exists)
logo_html = ""
if os.path.exists(LOGO_PATH):
    logo_html = f'<div class="header"><img src="{LOGO_PATH}" alt="logo"><div><h1 class="app-title">ADUAVIR 2.1.7</h1><div class="app-sub">Su aliado en el cumplimiento</div></div></div>'
else:
    logo_html = '<div class="header"><div><h1 class="app-title">ADUAVIR 2.1.7</h1><div class="app-sub">Su aliado en el cumplimiento</div></div></div>'
st.markdown(logo_html, unsafe_allow_html=True)
st.markdown('<div class="watermark">ADUAVIR</div>', unsafe_allow_html=True)

# =====================================
# FUNCIONES DE UTILIDAD
# =====================================
@st.cache_data
def load_catalog(path=CATALOG_PATH):
    """Carga catálogo corregido (archivo preparado)"""
    try:
        df = pd.read_excel(path, dtype=str).fillna("")
        # normalizar columna names a clave simple (por si quedan variaciones)
        def _norm_col(c):
            s = str(c).strip()
            s = unicodedata.normalize('NFKD', s).encode('ASCII','ignore').decode('ASCII')
            s = re.sub(r'[^A-Za-z0-9]', '', s).lower()
            return s
        df.columns = [_norm_col(c) for c in df.columns]
        return df
    except Exception as e:
        st.error(f"⚠️ Error cargando catálogo: {e}")
        return pd.DataFrame()

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    s = text.lower()
    s = unicodedata.normalize('NFKD', s).encode('ASCII','ignore').decode('ASCII')
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def search_error(df, query, max_results=5):
    """Búsqueda robusta: acepta combos numéricos y texto parcial."""
    if df.empty or not query or not str(query).strip():
        return df.iloc[0:0]
    q = normalize_text(query)
    nums = re.findall(r"\d+", q)
    tokens = [t for t in q.split() if t]

    # columnas de interés (normalizadas)
    cols = [c for c in df.columns if any(k in c for k in ("codigo","clase","registro","campo","error","descripcion","solucion","observaciones"))]
    if not cols:
        cols = list(df.columns)

    mask = pd.Series([False]*len(df), index=df.index)

    # 1) búsqueda literal en columnas relevantes (texto normalizado)
    for c in cols:
        try:
            mask |= df[c].astype(str).apply(normalize_text).str.contains(q, na=False)
        except Exception:
            pass

    # 2) búsqueda por números individuales (701 etc)
    for n in nums:
        for c in cols:
            try:
                # comparar como texto literal
                mask |= df[c].astype(str).str.contains(n, na=False, regex=False)
            except Exception:
                pass

    # 3) búsqueda por tokens (cada palabra)
    for t in tokens:
        for c in cols:
            try:
                mask |= df[c].astype(str).apply(normalize_text).str.contains(t, na=False)
            except Exception:
                pass

    results = df[mask].copy()
    if results.empty:
        return results.head(0)
    return results.head(max_results)

# =====================================
# LOGIN SIMPLIFICADO (UN USUARIO COMPARTIDO)
# =====================================
def simple_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if st.session_state.logged_in:
        return True

    st.markdown("<div class='block'>", unsafe_allow_html=True)
    st.write("**Acceso restringido — área de pruebas**")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    col1, col2 = st.columns([1,2])
    with col1:
        if st.button("Ingresar"):
            if user == SINGLE_USER["user"] and pwd == SINGLE_USER["password"]:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    with col2:
        st.write(" ")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# Ejecutar login
simple_login()

# =====================================
# APP: carga y búsqueda
# =====================================
st.markdown("<div class='block'>", unsafe_allow_html=True)
with st.spinner("Cargando catálogo..."):
    df_catalog = load_catalog()

if df_catalog.empty:
    st.error("No se pudo cargar el catálogo. Verifica que el archivo corregido esté en la raíz del repo.")
    st.stop()

st.success(f"Catálogo cargado ({len(df_catalog)} filas).")

query = st.text_input("Ingrese código, registro o descripción:", placeholder="Ejemplo: 1 3 353 6 | registro 701 | tipo de cambio")
st.markdown("")

if st.button("Buscar"):
    if not query or not query.strip():
        st.warning("Por favor ingrese una búsqueda válida.")
    else:
        results = search_error(df_catalog, query)
        st.markdown('<div class="result-card">', unsafe_allow_html=True)
        if results is not None and not results.empty:
            st.markdown(f"**Consulta:** {query}")
            st.write(f"Se encontraron **{len(results)}** coincidencias (mostrando hasta 5).")
            # elegir columnas para mostrar (si existen)
            preferred = ["registro","codigo","clase","camporelacionado","errordescripcion","solucion","llenadoobservaciones","ejemplo","criteriorelacionado"]
            show_cols = [c for c in preferred if c in results.columns]
            if not show_cols:
                show_cols = list(results.columns[:6])
            display_df = results[show_cols].reset_index(drop=True)
            st.dataframe(display_df, use_container_width=True, height=360)
        else:
            st.warning("No se encontraron coincidencias para la consulta.")
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
st.caption("ADUAVIR — Plataforma interna de consulta © 2025")