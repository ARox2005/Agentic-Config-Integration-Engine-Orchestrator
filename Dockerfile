FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir uvicorn python-multipart python-dotenv

# Create data directory so ChromaDB has persistent storage mapped gracefully
RUN mkdir -p data

# Copy the entire orchestrator source code
COPY orchestrator/ /app/

# Expose port 7860 as required by Hugging Face Spaces
EXPOSE 7860

# Run the app on 7860
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
