# app/application/ports/llm_port.py
from abc import ABC, abstractmethod

from app.llm.agent import LLMDecision
from app.db.models import Trade


class ILLMPort(ABC):
    @abstractmethod
    def analyze_signal(self, symbol: str, strength: str, rsi: float, macd: float,
                       volume_ratio: float, signal_id: int) -> LLMDecision:
        ...

    @abstractmethod
    def run_postmortem(self, trade: Trade, feature_snapshot=None) -> None:
        ...

    @abstractmethod
    def interpret_analysis(self, symbol: str, prompt: str, timeout: int = 60) -> str:
        ...
