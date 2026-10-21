# One process, three threads, latest-frame hand-off

The Runtime is one Python process with a receive thread, a generation thread and a send thread. Stages hand frames to each other through single-slot mailboxes where the newest frame replaces any unread one: a stage that falls behind drops old frames instead of queueing them. GPU work runs on dedicated CUDA streams with event-based synchronisation, never a device-wide synchronise per frame.

In live performance a late frame is worse than a skipped one, so latency is bounded by design rather than by tuning queue lengths. Threads are enough because the heavy work (NDI decoding, Spout copies, CUDA kernels) runs outside the GIL.

## Considered Options

- Multiprocessing with shared memory, as upstream's demo did: rejected, it adds a CPU copy and IPC per frame for no gain.
- Free-threaded CPython 3.14t: rejected for now, several required wheels have no free-threaded build.
