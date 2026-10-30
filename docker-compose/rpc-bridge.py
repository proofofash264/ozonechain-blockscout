#!/usr/bin/env python3
"""Forward Docker-bridge connections to Ethermint listeners on 127.0.0.1.

host.docker.internal is 172.17.0.1. The node binds JSON-RPC, its websocket,
and CometBFT to localhost only, so the explorer proxy cannot reach them
directly.
"""

import select
import socket
import threading

LISTEN = "172.17.0.1"
TARGETS = (
    (8545, "127.0.0.1", 8545),
    (8546, "127.0.0.1", 8546),
    (26657, "127.0.0.1", 26657),
)


def pipe(left, right):
    sockets = [left, right]
    try:
        while True:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                continue
            for source in readable:
                dest = right if source is left else left
                data = source.recv(65536)
                if not data:
                    return
                dest.sendall(data)
    except OSError:
        return
    finally:
        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass


def handle(client, upstream_host, upstream_port):
    try:
        upstream = socket.create_connection((upstream_host, upstream_port), timeout=10)
    except OSError:
        client.close()
        return
    pipe(client, upstream)


def serve(listen_port, upstream_host, upstream_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN, listen_port))
    server.listen(128)
    while True:
        client, _ = server.accept()
        threading.Thread(
            target=handle,
            args=(client, upstream_host, upstream_port),
            daemon=True,
        ).start()


def main():
    threads = []
    for listen_port, upstream_host, upstream_port in TARGETS:
        thread = threading.Thread(
            target=serve,
            args=(listen_port, upstream_host, upstream_port),
            daemon=True,
        )
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
