#!/usr/bin/env python

# command_line reads is a command line to load a  CK2 saved game into a database.

# Copyright (C) 2016  Jamil Navarro <jamilnavarro@gmail.com>

# This file is part of CK2_Parser.

# CK2_Parser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# CK2_Parser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with CK2_Parser.  If not, see <http://www.gnu.org/licenses/>.

import sys, getopt
import sqlite3
from ck2_parser import ck2_parser

def main(argv=[]):
    if not argv :
        argv = sys.argv[1:]
    help_string = """Usage:   ck2_file_parser --input <input-file> --output <output-file> [--rewrite] [--root <root-element>]
         ck2_file_parser --help"""
    inputfiles = []
    outputfile = ''
    root = None
    
    try:
        opts, args = getopt.gnu_getopt(argv,"hi:o:r:w",['help', 'input=', 'output=','rewrite', 'root='])
    except getopt.GetoptError:
        print help_string
        sys.exit(2)
    print "opts : %s" % (repr(opts))
    print "args : %s" % (repr(args))

    for opt, arg in opts:
        if opt in ['-h', '--help'] :
            print help_string
            sys.exit()
        elif opt in ['-i','--input'] :
            list = [] + arg.split(",")
            inputfiles += list
        elif opt in ['-o','--output'] :
            outputfile = arg
        elif opt in ['-r', '--root'] :
            root = arg
        
    print "inputfiles : %s" % (repr(inputfiles))
    print "outputfile : %s" % (repr(outputfile))

    conn = sqlite3.connect(outputfile)
    ck2p = ck2_parser(conn, False)
    
    for file in inputfiles :
        if root :
            ck2p.parse_file(file, root)
        else:
            ck2p.parse_file(file)
        
if __name__ == "__main__":
   main(sys.argv[1:])    
