# Extending the System

## Adding a New Use Case

1. Create `app/application/use_cases/my_use_case.py`:
```python
from app.application.ports.broker_port import IBrokerPort
from app.application.ports.notification_port import INotificationPort
from app.application.event_bus import EventBus

class MyUseCase:
    def __init__(self, broker: IBrokerPort, notifier: INotificationPort, event_bus: EventBus):
        self._broker = broker
        self._notifier = notifier
        self._event_bus = event_bus

    def execute(self, ...) -> MyResult:
        # business logic
        self._event_bus.publish(SomeDomainEvent(...))
        return MyResult(...)
```

2. Add to `Container.__init__` in `app/container.py`:
```python
self.my_use_case = MyUseCase(broker=self.broker, notifier=self.notifier, event_bus=self.event_bus)
```

3. Wire into an API route:
```python
# app/interfaces/api/routes/my_routes.py
from app.container import get_container

@router.post("/my-action")
def my_action(req: MyRequest):
    return get_container().my_use_case.execute(req.param)
```

4. Write tests using `test_container()`:
```python
from app.container import test_container

def test_my_use_case():
    c = test_container()  # MockBrokerAdapter, in-memory SQLite
    result = c.my_use_case.execute(...)
    assert result.success
```

## Adding a New Domain Event

1. Add a frozen dataclass to `app/domain/trading/events.py`:
```python
@dataclass(frozen=True)
class MyEvent:
    entity_id: int
    payload: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
```

2. Register a handler in `Container._register_event_handlers()`:
```python
self.event_bus.subscribe(MyEvent, audit_handler.handle)
self.event_bus.subscribe(MyEvent, self._on_my_event)
```

3. Publish from a use case:
```python
self._event_bus.publish(MyEvent(entity_id=123, payload="..."))
```

## Adding a New SQLAlchemy Model

1. Create `app/infrastructure/db/models/my_model.py`:
```python
from app.infrastructure.db.base import Base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

class MyModel(Base):
    __tablename__ = "my_table"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

2. Import in `app/infrastructure/db/models/__init__.py`

3. Generate migration:
```bash
alembic revision --autogenerate -m "add my_table"
alembic upgrade head
```

## Adding a New API Route File

1. Create `app/interfaces/api/routes/my_routes.py` with `router = APIRouter()`
2. Register in `app/interfaces/api/app.py`:
```python
from app.interfaces.api.routes.my_routes import router as my_router
app.include_router(my_router, prefix="/my", tags=["My Feature"])
```

## Adding a New Port (Interface)

1. Create `app/application/ports/my_port.py`:
```python
from abc import ABC, abstractmethod

class IMyPort(ABC):
    @abstractmethod
    def do_thing(self, input: str) -> str: ...
```

2. Create production adapter: `app/infrastructure/my_service/my_adapter.py`
3. Create mock: `tests/mocks/mock_my.py`
4. Inject via Container: `self.my_port = MyAdapter() or passed_in_mock`

## Circular Import Rules

- Never import `from app.container import get_container` at module top level
- Only call `get_container()` inside function bodies (lazy import pattern)
- `app/domain/` has zero imports from other app layers
- `app/application/ports/` has zero imports from `app/infrastructure/`

## Testing Patterns

```python
# Use test_container() for isolation — never get_container() in tests
from app.container import test_container

def test_something():
    c = test_container()
    # c.broker is MockBrokerAdapter
    # c.notifier is MockNotificationAdapter
    # c.engine is in-memory SQLite
    # All wired, all isolated
```

```python
# To test with specific mock state:
from tests.mocks.mock_broker import MockBrokerAdapter
from decimal import Decimal

broker = MockBrokerAdapter(
    prices={"AAPL": Decimal("200.00")},
    prev_closes={"AAPL": Decimal("195.00")},
)
```
