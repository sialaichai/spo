import streamlit as st
import os
import subprocess
from streamlit_pdf_viewer import pdf_viewer
from github import Github
import shutil

# --- Configuration ---
TOPICS_DIR = "topics"
TEMP_DIR = "temp_build"
os.makedirs(TEMP_DIR, exist_ok=True)

st.set_page_config(page_title="Physics Topics", layout="wide")

# ==========================================
# 🔒 AUTHENTICATION LOGIC (DUAL LEVEL)
# ==========================================
def check_login():
    """
    Returns: 'admin', 'viewer', or None
    """
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
            # Check against secrets.toml
            if password_input == st.secrets["admin_password"]:
                st.session_state.user_role = "admin"
                st.success("Logged in as Administrator")
                st.rerun()
            elif password_input == st.secrets["viewer_password"]:
                st.session_state.user_role = "viewer"
                st.success("Logged in as Viewer")
                st.rerun()
            else:
                st.error("❌ Invalid Password")

    return None

# STOP IF NOT LOGGED IN
current_role = check_login()
if not current_role:
    st.stop()

# ==========================================
# 🐙 GITHUB SYNC FUNCTIONS
# ==========================================
def push_to_github(local_path, content, commit_message):
    """
    Updates the file on GitHub.
    local_path: 'topics/Topic1/file.tex'
    """
    try:
        g = Github(st.secrets["github_token"])
        repo = g.get_repo(st.secrets["github_repo"])
        
        # Get the file from the repo to retrieve its SHA (needed for update)
        contents = repo.get_contents(local_path, ref=st.secrets["github_branch"])
        
        # Update the file
        repo.update_file(
            path=contents.path,
            message=commit_message,
            content=content,
            sha=contents.sha,
            branch=st.secrets["github_branch"]
        )
        return True, "Successfully pushed to GitHub!"
    except Exception as e:
        return False, f"GitHub Error: {str(e)}"

def pull_from_github():
    """
    1. Wipes the local 'topics' folder.
    2. Downloads a fresh copy from GitHub.
    """
    try:
        # 1. WIPE LOCAL FOLDER CLEAN
        if os.path.exists(TOPICS_DIR):
            shutil.rmtree(TOPICS_DIR)  # Deletes the folder and everything inside
        
        # Re-create the empty folder
        os.makedirs(TOPICS_DIR, exist_ok=True)

        # 2. CONNECT TO GITHUB
        g = Github(st.secrets["github_token"])
        repo = g.get_repo(st.secrets["github_repo"])
        
        # 3. DOWNLOAD EVERYTHING
        contents = repo.get_contents(TOPICS_DIR, ref=st.secrets["github_branch"])
        count = 0
        
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path, ref=st.secrets["github_branch"]))
            else:
                # Calculate where to save it locally
                local_path = file_content.path 
                
                # Ensure the subfolder exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Write the file
                with open(local_path, "wb") as f:
                    f.write(file_content.decoded_content)
                count += 1
                    
        return True, f"Clean sync complete! Downloaded {count} files."
    except Exception as e:
        return False, str(e)

# ==========================================
# 🚀 MAIN APP LOGIC
# ==========================================

def get_topics():
    if not os.path.exists(TOPICS_DIR): return []
    return sorted([d for d in os.listdir(TOPICS_DIR) if os.path.isdir(os.path.join(TOPICS_DIR, d))])

def get_topic_files(topic):
    topic_path = os.path.join(TOPICS_DIR, topic)
    # MODIFIED: Now accepts images (jpg, png) in addition to tex and pdf
    allowed_extensions = ('.tex', '.pdf', '.jpg', '.jpeg', '.png')
    return sorted([f for f in os.listdir(topic_path) if f.lower().endswith(allowed_extensions)])

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
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        pdf_path = os.path.join(abs_temp_dir, f"{job_name}.pdf")
        
        if process.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path, None
        else:
            return None, process.stdout
    except Exception as e:
        return None, str(e)

        
# --- SIDEBAR ---
st.sidebar.title(f"Physics Archive ({current_role.title()})")

# ADMIN ONLY: Sync Button
if current_role == 'admin':
    if st.sidebar.button("🔄 Pull from GitHub"):
        with st.spinner("Downloading latest files..."):
            success, msg = pull_from_github()
            if success:
                st.sidebar.success(msg)
                st.rerun()
            else:
                st.sidebar.error(msg)

if st.sidebar.button("Logout", type="secondary"):
    st.session_state.user_role = None
    st.rerun()

topics = get_topics()
if not topics:
    st.sidebar.error("No topics found in 'topics/' folder.")
    st.stop()

selected_topic = st.sidebar.selectbox("Select Topic", topics)
st.sidebar.markdown("---") 
files = get_topic_files(selected_topic)

if not files:
    st.sidebar.warning("No files found.")
    st.stop()

selected_file = st.sidebar.radio(f"Documents in {selected_topic}", files)

# --- FILE PATHS ---
rel_path = os.path.join(TOPICS_DIR, selected_topic, selected_file).replace("\\", "/")
abs_path = os.path.abspath(rel_path)

# --- PROCESSING LOGIC ---
if "force_recompile" not in st.session_state:
    st.session_state.force_recompile = False
if "last_processed" not in st.session_state:
    st.session_state.last_processed = None

# Logic to determine what to show based on file type
file_ext = selected_file.lower().split('.')[-1]
is_image = file_ext in ['jpg', 'jpeg', 'png']
is_pdf = file_ext == 'pdf'
is_tex = file_ext == 'tex'

# Run processing only if file changed or recompile forced
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
            
    # For images, we don't need to "process" them, we just read them directly in the view
            
    st.session_state.last_processed = rel_path
    st.session_state.force_recompile = False

# --- TABS ---
tab_label = "✏️ Edit Source" if current_role == 'admin' else "📝 Source Code"
tab_view, tab_edit = st.tabs(["📄 Document Viewer", tab_label])

# 1. VIEWER TAB
with tab_view:
    # A. IMAGE VIEWER
    if is_image:
        st.success(f"**{selected_file}** loaded.")
        st.image(abs_path, caption=selected_file, use_container_width=True)
        
    # B. PDF VIEWER (Native or Compiled)
    elif st.session_state.current_pdf and os.path.exists(st.session_state.current_pdf):
        col1, col2 = st.columns([6, 1])
        with col1: st.success(f"**{selected_file}** loaded.")
        with col2:
            with open(st.session_state.current_pdf, "rb") as f:
                st.download_button("⬇️ PDF", f, file_name=selected_file.replace('.tex','.pdf'), mime="application/pdf", type="primary")
        
        st.markdown("---")
        pdf_viewer(st.session_state.current_pdf, width=800, height=1000)
        
    # C. ERROR STATE
    elif st.session_state.compilation_error:
        st.error("⚠️ Compilation Failed")
        with st.expander("Error Log"):
            st.code(st.session_state.compilation_error)

# 2. EDIT / SOURCE TAB
with tab_edit:
    if is_image or is_pdf:
        st.info(f"Binary file ({file_ext.upper()}) cannot be edited directly.")
    else:
        # Read current content
        with open(abs_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        if current_role == 'admin':
            st.warning(f"⚠️ You are editing: {selected_file}")
            
            # The Text Editor
            new_content = st.text_area(
                "LaTeX Source", 
                value=file_content, 
                height=600,
                key=abs_path # Dynamic key to reset on file change
            )

            # SAVE BUTTON
            if st.button("💾 Save to GitHub & Re-Render", type="primary"):
                if new_content != file_content:
                    # 1. Save locally (immediate update)
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    
                    # 2. Push to GitHub
                    with st.spinner("Pushing to GitHub..."):
                        success, msg = push_to_github(
                            rel_path, 
                            new_content, 
                            f"Update {selected_file} via Streamlit Admin"
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
            # Viewer Mode (Read Only)
            st.caption(f"Path: {rel_path}")
            st.code(file_content, language="latex")
