# WattWhere

> Ask questions about the energy transition in Baden-Württemberg in plain language and get answers on a map, in charts and in text. _(Full README is written in Phase 8.)_

## Use the tools from Claude Desktop (MCP)

The same six tools the web app uses are available over the Model Context Protocol (stdio). They answer from your local PostGIS database, so run `make db-up` first and import data (`make seed-sample` for a quick start).

Add this to `claude_desktop_config.json` (replace `/ABSOLUTE/PATH/TO/wattwhere`):

```json
{
  "mcpServers": {
    "wattwhere": {
      "command": "uv",
      "args": [
        "run", "--directory", "/ABSOLUTE/PATH/TO/wattwhere/backend",
        "python", "-m", "mcp_server.server"
      ]
    }
  }
}
```

Tools: `find_municipality`, `capacity_summary`, `rank_municipalities`, `units_near`, `capacity_timeseries`, `run_readonly_sql`. Resource: `wattwhere://schema`.

Test it with the MCP Inspector (`make mcp-inspect`, or `npx @modelcontextprotocol/inspector uv run --directory <abs path>/backend python -m mcp_server.server`).
