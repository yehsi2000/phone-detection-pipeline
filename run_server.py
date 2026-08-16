import uvicorn
import os
import sys

def main():
    print("=" * 60)
    print("  PhoneGuard AI — Central Server & Active Learning Studio")
    print("  Web Dashboard: http://localhost:8000")
    print("  API Docs:      http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
