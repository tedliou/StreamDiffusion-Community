# NDI and Spout as interchangeable Transports

Every Source and Sink implements one small interface and is backed by either NDI (cyndilib, for links between machines) or Spout (SpoutGL, for same-machine links without compression). The Transport is a Reset Setting, so the user can switch without restarting.

NDI frames are received in their native UYVY format and converted on the GPU: that halves upload bandwidth and skips the NDI SDK's CPU conversion. cyndilib is chosen because its Windows wheels bundle the NDI runtime, so users never install NDI separately. The NDI licence still requires an ndi.video link in the Web Panel and README, and shipping the licence text.

## Considered Options

- ndi-python: rejected, narrower wheel coverage and no bundled runtime.
- Shared memory or CUDA IPC with a custom TouchDesigner component: rejected, it needs native code on the TouchDesigner side.
