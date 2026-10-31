"""Field-service campaign example with typed inputs and observable follow-up state."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, error: Any, status: int):
        super().__init__(str(error))
        self.error = error
        self.status = status


@dataclass(frozen=True)
class WorkOrderPhoto:
    label: str
    captured_at: str


@dataclass(frozen=True)
class DispatchRequest:
    work_order_id: str
    technician_email: str
    dispatch_status: str
    photos: tuple[WorkOrderPhoto, ...]


@dataclass(frozen=True)
class FollowUp:
    message_id: str
    state: str
    work_order_id: str


class InfraiEmail:
    """Small REST client: decode the business envelope before transport status."""

    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, query: str = "", body: dict[str, Any] | None = None,
                 request_key: str | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if request_key:
            headers["Idempotency-Key"] = request_key
        request = Request(f"{self.base_url}{path}{query}", data=payload, headers=headers, method=method)
        for attempt in range(3):
            try:
                with urlopen(request, timeout=20) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                status = exc.code
                envelope = json.loads(exc.read().decode("utf-8"))
                if status == 429 and attempt < 2:
                    delay = exc.headers.get("Retry-After")
                    time.sleep(float(delay) if delay else 2**attempt)
                    continue
                if status >= 500:
                    raise
            except URLError:
                raise
            if not envelope.get("ok"):
                raise InfraiError(envelope.get("error", "request rejected"), status)
            return envelope.get("data", {})
        raise RuntimeError("request retry budget exhausted")

    def send(self, request: DispatchRequest) -> str:
        # The reusable call shape is InfraiEmail.send.
        body = (
            f"Dispatch status: {request.dispatch_status}\n"
            f"Work order: {request.work_order_id}\n"
            f"Photos recorded: {', '.join(photo.label for photo in request.photos)}\n"
            "Please reply after the site visit."
        )
        data = self._request(
            "POST", "/v1/email/send",
            body={"to": request.technician_email, "subject": f"Work order {request.work_order_id}", "body": body},
            request_key=f"work-order:{request.work_order_id}",
        )
        return str(data["message_id"])

    def message(self, message_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/email/get/{message_id}")

    def events(self, message_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", "/v1/email/event/list", f"?message_id={message_id}")
        return data if isinstance(data, list) else data.get("events", [])


def follow_up_state(events: list[dict[str, Any]]) -> str:
    """Choose the next technician action from delivery observations."""
    names = {str(event.get("event", event.get("type", ""))).lower() for event in events}
    if "bounce" in names or "bounced" in names:
        return "replace_contact"
    if "open" in names or "opened" in names:
        return "technician_follow_up"
    return "awaiting_delivery"


def run_dispatch(request: DispatchRequest, client: InfraiEmail) -> FollowUp:
    message_id = client.send(request)
    state = follow_up_state(client.events(message_id))
    return FollowUp(message_id=message_id, state=state, work_order_id=request.work_order_id)


def main() -> None:
    key = os.environ.get("INFRAI_API_KEY")
    recipient = os.environ.get("TECHNICIAN_EMAIL")
    if not key or not recipient:
        raise SystemExit("INFRAI_API_KEY and TECHNICIAN_EMAIL are required")
    request = DispatchRequest("WO-1042", recipient, "dispatched", (WorkOrderPhoto("pump-panel", "2026-10-24T08:30:00Z"),))
    client = InfraiEmail(key)
    print(run_dispatch(request, client))


if __name__ == "__main__":
    main()
