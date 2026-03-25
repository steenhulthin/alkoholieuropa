Use separate venvs without conflicts by always calling the interpreter explicitly.

Data pipeline (uses `data/.venv`):

```powershell
.\run_data.ps1
```

Shiny app (uses `alcoholandsex/.venv`):

```powershell
.\run_app.ps1
```

Recommended order after this change:

```powershell
.\run_data.ps1
.\run_app.ps1
```

The dashboard now expects local observation Parquet files in `data/processed/` and does not call the Eurostat API at runtime.

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
