# Dot-source this file: . ./scripts/dev-env.ps1
# Existing terminals may predate installation; preserve process overrides and load saved user settings.
foreach ($taskEngineVariable in @('PCBAI_TRACEMAKER', 'PCBAI_TRACEMAKER_PLACE')) {
    if (-not [Environment]::GetEnvironmentVariable($taskEngineVariable, 'Process')) {
        $taskEngineSetting = [Environment]::GetEnvironmentVariable($taskEngineVariable, 'User')
        if ($taskEngineSetting) {
            [Environment]::SetEnvironmentVariable($taskEngineVariable, $taskEngineSetting, 'Process')
        }
    }
}
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskVenv = Join-Path $taskRoot '.venv\Scripts'
if (Test-Path -LiteralPath (Join-Path $taskVenv 'python.exe')) {
    $env:PATH = $taskVenv + [IO.Path]::PathSeparator + $env:PATH
}
$taskNode = Join-Path $taskRoot '.tools\node\node.exe'
if (-not $env:PCBAI_NODE -and (Test-Path -LiteralPath $taskNode)) {
    $env:PCBAI_NODE = $taskNode
    $env:PATH = (Split-Path $taskNode -Parent) + [IO.Path]::PathSeparator + $env:PATH
}
$taskJar = Join-Path $taskRoot '.tools\freerouting\freerouting-2.5.0.jar'
$taskJre = Get-ChildItem -LiteralPath (Join-Path $taskRoot '.tools') -Directory -Filter 'jdk-*-jre' -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
if (-not $env:PCBAI_JAVA -and $taskJre) {
    $taskJava = Join-Path $taskJre.FullName 'bin\java.exe'
    if (Test-Path -LiteralPath $taskJava) { $env:PCBAI_JAVA = $taskJava }
}
if (-not $env:PCBAI_FREEROUTING -and $env:PCBAI_JAVA -and (Test-Path -LiteralPath $taskJar)) {
    $env:PCBAI_FREEROUTING = $taskJar
}
