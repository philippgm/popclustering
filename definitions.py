def Requisition_template():
    body = {
        "definitions": [
            {
            "target": "target",
            "af": 4,
            "packets": 1,
            "size": 48,
            "description": "Ping measurement to ",
            "interval": 60,
            "resolve_on_probe": True,
            "skip_dns_check": False,
            "include_probe_id": False,
            "type": "ping"
        }
        ],
        "probes": [
            {
            "value": "WW",
            "type": "area",
            "requested": 1
        }
        ],
        "is_oneoff": False,
        "bill_to": "philippegarandy@gmail.com",
        "start_time": "start_time",
        "stop_time": "stop_time"
    }
    
    return body