# -*- coding: utf-8 -*-
#捕获websocket数据并解析雀魂"动作"语义为Json
import time
import json
import struct
import pickle
from xmlrpc.client import ServerProxy
import base64

import proto.liqi_pb2 as pb
from google.protobuf.json_format import MessageToDict

class LiqiProto:
    #解析一局的WS消息队列
    tot = 0  # 当前解析指针
    # (method_name:str,pb.MethodObj) for 256 sliding windows; req->res
    res_type = [None for i in range(256)]
    jsonProto = json.load(open('proto/liqi.json', 'r'))

    def parse(self, flow_msg) -> bool:
        #parse一帧WS flow msg，要求按顺序parse
        buf = flow_msg.content
        from_client = flow_msg.from_client
        result = dict()

        msg_type = ('', 'notify', 'req', 'res')[buf[0]]  # 通信报文类型
        if msg_type == 'notify':
            msg_block = analysis_protobuf(buf[1:])      # 解析剩余报文结构
            method_name = msg_block[0]['data'].decode()
            """
            msg_block结构通常为
            [{'id': 1, 'type': 'string', 'data': b'.lq.ActionPrototype'},
            {'id': 2, 'type': 'string','data': b'protobuf_bytes'}]
            """
            _, lq, message_name = method_name.split('.')
            liqi_pb2_notify = getattr(pb, message_name)
            proto_obj = liqi_pb2_notify.FromString(msg_block[1]['data'])
            dict_obj = MessageToDict(proto_obj)
            if 'data' in dict_obj:
                B = base64.b64decode(dict_obj['data'])
                action_proto_obj = getattr(pb, dict_obj['name']).FromString(B)
                action_dict_obj = MessageToDict(action_proto_obj)
                dict_obj['data'] = action_dict_obj
            msg_id = self.tot
        else:
            msg_id = struct.unpack('<H', buf[1:3])[0]   # 小端序解析报文编号(0~255)
            msg_block = analysis_protobuf(buf[3:])      # 解析剩余报文结构
            """
            msg_block结构通常为
            [{'id': 1, 'type': 'string', 'data': b'.lq.FastTest.authGame'},
            {'id': 2, 'type': 'string','data': b'protobuf_bytes'}]
            """
            if msg_type == 'req':
                assert(msg_id < 256)
                assert(len(msg_block) == 2)
                assert(self.res_type[msg_id] == None)
                method_name = msg_block[0]['data'].decode()
                _, lq, service, rpc = method_name.split('.')
                proto_domain = self.jsonProto['nested'][lq]['nested'][service]['methods'][rpc]
                liqi_pb2_req = getattr(pb, proto_domain['requestType'])
                proto_obj = liqi_pb2_req.FromString(msg_block[1]['data'])
                dict_obj = MessageToDict(proto_obj)
                self.res_type[msg_id] = (method_name, getattr(
                    pb, proto_domain['responseType']))  # wait response
            elif msg_type == 'res':
                assert(len(msg_block[0]['data']) == 0)
                assert(self.res_type[msg_id] != None)
                method_name, liqi_pb2_res = self.res_type[msg_id]
                self.res_type[msg_id] = None
                proto_obj = liqi_pb2_res.FromString(msg_block[1]['data'])
                dict_obj = MessageToDict(proto_obj)
        result = {'id': self.tot, 'type': msg_type,
                  'method': method_name, 'data': dict_obj}
        return result


def analysis_protobuf(buf):
    """
    dump the struct of protobuf,观察报文结构
    buf: protobuf bytes
    """
    def parseVarint(buf, p):
        data = 0
        base = 0
        while(p < len(buf)):
            data += (buf[p] & 127) << base
            base += 7
            p += 1
            if buf[p-1] >> 7 == 0:
                break
        return (data, p)

    p = 0
    result = []
    while(p < len(buf)):
        block_type = (buf[p] & 7)
        block_id = buf[p] >> 3
        p += 1
        if block_type == 0:
            #varint
            block_type = 'varint'
            data, p = parseVarint(buf, p)
        elif block_type == 2:
            #string
            block_type = 'string'
            s_len, p = parseVarint(buf, p)
            data = buf[p:p+s_len]
            p += s_len
        else:
            raise Exception('unknow type:', block_type, ' at', p)
        result.append({'id': block_id, 'type': block_type, 'data': data})
    return result


def dumpWebSocket():
    server = ServerProxy("http://localhost:8888")  # 初始化服务器
    liqi = LiqiProto()
    tot = 0
    history_msg = []
    while True:
        n = server.get_len()
        if tot < n:
            flow = pickle.loads(server.get_items(tot, n).data)
            for flow_msg in flow:
                result = liqi.parse(flow_msg)
                print(result)
                print('-'*65)
                #packet = flow_msg.content
                #from_client = flow_msg.from_client
                #print("[" + ("Sended" if from_client else "Reveived") +
                #      "]: decode the packet here: %r…" % packet)
                tot += 1
            history_msg = history_msg+flow
            pickle.dump(history_msg, open('websocket_frames.pkl', 'wb'))
        time.sleep(0.2)


def replayWebSocket():
    history_msg = pickle.load(open('websocket_frames.pkl', 'rb'))
    liqi = LiqiProto()
    for flow_msg in history_msg:
        result = liqi.parse(flow_msg)
        print(result)
        print('-'*65)


if __name__ == '__main__':
    dumpWebSocket()
    #replayWebSocket()
