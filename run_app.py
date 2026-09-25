import os
import sys
import time
import threading
import webbrowser
import uvicorn
from main import app

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("=" * 55)
    print("        Starting Prescription Reader...")
    print("   Application will open at http://localhost:8000")
    print("=" * 55)
    
    # Launch browser automatically
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run FastAPI server
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
