<#
공식 시험의 렌더된 페이지 이미지를 Windows 내장 OCR로 비공개 텍스트로 추출한다.

필요 변수: ImagePath(PNG/JPEG 페이지), OutputDirectory(비공개 출력), LanguageTag(기본 ko).
작동 원리: Windows Runtime의 BitmapDecoder가 렌더된 페이지 이미지를 읽고 OCR 엔진이
텍스트를 인식한다. 입력 이미지와 OCR 결과는 private_benchmarks 안에서만 보관하며,
Git·Vercel 경로에는 쓰지 않는다. OCR 오인식은 자동 정답 데이터로 승격하지 않는다.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory,

    [string]$LanguageTag = 'ko'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Runtime.WindowsRuntime

# 변수: WinRT 비동기 작업과 결과 형식. 원리: IAsyncOperation<T>를 .NET Task<T>로 안전하게 대기한다.
$script:WinRtAsTask = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } |
    Select-Object -First 1

function Get-WinRtResult {
    <#
    변수: Operation(WinRT IAsyncOperation), ResultType(반환 형식).
    작동 원리: Windows Runtime 비동기 작업을 Task로 변환해 끝날 때까지 기다린 뒤 결과를 돌려준다.
    #>
    param(
        [Parameter(Mandatory = $true)]$Operation,
        [Parameter(Mandatory = $true)][Type]$ResultType
    )

    $task = $script:WinRtAsTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}

function Assert-PrivateOutputDirectory {
    <#
    변수: OutputDirectory. 작동 원리: PDF OCR 전문이 저장소·배포 경로에 기록되지 않도록 private_benchmarks 하위만 허용한다.
    #>
    param([Parameter(Mandatory = $true)][string]$Path)

    $projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $privateRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'private_benchmarks'))
    $candidate = [IO.Path]::GetFullPath($Path)
    if (-not $candidate.StartsWith($privateRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'OCR 출력 경로는 private_benchmarks 하위여야 합니다.'
    }
    return $candidate
}

function Invoke-PageImageOcr {
    <#
    변수: 페이지 이미지 경로·출력 폴더·OCR 언어. 작동 원리: OCR 텍스트와 최소 메타데이터를 UTF-8로 기록한다.
    #>
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$Language
    )

    $source = (Resolve-Path -LiteralPath $SourcePath).Path
    $destination = Assert-PrivateOutputDirectory -Path $Destination
    New-Item -ItemType Directory -Force -Path $destination | Out-Null

    [void][Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    [void][Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    [void][Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType = WindowsRuntime]
    [void][Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
    [void][Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    [void][Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    [void][Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType = WindowsRuntime]

    $ocrLanguage = [Windows.Globalization.Language]::new($Language)
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($ocrLanguage)
    if ($null -eq $engine) {
        throw "설치된 Windows OCR 언어가 아닙니다: $Language"
    }

    $file = Get-WinRtResult ([Windows.Storage.StorageFile]::GetFileFromPathAsync($source)) ([Windows.Storage.StorageFile])
    $stream = Get-WinRtResult ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    try {
        $decoder = Get-WinRtResult ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Get-WinRtResult ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        try {
            $result = Get-WinRtResult ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            $textPath = Join-Path $destination ("{0}.ocr.txt" -f [IO.Path]::GetFileNameWithoutExtension($source))
            Set-Content -LiteralPath $textPath -Value $result.Text -Encoding utf8
            $metadata = [ordered]@{
                source_image_sha256 = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
                source_file = [IO.Path]::GetFileName($source)
                language = $Language
                pages_extracted = 1
                output_file = [IO.Path]::GetFileName($textPath)
                warning = 'OCR 결과는 원문 수식·도형과 다를 수 있다. 문항·정답 데이터 승격 전 사람이 원본 이미지와 대조해야 한다.'
            }
            $metadata | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $destination 'ocr_manifest.json') -Encoding utf8
            return $metadata
        }
        finally { $bitmap.Dispose() }
    }
    finally { $stream.Dispose() }
}

Invoke-PageImageOcr -SourcePath $ImagePath -Destination $OutputDirectory -Language $LanguageTag | ConvertTo-Json -Depth 3
