import requests

# This should be flagged - no timeout
requests.get("http://example.com")

# This should be flagged - no timeout
requests.get("http://example.com", headers={"User-Agent": "test"})

# This should NOT be flagged - has timeout
requests.get("http://example.com", timeout=30)

# This should NOT be flagged - has timeout
requests.get("http://example.com", headers={"User-Agent": "test"}, timeout=5)
