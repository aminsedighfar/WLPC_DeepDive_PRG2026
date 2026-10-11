"""Expose common Juniper Mist API operations.

This module must use mcp.server.fastmcp because the standalone fastmcp package crashes on import.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

mcp = FastMCP("Juniper Mist")

MIST_BASE_URL = (
    os.getenv("MIST_API_HOST")
    or os.getenv("MIST_BASE_URL")
    or os.getenv("MIST_API_BASE_URL")
    or "https://api.mist.com"
).rstrip("/")
MIST_API_TOKEN = os.getenv("MIST_API_TOKEN", "").strip()
MIST_ORG_ID = os.getenv("MIST_ORG_ID", "").strip()
MIST_SITE_ID = os.getenv("MIST_SITE_ID", "").strip()

ALLOWED_STATS_TYPES = {
    "clients",
    "devices",
    "mxedges",
    "ports",
    "sites",
    "switches",
    "unconnected_clients",
}

HTTP_CLIENT = httpx.Client(
    base_url=MIST_BASE_URL,
    timeout=30.0,
    follow_redirects=False,
    trust_env=False,
)


def _require_token() -> str:
    if not MIST_API_TOKEN:
        raise RuntimeError("MIST_API_TOKEN is not configured")
    return MIST_API_TOKEN


def _require_org_id() -> str:
    if not MIST_ORG_ID:
        raise RuntimeError("MIST_ORG_ID is not configured")
    return MIST_ORG_ID


def _normalize_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        raise ValueError("Mist API path cannot be empty")
    if normalized.startswith(("http://", "https://", "//")):
        raise ValueError("Use a relative Mist API path, not an absolute URL")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if not normalized.startswith("/api/"):
        normalized = f"/api/v1{normalized}"
    return normalized


def _error_detail(response: httpx.Response) -> str:
    try:
        detail = response.json()
    except ValueError:
        detail = response.text
    return str(detail)[:2000]


def _request(
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    body: Any = None,
) -> Any:
    token = _require_token()
    normalized_path = _normalize_path(path)
    request_method = method.upper()
    headers = {
        "Authorization": f"Token {token}",
        "Accept": "application/json, application/vnd.api+json",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"

    try:
        response = HTTP_CLIENT.request(
            request_method,
            normalized_path,
            params=params,
            json=body,
            headers=headers,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(f"Mist API request failed: {exc}") from exc

    if response.is_error:
        raise RuntimeError(
            f"Mist API returned HTTP {response.status_code} for "
            f"{request_method} {normalized_path}: {_error_detail(response)}"
        )

    if response.status_code == 204 or not response.content:
        return {"ok": True, "status_code": response.status_code}

    try:
        return response.json()
    except ValueError:
        return {
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "text": response.text,
        }


def _resolve_site_id(site_id: str | None = None) -> str:
    resolved = (site_id or "").strip() or MIST_SITE_ID
    if resolved:
        return resolved

    org_id = _require_org_id()
    sites = _request(
        "GET",
        f"/orgs/{org_id}/sites",
        params={"limit": 1000, "page": 1},
    )
    if not isinstance(sites, list):
        raise RuntimeError("Mist returned an unexpected response while resolving the site")
    if not sites:
        raise RuntimeError("No sites were found in the configured Mist organization")
    if len(sites) > 1:
        site_names = ", ".join(
            f"{site.get('name', '')} ({site.get('id', '')})" for site in sites
        )
        raise RuntimeError(
            "Multiple sites exist; provide site_id or set MIST_SITE_ID. "
            f"Sites: {site_names}"
        )

    sole_site_id = str(sites[0].get("id", "")).strip()
    if not sole_site_id:
        raise RuntimeError("The sole Mist site did not include an id")
    return sole_site_id


@mcp.tool()
def mist_raw_request(
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"],
    path: str,
    params: dict[str, Any] | None = None,
    body: Any = None,
) -> Any:
    """Send an authenticated request to a relative Juniper Mist API path."""
    return _request(method, path, params=params, body=body)


@mcp.tool()
def mist_get_org() -> Any:
    """Get details for the configured Juniper Mist organization."""
    org_id = _require_org_id()
    return _request("GET", f"/orgs/{org_id}")


@mcp.tool()
def mist_get_site(site_id: str | None = None) -> Any:
    """Get details for a Juniper Mist site by ID or the configured default."""
    resolved_site_id = _resolve_site_id(site_id)
    return _request("GET", f"/sites/{resolved_site_id}")


@mcp.tool()
def mist_list_sites() -> Any:
    """List all sites in the configured Juniper Mist organization."""
    org_id = _require_org_id()
    combined: list[Any] = []
    page = 1

    while True:
        result = _request(
            "GET",
            f"/orgs/{org_id}/sites",
            params={"limit": 1000, "page": page},
        )
        if not isinstance(result, list):
            return result
        combined.extend(result)
        if len(result) < 1000:
            return combined
        page += 1


@mcp.tool()
def mist_list_wlans(site_id: str | None = None) -> Any:
    """List WLANs for a Juniper Mist site by ID or the configured default."""
    resolved_site_id = _resolve_site_id(site_id)
    return _request("GET", f"/sites/{resolved_site_id}/wlans")


@mcp.tool()
def mist_get_site_stats(
    site_id: str | None = None,
    stats_type: str = "devices",
) -> Any:
    """Get a supported statistics collection for a Juniper Mist site."""
    normalized_type = stats_type.strip().lower()
    if (
        normalized_type not in ALLOWED_STATS_TYPES
        or re.fullmatch(r"[a-z_]+", normalized_type) is None
    ):
        allowed = ", ".join(sorted(ALLOWED_STATS_TYPES))
        raise ValueError(
            f"Unsupported stats_type '{stats_type}'; allowed values: {allowed}"
        )
    resolved_site_id = _resolve_site_id(site_id)
    return _request("GET", f"/sites/{resolved_site_id}/stats/{normalized_type}")


@mcp.tool()
def mist_update_wlan(
    site_id: str,
    wlan_id: str,
    update: dict[str, Any],
) -> Any:
    """Update a WLAN at a Juniper Mist site using a partial configuration object."""
    normalized_site_id = site_id.strip()
    if not normalized_site_id:
        raise ValueError("site_id is required")
    normalized_wlan_id = wlan_id.strip()
    if not normalized_wlan_id:
        raise ValueError("wlan_id is required")
    if not update:
        raise ValueError("update must contain at least one WLAN field")
    return _request(
        "PUT",
        f"/sites/{normalized_site_id}/wlans/{normalized_wlan_id}",
        body=update,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
