from utils.xml_loader import load_config
from config.keysight_scope import build_scpi_sequence
import pyvisa

def apply_xml_to_scope(xml_path: str, resource: str | None = None):
    cfg = load_config(xml_path)
    cmds = build_scpi_sequence(cfg)

    rm = pyvisa.ResourceManager()
    if resource is None:
        resources = rm.list_resources()
        if not resources:
            raise RuntimeError("No VISA resources found.")
        resource = resources[0]

    with rm.open_resource(resource, timeout=2000) as inst:
        try:
            _ = inst.query("*IDN?").strip()
        except Exception:
            pass
        for cmd in cmds:
            inst.write(cmd)
    return True
