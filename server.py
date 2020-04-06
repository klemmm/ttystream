#!/usr/bin/env python3
import time
import pty
import asyncio
import fcntl
import termios
import struct
import sys
import pyte
import os
import socket
import threading
import websockets
import queue

HEIGHT=24
WIDTH=80
SHELL="/bin/bash"

q = queue.Queue(maxsize=10)

loop = asyncio.get_event_loop()
class Queue:
    def __init__(self):
        self.q = []
        self.f = None

    def enqueue_mt(self, data):
        global loop
        asyncio.run_coroutine_threadsafe(self.enqueue(data), loop)

    async def enqueue(self, data):
        self.q.append(data)
        if self.f is not None and  (not self.f.done()):
            self.f.set_result(True)
        
    async def dequeue(self):
        if len(self.q) == 0:
            assert(self.f == None)
            self.f = loop.create_future()
            r = await self.f
            self.f = None
        return self.q.pop(0)

def dispatch(data):
    for q in clients:
        q.enqueue_mt(data)

sizeset = False
sent = 0
lastreset = 0.0
idle_until = 0.0
idle = False
def master_read(fd):
    global sizeset
    global q
    global sent
    global lastreset
    global idle
    global idle_until
    if not sizeset:
        winsize = struct.pack("HHHH", HEIGHT, WIDTH, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        sizeset = True
    data = os.read(fd, 1024)
    stream.feed(data.decode(encoding="utf-8", errors="ignore"))
    sent += len(data)
    if sent > 512:
        idle = True
    now = time.time()
    if now - lastreset > 0.5:
        sent = 0
        lastreet = now
    if not idle:
        q.put_nowait(data)    
    return data
    
screen = pyte.Screen(WIDTH, HEIGHT)
stream = pyte.Stream(screen)

class DispatcherThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global q
        global idle
        while True:
            try:
                data = q.get(timeout=1.0)
                dispatch(data)
            except:
                if idle:
                    idle = False
                    dispatch(resync())

        
tty_has_quit = False
class TtyThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
    def run(self):
        global tty_has_quit
        print("TTY cast started")
        os.environ["TERM"] = "linux"
        pty.spawn(SHELL, master_read)
        print("TTY cast finished")
        os._exit(0)


def resync():
    buf = ""
    lastchar = None
    first = True
    for y in range(len(screen.buffer)):
        if y > 0:
            buf += "\n"
        line = screen.buffer[y]
        for x in range(len(line)):
            current = line[x]
            
            status = []
            
            if (lastchar is not None and (((current.fg == 'default') and (lastchar.fg != 'default')) or ((current.bg == 'default') and (lastchar.bg != 'default')))):
                lastchar = None
                status.append("0")
            
            fgcolors = {
                "black" : "30",
                "red" : "31",
                "green" : "32",
                "brown" : "33",
                "blue" : "34",
                "magenta" : "35",
                "cyan" : "36",
                "white" : "37"
            }
            if ((lastchar is None) or (lastchar.fg != current.fg)) and (current.fg != 'default') :
                status.append(str(fgcolors[current.fg]))

            bgcolors = {
                "black" : "40",
                "red" : "41",
                "green" : "42",
                "brown" : "43",
                "blue" : "44",
                "magenta" : "45",
                "cyan" : "46",
                "white" : "47"
            }
            if ((lastchar is None) or (lastchar.bg != current.bg)) and (current.bg != 'default') :
                status.append(str(bgcolors[current.bg]))
            
            bold = {
                True : "1",
                False: "22"
            }    
            if (lastchar is None) or (lastchar.bold != current.bold):
                status.append(str(bold[current.bold]))
                

            reverse = {
                True : "7",
                False: "27"
            }    
            if (lastchar is None) or (lastchar.reverse != current.reverse):
                status.append(str(reverse[current.reverse]))
                
            underscore = {
                True : "4",
                False: "24"
            }    
            if (lastchar is None) or (lastchar.underscore != current.underscore):
                status.append(str(underscore[current.underscore]))
                
            blink = {
                True : "5",
                False: "25"
            }    
            if (lastchar is None) or (lastchar.blink != current.blink):
                status.append(str(blink[current.blink]))
                
            
            if status != []:
                buf += "\x1B[" + ";".join(status) + "m"
            buf += current.data
            lastchar = current

    return b"\x1B[H\x1B[2J" + buf.encode("utf-8") + b"\x1B[" + str(screen.cursor.y + 1).encode("utf-8") + b";" + str(screen.cursor.x + 1).encode("utf-8") + b"H"

clients = []
async def serve(ws, path):
    await ws.send(resync())
    q = Queue()
    clients.append(q)
    try:
        while True:
            data = await q.dequeue()
            await ws.send(data)
    except websockets.exceptions.ConnectionClosed:
        clients.remove(q)

cols, rows = os.get_terminal_size(0)
if rows < HEIGHT or cols < WIDTH:
    print("Terminal size must be at least " + str(WIDTH) + "x" + str(HEIGHT))
    sys.exit(1)

start_server = websockets.serve(serve, "0.0.0.0", int(sys.argv[1]))
asyncio.ensure_future(start_server)
disp_thread = DispatcherThread()
disp_thread.start()
tty_thread = TtyThread()
tty_thread.start()
loop.run_forever()
