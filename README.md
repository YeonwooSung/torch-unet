# PyTorch UNet

My PyTorch implementation of UNet.

## Dataset

First download the dataset from [here](https://imagej.net/events/isbi-2012-segmentation-challenge).

## Training

```bash
python train.py --data_dir /path/to/dataset --mode train --batch_size 4 --num_epochs 100 --lr 0.001 --ckpt_dir /path/to/save/checkpoint --result_dir /path/to/save/result
```

To continue training from checkpoint:

```bash
python train.py --data_dir /path/to/dataset --mode train --batch_size 4 --num_epochs 100 --lr 0.001 --ckpt_dir /path/to/save/checkpoint --result_dir /path/to/save/result --train_continue on
```
