# Use official Python image
FROM python:3.9

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y ffmpeg

# Copy requirements first (to leverage Docker cache)
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source code
COPY stream.py /app/stream.py

# Expose Flask port (Optional)
EXPOSE 8000

# Run the application
ENTRYPOINT ["python", "stream.py"]