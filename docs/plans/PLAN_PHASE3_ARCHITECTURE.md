# Phase 3: Extract God Classes (Architecture)

**Status**: Pending
**Effort**: Large
**Risk**: Medium - refactoring

## Rationale

DataOrchestrator (1,827 lines, 50 methods) and AuthDiscovery (1,415 lines) are too large to maintain and test effectively.

---

## 3.1 Extract ParserDetectionPipeline

**Current location:** `core/data_orchestrator.py` (lines 888-1063, 1196-1259)

**New file:** `core/parser_detection.py`

### What to Extract

**Detection methods (~15 methods):**
- `_detect_parser()`
- `_try_parser_detection()`
- `_detect_with_parser()`
- `_match_parser_by_content()`
- `_match_parser_by_url()`
- All `_is_*` detection helpers

**Detection phase logic:**
- Phase 0: Direct match from config
- Phase 1: URL pattern matching
- Phase 1b: Content-based detection
- Phase 2: Heuristic matching
- Phase 3: Fallback parser

### New Class Structure

```python
# core/parser_detection.py

class ParserDetectionPipeline:
    """Handles parser detection across multiple phases."""

    def __init__(self, parsers: list[type[ModemParser]], config: ModemConfig):
        self.parsers = parsers
        self.config = config

    def detect(self, response: Response, url: str) -> type[ModemParser] | None:
        """Run detection pipeline and return matching parser."""
        for phase in self._get_phases():
            result = phase.detect(response, url)
            if result:
                return result
        return None

    def _get_phases(self) -> list[DetectionPhase]:
        return [
            DirectMatchPhase(self.config),
            URLPatternPhase(self.parsers),
            ContentMatchPhase(self.parsers),
            HeuristicPhase(self.parsers),
            FallbackPhase(),
        ]
```

### Benefits
- Reduces DataOrchestrator by ~400 lines
- Each detection phase independently testable
- Easier to add new detection strategies
- Clear separation of concerns

---

## 3.2 Extract ResponseBuilder

**Current location:** `core/data_orchestrator.py` (lines 1539-1603, 1616-1682)

**New file:** `core/response_builder.py`

### What to Extract

- `_build_response()` method
- `_merge_config_data()` helper
- `_aggregate_channels()` helper
- Response formatting logic

### New Class Structure

```python
# core/response_builder.py

class ResponseBuilder:
    """Builds modem data response from parser output and config."""

    def __init__(self, config: ModemConfig):
        self.config = config

    def build(self, parser_data: ParseResult) -> dict[str, Any]:
        """Merge parser data with config to build response."""
        return {
            "downstream": self._format_downstream(parser_data["downstream"]),
            "upstream": self._format_upstream(parser_data["upstream"]),
            "system_info": self._merge_system_info(parser_data["system_info"]),
            "metadata": self._build_metadata(),
        }
```

### Benefits
- Reduces DataOrchestrator by ~150 lines
- Separates orchestration from presentation
- Easier to test response formatting

---

## 3.3 Extract DiagnosticsCapture (Optional)

**Current location:** `core/data_orchestrator.py` (lines 303-401)

**New file:** `core/diagnostics_capture.py`

### What to Extract

- `_capture_response()` method
- `_record_failed_url()` method
- `_captured_urls`, `_failed_urls` state
- `_capture_enabled` flag logic

### Design Options

**Option A: Wrapper/Decorator Pattern**
```python
class DiagnosticsCapture:
    """Wraps HTTP fetching to capture responses for diagnostics."""

    def __init__(self, fetcher: Fetcher):
        self.fetcher = fetcher
        self.captured_urls: list[CapturedURL] = []
        self.failed_urls: list[FailedURL] = []

    async def fetch(self, url: str) -> Response:
        response = await self.fetcher.fetch(url)
        self._capture(url, response)
        return response
```

**Option B: Mixin Pattern**
```python
class DiagnosticsCaptureMixin:
    """Mixin for adding diagnostics capture to orchestrator."""

    def _capture_response(self, url: str, response: Response) -> None:
        ...
```

### Benefits
- Removes cross-cutting concern from orchestrator
- Can be enabled/disabled cleanly
- Capture logic isolated and testable

---

## 3.4 Refactor AuthDiscovery (Future)

**Current location:** `core/auth/discovery.py` (1,415 lines, 40+ methods)

**Note:** This is a larger effort that could be deferred. The class handles:
- Form auth detection
- HNAP detection
- URL token detection
- JS-based auth detection
- Combined form handling

**Potential split:**
- `FormAuthDetector`
- `HNAPDetector`
- `URLTokenDetector`
- `AuthDiscoveryCoordinator`

---

## Files Summary

### New Files
- `core/parser_detection.py` - Parser detection pipeline
- `core/response_builder.py` - Response construction
- `core/diagnostics_capture.py` - Diagnostics wrapper (optional)

### Modified Files
- `core/data_orchestrator.py` - Reduced from 1,827 to ~1,200 lines

---

## Verification

```bash
ruff check .
pytest

# Specific tests for extracted classes
pytest tests/core/test_parser_detection.py
pytest tests/core/test_response_builder.py
```

### Integration Testing
1. Deploy to local HA instance
2. Test parser detection with multiple modem types
3. Verify diagnostics capture still works
4. Verify response format unchanged

---

## Dependencies

- Should be done after Phase 1 (schemas) for type safety
- Independent of Phase 2 (auth)

## Migration Strategy

1. Create new classes with same logic (copy, don't cut)
2. Add tests for new classes
3. Update DataOrchestrator to use new classes
4. Remove duplicated code from DataOrchestrator
5. Verify all tests pass
