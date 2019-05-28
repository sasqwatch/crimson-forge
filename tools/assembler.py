#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  tools/asssembler.py
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are
#  met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following disclaimer
#    in the documentation and/or other materials provided with the
#    distribution.
#  * Neither the name of the  nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
#  A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
#  OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
#  SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
#  LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#  OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import argparse
import functools
import os
import sys

relpath = functools.partial(os.path.join, os.path.dirname(os.path.realpath(__file__)), '..')
sys.path.append(relpath())

import crimson_forge
import crimson_forge.cli as cli
import crimson_forge.source as source

import jinja_vanish
import jinja2
import keystone

architectures = cli.architectures

@jinja_vanish.markup_escape_func
def _asm_escape(value):
	if isinstance(value, int):
		return "0x{:x}".format(value)
	return value

def _jinja_assert(value, message):
	if not value:
		raise AssertionError("Jinja assertion '{0}' failed".format(message))
	return ''

def _jinja_bw_or(*values):
	result = 0
	for value in values:
		result |= value
	return result

def _block_api_hash(*args):
	return "0x{:>08x}".format(source.block_api_hash(*args))

def main():
	parser = argparse.ArgumentParser(
		'crimson-forge',
		description="Crimson Forge Assembler v{0}".format(crimson_forge.__version__),
		conflict_handler='resolve',
		formatter_class=argparse.RawTextHelpFormatter,
		fromfile_prefix_chars='@'
	)
	parser.add_argument('-a', '--arch', dest='arch', default='x86', metavar='value', choices=architectures.keys(), help='the architecture')
	parser.add_argument('input', type=argparse.FileType('r'), help='the input file')
	parser.add_argument('output', type=argparse.FileType('wb'), help='the output file')
	args = parser.parse_args()
	printer = crimson_forge.utilities

	arch = architectures[args.arch]
	environment = jinja_vanish.DynAutoEscapeEnvironment(
		autoescape=True,
		escape_func=_asm_escape,
		extensions=['jinja2.ext.do'],
		loader=jinja2.FileSystemLoader([relpath('data', 'stubs')]),
		lstrip_blocks=True,
		trim_blocks=True,
	)
	# functions
	environment.globals['api_hash'] = _block_api_hash
	environment.globals['arch'] = args.arch
	environment.globals['assert'] = _jinja_assert
	environment.globals['bw_or'] = _jinja_bw_or
	environment.globals['raw_bytes'] = source.raw_bytes
	environment.globals['raw_string'] = source.raw_string

	text = args.input.read()
	template = environment.from_string(text)
	text = template.render()
	text = source.remove_comments(text)

	try:
		assembled = bytes(arch.keystone.asm(text, 0x1000)[0])
	except keystone.KsError as error:
		printer.print_error("Error: {}".format(error.message))
		asm_count = error.get_asm_count()
		if asm_count is not None:
			lines = text.split('\n')
			start = max(0, asm_count - 3)
			end = min(len(lines), asm_count + 3)
			for lineno, line in enumerate(lines[start:end], start):
				print(" {: >2} {: >4}: {}".format(('->' if lineno == asm_count else ''), lineno, line))
		return

	args.output.write(assembled)

if __name__ == '__main__':
	main()
