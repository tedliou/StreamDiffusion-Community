"""Builds the StreamTurbo example component inside TouchDesigner and saves it as StreamTurbo.tox.

The .tox in this folder is the result; this script is its readable, diffable source. To regenerate it, run in the
Textport (with <repo> replaced by this repository's path):

    exec(open(r"<repo>/touchdesigner/build_example.py").read())
    build_and_save(op("/project1"), r"<repo>/touchdesigner/StreamTurbo.tox")

The component sends a picture to StreamTurbo over NDI or Spout, receives the Output Frames back, drives
Settings over OSC, shows status, and measures Round-trip Latency.
"""

# ruff: noqa: F821  (operator types such as baseCOMP are globals inside TouchDesigner)

PAREXEC = r"""
# Sends Settings to StreamTurbo when the component's parameters change (OSC, /streamturbo/<setting path>).
SETTINGS = {"Prompt": "prompt", "Strength": "strength", "Seed": "seed"}


def send(address, value):
    op("oscout").sendOSC(address, [value])


def onValueChange(par, prev):
    if par.name in SETTINGS:
        value = par.eval()
        if parent().fetch("from_runtime_" + par.name, None) == value:
            return  # an echo of a change StreamTurbo just reported
        send("/streamturbo/" + SETTINGS[par.name], value)
    elif par.name == "Transport":
        send("/streamturbo/source/transport", par.eval())
        send("/streamturbo/sink/transport", par.eval())
        sender = op("ndi_out").par.name if par.eval() == "ndi" else op("spout_out").par.sendername
        send("/streamturbo/source/name", sender.eval())


def onPulse(par):
    if par.name == "Recall":
        send("/streamturbo/preset/recall", parent().par.Preset.eval())
    elif par.name == "Savepreset":
        send("/streamturbo/preset/save", parent().par.Preset.eval())
    elif par.name == "Sync":
        op("oscout").sendOSC("/streamturbo/sync", [])
    elif par.name == "Measurelatency":
        op("latency").module.start()
"""

OSCIN_CALLBACKS = r"""
# Shows what StreamTurbo reports: its Settings (whichever Control Surface changed them) and its status.
SETTINGS = {"/streamturbo/prompt": "Prompt", "/streamturbo/strength": "Strength", "/streamturbo/seed": "Seed"}
STATUS = {
    "/streamturbo/status/source_state": "Sourcestate",
    "/streamturbo/status/throughput_fps": "Throughput",
    "/streamturbo/status/generation_ms_p50": "Generationms",
    "/streamturbo/status/error": "Error",
}


def onReceiveOSC(dat, rowIndex, message, byteData, timeStamp, address, args, peer):
    comp = parent()
    if not args:
        return
    value = args[0]
    if address in SETTINGS:
        name = SETTINGS[address]
        comp.store("from_runtime_" + name, value)
        if comp.pars(name)[0].eval() != value:
            comp.pars(name)[0].val = value
    elif address in STATUS:
        comp.pars(STATUS[address])[0].val = value
    elif address == "/streamturbo/error":
        comp.par.Error = value
"""

LATENCY = r"""
# Round-trip Latency: switch the picture sent between black and white at known times, and time how long it takes
# for the brightness of what comes back to follow. Measured at the current Settings, so Generation is included.
import time

SAMPLES = 10
SETTLE = 0.8  # seconds between switches, so the previous change has fully come back
TIMEOUT = 5.0
THRESHOLD = 0.08  # change in mean brightness that counts as "came back"


def brightness():
    chop = op("brightness")
    return (chop["r"].eval() + chop["g"].eval() + chop["b"].eval()) / 3


def start():
    parent().par.Latency = "Measuring…"
    parent().store("latency", {"phase": "settle", "until": time.perf_counter() + 1.5, "white": False, "samples": []})
    op("pattern").par.colorr = op("pattern").par.colorg = op("pattern").par.colorb = 0
    op("send_select").par.index = 1


def finish(state, error=None):
    op("send_select").par.index = 0
    parent().unstore("latency")
    samples = sorted(1000 * s for s in state["samples"])
    if error or not samples:
        parent().par.Latency = error or "No samples"
        return
    mean = sum(samples) / len(samples)
    parent().par.Latency = f"{mean:.0f} ms (min {samples[0]:.0f}, max {samples[-1]:.0f}, n={len(samples)})"


def onFrameStart(frame):
    state = parent().fetch("latency", None)
    if state is None:
        return
    now, level = time.perf_counter(), brightness()
    if state["phase"] == "settle" and now >= state["until"]:
        state["white"] = not state["white"]
        value = 1 if state["white"] else 0
        op("pattern").par.colorr = op("pattern").par.colorg = op("pattern").par.colorb = value
        state.update(phase="wait", switched=now, before=level)
    elif state["phase"] == "wait":
        if abs(level - state["before"]) > THRESHOLD:
            state["samples"].append(now - state["switched"])
            state.update(phase="settle", until=now + SETTLE)
            if len(state["samples"]) >= SAMPLES:
                finish(state)
                return
        elif now - state["switched"] > TIMEOUT:
            finish(state, "Timed out: is StreamTurbo receiving and sending?")
            return
    parent().store("latency", state)
"""


def _set(target, **values):
    for name, value in values.items():
        pars = target.pars(name)
        if not pars:
            raise AttributeError(f"{target.path} has no parameter {name}")
        pars[0].val = value


def _expr(target, name, expression):
    pars = target.pars(name)
    if not pars:
        raise AttributeError(f"{target.path} has no parameter {name}")
    pars[0].expr = expression


def _custom_parameters(comp):
    page = comp.appendCustomPage("StreamTurbo")
    transport = page.appendMenu("Transport", label="Transport")[0]
    transport.menuNames, transport.menuLabels = ["ndi", "spout"], ["NDI", "Spout"]
    page.appendStr("Prompt", label="Prompt")
    strength = page.appendFloat("Strength", label="Strength")[0]
    strength.min, strength.max, strength.clampMin, strength.clampMax = 0, 1, True, True
    strength.normMin, strength.normMax, strength.default, strength.val = 0, 1, 0.68, 0.68
    seed = page.appendInt("Seed", label="Seed")[0]
    seed.min, seed.clampMin, seed.normMax, seed.default, seed.val = 0, True, 1000, 2, 2
    page.appendStr("Preset", label="Preset")[0].val = "Glass"
    page.appendPulse("Recall", label="Recall Preset")
    page.appendPulse("Savepreset", label="Save Preset")
    page.appendPulse("Sync", label="Get Settings")

    status = comp.appendCustomPage("Status")
    for name, label in (("Sourcestate", "Source"), ("Error", "Error"), ("Latency", "Round-trip Latency")):
        par = status.appendStr(name, label=label)[0]
        par.readOnly = True
    for name, label in (("Throughput", "Throughput (fps)"), ("Generationms", "Generation Time p50 (ms)")):
        par = status.appendFloat(name, label=label)[0]
        par.readOnly = True
    status.appendPulse("Measurelatency", label="Measure Latency")

    connection = comp.appendCustomPage("Connection")
    connection.appendStr("Host", label="StreamTurbo Host")[0].val = "127.0.0.1"
    port = connection.appendInt("Port", label="OSC Port")[0]
    port.default = port.val = 7000
    reply = connection.appendInt("Replyport", label="OSC Reply Port")[0]
    reply.default = reply.val = 7001


def build(parent_comp, name="StreamTurbo"):
    comp = parent_comp.create(baseCOMP, name)
    comp.comment = "StreamTurbo example: send, receive, control over OSC, measure Round-trip Latency."
    _custom_parameters(comp)

    # What is sent: the component's input when connected, else an animated test picture.
    source_in = comp.create(inTOP, "in1")
    test = comp.create(noiseTOP, "test_picture")
    _set(test, outputresolution="custom", resolutionw=1024, resolutionh=768, mono=False)
    _expr(test, "tz", "absTime.seconds * 0.2")
    source = comp.create(switchTOP, "source_select")
    source.inputConnectors[0].connect(test)
    source.inputConnectors[1].connect(source_in)
    _expr(source, "index", "1 if parent().inputConnectors[0].connections else 0")

    pattern = comp.create(constantTOP, "pattern")  # the Round-trip Latency pattern: black or white
    _set(pattern, outputresolution="custom", resolutionw=1024, resolutionh=768, colorr=0, colorg=0, colorb=0)
    send = comp.create(switchTOP, "send_select")
    send.inputConnectors[0].connect(source)
    send.inputConnectors[1].connect(pattern)
    _set(send, index=0)

    ndi_out = comp.create(ndioutTOP, "ndi_out")
    ndi_out.inputConnectors[0].connect(send)
    _set(ndi_out, name="TD Out")
    _expr(ndi_out, "active", "parent().par.Transport == 'ndi'")
    spout_out = comp.create(spoutoutTOP, "spout_out")
    spout_out.inputConnectors[0].connect(send)
    _set(spout_out, sendername="TD Spout")
    _expr(spout_out, "active", "parent().par.Transport == 'spout'")

    # What comes back: StreamTurbo's Sink, named "StreamTurbo" by default.
    ndi_in = comp.create(ndiinTOP, "ndi_in")
    _expr(ndi_in, "name", "__import__('os').environ.get('COMPUTERNAME', '') + ' (StreamTurbo)'")
    _expr(ndi_in, "active", "parent().par.Transport == 'ndi'")
    spout_in = comp.create(spoutinTOP, "spout_in")
    _set(spout_in, sendername="StreamTurbo")
    received = comp.create(switchTOP, "received_select")
    received.inputConnectors[0].connect(ndi_in)
    received.inputConnectors[1].connect(spout_in)
    _expr(received, "index", "0 if parent().par.Transport == 'ndi' else 1")
    out = comp.create(outTOP, "out1")
    out.inputConnectors[0].connect(received)

    analyze = comp.create(analyzeTOP, "analyze")
    analyze.inputConnectors[0].connect(received)
    _set(analyze, op="average")
    level = comp.create(toptoCHOP, "brightness")
    _set(level, top=analyze.path)

    # OSC to and from StreamTurbo.
    osc_out = comp.create(oscoutDAT, "oscout")
    _expr(osc_out, "address", "parent().par.Host")
    _expr(osc_out, "port", "parent().par.Port")
    osc_in = comp.create(oscinDAT, "oscin")
    _expr(osc_in, "port", "parent().par.Replyport")
    callbacks = comp.create(textDAT, "oscin_callbacks")
    callbacks.text = OSCIN_CALLBACKS
    _set(osc_in, callbacks=callbacks.path)

    parexec = comp.create(parameterexecuteDAT, "parameters_to_osc")
    parexec.text = PAREXEC
    _set(parexec, op=comp.path, pars="*", valuechange=True, onpulse=True, custom=True, builtin=False)

    latency = comp.create(executeDAT, "latency")
    latency.text = LATENCY
    _set(latency, framestart=True)

    _layout(comp)
    for node in (ndi_out, spout_out, received):  # viewers keep the senders and receivers cooking every frame
        node.viewer = True
    return comp


def _layout(comp):
    columns = [
        ["in1", "test_picture", "pattern"],
        ["source_select", "send_select"],
        ["ndi_out", "spout_out"],
        ["ndi_in", "spout_in"],
        ["received_select", "analyze", "brightness"],
        ["out1"],
        ["oscout", "oscin", "oscin_callbacks", "parameters_to_osc", "latency"],
    ]
    for x, names in enumerate(columns):
        for y, name in enumerate(names):
            node = comp.op(name)
            node.nodeX, node.nodeY = x * 200, -y * 150


def build_and_save(parent_comp, path, name="StreamTurbo"):
    comp = build(parent_comp, name)
    comp.save(path)
    return comp
