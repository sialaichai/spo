import streamlit as st
import os
import subprocess
from streamlit_pdf_viewer import pdf_viewer

# --- Configuration ---
TOPICS_DIR = "topics"
TEMP_DIR = "temp_build"
os.makedirs(TEMP_DIR, exist_ok=True)

st.set_page_config(page_title="Physics Topics", layout="wide")

# --- Helper Functions ---
def get_topics():
    if not os.path.exists(TOPICS_DIR): return []
    return sorted([d for d in os.listdir(TOPICS_DIR) if os.path.isdir(os.path.join(TOPICS_DIR, d))])

def get_tex_files(topic):
    topic_path = os.path.join(TOPICS_DIR, topic)
    return sorted([f for f in os.listdir(topic_path) if f.endswith(".tex")])

def compile_latex(file_path):
    file_name = os.path.basename(file_path)
    job_name = os.path.splitext(file_name)[0]
    
    try:
        process = subprocess.run(
            [
                "pdflatex", 
                "-interaction=nonstopmode", 
                f"-output-directory={TEMP_DIR}",
                f"-jobname={job_name}",
                file_path
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        pdf_path = os.path.join(TEMP_DIR, f"{job_name}.pdf")
        if process.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path, None
        else:
            return None, process.stdout
    except Exception as e:
        return None, str(e)

# --- Sidebar Navigation ---
st.sidebar.title("Physics Archive")

topics = get_topics()
if not topics:
    st.sidebar.error("No topics found.")
    st.stop()

# 1. Topic Selection (Dropdown)
selected_topic = st.sidebar.selectbox("Select Topic", topics)

st.sidebar.markdown("---") 

# 2. Document Selection (Radio List)
tex_files = get_tex_files(selected_topic)

if not tex_files:
    st.sidebar.warning("No files in this topic.")
    st.stop()

selected_file = st.sidebar.radio(f"Documents in {selected_topic}", tex_files)


# --- Auto-Compilation & Logic ---
source_path = os.path.join(TOPICS_DIR, selected_topic, selected_file)

# Session State Init
if "last_compiled_file" not in st.session_state:
    st.session_state.last_compiled_file = None
if "compilation_error" not in st.session_state:
    st.session_state.compilation_error = None

# Compile Trigger
if st.session_state.last_compiled_file != source_path:
    with st.spinner(f"Rendering {selected_file}..."):
        pdf_path, error_log = compile_latex(source_path)
        
        if pdf_path:
            st.session_state.current_pdf_path = pdf_path
            st.session_state.last_compiled_file = source_path
            st.session_state.compilation_error = None
        else:
            st.session_state.current_pdf_path = None
            st.session_state.compilation_error = error_log

# --- Main View ---
tab_view, tab_code = st.tabs(["📄 Document Viewer", "📝 Source Code"])

with tab_view:
    # SUCCESS: Show PDF
    if st.session_state.get("current_pdf_path") and os.path.exists(st.session_state.current_pdf_path):
        
        # --- HEADER SECTION (Download Button Here) ---
        col1, col2 = st.columns([6, 1]) # Split space: Text on left, Button on right
        
        with col1:
            st.success(f"**{selected_file}** rendered successfully.")
            
        with col2:
            with open(st.session_state.current_pdf_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=f,
                    file_name=selected_file.replace('.tex', '.pdf'),
                    mime="application/pdf",
                    type="primary"  # Makes the button stand out
                )
        
        st.markdown("---") # Separator line
        
        # --- PDF VIEWER ---
        pdf_viewer(st.session_state.current_pdf_path, width=800, height=1000)

    # FAILURE: Show Error Log
    elif st.session_state.get("compilation_error"):
        st.error("⚠️ Compilation Failed")
        with st.expander("View Error Log", expanded=True):
            st.code(st.session_state.compilation_error, language="text")

with tab_code:
    st.caption(f"File: {source_path}")
    with open(source_path, "r", encoding="utf-8") as f:
        st.code(f.read(), language="latex")
