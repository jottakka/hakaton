"""BenchmarkControl Arcade MCP server.

Owns triggering, status, history, and comparisons for AIOA and GEO benchmark
runs. Tool handlers are implemented in later tasks; this module defines the
app entry point and wires it to the transport.
"""

import sys

from arcade_mcp_server import MCPApp

app = MCPApp(
    name="BenchmarkControl",
    version="0.1.0",
    instructions=(
        "Control plane for AIOA and GEO benchmark runs. "
        "Use StartRun to trigger a new benchmark, then GetRunStatus, "
        "ListRuns, GetRunReport, GetRunArtifacts, or CompareAioaRuns "
        "to inspect historical results."
    ),
    log_level="INFO",
)

if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    app.run(transport=transport, host="127.0.0.1", port=8001)
