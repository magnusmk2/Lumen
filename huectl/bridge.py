"""Access to the Philips Hue bridge via the local CLIP v2 API."""

import requests
import urllib3

from .config import load_config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Bridge:
    """The bridge uses a self-signed certificate, hence verify=False."""

    def __init__(self, ip, app_key):
        self.base = f"https://{ip}"
        self.headers = {"hue-application-key": app_key}

    def _req(self, method, path, payload=None):
        r = requests.request(method, self.base + path, headers=self.headers,
                             json=payload, verify=False, timeout=10)
        r.raise_for_status()
        data = r.json() if r.text else {}
        errs = data.get("errors") if isinstance(data, dict) else None
        if errs:
            raise RuntimeError("; ".join(e.get("description", "") for e in errs))
        return data

    def application_id(self):
        response = requests.get(self.base + '/auth/v1', headers=self.headers,
                                verify=False, timeout=5)
        response.raise_for_status()
        identity = response.headers.get('hue-application-id')
        if not identity:
            raise RuntimeError('Bridge did not identify this application')
        return identity

    def get(self, rtype):
        return self._req("GET", f"/clip/v2/resource/{rtype}").get("data", [])

    def put(self, rtype, rid, payload):
        return self._req("PUT", f"/clip/v2/resource/{rtype}/{rid}", payload)

    def post(self, rtype, payload):
        return self._req("POST", f"/clip/v2/resource/{rtype}", payload)

    def delete(self, rtype, rid):
        return self._req("DELETE", f"/clip/v2/resource/{rtype}/{rid}")

    def snapshot(self):
        # devices are needed to edit rooms (a room holds devices, not lights)
        return {"light": self.get("light"), "room": self.get("room"),
                "zone": self.get("zone"), "scene": self.get("scene"),
                "device": self.get("device")}


def discover_bridge_ip():
    """Discovery via the Philips cloud service (requires internet access)."""
    r = requests.get("https://discovery.meethue.com", timeout=8)
    r.raise_for_status()
    found = r.json()
    return found[0]["internalipaddress"] if found else None


def load_bridge():
    cfg = load_config()
    if not cfg.get("bridge_ip") or not cfg.get("app_key"):
        return None
    return Bridge(cfg["bridge_ip"], cfg["app_key"])
