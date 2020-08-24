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

set_seed(605)

FULL_ATTRIBUTES = ["personalLess30", "personalLess45", "personalLess60", "personalLarger60", "carryingBackpack",
                   "carryingOther", "lowerBodyCasual", "upperBodyCasual", "lowerBodyFormal", "upperBodyFormal",
                   "accessoryHat", "upperBodyJacket", "lowerBodyJeans", "footwearLeatherShoes", "upperBodyLogo",
                   "hairLong", "personalMale", "carryingMessengerBag", "accessoryMuffler", "accessoryNothing",
                   "carryingNothing", "upperBodyPlaid", "carryingPlasticBags", "footwearSandals", "footwearShoes",
                   "lowerBodyShorts", "upperBodyShortSleeve", "lowerBodyShortSkirt", "footwearSneaker",
                   "upperBodyThinStripes", "accessorySunglasses", "lowerBodyTrousers", "upperBodyTshirt",
                   "upperBodyOther", "upperBodyVNeck", "upperBodyBlack", "upperBodyBlue", "upperBodyBrown",
                   "upperBodyGreen", "upperBodyGrey", "upperBodyOrange", "upperBodyPink", "upperBodyPurple",
                   "upperBodyRed", "upperBodyWhite", "upperBodyYellow", "lowerBodyBlack", "lowerBodyBlue",
                   "lowerBodyBrown", "lowerBodyGreen", "lowerBodyGrey", "lowerBodyOrange", "lowerBodyPink",
                   "lowerBodyPurple", "lowerBodyRed", "lowerBodyWhite", "lowerBodyYellow", "hairBlack", "hairBlue",
                   "hairBrown", "hairGreen", "hairGrey", "hairOrange", "hairPink", "hairPurple", "hairRed",
                   "hairWhite", "hairYellow", "footwearBlack", "footwearBlue", "footwearBrown", "footwearGreen",
                   "footwearGrey", "footwearOrange", "footwearPink", "footwearPurple", "footwearRed", "footwearWhite",
                   "footwearYellow", "accessoryHeadphone", "personalLess15", "carryingBabyBuggy", "hairBald",
                   "footwearBoots", "lowerBodyCapri", "carryingShoppingTro", "carryingUmbrella", "personalFemale",
                   "carryingFolder", "accessoryHairBand", "lowerBodyHotPants", "accessoryKerchief",
                   "lowerBodyLongSkirt", "upperBodyLongSleeve", "lowerBodyPlaid", "lowerBodyThinStripes",
                   "carryingLuggageCase", "upperBodyNoSleeve", "hairShort", "footwearStocking", "upperBodySuit",
                   "carryingSuitcase", "lowerBodySuits", "upperBodySweater", "upperBodyThickStripes", "carryingBlack",
                   "carryingBlue", "carryingBrown", "carryingGreen", "carryingGrey", "carryingOrange", "carryingPink",
                   "carryingPurple", "carryingRed", "carryingWhite", "carryingYellow"]


class AttrRecogModel:
    def __init__(self):
        parser = argument_parser()
        parser.add_argument('--dataset', type=str, default='PETA', choices=['peta', 'rap', 'pa100k'])
        args = parser.parse_args()

        visenv_name = 'PETA'
        exp_dir = os.path.join('trained_weights', visenv_name)
        model_dir, log_dir = get_model_log_path(exp_dir)
        stdout_file = os.path.join(log_dir, f'stdout_{time_str()}.txt')
        save_model_path = os.path.join(model_dir, 'ckpt_max_guofe_2020-08-14_23-13-18.pth')

        if args.redirector:
            print('redirector stdout')
            ReDirectSTD(stdout_file, 'stdout', False)

        pprint.pprint(OrderedDict(args.__dict__))

        print('-' * 60)
        print(f'use GPU{args.device} for training')

        _, predict_tsfm = get_transform(args)

        valid_set = AttrDataset(args=args, split=args.valid_split, transform=predict_tsfm)

        # todo: not to load from .pkl file but from a file containing list of attributes
        args.att_list = valid_set.attr_id

        backbone = resnet50()
        net_parameter = 2048
        classifier = BaseClassifier(netpara=net_parameter, nattr=valid_set.attr_num)
        model = FeatClassifier(backbone, classifier)

        if torch.cuda.is_available():
            model = torch.nn.DataParallel(model).cuda()

        # model.to(torch.device('cpu'))

        ckpt = torch.load(save_model_path)
        model.load_state_dict(ckpt['state_dicts'])
        model.eval()

        from torchsummary import summary
        summary(model, input_size=(3, 256, 256))

        print('Total number of parameters: ', sum(p.numel() for p in model.parameters() if p.requires_grad))

        self.args = args
        self.predict_tsfm = predict_tsfm
        self.model = model

    def predict_image_general(self, input_image_full_path):
        from collections import OrderedDict
        img = Image.open(input_image_full_path)
        img_trans = self.predict_tsfm(img)
        img_trans = torch.unsqueeze(img_trans, dim=0)
        img_var = Variable(img_trans).cuda()
        score = self.model(img_var).data.cpu().numpy()

        # show the score in command line
        result = OrderedDict()
        for idx in range(len(self.args.att_list)):
            orgin_score = score[0, idx]
            sigmoid_score = 1 / (1 + np.exp(-1 * orgin_score))
            # if score[0, idx] >= 0:
            #     print('%s: %.2f' % (cfg.att_list[idx], score[0, idx]))
            # print('%s: %.5f' % (self.args.att_list[idx], sigmoid_score))
            result[self.args.att_list[idx]] = sigmoid_score

        return result