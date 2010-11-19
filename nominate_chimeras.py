'''
Created on Nov 19, 2010

@author: mkiyer
'''
import argparse
import logging
import subprocess
import os
import sys

from config import JOB_SUCCESS, JOB_ERROR

_module_dir = os.path.abspath(os.path.dirname(__file__))

def nominate_chimeras(job_name, bam_file, tmp_dir, output_file,
                      gene_file, bedtools_path):
    pairtobed_bin = "pairToBed"
    if bedtools_path is not None:
        pairtobed_bin = os.path.join(bedtools_path, pairtobed_bin)    
    if not os.path.exists(tmp_dir):
        logging.info("%s: Creating dir %s" % (job_name, tmp_dir))
        os.makedirs(tmp_dir)     
    #
    # Step 1: Extract discordant mate pairs as BEDPE file
    #
    logging.info("%s: Nominate chimeras from BAM file" % (job_name))
    perl_script = os.path.join(_module_dir, "discordant_reads_to_chimeras.pl")
    args = ["perl", perl_script,
            "-b", bam_file,
            "-o", tmp_dir]
    if subprocess.call(args) != JOB_SUCCESS:
        logging.error("%s: Error nominating chimeras" % (job_name))    
        return JOB_ERROR
    prev_output_file = os.path.join(tmp_dir, "split_chimeras.bedpe.txt")
    #
    # Step 2: Compare BEDPE using BEDTools to all genes
    #
    logging.info("%s: Finding overlapping genes" % (job_name))
    args = [pairtobed_bin, "-type", "both", 
            "-a", prev_output_file, "-b", gene_file]
    bedpe_overlap_file = os.path.join(tmp_dir, "chimera_gene_overlap_bedpe.txt" % (job_name))
    f = open(bedpe_overlap_file, "w")
    if subprocess.call(args, stdout=f) != JOB_SUCCESS:
        logging.error("%s: Error finding overlapping genes" % (job_name))    
        return JOB_ERROR
    f.close()
    prev_output_file = bedpe_overlap_file
    #
    # Step 3: Remove unnecessary mate pairs
    #
    logging.info("Removing unnecessary discordant pairs" % (job_name))
    perl_script = os.path.join(_module_dir, "filter_overlapping_chimeras.pl")
    filtered_bedpe_file = os.path.join(tmp_dir, "filtered_overlapping_genes_bedpe.txt" % (job_name))
    args = ["perl", perl_script, "-i", prev_output_file, "-o", filtered_bedpe_file]
    if subprocess.call(args, stdout=f) != JOB_SUCCESS:
        logging.error("%s: Error filtering overlapping genes" % (job_name))    
        return JOB_ERROR
    prev_output_file = filtered_bedpe_file
    #
    # Step 4: Clean up unnecessary files
    #
    # echo "Step 4: Cleaning up intermediate files: ${x} lane ${l}..." 
    # rm /home/chrmaher/CHIMERASCAN_1.0/BEDPE_Overlap_Gene/${x}_${l}_BEDPE_Gene.txt
    #
    # Step 5: Extract chimeras
    #
    logging.info("%s: Extracting chimeras" % (job_name))
    perl_script = os.path.join(_module_dir, "extract_chimera_candidates.pl")
    candidates_dir = os.path.join(tmp_dir, "candidates")
    if not os.path.exists(candidates_dir):
        logging.info("%s: Creating dir %s for chimera candidates" % (job_name, candidates_dir))
        os.makedirs(candidates_dir)
    args = ["perl", perl_script,
            "-i", prev_output_file, 
            "-o", candidates_dir,
            "-u", gene_file]
    f = open(output_file, "w")
    if subprocess.call(args, stdout=f) != JOB_SUCCESS:
        logging.error("%s: Error extracting chimeras" % (job_name))    
        return JOB_ERROR
    f.close()
    return JOB_SUCCESS

def main():
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--bedtools-path", dest="bedtools_path", default=None)
    parser.add_argument("--gene-file", dest="gene_file")
    parser.add_argument("job_name")
    parser.add_argument("bam_file")
    parser.add_argument("tmp_dir")
    parser.add_argument("output_file")
    options = parser.parse_args()
    return nominate_chimeras(options.job_name, options.bam_file, options.tmp_dir,
                             options.output_file,
                             gene_file=options.gene_file,
                             bedtools_path=options.bedtools_path)

if __name__ == '__main__': sys.exit(main()) 

#foreach x ( 30TUEAAXX ) # Flowcell
#     
#    foreach l ( s_3 ) # Lane
#    
#    # Step 1: Extract discordant mate pairs as BEDPE file
#    echo "Step 1: Flowcell ${x} lane ${l} to BEDPE"     
#    perl /home/chrmaher/CHIMERASCAN_1.0/SAM2chimera_vr1.pl -f ${x} -l ${l} -b /exds/projects/chimerascan/lowseq_vcap/discordant_reads.bam -o /home/chrmaher/CHIMERASCAN_1.0/BEDPE/
#    
#    # Step 2: Compare BEDPE using BEDTools to all genes
#    echo "Step 2: BEDPE to find overlappings genes in Flowcell ${x} lane ${l}..."     
#    pairToBed -type both -a /home/chrmaher/CHIMERASCAN_1.0/BEDPE/${x}_${l}_split_chimeras.bedpe.txt -b /home/chrmaher/GENE_FUSION_PIPE_VR3/REFERENCE/UCSC_04_19_2010_hg19.bed > /home/chrmaher/CHIMERASCAN_1.0/BEDPE_Overlap_Gene/${x}_${l}_BEDPE_Gene.txt
#
#        # Step 3: Remove unnecessary mate pairs
#        echo "Step 3: Remove unnecessary discordant pairs from Flowcell ${x} lane ${l}..." 
#        perl /home/chrmaher/CHIMERASCAN_1.0/Filter_BEDPE_4_chimeras.pl -f ${x} -l ${l} -i /home/chrmaher/CHIMERASCAN_1.0/ -o /home/chrmaher/CHIMERASCAN_1.0/FILTERED4GENES_BEDPE/
#
#        # Step 4: Clean up unnecessary files
#          echo "Step 4: Cleaning up intermediate files: ${x} lane ${l}..." 
#    rm /home/chrmaher/CHIMERASCAN_1.0/BEDPE_Overlap_Gene/${x}_${l}_BEDPE_Gene.txt
#
#        # Step 5: Extract chimeras
#       echo "Step 5: Extract chimeras Flowcell ${x} lane ${l}..." 
#        perl /home/chrmaher/CHIMERASCAN_1.0/Extract_Chimera_Candidates_hg19.pl -f ${x} -l ${l} -o /home/chrmaher/CHIMERASCAN_1.0/CANDIDATES/ -i /home/chrmaher/CHIMERASCAN_1.0/FILTERED4GENES_BEDPE/${x}_${l}_filtered_genes_BEDPE.txt > /home/chrmaher/CHIMERASCAN_1.0/CANDIDATES/${x}_${l}_filtered_chimeras.bedpe.txt
#
#   end
#
#end