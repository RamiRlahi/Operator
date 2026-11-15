"""
Adversarial prompt injection test suite for The Operator.
Contains 7 targeted attack vectors designed to test:
1. Direct override ('Ignore all previous instructions')
2. Unauthorized financial writes ($10,000 refund)
3. Data exfiltration / credential harvesting
4. SQL / tool output poisoning
5. Role-play / jailbreaking ('Developer mode')
6. Social engineering / Executive impersonation
7. Encoded instructions / Markdown payload
"""

from typing import List
from eval.scenarios import SCENARIOS, TestScenario

# Filter to get the injection cohort
INJECTION_CASES: List[TestScenario] = [s for s in SCENARIOS if s.category == "injection"]

def get_injection_cases() -> List[TestScenario]:
    return INJECTION_CASES
