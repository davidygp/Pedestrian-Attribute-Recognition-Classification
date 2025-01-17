import os
import pprint
from collections import OrderedDict

import numpy as np
import torch
from PIL import Image, ImageDraw
from torch.autograd import Variable

from config import argument_parser
from dataset.AttrDataset import AttrDataset, get_transform
from models.base_block import FeatClassifier, BaseClassifier
from models.resnet import resnet50
from tools.function import get_model_log_path
from tools.utils import time_str, ReDirectSTD, set_seed
from models.dpn import dpn68, dpn68b, dpn92, dpn98, dpn131, dpn107

import sys

set_seed(605)


class AttrRecogModel:
    def __init__(self):
        device = torch.device('cpu')
        FORCE_TO_CPU = True
        parser = argument_parser()
        args = parser.parse_args(['PETA', '--model=dpn107'])

        visenv_name = 'PETA'
        exp_dir = os.path.join('exp_result', visenv_name)
        model_dir, log_dir = get_model_log_path(exp_dir, visenv_name)
        stdout_file = os.path.join(log_dir, f'stdout_{time_str()}.txt')
        save_model_path = os.path.join(model_dir, 'ckpt_max_e0384293_2020-09-17_18-35-21.pth')

        if args.redirector:
            print('redirector stdout')
            ReDirectSTD(stdout_file, 'stdout', False)

        pprint.pprint(OrderedDict(args.__dict__))

        print('-' * 60)
        print(f'use GPU{args.device} for training')

        _, predict_tsfm = get_transform(args)

        valid_set = AttrDataset(args=args, split=args.valid_split, transform=predict_tsfm)

        args.att_list = valid_set.attr_id

        backbone = getattr(sys.modules[__name__], args.model)()

        if "dpn68" in args.model:
            net_parameter = 832
        elif "dpn" in args.model:
            net_parameter = 2688
        elif "densenet" in args.model:
            net_parameter = 1024
        else:
            net_parameter = 2048
            
        classifier = BaseClassifier(netpara=net_parameter, nattr=valid_set.attr_num)
        model = FeatClassifier(backbone, classifier)

        if torch.cuda.is_available() and not FORCE_TO_CPU:
            model = torch.nn.DataParallel(model).cuda()
            ckpt = torch.load(save_model_path)
            print(f'Model is served with GPU ')
        else:
            model = torch.nn.DataParallel(model)
            ckpt = torch.load(save_model_path, map_location=torch.device('cpu'))
            print(f'Model is served with CPU ')

        model.load_state_dict(ckpt['state_dicts'])
        model.eval()

        # from torchsummary import summary
        # summary(model, input_size=(3, 256, 192))

        print('Total number of parameters: ', sum(p.numel() for p in model.parameters() if p.requires_grad))

        self.args = args
        self.predict_tsfm = predict_tsfm
        self.model = model

    def predict_image(self, input_image):
        # visenv_name = args.dataset
        # load one image
        path = './static/uploads/'
        output_image = input_image[:-4] + '_predicted.png'
        img = Image.open(path + input_image)
        img_trans = self.predict_tsfm(img)
        img_trans = torch.unsqueeze(img_trans, dim=0)
        img_var = Variable(img_trans).cuda()
        score = self.model(img_var).data.cpu().numpy()

        # show the score in command line
        result = {}
        for idx in range(len(self.args.att_list)):
            orgin_score = score[0, idx]
            sigmoid_score = 1 / (1 + np.exp(-1 * orgin_score))
            # if score[0, idx] >= 0:
            #     print('%s: %.2f' % (cfg.att_list[idx], score[0, idx]))
            print('%s: %.5f' % (self.args.att_list[idx], sigmoid_score))
            result[self.args.att_list[idx]] = sigmoid_score

        # show the score in the image
        img = img.resize(size=(256, 512), resample=Image.BILINEAR)
        draw = ImageDraw.Draw(img)
        positive_cnt = 0
        for idx in range(len(self.args.att_list)):
            if score[0, idx] >= 0:
                orgin_score = score[0, idx]
                sigmoid_score = 1 / (1 + np.exp(-1 * orgin_score))
                # txt = '%s: %.2f' % (cfg.att_list[idx], score[0, idx])
                txt = '%s: %.5f' % (self.args.att_list[idx], sigmoid_score)
                draw.text((10, 10 + 10 * positive_cnt), txt, (255, 0, 0))
                positive_cnt += 1
        # img.save('./static/uploads/00003_predicted.png')
        img.save(path + output_image)

        return result

    def predict_image_general(self, input_image_full_path):
        from collections import OrderedDict
        img = Image.open(input_image_full_path)
        img_trans = self.predict_tsfm(img)
        img_trans = torch.unsqueeze(img_trans, dim=0)
        img_var = Variable(img_trans).cpu()
        score = self.model(img_var).data.cpu().numpy()

        # show the score in command line
        result = OrderedDict()
        for idx in range(len(self.args.att_list)):
            orgin_score = score[0, idx]
            sigmoid_score = 1 / (1 + np.exp(-1 * orgin_score))
            # if score[0, idx] >= 0:
            #     print('%s: %.2f' % (cfg.att_list[idx], score[0, idx]))
            print('%s: %.5f' % (self.args.att_list[idx], sigmoid_score))
            result[self.args.att_list[idx]] = sigmoid_score

        return result
