from celescope.trust_vdj.__init__ import __ASSAY__
from celescope.tools.multi import Multi


class Multi_trust_vdj(Multi):

    def mapping(self, sample):
        step = 'mapping'
        cmd_line = self.get_cmd_line(step, sample)
        fq = f'{self.outdir_dic[sample]["cutadapt"]}/{sample}_clean_2.fq'
        cmd = (
            f'{cmd_line} '
            f'--fq {fq} '
        )
        self.process_cmd(cmd, step, sample,  m=self.args.starMem, x=self.args.thread)


    def count(self, sample):
        step = 'count'
        cmd_line = self.get_cmd_line(step, sample)
        bam_file = f'{self.outdir_dic[sample]["mapping"]}/{sample}_name_sorted.bam'
        cmd = (
            f'{cmd_line} '
            f'--bam_file {bam_file} '
            f'--match_dir {self.col4_dict[sample]} '
        )
        self.process_cmd(cmd, step, sample, m=5, x=2)


    def assemble(self, sample):
        step = 'assemble'
        cmd_line = self.get_cmd_line(step, sample)
        fq1 = f'{self.outdir_dic[sample]["count"]}/{sample}_mapped_R1.fq'
        fq2 = f'{self.outdir_dic[sample]["count"]}/{sample}_mapped_R2.fq' 
        cmd = (
            f'{cmd_line} '
            f'--fq1 {fq1} '
            f'--fq2 {fq2} '
        )
        self.process_cmd(cmd, step, sample, m=30, x=self.args.thread)

    def res_format(self, sample):
        step = 'res_format'
        cmd_line = self.get_cmd_line(step, sample)
        report = f'{self.outdir_dic[sample]["assemble"]}/{sample}_barcode_report.tsv'
        fa = f'{self.outdir_dic[sample]["assemble"]}/{sample}_annot.fa'
        count_file = f'{self.outdir_dic[sample]["count"]}/count.txt'
        cdr3out = f'{self.outdir_dic[sample]["assemble"]}/{sample}_cdr3.out'
        assign_file = f'{self.outdir_dic[sample]["assemble"]}/{sample}_assign.out'
        cmd = (
            f'{cmd_line} '
            f'--report {report} '
            f'--fa {fa} '
            f'--count_file {count_file} '
            f'--cdr3out {cdr3out} '
            f'--assign_file {assign_file} '
        )
        self.process_cmd(cmd, step, sample, m=5, x=1)


def main():
    multi = Multi_trust_vdj(__ASSAY__)
    multi.run()

if __name__ == '__main__':
    main()