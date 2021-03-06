import torch.nn as nn
from torchvision import models



class ResBase(nn.Module):
    def __init__(self):
        super(ResBase, self).__init__()
        # Initialize pre-trained resnet18
        model_resnet = models.resnet34(pretrained=True)

        # "Steal" pretrained layers from the torchvision pretrained Resnet18
        self.conv1 = model_resnet.conv1
        self.bn1 = model_resnet.bn1
        self.relu = model_resnet.relu
        self.maxpool = model_resnet.maxpool
        self.layer1 = model_resnet.layer1
        self.layer2 = model_resnet.layer2
        self.layer3 = model_resnet.layer3
        self.layer4 = model_resnet.layer4
        self.avgpool = model_resnet.avgpool

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)

        x = self.layer4(x)
        # Non-pooled tensor
        x_p = x
        x = self.avgpool(x)
        # Flatten the pooled tensor
        x = x.flatten(start_dim=1)

        # Return both
        return x, x_p


class ResClassifier(nn.Module):
    def __init__(self, input_dim=1024, class_num=47, dropout_p=0.5):
        super(ResClassifier, self).__init__()
        self.fc1 = nn.Sequential(
            nn.Linear(input_dim, 1000),
            nn.BatchNorm1d(1000, affine=True),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout_p)
        )
        self.fc2 = nn.Linear(1000, class_num)
        self.dropout_p = dropout_p

    def forward(self, x):
        emb = self.fc1(x)
        logit = self.fc2(emb)

        return logit


class RelativeRotationClassifier(nn.Module):
    def __init__(self, input_dim, projection_dim=100, class_num=4):
        super(RelativeRotationClassifier, self).__init__()
        self.input_dim = input_dim
        self.projection_dim = projection_dim

        self.conv_1x1 = nn.Sequential(
            nn.Conv2d(self.input_dim, self.projection_dim, (1, 1), stride=(1, 1)),
            nn.BatchNorm2d(self.projection_dim),
            nn.ReLU(inplace=True)
        )
        self.conv_3x3 = nn.Sequential(
            nn.Conv2d(self.projection_dim, self.projection_dim, (3, 3), stride=(2, 2)),
            nn.BatchNorm2d(self.projection_dim),
            nn.ReLU(inplace=True)
        )
        self.fc1 = nn.Sequential(
            nn.Linear(self.projection_dim * 3 * 3, self.projection_dim),
            nn.BatchNorm1d(self.projection_dim, affine=True),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.5)
        )
        self.fc2 = nn.Linear(projection_dim, class_num)

    def forward(self, x):
        x = self.conv_1x1(x)
        x = self.conv_3x3(x)
        x = x.flatten(start_dim=1)
        x = self.fc1(x)
        x = self.fc2(x)
        return x


class FlippingClassifier(nn.Module):

    def __init__(self, input_dim, class_num=2):
        super(FlippingClassifier,self).__init__()

        self.conv = nn.Sequential()
        self.conv.add_module('conv1_s1',nn.Conv2d(3, 96, kernel_size=11, stride=2, padding=0))
        self.conv.add_module('relu1_s1',nn.ReLU(inplace=True))
        self.conv.add_module('pool1_s1',nn.MaxPool2d(kernel_size=3, stride=2))


        self.conv.add_module('conv2_s1',nn.Conv2d(96, 256, kernel_size=5, padding=2, groups=2))
        self.conv.add_module('relu2_s1',nn.ReLU(inplace=True))
        self.conv.add_module('pool2_s1',nn.MaxPool2d(kernel_size=3, stride=2))


        self.conv.add_module('conv3_s1',nn.Conv2d(256, 384, kernel_size=3, padding=1))
        self.conv.add_module('relu3_s1',nn.ReLU(inplace=True))

        self.conv.add_module('conv4_s1',nn.Conv2d(384, 384, kernel_size=3, padding=1, groups=2))
        self.conv.add_module('relu4_s1',nn.ReLU(inplace=True))

        self.conv.add_module('conv5_s1',nn.Conv2d(384, 256, kernel_size=3, padding=1, groups=2))
        self.conv.add_module('relu5_s1',nn.ReLU(inplace=True))
        self.conv.add_module('pool5_s1',nn.MaxPool2d(kernel_size=3, stride=2))

        self.classifier = nn.Sequential()
        self.classifier.add_module('fc8',nn.Linear(256, class_num))



    def forward(self, x):

        x = self.conv(x)
        x = self.classifier(x)

        return x
