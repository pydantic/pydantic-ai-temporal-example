import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qs

from fastapi import HTTPException
from starlette.requests import Request

from pydantic_temporal_example.models import (
    SlackEventsAPIBody,
    SlackEventsAPIBodyAdapter,
    URLVerificationEvent,
)
from pydantic_temporal_example.settings import get_settings


async def get_verified_slack_events_body(
    request: Request,
) -> SlackEventsAPIBody | URLVerificationEvent | dict[str, Any]:
    signing_secret = get_settings().slack_signing_secret
    # Get timestamp header
    timestamp_header = request.headers.get("x-slack-request-timestamp")
    if not timestamp_header:
        raise HTTPException(status_code=401, detail="Missing x-slack-request-timestamp header")

    # Check if timestamp is not older than 5 minutes
    five_minutes_ago = int(time.time()) - (60 * 5)
    if int(timestamp_header) < five_minutes_ago:
        raise HTTPException(status_code=401, detail="Request timestamp too old")

    # Get signature header
    signature_header = request.headers.get("x-slack-signature")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing x-slack-signature header")

    # Get request body
    request_body = await request.body()
    request_body_str = request_body.decode("utf-8")

    # Create the base string for the signature
    base_string = f"v0:{timestamp_header}:{request_body_str}"

    # Calculate expected signature
    expected_signature = (
        "v0=" + hmac.new(signing_secret.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha256).hexdigest()
    )

    # Compare signatures
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    return SlackEventsAPIBodyAdapter.validate_json(request_body_str)


async def get_verified_slack_interaction_body(
    request: Request,
) -> dict[str, Any]:
    signing_secret = get_settings().slack_signing_secret
    # Get timestamp header
    timestamp_header = request.headers.get("x-slack-request-timestamp")
    if not timestamp_header:
        raise HTTPException(status_code=401, detail="Missing x-slack-request-timestamp header")

    # Check if timestamp is not older than 5 minutes
    five_minutes_ago = int(time.time()) - (60 * 5)
    if int(timestamp_header) < five_minutes_ago:
        raise HTTPException(status_code=401, detail="Request timestamp too old")

    # Get signature header
    signature_header = request.headers.get("x-slack-signature")
    if not signature_header:
        raise HTTPException(status_code=401, detail="Missing x-slack-signature header")

    # Get request body
    request_body = await request.body()
    request_body_str = request_body.decode("utf-8")

    # Create the base string for the signature
    base_string = f"v0:{timestamp_header}:{request_body_str}"

    # Calculate expected signature
    expected_signature = (
        "v0=" + hmac.new(signing_secret.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha256).hexdigest()
    )

    # Compare signatures
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=401, detail="Invalid request signature")

    data = parse_qs(request_body_str)
    return json.loads(data["payload"][0])
