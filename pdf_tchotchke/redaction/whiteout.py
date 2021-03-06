#!/usr/bin/env python3

# whiteout.py
# Author: Lorenzo Van Muñoz
# Last Updated Jan 1, 2021
'''
A script to remove patterns in a file.
Designed with PDFs in mind. 
It reads in a document as a byte string 
and then tries identifying the text in
various encodings.
'''

import os 
import re 
import argparse

import pdftotext

from pdf_tchotchke.utils import filenames 

# Global variables
# Define available encodings of byte-strings with format specification mini-language
INT_ENCODINGS = {
        'c' : (lambda s : b''.join(bytes(f'{e:c}', 'utf-8') for e in s)), #Character unicode (default)
        'X' : (lambda s : b''.join(bytes(f'{e:X}', 'utf-8') for e in s)), #Hex capitalized
        'x' : (lambda s : b''.join(bytes(f'{e:x}', 'utf-8') for e in s)), #Hex uncapitalized
        'd' : (lambda s : b''.join(bytes(f'{e:d}', 'utf-8') for e in s)), #Decimal
        'o' : (lambda s : b''.join(bytes(f'{e:o}', 'utf-8') for e in s)), #Octal
        'b' : (lambda s : b''.join(bytes(f'{e:b}', 'utf-8') for e in s)) #Binary
        }

# Begin text manipulations
def findEnvAndMatchRanges(og_file, text_patterns, formats, beg_env, end_env):
    '''
    Searches for environments (including nested ones) and returns ranges of their indices in the file.
    If any of those environments contains a match with any of the patterns in any of the formats, these ranges are returned separately so they can be deleted.
    Also returns a dictionary with some results about how many matches were made in which formats.
    '''
    
    def searchLine(line, all_patterns, match_results):
        '''
        does the search for a line in all the patterns and documents which did it
        '''
        for j, format_group in enumerate(all_patterns):
            for k, pattern in enumerate(format_group):
                if bool(pattern.search(line)):
                    match_results[formats[j]][text_patterns[k]] += 1
                    return True
        return False

    # remove duplicates
    formats = list(set(formats))
    # these are all the utf-8 and numerically encoded search patterns grouped by format
    beg_pattern = re.compile(beg_env)
    end_pattern = re.compile(end_env)
    # the patterns are read in as strings but they need to be in bytes to match
    # inside the pdfs
    all_patterns = [[re.compile(INT_ENCODINGS[f](p)) 
                        for p in text_patterns] for f in formats ]
    # we can infer the format based on the index of the group of the matched element in this list

    # initialize lists of ranges to return
    matched_envs = []
    unmatched_envs = []
    # initialize dictionary to count all matches made, grouped by format
    match_results = { e : { p : 0 for p in text_patterns} for e in formats }
    # initialize search caches
    beg_env_indices = []
    end_env_indices = []

    for i, line in enumerate(og_file):
        if bool(re.search(beg_pattern, line)):
            beg_env_indices.append([i, False])
        if bool(re.search(end_pattern, line)):
            end_env_indices.append(i)
        if bool(beg_env_indices):
            is_match = searchLine(line, all_patterns, match_results)
            if is_match:
                beg_env_indices[-1][1] = is_match
        if bool(beg_env_indices) and bool(end_env_indices):
            beg_index, beg_bool = beg_env_indices.pop()
            end_index = end_env_indices.pop()
            if beg_bool:
                matched_envs.append(range(  
                        beg_index, end_index+1))
            else:
                unmatched_envs.append(range(    
                        beg_index, end_index+1))
    if bool(beg_env_indices) or bool(end_env_indices):
        print('whiteout.py Warning: Environment beginnings and endings are mismatched: The input file may be damaged')

    return matched_envs, unmatched_envs, match_results


def findPDFMatchesBruteForce(f, text_patterns, env_matches, og_file=None,
        raw=False):
    '''
    This processes the environments which weren't already matched by deleting them from the file, running pdftotext to see the difference with the original, 
    Arguments:
    f: file object in read bytes mode: the pdf to whiteout
    text_patterns: a list of byte strings to whiteout
    env_matches: a list of ranges to test in f
    og_file: f.readlines()
    raw: whether to use pdftotext raw
    '''
    def searchDiff(og_text, new_text, patterns, brute_results):
        '''
        Returns True if a match was found and collect data about which pattern was matched
        Arguments:
        A string of the original text 
        A string of the edited text
        patterns: a list of compiled re patterns from text_patterns (not bytes)
        brute_results: a dictionary like { 'c' : {e:0 for e in text_patterns}}
            where text_patterns are strings that were compiled into patterns
        '''
        # check to see if the new text has at least one fewer instance of the 
        # search pattern
        for i, pattern in enumerate(patterns):
            if len(pattern.findall(og_text)) > len(pattern.findall(new_text)):
                brute_results['c'][text_patterns[i]] += 1
                return True
        return False
    
    # initialize search items
    brute_search_matches = []
    brute_search_unmatched = []
    # initialize data collector
    brute_results = { 'c' : { e : 0  for e in text_patterns } }
    # compile re's as strings (output of pdftotext)
    if raw:
        patterns = [re.compile(''.join(e.decode('utf-8').split())) for e in text_patterns]
    else:
        patterns = [re.compile(e.decode('utf-8')) for e in text_patterns]
    
    # Using pdftotext python library to read text
    # all manipulations are done in memory so hopefull this is quick
    # produce original text
    og_text = pdftotext.PDF(f, raw=raw)
    
    # remove text in each range once, one by one, checking for diffs in each page
    if not og_file:
        f.seek(0)
        og_file = f.readlines()
    tmp_pdf_file = filenames.fileOut(re.sub('.pdf','_tmp_whiteout.pdf',f.name))
    exists_text = re.compile(rb'[\(<].*?[\)>] *?Tj')
    for rng in env_matches:
        with open(tmp_pdf_file, 'w+b') as g:
            # if the rng has no text objects, skip it
            if not exists_text.search(b''.join(og_file[rng.start : rng.stop])):
                brute_search_unmatched.append(rng)
                continue
            g.writelines([replacePDFTextWithSpace(e) 
                            if i in rng else e 
                            for i, e in enumerate(og_file)])
            g.seek(0)
            try:
                tmp_text = pdftotext.PDF(g, raw=raw)
            except pdftotext.Error as e:
                print(f'Warning: pdftotext.Error: {e}')
                brute_search_unmatched.append(rng)
                continue
            try:
                is_match = False
                for i, page in enumerate(og_text):
                    if searchDiff(page, tmp_text[i],
                                    patterns, brute_results):
                        brute_search_matches.append(rng)
                        # Exception case for bad pdfs
                        if b' ' in new_patterns:
                            brute_search_unmatched.append(env)
                            continue 
                        is_match = True
                        new_patterns = []
                        for line in og_file[rng.start : rng.stop]:
                            m = replacePDFTextWithSpace(line, just_match=True)
                            if bool(m):
                                new_patterns.append(m)
                        new_ranges, _, new_results = findEnvAndMatchRanges(
                                og_file, new_patterns, ['c'], 
                                rb'^\d+ \d+ obj', rb'^endobj')
                        [brute_search_matches.append(env_matches.pop(i))
                            for i,r in enumerate(env_matches) if r in new_ranges]
                        brute_results['c'].update(new_results['c'])
                        break
                    else:
                        pass
                if not is_match:
                    brute_search_unmatched.append(rng)
            except BaseException as e:
                print(f'Warning: {e}')
                brute_search_unmatched.append(rng)
    os.remove(tmp_pdf_file)

    return (brute_search_matches, brute_search_unmatched, brute_results)


def replacePDFTextWithSpace(line, count_del=None, just_match=False):
    '''
    This replaces the characters in a string with an equivalent number of spaces
    '''
    p = re.compile(b'^([\(<])(.*)([\)>] *Tj)$')
    m = p.match(line)
    if just_match:
        if bool(m):
            return m.group(2)
        else:
            return None
    elif bool(m):
        # adding b' '*len(re.findall(b'\\\\\\\\', match.group('text'))) because sometimes I've seen lines with multiple backslashes and only these lines need an extra space because otherwise the pdf displays an empty box
        if bool(count_del):
            count_del[0] += 1
        return m.group(1) + b' ' * len(re.findall(b'\\\\\\\\', m.group(2))) \
                + re.sub(b'.', b' ', m.group(2)) + m.group(3) + b'\n'

    else:
        return line


def printSearchDict(results):
    '''
    Prints the search dictionary in an easily readable format
    '''
    # formats are first level and patterns the second but I want to flip this when printing
    for pattern in results['c']:
        data = { e : results[e][pattern] for e in results.keys() }
        total = sum(data.values())
        print(f'Matched {total} times in total with format distribution {data}\n\t{pattern}\n')
    return 

# Begin core functions
def deleteTextFromPDF(pattern_file, input_file, output_file, formats,
        beg_env=rb'^\d+ 0 obj', end_env=rb'^endobj', raw=False, brute_force=False,
        keep_nested=False, verbose=False, show_indices=False):
    '''
    This will whiteout / replace with spaces the search text.
    The default scope for whiting out is a single pdf object at a time.
    This is preferred because the object tends to be the basic unit of text
    on the page and it will DRASTICALLY speed up the brute force option 
    compared to replacing the text environments one by one.
    Arguments:
    patterns: a readable file object (the strings to remove) in string mode
    input_file: a readable file object (the document) in bytes mode
    output_file: a writeable file object (the output) in bytes mode
    formats: A list with strings in whiteout.INT_ENCODINGS.keys()
    beg_env: a string to match the beginning of an environment
    end_env: a string to match the ending of an environment
    brute_force: If true uses pdftotext to search for the text to remove
    keep_nested: Boolean: If True don't delete unmatched envs inside matched ones
    verbose: Boolean: Print some results about deleting
    Show_indices: Boolean: Show the line-numbers being deleted 
    (the bool arguments should be recast with the logging module)
    '''
    # the only types of strings in pdfs are literal and hex strings
    formats = [e for e in ['c','X','x'] if e in formats]
    # get the original text patterns to search, and separately those patterns in all requested encodings
    with pattern_file as p:
        text_patterns = list(set([e.strip() for e in p]))
    with input_file as f:
        og_file = f.readlines()
        search_env_matches, env_matches, search_results = \
                findEnvAndMatchRanges(
                        og_file, text_patterns, formats, 
                        beg_env, end_env)
        all_matched_indices = set()
        [all_matched_indices.update(set(rng)) for rng in search_env_matches]
        all_unmatched_env_indices = set()
        [all_unmatched_env_indices.update(set(rng)) for rng in env_matches]

        if brute_force:
            print(f'Brute Force! {f.name}')
            f.seek(0)
            brute_search_matches, brute_search_unmatched, brute_results =   \
                    findPDFMatchesBruteForce(f, text_patterns, 
                                                env_matches, og_file, raw)
            # add the indices of the new matches
            [all_matched_indices.update(set(rng)) for rng in brute_search_matches]
            # remove the indices of new ranges that were matched
            final_unmatched_envs = set()
            [final_unmatched_envs.update(set(rng)) for rng in brute_search_unmatched]
            all_unmatched_env_indices.intersection(final_unmatched_envs) 
            if show_indices:
                print('Matched ranges:')
                print(brute_search_matches)
                print('Unmatched ranges:')
                print(brute_search_unmatched)

        elif show_indices:
            print('Matched ranges:')
            print(env_matches)
            print('Unmatched ranges:')
            print(search_env_matches)


        # write the final edited pdf
        with output_file as g:
            lines_removed = [0]
            # omit the matched lines when writing
            for i, line in enumerate(og_file):
                if keep_nested:
                    if i in all_matched_indices and i not in all_unmatched_env_indices:
                        g.write(replacePDFTextWithSpace(line,
                            count_del=lines_removed))
                elif i in all_matched_indices:
                    g.write(replacePDFTextWithSpace(line,
                        count_del=lines_removed))
                else:
                    g.write(line)

        if verbose:
            print(f'Generic results: {f.name}')
            printSearchDict(search_results)
            if brute_force:
                print(f'With Brute Force: {f.name}')
                printSearchDict(brute_results)
            print(f'Result: {lines_removed[0]} lines removed')
    return    


def deleteGeneric(pattern_file, input_file, output_file, formats, 
        beg_env, end_env, keep_nested=False, verbose=False, show_indices=False):
    '''
    Find and delete matched environments.
    If there is a matched environment which contains an unmatched nested environment, the default behavior is to delete the whole match
    Arguments:
    patterns: a readable file object (the strings to remove) in string mode
    input_file: a readable file object (the document) in bytes mode
    output_file: a writeable file object (the output) in bytes mode
    formats: A list with strings in whiteout.INT_ENCODINGS.keys()
    beg_env: a string to match the beginning of an environment
    end_env: a string to match the ending of an environment
    keep_nested: Boolean: If True don't delete unmatched envs inside matched ones
    verbose: Boolean: Print some results about deleting
    Show_indices: Boolean: Show the line-numbers being deleted 
    (the bool arguments should be recast with the logging module)
    '''
    with pattern_file as p:
        text_patterns = [e.strip() for e in p]
    with input_file as f:
        search_env_matches, env_matches, search_results = findEnvAndMatchRanges(
                f, text_patterns, formats, beg_env, end_env)

        all_matched_indices = set()
        [all_matched_indices.update(set(rng)) for rng in search_env_matches]
        all_unmatched_env_indices = set()
        [all_unmatched_env_indices.update(set(rng)) for rng in env_matches]

        with output_file as g:
            f.seek(0)
            lines_removed = 0
            for i, line in enumerate(f):
                if keep_nested:
                    if i in all_matched_indices and i not in all_unmatched_env_indices:
                        lines_removed += 1
                        continue
                elif i in all_matched_indices:
                    lines_removed += 1
                    continue
                else:
                    g.write(line)

        if show_indices:
            print('Matched ranges:')
            print(search_env_matches) # all_matched_indices can be overwhelming

        if verbose:
            print(f'Generic results: {f.name}\n{lines_removed} lines removed')
            printSearchDict(search_results)

    return


# begin cli arg handling to core functions
def cli_pdf(args):
    '''
    This function passes the cli args to deleteTextFromPDF
    '''
    deleteTextFromPDF(args.patterns, args.input, args.output, args.format,
            args.beg_env, args.end_env, args.raw, args.brute_force, 
            args.keep_nested, args.verbose, args.show_indices)
    return


def cli_generic(args):
    '''
    This function passes the cli args to deleteGeneric
    '''
    deleteGeneric(args.patterns, args.input, args.output, args.format, 
            args.beg_env, args.end_env,
            args.keep_nested, args.verbose, args.show_indices)
    return


def cli():
    '''
    Setup the command line interface. run 'whiteout -h' for help.
    '''
    parser = argparse.ArgumentParser(   
            prog='whiteout',
            description='''A script to remove patterns in text environments''',    
            epilog='''E.g., in LaTeX, to delete all 'center' environments with 
                the string \LaTeX, call `$whiteout generic patterns.txt 
                input.tex output.tex -b '\\begin{center}' -e '\\end{center}'` 
                where patterns.txt contains the line `\LaTeX`.''')
  
    subparsers = parser.add_subparsers(help='Available actions')
   
    # Setup the generic deleting tool
    parser_generic = subparsers.add_parser('generic',   
            help='delete ascii patterns in any file')
    parser_generic.set_defaults(func=cli_generic)
    
    # Setup the deleteTextFromPDF command
    parser_pdf = subparsers.add_parser(
            'pdf', 
            help='delete text patterns from a pdf, by default ascii')
    parser_pdf.set_defaults(func=cli_pdf)
    parser_pdf.add_argument(
            '-R', dest='raw', action='store_true',
            help='call pdftotext with the raw flag (good if no big images)')
    parser_pdf.add_argument(
            '-B', dest='brute_force', action='store_true',    
            help='For non-ASCII text blocks in a pdf, uses pdftotext to read'
                'its contents, and removes them if they match the patterns')


    # Main arguments
    parser.add_argument(
            'patterns', type=argparse.FileType('rb'), 
            help='enter the name of path of a text file with lines to remove')
    parser.add_argument(
            'input',   
            help='enter the name or path of a pdf')
    parser.add_argument(
            '-o', dest='output',
            help='enter the name or path to write to')
    parser.add_argument(
            '-f', dest='format', 
            default=set('c'), type=(lambda x: list(set(['c'] + [e for e in x]))),
            help='Delete integer encodings of the search pattern. Options \'cxXdob\'.' 
                ' See Python\'s \'Format Specification Mini-Language\'.')
    parser.add_argument(
            '-F', dest='format',
            action='store_const', const=list(INT_ENCODINGS.keys()),
            help='Overrides --format and tries all available formats')
    parser.add_argument(
            '-s', dest='show_indices', action='store_true',  
            help='print all of the matched indices')
    parser.add_argument(
            '-k', dest='keep_nested', action='store_true',   
            help='this changes the default behavior so that nested'
                ' environments which have no matches, but are contained in a'
                ' matched environment, aren\'t removed')
    parser.add_argument('-v', dest='verbose', action='store_true',   
            help='print information about the match results')

    def mybytes(string):
        return bytes(string, 'utf-8')
    parser.add_argument(
            '-b', dest='beg_env',
            type=mybytes, default=rb'^\d+ \d+ obj',
            help='string or python regexp to match the beginning of a text'
                ' block containing the main pattern')
    parser.add_argument(
            '-e', dest='end_env',
            type=mybytes, default=rb'^endobj',
            help='string or python regexp to match the beginning of a text'
                ' block containing the main pattern')
    
    args = parser.parse_args()

    args.input, args.output = filenames.fileIO(args.input, args.output)

    with open(args.input,'rb') as args.input:
        with open(args.output,'wb') as args.output:
            args.func(args)

    return


if __name__ == '__main__':
    cli()
    raise SystemExit()
