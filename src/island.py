"""Moves a batch's Dynamic Island while the app is closed. iOS stops an app about 30 seconds after you leave it, so after
that only Apple's push service can reach the Island. The phone gives the desk a token for the batch it is showing, and
when that batch's stage changes, this sends the new state to Apple.

It needs one file: the AuthKey_XXXXXXXXXX.p8 from the Apple Developer site, in the ios folder. Its name carries the key
ID, so nothing else is set up. Without it nothing is sent, and the Island still moves while the app is open.
Check a key with: uv run python src/api.py --check-push
"""

from __future__ import annotations

import json
from pathlib import Path
import threading
import time

import httpx
import jwt

import ops

ROOT = Path(__file__).resolve().parents[1]
TOKENS = ROOT / "records" / "island.json"
DEVICES = ROOT / "records" / "devices.json"
KEYS = ROOT / "ios"
TEAM = "GA5MADTKBJ"
APP = "com.adityapandhari.threadline"
TOPIC = APP + ".push-type.liveactivity"
SERVERS = ("https://api.sandbox.push.apple.com", "https://api.push.apple.com")   # Test builds, then TestFlight.
LINGER = 600            # Seconds a finished batch stays on the Lock Screen.
RESIGN = 2400           # Apple rejects a signature over an hour old, and also one renewed too often.
GONE = ("BadDeviceToken", "Unregistered", "ExpiredToken")


class Island:
    def __init__(self, tokens=TOKENS, keys=KEYS, client=None, devices=DEVICES):
        self.tokens, self.keys, self.client, self.devices = tokens, keys, client, devices
        self.phones = json.loads(devices.read_text()) if devices.exists() else []
        self.lock = threading.Lock()
        self.signature, self.signed_at = None, 0
        self.tracked = json.loads(tokens.read_text()) if tokens.exists() else {}

    def key_file(self) -> Path | None:
        return next(iter(sorted(self.keys.glob("AuthKey_*.p8"))), None)

    def ready(self) -> bool:
        return self.key_file() is not None

    def _save(self) -> None:
        draft = self.tokens.with_suffix(".tmp")
        draft.write_text(json.dumps(self.tracked))
        draft.replace(self.tokens)

    def _bearer(self) -> str:
        if time.time() - self.signed_at > RESIGN:
            path = self.key_file()
            self.signed_at = int(time.time())
            self.signature = jwt.encode({"iss": TEAM, "iat": self.signed_at}, path.read_text(), algorithm="ES256",
                                        headers={"kid": path.stem.removeprefix("AuthKey_")})
        return self.signature

    def _post(self, server, token, aps, topic=TOPIC, push="liveactivity") -> tuple[int, str | None]:
        self.client = self.client or httpx.Client(http2=True, timeout=10)
        reply = self.client.post(f"{server}/3/device/{token}", json={"aps": aps}, headers={
            "authorization": f"bearer {self._bearer()}", "apns-topic": topic, "apns-push-type": push, "apns-priority": "10"})
        return reply.status_code, reply.json().get("reason") if reply.content else None

    def watch(self, token, job_key, state) -> None:
        """A batch has one token at a time. Apple can change it, and the phone then sends the new one."""
        with self.lock:
            self.tracked = {t: entry for t, entry in self.tracked.items() if entry["job"] != job_key}
            self.tracked[token] = {"job": job_key, "state": state}
            self._save()

    def phone(self, token) -> None:
        """A phone that wants alerts. Apple can change the token, so a new one simply joins the list."""
        with self.lock:
            if token not in self.phones:
                self.phones.append(token)
                self.devices.write_text(json.dumps(self.phones))

    def alert(self, text) -> None:
        """A normal phone alert for what the team chat just heard. The first line is the title when there is more than one."""
        if not self.ready():
            return
        lines = [line for line in text.splitlines() if not line.startswith("Approve here")]
        aps = {"alert": {"title": lines[0] if len(lines) > 1 else "Threadline", "body": " ".join(lines[1:]) or lines[0]}, "sound": "default"}
        with self.lock:
            for token in list(self.phones):
                try:
                    status, reason = self._post(SERVERS[0], token, aps, APP, "alert")
                    if reason == "BadDeviceToken":
                        status, reason = self._post(SERVERS[1], token, aps, APP, "alert")
                except httpx.HTTPError as error:
                    print(f"Could not reach Apple to send an alert: {error}", flush=True)
                    return
                if reason in GONE:
                    self.phones.remove(token)
                    self.devices.write_text(json.dumps(self.phones))
                elif status != 200:
                    print(f"Apple refused an alert: {status} {reason}", flush=True)

    def send(self, token, state, over=False) -> str:
        """'sent', 'gone' when the token is finished with, or 'failed' when it is worth trying on the next change."""
        now = int(time.time())
        aps = {"timestamp": now, "event": "end" if over else "update", "content-state": state,
               "alert": {"title": state["status"], "body": state["detail"], **({"sound": "default"} if state["alert"] else {})}}
        if over:
            aps["dismissal-date"] = now + LINGER
        status, reason = None, None
        try:
            for server in SERVERS:
                status, reason = self._post(server, token, aps)
                if status == 200:
                    return "sent"
                if reason != "BadDeviceToken":     # That one can mean the other server, so it gets one more try.
                    break
        except httpx.HTTPError as error:
            print(f"Could not reach Apple to update the Island: {error}", flush=True)
            return "failed"
        if reason in GONE:
            return "gone"
        print(f"Apple refused an Island update: {status} {reason}", flush=True)
        return "failed"

    def sync(self, world) -> None:
        """Sends what has changed. A batch that is back, or gone after a demo reset, ends its Island."""
        if not self.ready():
            return
        with self.lock:
            for token, entry in list(self.tracked.items()):
                job = world.jobs.get(entry["job"])
                state = ops.island(job) if job else entry["state"]
                over = job is None or job["stage"] == "received"
                if state == entry["state"] and not over:
                    continue
                outcome = self.send(token, state, over)
                if outcome == "gone" or (outcome == "sent" and over):
                    del self.tracked[token]
                elif outcome == "sent":
                    entry["state"] = state
                self._save()

    def check(self) -> str:
        """Apple only says a made-up token is bad after it has accepted the signature, so this proves the key without a phone."""
        if not self.ready():
            return f"No AuthKey_*.p8 file in {self.keys}."
        aps = {"timestamp": int(time.time()), "event": "update", "content-state": {}}
        status, reason = self._post(SERVERS[0], "0" * 64, aps)
        return "The key works." if reason == "BadDeviceToken" else f"Apple refused the key: {status} {reason}"
