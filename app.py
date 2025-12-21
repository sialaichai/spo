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
    """Compiles LaTeX to PDF and returns the PDF path."""
    file_name = os.path.basename(file_path)
    job_name = os.path.splitext(file_name)[0]
    
    # Run pdflatex
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
            stderr=subprocess.PIPE
        )
        pdf_path = os.path.join(TEMP_DIR, f"{job_name}.pdf")
        if process.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path
    except Exception:
        return None
    return None

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
# We use session state to track which file is currently compiled
# so we don't re-compile every time you click a tab.

if "last_compiled_file" not in st.session_state:
    st.session_state.last_compiled_file = None

# If the user selected a new file, trigger compilation immediately
if st.session_state.last_compiled_file != source_path:
    with st.spinner("Rendering document..."):
        pdf_path = compile_latex(source_path)
        if pdf_path:
            st.session_state.current_pdf_path = pdf_path
            st.session_state.last_compiled_file = source_path
        else:
            st.error("Error: Could not compile LaTeX.")

# --- Display Area ---
tab_view, tab_code = st.tabs(["📄 Document Viewer", "📝 Source Code"])

with tab_view:
    # Check if we have a valid PDF path in the state
    if "current_pdf_path" in st.session_state and os.path.exists(st.session_state.current_pdf_path):
        
        # 1. Use streamlit-pdf-viewer (Safe, won't be blocked)
        # width and height can be adjusted. 'width' ensures it fits the container.
        pdf_viewer(st.session_state.current_pdf_path, width=700, height=1000)

        st.markdown("---")
        # 2. Download Button
        with open(st.session_state.current_pdf_path, "rb") as f:
            st.download_button(
                label="⬇️ Download PDF",
                data=f,
                file_name=os.path.basename(st.session_state.current_pdf_path),
                mime="application/pdf"
            )

with tab_code:
    with open(source_path, "r", encoding="utf-8") as f:
        st.code(f.read(), language="latex")
