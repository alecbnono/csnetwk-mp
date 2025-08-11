import sys
import time

class VerboseLogger:
    def __init__(self, verbose: bool, use_color: bool = True):
        self.verbose = verbose
        self.use_color = use_color and sys.stdout.isatty()

    def set_verbose(self, v: bool):
        self.verbose = v

    def _c(self, s: str, code: str) -> str:
        return f"\x1b[{code}m{s}\x1b[0m" if self.use_color else s

    def _p(self, prefix: str, msg: str):
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"{ts} {prefix} {msg}", file=sys.stdout, flush=True)

    def send(self, msg: str):
        if self.verbose: self._p(self._c("SEND >", "36"), msg)   # cyan

    def recv(self, msg: str):
        if self.verbose: self._p(self._c("RECV <", "35"), msg)   # magenta

    def drop(self, why: str):
        if self.verbose: self._p(self._c("DROP !", "33"), why)   # yellow

    def info(self, msg: str):
        self._p(self._c("INFO -", "34"), msg)                    # blue

    def warn(self, msg: str):
        self._p(self._c("WARN -", "33;1"), msg)                  # bright yellow

    def error(self, msg: str):
        self._p(self._c("ERR  -", "31;1"), msg)                  # bright red
