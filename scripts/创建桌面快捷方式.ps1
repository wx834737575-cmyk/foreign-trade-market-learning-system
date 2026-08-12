$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonw = Join-Path $projectRoot 'backend\.runtime\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) {
    $pythonw = Join-Path $projectRoot 'backend\.venv\Scripts\pythonw.exe'
}
$launcher = Join-Path $projectRoot 'launcher.py'
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw '尚未安装本地运行环境，请先双击“首次安装.cmd”。'
}
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop '外贸与投资决策系统.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = ('"{0}"' -f $launcher)
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = '打开外贸与投资决策系统'
$shortcut.IconLocation = "$pythonw,0"
$shortcut.Save()
Write-Host "桌面快捷方式已创建：$shortcutPath"
