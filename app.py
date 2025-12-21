import streamlit as st
import os
import subprocess
import base64
import shutil
from pathlib import Path

# --- Configuration ---
TOPICS_DIR = "topics"  # Folder containing your topic subfolders
TEMP_DIR = "temp_build" # Folder for temporary compilation files

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

st.set_page_config(page_title="Physics Topics Archive", layout="wide")

# --- Helper Functions ---

def get_topics():
    """Returns a list of subdirectories in the topics folder."""
    if not os.path.exists(TOPICS_DIR):
        os.makedirs(TOPICS_DIR)
        return []
    return [d for d in os.listdir(TOPICS_DIR) if os.path.isdir(os.path.join(TOPICS_DIR, d))]

def get_tex_files(topic):
    """Returns a list of .tex files in a specific topic folder."""
    topic_path = os.path.join(TOPICS_DIR, topic)
    return [f for f in os.listdir(topic_path) if f.endswith(".tex")]

def compile_latex(file_path):
    """
    Compiles a .tex file to PDF using pdflatex.
    Returns the path to the generated PDF or None if failed.
    """
    file_name = os.path.basename(file_path)
    job_name = os.path.splitext(file_name)[0]
    
    # We compile into a temp directory to keep the source clean
    # Command: pdflatex -output-directory=TEMP_DIR -jobname=NAME file_path
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
        else:
            # If there is an error, we can look at process.stdout for debugging
            return None
    except Exception as e:
        st.error(f"System Error: {e}")
        return None

def display_pdf(pdf_path):
    """Embeds the PDF file in the Streamlit app."""
    with open(pdf_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    
    # Embedding PDF in HTML
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- Main App Layout ---

st.title("📚 Physics Topics Repository")

# 1. Sidebar for Navigation
st.sidebar.header("Navigation")
topics = get_topics()

if not topics:
    st.warning(f"No topics found. Please create folders inside '{TOPICS_DIR}'.")
    st.stop()

selected_topic = st.sidebar.selectbox("Select Topic", topics)
tex_files = get_tex_files(selected_topic)

if not tex_files:
    st.sidebar.warning("No .tex files found in this topic.")
    st.stop()

selected_file = st.sidebar.selectbox("Select Document", tex_files)

# Construct full path
full_file_path = os.path.join(TOPICS_DIR, selected_topic, selected_file)

# 2. Main Content Area
st.subheader(f"Viewing: {selected_file}")

# Create Tabs for different views
tab_view, tab_code = st.tabs(["📄 Document Viewer", "📝 Source Code"])

with tab_view:
    st.write("Click below to render the document.")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Render / Update PDF", type="primary"):
            with st.spinner("Compiling LaTeX..."):
                pdf_output = compile_latex(full_file_path)
                if pdf_output:
                    st.session_state['current_pdf'] = pdf_output
                    st.success("Compilation successful!")
                else:
                    st.error("Compilation failed. Check your LaTeX syntax.")
    
    # Display PDF if it exists in session state
    if 'current_pdf' in st.session_state and os.path.exists(st.session_state['current_pdf']):
        st.markdown("---")
        display_pdf(st.session_state['current_pdf'])
        
        # Download Button
        with open(st.session_state['current_pdf'], "rb") as pdf_file:
            st.download_button(
                label="⬇️ Download PDF",
                data=pdf_file,
                file_name=os.path.basename(st.session_state['current_pdf']),
                mime="application/pdf"
            )

with tab_code:
    st.info("This is the raw LaTeX content used to generate the document.")
    with open(full_file_path, "r", encoding='utf-8') as f:
        content = f.read()
    st.code(content, language="latex")
