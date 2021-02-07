from PIL import Image


import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

import matplotlib.pyplot as plt


import torchvision.transforms as transforms
from torchvision.utils import save_image
import numpy as np


import copy

imsize = 256

loader = transforms.Compose([
    transforms.Resize(imsize),  # нормируем размер изображения
    transforms.CenterCrop(imsize),
    transforms.ToTensor()])

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
unloader = transforms.ToPILImage()


def image_loader(image_name):
    # image = Image.open(image_name)
    image = loader(image_name).unsqueeze(0)
    return image.to(device, torch.float)


class ContentLoss(nn.Module):

    def __init__(self, target):
        super(ContentLoss, self).__init__()
            # we 'detach' the target content from the tree used
            # to dynamically compute the gradient: this is a stated value,
            # not a variable. Otherwise the forward method of the criterion
            # will throw an error.
        self.target = target.detach()  # это константа. Убираем ее из дерева вычеслений
        self.loss = F.mse_loss(self.target, self.target)  # to initialize with something

    def forward(self, input):
        self.loss = F.mse_loss(input, self.target)
        return input


def gram_matrix(input):
    batch_size, h, w, f_map_num = input.size()  # batch size(=1)
    # b=number of feature maps
    # (h,w)=dimensions of a feature map (N=h*w)

    features = input.view(batch_size * h, w * f_map_num)  # resise F_XL into \hat F_XL

    G = torch.mm(features, features.t())  # compute the gram product

    # we 'normalize' the values of the gram matrix
    # by dividing by the number of element in each feature maps.
    return G.div(batch_size * h * w * f_map_num)


def get_input_optimizer(input_img):
    # this line to show that input is a parameter that requires a gradient
    # добоваляет содержимое тензора катринки в список изменяемых оптимизатором параметров
    optimizer = optim.LBFGS([input_img.requires_grad_()])
    return optimizer


class StyleLoss(nn.Module):
    def __init__(self, target_feature):
        super(StyleLoss, self).__init__()
        self.target = gram_matrix(target_feature).detach()
        self.loss = F.mse_loss(self.target, self.target)  # to initialize with something

    def forward(self, input):
        G = gram_matrix(input)
        self.loss = F.mse_loss(G, self.target)
        return input


cnn_normalization_mean = torch.tensor([0.485, 0.456, 0.406]).to(device)
cnn_normalization_std = torch.tensor([0.229, 0.224, 0.225]).to(device)


class Normalization(nn.Module):
    def __init__(self, mean, std):
        super(Normalization, self).__init__()
        # .view the mean and std to make them [C x 1 x 1] so that they can
        # directly work with image Tensor of shape [B x C x H x W].
        # B is batch size. C is number of channels. H is height and W is width.
        self.mean = torch.tensor(mean).view(-1, 1, 1)
        self.std = torch.tensor(std).view(-1, 1, 1)

    def forward(self, img):
        # normalize img
        return (img - self.mean) / self.std


def imshow(tensor, title=None):
    image = tensor.cpu().clone()
    image = image.squeeze(0)      # функция для отрисовки изображения
    image = unloader(image)
    return image
    # plt.imshow(image)
    # if title is not None:
    #     plt.title(title)
    # plt.pause(0.001)


def imsave(tensor, cnt):
    image = tensor.cpu().clone()
    # image = image.squeeze(0)  # функция для отрисовки изображения
    # image = unloader(image)
    # plt.imsave(image, 'output.png')
    image = image[0]
    save_image(image, f'{cnt}.png')
