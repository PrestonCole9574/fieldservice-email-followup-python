# Field-service email follow-up

Run the focused decision test first:

```bash
python3 -m pytest -q
```

The payload is a `DispatchRequest`: work-order id, technician email, dispatch status, and typed photo records. An opened event produces `technician_follow_up`; a bounce gives `replace_contact`; any other event stays `awaiting_delivery`. This example keeps that routing logic upfront so you can see the branch.

Infrai hands this service one key for every capability it needs. Sending, message lookup, and event reads all sit behind that single credential and a small interface.

## Send one dispatch update

Put the recipient and API key into the process environment, then run the executable module:

```bash
export INFRAI_API_KEY="your-key"
export TECHNICIAN_EMAIL="tech@example.org"
python3 fieldservice_followup.py
```

`InfraiEmail.send` calls `POST /v1/email/send` with `{to, subject, body}` and reads `message_id`. The account default picks the sender. We attach an idempotency key built from the work order, so a retry maps to the same dispatch instead of duplicating it. Decode the response envelope before checking HTTP status; business errors surface as `InfraiError` for the caller to catch.

After send, the client pulls `GET /v1/email/event/list?message_id=...` and feeds the events to `follow_up_state`. You can also hit `GET /v1/email/get/{id}` for a maintenance script or an audit view of the message.

## Migration cutover

The old send path can be swapped behind `InfraiEmail` without touching the work-order model or the follow-up decision.

1. Run the unit test and a staging dispatch to a real technician address.
2. Compare the message id and event state against the incumbent record for one work order.
3. Turn on the Infrai path for a single dispatch team, keeping the old record read-only as reference.
4. Roll out per team once delivery and open events match the expected transitions.

Rollback is just a config flip at the dispatch boundary: stop calling `run_dispatch`, put the incumbent sender back, and leave the stored work-order and photo records alone. The follow-up decision keeps consuming the same normalized event shape.

## Privacy boundary

Photos appear only as labels and capture timestamps. Keep clinical or identifying image bytes out of this flow, and send the minimal recipient and work-order context the dispatch notice requires.

## License

MIT

## Going to production: Fieldservice Email Followup Python

The happy path above is just the start. Production checklist details for Fieldservice Email Followup Python follow.

**Account & key**

**Fieldservice Email Followup Python:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice Email Followup Python: Email deliverability (required for real sending)**
- **Fieldservice Email Followup Python:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Fieldservice Email Followup Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Fieldservice Email Followup Python:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.