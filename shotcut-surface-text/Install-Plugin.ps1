# Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
[CmdletBinding()]
param([string]$ShotcutPath, [switch]$NoDialog)
$ErrorActionPreference='Stop'
try {
    if (Get-Process -Name shotcut -ErrorAction SilentlyContinue) { throw '请先保存项目并关闭 Shotcut，再安装滤镜。' }
    Add-Type -AssemblyName System.Windows.Forms
    if (-not $ShotcutPath) {
        $picker=New-Object Windows.Forms.OpenFileDialog
        $picker.Title='请选择 Shotcut 的 shotcut.exe（建议使用可写的官方便携版）'
        $picker.Filter='Shotcut|shotcut.exe'
        try { if ($picker.ShowDialog() -ne 'OK') {exit 2}; $ShotcutPath=$picker.FileName } finally {$picker.Dispose()}
    }
    if (Test-Path -LiteralPath $ShotcutPath -PathType Container) {$ShotcutPath=Join-Path $ShotcutPath 'shotcut.exe'}
    if (-not (Test-Path -LiteralPath $ShotcutPath -PathType Leaf) -or [IO.Path]::GetFileName($ShotcutPath) -ine 'shotcut.exe') { throw '请选择有效的 shotcut.exe。' }
    $pluginRoot=Join-Path (Split-Path -Parent (Resolve-Path -LiteralPath $ShotcutPath).ProviderPath) 'lib/frei0r-1'
    if (-not (Test-Path -LiteralPath $pluginRoot -PathType Container)) {throw '此版本目录布局不受支持，缺少 lib/frei0r-1。请使用官方 Windows x64 便携版。'}
    $shotcutDir=Split-Path -Parent (Resolve-Path -LiteralPath $ShotcutPath).ProviderPath
    $filtersRoot=Join-Path $shotcutDir 'share/shotcut/qml/filters'
    if (-not (Test-Path -LiteralPath $filtersRoot -PathType Container)) {throw '此版本目录布局不受支持，缺少 share/shotcut/qml/filters。请使用官方 Windows x64 便携版。'}
    $source=Join-Path $PSScriptRoot 'bin/windows/surfacepin.dll'
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {throw '缺少 Windows 滤镜 DLL，请完整解压部署包。'}
    $target=Join-Path $pluginRoot 'surfacepin.dll'
    $qmlTarget=Join-Path $filtersRoot 'surface_text'
    $backupSuffix='.surface-text-backup-'+(Get-Date -Format 'yyyyMMddHHmmss')+'-'+[guid]::NewGuid().ToString('N')
    if (Test-Path -LiteralPath $qmlTarget) {
        # A directory backup outside the filters search tree avoids duplicate metadata.
        $backupRoot=Join-Path $shotcutDir 'surface-text-backups'
        [void][IO.Directory]::CreateDirectory($backupRoot)
        Copy-Item -LiteralPath $qmlTarget -Destination (Join-Path $backupRoot ('surface_text'+$backupSuffix)) -Recurse
    }
    if (Test-Path -LiteralPath $target) {Copy-Item -LiteralPath $target -Destination ($target+$backupSuffix)}
    try {Copy-Item -LiteralPath $source -Destination $target -Force} catch {throw '安装目录不可写。请改用解压在用户目录的官方便携版；助手不会请求管理员权限。'}
    [void][IO.Directory]::CreateDirectory($qmlTarget)
    foreach($name in @('meta.qml','ui.qml','Track.js')) {Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('shotcut-filter/'+$name)) -Destination (Join-Path $qmlTarget $name) -Force}
    if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {throw 'DLL 复制后校验失败，请重新安装。'}
    $message="安装完成。重启 Shotcut，在视频滤镜中搜索：表面贴字。`n`nDLL: $target`n界面: $qmlTarget`n`n然后双击 Start-Assistant.cmd 开始选四角。"
    Write-Output $message
    if (-not $NoDialog) {[void][Windows.Forms.MessageBox]::Show($message,'Surface Text')}
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
