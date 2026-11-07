"""Create one small Vultr instance for the live trial. NOT RUN YET: written while the Vultr API
refused this machine's address, so treat it as a draft until it has been run once.

    VULTR_ENV_FILE=/path/to/.env  python live/deploy/provision_vultr.py --ssh-pubkey KEY.pub --ssh-from 203.0.113.7 [--create]

Without --create it only reads the account and prints what it would do.

What it does, and nothing else:
  - reads the account balance and refuses to go on unless there is credit to cover the instance;
  - creates an SSH key entry, a firewall group (80 and 443 from anywhere, 22 from --ssh-from only) and
    one instance, all named or tagged "docsdrift-live";
  - stops if an instance named "docsdrift-live" already exists; reuses its own SSH key and firewall group from an earlier try.
It never modifies or deletes anything, so existing instances, firewall groups and subscriptions are untouched.
The API key is read from VULTR_ENV_FILE (a line VULTR_API_KEY=...) and never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LABEL = "docsdrift-live"
REGION, PLAN, OS_NAME = "ewr", "vc2-1c-0.5gb", "Debian 12 x64 (bookworm)"   # cheapest plan with IPv4; Ubuntu 24.04 needs 1 GB


def api_key() -> str:
    path = Path(os.environ.get("VULTR_ENV_FILE", ""))
    if not path.is_file():
        sys.exit("set VULTR_ENV_FILE to a file with a VULTR_API_KEY=... line")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("VULTR_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("no VULTR_API_KEY in VULTR_ENV_FILE")


def call(key: str, method: str, path: str, body: dict | None = None):
    req = urllib.request.Request("https://api.vultr.com" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(4 if method == "GET" else 1):     # only reads are retried: a repeated POST could create twice
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            return e.code, {"error": e.read().decode("utf-8", "replace")[:300]}
        except urllib.error.URLError:
            if attempt == 3 or method != "GET":
                raise
            time.sleep(3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssh-pubkey", required=True, help="public key file to install on the instance")
    ap.add_argument("--ssh-from", required=True, help="the one IPv4 address allowed to reach port 22")
    ap.add_argument("--create", action="store_true", help="actually create the resources")
    args = ap.parse_args()
    key = api_key()

    status, acc = call(key, "GET", "/v2/account")
    if status != 200:
        print("account:", status, acc.get("error"))
        return 2
    balance, pending = acc["account"]["balance"], acc["account"]["pending_charges"]
    credit = -balance - pending          # Vultr shows credit as a negative balance
    print(f"account: balance {balance}, pending charges {pending} -> about ${credit:.2f} of credit left")
    status, plans = call(key, "GET", "/v2/plans?per_page=500&type=all")
    plan = next(p for p in plans["plans"] if p["id"] == PLAN)
    print(f"plan {PLAN}: ${plan['monthly_cost']}/month, ${plan['hourly_cost']}/hour, in {REGION}: {REGION in plan['locations']}")
    status, avail = call(key, "GET", f"/v2/regions/{REGION}/availability")
    print(f"plan on sale in {REGION} right now: {PLAN in avail.get('available_plans', [])}")
    if credit < plan["monthly_cost"]:
        print("not enough credit to cover a month of this instance; stopping (nothing was created)")
        return 3

    status, d = call(key, "GET", "/v2/instances")
    for item in d.get("instances", []):
        if item.get("label") == LABEL or LABEL in (item.get("tags") or []):
            print(f"instance {item.get('id')} named {LABEL} already exists; stopping")
            return 4
    status, d = call(key, "GET", "/v2/ssh-keys")
    ssh_id = next((k["id"] for k in d.get("ssh_keys", []) if k.get("name") == LABEL), None)
    status, d = call(key, "GET", "/v2/firewalls")
    fw_id = next((g["id"] for g in d.get("firewall_groups", []) if g.get("description") == LABEL), None)
    status, oses = call(key, "GET", "/v2/os?per_page=500")
    os_id = next(o["id"] for o in oses["os"] if o["name"] == OS_NAME)
    pub = Path(args.ssh_pubkey).read_text(encoding="utf-8").strip()
    print(f"would create: ssh key, firewall group (80, 443 open; 22 from {args.ssh_from}), instance {PLAN} {OS_NAME} in {REGION}")
    if not args.create:
        print("dry run: add --create to do it")
        return 0

    if not ssh_id:
        status, k = call(key, "POST", "/v2/ssh-keys", {"name": LABEL, "ssh_key": pub})
        assert status in (200, 201), k
        ssh_id = k["ssh_key"]["id"]
    if not fw_id:
        status, fw = call(key, "POST", "/v2/firewalls", {"description": LABEL})
        assert status in (200, 201), fw
        fw_id = fw["firewall_group"]["id"]
        rules = [("v4", "0.0.0.0", 0, "80"), ("v4", "0.0.0.0", 0, "443"), ("v6", "::", 0, "80"), ("v6", "::", 0, "443"),
                 ("v4", args.ssh_from, 32, "22")]
        for ip_type, subnet, size, port in rules:
            status, r = call(key, "POST", f"/v2/firewalls/{fw_id}/rules",
                             {"ip_type": ip_type, "protocol": "tcp", "subnet": subnet, "subnet_size": size, "port": port})
            assert status in (200, 201), r
    status, inst = call(key, "POST", "/v2/instances", {
        "region": REGION, "plan": PLAN, "os_id": os_id, "label": LABEL, "hostname": LABEL, "tags": [LABEL],
        "sshkey_id": [ssh_id], "firewall_group_id": fw_id, "backups": "disabled", "enable_ipv6": False})
    assert status in (200, 201, 202), inst
    iid = inst["instance"]["id"]
    print("instance", iid, "created; waiting for an address")
    for _ in range(60):
        time.sleep(10)
        status, d = call(key, "GET", f"/v2/instances/{iid}")
        i = d["instance"]
        if i["status"] == "active" and i["main_ip"] not in ("", "0.0.0.0") and i.get("server_status") == "ok":
            break
    print(json.dumps({"instance_id": iid, "main_ip": i["main_ip"], "plan": PLAN, "region": REGION,
                      "hourly_cost": plan["hourly_cost"], "monthly_cost": plan["monthly_cost"],
                      "firewall_group_id": fw_id, "ssh_key_id": ssh_id,
                      "domain": i["main_ip"].replace(".", "-") + ".sslip.io"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
