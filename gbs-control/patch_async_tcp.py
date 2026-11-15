# Keep a large control page moving. The stock libraries wait until the TCP
# send buffer is completely empty before writing more, and a phone gives up.
Import("env")
from pathlib import Path

lib = Path(env.subst("$PROJECT_LIBDEPS_DIR")) / env["PIOENV"]


def replace_once(path, old, new, marker):
    if not path.is_file():
        print("patch skipped, missing", path)
        return
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print("already patched", path.name)
        return
    if old not in text:
        print("patch did not match", path.name)
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("patched", path.name)


replace_once(
    lib / "ESPAsyncWebServer" / "src" / "ESPAsyncWebServer.h",
    "#ifndef ASYNCWEBSERVER_USE_CHUNK_INFLIGHT\n#define ASYNCWEBSERVER_USE_CHUNK_INFLIGHT 1\n#endif",
    "#ifndef ASYNCWEBSERVER_USE_CHUNK_INFLIGHT\n// A phone does not empty the send buffer before the next write.\n#define ASYNCWEBSERVER_USE_CHUNK_INFLIGHT 0\n#endif",
    "A phone does not empty the send buffer",
)

replace_once(
    lib / "ESPAsyncTCP" / "src" / "ESPAsyncTCP.cpp",
    """  if(_tx_unacked_len == 0){
    _pcb_busy = false;
    errorTracker->setCloseError(ERR_OK);
    if(_sent_cb) {
      _sent_cb(_sent_cb_arg, this, _tx_acked_len, (millis() - _pcb_sent_at));
      if(!errorTracker->hasClient())
        return;
    }
    _tx_acked_len = 0;
  }
""",
    """  if(_tx_unacked_len == 0){
    _pcb_busy = false;
    errorTracker->setCloseError(ERR_OK);
  }
  // Every ACK, not only a fully drained buffer. Otherwise a 250 kB page
  // stalls and the phone stays on "waiting" until it retries.
  if(_sent_cb && _tx_acked_len) {
    size_t acked = _tx_acked_len;
    _tx_acked_len = 0;
    _sent_cb(_sent_cb_arg, this, acked, (millis() - _pcb_sent_at));
    if(!errorTracker->hasClient())
      return;
  }
""",
    "Every ACK, not only a fully drained buffer",
)
