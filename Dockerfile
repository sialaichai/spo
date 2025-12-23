# Use a lightweight Python setup
FROM python:3.9-slim

# 1. Install LaTeX and Git (System Level)
# We use 'slim' to keep it small, but we need these specific packages for your app.
RUN apt-get update && apt-get install -y \
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-extra \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Set up the working directory
WORKDIR /app

# 3. Copy python requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of your app code
COPY . .

# 5. expose the Streamlit port
EXPOSE 8501

# 6. Run the app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
