FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy nina_session_analyzer.py from repo root to container root
# (backend/main.py looks for it in parent.parent, which from /app/main.py is /)
COPY nina_session_analyzer.py /nina_session_analyzer.py

# Expose the port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

