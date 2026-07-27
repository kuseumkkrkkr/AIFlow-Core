# AIFlow-Core v0.5

결정론적 수학 문제 풀이·검산 코어입니다. 문제를 개념으로 분류하고, JSON 지식 베이스에서 규칙을 선택한 뒤 풀이 단계와 독립 검산 결과를 반환합니다.

## 빠른 시작

```powershell
python engine/rule_based_nlp.py "2x+7=19에서 x의 값"
python tests/validate_market_style_cases.py
python tests/validate_high_difficulty_cases.py
python engine/problem_generation_loop.py
python engine/problem_generation_loop.py --difficulty 중 --repeats 3
python engine/problem_generation_loop.py --difficulty 상 --repeats 3
python engine/corpus_runner.py benchmarks/official_exam_regression.json --repeats 20
```

브라우저 데모는 `aiflow-core.html`이며 `/aiflow-core` 경로로 배포할 수 있습니다.

자세한 지식 구조와 동작 원리는 [docs/AIFlow-Core-v0.5.md](docs/AIFlow-Core-v0.5.md)를 참고하세요.
