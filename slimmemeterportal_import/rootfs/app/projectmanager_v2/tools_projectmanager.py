"""Projectmanager MCP implementation lives in Infra/Docker/native-mcp.

This package intentionally contains no MCP registration and no RuntimeV2 write
surface. RuntimeV2 has exactly one writer: the embedded Projectmanager.
External command proposals use Data/03_Systeem/Projectmanager/CommandIngress;
Peter approvals use the authenticated Home Assistant ApprovalIngress UI.
"""

MCP_TOOL_IMPLEMENTATION = 'Infra/Docker/native-mcp/tools_projectmanager.py'
RUNTIME_WRITE_SURFACE = False
