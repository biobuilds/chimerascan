'''
Created on Jun 1, 2012

@author: mkiyer
'''
import os
import sys
import subprocess
import logging

from chimerascan.lib import config
import chimerascan.pipeline

_pipeline_dir = chimerascan.pipeline.__path__[0]

_bowtie2_pe_args = ['--phred33', '--end-to-end', '--very-sensitive', 
                    '--reorder', '--no-mixed', '--no-discordant']

def get_bowtie_library_type(library_type):
    """
    returns the bowtie library type option '--fr' or '--ff' corresponding
    to the first two characters of the library type string
    """
    return library_type[0:2]

def bowtie2_align_transcriptome_pe(transcriptome_index,
                                   genome_index,
                                   transcript_file,                                   
                                   fastq_files,
                                   unaligned_path,
                                   bam_file,
                                   log_file,
                                   library_type,
                                   min_fragment_length=0,
                                   max_fragment_length=1000,
                                   max_transcriptome_hits=1,
                                   num_processors=1):
    """
    align reads to a transcriptome index, convert SAM to BAM,
    and translate alignments to genomic coordinates
    """
    # setup bowtie2 library type param
    library_type_param = get_bowtie_library_type(library_type)
    # setup bowtie2 command line args
    args = [config.BOWTIE2_BIN]
    args.extend(_bowtie2_pe_args)
    args.extend(['-p', num_processors, 
                 '-M', max_transcriptome_hits,
                 '-I', min_fragment_length,
                 '-X', max_fragment_length,
                 '--%s' % library_type_param,
                 '-x', transcriptome_index,
                 '-1', fastq_files[0],
                 '-2', fastq_files[1],
                 '--un-conc', unaligned_path])
    args = map(str, args)
    # kickoff alignment process
    logfh = open(log_file, "w")
    aln_p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=logfh)
    # pipe the bowtie SAM output to a transcriptome to genome conversion
    # script that writes a genomic BAM file
    py_script = os.path.join(_pipeline_dir, "transcriptome_to_genome.py")
    args = [sys.executable, py_script, "--library-type", library_type, 
            "--sam", genome_index, transcript_file, "-", bam_file]
    args = map(str, args)
    logging.debug("Transcriptome to Genome converter args: %s" % 
                  (' '.join(args)))
    convert_p = subprocess.Popen(args, stdin=aln_p.stdout, stderr=logfh)
    # wait for this to finish
    retcode = convert_p.wait()
    if retcode != 0:
        aln_p.terminate()
        return config.JOB_ERROR
    retcode = aln_p.wait()
    if retcode != 0:
        return config.JOB_ERROR        
    logfh.close()
    return retcode

def bowtie2_align_pe(index,
                     fastq_files,
                     unaligned_path,
                     bam_file,
                     log_file,
                     library_type,
                     min_fragment_length=0,
                     max_fragment_length=1000,
                     max_hits=1,
                     num_processors=1):
    # setup bowtie2 library type param
    library_type_param = get_bowtie_library_type(library_type)
    args = [config.BOWTIE2_BIN]
    args.extend(_bowtie2_pe_args)
    args = [config.BOWTIE2_BIN, 
            '-p', num_processors, 
            '-M', max_hits,
            '-I', min_fragment_length,
            '-X', max_fragment_length,
            '--%s' % library_type_param,
            '-x', index,
            '-1', fastq_files[0],
            '-2', fastq_files[1],
            '--un-conc', unaligned_path]
    args = map(str, args)
    # kickoff alignment process
    logfh = open(log_file, "w")
    aln_p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=logfh)
    # pipe the bowtie SAM output to a filter that writes in BAM format
    py_script = os.path.join(_pipeline_dir, "sam_to_bam.py")
    args = [sys.executable, py_script, "-", bam_file] 
    logging.debug("SAM to BAM converter args: %s" % (' '.join(args)))
    sam2bam_p = subprocess.Popen(args, stdin=aln_p.stdout, stderr=logfh)
    # wait for this to finish
    retcode = sam2bam_p.wait()
    if retcode != 0:
        aln_p.terminate()
        return config.JOB_ERROR
    retcode = aln_p.wait()
    if retcode != 0:
        return config.JOB_ERROR        
    logfh.close()
    return retcode

def bowtie2_align_sr(index,
                     fastq_file,
                     bam_file,
                     log_file,
                     library_type,
                     maxhits=1,
                     num_processors=1):
    # align reads
    logfh = open(log_file, "w")
    # setup bowtie2 library type param
    args = [config.BOWTIE2_BIN, 
            '-p', num_processors, '--phred33',
            '--end-to-end', '--very-sensitive', '--reorder',
            '-M', maxhits,
            '-x', index,
            '-U', fastq_file]
    args = map(str, args)
    logging.debug("Alignment args: %s" % (' '.join(args)))
    aln_p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=logfh)
    # pipe the bowtie SAM output to a filter that writes in BAM format
    py_script = os.path.join(_pipeline_dir, "sam_to_bam.py")
    args = [sys.executable, py_script, "-", bam_file] 
    logging.debug("SAM to BAM converter args: %s" % (' '.join(args)))
    sam2bam_p = subprocess.Popen(args, stdin=aln_p.stdout, stderr=logfh)
    # wait for this to finish
    retcode = sam2bam_p.wait()
    if retcode != 0:
        if os.path.exists(bam_file):
            os.remove(bam_file)
        aln_p.terminate()
    else:
        retcode = aln_p.wait()
        if retcode != 0:
            if os.path.exists(bam_file):
                os.remove(bam_file)
    logfh.close()
    return retcode

def parse_fastq(line_iter):
    with line_iter:
        while True:
            lines = [line_iter.next().rstrip() for x in xrange(4)]
            yield lines

def trim_and_merge_fastq(infiles, outfile, segment_length):
    fqiters = [parse_fastq(open(f)) for f in infiles]    
    if outfile == "-":
        outfh = sys.stdout
    else:
        outfh = open(outfile, "w")
    try:
        while True:
            pe_lines = [fqiter.next() for fqiter in fqiters]
            for readnum,lines in enumerate(pe_lines):
                seqlen = len(lines[1])
                if seqlen > segment_length:
                    # encode a '0' or '1' as the first character of the line
                    lines[0] = "@%d%s" % (readnum, lines[0][1:])
                    lines[1] = lines[1][:segment_length]
                    lines[3] = lines[3][:segment_length]
                print >>outfh, '\n'.join(lines)
    except StopIteration:
        pass
    if outfile != "-":
        outfh.close()
    return config.JOB_SUCCESS

def bowtie2_align_pe_sr(index,
                        transcript_file,
                        fastq_files,
                        bam_file,
                        log_file,
                        tmp_dir,
                        segment_length,
                        maxhits=1,
                        max_multihits=1,
                        num_processors=1):
    # create tmp interleaved fastq file
    interleaved_fastq_file = os.path.join(tmp_dir, config.INTERLEAVED_TRIMMED_FASTQ_FILE)
    retcode = trim_and_merge_fastq(fastq_files, 
                                   interleaved_fastq_file, 
                                   segment_length)
    if retcode != config.JOB_SUCCESS:
        if os.path.exists(interleaved_fastq_file):
            os.remove(interleaved_fastq_file)
        return config.JOB_ERROR
    #
    # Align trimmed reads
    #
    logfh = open(log_file, "w")
    # setup bowtie2 library type param
    args = [config.BOWTIE2_BIN, 
            '-p', num_processors, '--phred33',
            '--end-to-end', '--very-sensitive', '--reorder',
            '-k', maxhits,
            '-x', index,
            '-U', interleaved_fastq_file]
    args = map(str, args)
    logging.debug("Alignment args: %s" % (' '.join(args)))
    aln_p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=logfh)
    #
    # Convert to BAM, also extend sequences back to full length by 
    # adding padding to CIGAR string
    #
    py_script = os.path.join(_pipeline_dir, "sam_to_bam_pesr.py")
    args = [sys.executable, py_script, "-", interleaved_fastq_file, "-"] 
    logging.debug("SAM to BAM converter args: %s" % (' '.join(args)))
    sam2bam_p = subprocess.Popen(args, stdin=aln_p.stdout, stdout=subprocess.PIPE, stderr=logfh)
    #
    # Pipe through BAM filter that annotates and filters multihits
    #
    py_script = os.path.join(_pipeline_dir, "filter_transcriptome_multihits.py")    
    args = [sys.executable, py_script, "--max-multihits", max_multihits, 
            transcript_file, "-", bam_file]
    args = map(str,args)
    logging.debug("Multihit filter args: %s" % (' '.join(args)))
    multihit_p = subprocess.Popen(args, stdin=sam2bam_p.stdout, stderr=logfh)
    # wait for this to finish
    retcode = multihit_p.wait()
    if retcode != 0:        
        logging.debug("Error during multihit filtering")
        sam2bam_p.terminate()
        aln_p.terminate()
        return config.JOB_ERROR
    retcode = sam2bam_p.wait()
    if retcode != 0:
        logging.debug("Error during SAM to BAM conversion")
        aln_p.terminate()
        return config.JOB_ERROR
    retcode = aln_p.wait()
    if retcode != 0:
        logging.debug("Error during alignment")
        return config.JOB_ERROR        
    logfh.close()
    return retcode
