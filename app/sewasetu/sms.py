# -*- coding: utf-8 -*-
import logging
import threading

import requests

log = logging.getLogger("sewasetu.sms")


def send_sms(gateway_url, mobile, text):
    """Send one SMS. Returns True when the gateway accepted it."""
    try:
        resp = requests.post(gateway_url + "/api/send",
                             json={"to": mobile, "text": text}, timeout=(2, 4))
        resp.raise_for_status()
        return True
    except Exception as exc:
        log.error("sms gateway error: %s", exc)
        return False


def send_sms_async(gateway_url, mobile, text):
    """Fire-and-forget for messages the citizen is not waiting on."""
    threading.Thread(target=send_sms, args=(gateway_url, mobile, text),
                     daemon=True).start()
