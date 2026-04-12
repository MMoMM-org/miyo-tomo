# version: 0.2.0
"""kado_client.py — Lightweight MCP client for Kado's StreamableHTTP transport.

Communicates with the Kado MCP server via JSON-RPC 2.0 over HTTP POST /mcp.
Uses Python stdlib only (urllib.request, json) — no external dependencies.

Configuration (in priority order):
  1. Arguments to KadoClient.__init__
  2. Environment variables: KADO_URL, KADO_TOKEN
  3. .mcp.json in the current working directory

Usage:
  from lib.kado_client import KadoClient
  client = KadoClient()
  items = client.list_dir("Calendar")
  note  = client.read_note("Calendar/2026-03-31.md")

  # Verify connectivity
  python3 -m lib.kado_client --test
"""

import json
import os
import sys
import urllib.error
import urllib.request

# ── Constants ──────────────────────────────────────────────────────────────────

_DEFAULT_TIMEOUT = 30  # seconds


# ── Exceptions ─────────────────────────────────────────────────────────────────

class KadoError(Exception):
    """Base exception for all Kado client errors."""


class KadoConnectionError(KadoError):
    """Raised when the server is unreachable."""


class KadoAuthError(KadoError):
    """Raised on 401/403 responses."""


class KadoNotFoundError(KadoError):
    """Raised when the requested resource does not exist (404 or MCP not-found)."""


class KadoToolError(KadoError):
    """Raised when the MCP tool returns isError: true."""


# ── Client ─────────────────────────────────────────────────────────────────────

class KadoClient:
    """Lightweight MCP client for the Kado vault gateway.

    Wraps the three Kado MCP tools (kado-read, kado-search, kado-write) as
    typed Python methods. Pagination is handled automatically: search methods
    follow the cursor until the result set is exhausted.
    """

    def __init__(self, base_url: str = None, token: str = None):
        """Initialise the client.

        Parameters
        ----------
        base_url:
            Base URL of the Kado MCP server, e.g. ``http://host.docker.internal:37022``.
            Defaults to the ``KADO_URL`` environment variable, or falls back to
            ``.mcp.json`` discovery.
        token:
            Bearer token for the Kado API key.
            Defaults to the ``KADO_TOKEN`` environment variable, or falls back to
            ``.mcp.json`` discovery.
        """
        resolved_url, resolved_token = _resolve_config(base_url, token)
        if not resolved_url:
            raise KadoError(
                "Kado base URL not found. Set KADO_URL env var, pass base_url=, "
                "or add a .mcp.json with kado URL in the current directory."
            )
        if not resolved_token:
            raise KadoError(
                "Kado token not found. Set KADO_TOKEN env var, pass token=, "
                "or add a .mcp.json with kado token in the current directory."
            )

        # Normalize endpoint: tolerate URLs that already include /mcp so we don't
        # end up with /mcp/mcp. Installer writes the full URL in .mcp.json.
        normalized = resolved_url.rstrip("/")
        if not normalized.endswith("/mcp"):
            normalized += "/mcp"
        self._endpoint = normalized
        self._token = resolved_token
        self._req_id = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def read_note(self, path: str) -> dict:
        """Read note content.

        Returns
        -------
        dict with keys: content (str), created (int), modified (int), size (int)
        """
        return self._call_read("note", path)

    def read_frontmatter(self, path: str) -> dict:
        """Read frontmatter as a parsed dict.

        Returns
        -------
        dict with keys: content (dict), created (int), modified (int), size (int)
        """
        result = self._call_read("frontmatter", path)
        # content is returned as a JSON string — parse it if it's still a string
        if isinstance(result.get("content"), str):
            try:
                result["content"] = json.loads(result["content"])
            except json.JSONDecodeError:
                pass  # leave as-is if not valid JSON
        return result

    def list_dir(self, path: str = "/", *, depth: int = None, limit: int = 500) -> list:
        """List items under a vault path.

        Returns both files and folders, each carrying a ``type`` field
        (``'file'`` or ``'folder'``).  Folder items have zero-valued
        ``size``, ``created``, ``modified`` — guard on
        ``item['type'] == 'file'`` before using stat fields.

        Parameters
        ----------
        path:
            Vault-relative path, e.g. ``"Calendar"``.
            Use ``"/"`` (default) for the vault root.
        depth:
            Maximum recursion depth.  ``1`` returns direct children only.
            ``None`` (default) recurses without limit.
        limit:
            Page size for Kado's cursor-based pagination.
        """
        return self._search_all("listDir", path=path or "/", depth=depth, limit=limit)

    def search_by_tag(self, tag: str, limit: int = 500) -> list:
        """Find notes that carry the given tag.

        Returns
        -------
        list of dicts, each with at minimum: path (str)
        """
        return self._search_all("byTag", query=tag, limit=limit)

    def search_by_name(self, query: str, limit: int = 500) -> list:
        """Find notes whose filename matches the query/glob.

        Returns
        -------
        list of dicts, each with at minimum: path (str)
        """
        return self._search_all("byName", query=query, limit=limit)

    def search_by_content(self, query: str, limit: int = 500) -> list:
        """Find notes whose body contains the query string.

        Returns
        -------
        list of dicts, each with at minimum: path (str)
        """
        return self._search_all("byContent", query=query, limit=limit)

    def list_tags(self, limit: int = 500) -> list:
        """List all tags with their note counts.

        Returns
        -------
        list of dicts, each with: tag (str), count (int)
        """
        return self._search_all("listTags", limit=limit)

    def write_note(
        self, path: str, content: str, expected_modified: int = None
    ) -> dict:
        """Write (create or overwrite) a note.

        Parameters
        ----------
        path:
            Vault-relative path, e.g. ``Inbox/new-note.md``.
        content:
            Full Markdown content to write.
        expected_modified:
            Optional optimistic-concurrency guard. Pass the ``modified`` timestamp
            from a previous read to prevent overwriting concurrent edits.

        Returns
        -------
        dict with the server response (typically: path, modified).
        """
        args: dict = {"operation": "note", "path": path, "content": content}
        if expected_modified is not None:
            args["expectedModified"] = expected_modified
        return self._call_tool("kado-write", args)

    def test_connection(self) -> bool:
        """Verify connectivity by listing the vault root.

        Returns
        -------
        True if the server responds successfully, False otherwise.
        Prints a human-readable status line to stdout.
        """
        try:
            items = self.list_dir("/", depth=1, limit=1)
            print(f"[kado] Connection OK — root contains {len(items)} item(s) (page 1)")
            return True
        except KadoConnectionError as exc:
            print(f"[kado] Connection FAILED — {exc}", file=sys.stderr)
        except KadoAuthError as exc:
            print(f"[kado] Auth FAILED — {exc}", file=sys.stderr)
        except KadoError as exc:
            print(f"[kado] Error — {exc}", file=sys.stderr)
        return False

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _call_read(self, operation: str, path: str) -> dict:
        """Call kado-read and return the parsed result dict."""
        args = {"operation": operation, "path": path}
        return self._call_tool("kado-read", args)

    def _search_all(
        self,
        operation: str,
        *,
        query: str = None,
        path: str = None,
        depth: int = None,
        limit: int = 500,
    ) -> list:
        """Call kado-search, following cursors until all pages are collected."""
        all_items: list = []
        cursor: str = None

        while True:
            args: dict = {"operation": operation, "limit": limit}
            if query is not None:
                args["query"] = query
            if path is not None:
                args["path"] = path
            if depth is not None:
                args["depth"] = depth
            if cursor is not None:
                args["cursor"] = cursor

            result = self._call_tool("kado-search", args)
            page_items = result.get("items", [])
            all_items.extend(page_items)

            next_cursor = result.get("nextCursor") or result.get("cursor")
            if not next_cursor or not page_items:
                break
            cursor = next_cursor

        return all_items

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Send a JSON-RPC 2.0 tools/call request and return the parsed result.

        Raises
        ------
        KadoConnectionError  — server unreachable
        KadoAuthError        — 401/403 HTTP response
        KadoNotFoundError    — 404 HTTP response or tool not-found error
        KadoToolError        — MCP tool returned isError: true
        KadoError            — any other protocol/server error
        """
        self._req_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self._req_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=_DEFAULT_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise KadoAuthError(
                    f"Kado rejected the request (HTTP {exc.code}). "
                    "Check that KADO_TOKEN matches the configured API key."
                ) from exc
            if exc.code == 404:
                raise KadoNotFoundError(
                    f"Kado endpoint not found (HTTP 404). "
                    f"Check that KADO_URL points to the right server and port."
                ) from exc
            raise KadoError(f"HTTP {exc.code} from Kado: {exc.reason}") from exc
        except urllib.error.URLError as exc:
            reason = str(exc.reason)
            if "refused" in reason.lower() or "timed out" in reason.lower():
                raise KadoConnectionError(
                    f"Cannot reach Kado at {self._endpoint}. "
                    f"Is the server running? ({reason})"
                ) from exc
            raise KadoConnectionError(
                f"Network error reaching {self._endpoint}: {reason}"
            ) from exc

        return _parse_rpc_response(raw, tool_name)


# ── Config resolution ──────────────────────────────────────────────────────────

def _resolve_config(base_url: str | None, token: str | None) -> tuple[str, str]:
    """Resolve base_url and token from args → env → .mcp.json fallback."""
    resolved_url = base_url or os.environ.get("KADO_URL")
    resolved_token = token or os.environ.get("KADO_TOKEN")

    if resolved_url and resolved_token:
        return resolved_url, resolved_token

    # Fall back to .mcp.json in the current directory
    mcp_json_path = os.path.join(os.getcwd(), ".mcp.json")
    if os.path.isfile(mcp_json_path):
        try:
            with open(mcp_json_path, encoding="utf-8") as fh:
                mcp_cfg = json.load(fh)
            url, tok = _extract_from_mcp_json(mcp_cfg)
            resolved_url = resolved_url or url
            resolved_token = resolved_token or tok
        except (OSError, json.JSONDecodeError, KeyError):
            pass  # best-effort

    return resolved_url, resolved_token


def _extract_from_mcp_json(cfg: dict) -> tuple[str | None, str | None]:
    """Extract Kado URL and token from a parsed .mcp.json structure.

    Supports three formats:
    1. Claude Code HTTP MCP: {mcpServers: {kado: {url, headers: {Authorization: "Bearer X"}}}}
    2. Claude Code env format: {mcpServers: {kado: {url, env: {KADO_TOKEN: X}}}}
    3. Bare format: {kado: {url, token}}
    """
    servers = cfg.get("mcpServers", {})
    kado_server = servers.get("kado") or servers.get("miyo-kado")
    if kado_server:
        url = kado_server.get("url")

        # Format 1: headers.Authorization: "Bearer <token>"
        headers = kado_server.get("headers", {})
        auth = headers.get("Authorization") or headers.get("authorization")
        if auth and isinstance(auth, str) and auth.startswith("Bearer "):
            return url, auth[len("Bearer "):].strip()

        # Format 2: env.KADO_TOKEN
        env_block = kado_server.get("env", {})
        tok = env_block.get("KADO_TOKEN") or env_block.get("token")
        if tok:
            return url, tok

        # URL found but no token in either location
        return url, None

    # Format 3: bare {kado: {url, token}}
    bare = cfg.get("kado", {})
    return bare.get("url"), bare.get("token")


# ── Response parsing ───────────────────────────────────────────────────────────

def _parse_rpc_response(raw: str, tool_name: str) -> dict:
    """Parse a JSON-RPC 2.0 response and extract the tool result.

    MCP content format::

        result.content[0].text  →  JSON string with actual data

    Raises
    ------
    KadoToolError   — MCP tool returned isError: true
    KadoError       — malformed response or JSON-RPC level error
    """
    try:
        rpc = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KadoError(f"Non-JSON response from Kado: {raw[:200]}") from exc

    # JSON-RPC level error (e.g. method not found, invalid params)
    if "error" in rpc:
        err = rpc["error"]
        raise KadoError(
            f"JSON-RPC error from Kado ({err.get('code')}): {err.get('message')}"
        )

    result = rpc.get("result")
    if result is None:
        raise KadoError(f"Unexpected Kado response (no result field): {raw[:200]}")

    # MCP tool-level error
    if result.get("isError"):
        content = result.get("content", [])
        msg = content[0].get("text", "(no message)") if content else "(no message)"
        if "not found" in msg.lower():
            raise KadoNotFoundError(f"{tool_name}: {msg}")
        raise KadoToolError(f"{tool_name} returned an error: {msg}")

    # Extract text payload
    content = result.get("content", [])
    if not content:
        return {}

    text = content[0].get("text", "")
    if not text:
        return {}

    # Parse JSON payload if the text looks like JSON
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Plain text — return as {content: text}
    return {"content": text}


# ── CLI entry point ────────────────────────────────────────────────────────────

def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Kado MCP client — test connectivity and basic operations."
    )
    parser.add_argument(
        "--test", action="store_true", help="Test connection to Kado (default action)"
    )
    parser.add_argument("--url", default=None, help="Override Kado base URL")
    parser.add_argument("--token", default=None, help="Override Kado bearer token")
    args = parser.parse_args()

    try:
        client = KadoClient(base_url=args.url, token=args.token)
    except KadoError as exc:
        print(f"[kado] Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    ok = client.test_connection()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    _main()
