import torchvision.models as models
from side_functions import *
import os


class NST:
    def __init__(self, style, content):
        self.prev_img = [1e10, None]
        self.style_img = image_loader(style)
        self.content_img = image_loader(content)
        self.cnn = models.vgg19(pretrained=True).features.to(device).eval()
        self.content_layers_default = ['conv_4']
        self.style_layers_default = ['conv_1', 'conv_2', 'conv_3', 'conv_4', 'conv_5']
        self.normalization = Normalization(cnn_normalization_mean, cnn_normalization_std).to(device)
        self.model = nn.Sequential(self.normalization)
        self.content_losses = []
        self.style_losses = []

    def get_style_model_and_losses(self) -> None:

        i = 0  # increment every time we see a conv
        for layer in self.cnn.children():
            if isinstance(layer, nn.Conv2d):
                i += 1
                name = 'conv_{}'.format(i)
            elif isinstance(layer, nn.ReLU):
                name = 'relu_{}'.format(i)
                # The in-place version doesn't play very nicely with the ContentLoss
                # and StyleLoss we insert below. So we replace with out-of-place
                # ones here.
                # Переопределим relu уровень
                layer = nn.ReLU(inplace=False)
            elif isinstance(layer, nn.MaxPool2d):
                name = 'pool_{}'.format(i)
            elif isinstance(layer, nn.BatchNorm2d):
                name = 'bn_{}'.format(i)
            else:
                raise RuntimeError('Unrecognized layer: {}'.format(layer.__class__.__name__))

            self.model.add_module(name, layer)

            if name in self.content_layers_default:
                # add content loss:
                target = self.model(self.content_img).detach()
                content_loss = ContentLoss(target)
                self.model.add_module("content_loss_{}".format(i), content_loss)
                self.content_losses.append(content_loss)

            if name in self.content_layers_default:
                # add style loss:
                target_feature_1 = self.model(self.style_img).detach()

                style_loss = StyleLoss(target_feature_1)
                self.model.add_module("style_loss_{}".format(i), style_loss)
                self.style_losses.append(style_loss)

        # now we trim off the layers after the last content and style losses
        # выбрасываем все уровни после последенего styel loss или content loss
        for i in range(len(self.model) - 1, -1, -1):
            if isinstance(self.model[i], ContentLoss) or isinstance(self.model[i], StyleLoss):
                break

        self.model = self.model[:(i + 1)]

    def run_style_transfer(self) -> None:
        num_steps = 500
        style_weight = 100000
        content_weight = 1
        input_img = self.content_img.clone()

        self.get_style_model_and_losses()
        optimizer = get_input_optimizer(input_img)
        run = [0]
        while run[0] <= num_steps:

            def closure():
                # correct the values
                # это для того, чтобы значения тензора картинки не выходили за пределы [0;1]
                input_img.data.clamp_(0, 1)

                optimizer.zero_grad()

                self.model(input_img)

                style_score = 0
                content_score = 0

                for sl in self.style_losses:
                    style_score += sl.loss
                for cl in self.content_losses:
                    content_score += cl.loss

                # взвешивание ощибки
                style_score *= style_weight
                content_score *= content_weight

                loss = style_score + content_score
                loss.backward()

                run[0] += 1
                if style_score.item() + content_score.item() < self.prev_img[0]:
                    self.prev_img[0] = style_score.item() + content_score.item()
                    self.prev_img[1] = input_img.clone()
                # if run[0] % 50 == 0:
                #     print("run {}:".format(run))
                #     print('Style Loss : {:4f} Content Loss: {:4f}'.format(
                #         style_score.item(), content_score.item()))
                #     print()
                    # imsave(input_img, style_score.item() + content_score.item())
                    # imshow(input_img, title='step photo')

                return style_score + content_score

            optimizer.step(closure)

        # a last correction...
        input_img.data.clamp_(0, 1)

        # return input_img

    def compose(self):
        self.run_style_transfer()
        return imshow(self.prev_img[1].data.clamp_(0, 1))



#
# t1 = NST()
# t1.test()
