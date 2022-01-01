"""
Imports Commodore BASIC type-in programs in various magazine formats,
checks for errors, and converts to an executable file for use with an
emulator or on original hardware.
"""

import argparse
from argparse import RawTextHelpFormatter
from os import path, get_terminal_size
import re
import sys
import math

try:
    from debug_tokenize import char_maps
except ImportError:
    import char_maps


def parse_args(argv):
    """Parses command line inputs and generate command line interface and
    documentation.
    """
    parser = argparse.ArgumentParser(description=
        "A tokenizer for Commodore BASIC typein programs. So far, supports \n"
        "Ahoy magazine programs for C64, but more formats to come.",
        formatter_class=RawTextHelpFormatter,
        epilog=
        "Notes for entering programs from Ahoy magazine:\n\n"
        "In addition to the special character codes contained in braces \n"
        "in the magazine, Ahoy also used a shorthand convention for \n"
        "specifying a key entry preceeded by either the Shift key or the \n"
        "Commodore key as follows:\n\n"
        "    - Underlined characters - preceed entry with Shift key\n"
        "    - Overlined characters - preceed entry with Commodore key\n\n"
        "Standard keyboard letters should be typed as follows for these " 
        "two cases.\n"
        "    -{SHIFT-A}, {SHIFT-B}, {SHIFT-*} etc.\n"
        "    -{C=-A}, {C=-B}, {C=-*}, etc.\n\n"
        "There are a few instances where the old hardware has keys not\n"
        "available on a modern keyboard or are otherwise ambiguous.\n"
        "Those should be entered as follows:\n"
        "    {pound} - British Pound symbol\n"
        "    {up_arrow} - up arrow symbol\n"
        "    {left_arrow} - left arrow symbol\n"
        "    {pi} - Pi symbol\n"
        "    {shift-return} - shifted return\n"
        "    {shift-space} - shifted space\n"
        "    {c=-pound} - Commodore-Bristish Pound symbol\n"
        "    {shift-up_arrow} - shifted up arrow symbol\n\n"
    )

    parser.add_argument(
        "-l", "--loadaddr", type=str, nargs=1, required=False,
        metavar="load_address", default=["0x0801"],
        help="Specifies the target BASIC memory address when loading:\n"
             "- 0x0801 - C64 (default)\n"
             "- 0x1001 - VIC20 Unexpanded\n"
             "- 0x0401 - VIC20 +3K\n"
             "- 0x1201 - VIC20 +8K\n"
             "- 0x1201 - VIC20 +16\n"
             "- 0x1201 - VIC20 +24K\n"
    )

    parser.add_argument(
        "-v", "--version", choices=['1', '2', '3', '4', '7'], type=str,
        nargs=1, required=False, metavar="basic_version", default=['2'],
        help="Specifies the BASIC version for use in tokenizing file:\n"
             "- 1 - Basic v1.0  PET\n"
             "- 2 - Basic v2.0  C64/VIC20/PET (default)\n"
             "- 3 - Basic v3.5  C16/C116/Plus/4\n"
             "- 4 - Basic v4.0  PET/CBM2\n"
             "- 7 - Basic v7.0  C128\n"
    )

    parser.add_argument(
        "-s", "--source", choices=["ahoy1", "ahoy2"], type=str, nargs=1,
        required=False, metavar="source_format", default=["ahoy2"],
        help="Specifies the magazine source for conversion and checksum:\n"
             "ahoy1 - Ahoy magazine (Apr-May 1984)\n"
             "ahoy2 - Ahoy magazine (Jun 1984-Apr 1987) (default)\n"
    )

    parser.add_argument(
        "file_in", type=str, metavar="input_file",
        help="Specify the input file name including path\n"
             "Note:  Output files will use input file basename\n"
             "with extensions '.bas' for petcat-ready file and\n"
             "'.prg' for Commodore run file format."
    )

    return parser.parse_args(argv)


def read_file(filename):
    """Opens and reads magazine source, strips whitespace, and
       returns a list of lines converted to lowercase

    Args:
        filename (str): The file name of the magazine source file

    Returns:
        list: a list of strings for each non-blank line from the source file
            converted to lowercase
    """

    with open(filename) as file:
        lines = file.readlines()
        lower_lines = []
        for line in lines:
            # remove any lines with no characters
            if not line.strip():
                continue
            lower_lines.append(line.rstrip().lower())
        return lower_lines


def write_binary(filename, int_list):
    """Write binary file readable on Commodore computers or emulators

    Args:
        filename (str): The file name of the file to write as binary
        int_list (list): List of integers to convert to binary bytes and
            output write to file

    Returns:
        None: implicit return
    """

    with open(filename, "wb") as file:
        for byte in int_list:
            file.write(byte.to_bytes(1, byteorder='big'))


def check_line_number_seq(lines_list):
    """Check each line in the program that either does not start with a line
       number or starts with an out of sequence line number.

    Args:
        lines_list (list): List of lines (str) in program.

    Returns:
        None: implicit return
    """

    line_no = 0;  # handles case where first line does not have a line number
    ln_num_buffer = [0];  # first popped after three line numbers are appended
    for line in lines_list:
        try:
            (line_no, line_str) = split_line_num(line)
            ln_num_buffer.append(line_no)
            if len(ln_num_buffer) < 4:
                continue
            ln_num_buffer.pop(0)

            if not ln_num_buffer[0] <= ln_num_buffer[1] <= ln_num_buffer[2]:
                print("Entry error one or two lines after line "
                      f"{ln_num_buffer[0]} - lines should be in sequential "
                      "order.  Exiting.")
                sys.exit(1)

        except ValueError:
            print(f"Entry error after line {line_no} - each line should start "
                  "with a line number.  Exiting.")
            sys.exit(1)


# convert ahoy special characters to petcat special characters
def ahoy_lines_list(lines_list, char_maps):

    new_lines = []

    for line in lines_list:
        # split each line on ahoy special characters
        str_split = re.split(r"\{.*?\}", line)

        # check for loose braces in each substring, return error indication
        for sub_str in str_split:
            loose_brace = re.search(r"\}|{", sub_str)
            # TODO: Improve loose brace error handling, inconsistent return
            if loose_brace is not None:
                return (None, line)

        # create list of ahoy special character code strings
        code_split = re.findall(r"\{.*?\}", line)

        new_codes = []

        # for each ahoy special character, append the petcat equivalent
        for item in code_split:
            if item.upper() in char_maps.AHOY_TO_PETCAT:
                new_codes.append(char_maps.AHOY_TO_PETCAT[item.upper()])
            else:
                new_codes.append(item)

        # add blank item to list of special characters to aide enumerate
        if new_codes:
            new_codes.append('')

            new_line = []

            # piece the string segments and petcat codes back together
            for count, segment in enumerate(new_codes):
                new_line.append(str_split[count])
                new_line.append(new_codes[count])
        # handle case where line contained no special characters
        else:
            new_line = str_split
        new_lines.append(''.join(new_line))
    return new_lines


def split_line_num(line):
    """Split each line into line number and remaining line text

    Args:
        line (str): Text of each line to split

    Returns:
        tuple consisting of:
            line number (int): Line number split from the beginning of line
            remaining text (str): Text for remainder of line with whitespace
                stripped
    """

    line = line.lstrip()
    acc = []
    while line and line[0].isdigit():
        acc.append(line[0])
        line = line[1:]
    return (int(''.join(acc)), line.lstrip())


# manage the tokenization process for each line text string
def scan_manager(ln):
    in_quotes = False
    in_remark = False
    bytestr = []

    while ln:
        (byte, ln) = scan(ln, char_maps, tokenize=not (in_quotes or in_remark))
        # if byte is not None:
        bytestr.append(byte)
        if byte == ord('"'):
            in_quotes = not in_quotes
        if byte == 143:
            in_remark = True
    bytestr.append(0)
    return bytestr


# scan each line segement and convert to tokenized bytes.
# returns byte and remaining line segment
def scan(ln, char_maps, tokenize=True):
    """Scan beginning of each line for BASIC keywords, petcat special
       characters, or ascii characters, convert to tokenized bytes, and
       return remaining line segment after converted characters are removed

    Args:
        ln (str): Text of each line segment to parse and convert
        tokenize (bool): Flag to indicate if start of line segment should be
            tokenized (False if line segment start is within quotes or after
            a REM statement)

    Returns:
        tuple consisting of:
            character/token value (int): Decimal value of ascii character or
                tokenized word
            remainder of line (str): Text for remainder of line with keyword,
                specical character, or alphanumeric character stripped
    """

    # check if each line passed in starts with a petcat special character
    # if so, return value of token and line with token string removed
    for (token, value) in char_maps.PETCAT_TOKENS:
        if ln.startswith(token):
            return (value, ln[len(token):])
    # check if each line passed in starts with shifted or commodore special
    # character.  if so, return value of token, line with token string removed
    for (token, value) in char_maps.SHIFT_CMDRE_TOKENS:
        if ln.startswith(token):
            return (value, ln[len(token):])
    # if tokenize flag is True (i.e. line beginning is not inside quotes or
    # after a REM statement), check if line starts with a BASIC keyword
    # if so, return value of token and line with BASIC keyword removed
    if tokenize:
        for (token, value) in char_maps.TOKENS_V2:
            if ln.startswith(token):
                return (value, ln[len(token):])
    # for characters without token values, convert to unicode (ascii) value
    # and, for latin letters, shift values by -32 to account for difference
    # between ascii and petscii used by Commodore BASIC
    # finally, return character value and line with character removed
    char_val = ord(ln[0])
    if char_val >= 97 and char_val <= 122:
        char_val -= 32
    return (char_val, ln[1:])


def check_overwrite(filename):
    overwrite = 'y'
    if path.isfile(filename):
        overwrite = input(f'Output file "{filename}" already exists. '
                          'Overwrite? (Y = yes) ')
    if overwrite.lower() == 'y':
        return True
    else:
        print('File not overwritten - exiting.')
        sys.exit(1)


def ahoy1_checksum(byte_list):
    '''
    Function to create Ahoy checksums from passed in byte list to match the
    codes printed in the magazine to check each line for typed in accuracy.
    Covers Ahoy Bug Repellent version for Mar-Apr 1984 issues.
    '''

    next_value = 0

    for char_val in byte_list:
        # Detect spaces that are outside of quotes and ignore them, else
        # execute primary checksum generation algorithm
        if char_val == 32:
            continue
        else:
            next_value = char_val + next_value
            next_value = next_value << 1

    xor_value = next_value
    # get high nibble of xor_value
    high_nib = (xor_value & 0xf0) >> 4
    high_char_val = high_nib + 65  # 0x41
    # get low nibble of xor_value
    low_nib = xor_value & 0x0f
    low_char_val = low_nib + 65  # 0x41
    checksum = chr(high_char_val) + chr(low_char_val)
    return checksum


def ahoy2_checksum(byte_list):
    '''
    Function to create Ahoy checksums from passed in byte list to match the
    codes printed in the magazine to check each line for typed in accuracy.
    Covers Ahoy Bug Repellent version for May 1984-Apr 1987 issues.
    '''

    xor_value = 0
    char_position = 1
    carry_flag = 1
    in_quotes = False

    for char_val in byte_list:

        # set carry flag to zero for char values less than ascii value for
        # quote character since assembly code for repellent sets carry flag
        # based on cmp 0x22 (decimal 34)
        if char_val < 34:
            carry_flag = 0
        else:
            carry_flag = 1

        # Detect quote symbol in line and toggle in-quotes flag
        if char_val == 34:
            in_quotes = not in_quotes

        # Detect spaces that are outside of quotes and ignore them, else
        # execute primary checksum generation algorithm
        if char_val == 32 and in_quotes is False:
            continue
        else:
            next_value = char_val + xor_value + carry_flag

            xor_value = next_value ^ char_position

            # limit next value to fit in one byte
            next_value = next_value & 255

            char_position = char_position + 1

    # get high nibble of xor_value
    high_nib = (xor_value & 0xf0) >> 4
    high_char_val = high_nib + 65  # 0x41
    # get low nibble of xor_value
    low_nib = xor_value & 0x0f
    low_char_val = low_nib + 65  # 0x41
    checksum = chr(high_char_val) + chr(low_char_val)
    return checksum


def print_checksums(ahoy_checksums, terminal_width):

    # Determine number of columns to print based on terminal window width
    columns = int(terminal_width / 12)
    # Determine number of rows based on column count
    rows = math.ceil(len(ahoy_checksums) / columns)

    # Print each line number, code combination in matrix format
    for i in range(rows):
        for j in range(columns):
            indx = i + (j * rows)
            if indx < len(ahoy_checksums):
                prt_line = str(ahoy_checksums[indx][0])
                prt_code = str(ahoy_checksums[indx][1])
                left_space = 7 - len(prt_line) - len(prt_code)
                print(" "*left_space, prt_line, prt_code, " "*2, end='')
        print(end='\n')

    print(f'\nLines: {len(ahoy_checksums)}')


def main(argv=None):

    # call function to parse command line input arguments
    args = parse_args(argv)

    # define load address from input argument
    load_addr = args.loadaddr[0]

    # call function to read input file lines
    try:
        lines_list = read_file(args.file_in)
    except IOError:
        print("File read failed - please check source file name and path.")
        sys.exit(1)

    # check each line to insure each starts with a line number
    check_line_number_seq(lines_list)

    # convert to petcat format and write petcat-ready file
    if args.source[0][:4] == 'ahoy':
        lines_list = ahoy_lines_list(lines_list, char_maps)
        # handle loose brace error returned from ahoy_lines_list()
        if lines_list[0] is None:
            print(f"Loose brace error in line:\n {lines_list[1]}\n"
                  "Special characters should be enclosed in two braces.\n"
                  "Please check for unmatched single braces in above line.")
            sys.exit(1)

    # Write petcat-ready file with extension .bas
    outfile = args.file_in.split('.')[0] + '.bas'

    print('Writing petcat-ready file "' + outfile + '.\n')

    if check_overwrite(outfile):
        with open(outfile, "w") as file:
            for line in lines_list:
                file.write(line + '\n')
        print('\nFile "' + outfile + '" written successfully.\n')

    addr = int(load_addr, 16)

    out_list = []
    ahoy_checksums = []

    for line in lines_list:
        # split each line into line number and remaining text
        (line_num, line_txt) = split_line_num(line)

        token_ln = []
        # add load address at start of first line only
        if addr == int(load_addr, 16):
            token_ln.append(addr.to_bytes(2, 'little'))
        byte_list = scan_manager(line_txt)

        addr = addr + len(byte_list) + 4

        token_ln.append(addr.to_bytes(2, 'little'))
        token_ln.append(line_num.to_bytes(2, 'little'))
        token_ln.append(byte_list)
        token_ln = [byte for sublist in token_ln for byte in sublist]

        # call checksum generator function to build list of tuples
        if args.source[0] == 'ahoy1':
            ahoy_checksums.append((line_num, ahoy1_checksum(byte_list)))
        elif args.source[0] == 'ahoy2':
            ahoy_checksums.append((line_num, ahoy2_checksum(byte_list)))
        else:
            print("Magazine format not yet supported.")
            sys.exit(1)

        out_list.append(token_ln)

    out_list.append([0, 0])

    dec_list = [byte for sublist in out_list for byte in sublist]

    # Write binary file compatible with Commodore computers or emulators

    bin_file = args.file_in.split('.')[0] + '.prg'

    print('Writing binary output file "' + bin_file + '.\n')

    if check_overwrite(bin_file):
        write_binary(bin_file, dec_list)

        print('\nFile "' + bin_file + '" written successfully.\n')

    print_checksums(ahoy_checksums, get_terminal_size()[0])


if __name__ == '__main__':
    sys.exit(main())
