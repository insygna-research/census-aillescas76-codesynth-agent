# Dockerfile for ADK Agent System

# Use an official Python runtime as a parent image
# Choose a version compatible with ADK and your dependencies (e.g., 3.9-3.12)
FROM python:3.11-slim

# Set environment variables
# Prevents Python from writing pyc files to disc (equivalent to python -B)
ENV PYTHONDONTWRITEBYTECODE 1
# Ensures Python output is sent straight to terminal without buffering
ENV PYTHONUNBUFFERED 1
# Set the port the application will run on (must match CMD and docker-compose)
ENV PORT=8080
# src/ for the agents package, /app for the src.custom_tools imports
ENV PYTHONPATH=/app:/app/src

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed (e.g., for certain Python packages)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .
# --no-cache-dir: Disables the pip cache
# -r: Installs packages from the given requirements file.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
# Assumes your agent code (main.py, agent modules, tools) is in an 'src' directory
# Adjust the source path '.' if your Dockerfile is not in the project root
COPY ./src /app/src

# Expose the port the app runs on
# This informs Docker that the container listens on this network port at runtime
EXPOSE ${PORT}

# Define the command to run the application
# This command runs when the container launches
# Uses uvicorn to serve the ADK API server defined in src/server.py
# (src/main.py is the command-line runner and serves nothing)
# --host 0.0.0.0: Makes the server accessible from outside the container
# --port ${PORT}: Specifies the port to run on (using the ENV variable)
# Run through a shell so ${PORT} is expanded: the exec (JSON) form passes it to
# uvicorn literally, which exits with "'${PORT}' is not a valid integer".
# exec keeps uvicorn as PID 1 so it receives SIGTERM. No --reload: that is for development.
CMD ["sh", "-c", "exec uvicorn src.server:app --host 0.0.0.0 --port \"${PORT:-8080}\""]
