"""
start_mcp.py
Simple script to start the MCP server
"""
import sys
import subprocess

print("Starting AI Excel Agent MCP Server...")
print("Server name: ai-excel-agent")
print("Skills: 67 Excel automation skills")
print("Protocol: MCP 1.29.0 (stdio)")
print("\nServer is running and waiting for MCP clients...")
print("Configure Claude Desktop to connect (see MCP_SETUP.md)")
print("\nPress Ctrl+C to stop\n")

try:
    subprocess.run([sys.executable, "-m", "mcp_server.server"])
except KeyboardInterrupt:
    print("\n\nMCP Server stopped")
