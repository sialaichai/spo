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
    return [d for d in os.listdir(TOPICS_DIR) if os.path.isdir(os.path.join(TOPICS_DIR, d))]

def get_tex_files(topic):
    topic_path = os.path.join(TOPICS_DIR, topic)
    return [f for f in os.listdir(topic_path) if f.endswith(".tex")]

def compile_latex(file_path):
    """
    Compiles LaTeX to PDF. 
    Returns:
        - (pdf_path, None) if successful
        - (None, error_log) if failed
    """
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
            text=True  # specific to Python 3.7+, ensures output is string not bytes
        )
        
        pdf_path = os.path.join(TEMP_DIR, f"{job_name}.pdf")
        
        if process.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path, None
        else:
            # Return the standard output (where LaTeX prints errors)
            return None, process.stdout
            
    except Exception as e:
        return None, str(e)

# --- Main Layout ---
st.title("📚 Physics Topics Repository")

# Sidebar
topics = get_topics()
if not topics:
    st.error("No topics found.")
    st.stop()

selected_topic = st.sidebar.selectbox("Select Topic", topics)
tex_files = get_tex_files(selected_topic)
selected_file = st.sidebar.selectbox("Select Document", tex_files)

# Full path to the source file
source_path = os.path.join(TOPICS_DIR, selected_topic, selected_file)

# --- Automatic Compilation Logic ---
if "last_compiled_file" not in st.session_state:
    st.session_state.last_compiled_file = None
if "compilation_error" not in st.session_state:
    st.session_state.compilation_error = None

# Trigger compilation if file changed
if st.session_state.last_compiled_file != source_path:
    with st.spinner("Rendering document..."):
        pdf_path, error_log = compile_latex(source_path)
        
        if pdf_path:
            st.session_state.current_pdf_path = pdf_path
            st.session_state.last_compiled_file = source_path
            st.session_state.compilation_error = None # Clear previous errors
        else:
            st.session_state.current_pdf_path = None
            st.session_state.compilation_error = error_log

# --- Display Area ---
tab_view, tab_code = st.tabs(["📄 Document Viewer", "📝 Source Code"])

with tab_view:
    # 1. Success Case: Display PDF
    if st.session_state.get("current_pdf_path") and os.path.exists(st.session_state.current_pdf_path):
        pdf_viewer(st.session_state.current_pdf_path, width=700, height=1000)
        
        st.markdown("---")
        with open(st.session_state.current_pdf_path, "rb") as f:
            st.download_button(
                label="⬇️ Download PDF",
                data=f,
                file_name=os.path.basename(st.session_state.current_pdf_path),
                mime="application/pdf"
            )

    # 2. Error Case: Display Log
    elif st.session_state.get("compilation_error"):
        st.error("⚠️ Compilation Failed")
        with st.expander("View Error Log (Click to expand)", expanded=True):
            st.code(st.session_state.compilation_error, language="text")
            
        st.info("Tip: Look for lines starting with '! LaTeX Error'. It usually means a package is missing.")

with tab_code:
    with open(source_path, "r", encoding="utf-8") as f:
        st.code(f.read(), language="latex")
