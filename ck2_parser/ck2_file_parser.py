#!/usr/bin/env python

# ck2_file_parser reads a CK2 saved game and loads it into a database.

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

import re
import codecs
import sqlite3


def clean_date(original_date) :
    if not original_date :
        return None
    
    date_pattern = "^(\d{1,4})[^\d](\d{1,2})[^\d](\d{1,2})$"
    dp = re.compile(date_pattern)
    dp_match = dp.match(original_date)
    
    if dp_match :
        return "%s-%s-%s" % (dp_match.group(1).zfill(4),dp_match.group(2).zfill(2),dp_match.group(3).zfill(2))
    else :
        return None

class ck2_parser :
    def __init__(self, dbconn, drop_tables = False) :
        
        # RE patterns
        key_key_value_pattern = '^\s*([^\s]+)\s*=\s*{\s*([^\s]+)\s*=\s*"?([^{}"\s][^{}"]*)"?\s*}'
        key_value_pattern = '^\s*([^\s]+)\s*=\s*(?:{\s*)?"?([^{}"\s][^{}"]*)"?(?:\s*{)?'
        key_no_value_pattern = "^\s*([^\s]+)\s*=\s*{?"
        single_line_bracket = "^\s*([^{}\s=][^{}=]+)\s*}" #added =
        all_numeric_pattern = "^\d+$"
        date_pattern = "^\-?\d{1,4}\.\d{1,2}\.\d{1,2}$"
        title_pattern = "^(([bcdke])_[^\s=]+)"
        rel_pattern = "^rel_(\d+)$"
        comment_pattern = "\#.*$"
        
        # Compiled RE patterns
        self.kkvp = re.compile(key_key_value_pattern)
        self.kvp = re.compile(key_value_pattern)
        self.knvp = re.compile(key_no_value_pattern)
        self.slb = re.compile(single_line_bracket)
        self.anp = re.compile(all_numeric_pattern)
        self.dtp = re.compile(date_pattern)
        self.tip = re.compile(title_pattern)
        self.rep = re.compile(rel_pattern)
        self.cp = re.compile(comment_pattern)
        
        # The stack keeps track of the depth.
        self.tag_stack = []
        # The dict keeps tack of the key value pairs
        self.dict = []
        
        #self.tag_stack.append(root)
        #self.dict[root] = {}
        
        # once the tag is opened, clear tag name to deal properly with brackets
        self.tagname = ""
        self.line_count = 0
        
        self.db = ck2_db(dbconn, 10000, drop_tables)
        
        self.root = ""
    
    # Auxiliary functions
    def get_parent_tag (self, generation = 0) :
        if len(self.tag_stack) > generation :
            return self.tag_stack[-(1 + generation)]
        elif self.root : #Workaround error in history\\characters\\danish.txt
            if len(self.tag_stack) == 0 :
                self.tag_stack.append(self.root)
            return self.root
        else :
            return None
            
    def get_tag_path(self, delimiter = '.') :
        return delimiter.join(self.tag_stack)
    
    def process_line( self, line) :
        self.line_count += 1
        
        line = line.strip('\r\n')
        #print "<%i> %s" % (self.line_count,repr(line))
        
        if line and "#" in line :
            #print "[%i] STRIP COMMENT from : %s" % (self.line_count, repr(line))
            line = self.cp.sub('',line)
            
        line = line.strip()
        
        if not line :
            return
        
        key_key_value_match = self.kkvp.match(line)
        key_value_match = self.kvp.match(line)
        key_no_value_match = self.knvp.match(line)
        slb_match = self.slb.match(line)
        
        path = self.get_tag_path()
        
        if key_key_value_match :
            key1 = key_key_value_match.group(1)
            key2 = key_key_value_match.group(2)
            value = key_key_value_match.group(3)
            self.clean_and_start_element(key1)
            self.add_value(key2, value)
            self.end_element()
            #print "[%i] $ %s %s : {%s : %s}" % (self.line_count, path, key1, key2, repr(value))
        elif key_value_match :
            self.tagname = key_value_match.group(1)
            value = key_value_match.group(2)
            #print "[%i] %s %s : %s" % (self.line_count, path, self.tagname, repr(value))
            self.add_value(self.tagname, value)
            self.tagname = ""
        elif key_no_value_match and not "{" in line :
            # key = 
            # Get the tagname value. The element will be added once the open 
            # bracket ('{') is found
            self.tagname = key_no_value_match.group(1).strip()
            #print "[%i] %s %s = ?" % (self.line_count, path, self.tagname)
        elif "{" in line :
            if key_no_value_match :
                if not self.tagname :
                    self.tagname = key_no_value_match.group(1).strip()
                else :
                    print "[%i] CONFLICT with open tagname %s at %s and line %s" % (self.line_count,self.tagname,path,repr(line))
            elif not self.tagname :
                # if tagname is empty, is an anon element of a list.
                # use suffix '_inner' and add to outer tag to create dummy tags
                self.tagname = self.get_parent_tag() + "_inner"
            
            #start element tagname. call method to deal with proper id's
            self.clean_and_start_element(self.tagname)
            self.tagname = ""
            
        elif slb_match :
            # Found a close bracket in line, preceded by a value. 
            # Write the value inside inside tag, then close the tag.
            value = slb_match.group(1).strip()
            try :
                self.tagname = self.get_parent_tag()
            except IndexError :
                print "[%i] = stack is empty: %s" % (self.line_count, repr(line))
            self.end_element()
            self.add_value(self.tagname,value)
            #self.set_value(self.tagname,value)
            #print "[%i] %s %s = %s" % (self.line_count, path, self.tagname, repr(value))
            self.tagname = ""
            
        elif "}" in line :
            self.end_element()
            try :
                self.tagname = self.get_parent_tag()
            except IndexError :
                print "[%i] = stack is empty: %s" % (self.line_count, repr(line))
            self.tagname = ""
        else :
            print "[%i] NOT MATCH : %s" % (self.line_count, repr(line))
    
    def clean_and_start_element( self, key) :
        #self.dict[key] = value
        #self.tag_stack.append(key)
        anp_match = self.anp.match(key)
        dtp_match = self.dtp.match(key)
        tip_match = self.tip.match(key)
        rep_match = self.rep.match(key)
        
        path = self.get_tag_path()
        
        if anp_match :
            # tagname is all numeric
            # Can't use an all numeric tag. Save the numric value. Will be used as an id
            id = key
            
            # use suffix '_element' and add to outer tag to create dummy tags
            tagname = self.get_parent_tag() + "_element"
            #self.tag_stack.append(tagname)
            self.add_level(tagname)
            self.add_value("id",id)
            #xml.startTag(tagname)
            
            # Add an id element inside the new tag. Close it immediateley
            print "[%i] %s.%s id = %s" % ( self.line_count, path, tagname, id)
            #tagname = ""
        elif dtp_match :
            # tagname is a date
            # Can't start a tag with a number. Will be used as date
            
            date = key
            
            tagname = self.get_parent_tag() + "_element"
            #tag_stack.append(tagname)
            self.add_level(tagname)
            self.add_value("date",clean_date(date))
            #xml.startTag(tagname)
            
            # Add an id element inside the new tag. Close it immediateley
            print "[%i] %s.%s id = %s" % ( self.line_count, path, tagname, date)
            #tagname = ""
        elif tip_match :
            #tagname is a title
            title = key
            
            if self.get_parent_tag() == "CK2_Save_game_element" :
                tagname = "title_information"
            elif self.get_parent_tag() in ["landed_titles","landed_title"] :
                tagname = "landed_title"
            else :
                tagname = "title_element"
            
            self.add_level(tagname)
            self.add_value("title_id",title)
            #xml.startTag(tagname)
            
            # Add an id element inside the new tag. Close it immediateley
            print "[%i] %s.%s id = %s" % ( self.line_count, path, tagname, title)
            #tagname = ""
        elif rep_match :
            #tagname is a title
            character_id = rep_match.group(1)
            tagname = "rel"
            
            #tag_stack.append(tagname)
            self.add_level(tagname)
            self.add_value("character_id", character_id)
            
            # Add an id element inside the new tag. Close it immediateley
            print "[%i] %s.%s id = %s" % ( self.line_count, path, tagname, character_id)
            #tagname = ""
        else :
            # Non numeric tag can be used. Script doesn't check yet for spaces or other special chars
            #self.tag_stack.append(key)
            self.add_level(key)
            print "[%i] %s.%s" % (self.line_count, path, key) #self.tagname ?
            #tagname = ""
    
    def get_parent_dict(self, generation = 0) :
        if len(self.dict) == 0 :
            self.dict.append({})
        
        dict = self.dict[-1]
        
        for tag in self.tag_stack[0:len(self.tag_stack) - generation] : # 
            if tag in dict.keys() :
                if len(dict[tag]) == 0 : # Added as workaround for error in danish.txt line 2379
                    dict[tag].append({})
                dict = dict[tag][-1]
            else :
                print "No key %s in %s" % (tag, repr(dict))
        return dict
    
    def get_value_from_dict(self, key, generation = 0) :
        dict = self.get_parent_dict(generation)
        if key in dict.keys() and len(dict[key]) > 0 :
            return " ".join(dict[key])
        else :
            return None
    
    def end_element(self) :
        #print "end_element before full dict = %s " % repr(self.dict)
        
        self.save_element_to_db()
        
        top = self.tag_stack.pop()
        
        dict = self.get_parent_dict()
        #self.save_element_to_db(dict)
        print "[%i] closing (%s) (%s) = %s" % (self.line_count, self.get_tag_path(), top, repr(dict))
        
        try :
            del dict[top][-1]
        except:
            print "no %s in %s" % (top,repr(dict))
        
        #print "end_element (%s) full dict = %s " % (self.get_tag_path(), repr(self.dict))
        
    def add_level (self, key) :
        #print "add_level before full dict = %s " % repr(self.dict)
        
        #if len(self.dict) == 0 :
            # self.dict.append({})
        
        # dict = self.dict[-1]
        
        # for tag in self.tag_stack : # 
            # if tag in dict.keys() :
                # dict = dict[tag][-1]
            # else :
                # print "No key %s in %s" % (tag, repr(dict))
        dict = self.get_parent_dict()
        
        try:
            dict[key].append({})
        except :
            dict[key] = []
            dict[key].append({})
        
        self.tag_stack.append(key)
        #print "add_level (%s) full dict = %s " % (self.get_tag_path(), repr(self.dict))
    
    def add_value( self, key, value) :
        #print "add_value before full dict = %s " % repr(self.dict)
        # dict = self.dict[-1]
        # for tag in self.tag_stack :
            # if tag in dict.keys() :
                # dict = dict[tag][-1]
            # else :
                # print "No key %s in %s" % (tag, repr(dict))
        dict = self.get_parent_dict()
        try:
            dict[key].append(value)
        except :
            dict[key] = []
            dict[key].append(value)
        
        #print "add_value (%s) full dict = %s " % (self.get_tag_path(), repr(self.dict))
        
    def set_value(self, key, value) :
        #print "set_value before full dict = %s " % repr(self.dict)
        # dict = self.dict[-1]
        # for tag in self.tag_stack :
            # if tag in dict.keys() :
                # dict = dict[tag][-1]
            # else :
                # print "No key %s in %s" % (tag, repr(dict))
        dict = self.get_parent_dict()
        dict[key] = value
        ##test :
        tag = self.tag_stack.pop()
        print "set_value (%s) full dict = %s (%s)" % (self.get_tag_path(), repr(self.dict), tag)
    
    def save_element_to_db(self, dict = None, tag = None) :
        if dict is None and tag is None :
            dict = self.get_parent_dict(0)
            tag = self.get_parent_tag(0)
        #print "save type = %s ; value = %s; flat = %s" % (tag, dict, flat_dict(dict))
        
        if tag == "historic_dynasties_element" :
            self.db.add_historic_dynasty(dict)
        elif tag == "landed_title" :
            self.db.add_landed_title(dict, self.get_value_from_dict("title_id",1))
        elif self.get_parent_tag(1) == "traits" :
            self.db.add_trait(dict, tag)
        elif tag == "modifier" and self.get_parent_tag(4) == "technology" :
            self.db.add_technology(dict, self.get_parent_tag(2), self.get_parent_tag(3), self.get_parent_dict(1)['id'][-1])
        elif self.get_parent_tag(1) == "opinion_modifier" :
            self.db.add_opinion_modifier(dict, self.get_parent_tag(0))
        elif self.get_parent_tag(1) == "minor_title" :
            self.db.add_minor_title(dict, tag)
        elif tag == "historic_character_element_element" :
            for key in dict.keys() :
                if key in ['birth', 'death'] :
                    self.get_parent_dict(1)[key] = dict[key]
        elif tag == "historic_character_element" :
            self.db.add_historic_character(dict)
        elif tag == "dynasties_element" :
            self.db.add_dynasty(dict)
        elif tag == "character_element" :
            self.db.add_character(dict)
        elif tag == "CK2_Save_game_element" :
            self.db.add_province(dict)
        elif tag == "claim" :
            self.db.add_claim(dict, self.get_parent_dict(1)['id'][-1]) 
        elif tag == "title_element" :
            self.db.add_title(dict)
        else :
            # print "No method to handle tag %s %s" % (self.get_tag_path(), tag)
            pass
            
    def parse_file(self, path, root="CK2_Save_game") :
        # clear the stack and the dict
        self.root = root
        self.tag_stack = []
        self.dict = []
        self.line_count = 0
        # Add a root element
        self.add_level(root)
        
        with codecs.open(path,'r','cp1252') as f :
            #os.remove('testfile.txt')
            for line in f :
                self.process_line(line)
                #try :
                #    self.process_line(line)
                #except Exception as error:
                #    self.db.close()
                #    raise error
                if self.line_count > 10000000 :
                    break
        self.db.close()

def rename_dict_key(dict, old_key, new_key) :
    dict[new_key] = dict.get(old_key)
    try :
        del dict[old_key]
    except KeyError :
        pass
    return dict

def validate_dict(dict, name, key_list) :
    for key in dict.keys() :
        if key not in key_list :
            print "Can't handle field in %s: %s = %s" % (name,key,dict.get(key))

def generate_insert_sql(table, columns) :
    column_text = ", ".join(columns)
    placeholder = ", ".join("?" * len(columns))
    return "INSERT INTO %s (%s) VALUES (%s)" % (table, column_text,placeholder)

def flat_dict(old_dict) :
    dict = {}
    #print "old_dict %s" % repr(old_dict)
    for key in old_dict.keys() :
        if old_dict[key] and len(old_dict[key]) > 0 :
            list_value =  [x for x in old_dict[key] if x]
            text_value = " ".join(list_value).strip()
            dict[key.lower()] = text_value
            #print "flat_dict y %s : %s" % (key,repr(dict))
        else :
            #print "flat_dict n %s : %s" % (key,repr(dict))
            pass
    return dict
    
def generate_value_tuple(dict, key_list) :
    return tuple(map(lambda x: dict.get(x),key_list))
                
class ck2_db :
    def __init__ (self, dbconn, commit_interval = 1000, drop_tables = False) :
        self.conn = dbconn
        self.c = self.conn.cursor()
        self.fields = {}
        self.fields['historic_dynasty'] = ['id', 'name', 'culture']
        self.fields['dynasty'] = ['id', 'name', 'culture']
        self.fields['landed_title'] = ['title_id', 'de_jure_liege','character_title', 'title_prefix', 
        'foa', 'short_name', 'location_ruler_title', 'capital_id', 'caliphate',
        'holy_order', 'mercenary', 'pirate','rebel','landless','is_primary','independent','culture','religion','controls_religion','tribe','color','color2',
        'modifier']
        
        self.fields['trait'] = ['trait_name','education',
        'diplomacy','intrigue','learning','martial','stewardship',
        'ai_ambition', 'ai_greed', 'ai_honor','ai_rationality',
        'congenital','fertility','birth', 'health', 'inbred', 'lifestyle','personality', 'priest',
        'is_health','is_illness','incapacitating', 'is_epidemic',
        'ambition_opinion', 'church_opinion', 'dynasty_opinion', 'infidel_opinion', 'liege_opinion', 'opposite_opinion', 'same_opinion', 'same_religion_opinion', 'sex_appeal_opinion','spouse_opinion', 'twin_opinion', 'vassal_opinion', 'monthly_character_piety', 'monthly_character_prestige', 'global_tax_modifier' ]
        
        self.fields['technology'] = ['tech_name', 'tech_group', 'tech_level', 
        'archers_defensive', 'archers_offensive', 
        'heavy_infantry_defensive', 'heavy_infantry_offensive',
        'horse_archers_defensive','horse_archers_offensive',
        'knights_defensive', 'knights_offensive',
        'light_cavalry_defensive', 'light_cavalry_offensive', 
        'light_infantry_defensive', 'light_infantry_offensive',
        'pikemen_defensive', 'pikemen_offensive',
        'siege_speed', 'siege_defence', 'land_morale', ''
        'castle_tax_modifier', 'city_tax_modifier', 'temple_tax_modifier',
        'castle_opinion', 'town_opinion', 'church_opinion', 
        'add_prestige_modifier', 'add_piety_modifier',
        'culture_flex', 'religion_flex',
        'local_build_time_modifier', 'short_reign_length'
        ]
        
        self.fields['opinion_modifier'] = ['name', 'opinion', 'months', 'prison_reason', 'revoke_reason']
        """
        """
        self.fields['minor_title'] = ['name', 'realm_in_name', 'dignity', 'monthly_salary', 'monthly_prestige', 'message']
        
        self.fields['historic_character'] = ['id', 'name', 'female','birth_date', 'death_date','father', 'mother', 
        'diplomacy', 'stewardship', 'intrigue', 'learning', 'martial', 
        'add_trait','give_nickname', 'add_claim', #historical files
        'religion', 'culture', 'dynasty','dna', 'properties', 'employer']
        
        self.fields['character'] = ['id', 'birth_name', 'name', 'nickname', 'female', 'historical','birth_date', 'death_date','father', 'mother', 'spouse', 'attributes', 'fertility', 'health', 'traits', 'prestige', 'score', 'piety', 'religion', 'culture', 'graphical_culture', 'dynasty', 'old_holding','dna', 'properties', 'type', 'is_bastard', 'title','job_title','wealth','employer', 'host', 'guardian', 'regent', 'betrothal', 'lover', 'is_prisoner', 'imprisoned', 'known_plots', 'last_objective', 'current_income', 'estimated_monthly_income', 'estimated_monthly_expense', 'estimated_yearly_income', 'averaged_income', 'ambition_date', 'action', 'action_date', 'action_location', 'tech_focus', 'player']
        
        self.fields['province'] = ['id', 'name', 'culture', 'religion', 'max_settlements', 'title_id']
        
        self.fields['claim'] = ['character_id', 'title_id', 'pressed']
        
        self.fields['title'] = ['id', 'liege', 'holder', 'succession', 'gender', 'usurp_date', 'army_size_percentage', 'set_investiture', 'active', 'de_jure_law_changer', 'normal_law_changer', 'succ_law_changer', 'de_jure_law_change', 'normal_law_change', 'succ_law_change', 'set_the_kings_peace', 'set_protected_inheritance', 'set_appoint_generals', 'set_allow_title_revokation', 'set_allow_free_infidel_revokation', 'cannot_cancel_vote', 'previous']
        
        self.db_init(drop_tables)
        self.insert_count = 0
        self.commit_interval = max(1,commit_interval)
    
    def insert_record(self, table_name, dict) :
        fields = self.fields[table_name]
        validate_dict(dict, table_name, fields)
        sql = generate_insert_sql(table_name, fields)
        values = generate_value_tuple(dict, fields)
        
        #print (sql, repr(values))
        try :
            self.c.execute(sql, values)
        except Exception:
            self.conn.commit()
            print ">%s -- %s<" % (sql,repr(values))
            raise Exception
        self.insert_count = self.insert_count + 1
        if self.insert_count % self.commit_interval == 0 :
            print "Inserted %i records" % (self.insert_count)
            self.conn.commit()

    def db_init(self, drop_tables = False) :
        for table_name in self.fields.keys() :
            if drop_tables :
                self.c.execute("DROP TABLE IF EXISTS %s" % (table_name))
            columns = ", ".join(self.fields[table_name])
            self.c.execute("CREATE TABLE IF NOT EXISTS %s (%s)" % (table_name, columns))
        views = [
            "CREATE VIEW IF NOT EXISTS dynasty_view AS SELECT id, name, culture from historic_dynasty UNION SELECT id, name, culture from dynasty",
            """CREATE VIEW IF NOT EXISTS character_view AS SELECT tmp.id, coalesce(ch.birth_name,hc.name) name, coalesce(ch.female,hc.female) female,         
                coalesce(ch.birth_date,hc.birth_date) birth_date, 
                coalesce(ch.death_date,hc.death_date) death_date, coalesce(ch.dynasty,hc.dynasty) dynasty, coalesce(ch.father,hc.father) father, 
                coalesce(ch.mother, hc.mother) mother, coalesce(ch.religion,hc.religion) religion, coalesce(ch.culture,hc.culture) culture, 
                coalesce(ch.employer,hc.employer) employer, coalesce(ch.properties,hc.properties) properties
            FROM (SELECT id FROM character UNION SELECT id FROM historic_character) tmp
            LEFT JOIN character ch ON ch.id = tmp.id
            LEFT JOIN historic_character hc ON hc.id = tmp.id""",
            """CREATE VIEW IF NOT EXISTS family_tree AS SELECT cv.id id, cv.dynasty dynasty, cv.father father_id, fgp.dynasty pdynasty, cv.mother mother_id,
                mgp.dynasty mdynasty, fgp.father pgfather_id, fgp.mother pgmother_id, mgp.father mgfather_id, mgp.mother mgmother_id
            FROM character_view cv
            LEFT JOIN character_view fgp
            ON cv.father = fgp.id
            LEFT JOIN character_view mgp
            ON cv.mother = mgp.id""",
            """CREATE VIEW IF NOT EXISTS single_claimants AS SELECT cl.character_id, cl.title_id title_claim, cl.pressed pressed_claim, ch.female, ch.birth_name, 
                dy.name dynasty_name, ch.culture, ch.religion, ch.dynasty dynasty_id, ch.birth_date, ch.is_bastard
            FROM claim cl
            LEFT JOIN title ti ON ti.holder = cl.character_id
            LEFT JOIN character ch ON ch.id = cl.character_id
            LEFT JOIN dynasty_view dy ON dy.id = ch.dynasty
            WHERE 1=1
            AND ti.id IS NULL
            AND ch.spouse IS NULL AND ch.death_date IS NULL AND ch.betrothal IS NULL""",
            """CREATE VIEW IF NOT EXISTS single_dynasts AS SELECT ch2.* FROM character ch1 JOIN character ch2 ON ch1.dynasty = ch2.dynasty
            WHERE ch1.player = 'yes' AND ch2.death_date IS NULL AND ch2.spouse IS NULL AND ch2.betrothal IS NULL""",
            """CREATE VIEW IF NOT EXISTS marry_into_title AS SELECT ti.id title_id, ti.holder, ti.succession, 
                ti.gender, ch.birth_name, dv.name dynasty_name, ch.dynasty, ch.female, ch.birth_date, ch.culture, ch.religion, ch.is_bastard
            FROM title ti LEFT JOIN character ch ON ch.id = ti.holder LEFT JOIN dynasty_view dv ON dv.id = ch.dynasty
            WHERE (ch.female IS NOT NULL OR ch.is_bastard IS NOT NULL) AND ch.spouse IS NULL AND ch.betrothal IS NULL AND ch.death_date IS NULL""",
            """CREATE VIEW IF NOT EXISTS exiled_ruler_single_child AS SELECT ch.id, ch.birth_name, dv.name dynasty_name, ch.culture, 
                ch.religion, ch.birth_date, ch.dynasty, ch.female, ch.is_bastard, ch.father, ft.id father_title, ch.mother, mt.id mother_title
            FROM character ch
            LEFT JOIN title ft ON ft.holder = ch.father
            LEFT JOIN title mt ON mt.holder = ch.mother
            LEFT JOIN dynasty_view dv ON dv.id = ch.dynasty
            WHERE ch.death_date IS NULL AND ch.spouse IS NULL AND ch.betrothal IS NULL 
            AND ch.host <> ch.id AND ch.host <> ch.father AND ch.host <> ch.mother
            AND (ft.id IS NOT NULL OR mt.id IS NOT NULL)""",
            """CREATE VIEW IF NOT EXISTS live_dynasts AS SELECT ch2.id, ch2.birth_name, ch2.female, ch2.birth_date, ch2.father, ch2.mother, ch2.spouse, ch2.host,
            CASE WHEN ch2.host = ch2.id THEN 'ruler' WHEN ch2.host = ch2.father OR ch2.host = ch2.mother THEN 'child of ruler' WHEN ch2.host = ch2.spouse 
            THEN 'consort of ruler' END status
            FROM character ch1 JOIN character ch2 ON ch1.dynasty = ch2.dynasty
            WHERE ch1.player = 'yes' AND ch2.death_date IS NULL""",
        ]
        for query in views :
            self.c.execute(query)
        self.conn.commit()
        
    def db_get_column_names(self, table_name) :
        pass
        # validate table_name
        sql = 'select * FROM %s LIMIT 0' % (table_name)
        cursor = connection.execute(sql)
        names = [description[0] for description in cursor.description]
        return names

    def add_historic_dynasty(self, dict) :
        #fields = ['id', 'name', 'culture']
        self.insert_record('historic_dynasty', flat_dict(dict))
        
    def add_landed_title(self, dict, liege) :
        fdict = flat_dict(dict)
        fdict = rename_dict_key( fdict, 'title', 'character_title')
        fdict = rename_dict_key( fdict, 'capital', 'capital_id')
        fdict = rename_dict_key( fdict, 'primary', 'is_primary')
        if liege :
            fdict['de_jure_liege'] = liege
        #fields = self.fields['landed_title']
        
        self.insert_record('landed_title', fdict)
    
    def add_trait(self, dict, trait_name) :
        fdict = flat_dict(dict)
        fdict['trait_name'] = trait_name
        print "add trait %s" % repr(fdict)
        self.insert_record('trait', fdict)
        
    def add_technology(self, dict, name, group, level) :
        fdict = flat_dict(dict)
        fdict['tech_level'] = level
        fdict['tech_name'] = name
        fdict['tech_group'] = group
        print "add trait %s" % repr(fdict)
        self.insert_record('technology', fdict)
        
    def add_opinion_modifier( self, dict, name) :
        fdict = flat_dict(dict)
        fdict['name'] = name
        print "add opinion_modifier %s" % repr(fdict)
        self.insert_record('opinion_modifier', fdict)
        
    def add_minor_title( self, dict, name) :
        fdict = flat_dict(dict)
        fdict['name'] = name
        print "add opinion_modifier %s" % repr(fdict)
        self.insert_record('minor_title', fdict)
        
    def add_dynasty(self, dict) :
        #fields = ['id', 'name', 'culture']
        self.insert_record('dynasty', flat_dict(dict))
        #print "add dynasty"
        
    def add_historic_character (self, dict) :
        fdict = flat_dict(dict)
        if fdict.get('id') : # Workaround for error in danish.txt
            fdict = rename_dict_key(fdict, 'birth', 'birth_date')
            fdict['birth_date'] = clean_date(fdict['birth_date'])
            fdict = rename_dict_key(fdict, 'death', 'death_date')
            fdict['death_date'] = clean_date(fdict['death_date'])
            #switch to make historical yes ??
            print "add character %s" % repr(fdict)
            self.insert_record('historic_character', fdict)
        
    def add_character (self, dict) :
        fdict = flat_dict(dict)
        fdict['birth_date'] = clean_date(fdict.get('birth_date'))
        fdict['death_date'] = clean_date(fdict.get('death_date'))
        fdict['ambition_date'] = clean_date(fdict.get('ambition_date'))
        fdict['action_date'] = clean_date(fdict.get('action_date'))
        fdict['imprisoned'] = clean_date(fdict.get('imprisoned'))
        self.insert_record('character', fdict)
        
    def add_province (self, dict) :
        #print "dict : %s" % repr(dict)
        fdict = flat_dict(dict)
        fdict = rename_dict_key(fdict, 'title', 'title_id')
        #print "fdict : %s" % repr(fdict)
        self.insert_record('province',fdict)
        
    def add_claim(self, dict, character_id) :
        fdict = flat_dict(dict)
        fdict = rename_dict_key(fdict, 'title', 'title_id')
        fdict['character_id'] = character_id 
        self.insert_record('claim',fdict)
        
    def add_title(self, dict) :
        fdict = flat_dict(dict)
        
        fdict = rename_dict_key(fdict, 'title_id', 'id')
        fdict['usurp_date'] = clean_date(fdict.get('usurp_date'))
        fdict['de_jure_law_change'] = clean_date(fdict.get('de_jure_law_change'))
        fdict['normal_law_change'] = clean_date(fdict.get('normal_law_change'))
        fdict['succ_law_change'] = clean_date(fdict.get('succ_law_change'))
        
        self.insert_record('title',fdict)
    def close(self) :
        self.conn.commit()
        