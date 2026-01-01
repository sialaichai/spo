import streamlit as st
import os
import subprocess
from streamlit_pdf_viewer import pdf_viewer
from github import Github, Auth
import shutil
# Removed: from cryptography.fernet import Fernet

# --- HELPER FUNCTION ---
def get_secret(key):
    # 1. Priority: Check Environment Variables (Render)
    if key in os.environ:
        return os.environ[key]

    # 2. Fallback: Check st.secrets (Local)
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    return None


# --- Configuration ---
BASE_DIRS = {
    "Topics": "topics",
    "Year": "year"
}

TEMP_DIR = "temp_build"
os.makedirs(TEMP_DIR, exist_ok=True)

st.set_page_config(page_title="JPJC SPhO Archive", layout="wide")

# ==========================================
# 🔐 AUTHENTICATION LOGIC
# ==========================================
def check_login():
    if "user_role" not in st.session_state:
        st.session_state.user_role = None

    if st.session_state.user_role:
        return st.session_state.user_role

    st.title("🔒 Access Restricted")
    st.markdown("Please log in to access the Physics Archive.")
    
    with st.form("login_form"):
        password_input = st.text_input("Enter Access Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            if password_input == get_secret("admin_password"):  
                st.session_state.user_role = "admin"
                st.success("Logged in as Administrator")
                st.rerun()
            elif password_input == get_secret("viewer_password"):  
                st.session_state.user_role = "viewer"
                st.success("Logged in as Viewer")
                st.rerun()
            else:
                st.error("❌ Invalid Password")
    return None

current_role = check_login()
if not current_role: st.stop()

# ==========================================
# 🐙 GITHUB SYNC (MULTI-FOLDER)
# ==========================================
def push_to_github(local_path, content, commit_message):
    """
    Pushes content directly to GitHub (No Encryption).
    local_path example: 'Year/2023/exam.tex'
    """
    try:
        auth_token = Auth.Token(get_secret("github_token"))
        g = Github(auth=auth_token)
        repo = g.get_repo(get_secret("github_repo"))
        
        # 1. GET CONTENT REF
        # We need to get the file to update it (sha is required)
        contents = repo.get_contents(local_path, ref=get_secret("github_branch"))
        
        # 2. PUSH DIRECTLY
        repo.update_file(
            path=contents.path,
            message=commit_message,
            content=content, # Send plain string
            sha=contents.sha,
            branch=get_secret("github_branch")
        )
        return True, "Successfully pushed to GitHub!"
    except Exception as e:
        return False, f"GitHub Error: {str(e)}"

def pull_from_github():
    """
    Loops through BASE_DIRS, wipes them locally, and re-downloads from GitHub.
    Robustly handles file encodings.
    """
    try:
        auth_token = Auth.Token(get_secret("github_token"))
        g = Github(auth=auth_token)
        repo = g.get_repo(get_secret("github_repo"))
        
        total_files = 0
        
        # Iterate over "topics" and "Year"
        for label, folder_name in BASE_DIRS.items():
            
            # 1. Wipe Local Folder
            if os.path.exists(folder_name):
                shutil.rmtree(folder_name)
            os.makedirs(folder_name, exist_ok=True)
            
            # 2. Get Contents from GitHub
            try:
                contents = repo.get_contents(folder_name, ref=get_secret("github_branch"))
            except Exception as e:
                # If folder doesn't exist on GitHub, just skip it
                print(f"Warning: {folder_name} not found. {e}")
                continue

            # 3. Recursive Download
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    contents.extend(repo.get_contents(file_content.path, ref=get_secret("github_branch")))
                else:
                    local_path = file_content.path 
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    
                    # --- ROBUST CONTENT DECODING ---
                    try:
                        # Case A: Standard Base64 encoded file
                        if file_content.encoding == "base64":
                            raw_data = file_content.decoded_content
                        
                        # Case B: 'none' encoding (often empty files or raw text)
                        elif file_content.encoding == "none" or file_content.encoding is None:
                            # Treat content as string, encode to bytes. If None, use empty bytes.
                            raw_data = (file_content.content or "").encode('utf-8')
                        
                        # Case C: Fallback for anything else
                        else:
                            raw_data = file_content.decoded_content
                            
                    except Exception as decode_error:
                        # Log error to console but don't crash the app
                        print(f"⚠️ Error downloading {local_path}: {decode_error}")
                        continue

                    # Write bytes to disk
                    with open(local_path, "wb") as f:
                        f.write(raw_data)
                    total_files += 1
                    
        return True, f"Sync complete! Processed {total_files} files."
    except Exception as e:
        return False, str(e)

# --- AUTO-PULL CHECK ---
# If "topics" is missing, we assume we need to pull everything
if not os.path.exists(BASE_DIRS["Topics"]) or not os.listdir(BASE_DIRS["Topics"]):
    pull_from_github()

# ==========================================
# 🚀 HELPER FUNCTIONS
# ==========================================

def get_subfolders(root_dir):
    """Returns list of subfolders (e.g., 'Kinematics', '2023')"""
    if not os.path.exists(root_dir): return []
    return sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])

def get_files(root_dir, subfolder):
    """Returns list of supported files in the specific subfolder"""
    target_path = os.path.join(root_dir, subfolder)
    allowed_extensions = ('.tex', '.pdf', '.jpg', '.jpeg', '.png')
    return sorted([f for f in os.listdir(target_path) if f.lower().endswith(allowed_extensions)])

def compile_latex(file_path):
    file_name = os.path.basename(file_path)
    job_name = os.path.splitext(file_name)[0]
    abs_temp_dir = os.path.abspath(TEMP_DIR)
    
    try:
        process = subprocess.run(
            [
                "pdflatex", 
                "-interaction=nonstopmode", 
                f"-output-directory={abs_temp_dir}",
                f"-jobname={job_name}",
                file_path
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        pdf_path = os.path.join(abs_temp_dir, f"{job_name}.pdf")
        if process.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path, None
        else:
            return None, process.stdout
    except Exception as e:
        return None, str(e)

# ==========================================
# 🖥️ SIDEBAR NAVIGATION
# ==========================================
st.sidebar.title(f"JPJC SPhO ({current_role.title()})")

# ADMIN SYNC
if current_role == 'admin':
    if st.sidebar.button("🔄 Pull All"):
        with st.spinner("Syncing Topics and Year..."):
            success, msg = pull_from_github()
            if success:
                st.sidebar.success(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)

if st.sidebar.button("Logout", type="secondary"):
    st.session_state.user_role = None
    st.rerun()

# 1. SELECT MODE (Topics vs Year)
browse_mode = st.sidebar.radio("Library Section:", ["Topics", "Year"], horizontal=True)
current_root_dir = BASE_DIRS[browse_mode] 

# 2. SELECT SUBFOLDER
subfolders = get_subfolders(current_root_dir)

if not subfolders:
    st.sidebar.error(f"No folders found in '{current_root_dir}'.")
    st.stop()

selected_subfolder = st.sidebar.selectbox(f"Select {browse_mode[:-1]}", subfolders)

# 3. SELECT FILE
files = get_files(current_root_dir, selected_subfolder)

if not files:
    st.sidebar.warning("No files found.")
    st.stop()

selected_file = st.sidebar.radio(f"Documents in {selected_subfolder}", files)

# Build Paths
rel_path = os.path.join(current_root_dir, selected_subfolder, selected_file).replace("\\", "/")
abs_path = os.path.abspath(rel_path)

# ==========================================
# 👁️ MAIN VIEW / EDIT LOGIC
# ==========================================

# Determine file type
file_ext = selected_file.lower().split('.')[-1]
is_image = file_ext in ['jpg', 'jpeg', 'png']
is_pdf = file_ext == 'pdf'
is_tex = file_ext == 'tex'

# Check if we need to recompile or if selection changed
if "force_recompile" not in st.session_state: st.session_state.force_recompile = False
if "last_processed" not in st.session_state: st.session_state.last_processed = None

if st.session_state.last_processed != rel_path or st.session_state.force_recompile:
    st.session_state.current_pdf = None
    st.session_state.compilation_error = None
    
    if is_pdf:
        st.session_state.current_pdf = abs_path
    elif is_tex:
        with st.spinner(f"Compiling {selected_file}..."):
            pdf, log = compile_latex(abs_path)
            st.session_state.current_pdf = pdf
            st.session_state.compilation_error = log
            
    st.session_state.last_processed = rel_path
    st.session_state.force_recompile = False

# TABS
tab_label = "✏️ Edit Source" if current_role == 'admin' else "📝 Source Code"
tab_view, tab_edit = st.tabs(["📄 Document Viewer", tab_label])

# --- VIEWER TAB ---
with tab_view:
    if is_image:
        st.success(f"**{selected_file}** loaded.")
        st.image(abs_path, caption=selected_file, use_container_width=True)
    elif st.session_state.current_pdf and os.path.exists(st.session_state.current_pdf):
        col1, col2 = st.columns([6, 1])
        with col1: st.success(f"**{selected_file}** loaded.")
        with col2:
            with open(st.session_state.current_pdf, "rb") as f:
                st.download_button("⬇️ PDF", f, file_name=selected_file.replace('.tex','.pdf'), mime="application/pdf", type="primary")
        st.markdown("---")
        pdf_viewer(st.session_state.current_pdf, width=800, height=1000)
    elif st.session_state.compilation_error:
        st.error("⚠️ Compilation Failed")
        with st.expander("Error Log"):
            st.code(st.session_state.compilation_error)

# --- EDITOR TAB ---
with tab_edit:
    if is_image or is_pdf:
        st.info(f"Binary file ({file_ext.upper()}) cannot be edited directly.")
    else:
        # Read file
        with open(abs_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        if current_role == 'admin':
            st.warning(f"⚠️ You are editing: {rel_path}")
            
            new_content = st.text_area(
                "LaTeX Source", 
                value=file_content, 
                height=600, 
                key=abs_path
            )
            
            if st.button("💾 Push to GitHub", type="primary"):
                if new_content != file_content:
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    
                    with st.spinner("Pushing to GitHub..."):
                        success, msg = push_to_github(
                            rel_path, 
                            new_content, 
                            f"Update {selected_file} via Streamlit"
                        )
                    if success:
                        st.success(msg)
                        st.session_state.force_recompile = True
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.info("No changes detected.")
        else:
            st.caption(f"Path: {rel_path}")
            st.code(file_content, language="latex")
