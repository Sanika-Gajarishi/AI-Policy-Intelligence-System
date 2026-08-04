import sys
import os
import subprocess

# Change to the backend directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Run the server
subprocess.run([
    sys.executable,
    "-m",
    "uvicorn",
    "app:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000",
    "--reload",
])
