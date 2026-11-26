"""Local acceptance harness. Block non-loopback TCP destinations for this process."""
import ipaddress
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
from demo import Assistant, main
from verify_demo import SQL_PROMPT, count_rows
from gradio_client import Client
import gradio as gr
import torch

real_connect = socket.socket.connect
def local_connect(sock, address):
    if isinstance(address,tuple) and address[0] != "localhost" and not ipaddress.ip_address(address[0]).is_loopback:
        raise AssertionError("External connection " + str(address))
    return real_connect(sock,address)

instance = []
old_init = Assistant.__init__
def capture(self,args):
    old_init(self,args)
    instance.append(self)

original_launch = gr.Blocks.launch
def verify(self,**kwargs):
    original_launch(self,**kwargs,prevent_thread_lock=True)
    c=Client(self.local_url,verbose=False)
    try:
        a=instance[0]
        for text in [" ", "word " * 2000]:
            try:
                list(a.generate(text,[]))
            except ValueError:
                pass
            else:
                raise AssertionError("Expected input rejection")
        with patch.object(a.model,"generate",side_effect=torch.OutOfMemoryError("injected")):
            try:
                list(a.generate("hi",[]))
            except RuntimeError as err:
                assert "out of memory" in str(err)
            else:
                raise AssertionError("Expected an allocation error")
        stream=a.generate("Explain statistics in detail.",[])
        next(stream)
        stream.close()
        count_rows(c.predict(SQL_PROMPT,api_name='/chat'))
        print("PASS offline cold start, input rejection, OOM recovery, cancellation, SQL",flush=True)
    finally:
        c.close()
        self.close()
with patch.object(socket.socket,"connect",local_connect),patch.object(Assistant,"__init__",capture),patch.object(gr.Blocks,"launch",verify):
    main(sys.argv[1:])
