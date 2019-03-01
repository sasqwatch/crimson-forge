#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  crimson_forge/binfile.py
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

import logging
import os

import archinfo
import lief

logger = logging.getLogger('crimson-forge.binfile')

template_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'templates'))

def _build_pe(pe_binary, shellcode, certificate_table=b''):
	# build and add the .text section
	section_text = lief.PE.Section('.text')
	section_text.characteristics = 0x60000020
	section_text.content = shellcode
	section_text.virtual_address = 0x1000
	pe_binary.add_section(section_text)
	pe_binary.optional_header.addressof_entrypoint = section_text.virtual_address

	# add imports
	# todo: these imports should be user-configurable but default to sane profiles of legitimate functionality (i.e. file operations)
	kernel32 = pe_binary.add_library('kernel32.dll')
	kernel32.add_entry('CloseHandle')
	kernel32.add_entry('ExitProcess')
	user32 = pe_binary.add_library('user32.dll')
	user32.add_entry('MessageBoxA')

	# optionally add the certificate table
	if certificate_table:
		data_directory = pe_binary.data_directories[lief.PE.DATA_DIRECTORY.CERTIFICATE_TABLE]
		last_section = tuple(pe_binary.sections)[-1]
		data_directory.rva = last_section.offset + last_section.size
		data_directory.size = len(certificate_table)

	# build the pe file
	builder = lief.PE.Builder(pe_binary)
	builder.build_imports(True)
	builder.build()
	return bytes(builder.get_build()) + certificate_table

def build_pe_dll_for_shellcode(arch, shellcode):
	if isinstance(arch, archinfo.ArchX86):
		pe_binary = lief.PE.Binary('crimson-forge', lief.PE.PE_TYPE.PE32)
		pe_binary.header.add_characteristic(lief.PE.HEADER_CHARACTERISTICS.DLL)
		pe_binary.optional_header.imagebase = 0x10000000
	elif isinstance(arch, archinfo.ArchAMD64):
		pe_binary = lief.PE.Binary('crimson-forge', lief.PE.PE_TYPE.PE32_PLUS)
		pe_binary.header.add_characteristic(lief.PE.HEADER_CHARACTERISTICS.DLL)
		pe_binary.optional_header.imagebase = 0x180000000
	else:
		raise ValueError('unsupported architecture: ' + repr(arch))
	return _build_pe(pe_binary, shellcode)

def build_pe_exe_for_shellcode(arch, shellcode):
	if isinstance(arch, archinfo.ArchX86):
		pe_binary = lief.PE.Binary('crimson-forge', lief.PE.PE_TYPE.PE32)
		pe_binary.optional_header.imagebase = 0x400000
	elif isinstance(arch, archinfo.ArchAMD64):
		pe_binary = lief.PE.Binary('crimson-forge', lief.PE.PE_TYPE.PE32_PLUS)
		pe_binary.optional_header.imagebase = 0x140000000
	else:
		raise ValueError('unsupported architecture: ' + repr(arch))
	return _build_pe(pe_binary, shellcode)

def patch_pe_with_shellcode(arch, shellcode, template, *args, **kwargs):
	return patch_template_with_shellcode(arch, shellcode, template, '.exe', *args, **kwargs)

def patch_template_with_shellcode(arch, shellcode, template, extension, extra=None):
	patch_points = {'SHELLCODE:': shellcode}
	if extra:
		patch_points.update(extra)
	template_path = os.path.join(template_directory, template + '.' + arch.name.lower() + extension)
	if not os.path.isfile(template_path):
		raise RuntimeError('missing template file: ' + template_path)
	logger.info('Loading template file: ' + template_path)
	with open(template_path, 'rb') as file_h:
		data = file_h.read()
	for point, content in patch_points.items():
		if not isinstance(point, bytes):
			point = point.encode('ascii')
		if not isinstance(content, bytes):
			content = content.encode('ascii')
		offset = data.index(point)
		data = data[:offset] + content + data[offset + len(content):]
	return data
