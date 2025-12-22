import streamlit as st
import os
import subprocess
from streamlit_pdf_viewer import pdf_viewer

# --- Configuration ---
TOPICS_DIR = "topics"
TEMP_DIR = "temp_build"
os.makedirs(TEMP_DIR, exist_ok=True)

st.set_page_config(page_title="Physics Topics", layout="wide")

# ==========================================
# 🔒 AUTHENTICATION LOGIC
# ==========================================
def check_login():
    """
    Verifies the password against st.secrets.
    Returns True if logged in, False otherwise.
    """
    # 1. Initialize session state for authentication
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # 2. If already logged in, return True immediately
    if st.session_state.authenticated:
        return True

    # 3. If not logged in, show the login form
    st.title("🔒 Login Required")
    
    # We use a form so the user can hit 'Enter' to submit
    with st.form("login_form"):
        password_input = st.text_input("Enter Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            # DIRECT COMPARISON (No Hash as requested)
            if password_input == st.secrets["app_password"]:
                st.session_state.authenticated = True
                st.rerun()  # Rerun the app to remove the login form
            else:
                st.error("❌ Incorrect Password")

    return False

# STOP THE APP HERE IF NOT LOGGED IN
if not check_login():
    st.stop()  # This prevents the rest of the code from running

# ==========================================
# 🚀 MAIN APPLICATION
# (Only runs if authenticated)
# ==========================================

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
st.sidebar.title("Physics SPO")

# Logout Button (Optional but useful)
if st.sidebar.button("Logout", type="secondary"):
    st.session_state.authenticated = False
    st.rerun()

topics = get_topics()
if not topics:
    st.sidebar.error("No topics found.")
    st.stop()

# 1. Topic Selection
selected_topic = st.sidebar.selectbox("Select Topic", topics)
st.sidebar.markdown("---") 

# 2. Document Selection
tex_files = get_tex_files(selected_topic)
if not tex_files:
    st.sidebar.warning("No files in this topic.")
    st.stop()

selected_file = st.sidebar.radio(f"Documents in {selected_topic}", tex_files)


# --- Auto-Compilation & Logic ---
source_path = os.path.join(TOPICS_DIR, selected_topic, selected_file)

if "last_compiled_file" not in st.session_state:
    st.session_state.last_compiled_file = None
if "compilation_error" not in st.session_state:
    st.session_state.compilation_error = None

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
    if st.session_state.get("current_pdf_path") and os.path.exists(st.session_state.current_pdf_path):
        
        col1, col2 = st.columns([6, 1])
        with col1:
            st.success(f"**{selected_file}** rendered successfully.")
        with col2:
            with open(st.session_state.current_pdf_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=f,
                    file_name=selected_file.replace('.tex', '.pdf'),
                    mime="application/pdf",
                    type="primary"
                )
        
        st.markdown("---")
        pdf_viewer(st.session_state.current_pdf_path, width=800, height=1000)

    elif st.session_state.get("compilation_error"):
        st.error("⚠️ Compilation Failed")
        with st.expander("View Error Log", expanded=True):
            st.code(st.session_state.compilation_error, language="text")

with tab_code:
    st.caption(f"File: {source_path}")
    with open(source_path, "r", encoding="utf-8") as f:
        st.code(f.read(), language="latex")
