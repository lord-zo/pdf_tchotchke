#!/usr/bin/env python3

# interleave.py
# A script to automatic interleave lines between blocks in a text file
# Written by Lorenzo Van Muñoz
# Last Updated Dec 21 2020

import argparse

from pdf_tchotchke.utils import filenames

def interleave(lines):
    '''
    Read a file with alternating blocks of entries and page numbers and interleave them so that they alternate line by line

    Arguments:
        List : containing strings read in from a pdf's TOC

    Returns:
        List : a permutation of the list elements from the input
    '''

    # identify numerical lines representing page numbers
    num_indices = []
    entry_indices = []
    output_index = 0
    lines = [e.rstrip() for e in lines]   
    for e in lines:
        # if there is an empty line, skip it, reducing the total number of lines in the output by 1 
        if not bool(e):
            continue
        elif e.isdigit():
            num_indices.append(output_index)
        else:
            entry_indices.append(output_index)
        output_index += 1

    output = []
    # perform the permutations (entries alternate with numbers)
    for i,_ in enumerate(lines):
        if i % 2 == 0:
            output.append(lines[entry_indices[int(i/2)]] + "   @" 
                        + lines[num_indices[int(i/2)]] + "\n")
        else:
           continue

    return output


def cli():
    '''
    This handles the command line arguments for interleaving.py
    '''
    
    #define command line arguments
    parser = argparse.ArgumentParser(   
            prog="interleave",
            description='''a script to interleave lines''')

    parser.add_argument(
            "input", type=argparse.FileType('r'),
            help="input file name")
    parser.add_argument(
            "-o", dest="output", 
            help="output file name")

    args = parser.parse_args()  

    print("interleave.py - a script to interleave lines\n")
    
    args = filenames.getSafeArgsOutput(args, ext='.txt', 
                                    overwrite=False, mode='w')

    for line in interleave(args.input.readlines()):
        args.output.write(line)

    args.input.close()
    args.output.close()
    
    print("Lines interleaved")

    return

if __name__ == "__main__":
    cli()
    raise SystemExit()
