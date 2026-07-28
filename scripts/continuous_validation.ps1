<#!
AIFlow-Core 무료 로컬 검증 루프

필요 변수: 저장소 루트 경로와 Python 실행기.
작동 원리: GitHub Actions 없이 핵심 엔진·생성·코퍼스·다중 seed 검증을 순서대로 실행하고
각 단계의 실패 즉시 종료한다. 모든 생성 결과는 UTF-8로 저장된다.
#>
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Invoke-ValidationStep {
    <# 필요 변수: 단계 이름과 Python 인자. 반환값: 실패 시 즉시 종료. #>
    param([string]$Name, [string[]]$Arguments)
    Write-Host "[RUN] $Name" -ForegroundColor Cyan
    & python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "검증 실패: $Name (exit=$LASTEXITCODE)" }
    Write-Host "[PASS] $Name" -ForegroundColor Green
}

Invoke-ValidationStep "핵심 규칙" @("tests/test_rule_based_nlp.py")
Invoke-ValidationStep "LaTeX router" "tests/test_latex_and_routing.py"
Invoke-ValidationStep "knowledge contract" "tests/test_knowledge_catalog.py"
Invoke-ValidationStep "API serialization" "tests/test_api_serialization.py"
Invoke-ValidationStep "문제 생성 루프" @("tests/test_generation_loop.py")
Invoke-ValidationStep "생성 검증 계약" @("tests/test_generation_validation.py")
Invoke-ValidationStep "다중 seed 매트릭스" @("tests/test_benchmark_matrix.py")
Invoke-ValidationStep "코퍼스 검증기" @("tests/test_corpus_runner.py")
Invoke-ValidationStep "시장형 코퍼스 반복" @("engine/corpus_runner.py", "benchmarks/market_style_corpus.json", "--repeats", "20", "--output", "docs/corpus_validation_local.json")
Invoke-ValidationStep "전체 학년 매트릭스" @("engine/run_benchmark_matrix.py", "--seeds", "1,2,3,4,5", "--repeats", "2", "--output", "docs/benchmark_matrix_local.json")
Write-Host "전체 로컬 검증 완료" -ForegroundColor Green
