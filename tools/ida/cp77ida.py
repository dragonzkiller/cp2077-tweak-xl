# Main scan routine is based on https://github.com/WopsS/RED4ext.SDK/blob/master/scripts/find_patterns.py (c) WopsS

import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple

import ida_bytes
import ida_idaapi
import ida_kernwin
import ida_nalt
import idc


class Item(NamedTuple):
    name: str
    pattern: str
    expected: int = 1
    index: int = 0
    offset: int = 0


class Group(NamedTuple):
    name: str = ""
    pointers: List[Item] = []
    functions: List[Item] = []


class Output(NamedTuple):
    filename: str
    namespace: str
    groups: List[Group]


cached_patterns: Dict[str, List[int]] = dict()


def bin_search(bin_str: str) -> List[int]:
    if not isinstance(bin_str, str):
        raise ValueError('bin_str must be a string')

    if bin_str in cached_patterns:
        return cached_patterns[bin_str]

    bin_list = bin_str.split()
    image = bytearray()
    mask = bytearray()

    # Create the mask and convert '?' to 'CC'.
    for i in range(len(bin_list)):
        byte = bin_list[i]
        if byte == '?':
            image.append(int('CC', 16))
            mask.append(0)
        else:
            image.append(int(byte, 16))
            mask.append(1)

    image = bytes(image)
    mask = bytes(mask)

    start = ida_nalt.get_imagebase()
    end = ida_idaapi.BADADDR

    addrs: List[int] = []

    ea = ida_bytes.bin_search(start, end, image, mask, 0, ida_bytes.BIN_SEARCH_FORWARD)
    while ea != ida_idaapi.BADADDR:
        addrs.append(ea)
        ea = ida_bytes.bin_search(ea + len(image), end, image, mask, 0, ida_bytes.BIN_SEARCH_FORWARD)

    cached_patterns[bin_str] = addrs
    return cached_patterns[bin_str]


def find_pattern(pattern: str, expected: int = 1, index: int = 0) -> int:
    if not isinstance(expected, int):
        raise ValueError('expected must be an integer')

    if not isinstance(index, int):
        raise ValueError('index must be an integer')

    addrs = bin_search(pattern)
    if len(addrs) != expected:
        print(f'Found {len(addrs)} match(es) but {expected} match(es) were expected for pattern "{pattern}"')
        return ida_idaapi.BADADDR

    return addrs[index]


def find_function(pattern: str, expected: int = 1, index: int = 0) -> int:
    return find_pattern(pattern, expected, index)


def find_ptr(pattern: str, expected: int = 1, index: int = 0, offset: int = 0) -> int:
    addr = find_pattern(pattern, expected, index)
    if addr == ida_idaapi.BADADDR:
        return addr

    disp = ida_bytes.get_dword(addr + offset)

    # Real address is: pattern_addr + offset + displacement + size_of_displacement.
    return addr + offset + disp + 4


def scan(patterns: List[Output], output_dir: Path):
    try:
        addr = find_ptr(pattern='4C 8D 05 ? ? ? ? 45 89 BE 20 02 00 00', offset=3)
        if addr == ida_idaapi.BADADDR:
            raise Exception('The pattern for game\'s version is not found')
        version = idc.get_strlit_contents(addr)

        current_date = datetime.today().strftime('%Y-%m-%d')

        for output in patterns:
            output_file = output_dir / Path(output.filename)

            print(f'Processing "{output_file}"...')

            with open(output_file, 'w') as file:
                file.write('// This file is generated. DO NOT MODIFY IT!\n')
                file.write(f'// Created on {current_date} for Cyberpunk 2077 v.{version.decode()}.\n')
                file.write('// Define patterns in "patterns.py" and run "scan.py" to update.\n')
                file.write('\n')
                file.write('#pragma once\n')
                file.write('\n')
                file.write('#include <cstdint>\n')
                file.write('\n')
                file.write(f'namespace {output.namespace}\n')
                file.write('{\n')
                file.write(f'constexpr uintptr_t ImageBase = 0x{ida_nalt.get_imagebase():X};\n')
                file.write('\n')

                groups = output.groups
                groups.sort(key=lambda g: g.name.lower())

                for group in groups:
                    for ptr in group.pointers:
                        addr = find_ptr(pattern=ptr.pattern, expected=ptr.expected, index=ptr.index, offset=ptr.offset)
                        if addr == ida_idaapi.BADADDR:
                            file.write(
                                f'#error Could not find pattern "{ptr.pattern}", expected: {ptr.expected}, index: {ptr.index}, offset: {ptr.offset}\n')
                            continue

                        file.write('constexpr uintptr_t ')

                        if group.name:
                            file.write(f'{group.name}_')

                        if ptr.name:
                            file.write(ptr.name)
                        else:
                            file.write(f'ptr_{addr:X}')

                        file.write(f' = 0x{addr:X} - ImageBase; ')
                        file.write(
                            f'// {ptr.pattern}, expected: {ptr.expected}, index: {ptr.index}, offset: {ptr.offset}\n')

                    for func in group.functions:
                        addr = find_function(pattern=func.pattern, expected=func.expected, index=func.index)
                        if addr == ida_idaapi.BADADDR:
                            file.write(
                                f'#error Could not find pattern "{func.pattern}", expected: {func.expected}, index: {func.index}\n')
                            continue

                        file.write('constexpr uintptr_t ')

                        if group.name:
                            file.write(f'{group.name}_')

                        if func.name:
                            file.write(func.name)
                        else:
                            file.write(f'sub_{addr:X}')

                        file.write(f' = 0x{addr:X} - ImageBase; ')
                        file.write(f'// {func.pattern}, expected: {func.expected}, index: {func.index}\n')

                    if group != groups[-1]:
                        file.write('\n')

                file.write('}\n')

        print('Done!')
        ida_kernwin.beep()

    except:
        traceback.print_exc()
