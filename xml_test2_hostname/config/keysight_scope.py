def build_scpi_sequence(cfg: dict):
    cmds = []
    cmds.append("DISP:LAB " + ("ON" if cfg.get("display_label", False) else "OFF"))

    ts = cfg.get("time_scale", "").strip()
    if ts:
        cmds.append(f":TIM:SCAL {ts}")

    for ch in cfg.get("channels", []):
        n = ch.get("number", 1)
        on = ch.get("display", False)
        cmds.append(f":CHAN{n}:DISP {'ON' if on else 'OFF'}")
        if on:
            if ch.get("scale"):
                cmds.append(f":CHAN{n}:SCAL {ch['scale']}")
            if ch.get("label"):
                lab = ch['label'].replace("'", "\'")
                cmds.append(f":CHAN{n}:LAB '{lab}'")
            if ch.get("probe"):
                cmds.append(f":CHAN{n}:PROB {ch['probe']}")
            # Unit handling differs by model; uncomment if supported:
            # if ch.get("unit") in ("VOLT", "AMP"):
            #     cmds.append(f":CHAN{n}:UNIT {ch['unit']}")

    trig = cfg.get("trigger", {})
    mode = trig.get("mode", "EDGE")
    src = trig.get("source", "CHAN1")
    lvl = trig.get("level", "")
    slope = trig.get("slope", "POS")

    cmds.append(f":TRIG:MODE {mode}")
    cmds.append(f":TRIG:{mode}:SOUR {src}")
    if lvl:
        cmds.append(f":TRIG:{mode}:LEV {lvl}")
    if slope:
        cmds.append(f":TRIG:{mode}:SLOP {slope}")

    tcmd = cfg.get("trigger_command", "SINGLE")
    if tcmd:
        cmds.append(tcmd)

    return cmds
