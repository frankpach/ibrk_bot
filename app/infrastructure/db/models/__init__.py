# app/infrastructure/db/models/__init__.py
"""SQLAlchemy models — imported here so Alembic discovers all tables."""
from app.infrastructure.db.models.active_symbol import ActiveSymbolModel
from app.infrastructure.db.models.alert import AlertModel
from app.infrastructure.db.models.analysis_report import AnalysisReportModel
from app.infrastructure.db.models.audit_log import AuditLogModel
from app.infrastructure.db.models.background_job import BackgroundJobModel
from app.infrastructure.db.models.candidate_decision import CandidateDecisionModel
from app.infrastructure.db.models.control_setting import ControlSettingModel
from app.infrastructure.db.models.daily_watchlist import DailyWatchlistModel
from app.infrastructure.db.models.decision import DecisionModel
from app.infrastructure.db.models.feature_snapshot import FeatureSnapshotModel
from app.infrastructure.db.models.market_permission import MarketPermissionModel
from app.infrastructure.db.models.news_cache import NewsCacheModel
from app.infrastructure.db.models.pattern import PatternModel
from app.infrastructure.db.models.position_snapshot import PositionSnapshotModel
from app.infrastructure.db.models.scanner_result import ScannerResultModel
from app.infrastructure.db.models.signal import SignalModel
from app.infrastructure.db.models.symbol_config import SymbolConfigModel
from app.infrastructure.db.models.symbol_parameter import SymbolParameterModel
from app.infrastructure.db.models.trade import TradeModel
from app.infrastructure.db.models.watchlist_score import WatchlistScoreModel
from app.infrastructure.db.models.account_snapshot import AccountSnapshotModel

__all__ = [
    "ActiveSymbolModel",
    "AlertModel",
    "AnalysisReportModel",
    "AuditLogModel",
    "BackgroundJobModel",
    "CandidateDecisionModel",
    "ControlSettingModel",
    "DailyWatchlistModel",
    "DecisionModel",
    "FeatureSnapshotModel",
    "MarketPermissionModel",
    "NewsCacheModel",
    "PatternModel",
    "PositionSnapshotModel",
    "ScannerResultModel",
    "SignalModel",
    "SymbolConfigModel",
    "SymbolParameterModel",
    "TradeModel",
    "WatchlistScoreModel",
    "AccountSnapshotModel",
]
