# -*- coding: utf-8 -*-
#Json报文映射到动作回调函数
import re
import time
import inspect
import pickle
import functools
from xmlrpc.client import ServerProxy
from typing import Dict, List, Tuple
from enum import Enum

from .liqi import LiqiProto, MsgType

PRINT_LOG = True  # whether print args when enter handler

# 万桶条(0~10|mps),0为红宝牌；东南西北白发中(z1~z7)
all_tiles = set([str(i)+j for j in ('m', 'p', 's') for i in range(10)] +
                [str(i)+'z' for i in range(1, 8)])


class Operation(Enum):
    Discard = 1
    Chi = 2
    Peng = 3
    MingGang = 5
    JiaGang = 6
    Liqi = 7
    Hu = 9


def dump_args(func):
    #Decorator to print function call details - parameters names and effective values.
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if PRINT_LOG:
            func_args = inspect.signature(func).bind(*args, **kwargs).arguments
            func_args_str = ', '.join('{} = {!r}'.format(*item)
                                      for item in func_args.items())
            func_args_str = re.sub(r' *self.*?=.*?, *', '', func_args_str)
            #print(f'{func.__module__}.{func.__qualname__} ( {func_args_str} )')
            print(f'{func.__name__} ({func_args_str})')
        return func(*args, **kwargs)
    return wrapper


class MajsoulHandler:

    no_effect_method = {
        '.lq.NotifyPlayerLoadGameReady',        # 通知游戏开始
        '.lq.FastTest.checkNetworkDelay',       # 心跳包
        '.lq.FastTest.enterGame',               # 成功进入游戏
        '.lq.FastTest.fetchGamePlayerState',    # 检测所有玩家准备就绪
        '.lq.FastTest.inputOperation',          # 发送出牌操作
        '.lq.FastTest.inputChiPengGang',        # 发送吃碰杠操作
        '.lq.FastTest.confirmNewRound',         # 确认下一轮
        '.lq.PlayerLeaving',                    # 用户离线
        '.lq.FastTest.clearLeaving',            # 用户离线后上线
        '.lq.NotifyGameEndResult',
        '.lq.NotifyGameFinishReward',
        '.lq.NotifyActivityReward',
        '.lq.NotifyLeaderboardPoint',
    }

    no_effect_action = {
        'ActionMJStart',                        # 通知麻将开始
    }

    def parse(self, liqi_dict):
        method = liqi_dict['method']
        if method == '.lq.FastTest.authGame':
            if liqi_dict['type'] == MsgType.Req:
                # 初次进入游戏，请求对局信息
                self.accountId = liqi_dict['data']['accountId']
                return
            if liqi_dict['type'] == MsgType.Res:
                # 初次进入游戏，对局信息回复
                self.seatList = liqi_dict['data']['seatList']
                self.mySeat = self.seatList.index(self.accountId)
                return self.authGame(self.accountId, self.seatList)
        elif method == '.lq.ActionPrototype':
            if 'name' in liqi_dict['data']:
                action_name = liqi_dict['data']['name']
                if action_name in self.no_effect_action:
                    return
                elif action_name == 'ActionNewRound':
                    # 初始手牌
                    data = liqi_dict['data']['data']
                    ju = data.get('ju', 0)
                    ben = data.get('ben', 0)
                    tiles = data['tiles']
                    scores = data['scores']
                    leftTileCount = data.get('leftTileCount', 0)
                    assert(len(data['doras']) == 1)
                    doras = data['doras']
                    return self.newRound(ju, ben, tiles, scores, leftTileCount, doras)
                elif action_name == 'ActionDiscardTile':
                    # 他家出牌
                    data = liqi_dict['data']['data']
                    seat = data.get('seat', 0)
                    tile = data['tile']
                    moqie = data.get('moqie', False)
                    operation = data.get('operation', None)
                    return self.discardTile(seat, tile, moqie, operation)
                elif action_name == 'ActionDealTile':
                    data = liqi_dict['data']['data']
                    seat = data.get('seat', 0)
                    leftTileCount = data.get('leftTileCount', 0)
                    if 'tile' in data:
                        #自家摸牌
                        tile = data['tile']
                        operation = data['operation']
                        return self.iDealTile(seat, tile, leftTileCount, operation)
                    else:
                        # 他家摸牌
                        return self.dealTile(seat, leftTileCount)
                elif action_name == 'ActionChiPengGang':
                    # 吃碰杠
                    data = liqi_dict['data']['data']
                    type_ = data.get('type', 0)
                    seat = data.get('seat', 0)
                    tiles = data['tiles']
                    froms = data['froms']
                    tileStates = data['tileStates']
                    return self.chiPengGang(type_, seat, tiles, froms, tileStates)
        elif method in self.no_effect_method:
            return
        # mismatch
        print('unknown', liqi_dict)

    #-------------------------Majsoul回调函数-------------------------

    @dump_args
    def authGame(self, accountId: int, seatList: List[int]):
        """
        accountId:我的userID
        seatList:所有人的userID(从东家开始顺序)
        """
        assert(len(seatList) == 4)

    @dump_args
    def newRound(self, ju: int, ben: int, tiles: List[str], scores: List[int], leftTileCount: int, doras: List[str]):
        """
        ju:当前第几局(0:东1局,3:东4局，连庄不变，TODO:南)
        TODO:流局立直棒数量(画面左上角一个红点的棒)
        ben:连装棒数量(画面左上角八个黑点的棒)
        tiles:我的初始手牌
        scores:当前场上四个玩家的剩余分数(从东家开始顺序)
        leftTileCount:剩余牌数
        doras:宝牌列表
        """
        assert(len(tiles) in (13, 14) and all(
            tile in all_tiles for tile in tiles))
        assert(leftTileCount == 69)
        assert(all(dora in all_tiles for dora in doras))
        assert(len(doras) == 1)

    @dump_args
    def discardTile(self, seat: int, tile: str, moqie: bool, operation):
        """
        seat:打牌的玩家
        tile:打出的手牌
        moqie:是否是摸切
        operation:可选动作(吃碰杠)
        """

        #discardTile (seat = 2, tile = '3m', operation = {'seat': 3, 'operationList': [{'type': 2, 'combination': ['4m|5m']}, {'type': 3, 'combination': ['3m|3m']}], 'timeFixed': 60000})
        #终盘unknown {'id': 740, 'type': <MsgType.Notify: 1>, 'method': '.lq.ActionPrototype', 'data': {'step': 147, 'name': 'ActionNoTile', 'data': {'players': [{}, {}, {}, {'tingpai': True, 'hand': ['4m', '5m', '4s', '4s'], 'tings': [{'tile': '3m', 'haveyi': True, 'count': 1, 'fu': 30, 'biaoDoraCount': 5, 'countZimo': 1, 'fuZimo': 40}, {'tile': '6m', 'haveyi': True, 'count': 1, 'fu': 30, 'biaoDoraCount': 4, 'countZimo': 1, 'fuZimo': 40}]}], 'scores': [{'oldScores': [25000, 25000, 25000, 25000], 'deltaScores': [-1000, -1000, -1000, 3000]}]}}}
        #我胡了unknown {'id': 1458, 'type': <MsgType.Notify: 1>, 'method': '.lq.ActionPrototype', 'data': {'step': 96, 'name': 'ActionHule', 'data': {'hules': [{'hand': ['0m', '5m', '5m', '8m', '9m', '4p', '5p', '6p', '6s', '6s'], 'ming': ['kezi(7z,7z,7z)'], 'huTile': '7m', 'seat': 3, 'doras': ['9p'], 'count': 2, 'fans': [{'val': 1, 'id': 9}, {'val': 1, 'id': 32}], 'fu': 30, 'pointRong': 2000, 'pointZimoQin': 1000, 'pointZimoXian': 500, 'pointSum': 2000}], 'oldScores': [24000, 24000, 24000, 28000], 'deltaScores': [0, 0, -2300, 2300], 'scores': [24000, 24000, 21700, 30300]}}}
        assert(0 <= seat < 4)
        assert(tile in all_tiles)
        assert(type(operation) == dict or operation == None)

    @dump_args
    def dealTile(self, seat: int, leftTileCount: int):
        """
        seat:摸牌的玩家
        leftTileCount:剩余牌数
        """
        assert(0 <= seat < 4)

    @dump_args
    def iDealTile(self, seat: int, tile: str, leftTileCount: int, operation: Dict):
        """
        seat:我自己
        tile:摸到的牌
        leftTileCount:剩余牌数
        operation:可选操作列表(TODO)
        """
        #iDealTile (seat = 3, tile = '3m', leftTileCount = 25, operation = {'seat': 3, 'operationList': [{'type': 1}, {'type': 6, 'combination': ['3m|3m|3m|3m']}], 'timeFixed': 60000}) 自摸加杠3m
        assert(seat == self.mySeat)
        assert(tile in all_tiles)

    @dump_args
    def chiPengGang(self, type_: int, seat: int, tiles: List[str], froms: List[int], tileStates: List[int]):
        """
        type_:操作类型
        seat:吃碰杠的玩家
        tiles:吃碰杠牌组
        froms:每张牌来自哪个玩家
        tileStates:未知(TODO)
        """
        #{'step': 39, 'name': 'ActionChiPengGang', 'data': {'seat': 3, 'type': 1, 'tiles': ['3m', '3m', '3m'], 'froms': [3, 3, 2], 'operation': {'seat': 3, 'operationList': [{'type': 1, 'combination': ['3m']}], 'timeFixed': 60000}, 'tileStates': [0, 0]}}
        #'data': {'step': 79, 'name': 'ActionChiPengGang', 'data': {'seat': 3, 'tiles': ['3p', '4p', '2p'], 'froms': [3, 3, 2], 'operation': {'seat': 3, 'operationList': [{'type': 1, 'combination': ['2p', '5p']}], 'timeFixed': 60000}, 'tingpais': [{'tile': '8p', 'infos': [{'tile': '3m', 'fu': 30, 'fuZimo': 30}, {'tile': '6m', 'fu': 30, 'fuZimo': 30}]}], 'tileStates': [0, 0]}}
        #'data': {'step': 96, 'name': 'ActionAnGangAddGang', 'data': {'seat': 3, 'type': 2, 'tiles': '3m', 'tingpais': [{'tile': '3m', 'fu': 30, 'fuZimo': 40}, {'tile': '6m', 'fu': 30, 'fuZimo': 40}]}}}
        assert(0 <= seat < 4)
        assert(all(tile in all_tiles for tile in tiles))
        assert(all(0 <= i < 4 for i in froms))
        if type_ == 0:      # 吃
            assert(len(tiles) == 3)
            assert(tiles[0] != tiles[1] != tiles[2])
        elif type_ == 1:    # 碰
            assert(len(tiles) == 3)
            assert(tiles[0] == tiles[1] == tiles[2] or all(
                i[0] in ('0', '5') for i in tiles))
        elif type_ == 2:    # 明杠
            assert(len(tiles) == 4)
            assert(tiles[0] == tiles[1] == tiles[2] == tiles[2] or all(
                i[0] in ('0', '5') for i in tiles))
        else:
            raise NotImplementedError

    #-------------------------Majsoul动作函数-------------------------

    @dump_args
    def actionDiscardTile(self, tile: str):
        """
        tile:要打的手牌
        """
        assert(tile in all_tiles)
        print('discard:', tile)

    @dump_args
    def actionLiqi(self, tile: str):
        """
        tile:立直要打的手牌
        """
        assert(tile in all_tiles)
        print('liqi:', tile)


def dumpWebSocket(handler: MajsoulHandler):
    # 监听mitmproxy当前websocket，将所有报文按顺序交由handler.parse
    server = ServerProxy("http://127.0.0.1:8888")  # 初始化服务器
    liqi = LiqiProto()
    tot = 0
    history_msg = []
    while True:
        n = server.get_len()
        if tot < n:
            flow = pickle.loads(server.get_items(tot, n).data)
            for flow_msg in flow:
                result = liqi.parse(flow_msg)
                handler.parse(result)
                tot += 1
            history_msg = history_msg+flow
            pickle.dump(history_msg, open('websocket_frames.pkl', 'wb'))
        time.sleep(0.2)


def replayWebSocket(handler: MajsoulHandler):
    # 回放历史websocket报文，按顺序交由handler.parse
    history_msg = pickle.load(open('websocket_frames.pkl', 'rb'))
    liqi = LiqiProto()
    for flow_msg in history_msg:
        result = liqi.parse(flow_msg)
        handler.parse(result)


if __name__ == '__main__':
    handler = MajsoulHandler()
    #dumpWebSocket(handler)
    replayWebSocket(handler)
