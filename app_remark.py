import streamlit as st  # The main library for building the web interface
import os               # Used for operating system interactions (file paths, folders)
import subprocess       # Used to run external commands (like the LaTeX compiler)
from streamlit_pdf_viewer import pdf_viewer  # A special component to display PDFs in the app
from github import Github, Auth  # Libraries to interact with the GitHub API
import shutil           # High-level file operations (used here to delete entire folders)

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def get_secret(key):
    """
    Retrieves sensitive data (passwords, tokens) safely.
    It checks two locations:
    1. System Environment Variables (used when deployed on cloud servers like Render).
    2. Streamlit's local secrets.toml file (used when running on your own computer).
    """
    # 1. Check if the key exists in the cloud environment settings
    if key in os.environ:
        return os.environ[key]

    # 2. Check if the key exists in the local secrets file
    # We use a try-except block to prevent the app from crashing if secrets.toml is missing.
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass

    # If the key isn't found anywhere, return None
    return None


# ==========================================
# ⚙️ CONFIGURATION
# ==========================================

# Define the folder structure we want to sync.
# The keys (Left) are what the user sees in the UI.
# The values (Right) are the actual folder names on the disk and GitHub.
BASE_DIRS = {
    "Topics": "topics",
    "Year": "year"
}

# Create a temporary folder to store compiled PDF files.
# exist_ok=True means "don't crash if this folder already exists".
TEMP_DIR = "temp_build"
os.makedirs(TEMP_DIR, exist_ok=True)

# Set up the browser tab title and layout width
st.set_page_config(page_title="JPJC SPhO Archive", layout="wide")

# ==========================================
# 🔐 AUTHENTICATION LOGIC
# ==========================================

def check_login():
    """
    Handles user login. Returns the role ('admin' or 'viewer') if logged in.
    If not logged in, it stops the app and shows the login form.
    """
    # Initialize 'user_role' in session_state if it doesn't exist yet.
    # session_state is how Streamlit 'remembers' data between page reloads.
    if "user_role" not in st.session_state:
        st.session_state.user_role = None

    # If the user is already logged in, return their role immediately.
    if st.session_state.user_role:
        return st.session_state.user_role

    # If we are here, the user is NOT logged in. Show the login screen.
    st.title("🔒 Access Restricted")
    st.markdown("Please log in to access the Physics Archive.")
    
    with st.form("login_form"):
        password_input = st.text_input("Enter Access Password", type="password")
        submit_button = st.form_submit_button("Login")

        if submit_button:
            # Check against the admin password
            if password_input == get_secret("admin_password"):  
                st.session_state.user_role = "admin"
                st.success("Logged in as Administrator")
                st.rerun() # Reload the app to update the view
            # Check against the viewer password
            elif password_input == get_secret("viewer_password"):  
                st.session_state.user_role = "viewer"
                st.success("Logged in as Viewer")
                st.rerun() # Reload the app to update the view
            else:
                st.error("❌ Invalid Password")
    
    # Return None to indicate no successful login yet
    return None

# Run the login check. If it returns None, stop the script here so no secret content is shown.
current_role = check_login()
if not current_role: st.stop()

# ==========================================
# 🐙 GITHUB SYNC (MULTI-FOLDER)
# ==========================================

def push_to_github(local_path, content, commit_message):
    """
    Uploads changes made in the Streamlit app back to GitHub.
    
    Args:
        local_path: The file path (e.g., 'topics/Kinematics/notes.tex')
        content: The text content to write to the file.
        commit_message: A note describing the change.
    """
    try:
        # Authenticate with GitHub using the token
        auth_token = Auth.Token(get_secret("github_token"))
        g = Github(auth=auth_token)
        repo = g.get_repo(get_secret("github_repo"))
        
        # 1. GET CONTENT REF
        # To update a file on GitHub, we first need to get its 'sha' (ID).
        # This confirms we are updating the specific version of the file we think we are.
        contents = repo.get_contents(local_path, ref=get_secret("github_branch"))
        
        # 2. PUSH UPDATE
        repo.update_file(
            path=contents.path,
            message=commit_message,
            content=content, 
            sha=contents.sha,
            branch=get_secret("github_branch")
        )
        return True, "Successfully pushed to GitHub!"
    except Exception as e:
        return False, f"GitHub Error: {str(e)}"

def pull_from_github():
    """
    Downloads all files from GitHub to the local Streamlit server.
    This effectively 'resets' the local files to match the master copy on GitHub.
    """
    try:
        # Connect to GitHub
        auth_token = Auth.Token(get_secret("github_token"))
        g = Github(auth=auth_token)
        repo = g.get_repo(get_secret("github_repo"))
        
        total_files = 0
        
        # Loop through our defined folders ("topics" and "year")
        for label, folder_name in BASE_DIRS.items():
            
            # 1. Wipe Local Folder
            # We delete the existing local folder to ensure no old/deleted files remain.
            if os.path.exists(folder_name):
                shutil.rmtree(folder_name)
            # Re-create the empty folder
            os.makedirs(folder_name, exist_ok=True)
            
            # 2. Get the list of files/folders from GitHub
            try:
                contents = repo.get_contents(folder_name, ref=get_secret("github_branch"))
            except Exception as e:
                # If the folder doesn't exist on GitHub, log a warning and skip it
                print(f"Warning: {folder_name} not found. {e}")
                continue

            # 3. Recursive Download
            # We use a 'while' loop to process files. If we find a folder, 
            # we add its contents to the list to process later.
            while contents:
                file_content = contents.pop(0)
                if file_content.type == "dir":
                    # If it's a directory, fetch its contents and add to our processing queue
                    contents.extend(repo.get_contents(file_content.path, ref=get_secret("github_branch")))
                else:
                    # If it's a file, we need to save it.
                    local_path = file_content.path 
                    # Ensure the subfolder exists locally
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    
                    # --- ROBUST CONTENT DECODING ---
                    # GitHub sends files in different ways. We must handle them all.
                    try:
                        # Case A: Standard Base64 encoded file (Images, PDFs, most code)
                        if file_content.encoding == "base64":
                            raw_data = file_content.decoded_content
                        
                        # Case B: 'none' encoding (Often occurs with empty files or raw text)
                        elif file_content.encoding == "none" or file_content.encoding is None:
                            # Use the raw content string if available, otherwise empty bytes
                            raw_data = (file_content.content or "").encode('utf-8')
                        
                        # Case C: Fallback for any other unexpected encoding
                        else:
                            raw_data = file_content.decoded_content
                            
                    except Exception as decode_error:
                        print(f"⚠️ Error downloading {local_path}: {decode_error}")
                        continue

                    # Write the raw bytes to the local hard drive
                    with open(local_path, "wb") as f:
                        f.write(raw_data)
                    total_files += 1
                    
        return True, f"Sync complete! Processed {total_files} files."
    except Exception as e:
        return False, str(e)

# --- AUTO-PULL CHECK ---
# If the "Topics" folder is missing or empty when the app starts, 
# automatically try to download everything from GitHub.
if not os.path.exists(BASE_DIRS["Topics"]) or not os.listdir(BASE_DIRS["Topics"]):
    pull_from_github()

# ==========================================
# 🚀 FILE SYSTEM HELPERS
# ==========================================

def get_subfolders(root_dir):
    """Returns a sorted list of subfolders inside a given directory."""
    if not os.path.exists(root_dir): return []
    return sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])

def get_files(root_dir, subfolder):
    """
    Returns a list of specific file types (.tex, .pdf, images) 
    found inside a specific subfolder.
    """
    target_path = os.path.join(root_dir, subfolder)
    allowed_extensions = ('.tex', '.pdf', '.jpg', '.jpeg', '.png')
    # List files, filter by extension, and sort them alphabetically
    return sorted([f for f in os.listdir(target_path) if f.lower().endswith(allowed_extensions)])

def compile_latex(file_path):
    """
    Runs the 'pdflatex' command to convert a .tex file into a .pdf file.
    """
    file_name = os.path.basename(file_path)
    job_name = os.path.splitext(file_name)[0]
    abs_temp_dir = os.path.abspath(TEMP_DIR)
    
    try:
        # subprocess.run executes the command in the system shell
        process = subprocess.run(
            [
                "pdflatex", 
                "-interaction=nonstopmode", # Don't pause if there are errors
                f"-output-directory={abs_temp_dir}", # Save the PDF in our temp folder
                f"-jobname={job_name}",
                file_path
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        pdf_path = os.path.join(abs_temp_dir, f"{job_name}.pdf")
        
        # Check if the command succeeded (returncode 0) and the PDF exists
        if process.returncode == 0 and os.path.exists(pdf_path):
            return pdf_path, None # Success
        else:
            return None, process.stdout # Failure, return the error log
    except Exception as e:
        return None, str(e)

# ==========================================
# 🖥️ SIDEBAR NAVIGATION UI
# ==========================================
st.sidebar.title(f"JPJC SPhO ({current_role.title()})")

# ADMIN TOOLS
if current_role == 'admin':
    # Button to force a download of all files from GitHub
    if st.sidebar.button("🔄 Pull All"):
        with st.spinner("Syncing Topics and Year..."):
            success, msg = pull_from_github()
            if success:
                st.sidebar.success(msg)
                st.rerun() # Refresh app to show new files
            else:
                st.sidebar.error(msg)

# Logout Button
if st.sidebar.button("Logout", type="secondary"):
    st.session_state.user_role = None
    st.rerun()

# 1. SELECT MODE (Browse by Topics or by Year)
browse_mode = st.sidebar.radio("Library Section:", ["Topics", "Year"], horizontal=True)
current_root_dir = BASE_DIRS[browse_mode] 

# 2. SELECT SUBFOLDER (e.g., 'Kinematics' or '2023')
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

# Construct absolute paths for file reading/writing
rel_path = os.path.join(current_root_dir, selected_subfolder, selected_file).replace("\\", "/")
abs_path = os.path.abspath(rel_path)

# ==========================================
# 👁️ MAIN VIEW / EDIT LOGIC
# ==========================================

# Determine file type based on extension
file_ext = selected_file.lower().split('.')[-1]
is_image = file_ext in ['jpg', 'jpeg', 'png']
is_pdf = file_ext == 'pdf'
is_tex = file_ext == 'tex'

# --- STATE MANAGEMENT FOR COMPILATION ---
# We check if the user selected a new file. If so, we reset the PDF view.
if "force_recompile" not in st.session_state: st.session_state.force_recompile = False
if "last_processed" not in st.session_state: st.session_state.last_processed = None

if st.session_state.last_processed != rel_path or st.session_state.force_recompile:
    st.session_state.current_pdf = None
    st.session_state.compilation_error = None
    
    if is_pdf:
        st.session_state.current_pdf = abs_path
    elif is_tex:
        # If it's a LaTeX file, we try to compile it into a PDF immediately
        with st.spinner(f"Compiling {selected_file}..."):
            pdf, log = compile_latex(abs_path)
            st.session_state.current_pdf = pdf
            st.session_state.compilation_error = log
            
    st.session_state.last_processed = rel_path
    st.session_state.force_recompile = False

# Create Tabs for Viewing and Editing
tab_label = "✏️ Edit Source" if current_role == 'admin' else "📝 Source Code"
tab_view, tab_edit = st.tabs(["📄 Document Viewer", tab_label])

# --- TAB 1: VIEWER ---
with tab_view:
    if is_image:
        st.success(f"**{selected_file}** loaded.")
        st.image(abs_path, caption=selected_file, use_container_width=True)
    elif st.session_state.current_pdf and os.path.exists(st.session_state.current_pdf):
        # Layout: Text on left, Download button on right
        col1, col2 = st.columns([6, 1])
        with col1: st.success(f"**{selected_file}** loaded.")
        with col2:
            with open(st.session_state.current_pdf, "rb") as f:
                st.download_button("⬇️ PDF", f, file_name=selected_file.replace('.tex','.pdf'), mime="application/pdf", type="primary")
        st.markdown("---")
        # Display the PDF inside the browser
        pdf_viewer(st.session_state.current_pdf, width=800, height=1000)
    elif st.session_state.compilation_error:
        st.error("⚠️ Compilation Failed")
        with st.expander("Error Log"):
            st.code(st.session_state.compilation_error)

# --- TAB 2: EDITOR (Admins only) or SOURCE VIEW (Viewers) ---
with tab_edit:
    if is_image or is_pdf:
        st.info(f"Binary file ({file_ext.upper()}) cannot be edited directly.")
    else:
        # Read the text file content
        with open(abs_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        if current_role == 'admin':
            st.warning(f"⚠️ You are editing: {rel_path}")
            
            # Text area allows admin to change the code
            new_content = st.text_area(
                "LaTeX Source", 
                value=file_content, 
                height=600, 
                key=abs_path
            )
            
            # Button to save changes to GitHub
            if st.button("💾 Push to GitHub", type="primary"):
                if new_content != file_content:
                    # 1. Save locally first
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    
                    # 2. Push to GitHub
                    with st.spinner("Pushing to GitHub..."):
                        success, msg = push_to_github(
                            rel_path, 
                            new_content, 
                            f"Update {selected_file} via Streamlit"
                        )
                    if success:
                        st.success(msg)
                        st.session_state.force_recompile = True # Trigger re-compile on reload
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.info("No changes detected.")
        else:
            # Viewers just see the code (read-only)
            st.caption(f"Path: {rel_path}")
            st.code(file_content, language="latex")
