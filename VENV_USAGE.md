Use separate venvs without conflicts by always calling the interpreter explicitly.

Data pipeline (uses `data/.venv`):

```powershell
.\run_data.ps1
```

Shiny app (uses `alcoholandsex/.venv`):

```powershell
.\run_app.ps1
```

Install packages in the correct venv:

```powershell
.\data\.venv\Scripts\python.exe -m pip install -r .\data\data_requirements.txt
.\alcoholandsex\.venv\Scripts\python.exe -m pip install -r .\alcoholandsex\app_requirements.txt
```

Quick check which interpreter you are using:

```powershell
.\data\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
.\alcoholandsex\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
```
