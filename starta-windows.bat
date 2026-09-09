@echo off
python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn bb.api:app --host 127.0.0.1 --port 8000
