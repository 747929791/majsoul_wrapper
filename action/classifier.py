# -*- coding: utf-8 -*-
# Use convolutional neural network to classify tile image
import os

import cv2
from PIL import Image
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as transforms

# CNN输出(int)与牌名(str)的对应关系
classes = {
    0: '1m',
    1: '2m',
    2: '3m',
    3: '4m',
    4: '5m',
    5: '6m',
    6: '7m',
    7: '8m',
    8: '9m',
    9: '1p',
    10: '2p',
    11: '3p',
    12: '4p',
    13: '5p',
    14: '6p',
    15: '7p',
    16: '8p',
    17: '9p',
    18: '1s',
    19: '2s',
    20: '3s',
    21: '4s',
    22: '5s',
    23: '6s',
    24: '7s',
    25: '8s',
    26: '9s',
    27: '1z',
    28: '2z',
    29: '3z',
    30: '4z',
    31: '5z',
    32: '6z',
    33: '7z',
    34: '0m',
    35: '0p',
    36: '0s',
    37: 'back'   # 牌背面
}

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def CV2PIL(img):
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


transform = transforms.Compose([
    transforms.Resize((32, 32)),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))])


class TileNet(nn.Module):
    def __init__(self):
        super(TileNet, self).__init__()
        self.conv1 = nn.Conv2d(3, 10, 5)
        self.pool = nn.MaxPool2d(2, 2)
        self.conv2 = nn.Conv2d(10, 26, 5)
        self.fc1 = nn.Linear(26 * 5 * 5, 300)
        self.fc2 = nn.Linear(300, 124)
        self.fc3 = nn.Linear(124, 38)

    def forward(self, x):
        x = self.pool(F.relu(self.conv1(x)))
        x = self.pool(F.relu(self.conv2(x)))
        x = x.view(-1, 26 * 5 * 5)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x


class Classify:

    def __init__(self):
        self.model = model = TileNet()
        path = os.path.join(os.path.dirname(__file__), 'tile.model')
        self.model.load_state_dict(torch.load(path))
        self.model.to(device)
        self.__call__(np.ones((32, 32, 3), dtype=np.uint8))  # load cache

    def __call__(self, img: np.ndarray):
        img = transform(CV2PIL(img))
        c, n, m = img.shape
        img = img.view(1, c, n, m).to(device)
        with torch.no_grad():
            _, predicted = torch.max(self.model(img), 1)
            TileID = predicted[0]
            TileName = classes[TileID.item()]
        return TileName

