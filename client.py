#!/usr/bin/env python3
import socket
import os
import sys
import termios
import atexit
import asyncio
import websockets

HEIGHT=24
WIDTH=80

def enable_echo(fd, enabled):
    (iflag, oflag, cflag, lflag, ispeed, ospeed, cc) \
        = termios.tcgetattr(fd)

    if enabled:
        lflag |= termios.ECHO
    else:
        lflag &= ~termios.ECHO

    new_attr = [iflag, oflag, cflag, lflag, ispeed, ospeed, cc]
    termios.tcsetattr(fd, termios.TCSANOW, new_attr)

cols, rows = os.get_terminal_size(0)
if rows < HEIGHT or cols < WIDTH:
    print("Terminal size must be at least " + str(WIDTH) + "x" + str(HEIGHT))
    sys.exit(1)



async def client():
    uri = sys.argv[1]
    async with websockets.connect(uri) as ws:
        try:
            while True:
                data = await ws.recv()
                sys.stdout.buffer.write(data)
                sys.stdout.flush()
        except websockets.exceptions.ConnectionClosed:
            print("Connection closed")


print("Connecting...")
atexit.register(enable_echo, sys.stdin.fileno(), True)
enable_echo(sys.stdin.fileno(), False)
asyncio.get_event_loop().run_until_complete(client())

    
