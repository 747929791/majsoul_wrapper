# -*- coding: utf-8 -*-
# 获取屏幕信息，并通过视觉方法标定手牌与按钮位置，仿真鼠标点击操作输出
import os
import time
from typing import List, Tuple

import cv2
import pyautogui
import numpy as np

from .classifier import classify

pyautogui.PAUSE = 0         # 函数执行后暂停时间
pyautogui.FAILSAFE = True   # 开启鼠标移动到左上角自动退出

DEBUG = False               # 是否显示检测中间结果


def PosTransfer(pos, M: np.ndarray) -> np.ndarray:
    assert(len(pos) == 2)
    return cv2.perspectiveTransform(np.float32([[pos]]), M)[0][0]


def Similarity(img1: np.ndarray, img2: np.ndarray):
    assert(len(img1.shape) == len(img2.shape) == 3)
    if img1.shape[0] < img2.shape[0]:
        img1, img2 = img2, img1
    n, m, c = img2.shape
    img1 = cv2.resize(img1, (m, n))
    if DEBUG:
        cv2.imshow('diff', np.uint8(np.abs(np.float32(img1)-np.float32(img2))))
        cv2.waitKey(1)
    ksize = max(1, min(n, m)//50)
    img1 = cv2.blur(img1, ksize=(ksize, ksize))
    img2 = cv2.blur(img2, ksize=(ksize, ksize))
    img1 = np.float32(img1)
    img2 = np.float32(img2)
    if DEBUG:
        cv2.imshow('bit', np.uint8((np.abs(img1-img2) < 30).sum(2) == 3)*255)
        cv2.waitKey(1)
    return ((np.abs(img1-img2) < 30).sum(2) == 3).sum()/(n*m)


def ObjectLocalization(objImg: np.ndarray, targetImg: np.ndarray) -> np.ndarray:
    """
    https://docs.opencv.org/master/dc/dc3/tutorial_py_matcher.html
    Feature based object detection
    return: Homography matrix M (objImg->targetImg), if not found return None
    """
    img1 = objImg
    img2 = targetImg
    # Initiate ORB detector
    orb = cv2.ORB_create(nfeatures=5000)
    # find the keypoints and descriptors with ORB
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)
    # FLANN parameters
    FLANN_INDEX_LSH = 6
    index_params = dict(algorithm=FLANN_INDEX_LSH,
                        table_number=6,  # 12
                        key_size=12,     # 20
                        multi_probe_level=1)  # 2
    search_params = dict(checks=50)   # or pass empty dictionary
    flann = cv2.FlannBasedMatcher(index_params, search_params)
    matches = flann.knnMatch(des1, des2, k=2)
    # Need to draw only good matches, so create a mask
    matchesMask = [[0, 0] for i in range(len(matches))]
    # store all the good matches as per Lowe's ratio test.
    good = []
    for i, j in enumerate(matches):
        if len(j) == 2:
            m, n = j
            if m.distance < 0.7*n.distance:
                good.append(m)
                matchesMask[i] = [1, 0]
    print('  Number of good matches:', len(good))
    if DEBUG:
        # draw
        draw_params = dict(matchColor=(0, 255, 0),
                           singlePointColor=(255, 0, 0),
                           matchesMask=matchesMask,
                           flags=cv2.DrawMatchesFlags_DEFAULT)
        img3 = cv2.drawMatchesKnn(
            img1, kp1, img2, kp2, matches, None, **draw_params)
        img3 = cv2.pyrDown(img3)
        cv2.imshow('ORB match', img3)
        cv2.waitKey(1)
    # Homography
    MIN_MATCH_COUNT = 100
    if len(good) > MIN_MATCH_COUNT:
        src_pts = np.float32(
            [kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32(
            [kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if DEBUG:
            # draw
            matchesMask = mask.ravel().tolist()
            h, w, d = img1.shape
            pts = np.float32([[0, 0], [0, h-1], [w-1, h-1],
                              [w-1, 0]]).reshape(-1, 1, 2)
            dst = cv2.perspectiveTransform(pts, M)
            img2 = cv2.polylines(img2, [np.int32(dst)],
                                 True, (0, 0, 255), 10, cv2.LINE_AA)
            draw_params = dict(matchColor=(0, 255, 0),  # draw matches in green color
                               singlePointColor=None,
                               matchesMask=matchesMask,  # draw only inliers
                               flags=2)
            img3 = cv2.drawMatches(img1, kp1, img2, kp2,
                                   good, None, **draw_params)
            img3 = cv2.pyrDown(img3)
            cv2.imshow('Homography match', img3)
            cv2.waitKey(1)
    else:
        print("Not enough matches are found - {}/{}".format(len(good), MIN_MATCH_COUNT))
        M = None
    assert(type(M) == type(None) or (
        type(M) == np.ndarray and M.shape == (3, 3)))
    return M


def getHomographyMatrix(img1, img2, threshold=0.0):
    # if similarity>threshold return M
    # else return None
    M = ObjectLocalization(img1, img2)
    if type(M) != type(None):
        print('  Homography Matrix:', M)
        n, m, c = img1.shape
        x0, y0 = np.int32(PosTransfer([0, 0], M))
        x1, y1 = np.int32(PosTransfer([m, n], M))
        sub_img = img2[y0:y1, x0:x1, :]
        S = Similarity(img1, sub_img)
        print('Similarity:', S)
        if S > threshold:
            return M
    return None


def screenShot():
    img = np.asarray(pyautogui.screenshot())
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


class Layout:
    size = (1920, 1080)                                     # 界面长宽
    duanWeiChang = (1348, 321)                              # 段位场按钮
    menuButtons = [(1382, 406), (1382, 573), (1382, 740)]   # 铜/银/金之间按钮
    tileSize = (95, 152)                                     # 自己牌的大小


class GUIInterface:

    def __init__(self):
        self.M = None  # Homography matrix from (1920,1080) to real window
        # load template imgs
        join = os.path.join
        root = os.path.dirname(__file__)
        self.menuImg = cv2.imread(join(root, 'template/menu.png'))     # 初始菜单界面

    def actionDiscardTile(self, tile: str):
        print('in actionDiscardTile')
        L = self._getHandTiles()
        print('actionDiscardTile tile:', tile, ' list:', L)
        for t, (x, y) in L:
            if t == tile:
                pyautogui.moveTo(x=x, y=y)
                time.sleep(0.3)
                pyautogui.click(x=x, y=y, button='left')
                time.sleep(0.1)
                # out of screen
                pyautogui.moveRel(xOffset=0, yOffset=-
                                  Layout.tileSize[1], duration=0.2)
                return True
        raise Exception(
            'GUIInterface.discardTile tile not found. L:', L, 'tile:', tile)
        return False

    def calibrateMenu(self):
        # if the browser is on the initial menu, set self.M and return to True
        # if not return False
        self.M = getHomographyMatrix(self.menuImg, screenShot(), threshold=0.5)
        return type(self.M) != type(None)

    def _getHandTiles(self) -> List[Tuple[str, Tuple[int, int]]]:
        # return a list of my tiles' position
        result = []
        assert(type(self.M) != type(None))
        screen_img = screenShot()
        img = screen_img.copy()     # for calculation
        start = np.int32(PosTransfer([235, 1002], self.M))
        O = PosTransfer([0, 0], self.M)
        colorThreshold = 200
        tileThreshold = np.int32(0.7*(PosTransfer(Layout.tileSize, self.M)-O))
        fail = 0
        maxFail = np.int32(PosTransfer([60, 0], self.M)-O)[0]
        i = 0
        while fail < maxFail:
            x, y = start[0]+i, start[1]
            if all(img[y, x, :] > colorThreshold):
                fail = 0
                img[y, x, :] = colorThreshold
                retval, image, mask, rect = cv2.floodFill(
                    image=img, mask=None, seedPoint=(x, y), newVal=(0, 0, 0),
                    loDiff=(0, 0, 0), upDiff=tuple([255-colorThreshold]*3), flags=cv2.FLOODFILL_FIXED_RANGE)
                x, y, dx, dy = rect
                if dx > tileThreshold[0] and dy > tileThreshold[1]:
                    tile_img = screen_img[y:y+dy, x:x+dx, :]
                    tileStr = classify(tile_img)
                    result.append((tileStr, (x+dx//2, y+dy//2)))
                    i = x+dx-start[0]
            else:
                fail += 1
            i += 1
        return result
