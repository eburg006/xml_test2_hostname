
import socket
import pyvisa

def _extract_host(resource: str) -> str:
    try:
        parts = resource.split("::")
        return parts[1] if len(parts) >= 2 else ""
    except Exception:
        return ""

def _reverse_dns(ip_or_host: str) -> str:
    if not ip_or_host:
        return ""
    try:
        name, _, _ = socket.gethostbyaddr(ip_or_host)
        return name
    except Exception:
        # Try forward lookup to get a canonical name if already a hostname
        try:
            return socket.gethostbyname_ex(ip_or_host)[0]
        except Exception:
            return ip_or_host  # fall back to the raw address

def discover_instruments():
    """Return a list of VISA resources excluding HiSLIP, with hostnames.

    Each item is a dict:
      - hostname: friendly label (via reverse DNS when possible)
      - resource: full VISA resource string
      - idn: *IDN? response or an error string
    """
    rows = []
    rm = pyvisa.ResourceManager()
    for res in rm.list_resources():
        up = res.upper()
        # Hard filter: no HiSLIP
        if "HISLIP" in up:
            continue
        # Keep classic INSTR and SOCKET only
        if not (up.endswith("::INSTR") or up.endswith("::SOCKET")):
            continue

        host = _extract_host(res)
        hostname = _reverse_dns(host)

        idn = ""
        try:
            with rm.open_resource(res, timeout=1500) as inst:
                try:
                    inst.read_termination = '\n'
                    inst.write_termination = '\n'
                except Exception:
                    pass
                try:
                    idn = inst.query("*IDN?").strip()
                except Exception:
                    try:
                        inst.write("*IDN?"); idn = inst.read().strip()
                    except Exception:
                        idn = "(no response)"
        except Exception as e:
            idn = f"(open failed: {e})"

        rows.append({
            "hostname": hostname or host or "(unknown)",
            "resource": res,
            "idn": idn,
        })

    rows.sort(key=lambda r: (r.get("hostname",""), r.get("resource","")))
    return rows
