import xml.etree.ElementTree as ET

def load_config(path):
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "configuration":
        raise ValueError("Not a valid configuration file (root != configuration)")

    channels = []
    channels_elem = root.find("channels")
    if channels_elem is not None:
        for ch in channels_elem.findall("channel"):
            num = int(ch.attrib.get("number", "1"))
            display = (ch.findtext("display", default="OFF").strip().upper() == "ON")
            label = (ch.findtext("label", default="") or "").strip()
            probe = (ch.findtext("probe", default="") or "").strip()
            scale = (ch.findtext("scale", default="") or "").strip()
            unit = (ch.findtext("unit", default="") or "").strip().upper()
            channels.append({
                "number": num,
                "display": display,
                "label": label,
                "probe": probe,
                "scale": scale,
                "unit": unit,
            })

    display_label = (root.findtext("display_label", default="OFF").strip().upper() == "ON")
    time_scale = (root.findtext("time_scale", default="") or "").strip()

    trig_elem = root.find("trigger")
    trig = {
        "mode": (trig_elem.findtext("mode", default="EDGE") if trig_elem is not None else "EDGE").strip().upper(),
        "source": (trig_elem.findtext("source", default="CHAN1") if trig_elem is not None else "CHAN1").strip().upper(),
        "level": (trig_elem.findtext("level", default="") if trig_elem is not None else "").strip(),
        "slope": (trig_elem.findtext("slope", default="POS") if trig_elem is not None else "POS").strip().upper(),
    }
    trig_cmd = (root.findtext("trigger_command", default="SINGLE") or "").strip().upper()

    return {
        "channels": channels,
        "display_label": display_label,
        "time_scale": time_scale,
        "trigger": trig,
        "trigger_command": trig_cmd,
    }
