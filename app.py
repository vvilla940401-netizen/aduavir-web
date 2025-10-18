import streamlit as st
from helpers import interpret_error

st.set_page_config(page_title="ADUAVIR 2.0", layout="wide")

st.title("🧠 ADUAVIR 2.0 - Asistente Aduanal Inteligente")
st.write("Versión Beta de prueba | Interpretación de errores de validación y prevalidación")

error_code = st.text_input("Introduce el código de error:", "")

if st.button("Interpretar error"):
    if error_code.strip() == "":
        st.warning("Por favor ingresa un código de error válido.")
    else:
        with st.spinner("Interpretando error..."):
            result = interpret_error(error_code)
            st.success("Interpretación completa:")
            st.write(result)