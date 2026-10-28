"""
Sovereign Configuration
Central configuration for cluster size, ports, and timeouts.
"""
from __future__ import annotations

import os
from typing import Dict

# Production cluster has EXACTLY 5 nodes.
# Environment variable override is allowed ONLY for test suites.
NODE_COUNT: int = int(os.environ.get("NODE_COUNT", 5))
BASE_PORT: int = 9000
GATEWAY_PORT: int = int(os.environ.get("PORT", 8000))
TELEMETRY_PORT: int = 9090


def get_node_ports(count: int = NODE_COUNT) -> Dict[int, int]:
    """Returns mapping of node_id (1..N) to TCP port (9001..900N)."""
    return {i: BASE_PORT + i for i in range(1, count + 1)}
