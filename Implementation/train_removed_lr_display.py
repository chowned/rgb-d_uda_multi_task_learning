#!/usr/bin/env python3
import numpy as np
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from torch.utils.data import DataLoader

from net import ResBase, ResClassifier, RelativeRotationClassifier
from data_loader import DatasetGeneratorMultimodal, MyTransform, INPUT_RESOLUTION
from utils import *
from tqdm import tqdm
import os

os.environ['CUDA_LAUNCH_BLOCKING'] = "1"
# Parse arguments
parser = argparse.ArgumentParser()

add_base_args(parser)
parser.add_argument("--weight_rot", default=1.0, type=float, help="Weight for the rotation loss")
parser.add_argument('--weight_ent', default=0.1, type=float, help="Weight for the entropy loss")
args = parser.parse_args()

# Run name
hp_list = [
    # Task
    'rgbd-rr',
    # Backbone. For these experiments we only use ResNet18
    'resnet18',
    # Number of epochs
    #'ep',
    #args.epochs,
    # Learning rate
    #'lr',
    #args.lr,
    # Learning rate multiplier for the non-pretrained parts of the network
    'lr_m',
    args.lr_mult,
    # Batch size
    'bs',
    args.batch_size,
    # Trade-off weight for the rotation classifier loss
    'wr',
    args.weight_rot,
    # Trade-off weight for the entropy regularization loss
    'we',
    args.weight_ent,
    'wd',
    args.weight_decay

]
if args.suffix is not None:
    hp_list.append(args.suffix)
hp_string = '_'.join(map(str, hp_list))
print(f"Run: {hp_string}")

# Initialize checkpoint path and Tensorboard logger
checkpoint_path = os.path.join(args.logdir, hp_string, 'checkpoint.pth')
writer = SummaryWriter(log_dir=os.path.join(args.logdir, hp_string), flush_secs=5)

# Device. If CUDA is not available (!!!) run on CPU
if not torch.cuda.is_available():
    print("WARNING! CUDA not available")
    device = torch.device('cpu')
else:
    device = torch.device(f'cuda:{args.gpu}')
    # Print device name
    print(f"Running on device {torch.cuda.get_device_name(device)}")

# Center crop, no random flip
test_transform = MyTransform([int((256 - INPUT_RESOLUTION) / 2), int((256 - INPUT_RESOLUTION) / 2)], False)

"""
    Prepare datasets
"""

data_root_source, data_root_target, split_source_train, split_source_test, split_target = make_paths(args.data_root)

# Source: training set
train_set_source = DatasetGeneratorMultimodal(data_root_source, split_source_train, do_rot=False)
# Source: test set
test_set_source = DatasetGeneratorMultimodal(data_root_source, split_source_test, do_rot=False,
                                             transform=test_transform)
# Target: training set (for entropy)
train_set_target = DatasetGeneratorMultimodal(data_root_target, split_target, ds_name='ROD',
                                              do_rot=False)
# Target: test set
test_set_target = DatasetGeneratorMultimodal(data_root_target, split_target, ds_name='ROD', do_rot=False,
                                             transform=test_transform)
# Source: training set (for relative rotation)
rot_set_source = DatasetGeneratorMultimodal(data_root_source, split_source_train, do_rot=True)
# Source: test set (for relative rotation)
rot_test_set_source = DatasetGeneratorMultimodal(data_root_source, split_source_test, do_rot=True)
# Target: training and test set (for relative rotation)
rot_set_target = DatasetGeneratorMultimodal(data_root_target, split_target, ds_name='ROD',
                                            do_rot=True)

"""
    Prepare data loaders
"""

# Source training recognition
train_loader_source = DataLoader(train_set_source,
                                 shuffle=True,
                                 batch_size=args.batch_size,
                                 num_workers=args.num_workers,
                                 drop_last=True)

# Source test recognition
test_loader_source = DataLoader(test_set_source,
                                shuffle=True,
                                batch_size=args.batch_size,
                                num_workers=args.num_workers,
                                drop_last=False)

# Target train
train_loader_target = DataLoader(train_set_target,
                                 shuffle=True,
                                 batch_size=args.batch_size,
                                 num_workers=args.num_workers,
                                 drop_last=True)

# Target test
test_loader_target = DataLoader(test_set_target,
                                shuffle=True,
                                batch_size=args.batch_size,
                                num_workers=args.num_workers,
                                drop_last=False)

# Source rot
rot_source_loader = DataLoader(rot_set_source,
                               shuffle=True,
                               batch_size=args.batch_size,
                               num_workers=args.num_workers,
                               drop_last=True)

rot_test_source_loader = DataLoader(rot_test_set_source,
                                    shuffle=True,
                                    batch_size=args.batch_size,
                                    num_workers=args.num_workers,
                                    drop_last=False)

# Target rot

rot_target_loader = DataLoader(rot_set_target,
                               shuffle=True,
                               batch_size=args.batch_size,
                               num_workers=args.num_workers,
                               drop_last=True)

rot_test_target_loader = DataLoader(rot_set_target,
                                    shuffle=True,
                                    batch_size=args.batch_size,
                                    num_workers=args.num_workers,
                                    drop_last=False)

"""
    Set up network & optimizer
"""
# This needs to be changed if a different backbone is used instead of ResNet18
input_dim_F = 512
# RGB feature extractor based on ResNet18
netG_rgb = ResBase()
# Depth feature extractor based on ResNet18
netG_depth = ResBase()
# Main task: classifier
netF = ResClassifier(input_dim=input_dim_F * 2, class_num=47, dropout_p=args.dropout_p)
netF.apply(weights_init)
# Pretext task: relative rotation classifier
netF_rot = RelativeRotationClassifier(input_dim=input_dim_F * 2, class_num=4)
netF_rot.apply(weights_init)

# Define a list of the networks. Move everything on the GPU
net_list = [netG_rgb, netG_depth, netF, netF_rot]
net_list = map_to_device(device, net_list)

# Classification loss
ce_loss = nn.CrossEntropyLoss()

# Optimizers
opt_g_rgb = optim.SGD(netG_rgb.parameters(), lr=args.lr, momentum=0.9, weight_decay=args.weight_decay)
opt_g_depth = optim.SGD(netG_depth.parameters(), lr=args.lr, momentum=0.9, weight_decay=args.weight_decay)
opt_f = optim.SGD(netF.parameters(), lr=args.lr * args.lr_mult, momentum=0.9, weight_decay=args.weight_decay)
opt_f_rot = optim.SGD(netF_rot.parameters(), lr=args.lr * args.lr_mult, momentum=0.9, weight_decay=args.weight_decay)

optims_list = [opt_g_rgb, opt_g_depth, opt_f, opt_f_rot]

first_epoch = 1
if args.resume:
    first_epoch = load_checkpoint(checkpoint_path, first_epoch, net_list, optims_list)

for epoch in range(first_epoch, args.epochs + 1):
    print("Epoch {} / {}".format(epoch, args.epochs))
    # ========================= TRAINING =========================

    # Train source (recognition)
    train_loader_source_rec_iter = train_loader_source
    # Train target (entropy)
    train_target_loader_iter = IteratorWrapper(train_loader_target)

    # Source (rotation)
    rot_source_loader_iter = IteratorWrapper(rot_source_loader)
    # Target (rotation)
    rot_target_loader_iter = IteratorWrapper(rot_target_loader)

    # Training loop. The tqdm thing is to show progress bar
    with tqdm(total=len(train_loader_source), desc="Train  ") as pb:
        for batch_num, (img_rgb, img_depth, img_label_source) in enumerate(train_loader_source_rec_iter):
            # The optimization step is performed by OptimizerManager
            with OptimizerManager(optims_list):
                # Compute source features
                img_rgb, img_depth, img_label_source = map_to_device(device, (img_rgb, img_depth, img_label_source))
                # TODO
                """
                Here you should compute features for RGB and Depth, concatenate them along the feature dimension
                and then compute the main task logits.

                Then compute the classidication loss.
                """
                feat_rgb, _ = netG_rgb(img_rgb)
                feat_depth, _ = netG_depth(img_depth)
                features_source = torch.cat((feat_rgb, feat_depth), 1)
                logits = netF(features_source)

                # Classification los
                loss_rec = ce_loss(logits, img_label_source)

                # Entropy loss
                if args.weight_ent > 0.:
                    # Load target batch
                    img_rgb, img_depth, _ = train_target_loader_iter.get_next()

                    # TODO
                    """
                    Here you should compute target features for RGB and Depth, concatenate them and compute logits.
                    Then you use the logits to compute the entropy loss.
                    """
                    img_rgb, img_depth = map_to_device(device, (img_rgb, img_depth))
                    feat_rgb, _ = netG_rgb(img_rgb)
                    feat_depth, _ = netG_depth(img_depth)
                    features_target = torch.cat((feat_rgb, feat_depth), 1)
                    logits = netF(features_target)

                    loss_ent = entropy_loss(logits)
                else:
                    loss_ent = 0

                # Backpropagate
                loss = loss_rec + args.weight_ent * loss_ent  # TODO: compute the total loss before backpropagating
                loss.backward()

                del img_rgb, img_depth, img_label_source

                # Relative Rotation
                if args.weight_rot > 0.0:
                    # Load batch: rotation, source
                    img_rgb, img_depth, _, rot_label = rot_source_loader_iter.get_next()

                    # TODO
                    """
                    Here you should compute the features (without pooling!), concatenate them and
                    then compute the rotation classification loss
                    """
                    img_rgb, img_depth, rot_label = map_to_device(device, (img_rgb, img_depth, rot_label))

                    # Compute features (without pooling!)
                    _, pooled_rgb = netG_rgb(img_rgb)
                    _, pooled_depth = netG_depth(img_depth)
                    # Prediction
                    logits_rot = netF_rot(torch.cat((pooled_rgb, pooled_depth), 1))

                    # Classification loss for the rleative rotation task

                    loss_rot = ce_loss(logits_rot, rot_label)  # TODO
                    loss = args.weight_rot * loss_rot # TODO: compute the total loss
                    # Backpropagate
                    loss.backward()

                    loss_rot = loss_rot.item()

                    del img_rgb, img_depth, rot_label, loss

                    # Load batch: rotation, target
                    img_rgb, img_depth, _, rot_label = rot_target_loader_iter.get_next()
                    #added from original code
                    img_rgb, img_depth, rot_label = map_to_device(device, (img_rgb, img_depth, rot_label))

                    # TODO
                    """
                    Same thing, but for target
                    """
                    # Compute features (without pooling!)
                    _, pooled_rgb = netG_rgb(img_rgb)
                    _, pooled_depth = netG_depth(img_depth)
                    # Prediction
                    logits_rot = netF_rot(torch.cat((pooled_rgb, pooled_depth), 1))

                    # Classification loss for the rleative rotation task
                    loss = args.weight_rot * ce_loss(logits_rot, rot_label)
                    # Backpropagate
                    loss.backward()

                    del img_rgb, img_depth, rot_label, loss

                pb.update(1)

    # ========================= VALIDATION =========================

    # Classification - source
    actual_test_batches = min(len(test_loader_source), args.test_batches or len(test_loader_source))
    with EvaluationManager(net_list), tqdm(total=actual_test_batches, desc="TestClS") as pb:
        test_source_loader_iter = iter(test_loader_source)
        correct = 0.0
        num_predictions = 0.0
        val_loss = 0.0

        for num_batch, (img_rgb, img_depth, img_label_source) in enumerate(test_source_loader_iter):
            # By default validate only on 100 batches
            if num_batch >= args.test_batches and args.test_batches > 0:
                break

            # TODO
            """
            Here you should move the batch on GPU, compute the features and then the
            main task prediction
            """
            # Compute source features
            img_rgb, img_depth, img_label_source = map_to_device(device, (img_rgb, img_depth, img_label_source))
            feat_rgb, _ = netG_rgb(img_rgb)
            feat_depth, _ = netG_depth(img_depth)
            features_source = torch.cat((feat_rgb, feat_depth), 1)

            # Compute predictions
            preds = netF(features_source)

            val_loss += ce_loss(preds, img_label_source).item()
            correct += (torch.argmax(preds, dim=1) == img_label_source).sum().item()
            num_predictions += preds.shape[0]


            pb.update(1)

        # TODO: output the accuracy
        val_acc = correct / num_predictions
        val_loss = val_loss / args.test_batches
        print("Epoch: {} - Validation source accuracy (recognition): {}".format(epoch, val_acc))

    del img_rgb, img_depth, img_label_source

    # TODO: log accuracy and loss
    writer.add_scalar("Loss/train", loss_rec.item(), epoch)
    writer.add_scalar("Loss/val", val_loss, epoch)
    writer.add_scalar("Accuracy/val", val_acc, epoch)

    # Relative Rotation
    if args.weight_rot > 0.0:

        # Rotation - source
        cf_matrix = np.zeros((4, 4))
        actual_test_batches = min(len(rot_test_source_loader), args.test_batches or len(rot_test_source_loader))
        with EvaluationManager(net_list), tqdm(total=actual_test_batches, desc="TestRtS") as pb:
            rot_test_source_loader_iter = iter(rot_test_source_loader)
            correct = 0.0
            num_predictions = 0.0
            val_loss = 0.0

            for num_val_batch, (img_rgb, img_depth, _, rot_label) in enumerate(rot_test_source_loader_iter):
                if num_val_batch >= args.test_batches and args.test_batches > 0:
                    break

                # TODO: very similar to the previous part
                img_rgb, img_depth, rot_label = map_to_device(device, (img_rgb, img_depth, rot_label))

                # Compute features (without pooling)
                _, pooled_rgb = netG_rgb(img_rgb)
                _, pooled_depth = netG_depth(img_depth)
                # Compute predictions
                preds = netF_rot(torch.cat((pooled_rgb, pooled_depth), 1))

                val_loss_rot = ce_loss(preds, rot_label).item()
                correct += (torch.argmax(preds, dim=1) == rot_label).sum().item()
                num_predictions += preds.shape[0]

                pb.update(1)

            rot_val_acc = correct/num_predictions
            del img_rgb, img_depth, rot_label

            # TODO
            print("Epoch: {} - Val SRC ROT accuracy:{}".format(epoch, rot_val_acc))

        # Rotation - target
        actual_test_batches = min(len(rot_test_target_loader), args.test_batches or len(rot_test_target_loader))
        with EvaluationManager(net_list), tqdm(total=actual_test_batches, desc="TestRtT") as pb:
            rot_test_target_loader_iter = iter(rot_test_target_loader)
            correct = 0.0
            num_predictions = 0.0
            val_loss = 0.0

            for num_val_batch, (img_rgb, img_depth, _, rot_label) in enumerate(rot_test_target_loader_iter):
                if num_val_batch >= args.test_batches and args.test_batches > 0:
                    break

                # TODO: very similar to the previous part
                img_rgb, img_depth, rot_label = map_to_device(device, (img_rgb, img_depth, rot_label))

                # Compute features (without pooling)
                _, pooled_rgb = netG_rgb(img_rgb)
                _, pooled_depth = netG_depth(img_depth)
                # Compute predictions
                preds = netF_rot(torch.cat((pooled_rgb, pooled_depth), 1))

                val_loss_rot += ce_loss(preds, rot_label).item()
                correct += (torch.argmax(preds, dim=1) == rot_label).sum().item()
                num_predictions += preds.shape[0]



                pb.update(1)

            # TODO
            rot_val_acc = correct/num_predictions
            print("Epoch: {} - Val TRG ROT accuracy:{}".format(epoch, rot_val_acc))

        del img_rgb, img_depth, rot_label

        # TODO
        writer.add_scalar("Loss/rot", loss_rot, epoch)
        writer.add_scalar("Loss/rot_val", val_loss_rot, epoch)
        writer.add_scalar("Accuracy/rot_val", rot_val_acc, epoch)

    # Classification - target
    with EvaluationManager(net_list), tqdm(total=len(test_loader_target), desc="TestClT") as pb:
        # Test target
        correct = 0.0
        num_predictions = 0.0
        val_loss_class_target = 0.0

        for num_batch, (img_rgb, img_depth, img_label_source) in enumerate(test_loader_target):
            if num_batch >= args.test_batches and args.test_batches > 0:
                break
            # Move tensors to GPU
            img_rgb, img_depth, img_label_source = map_to_device(device, (img_rgb, img_depth, img_label_source))
            # Compute features
            feat_rgb, _ = netG_rgb(img_rgb)
            feat_depth, _ = netG_depth(img_depth)
            # Compute predictions
            pred = netF(torch.cat((feat_rgb, feat_depth), 1))
            pred = F.softmax(pred, dim=1)
            correct += (torch.argmax(pred, dim=1) == img_label_source).sum().item()
            num_predictions += img_label_source.shape[0]

            pb.update(1)

        # TODO: Output accuracy
        accuracy = correct / num_predictions

        print("Epoch: {} - Val TRG ROT accuracy:{}".format(epoch, accuracy))

    del img_rgb, img_depth, img_label_source

    # TODO: log loss and accuracy

    #writer.add_scalar("Loss/train_target", loss_rot, epoch)
    #writer.add_scalar("Loss/val_target", val_loss_class_target, epoch)
    writer.add_scalar("Accuracy/val_target", accuracy, epoch)

    # Save checkpoint
    save_checkpoint(checkpoint_path, epoch, net_list, optims_list)
    print("Checkpoint saved")
