#!/usr/bin/env -S uv run
# /// script
# dependencies = ["arrow"]
# ///
"""List the most recent backup snapshot for each group in a PBS datastore."""

import arrow
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_PATH = "pbs.token"


def eprint(*args):
    print(*args, file=sys.stderr)


def load_cfg(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"Missing token file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Token file must be JSON: {path}") from exc

    if not isinstance(data, dict):
        raise SystemExit("Token file JSON must be an object.")

    if not data.get("token_id") or not data.get("token_secret"):
        raise SystemExit("Token file JSON must include token_id and token_secret.")

    return data


def api_get(host, port, path, params, headers, insecure=False):
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"https://{host}:{port}/api2/json{path}"
    if qs:
        url += "?" + qs

    req = urllib.request.Request(url, headers=headers)
    ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_time(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            return int(s)
        try:
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return int(arrow.get(s).timestamp())
        except Exception:
            return None
    return None


def snapshot_to_group(item):
    bt = item.get("backup-type") or item.get("backup_type") or item.get("type")
    bid = item.get("backup-id") or item.get("backup_id") or item.get("id")

    snapshot = item.get("backup-dir") or item.get("snapshot") or item.get("backup")
    if snapshot and (not bt or not bid):
        m = re.match(r"^([^/]+)/([^/]+)/(.+)$", str(snapshot))
        if m:
            bt = bt or m.group(1)
            bid = bid or m.group(2)

    if bt and bid:
        return bt, bid, snapshot
    return None, None, snapshot


def build_snapshot_string(bt, bid, ts):
    if ts is None:
        return f"{bt}/{bid}"
    return f"{bt}/{bid}/{arrow.get(ts).to('utc').format('YYYY-MM-DDTHH:mm:ss')}Z"


def get_groups(host, port, datastore, namespace, headers, insecure=False):
    resp = api_get(
        host,
        port,
        f"/admin/datastore/{datastore}/groups",
        {"ns": namespace},
        headers,
        insecure,
    )
    data = resp.get("data") if isinstance(resp, dict) else resp
    if not isinstance(data, list):
        return {}
    out = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        bt = item.get("backup-type")
        bid = item.get("backup-id")
        if bt and bid:
            out[f"{bt}/{bid}"] = item.get("comment") or ""
    return out


def main():
    cfg = load_cfg(TOKEN_PATH)

    host = cfg.get("host", "pbs.mclean.harvard.edu")
    port = int(cfg.get("port", 8007))
    datastore = cfg.get("datastore", "backups")
    namespace = cfg.get("namespace")

    token_id = cfg["token_id"]
    token_secret = cfg["token_secret"]

    headers = {"Authorization": f"PBSAPIToken={token_id}:{token_secret}"}

    try:
        resp = api_get(
            host,
            port,
            f"/admin/datastore/{datastore}/snapshots",
            {"ns": namespace},
            headers,
            False,
        )
    except urllib.error.HTTPError as exc:
        eprint(f"HTTP {exc.code} {exc.reason}")
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            eprint("Response body (truncated):")
            eprint(body[:2000])
        return 2
    except urllib.error.URLError as exc:
        eprint(f"Request failed: {getattr(exc, 'reason', exc)}")
        return 2

    try:
        group_comments = get_groups(host, port, datastore, namespace, headers, False)
    except urllib.error.HTTPError as exc:
        eprint(f"HTTP {exc.code} {exc.reason} (groups)")
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            eprint("Response body (truncated):")
            eprint(body[:2000])
        group_comments = {}
    except urllib.error.URLError as exc:
        eprint(f"Request failed (groups): {getattr(exc, 'reason', exc)}")
        group_comments = {}

    data = resp.get("data") if isinstance(resp, dict) else resp
    if not isinstance(data, list):
        eprint("Unexpected response shape; expected a list under 'data'.")
        return 2

    latest = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        bt, bid, snapshot = snapshot_to_group(item)
        if not bt or not bid:
            continue
        ts = parse_time(
            item.get("backup-time")
            or item.get("backup_time")
            or item.get("time")
            or item.get("ctime")
        )
        key = f"{bt}/{bid}"
        cur = latest.get(key)
        if cur is None or (ts is not None and (cur.get("ts") is None or ts > cur.get("ts"))):
            latest[key] = {
                "group": key,
                "ts": ts,
                "snapshot": snapshot or build_snapshot_string(bt, bid, ts),
            }

    out = []
    now = arrow.utcnow()
    for key, item in latest.items():
        ts = item.get("ts")
        age = "unknown"
        if isinstance(ts, int):
            age = arrow.get(ts).humanize(now)
        out.append(
            {
                "comment": group_comments.get(key, ""),
                "group": key,
                "latest_time": age,
                "ts": ts,
            }
        )

    out.sort(key=lambda r: (r.get("ts") is None, -(r.get("ts") or 0)))

    for row in out:
        print(f"{row['comment']}\t{row['group']}\t{row['latest_time']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
