# -*- coding: utf-8 -*-
#监听websocket，通过xmlrpc为其他程序提供抓包服务
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
import threading
import pickle

import mitmproxy.addonmanager
import mitmproxy.connections
import mitmproxy.http
import mitmproxy.log
import mitmproxy.tcp
import mitmproxy.websocket
import mitmproxy.proxy.protocol
from xmlrpc.server import SimpleXMLRPCServer

flow_queue = []


class ClientWebSocket:

    def __init__(self):

        pass

    # Websocket lifecycle

    def websocket_handshake(self, flow: mitmproxy.http.HTTPFlow):
        """

            Called when a client wants to establish a WebSocket connection. The

            WebSocket-specific headers can be manipulated to alter the

            handshake. The flow object is guaranteed to have a non-None request

            attribute.

        """

    def websocket_start(self, flow: mitmproxy.websocket.WebSocketFlow):
        """

            A websocket connection has commenced.

        """

    def websocket_message(self, flow: mitmproxy.websocket.WebSocketFlow):
        """

            Called when a WebSocket message is received from the client or

            server. The most recent message will be flow.messages[-1]. The

            message is user-modifiable. Currently there are two types of

            messages, corresponding to the BINARY and TEXT frame types.

        """
        global flow_queue
        flow_queue = flow.messages
        flow_msg = flow_queue[-1]
        packet = flow_msg.content
        from_client = flow_msg.from_client
        print("[" + ("Sended" if from_client else "Reveived") +
              "]: decode the packet here: %r…" % packet)

    def websocket_error(self, flow: mitmproxy.websocket.WebSocketFlow):
        """

            A websocket connection has had an error.

        """

        print("websocket_error, %r" % flow)

    def websocket_end(self, flow: mitmproxy.websocket.WebSocketFlow):
        """

            A websocket connection has ended.

        """


addons = [
    ClientWebSocket()
]

# RPC调用函数


def get_len() -> int:
    global flow_queue
    return len(flow_queue)


def get_item(id: int):
    global flow_queue
    return pickle.dumps(flow_queue[id])


def get_items(from_: int, to_: int):
    global flow_queue
    return pickle.dumps(flow_queue[from_:to_:])


def RPC_init():
    server = SimpleXMLRPCServer(('localhost', 8888))
    server.register_function(get_len, "get_len")
    server.register_function(get_item, "get_item")
    server.register_function(get_items, "get_items")
    print("RPC Server Listening for Client.")
    server.serve_forever()


RPC_server = threading.Thread(target=RPC_init)
RPC_server.start()

# open chrome and liqi
chrome_options = Options()
chrome_options.add_argument('--proxy-server=127.0.0.1:8080')
chrome_options.add_argument('--ignore-certificate-errors')
browser = webdriver.Chrome(chrome_options=chrome_options)
#browser.get('https://www.majsoul.com/1/')
