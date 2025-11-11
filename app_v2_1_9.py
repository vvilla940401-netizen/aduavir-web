# app_v2_1_9.py
import streamlit as st
import pandas as pd
import os
import re
import unicodedata
from datetime import datetime
from dotenv import load_dotenv
import io

# ===========================
# CONFIG INICIAL
# ===========================
st.set_page_config(page_title="ADUAVIR 2.1.9", page_icon="🧭", layout="wide")
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Usuario compartido (cambiar si es necesario)
SINGLE_USER = {"user": "aduavir_admin", "password": "aduavir2025"}

# Rutas / recursos
CATALOG_PATH = "catalogo_errores_unificado_CORREGIDO.xlsx"
LOG_PATH = "consultas_log.csv"
# Logo público en github (útil en Render). Cambia si prefieres ruta local.
LOGO_URL = "https://raw.githubusercontent.com/vvilla940401-netizen/aduavir-web/main/assets/logo_aduavir.png"

# ===========================
# ESTILOS Y HEADER
# ===========================
st.markdown(
    """
    <style>
    :root { --main-blue: #003366; --muted: #4b6b8a; }
    .header { display:flex; align-items:center; gap:18px; padding:8px 0; }
    .header img { height:72px; border-radius:6px; }
    .app-title { color:var(--main-blue); font-size:24px; margin:0; }
    .app-sub { color:var(--muted); margin:0; font-size:14px; }
    .block { background: rgba(255,255,255,0.98); padding:18px; border-radius:12px; box-shadow:0 6px 18px rgba(0,0,0,0.06); }
    [data-testid="stAppViewContainer"] { background-color:#f5f6fa; }
    .watermark { position: fixed; bottom: 28%; right: 22%; opacity:0.06; z-index:0; font-size:160px; color: #003366; transform: rotate(-30deg); }
    .result-card { background:#fff; padding:14px; border-radius:10px; margin-bottom:12px; }
    .small-muted { color:#7b8a9a; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header con logo remoto (Render-friendly)
st.markdown(
    f"""
    <div class="header">
        <img src="{LOGO_URL}" alt="logo">
        <div>
            <h1 class="app-title">🧭 ADUAVIR 2.1.9</h1>
            <div class="app-sub">Su aliado en el cumplimiento</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="watermark">ADUAVIR</div>', unsafe_allow_html=True)

# ===========================
# UTILIDADES: carga/normalización
# ===========================
@st.cache_data
def load_catalog(path=CATALOG_PATH):
    """Carga el catálogo y normaliza encabezados a claves simples."""
    try:
        df = pd.read_excel(path, dtype=str).fillna("")
    except Exception as e:
        st.error(f"⚠️ Error cargando catálogo: {e}")
        return pd.DataFrame()

    def _norm_col(c):
        s = str(c).strip()
        s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
        s = re.sub(r"[^A-Za-z0-9]", "", s).lower()
        return s

    # guardar mapeo normalizado -> original (para mostrar nombres bonitos)
    orig_cols = list(df.columns)
    norm_cols = [_norm_col(c) for c in orig_cols]
    df.columns = norm_cols
    df._orig_map = {n: o for n, o in zip(norm_cols, orig_cols)}
    return df

def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    s = text.lower()
    s = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# ===========================
# LÓGICA DE BÚSQUEDA
# ===========================
def detect_column_filter(q: str):
    """
    Detecta si el usuario especificó 'registro 701', 'campo 3', 'tipo 1', 'codigo 1', etc.
    Retorna (col_key, value) o (None, None)
    """
    qnorm = q.lower()
    # mapear variantes a claves normalizadas
    col_aliases = {
        "registro": ["registro", "reg"],
        "campo": ["campo", "cam"],
        "codigo": ["codigo", "cod"],
        "tipo": ["tipo", "clase"],  # aceptamos que user cambie 'clase' por 'tipo'
    }
    for key, aliases in col_aliases.items():
        for a in aliases:
            # patrón: "registro 701" o "registro:701" o "registro=701"
            m = re.search(rf"\b{re.escape(a)}\b\W*(\d+)\b", qnorm)
            if m:
                return key, m.group(1)
    return None, None

def parse_numeric_sequence(q: str):
    """
    Si el usuario escribe una secuencia numérica tipo '1 3 353 6' o '133536' (sin espacios),
    intentamos extraer 4 números: codigo, tipo, registro, campo.
    Retorna dict con keys encontradas, p.e. {'codigo':'1','tipo':'3','registro':'353','campo':'6'}
    """
    nums = re.findall(r"\d+", q)
    if len(nums) >= 4:
        return {"codigo": nums[0], "tipo": nums[1], "registro": nums[2], "campo": nums[3]}
    # caso de cadena continua con 6 dígitos (ej: 133536) — intentar partir: 1,3,353,6
    joined = re.sub(r"\D", "", q)
    if len(joined) >= 6:
        # heurística: 1 digit codigo, 1 digit tipo, 3 digits registro, rest field (last digit)
        # solo aplicar si exactamente 6 digits
        if len(joined) == 6:
            return {"codigo": joined[0], "tipo": joined[1], "registro": joined[2:5], "campo": joined[5]}
    return {}

def search_error(df: pd.DataFrame, query: str, limit: int = 25) -> pd.DataFrame:
    """
    Búsqueda principal:
      - Si se detecta un filtro por columna ('registro 701') -> filtra esa columna exactamente.
      - Si se detecta secuencia numérica de 4 valores -> aplica filtros compuestos.
      - Si no, realiza búsqueda de texto en columnas relevantes (descripcion, solucion, observaciones).
    """
    if df is None or df.empty or not query or not str(query).strip():
        return df.iloc[0:0]

    q = query.strip()
    qnorm = normalize_text(q)

    # columnas clave en tu Excel (normalizadas)
    expected_keys = {
        "codigo": "codigo",
        "tipo": "tipo",
        "registro": "registro",
        "campo": "campo",
        "descripcion": "descripciondeerror",  # según tu encabezado "DESCRIPCION DE ERROR"
        "solucion": "solucion",
        "observacion": "observacionejemplo"  # si existe; habrá fallback a 'ejemplo' o 'llenadoobservaciones'
    }

    # detectar filtros claros
    col_key, col_value = detect_column_filter(q)
    seq = parse_numeric_sequence(q)

    # helper para comprobar columna real en df (normalizada)
    def find_col(possible_names):
        for p in possible_names:
            if p in df.columns:
                return p
        return None

    # tratar caso: secuencia 4 números (codigo,tipo,registro,campo)
    if seq:
        mask = pd.Series([True] * len(df), index=df.index)
        if "codigo" in seq:
            c = find_col([expected_keys["codigo"], "codigo"])
            if c is not None:
                mask &= df[c].astype(str).str.strip() == str(seq["codigo"])
        if "tipo" in seq:
            c = find_col([expected_keys["tipo"], "tipo", "clase"])
            if c is not None:
                mask &= df[c].astype(str).str.strip() == str(seq["tipo"])
        if "registro" in seq:
            c = find_col([expected_keys["registro"], "registro"])
            if c is not None:
                mask &= df[c].astype(str).str.strip() == str(seq["registro"])
        if "campo" in seq:
            c = find_col([expected_keys["campo"], "campo"])
            if c is not None:
                mask &= df[c].astype(str).str.strip() == str(seq["campo"])
        res = df[mask]
        return res.head(limit)

    # tratar caso: filtro por columna explícito (ej: "registro 701")
    if col_key:
        colname_map = {
            "registro": [expected_keys["registro"], "registro"],
            "campo": [expected_keys["campo"], "campo"],
            "codigo": [expected_keys["codigo"], "codigo"],
            "tipo": [expected_keys["tipo"], "tipo", "clase"]
        }
        desired_cols = colname_map.get(col_key, [])
        col_real = find_col(desired_cols)
        if col_real:
            mask = df[col_real].astype(str).str.strip() == str(col_value)
            return df[mask].head(limit)
        else:
            # no encontró la columna en el catálogo -> devolver vacío
            return df.iloc[0:0]

    # Si llegamos aquí -> búsqueda de texto libre y por números sueltos en columnas relevantes
    # columnas relevantes: descripcion, solucion, observacion/ejemplo, tipo, registro, campo, codigo
    candidate_cols = []
    # priorizamos las columnas con nombres esperados del catálogo
    for k in ["descripciondeerror", "descripcion", "errordescripcion", "solucion", "observacionejemplo", "ejemplo", "llenadoobservaciones", "tipo", "registro", "campo", "codigo"]:
        if k in df.columns and k not in candidate_cols:
            candidate_cols.append(k)
    if not candidate_cols:
        candidate_cols = list(df.columns)

    mask = pd.Series([False] * len(df), index=df.index)

    # búsqueda literal (texto normalizado) en candidate_cols
    for c in candidate_cols:
        try:
            mask |= df[c].astype(str).apply(normalize_text).str.contains(qnorm, na=False)
        except Exception:
            # if normalize or contains fails, fallback safe contains
            try:
                mask |= df[c].astype(str).str.contains(q, na=False, regex=False)
            except Exception:
                pass

    # también buscar números sueltos (ej. 701) en candidate_cols
    nums = re.findall(r"\d+", q)
    for n in nums:
        for c in candidate_cols:
            try:
                mask |= df[c].astype(str).str.contains(n, na=False, regex=False)
            except Exception:
                pass

    results = df[mask].copy()
    return results.head(limit)

# ===========================
# BITÁCORA (LOG) DE CONSULTAS
# ===========================
def log_query(user: str, columna: str, consulta: str, resultados: int):
    """Registra la consulta en consultas_log.csv (append)."""
    row = {
        "fecha_hora": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "usuario": user,
        "columna_filtrada": columna if columna else "",
        "consulta": consulta,
        "resultados": int(resultados),
    }
    df_row = pd.DataFrame([row])
    # si no existe archivo, crearlo con header; si existe, append sin header
    if not os.path.exists(LOG_PATH):
        df_row.to_csv(LOG_PATH, index=False, encoding="utf-8-sig")
    else:
        df_row.to_csv(LOG_PATH, index=False, mode="a", header=False, encoding="utf-8-sig")

def get_log_bytesio():
    """Devuelve el CSV de log listo para descargar."""
    if not os.path.exists(LOG_PATH):
        return None
    with open(LOG_PATH, "rb") as f:
        data = f.read()
    return io.BytesIO(data)

# ===========================
# LOGIN SIMPLE
# ===========================
def simple_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user = ""
    if st.session_state.logged_in:
        return True

    st.markdown("<div class='block'>", unsafe_allow_html=True)
    st.write("**Acceso restringido — área de pruebas**")
    user = st.text_input("Usuario")
    pwd = st.text_input("Contraseña", type="password")
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Ingresar"):
            if user == SINGLE_USER["user"] and pwd == SINGLE_USER["password"]:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.experimental_rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    with col2:
        st.write("")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# Ejecutar login
simple_login()

# ===========================
# APP: ejecución principal
# ===========================
st.markdown("<div class='block'>", unsafe_allow_html=True)
with st.spinner("Cargando catálogo..."):
    df_catalog = load_catalog()

if df_catalog.empty:
    st.error("No se pudo cargar el catálogo. Verifica el archivo corregido en la raíz del repo.")
    st.stop()

st.success(f"Catálogo cargado ({len(df_catalog)} filas).")

query = st.text_input("Ingrese código, registro o descripción:", placeholder="Ejemplo: 1 3 353 6 | registro 701 | tipo 1 | describir el error")
st.markdown("")

col1, col2, col3 = st.columns([3, 1, 1])
with col2:
    if st.button("Buscar"):
        current_user = st.session_state.get("user", SINGLE_USER["user"])
        results = search_error(df_catalog, query, limit=25)
        # determinar columna filtrada para registrar (si aplica)
        detected_col, detected_val = detect_column_filter(query)
        seq = parse_numeric_sequence(query)
        column_for_log = ""
        if detected_col:
            column_for_log = f"{detected_col}:{detected_val}"
        elif seq:
            # log which numeric pieces were included
            column_for_log = ",".join([f"{k}:{v}" for k, v in seq.items()])

        st.markdown('<div class="result-card">', unsafe_allow_html=True)
        if results is not None and not results.empty:
            # columnas a mostrar (en este orden) — mapear a nombres originales cuando estén
            prefer = ["tipo", "registro", "campo", "descripciondeerror", "solucion", "observacionejemplo", "ejemplo", "llenadoobservaciones"]
            show_cols = [c for c in prefer if c in results.columns]
            # rename to human-friendly headers (usar originales si tenemos mapping)
            rename_map = {}
            for c in show_cols:
                orig = df_catalog._orig_map.get(c, c)
                # reemplazar nombres largos por los finales requeridos
                if c == "descripciondeerror" and "DESCRIPCION DE ERROR" in orig.upper():
                    nice = "DESCRIPCION DE ERROR"
                elif c == "observacionejemplo" or c == "ejemplo":
                    nice = "OBSERVACION/EJEMPLO"
                else:
                    nice = orig
                rename_map[c] = nice

            display_df = results[show_cols].reset_index(drop=True).rename(columns=rename_map)
            st.markdown(f"**Consulta:** {query}")
            st.write(f"Se encontraron **{len(results)}** coincidencias (mostrando hasta 25).")
            st.dataframe(display_df, use_container_width=True, height=420)
            # registrar en log
            log_query(current_user, column_for_log, query, len(results))
        else:
            st.warning("No se encontraron coincidencias para la consulta.")
            log_query(current_user, column_for_log, query, 0)
        st.markdown("</div>", unsafe_allow_html=True)

with col3:
    st.write("")  # espacio
    # Botón para descargar log
    log_bio = get_log_bytesio()
    if log_bio is not None:
        st.download_button("📥 Descargar bitácora de consultas (CSV)", data=log_bio, file_name="consultas_log.csv", mime="text/csv")
    else:
        st.info("Aún no hay registros en la bitácora.")

st.markdown("---")
st.caption("ADUAVIR — Plataforma interna de consulta © 2025")