$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot

Write-Host 'Installing build dependencies...' -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host 'Verifying RDKit availability...' -ForegroundColor Cyan
python -c "from rdkit import Chem; from rdkit.Chem import Draw; mol = Chem.MolFromSmiles('CCO'); assert mol is not None; print('RDKit OK')"

Write-Host 'Building single-file Windows EXE...' -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean mass_finding.spec

Write-Host ''
Write-Host 'Build completed.' -ForegroundColor Green
Write-Host 'Output EXE: dist/MassFinding.exe' -ForegroundColor Green
Write-Host 'Runtime cache folder: %LOCALAPPDATA%/MassFinding/mass_finding_cache' -ForegroundColor Yellow
