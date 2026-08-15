# Publishes new-bill events to the pmr.> NATS hub (events.address.md),
# mirroring transit-parser's internal/publish: env-configured JetStream
# stream, one JSON message per event.
import asyncio
import datetime
import json
import logging
import os

base_url = "https://vspmr.org"

nats_url = os.environ.get("NATS_URL", "nats://localhost:4222")
nats_creds = os.environ.get("NATS_INGEST_CREDS", "")
nats_stream = os.environ.get("NATS_STREAM", "VSPMR")
nats_subject_prefix = os.environ.get("NATS_SUBJECT_PREFIX", "pmr.vspmr")
nats_stream_max_age = int(os.environ.get("NATS_STREAM_MAX_AGE", 30 * 24 * 3600))

_SEPARATORS = set(" \t\n\r.*>/")


def sanitize_token(s):
    out = []
    prev_underscore = False
    for ch in s:
        if ch in _SEPARATORS:
            if not prev_underscore:
                out.append("_")
                prev_underscore = True
        else:
            out.append(ch)
            prev_underscore = False
    token = "".join(out).strip("_")
    return token if token else "unknown"


def bill_subject(conv, number, prefix=None):
    if prefix is None:
        prefix = nats_subject_prefix
    return "{0}.bill.new.{1}.{2}".format(prefix, sanitize_token(conv), sanitize_token(number))


def build_event(entry, published_at):
    event = {
        "number": entry["number"],
        "conv": entry["conv"],
        "name": entry["name"],
        "url": base_url + entry["url"],
        "publishedAt": published_at,
    }
    for field in ("author", "committee"):
        if entry.get(field):
            event[field] = entry[field]
    return event


async def _publish(subject, payload):
    import nats
    from nats.js.api import StreamConfig, StorageType

    opts = {"allow_reconnect": False}
    if nats_creds:
        opts["user_credentials"] = nats_creds
    nc = await nats.connect(nats_url, **opts)
    try:
        js = nc.jetstream()
        cfg = StreamConfig(
            name=nats_stream,
            subjects=[nats_subject_prefix + ".>"],
            max_age=nats_stream_max_age,
            storage=StorageType.FILE,
        )
        try:
            await js.add_stream(cfg)
        except Exception:
            await js.update_stream(cfg)
        await js.publish(subject, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    finally:
        await nc.drain()


def publish_new_bill(entry):
    published_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    subject = bill_subject(entry["conv"], entry["number"])
    event = build_event(entry, published_at)
    try:
        asyncio.run(_publish(subject, event))
        logging.info("published " + subject)
    except Exception as e:
        logging.warning("failed to publish %s: %s", subject, e)
