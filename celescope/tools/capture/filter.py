import json
from collections import defaultdict

import numpy as np
import pandas as pd

import celescope.tools.utils as utils
from celescope.tools.count import Count
from celescope.tools.step import Step, s_common
import celescope.tools.capture.otsu as otsu
from celescope.__init__ import HELP_DICT


def get_opts_filter(parser, sub_program):

    parser.add_argument('--min_support_reads', help='Minimum number of reads to support a UMI', default=2)

    parser.add_argument(
        "--umi_threshold_method",
        help='method to find UMI threshold',
        choices=['otsu', 'auto', 'hard'],
        default='auto'
    )
    parser.add_argument(
        "--umi_hard_threshold",
        help='int, use together with `--umi_threshold_method hard`',
        default=1,
    )
    if sub_program:
        parser.add_argument('--match_dir', help=HELP_DICT['match_dir'], required=True)
        parser.add_argument('--raw_read_count_file', required=True)
        s_common(parser)


class Filter(Step):
    def __init__(self, args, display_title='Filtering'):
        super().__init__(args, display_title)
        self.umi_threshold_method = args.umi_threshold_method
        self.min_support_reads = int(args.min_support_reads)

        # data
        with open(args.raw_read_count_file) as f:
            self.count_dict = json.load(f)

        self.raw_umi = 0
        self.total_corrected_umi = 0
        self.del_umi = 0
        self.umi_threshold_dict = {}  # if not set explicitly, use 1 as default

        self.barcode_ref_umi_dict = utils.genDict(dim=2)
        self.ref_barcode_umi_dict = utils.genDict(dim=2)

        match_dir_dict = utils.parse_match_dir(args.match_dir)
        self.df_tsne = match_dir_dict['df_tsne']

        self.df_filter_tsne = self.df_tsne.copy()

        # out
        self.otsu_plot = f'{self.out_prefix}_otsu.png'
        self.raw_umi_count_file = f'{self.out_prefix}_corrected_UMI_count.json'
        self.filter_tsne_file = f'{self.out_prefix}_filtered_UMI_tsne.csv'

    @utils.add_log
    def correct_umi(self):
        for barcode in self.count_dict:
            for ref in self.count_dict[barcode]:
                n_corrected_umi, _n_corrected_read = Count.correct_umi(self.count_dict[barcode][ref])
                if self.debug:
                    print(f'{barcode} {ref} {n_corrected_umi}')
                self.total_corrected_umi += n_corrected_umi
                self.raw_umi += len(self.count_dict[barcode][ref])

        self.add_metric(
            name='Number of Raw UMI',
            value=self.raw_umi,
            help_info='number of total raw UMI',
        )

        self.add_metric(
            name='Number of Corrected UMI',
            value=self.total_corrected_umi,
            total=self.raw_umi,
            help_info='correct sequencing errors in the UMI sequences ',
        )

    @utils.add_log
    def filter_read(self):
        for barcode in self.count_dict:
            for ref in self.count_dict[barcode]:
                for umi in self.count_dict[barcode][ref]:
                    read_count = self.count_dict[barcode][ref][umi]
                    if read_count < self.min_support_reads:
                        self.del_umi += 1
                        self.count_dict[barcode][ref][umi] = 0

        self.add_metric(
            name='Minimum Number of Reads to Support a UMI',
            value=self.min_support_reads,
            help_info='filter UMI with less than this number of reads',
        )

        self.add_metric(
            name='Number of Filtered UMI',
            value=self.del_umi,
            total=self.raw_umi,
            help_info='filter UMI according to `min_support_read`',
        )

        if self.debug:
            print(self.count_dict)

    @utils.add_log
    def set_barcode_ref_umi_dict(self):

        for barcode in self.count_dict:
            for ref in self.count_dict[barcode]:
                for umi in self.count_dict[barcode][ref]:
                    if self.count_dict[barcode][ref][umi] > 0:
                        self.barcode_ref_umi_dict[barcode][ref] += 1
        if self.debug:
            print(self.barcode_ref_umi_dict)

    @utils.add_log
    def set_ref_barcode_umi_dict(self):

        for barcode in self.barcode_ref_umi_dict:
            for ref in self.barcode_ref_umi_dict[barcode]:
                self.ref_barcode_umi_dict[ref][barcode] = self.barcode_ref_umi_dict[barcode][ref]

    def get_umi_threshold(self):
        self.add_metric('UMI Threshold Method', self.umi_threshold_method)

        for ref in self.ref_barcode_umi_dict:
            umi_array = list(self.ref_barcode_umi_dict[ref].values())
            if self.umi_threshold_method == 'auto':
                umi_threshold = self.auto_threshold(umi_array)
            elif self.umi_threshold_method == 'otsu':
                umi_threshold = self.otsu_threshold(umi_array)
            elif self.umi_threshold_method == 'hard':
                umi_threshold = self.hard_threshold(umi_array)
            
            umi_threshold = max(1, umi_threshold)
            self.umi_threshold_dict[ref] = umi_threshold
            self.add_metric(f'{ref} UMI Threshold', umi_threshold)

    @staticmethod
    def otsu_threshold(umi_array):
        array = np.log2(umi_array)
        hist = otsu.array2hist(array)
        thresh = otsu.threshold_otsu(hist)
        otsu.makePlot(hist, thresh, self.otsu_plot)

        return int(2 ** thresh)

    @staticmethod
    def auto_threshold(umi_array):
        """
        threhold = 99 percentile of all cell UMIs / 10
        """

        cell_99th = len(umi_array) // 100
        sorted_umis = sorted(umi_array, reverse=True)
        percentile_99_umi = sorted_umis[cell_99th]
        return int(percentile_99_umi / 10)

    def hard_threshold(self):
        return int(self.args.umi_hard_threshold)

    @utils.add_log
    def filter_umi(self):
        for ref in self.ref_barcode_umi_dict:
            for barcode in self.ref_barcode_umi_dict[ref]:
                if self.ref_barcode_umi_dict[ref][barcode] < self.umi_threshold_dict[ref]:
                    self.ref_barcode_umi_dict[ref][barcode] = 0

    @utils.add_log
    def add_umi_write_tsne(self):
        for ref in self.umi_threshold_dict:
            self.df_filter_tsne[ref] = pd.Series(self.ref_barcode_umi_dict[ref])
            self.df_filter_tsne[ref].fillna(0, inplace=True)

        refs = list(self.umi_threshold_dict.keys()) 
        self.df_filter_tsne['sum_UMI'] = self.df_filter_tsne[refs].sum(axis=1)
        self.df_filter_tsne.to_csv(self.filter_tsne_file)


    def add_some_metrics(self):
        df = self.df_filter_tsne

        cell_total = len(df)
        df_positive = df[df['sum_UMI'] > 0]
        n_cell_positive = len(df_positive)
        self.add_metric(
            name='Number of Positive Cells after Filtering',
            value=n_cell_positive,
            total=cell_total,
        )

    def run(self):
        self.correct_umi()
        self.filter_read()
        self.set_barcode_ref_umi_dict()
        self.set_ref_barcode_umi_dict()
        self.get_umi_threshold()
        self.filter_umi()
        self.add_umi_write_tsne()
        self.add_some_metrics()