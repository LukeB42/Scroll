# -*- coding: utf-8 -*-
"""
Minimal IRC client protocol layer.

Connects to a server, sends/receives messages, and calls registered
handlers with parsed message dicts.
"""
import socket
import threading
import time


def parse_line(line):
    """
    Parse a raw IRC line into a dict with keys:
      prefix, command, params, trailing
    """
    msg = {"prefix": "", "command": "", "params": [], "trailing": "", "raw": line}
    if line.startswith(":"):
        idx = line.find(" ")
        msg["prefix"] = line[1:idx]
        line = line[idx + 1:]
    if " :" in line:
        idx = line.find(" :")
        trailing = line[idx + 2:]
        line = line[:idx]
        msg["trailing"] = trailing
    parts = line.split()
    if parts:
        msg["command"] = parts[0].upper()
        msg["params"] = parts[1:]
    return msg


class IRCClient:
    """
    Non-blocking IRC client.  Call .connect() then drive .poll() from
    your event loop to receive messages.
    """

    def __init__(self, host, port, nick, ident, realname):
        self.host     = host
        self.port     = port
        self.nick     = nick
        self.ident    = ident
        self.realname = realname

        self._sock      = None
        self._buf       = ""
        self._lock      = threading.Lock()
        self._send_queue = []
        self.connected  = False
        self.handlers   = []   # callables receiving parsed msg dicts

    # ------------------------------------------------------------------
    def connect(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((self.host, self.port))
        self._sock.setblocking(False)
        self.connected = True
        self.raw("NICK %s" % self.nick)
        self.raw("USER %s 0 * :%s" % (self.ident, self.realname))

    def disconnect(self, msg="Goodbye"):
        if self.connected:
            try:
                self.raw("QUIT :%s" % msg)
                time.sleep(0.2)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
        self.connected = False

    # ------------------------------------------------------------------
    def raw(self, line):
        """Send a raw IRC line."""
        with self._lock:
            self._send_queue.append(line.rstrip("\r\n") + "\r\n")

    def join(self, channel):
        self.raw("JOIN %s" % channel)

    def part(self, channel, reason=""):
        if reason:
            self.raw("PART %s :%s" % (channel, reason))
        else:
            self.raw("PART %s" % channel)

    def privmsg(self, target, text):
        self.raw("PRIVMSG %s :%s" % (target, text))

    def notice(self, target, text):
        self.raw("NOTICE %s :%s" % (target, text))

    # ------------------------------------------------------------------
    def poll(self):
        """
        Call from your event loop.  Reads available data, dispatches
        parsed messages to handlers, flushes the send queue.
        Returns list of parsed message dicts received this cycle.
        """
        if not self.connected:
            return []

        # flush outbound
        with self._lock:
            queue, self._send_queue = self._send_queue, []
        for line in queue:
            try:
                self._sock.sendall(line.encode("utf-8", errors="replace"))
            except Exception:
                pass

        # read inbound
        received = []
        try:
            data = self._sock.recv(4096).decode("utf-8", errors="replace")
            self._buf += data
        except BlockingIOError:
            pass
        except Exception:
            self.connected = False
            return received

        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip("\r")
            if not line:
                continue
            msg = parse_line(line)
            # Auto-respond to PING
            if msg["command"] == "PING":
                self.raw("PONG :%s" % msg["trailing"])
            for handler in self.handlers:
                try:
                    handler(msg)
                except Exception:
                    pass
            received.append(msg)

        return received
