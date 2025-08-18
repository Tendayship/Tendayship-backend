#!/usr/bin/env python3
"""
Azure App Service startup script for Family News Service
"""
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

# Set environment variables for Azure App Service
os.environ.setdefault("PYTHONPATH", str(app_dir))

if __name__ == "__main__":
    import uvicorn
    from app.main import app
    
    # Azure App Service will set PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    
    print(f"Starting Family News Service on {host}:{port}")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=False  # Production mode
    )