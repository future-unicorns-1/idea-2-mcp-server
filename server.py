"""
MCP Server for AI Outbound Operator.

Built with mcp-use framework. Exposes all outbound sales tools via MCP.
Talks to the Flask API running on localhost.

Run:
    python -m mcp_tools.server
    # => http://localhost:8000/mcp
"""

import json
import os

import requests
from mcp_use.server import MCPServer

API_BASE = os.getenv("API_BASE_URL", "http://localhost:5000")
INTERNAL_KEY = os.getenv("INTERNAL_SERVICE_KEY", "dev-internal-key-change-in-prod")

server = MCPServer(
    name="AI Outbound Operator",
    version="1.0.0",
    instructions=(
        "AI-powered outbound sales operator. "
        "Find leads, send outreach, analyze replies, get notified on hot leads."
    ),
)

# Session-level user ID — set by any tool that receives a user_id,
# reused by tools that only have a lead_id.
_session_user_id: str | None = None


def _api(method: str, path: str, user_id: str | None = None, **kwargs) -> dict:
    """Make a request to the Flask API with internal auth."""
    global _session_user_id
    if user_id:
        _session_user_id = user_id

    url = f"{API_BASE}{path}"
    headers = kwargs.pop("headers", {})
    headers["X-Internal-Key"] = INTERNAL_KEY
    if _session_user_id:
        headers["X-User-Id"] = _session_user_id

    resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


# ==========================================
# LEAD TOOLS
# ==========================================

@server.tool()
def search_leads(
    user_id: str,
    person_titles: list[str] | None = None,
    person_locations: list[str] | None = None,
    q_keywords: str | None = None,
    organization_num_employees_ranges: list[str] | None = None,
) -> str:
    """Search for leads matching criteria. Queries Apollo for people by title, location, keywords, and company size. Stores results in the pipeline.

    Args:
        user_id: The user's UUID
        person_titles: Job titles to search (e.g. ["CEO", "CTO", "Founder"])
        person_locations: Locations (e.g. ["San Francisco", "New York"])
        q_keywords: Keyword search (e.g. "SaaS hiring SDR")
        organization_num_employees_ranges: Company size ranges (e.g. ["1,10", "11,50"])
    """
    filters = {}
    if person_titles:
        filters["person_titles"] = person_titles
    if person_locations:
        filters["person_locations"] = person_locations
    if q_keywords:
        filters["q_keywords"] = q_keywords
    if organization_num_employees_ranges:
        filters["organization_num_employees_ranges"] = organization_num_employees_ranges

    result = _api("POST", "/leads/search", user_id=user_id, json={"filters": filters})
    return json.dumps(result, indent=2)


@server.tool()
def enrich_lead(lead_id: str) -> str:
    """Enrich a lead with scoring data. Computes lead_score (0-100) and temperature (cold/warm/hot).

    Args:
        lead_id: The lead's UUID
    """
    result = _api("POST", f"/leads/enrich/{lead_id}")
    return json.dumps(result, indent=2)


@server.tool()
def list_leads(user_id: str, temperature: str | None = None) -> str:
    """List all leads for a user, sorted by score. Optionally filter by temperature.

    Args:
        user_id: The user's UUID
        temperature: Filter by "cold", "warm", or "hot"
    """
    params = {}
    if temperature:
        params["temperature"] = temperature
    result = _api("GET", "/leads/list", user_id=user_id, params=params)
    return json.dumps(result, indent=2)


@server.tool()
def get_lead(lead_id: str) -> str:
    """Get full details for a single lead.

    Args:
        lead_id: The lead's UUID
    """
    result = _api("GET", f"/leads/{lead_id}")
    return json.dumps(result, indent=2)


@server.tool()
def mark_do_not_contact(lead_id: str, reason: str = "manual") -> str:
    """Mark a lead as do-not-contact. Cancels all pending sequences.

    Args:
        lead_id: The lead's UUID
        reason: Reason for marking DNC
    """
    result = _api("POST", f"/leads/{lead_id}/dnc", json={"reason": reason})
    return json.dumps(result, indent=2)


# ==========================================
# OUTREACH TOOLS
# ==========================================

@server.tool()
def draft_message(lead_id: str, channel: str, context: str = "") -> str:
    """Generate a personalized outreach message for a lead using AI.

    Args:
        lead_id: The lead's UUID
        channel: "email", "sms", or "call"
        context: Context about your product/offering for personalization
    """
    result = _api("POST", "/outreach/draft", json={
        "lead_id": lead_id,
        "channel": channel,
        "context": context,
    })
    return json.dumps(result, indent=2)


@server.tool()
def send_email(lead_id: str, subject: str, content: str) -> str:
    """Send an email to a lead via AgentMail.

    Args:
        lead_id: The lead's UUID
        subject: Email subject line
        content: Email body (HTML supported)
    """
    result = _api("POST", "/outreach/send/email", json={
        "lead_id": lead_id,
        "subject": subject,
        "content": content,
    })
    return json.dumps(result, indent=2)


@server.tool()
def send_sms(lead_id: str, content: str) -> str:
    """Send an SMS to a lead via Twilio.

    Args:
        lead_id: The lead's UUID
        content: SMS message (max 160 chars recommended)
    """
    result = _api("POST", "/outreach/send/sms", json={
        "lead_id": lead_id,
        "content": content,
    })
    return json.dumps(result, indent=2)


@server.tool()
def place_call(lead_id: str, script: str, callback_url: str) -> str:
    """Place an AI-scripted phone call to a lead via Twilio.

    Args:
        lead_id: The lead's UUID
        script: The call script to deliver
        callback_url: URL to receive call results
    """
    result = _api("POST", "/outreach/send/call", json={
        "lead_id": lead_id,
        "script": script,
        "callback_url": callback_url,
    })
    return json.dumps(result, indent=2)


@server.tool()
def create_sequence(
    lead_id: str,
    user_id: str,
    channel: str = "email",
    num_steps: int = 3,
    context: str = "",
    auto_send: bool = False,
) -> str:
    """Generate and schedule a multi-step follow-up sequence for a lead.

    Args:
        lead_id: The lead's UUID
        user_id: The user's UUID
        channel: "email" or "sms"
        num_steps: Number of follow-up steps (default 3)
        context: Context about your offering
        auto_send: True to auto-send, False for approval mode
    """
    result = _api("POST", "/outreach/sequence", user_id=user_id, json={
        "lead_id": lead_id,
        "channel": channel,
        "num_steps": num_steps,
        "context": context,
        "auto_send": auto_send,
    })
    return json.dumps(result, indent=2)


@server.tool()
def outreach_history(lead_id: str) -> str:
    """Get all outreach messages sent to a lead.

    Args:
        lead_id: The lead's UUID
    """
    result = _api("GET", f"/outreach/history/{lead_id}")
    return json.dumps(result, indent=2)


# ==========================================
# INTELLIGENCE TOOLS
# ==========================================

@server.tool()
def classify_reply(reply_text: str) -> str:
    """Classify a reply to determine sentiment, intent signals, and hot/warm/cold status.

    Args:
        reply_text: The reply text to analyze
    """
    result = _api("POST", "/scoring/classify", json={"reply_text": reply_text})
    return json.dumps(result, indent=2)


@server.tool()
def process_reply(lead_id: str, reply_text: str, channel: str = "email") -> str:
    """Process and store an incoming reply. Classifies it, updates lead score, and triggers hot lead notifications.

    Args:
        lead_id: The lead's UUID
        reply_text: The reply content
        channel: "email", "sms", or "call"
    """
    result = _api("POST", "/scoring/process-reply", json={
        "lead_id": lead_id,
        "reply_text": reply_text,
        "channel": channel,
    })
    return json.dumps(result, indent=2)


@server.tool()
def score_lead(lead_id: str) -> str:
    """Re-score a lead based on all interactions and engagement signals.

    Args:
        lead_id: The lead's UUID
    """
    result = _api("POST", f"/scoring/score/{lead_id}")
    return json.dumps(result, indent=2)


# ==========================================
# NOTIFICATION TOOLS
# ==========================================

@server.tool()
def get_hot_lead_notifications(user_id: str) -> str:
    """Get pending hot lead notifications. Returns leads that recently became hot.

    Args:
        user_id: The user's UUID
    """
    result = _api("GET", "/notifications/hot-leads", user_id=user_id)
    return json.dumps(result, indent=2)


@server.tool()
def summarize_pipeline(user_id: str) -> str:
    """Get a summary of the user's pipeline: total leads, temperature breakdown, outreach stats.

    Args:
        user_id: The user's UUID
    """
    result = _api("GET", "/notifications/pipeline-summary", user_id=user_id)
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    server.run(transport="streamable-http", host="0.0.0.0", port=8000, debug=True)
