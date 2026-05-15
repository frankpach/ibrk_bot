# tests/mocks/mock_llm.py
from app.application.ports.llm_port import ILLMPort
from app.llm.agent import LLMDecision
from app.db.models import Trade


class MockLLMAdapter(ILLMPort):
    def __init__(self, decision: LLMDecision = None):
        self.decision = decision or LLMDecision(
            action="IGNORE", stop_loss_pct=0.025, take_profit_pct=0.06,
            justification="mock", confidence="LOW",
        )

    def analyze_signal(self, symbol, strength, rsi, macd, volume_ratio, signal_id):
        return self.decision

    def run_postmortem(self, trade, feature_snapshot=None):
        pass

    def interpret_analysis(self, symbol, prompt, timeout=60):
        return "mock interpretation"
