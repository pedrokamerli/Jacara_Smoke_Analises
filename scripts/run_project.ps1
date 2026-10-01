param(
    [ValidateSet('Demo', 'Real')][string]$Mode = 'Demo',
    [ValidateSet('Local', 'Oidc')][string]$AuthMode = 'Local',
    [switch]$Refresh,
    [int]$Port = 8501,
    [string]$SourceRoot
)

$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Crie .venv e instale requirements.txt e o pacote do projeto antes de executar.'
}
if (-not $SourceRoot) { $SourceRoot = $projectPath }
Push-Location $projectPath
$previousPublicMode = $env:JACARE_PUBLIC_MODE
$previousAuthMode = $env:JACARE_AUTH_MODE
try {
    # Este lançador é estritamente local (127.0.0.1); habilita importação explicitamente.
    $env:JACARE_PUBLIC_MODE = if ($Mode -eq 'Real') { 'false' } else { 'true' }
    $env:JACARE_AUTH_MODE = $AuthMode.ToLowerInvariant()
    if ($Refresh) {
        if ($Mode -ne 'Real') { throw 'Refresh só é permitido com -Mode Real. Demo: python -m jacare_analytics.demo.' }
        & $pythonPath -m jacare_analytics.pipeline --source-root $SourceRoot
        if ($LASTEXITCODE -ne 0) { throw 'A atualização falhou; revise a mensagem do pipeline.' }
    }
    & $pythonPath -m streamlit run app/streamlit_app.py --server.port $Port --server.address 127.0.0.1
} finally {
    if ($null -eq $previousAuthMode) { Remove-Item Env:JACARE_AUTH_MODE -ErrorAction SilentlyContinue }
    else { $env:JACARE_AUTH_MODE = $previousAuthMode }
    if ($null -eq $previousPublicMode) {
        Remove-Item Env:JACARE_PUBLIC_MODE -ErrorAction SilentlyContinue
    } else {
        $env:JACARE_PUBLIC_MODE = $previousPublicMode
    }
    Pop-Location
}
