set windows-shell := ["powershell.exe", "-NoProfile", "-Command"]

serve:
    $env:PYTHONPATH = "src"; uv run python -m admiral_mcp.server

dev:
    uv run python -m admiral_mcp.server &
    bun --cwd webapp run dev

test:
    uv run pytest tests/ -v

lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

fmt:
    uv run ruff format src/ tests/

tcheck:
    bunx --cwd webapp tsc --noEmit

mcpb-pack:
    mcpb pack . dist/admiral-mcp-v0.1.0.mcpb

install:
    uv sync
    bun --cwd webapp install

# Bootstrap: install dev deps + pre-commit hook
bootstrap:
    uv sync --group dev
    uv run pre-commit install
    Write-Host "Pre-commit hooks installed." -ForegroundColor Green
# CUA smoke test with detailed report to reports and mcd
cua-nsis-test:
	uv run python scripts/cua-smoke.py --output-dir cua-reports
	$date = Get-Date -Format "yyyy-MM-dd"; $md = "reports/cua-admiral-$date.md"; if (Test-Path $md) { Copy-Item $md "D:/Dev/repos/mcp-central-docs/reports/" -Force; Write-Host "Synced $md to mcd" }

cua-webapp-test:
	uv run python scripts/cua-webapp-test.py --output-dir cua-reports
	$date = Get-Date -Format "yyyy-MM-dd"; $md = "reports/cua-admiral-$date.md"; if (Test-Path $md) { Copy-Item $md "D:/Dev/repos/mcp-central-docs/reports/" -Force; Write-Host "Synced $md to mcd" }

build-native:
	$env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
	Set-Location "{{justfile_directory()}}/src-tauri"
	powershell -NoProfile -ExecutionPolicy Bypass -File "src-tauri/build.ps1"
