"""Sabi Yummy Rides quote pilot - GitHub Actions runner edition.

Single-shot hybrid driver (MCP lifecycle/perception/taps + adb cursor ops),
merged from the live-validated phase_a/phase_b (2026-11-03, 10c spend).
PRIVACY: never prints addresses, prices, session ids, adb host/code, or keys.
No artifacts. Delivery: HTTPS POST of the screenshot to a private ingest
endpoint only; with no pending job the run exits as a clean no-op.
Always stops the phone. Hard billing cap: PH_MINUTES at session start.
Exit: 0 delivered-or-nothing-pending | 1 guard abort | 2 infra failure.
"""
import asyncio, base64, json, os, re, shutil, subprocess, sys, time
import httpx

PH_API = "https://api.phone-harness.com"
PH_MCP = "https://mcp.phone-harness.com/mcp"

KEY = os.environ.get("PH_API_KEY", "")
PROFILE = os.environ.get("PH_PROFILE_ID", "")
MINUTES = int(os.environ.get("PH_MINUTES", "3"))
API_BASE = os.environ.get("SABI_API_BASE", "").rstrip("/")
RUNNER_TOKEN = os.environ.get("SABI_RUNNER_TOKEN", "")
ADB = os.environ.get("ADB_BIN", "adb")

t0 = time.monotonic()
n = 0

class PilotAbort(Exception):
    pass

def log(step, msg):
    """Redacted log line: steps, counts, booleans, timings only."""
    print(f"[{time.monotonic()-t0:>6.1f}s] {step}: {msg}", flush=True)

def mask(value):
    if value:
        print(f"::add-mask::{value}", flush=True)

def norm(text):
    import unicodedata
    t = unicodedata.normalize("NFD", str(text))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    # punctuation-insensitive: app labels and user text disagree on commas
    t = re.sub(r"[^\w\s]", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()

def content_text(result):
    return " ".join(c.get("text", "") for c in result.get("content", [])
                    if c.get("type") == "text")

class Phone:
    def __init__(self, api_key):
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=30.0)
        self._id = 0
        self.device = ""

    async def _mcp(self, method, params):
        self._id += 1
        r = await self._http.post(PH_MCP, json={
            "jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        r.raise_for_status()
        return r.json()

    async def tool(self, name, args):
        if "device" not in args and name != "phone_list_available_devices":
            args = dict(args, device=self.device)
        res = await self._mcp("tools/call", {"name": name, "arguments": args})
        if res.get("error"):
            raise PilotAbort(f"tool {name} error")
        result = res.get("result", {})
        if result.get("isError"):
            raise PilotAbort(f"tool {name} isError: {content_text(result)[:120]}")
        return result

    async def balance_cents(self):
        r = await self._http.get(f"{PH_API}/me")
        r.raise_for_status()
        return int(r.json()["balance_cents"])

    async def start(self, minutes):
        self._http.timeout = httpx.Timeout(30.0, read=150.0)
        try:
            out = await self.tool("phone_start_device", {
                "platform": "android", "kind": "emulator",
                "device_id": PROFILE, "minutes": minutes})
        finally:
            self._http.timeout = httpx.Timeout(30.0)
        m = re.search(r"as device ([0-9a-f]{8,})", content_text(out))
        if not m:
            raise PilotAbort("start returned no device id")
        self.device = m.group(1)
        mask(self.device)
        return self.device

    async def stop(self):
        await self.tool("phone_stop_device", {"device": self.device})

    async def elements(self):
        out = await self.tool("phone_list_elements_on_screen", {"format": "json"})
        for c in out.get("content", []):
            if c.get("type") == "text":
                try:
                    data = json.loads(c["text"])
                except ValueError:
                    continue
                items = data if isinstance(data, list) else data.get("elements", [])
                for e in items:
                    if "center" not in e and "x" in e:
                        e["center"] = [int(e["x"]), int(e["y"])]
                return items
        return []

    async def tap(self, x, y):
        await self.tool("phone_click_on_screen_at_coordinates", {"x": x, "y": y})

    async def screenshot(self):
        out = await self.tool("phone_take_screenshot",
                              {"device": self.device, "max_size": 1024})
        for c in out.get("content", []):
            if c.get("type") == "image" and c.get("data"):
                return base64.b64decode(c["data"])
        raise PilotAbort("no screenshot content")

    async def adb_link(self):
        r = await self._http.get(f"{PH_API}/sessions")
        r.raise_for_status()
        data = r.json()
        sessions = data if isinstance(data, list) else data.get("sessions", [])
        sess = next((s for s in sessions
                     if self.device in (str(s.get("id", "")), str(s.get("sid", "")),
                                        str(s.get("device_id", "")))), None)
        adbinfo = (sess or {}).get("adb") or {}
        if not (adbinfo.get("host") and adbinfo.get("code")):
            r = await self._http.post(f"{PH_API}/sessions/{self.device}/adb")
            if r.status_code != 200:
                raise PilotAbort("adb link refused")
            adbinfo = r.json()
        return adbinfo["host"], adbinfo["port"], adbinfo["code"]

def adb(serial, *args, timeout=90):
    r = subprocess.run([ADB, "-s", serial, *args],
                       capture_output=True, text=True, timeout=timeout)
    return (r.stdout + r.stderr).strip()

def row_near(els, y_hint, needles, band=200):
    best = None
    for e in els:
        t = str(e.get("text", ""))
        if not t.strip() or "center" not in e:
            continue
        y = int(e["center"][1])
        if abs(y - y_hint) > band:
            continue
        if any(nd.lower() in t.lower() for nd in needles) and (
                best is None or abs(y - y_hint) < abs(int(best["center"][1]) - y_hint)):
            best = e
    return best

PLACEHOLDERS = {"type pick up location", "where are we going"}
PLACEHOLDER_TOKENS = set(" ".join(sorted(PLACEHOLDERS)).split())
SHEET_EXCLUDE = {"choose address on the map", "get fare quote", "your ride",
                 "flights new", "marketplace", "groceries", "gifts", "new"}

def sheet_fields(els):
    """Generic route-field locator, no address-specific strings or fixed
    coordinates: the edit sheet's two address rows are the long text
    elements (or known placeholders) between the 'Your ride' title and the
    GET FARE QUOTE button. Short home-screen labels are excluded; resource
    ids (rides_*) are excluded. Fail-closed: anything but exactly 2 aborts."""
    gq = [e for e in els if str(e.get("text", "")) == "GET FARE QUOTE"]
    if len(gq) != 1:
        raise PilotAbort(f"edit sheet not open (GQ={len(gq)})")
    gq_y = int(gq[0]["center"][1])
    title = [e for e in els if str(e.get("text", "")) == "Your ride"]
    top_y = int(title[0]["center"][1]) if title else 0
    # The sheet overlays the home grid; the accessibility tree includes both,
    # so the plain title..GQ band can catch home promos. When the address
    # edit-list container is exposed, only its own band holds the real rows.
    edit = next((e for e in els
                 if str(e.get("text", "")) == "rides_map_bs_address_edit_list"
                 and "center" in e and e.get("h")), None)
    # The home grid behind the sheet also exposes texts (e.g. its own
    # "Where are we going?" button) inside any y band. Those nodes mirror a
    # rides_* resource-id node at the same center; the sheet's real rows do
    # not. Exclude candidates collocated with a rides_* node.
    rides_centers = [(int(e["center"][0]), int(e["center"][1])) for e in els
                     if str(e.get("text", "")).startswith("rides_")
                     and "center" in e]

    def near_rides(x, y):
        return any(abs(x - rx) <= 15 and abs(y - ry) <= 15
                   for rx, ry in rides_centers)

    rows = []
    for e in els:
        t = str(e.get("text", "")).strip()
        if not t or "center" not in e or t.startswith("rides_"):
            continue
        x, y = int(e["center"][0]), int(e["center"][1])
        if edit is not None:
            ey, eh = int(edit["center"][1]), int(edit["h"])
            if not (ey - eh // 2 - 20 <= y <= ey + eh // 2 + 20):
                continue
        elif not (top_y < y < gq_y):
            continue
        if near_rides(x, y):
            continue
        n = norm(t)
        if n in SHEET_EXCLUDE:
            continue
        if n in PLACEHOLDERS or len(t) >= 15:
            rows.append(e)
    rows.sort(key=lambda e: int(e["center"][1]))
    if len(rows) != 2:
        raise PilotAbort(f"sheet fields != 2 ({len(rows)})")
    return rows[0], rows[1], gq[0]

async def clear_and_fill(ph, serial, row, value, tag):
    cx, cy = int(row["center"][0]), int(row["center"][1])
    old_tokens = set(norm(str(row.get("text", ""))).split()) - PLACEHOLDER_TOKENS
    log(tag, f"row found, {len(str(row.get('text','')))} chars")
    await ph.tap(cx, cy)
    await asyncio.sleep(1)
    if old_tokens:  # pre-filled saved profile: clear; placeholder means already empty
        adb(serial, "shell", "input", "keyevent", "KEYCODE_MOVE_END")
        adb(serial, "shell", "input", "keyevent", *(["KEYCODE_DEL"] * 220))
        await asyncio.sleep(1)
        els = await ph.elements()
        for e in els:
            if "center" not in e or abs(int(e["center"][1]) - cy) > 35:
                continue
            if old_tokens & set(norm(str(e.get("text", ""))).split()):
                raise PilotAbort(f"{tag}: field NOT empty after clear")
        log(tag, "EMPTY VERIFIED")
    await ph.tool("phone_type_keys", {"text": value})
    tokens = set(norm(value).split())
    cand = {}
    for _ in range(4):  # geocoder latency varies; poll ~8s then fail closed
        await asyncio.sleep(2)
        els = await ph.elements()
        cand = {}
        for e in els:
            t = str(e.get("text", ""))
            if "center" not in e or abs(int(e["center"][1]) - cy) < 28:
                continue
            if tokens and tokens <= set(norm(t).split()):
                cand.setdefault(norm(t), []).append(e)
        if cand:
            break
    if len(cand) != 1:
        raise PilotAbort(f"{tag}: suggestions not unique ({len(cand)})")
    nodes = next(iter(cand.values()))
    top = min(nodes, key=lambda e: int(e["center"][1]))
    await ph.tap(int(top["center"][0]), int(top["center"][1]))
    await asyncio.sleep(1.5)
    els = await ph.elements()
    row3 = row_near(els, cy, list(tokens), band=60)
    if not (row3 and tokens <= set(norm(str(row3.get("text", ""))).split())):
        raise PilotAbort(f"{tag}: readback failed")
    log(tag, "readback OK")

async def claim_job():
    """Pull the next pending pilot job from sabi-api (private channel:
    the route never touches GitHub's public run page). 204 = nothing to do."""
    async with httpx.AsyncClient(timeout=20.0) as h:
        r = await h.post(f"{API_BASE}/pilot/yummy/jobs/claim",
                         headers={"Authorization": f"Bearer {RUNNER_TOKEN}"})
    if r.status_code == 204:
        return None
    if r.status_code != 200:
        raise PilotAbort(f"job claim refused ({r.status_code})")
    job = r.json()
    if not (job.get("job_id") and job.get("origin") and job.get("dest")):
        raise PilotAbort("job payload incomplete")
    return job


async def ensure_sheet(ph):
    """The app does not open into the route edit sheet: with a saved route it
    opens on the map (address card up top), on a fresh state on the home grid
    ('Where are we going?'). Navigate to the sheet from either entry; retry
    briefly for slow loads; fail closed if the sheet never appears."""
    els = await ph.elements()
    for attempt in range(3):
        if any(str(e.get("text", "")) == "GET FARE QUOTE" for e in els):
            if attempt:
                log("sheet", f"open after nav step {attempt}")
            return els
        card = next((e for e in els
                     if str(e.get("text", "")) == "rides_map_address_card_btn"
                     and "center" in e), None)
        wtg = next((e for e in els
                    if norm(str(e.get("text", ""))) == "where are we going"
                    and "center" in e), None)
        target = card or wtg
        if not target:
            await asyncio.sleep(3)
            els = await ph.elements()
            continue
        log("sheet", "nav via " + ("address card" if card else "where-to-go"))
        await ph.tap(int(target["center"][0]), int(target["center"][1]))
        await asyncio.sleep(2.5)
        els = await ph.elements()
    raise PilotAbort("edit sheet not reachable (GQ=0)")

async def main():
    if not (KEY and PROFILE and API_BASE and RUNNER_TOKEN):
        log("config", "missing PH_API_KEY / PH_PROFILE_ID / SABI_API_BASE / SABI_RUNNER_TOKEN")
        sys.exit(2)
    adb_path = shutil.which(ADB) or (ADB if os.path.isfile(ADB) and os.access(ADB, os.X_OK) else None)
    if not adb_path:
        log("config", "adb unavailable on this runner; aborting before claim (free)")
        sys.exit(2)
    job = await claim_job()
    if not job:
        log("job", "no pending pilot job; clean no-op")
        sys.exit(0)
    JOB_ID = job["job_id"]
    mask(JOB_ID)
    ORIGIN, DEST = job["origin"], job["dest"]
    log("job", "claimed (route redacted)")
    ph = Phone(KEY)
    bal0 = None
    try:
        bal0 = await ph.balance_cents()
        if bal0 < MINUTES * 5:
            log("balance", "insufficient for capped run; aborting before boot")
            sys.exit(2)
        await ph.start(MINUTES)
        log("start", f"session ready (hard cap {MINUTES}min)")
        host, port, code = await ph.adb_link()
        serial = f"{host}:{port}"
        mask(serial); mask(code)
        subprocess.run([ADB, "connect", serial], capture_output=True,
                       text=True, timeout=30)
        probe = adb(serial, "shell", "echo", "ph-ok", timeout=20)
        if "ph-ok" not in probe:
            adb(serial, "shell", "unlock", code, timeout=20)
            probe = adb(serial, "shell", "echo", "ph-ok", timeout=20)
        if "ph-ok" not in probe:
            raise PilotAbort("adb link failed")
        log("adb", "connected")
        adb(serial, "shell", "monkey", "-p", "com.yummyrides",
            "-c", "android.intent.category.LAUNCHER", "1", timeout=20)
        await asyncio.sleep(6)
        els = await ensure_sheet(ph)
        row_o, row_d, gq_btn = sheet_fields(els)
        o_tok = set(norm(ORIGIN).split())
        d_tok = set(norm(DEST).split())
        o_dist, d_dist = o_tok - d_tok, d_tok - o_tok
        if not o_dist or not d_dist:
            raise PilotAbort("origin/dest not distinguishable; NOT quoting")
        await clear_and_fill(ph, serial, row_o, ORIGIN, "origin")
        await clear_and_fill(ph, serial, row_d, DEST, "dest")
        els = await ph.elements()
        ok_o = any(o_tok <= set(norm(str(e.get("text", ""))).split()) for e in els)
        ok_d = any(d_tok <= set(norm(str(e.get("text", ""))).split()) for e in els)
        # composite = one field holding distinctive tokens of BOTH ends
        # (distinctive = tokens unique to each side, so shared city/region
        # words never false-positive)
        composite = any(
            (o_dist & set(norm(str(e.get("text", ""))).split()))
            and (d_dist & set(norm(str(e.get("text", ""))).split())) for e in els)
        log("verify", f"origin={ok_o} dest={ok_d} composite={composite}")
        if not (ok_o and ok_d) or composite:
            raise PilotAbort("route verification failed; NOT quoting")
        UI_STRINGS = ("GET FARE QUOTE", "Your ride", "CONTINUE",
                      "Choose address on the map",
                      "rides_map_bs_vehicle_type_list", "rides_map_address_card_btn",
                      "rides_map_bs_vehicle_back_btn")
        def ui_flags(els):
            return " ".join(
                f"{tag}={any(str(e.get('text', '')) == s for e in els)}"
                for tag, s in zip(("gq", "title", "cont", "maplink", "vlist",
                                   "acard", "back"), UI_STRINGS))
        def find_prices(els):
            return [e for e in els
                    if str(e.get("text", "")).strip().startswith("$")
                    and str(e.get("text", "")).strip() != "$0.00"]
        prices = []
        for attempt in range(2):  # the tap can miss if the sheet shifts
            await ph.tap(int(gq_btn["center"][0]), int(gq_btn["center"][1]))
            for _ in range(6):  # quote latency varies by route; poll ~12s
                await asyncio.sleep(2)
                els = await ph.elements()
                prices = find_prices(els)
                if prices:
                    break
                if not any(str(e.get("text", "")) == "GET FARE QUOTE" for e in els):
                    break  # left the sheet: re-tapping makes no sense
            if prices:
                break
            gq_now = next((e for e in els
                           if str(e.get("text", "")) == "GET FARE QUOTE"
                           and "center" in e), None)
            if not gq_now:
                break
            gq_btn = gq_now  # button may have moved; re-tap fresh coords
            log("quote", "GQ still present after tap; re-tapping")
        if not prices:
            raise PilotAbort(
                f"no prices on quote screen (els={len(els)} {ui_flags(els)})")
        log("quote", f"prices found: {len(prices)} (values redacted)")
        jpeg = await ph.screenshot()
        log("screenshot", f"{len(jpeg)} bytes")
        dbg = os.environ.get("PILOT_DEBUG_CAPTURE_PATH")
        if dbg:
            with open(dbg, "wb") as f:
                f.write(jpeg)
            log("screenshot", "local debug copy saved")
        # Deliver ONLY the image + job id. The endpoint owns recipient,
        # route and send authority; the runner supplies none of them.
        r = await ph._http.post(
            f"{API_BASE}/pilot/yummy/jobs/{JOB_ID}/capture",
            headers={"Authorization": f"Bearer {RUNNER_TOKEN}",
                     "Idempotency-Key": JOB_ID,
                     "Content-Type": "image/jpeg"},
            content=jpeg,
            timeout=30.0)
        if r.status_code not in (200, 201, 202):
            raise PilotAbort(f"delivery refused ({r.status_code})")
        log("delivery", "accepted by ingest endpoint")
        rc = 0
    except PilotAbort as e:
        log("ABORT", str(e))
        rc = 1
    except FileNotFoundError as e:
        log("FAIL", f"missing executable: {e.filename}")
        rc = 2
    except Exception as e:
        log("FAIL", type(e).__name__)
        rc = 2
    finally:
        if ph.device:
            try:
                await ph.stop()
                log("stop", "session stopped")
            except Exception:
                log("stop", "stop failed; provider cap applies")
        if bal0 is not None:
            try:
                bal1 = await ph.balance_cents()
                log("balance", f"spent={bal0 - bal1}c")
            except Exception:
                pass
    sys.exit(rc)

asyncio.run(main())
