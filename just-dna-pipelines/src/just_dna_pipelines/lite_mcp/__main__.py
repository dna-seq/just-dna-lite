"""``python -m just_dna_pipelines.lite_mcp [--transport http --port N]`` — the launcher's argv for the MCP server."""

from just_dna_pipelines.lite_mcp.server import main

if __name__ == "__main__":
    main()
