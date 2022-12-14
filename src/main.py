import argparse
import numpy as np
import os
from PIL import Image
import matplotlib.pyplot as plt

import torch
import torch.nn as nn

from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from torchvision import transforms,datasets

from unet import UNet
from dataset import *
from utils import *



# Parser 생성
parser = argparse.ArgumentParser(description='Train the Unet',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

# parser에 사용할 argument add
parser.add_argument('--lr',default=1e-3,type=float,dest='lr')
parser.add_argument('--batch_size',default=4,type=float,dest='batch_size')
parser.add_argument('--num_epochs',default=100,type=float,dest='num_epoch')

parser.add_argument('--data_dir',default="./datasets",type=str,dest='data_dir')
parser.add_argument('--ckpt_dir',default='./checkpoint',type=str,dest='ckpt_dir')
parser.add_argument('--log_dir',default='./log',type=str,dest='log_dir')
parser.add_argument('--result_dir',default='./result',type=str,dest='result_dir')

parser.add_argument('--mode',default='train',type=str,dest='mode')
parser.add_argument('--train_continue',default='off',type=str, dest='train_continue')


args = parser.parse_args()

## 하이퍼 파라미터 설정
lr = args.lr
batch_size = args.batch_size
num_epoch = args.num_epoch

data_dir = args.data_dir
ckpt_dir = args.ckpt_dir
log_dir = args.log_dir
result_dir = args.result_dir


mode = args.mode
train_continue = args.train_continue

print('lr : %.4e'%lr)
print('batch : %d'% batch_size)

if not os.path.exists(result_dir):
    os.makedirs(os.path.join(result_dir,'png'))
    os.makedirs(os.path.join(result_dir,'numpy'))

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


if mode == 'train':
    transform = transforms.Compose([Normalization(mean=0.5, std=0.5), RandomFlip(), ToTensor()])
    dataset_train = Dataset(data_dir=os.path.join(data_dir,'train'),transform=transform)
    loader_train = DataLoader(dataset_train, batch_size = batch_size, shuffle=True)

    dataset_val = Dataset(data_dir=os.path.join(data_dir,'val'),transform = transform)
    loader_val = DataLoader(dataset_val, batch_size=batch_size , shuffle=True)

    num_train = len(dataset_train)
    num_val = len(dataset_val)

    num_train_for_epoch = np.ceil(num_train/batch_size)
    num_val_for_epoch = np.ceil(num_val/batch_size)
else:
    transform = transforms.Compose([Normalization(mean=0.5, std=0.5), ToTensor()])
    dataset_test = Dataset(data_dir=os.path.join(data_dir, 'test'), transform=transform)

    loader_test = DataLoader(dataset_test, batch_size=batch_size)

    net = UNet().to(device)

    fn_loss = nn.BCEWithLogitsLoss().to(device)
    optim = torch.optim.Adam(net.parameters(), lr=lr)

    num_test = len(dataset_test)
    num_test_for_epoch = np.ceil(num_test / batch_size)

net = UNet().to(device)

fn_loss = nn.BCEWithLogitsLoss().to(device)
optim = torch.optim.Adam(net.parameters(), lr = lr )

fn_tonumpy = lambda x : x.to('cpu').detach().numpy().transpose(0,2,3,1) # device 위에 올라간 텐서를 detach 한 뒤 numpy로 변환
fn_denorm = lambda x, mean, std : (x * std) + mean
fn_classifier = lambda x :  1.0 * (x > 0.5)  # threshold 0.5 기준으로 indicator function으로 classifier 구현

writer_train = SummaryWriter(log_dir=os.path.join(log_dir,'train'))
writer_val = SummaryWriter(log_dir = os.path.join(log_dir,'val'))


start_epoch = 0

## Train mode
if mode == 'train':
    if train_continue == 'on':
        net, optim, start_epoch = load(ckpt_dir=ckpt_dir, net=net, optim=optim)

    for epoch in range(start_epoch + 1, num_epoch + 1):
        net.train()
        loss_arr = []

        for batch, data in enumerate(loader_train):
            # forward
            label = data['label'].to(device)
            inputs = data['input'].to(device)
            output = net(inputs)

            # backward
            optim.zero_grad()
            loss = fn_loss(output, label)
            loss.backward()
            optim.step()

            loss_arr += [loss.item()]

            label = fn_tonumpy(label)
            inputs = fn_tonumpy(fn_denorm(inputs, 0.5, 0.5))
            output = fn_tonumpy(fn_classifier(output))

            writer_train.add_image('label', label, num_train_for_epoch * (epoch - 1) + batch, dataformats='NHWC')
            writer_train.add_image('input', inputs, num_train_for_epoch * (epoch - 1) + batch, dataformats='NHWC')
            writer_train.add_image('output', output, num_train_for_epoch * (epoch - 1) + batch, dataformats='NHWC')

        writer_train.add_scalar('loss', np.mean(loss_arr), epoch)


    # validation
    with torch.no_grad():
        net.eval()
        loss_arr = []

        for batch, data in enumerate(loader_val, 1):
            # forward
            label = data['label'].to(device)
            inputs = data['input'].to(device)
            output = net(inputs)

            # loss
            loss = fn_loss(output, label)
            loss_arr += [loss.item()]
            print('valid : epoch %04d / %04d | Batch %04d \ %04d | Loss %04d' % (
            epoch, num_epoch, batch, num_val_for_epoch, np.mean(loss_arr)))

            # Tensorboard 저장하기
            label = fn_tonumpy(label)
            inputs = fn_tonumpy(fn_denorm(inputs, mean=0.5, std=0.5))
            output = fn_tonumpy(fn_classifier(output))

            writer_val.add_image('label', label, num_val_for_epoch * (epoch - 1) + batch, dataformats='NHWC')
            writer_val.add_image('input', inputs, num_val_for_epoch * (epoch - 1) + batch, dataformats='NHWC')
            writer_val.add_image('output', output, num_val_for_epoch * (epoch - 1) + batch, dataformats='NHWC')

        writer_val.add_scalar('loss', np.mean(loss_arr), epoch)

        # epoch이 끝날때 마다 네트워크 저장
        if epoch % 5 == 0:
            save(ckpt_dir=ckpt_dir, net=net, optim=optim, epoch=epoch)

    writer_train.close()
    writer_val.close()


## Test mode
else:
    net, optim, start_epoch = load(ckpt_dir=ckpt_dir, net=net, optim=optim)

    with torch.no_grad():
        net.eval()
        loss_arr = []

        for batch, data in enumerate(loader_test, 1):
            # forward
            label = data['label'].to(device)
            inputs = data['input'].to(device)
            output = net(inputs)

            # loss
            loss = fn_loss(output, label)
            loss_arr += [loss.item()]
            print('Test : Batch %04d \ %04d | Loss %.4f' % (batch, num_test_for_epoch, np.mean(loss_arr)))

            # output을 numpy와 png 파일로 저장
            label = fn_tonumpy(label)
            inputs = fn_tonumpy(fn_denorm(inputs, mean=0.5, std=0.5))
            output = fn_tonumpy(fn_classifier(output))

            for j in range(label.shape[0]):
                id = num_test_for_epoch * (batch - 1) + j

                plt.imsave(os.path.join(result_dir, 'png', 'label_%04d.png' % id), label[j].squeeze(), cmap='gray')
                plt.imsave(os.path.join(result_dir, 'png', 'inputs_%04d.png' % id), inputs[j].squeeze(), cmap='gray')
                plt.imsave(os.path.join(result_dir, 'png', 'output_%04d.png' % id), output[j].squeeze(), cmap='gray')

                np.save(os.path.join(result_dir, 'numpy', 'label_%04d.np' % id), label[j].squeeze())
                np.save(os.path.join(result_dir, 'numpy', 'inputs_%04d.np' % id), inputs[j].squeeze())
                np.save(os.path.join(result_dir, 'numpy', 'output_%04d.np' % id), output[j].squeeze())

    print('Average Test : Batch %04d \ %04d | Loss %.4f' % (batch, num_test_for_epoch, np.mean(loss_arr)))
