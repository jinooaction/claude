"""자율 캐너리 → 풀라이브 승격 (스펙 026).

헌법 VI(단계적 출시) + IX.B-2: 풀라이브 승격은 라이브 캐너리가 사전 선언된 합격
지표를 만족한 뒤에만 허용된다. 이 패키지는 그 판단(게이트)과 적용을 담는다.
게이트는 순수·결정론적이고, 어떤 지표든 측정 불가(None)면 보수적으로 불합격이다.
"""

from auto_invest.promotion.gate import (
    PromotionReadiness,
    evaluate_promotion_readiness,
)

__all__ = ["PromotionReadiness", "evaluate_promotion_readiness"]
