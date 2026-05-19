# Troubleshooting Guide

## Common Issues and Solutions

### 500 Internal Server Error on `/candidate-analysis/{symbol}`

**Symptom**: Dashboard shows 500 error when clicking "Analizar" or calling the endpoint directly.

**Root Cause**: Missing Python dependencies, most commonly `feedparser`.

**Solution**:
```bash
# Install all dependencies from requirements.txt
pip install -r requirements.txt

# Or install the specific missing package
pip install feedparser==6.0.11
```

**Verification**:
```bash
# Test the endpoint
python -c "
from fastapi.testclient import TestClient
from app.api.main import app
client = TestClient(app)
response = client.get('/candidate-analysis/AAPL')
print(f'Status: {response.status_code}')
print(f'Response: {response.json()}')
"
```

### ModuleNotFoundError Errors

If you see errors like:
```
ModuleNotFoundError: No module named 'feedparser'
ModuleNotFoundError: No module named 'telegram'
```

**Solution**: Reinstall all dependencies:
```bash
pip install -r requirements.txt --force-reinstall
```

### IB Gateway Connection Issues

**Symptom**: Logs show "Connection refused" or "Not connected" errors.

**Expected Behavior**: If `IB_MOCK=false` but IB Gateway is not running, the system will:
1. Attempt to connect 3 times
2. Fall back to offline mode
3. Continue with mock data for testing

**Solution** (if you need real IB connection):
1. Start IB Gateway on the configured host/port
2. Ensure API port is enabled in IB Gateway settings
3. Verify connectivity: `telnet <IB_HOST> <IB_PORT>`

### Database Initialization Errors

**Symptom**: Errors about missing tables or SQLite database file.

**Solution**:
```bash
# Initialize database tables
python -c "from app.infrastructure.db.compat import init_db; init_db()"

# Or run migrations
alembic upgrade head
```

### Container Initialization Errors

**Symptom**: Errors when creating the dependency injection container.

**Solution**: The container gracefully handles missing connections by falling back to mock adapters. Check logs for specific adapter errors.

## Debugging Tips

### Enable Verbose Logging

Add to `.env`:
```
LOG_LEVEL=DEBUG
```

### Test Individual Components

```bash
# Test job runner
python -c "
from app.application.services.job_runner import get_global_runner
runner = get_global_runner()
print('Job runner OK:', runner)
"

# Test container
python -c "
from app.container import get_container
c = get_container()
print('Container OK:', c)
"

# Test data layer
python -c "
from app.llm.agent import get_data_layer
dl = get_data_layer()
print('Data layer OK:', dl)
"
```

### Check Server Health

```bash
# Health endpoint
curl http://localhost:8088/health

# Check running jobs
curl http://localhost:8088/jobs

# Check specific job
curl http://localhost:8088/jobs/<JOB_ID>
```

## Performance Issues

### Slow Analysis

The `/candidate-analysis` endpoint has a 60-second timeout. If analysis consistently times out:

1. Check IB Gateway connectivity (slow data fetch)
2. Reduce LLM token limits in agent configuration
3. Check network latency to external APIs

### Memory Issues

If running on Raspberry Pi with limited RAM:

1. Monitor memory: `free -h`
2. Reduce `max_workers` in `BackgroundJobRunner` (default: 3)
3. Limit concurrent scans in scheduler

## Support

For issues not covered here:

1. Check application logs in the running server
2. Review recent changes in git history
3. Test with `IB_MOCK=true` to isolate IB-related issues
4. Run pytest suite: `pytest tests/ --timeout=60 -q`
