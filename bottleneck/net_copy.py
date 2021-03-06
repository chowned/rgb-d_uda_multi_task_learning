import torch.nn as nn
from torchvision import models
#import pretrainedmodels
from data_loader import INPUT_RESOLUTION


class Resnet18(nn.Module):
    def __init__(self):
        super(Resnet18, self).__init__()
        self.model =  pretrainedmodels.__dict__['resnet18']()



    def forward(self, x):
        batch_size ,_,_,_ = x.shape #taking out batch_size from input image
        x = self.model.features(x)
        x = nn.functional.adaptive_avg_pool2d(x,1).reshape(batch_size,-1) # then reshaping the batch_size
        x = self.classifier_layer(x)
        # Non-pooled tensor
        x_p = x
        #x = self.avgpool(x)
        # Flatten the pooled tensor
        #x = x.flatten(start_dim=1)

        # Return both
        return x, x_p

#convolutional neural network with bottlenech following autoencoder
class Convolutional(nn.Module):
    def __init__(self):
        super(Convolutional, self).__init__()

        # Building an linear encoder with Linear
        # layer followed by Relu activation function
        # INPUT_RESOLUTION ==> 9
        self.encoder = nn.Sequential(
            nn.Linear(INPUT_RESOLUTION, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 36),
            nn.ReLU(),
            nn.Linear(36, 18),
            nn.ReLU(),
            nn.Linear(18, 9)
        )

        # Building an linear decoder with Linear
        # layer followed by Relu activation function
        # The Sigmoid activation function
        # outputs the value between 0 and 1
        # 9 ==> INPUT_RESOLUTION
        self.decoder = nn.Sequential(
            nn.Linear(9, 18),
            nn.ReLU(),
            nn.Linear(18, 36),
            nn.ReLU(),
            nn.Linear(36, 64),
            nn.ReLU(),
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, INPUT_RESOLUTION),
            nn.ReLU(),
            nn.Linear(INPUT_RESOLUTION, 512),
            nn.Sigmoid()
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        # Non-pooled tensor
        x_p = x
        # WHY TF it is not included in the normal implementation of convolutional network?
        convAvgpool = nn.AdaptiveAvgPool1d(3)
        #from original implementation
        x = convAvgpool(x)
        # Flatten the pooled tensor
        x = x.flatten(start_dim=1)

        # Return both
        return x, x_p

class ResBase(nn.Module):
    def __init__(self):
        super(ResBase, self).__init__()
        # Initialize pre-trained resnet34
        model_resnet = models.resnet18(pretrained=True)

        self.classifier_layer = nn.Sequential(
            nn.Linear(512 , 256),
            nn.ReLU(True),

            nn.Linear(256 , 128),
            nn.ReLU(True),

            nn.Linear(128 , 512),
            nn.ReLU(True),

            nn.Linear(512 , 256),
            nn.ReLU(True),

            nn.Linear(512 , 256),
            nn.ReLU(True),
        )


        # "Steal" pretrained layers from the torchvision pretrained Resnet18
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        #self.bn1 = nn.BatchNorm2d(3)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)



        """
        #INPUT_RESOLUTION = 224
        #self.conv9 = nn.Conv2d(in_channels=INPUT_RESOLUTION, out_channels=128, kernel_size=5, stride=1, padding=1)
        #self.bn9 = nn.BatchNorm2d(128)

        #implementing a neuron bottleneck
        #self.conv5 = nn.Conv2d(in_channels=64, out_channels=32, kernel_size=5, stride=1, padding=1)
        #self.bn5 = nn.BatchNorm2d(32)
        #self.conv8 = nn.Conv2d(in_channels=32, out_channels=9, kernel_size=5, stride=1, padding=1)
        #self.bn8 = nn.BatchNorm2d(9)
        #self.conv6 = nn.Conv2d(in_channels=9, out_channels=32, kernel_size=5, stride=1, padding=1)
        #self.bn6 = nn.BatchNorm2d(32)
        #self.conv7 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=5, stride=1, padding=1)
        #self.bn7 = nn.BatchNorm2d(64)

        #self.conv10 = nn.Conv2d(in_channels=128, out_channels=INPUT_RESOLUTION, kernel_size=5, stride=1, padding=1)
        #self.bn10 = nn.BatchNorm2d(INPUT_RESOLUTION)
        """

        self.layer1 = model_resnet.layer1
        self.layer2 = model_resnet.layer2 #after is 128



        self.layer3 = model_resnet.layer3
        self.layer4 = model_resnet.layer4
        self.avgpool = model_resnet.avgpool

    def forward(self, x):



        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)

        x = self.maxpool(x)

        #x = self.custom_layer

        #x = nn.functional.relu(self.bn9(self.conv9(x)))

        #x = nn.functional.relu(self.bn5(self.conv5(x)))
        #added later
        #x = nn.functional.relu(self.bn8(self.conv8(x)))
        #x = nn.functional.relu(self.bn6(self.conv6(x)))
        #x = nn.functional.relu(self.bn7(self.conv7(x)))

        #x = nn.functional.relu(self.bn10(self.conv10(x)))

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.custom_layer(x)
        x = self.layer3(x)
        x = self.layer4(x)
        # Non-pooled tensor
        x_p = x
        x = self.avgpool(x)
        # Flatten the pooled tensor
        x = x.flatten(start_dim=1)

        # Return both
        return x, x_p

class AUTOENCODER(nn.Module):
    def __init__(self):
        super(AUTOENCODER,self).__init__()

        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        #self.bn1 = nn.BatchNorm2d(3)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)





        self.encoder = nn.Sequential(
        nn.Conv2d(64, 32, 3, stride=3, padding=1),
        nn.ReLU(True),
        nn.MaxPool2d(2, stride=2),
        nn.Conv2d(32, 16, 3, stride=2, padding=1),
        nn.ReLU(True),
        nn.MaxPool2d(2, stride=1),
        nn.Conv2d(16, 8, 3, stride=3, padding=1),
        nn.ReLU(True),
        nn.MaxPool2d(2, stride=2),
        )
        self.decoder = nn.Sequential(
       nn.ConvTranspose2d(8, 16, 3, stride=2),
       nn.ReLU(True),
       nn.ConvTranspose2d(16, 32, 5, stride=3, padding=1),
       nn.ReLU(True),
       nn.ConvTranspose2d(32, 256, 2, stride=2, padding=1),
       nn.Tanh()
        )

        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))




    def forward(self,x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)


        x = self.encoder(x)
        x = self.decoder(x)
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
            nn.Linear(self.projection_dim * 1 * 4, self.projection_dim),
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
