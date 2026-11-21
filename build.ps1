param(
    [switch]$Zip,
    [ValidatePattern('^[a-zA-Z0-9][a-zA-Z0-9._-]*$')]
    [string]$Version = 'local'
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $venvPython = '.\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv.' }
    }

    & $venvPython -c "import sysconfig; raise SystemExit(sysconfig.get_platform() != 'win-amd64')"
    if ($LASTEXITCODE -ne 0) { throw 'The Windows x64 build requires x64 Python.' }

    & $venvPython -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw 'Could not install PyInstaller.' }

    & $venvPython -m PyInstaller --onedir --windowed --noconfirm --name GitHubFolderComparison --specpath build app.py
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

    Write-Host 'Application: dist\GitHubFolderComparison\GitHubFolderComparison.exe'
    if ($Zip) {
        $archive = "dist\GitHubFolderComparison-$Version-windows-x64.zip"
        & $venvPython -m zipfile -c $archive 'dist\GitHubFolderComparison'
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the release archive.' }
        Write-Host "Archive: $archive"
    }
}
finally {
    Pop-Location
}
