#!/usr/bin/env python

# ck2_to_xml reads a CK2 saved game and parses it to XML.
#
# Copyright (C) 2016  Jamil Navarro <jamilnavarro@gmail.com>

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from __future__ import unicode_literals
import os
import io
import re

import sys

reload(sys)
sys.setdefaultencoding('utf-8')

"""
    ck2_2_XML_stream reads a ck2 saved game stream and, parses it and writes to an 
    xml stream.
    
    f : input stream, a ck2 saved game
    out : output stream to write xml
"""
def ck2_2_XML_stream (f, out) :
    # Set up regex patterns
    single_line_pattern = '^\s*([^\s]+)="?([^{}"]+)"?'
    multi_line_pattern = "^\s*([^\s]+)=\s*{?"
    single_line_bracket = "^\s*([^{}]+)\s*}"
    
    slp = re.compile(single_line_pattern)
    mlp = re.compile(multi_line_pattern)
    slb = re.compile(single_line_bracket)
    
    # The stack keeps track of the depth.
    tag_stack = []
    
    # Add a root element
    tagname = "CK2 Save game"
    tag_stack.append(tagname)
    
    import loxun
    xml = loxun.XmlWriter(out)
    xml.startTag(tagname)
    
    line_count = 0
    
    # Clean tagname. Tags are only opened in file once the open bracket '{'
    # is found. This allows the script to depend on opening and closing 
    # brackets being balanced.
    tagname = ""
    
    for line in f:
        line_count += 1
        
        line = line.strip()
        
        single_line_match = slp.match(line)
        multi_line_match = mlp.match(line)
        slb_match = slb.match(line)
        
        if len(tag_stack) > 0 :
            parent = tag_stack[-1]
        else :
            parent = ""
        
        status = ">> Line %i. Current parent is %s" % (line_count, parent)
        
        if single_line_match :
            tagname = single_line_match.group(1).strip()
            value = single_line_match.group(2).strip()
            depth = len(tag_stack)
            xml.startTag(tagname)
            xml.text(value)
            xml.endTag()
            print "FULL TAG %s - %s. %s" % (tagname,value, status)
            last_action = "END TAG %s" % (tagname)
            # Clean tagname. The element is fully written.
            tagname = ""
        elif multi_line_match :
            # Get the tagname value. The element will be added once the open 
            # bracket ('{') is found
            tagname = multi_line_match.group(1).strip()
            depth = len(tag_stack)
            print "found %s (%i) [%i]. %s" % (tagname, line_count, depth, status)
        elif slb_match :
            # Found a close bracket in line, preceded by a value. 
            # Write the value inside inside tag, the close the tag.
            value = slb_match.group(1).strip()
            tagname = tag_stack.pop()
            xml.text(value)
            xml.endTag()
            depth = len(tag_stack)
            print "value : %s . close tag %s (%i) [%i]. %s" % (value,tagname,line_count,depth, status)
        elif "{" in line :
            # Found an open bracket. Time to open an element for tagname
            if tagname == "" :
                # if tagname is empty, is an anon element of a list.
                # use suffix '_inner' and add to outer tag to create dummy tags
                tagname = tag_stack[-1] + "_inner"
            tag_stack.append(tagname)
            xml.startTag(tagname)
            depth = len(tag_stack)
            print "open %s (%i) [%i]. %s" % (tagname, line_count, depth,status)
            # Clean tagname, so more anon elements of a list can be processed.
            tagname = ""
        elif "}" in line :
            # Found a close bracket without value. Value migth be empty or be 
            # in a previous line.
            tagname = tag_stack.pop()
            xml.endTag()
            depth = len(tag_stack)
            print "close %s (%i) [%i]: %s. %s" % (tagname,line_count,depth,line,status)
            tagname = ""
        elif line == "" :
            # empty line
            depth = len(tag_stack)
            print "skipping empty line (%i) [%i]. %s: %s" % (line_count,depth,status,line)
        elif len(tag_stack) > 0 :
            # no tag declaration, no bracket, not empty : means a value. if there's an open element
            # write as text
            print "text for tag %s : %s. %s" % (tag_stack[-1],line,status)
            xml.text(line)
        else :
            # else, write as comment as there's no element to contain it.
            print "other (%i) [%i]: %s " % (line_count, depth, line)
            xml.comment(line)
    
    # Tie any loose ends, in case brackets were not balanced.
    for tag in tag_stack :
        xml.endTag()
    
    xml.close()
    
    return

## MAIN SECTION ##

# Choose Saved Game file
from Tkinter import Tk
from tkFileDialog import askopenfilename, askdirectory

#Tk().withdraw() # we don't want a full GUI, so keep the root window from appearing
root=Tk()
root.withdraw()
save_file_path = askopenfilename(parent=root)
# save_file_path = "" # use \\ to escape backslash in windows.

print save_file_path

#base_file_name = save_file_path.split("\\")[-1]
xml_file_name = "saved_game" + ".xml"

print xml_file_name

root.withdraw()
xml_folder_path = askdirectory(parent=root)
# xml_folder_path = ""  # use \\ to escape backslash in windows.
#os.chdir(xml_folder_path)

print xml_folder_path

with io.open(xml_file_name, "wb") as out :
    import codecs
    with codecs.open(save_file_path,"r","latin-1") as f :
        ck2_2_XML_stream(f, out)
