"""Reproduce stale DNAT shadowing in a disposable network namespace.

Run: sudo -n unshare --net python3 scripts/tests/check_hermes_hostport.py
Requires iproute2/iptables. Never run in the host network namespace.
"""

import http.server
import os
import subprocess
import threading
import urllib.error
import urllib.request


def main():
    # unshare must have separated us from PID 1's network before any mutation.
    assert os.readlink("/proc/self/ns/net") != os.readlink("/proc/1/ns/net"), "Refusing host firewall mutation"
    subprocess.run(["ip", "link", "set", "lo", "up"], check=True)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    backend_port = server.server_address[1]
    chain = "HERMES-REPRO"

    def iptables(*args, check=True):
        return subprocess.run(["iptables", "-t", "nat", *args], check=check,
                              capture_output=True, text=True)

    iptables("-N", chain)
    iptables("-A", "OUTPUT", "-d", "127.0.0.1", "-p", "tcp", "--dport", "8787", "-j", chain)
    stale = ["-d", "127.0.0.1/32", "-p", "tcp", "-m", "tcp", "--dport", "8787",
             "-j", "DNAT", "--to-destination", f"127.0.0.2:{backend_port}"]
    current = [*stale[:-1], f"127.0.0.1:{backend_port}"]
    iptables("-A", chain, *stale)
    iptables("-A", chain, *current)
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        client.open("http://127.0.0.1:8787/", timeout=2)
    except urllib.error.URLError:
        print("PASS: obsolete DNAT shadows the live backend")
    else:
        raise AssertionError("Fixture did not reproduce the failure")
    iptables("-D", chain, *stale)
    with client.open("http://127.0.0.1:8787/", timeout=2) as response:
        assert response.status == 200
    assert iptables("-C", chain, *current, check=False).returncode == 0
    assert iptables("-C", chain, *stale, check=False).returncode == 1
    print("PASS: exact stale-rule removal restores HTTP 200 and retains active DNAT")
    server.shutdown()


if __name__ == "__main__":
    main()
