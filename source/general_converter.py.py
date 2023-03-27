#!/usr/bin/env python
# coding: utf-8

import PySimpleGUI as sg
import ast
import os.path
import threading
import string
import codecs
import re
from copy import copy


class Section:
    """
    This class describes section of input program file.
    """
    def __init__(self, id:str, converter:Converter, delimeters:tuple):
        assert len(delimeters)  == 2
        self.name       = name
        self.converter  = converter
        self.delimeters = delimeters
        self.processor_rules = {}
        self.i_code    = []
        self.o_code   = []
        self.subsections = {}
        self.post_processor = None


    def process(self) -> None:
        verdict = ""
        try:
            for line in self.i_code:
                verdict, processed  = self.process_line(line)
                good_line = self.post_processor(verdict, line)
                self.o_code.append(good_line)
                if(len(errors) > 0):
                    return
        except Exception as e:
            self.converter.errors.append(f"Synthesis section {self.name} error: {e}")


    def process_line(self, line:str) -> tuple:
        try:
            line = " " + line + " "
             for pattern in self.processor_rules:
                match = re.search(pattern, line)
                if match:
                    gl, rep, verd = self.processor_rules[pattern](match)
                    line = re.sub(pattern, rep, line, count=1)
                    goodline += gl + " "
                    verdict  += verd
                    line = re.sub(r"\s+", " ", line)

            if len(line) == 0 or re.fullmatch(r"\s*", line):
                return verd, goodline[:-1]

            return "unparsible", f"from {line} can extract only {goodline}"
        except Exception as e:
            self.converter.errors.append(f"Processing section {self.name} error {e}")
            self.converter.errors.append(f"while parsing >{line}<")

    def add_processor_rule(self, pattern, f):
        if pattern in self.processor_rules:
            self.converter.errors.append(f"Synthesis error: pattern >{pattern}< is used twice in section >{section}<")
        self.processor_rules[pattern] = f


class Converter:
    """
    This is the base class
    This class is used to ...
    """
    def __init__(self, config=None, input_file=None, output_file=None):

        self.lineno         = "keep"    
        if "use_line_numbers" in config:
            self.lineno = "new"
        if "keep_old_line_numbers" in config:
            self.lineno = "keep"
        self.analysator     = {}
        self.input_file     = input_file
        self.output_file    = output_file
        self.errors         = []
        self.unparsible     = []
        self.subroutines    = {}
        self.delimeters     = {}
        self.sections       = {}
        self.i_code         = ""
        self.o_code         = ""
        self.status         = "ready"
        self.sections_ordered = []

    def add_section(name:str, delimeters:tuple, rules:dict=None):
        try:
            if name in sections:
                self.errors.append(f"section {name} is added twice")
            self.sections[name] = Section(name, self, delimeters)
            self.sections_ordered.append(name)
            if rules is not None:
                for rule in rules:
                    self.sections[name].add_rule(rule, rules[rule])
        except Exception as e:
            self.errors.append(f"Error adding section {name}")
            self.status = "error"
            
    def add_analysis_rule(self, pattern:str, f:callable):
        if pattern in self.analysator:
            errors.append(f"Analysis error: pattern >{pattern}< is used twice")
            self.status = "error"
        self.analysator[pattern] = f


    def analyse_line(self, line:str):
        try:
            # removing newline characters and whitespaces
            line = re.sub(r"\s+", " ", line)
            for pattern in self.analizator:
                match = re.match(pattern, line)                                
                if match:
                    self.analizator[pattern](match)
        except Exception as e:
            self.errors.append(f"Error analysing: {e} while looking at line {line}")
            self.status = "error"

    def analysis(self):
        """
            Read the file and fills internal structures, such as sections, toolchange number, etc
        """
        try:
            for line in self.i_code:
                analyse_line(line)
                if(len(errors) > 0):
                    return
        except Exception as e:
            self.errors.append(f"Analysis failed: {e} ")
            self.status = "error"

    def synthesis(self):
            for section in self.sections_ordered:
                self.sections[section].process()
                               
    def load(self, input_file=None):
        if input_file is None and self.input_file is not None:
            input_file = self.input_file
        try:
            with open(input_file) as f:
                self.code = f.readlines()
                f.close()
        except:
            self.errors.append(f"can not load LST file {input_file}")
            self.status = "error"

    def save(self, output_file=None):
        if output_file is None and not self.output_file is None:
            output_file = self.output_file
        try:
            f = codecs.open(output_file,'w',encoding='utf-8')
            f.writelines(self.ngcode)
            f.close()
        except:
            self.errors.append(f"can not load LST file {output_file}")
            self.status = "error"

    def convert(self, lst_filename, ngc_filename):
        try:
            assert self.status == "ready"
            self.__init__(lst_filename, ngc_filename)

            self.prepare():


            print(f"operating file {lst_filename}")
            self.load_lst(self.input_file)
            if len(self.errors) == 0 and self.status:
                print("loading ok")
            else:
                return
            
            self.analysis()
            if len(self.errors) == 0:
                print("analysis ok")
            else:
                return
            

            self.synthesis()
            if len(self.errors) == 0:
                print("synthesis ok")
            else:
                return

            self.save_ngc(self.output_file)
            if len(self.errors) == 0:
                print("saving ok")
            else:
                return
            self.status = 'ok'
        except:
            self.status = "error"





class lst2ngc(Converter):
    def __init__(self):
        super().__init__()
        self.toolchange_cntr = 0
        self.load_consts()

    def restore_defaults(self):
        try:
            self.symbols = {
                0: 'N',
                1: 'X',
                2: 'Y',
                3: 'A',
                4: 'B',
                5: 'I',
                6: 'J',
                7: 'F', 
                80: 'G0',
                81 : 'G1',
                82 : 'G2',
                83 : 'G3',
                84 : 'G4',
                85 : 'G20',
                86 : 'G21',
                87 : 'M30',
                91 : 'G91',
                90 : 'G90'
            }
            self.sections ={
                        "WZG_CALLS" : {"pname":0,     "param_file_name": -1}, 
                        "PTT"       : {"pname":"PTT", "param_file_name": 1},
                        "SHEET_TECH": {"pname":"SHT", "param_file_name": 2},
                        "SHEET_LOAD": {"pname":"SHL", "param_file_name": 4}, 
                        "SHEET_UNLOAD"        : {"pname": "SHU", "param_file_name": 5 },
                        "PART_UNLOAD"         : {"pname": "PAU", "param_file_name": 6 },
                        "EINRICHTEPLAN_INFO"  : {"pname": "",    "param_file_name": -1 },
                        "PROGRAMM"            : {"pname": 0,     "param_file_name": -1 },
                        "WZG_STAMM"           : {"pname": "WST", "param_file_name": -1 },
                        "SHEET_REPOSIT"       : {"pname": "RPO", "param_file_name": 7}
                     }
            self.codes_renames = {
                'G70':' G20',
                'G71':' G21',
                'G01':' G1',
                'G00':' G0',
                'G02':' G2',
                'G03':' G3',
                'M30':' M30',
                'TC_TOOL_CHANGE':' M6',
                'TC_SUCTION_ON':' M108',
                'TC_SUCTION_OFF':' M109',
                'PRESSERFOOT_ON':'#<_PRESSERFOOT_ON> = 1\n M165 P#<_PRESSERFOOT_ON>',
                'PRESSERFOOT_OFF':'#<_PRESSERFOOT_ON> = 0\n M165 P#<_PRESSERFOOT_ON>',
                'G90':' G90',
                'G91':' G91',
                'G53':'G53'
            }
            self.groups = {
                'TC_TOOL_TECH'     : ["PTT", "M153 \n M165 P#<_PRESSERFOOT_ON>"],
                'TC_SHEET_TECH'   : ["SHEET_TECH", " M153"],
                'TC_SHEET_LOAD'   : ["SHEET_LOAD", " M651"],
                'TC_SHEET_UNLOAD' : ["SHEET_UNLOAD", " M652"],
                'TC_PART_UNLOAD'  : ["PART_UNLOAD", " M667"],
                'TC_SHEET_REPOSIT': ['RPO', " M610"]
            }
            self.coord_rename = {"C1":" A", "C2":" B"}
            self.sections ={
                        "WZG_CALLS" : {"pname":0,     "param_file_name": -1}, 
                        "PTT"       : {"pname":"PTT", "param_file_name": 1},
                        "SHEET_TECH": {"pname":"SHT", "param_file_name": 2},
                        "SHEET_LOAD": {"pname":"SHL", "param_file_name": 4}, 
                        "SHEET_UNLOAD"        : {"pname": "SHU", "param_file_name": 5 },
                        "PART_UNLOAD"         : {"pname": "PAU", "param_file_name": 6 },
                        "EINRICHTEPLAN_INFO"  : {"pname": "",    "param_file_name": -1 },
                        "PROGRAMM"            : {"pname": 0,     "param_file_name": -1 },
                        "WZG_STAMM"           : {"pname": "WST", "param_file_name": -1 },
                        "SHEET_REPOSIT"       : {"pname": "RPO", "param_file_name": 7}
                     }
            self.delimeters = {}
            for section in self.sections:
                self.delimeters["BEGIN_" + section]  = False
                self.delimeters["ENDE_" + section]  = False

            self.synthesator = self.build_synthesator()
            self.analysator = self.build_analysator()
            if len(self.errors) == 0:
                print("processor build ok")
            else:
                return
            
            
        except Exception as e:
            self.errors.append(f"Error in loading consts{e}")
            self.status = "error"

    def build_synthesator(self):
        try:
            """
            Prepares a dict of type 
                (regexp) : function(match object)

                specifed to operate with TOPS LST

            when matcher is found in program line, the function is called.

            Function must return a tuple (what we want to add to NGC code, with what we want to replace out match with, verdict)
            """            
            
            # removing comments
            self.add_rule(
                r"\s*(;.*)",
                lambda x: ("","", "skip")
                )

            # handling line numbers
            def N_proc(match):
                N_word = match[1]
                if self.lineno == "keep":
                    return match[0], "", "skip"
                return "", "","skip"
            self.add_rule(
                r"^\s*N(\d+)", 
                N_proc
                )

            #operator's messages
            self.add_rule(
                r'\s*MSG\s*\(\s*"([^"]*)"\s*\)',
                lambda x: (f"(MSG, {x[1].replace(",", "")})\n", "", "skip")
                )
            
            # simple bijective replacements
            for code in self.codes_renames.keys():
                self.add_rule(
                    f"({code})(\D)",
                    lambda x, code=copy(code): (self.codes_renames[code],  x[2], "OK")
                    )
                
                
            #coordinates
            float_patern = r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
            for coord in ["F", "X", "Y", "I", "J", "SPP="]:
                coord_pattern = coord + float_patern
                verd = "OK"
                if coord != 'F' and coord != "SPP=":
                    verd = "MOVE"
                self.add_rule(
                    coord_pattern,
                     lambda x,coord=copy(coord), verd=copy(verd): (f"{coord}{x[1]}", "", verd )
                    )


            #rotary coordinates -- forced to move simultaneously
            self.add_rule(
                r"C[12]\s*=DC\(" + float_patern + r"\s*\)",
                lambda x: ("A" + x[1] + " B" + x[1], "", "MOVE" )
                )

            # tool selection
            def Toolno_proc(match):
                goodline=""
                toolcode = "'" + match[1] + "'"
                if self.toolchange_cntr > 0:
                    goodline +=f" o{100 + self.toolchange_cntr} endif \n"
                self.toolchange_cntr += 1
                goodline +=f" o{100 + self.toolchange_cntr} if [#<_start_from> LE {self.toolchange_cntr}]\n"
                goodline +=f"T#<_TOOL_{self.sections['WZG_CALLS'][toolcode][0]}>"
                return goodline, "", "OK"

            self.add_rule(
                r'TC_TOOL_NO\s*\(\s*\"(\d+)\"\s*\)',
                Toolno_proc
                )
                        
           
            for key in self.groups:
                values = self.groups[key]
                pattern = key + r'\s*\(\s*\"([^\"]+)\"\s*\)'
                goodline = ' ;appply {0} parameters {1} \n o{2} call\n{3}'
                self.add_rule(
                    pattern,
                    lambda x, key=copy(key),values=copy(values), goodline=copy(goodline): (goodline.format(
                        key,
                        x[1],
                        str(self.subroutines["'" + x[1]+ "'"] ),
                        values[1]
                        ),
                        "",
                        "OK"
                        )
                )
                
            #TC_POS_ACCEL
            accel_patern = r"TC_POS_ACCEL\s*\(\s*"+ float_patern + r"\s*,\s*" + float_patern + r"\s*,\s*" + float_patern + r"\s*,\s*" + float_patern + r"\s*\)"
            self.add_rule(
                accel_patern,
                lambda x: (f' ;acceleration: {x[0]}\n', "", "OK")
                )
            
            # processor[accel_patern] = lambda x: (f' ;acceleration: {x[0]},{x[4]},{x[8]},{x[12]}\n', "", "OK")
            

                
            # trailon pattern
            trailon_pattern=r"TRAILON\(C[12],C[12]\)"
            self.add_rule(
                trailon_pattern,
                lambda x: ("","", "TRAILON")
                )
                
            #PUNCH_ON / PUNCH_OFF
            self.add_rule(
                'PUNCH_ON',
                lambda x: (" #<_PUNCH> = 1\n", "", "PON")
                )
            self.add_rule(
                'PUNCH_OFF',
                lambda x: (" #<_PUNCH> = 0\n", "", "POFF")
                )
                
            # NIBBLE_ON / NIBBLE_ON
            self.add_rule(
                'NIBBLE_ON',
                lambda x: (" #<_NIBBLING> = 1\n", "", "NON")
                )
            self.add_rule(
                'NIBBLE_OFF',
                lambda x: (" #<_NIBBLING> = 0\n", "", "NOFF")
                )
            
            
            # TANGTOOL
            self.add_rule(
                "TC_TANGTOOL_OFF",
                lambda x: ("#<_TANGTOOL_EN>=0\n#<_TANGTOOL_P>=0", "", "OK")
                )
            self.add_rule(
                r"TC_TANGTOOL_ON\s*\(\s*("+float_patern+r")\s*",
                lambda x: (f"#<_TANGTOOL_EN>=1\n#<_TANGTOOL_P>={x[1]}", "", "OK")
                )


            #skipped codes
            self.add_rule(
                "TC_CLAMP_CYC", 
                lambda x: ("","", "skip")
                )
            self.add_rule(
                "M17",
                 lambda x: ("","", "skip")
                 )
            
            # subroutine call
            # print(self.subroutines)
            # for sub in self.subroutines:
            #     sub_pattern = f'([^\"]|^){sub[1:-1]}([^\"]|$)'
            #     processor[sub_pattern] = lambda x, sub=copy(sub) : ('\no{0} call\n'.format(self.subroutines[sub]), x[1]+x[2], "OK" )
        except Exception as e:
            self.errors.append(f"building processor error : {e}")


    def build_analysator(self):

        for section in self.sections:
            pattern = "BEGIN_"+section
            self.add_analysis_rule(
                pattern,
                lambda section=copy(section): self.current_section = section
                )

            pattern = "ENDE_"+section
            self.add_analysis_rule(
                pattern,
                lambda section=copy(section): self.current_section = section
                )

        def start_text(match):
            self.text = True            
            self.sections[self.current_section][self.current_conf].append([match[0]])

        self.add_analysis_rule(
            r"^START_TEXT$",
            start_text
            ) 
                    
        self.add_analysis_rule(
            r"^START_TEXT$",
            lambda: self.text=False
            )


        def add_to_section(match):
            if self.text:
                self.sections[self.current_section][self.current_conf][-1].append(match[0])

        self.add_analysis_rule(
            r".*",
            add_to_section
            )
            
                            
        def ZA(match)
            _line = match[0].split(",")
            self.sections[self.current_section][_line[1]] = _line[2]
        
        self.add_analysis_rule(
            r".*ZA.*",
            ZA
            ) 


        def DA(match)
            _line = match[0].split(",")
            current_conf  = _line[1]
            self.sections[self.current_section][self.current_conf] = _line[2:]
        
        self.add_analysis_rule(
            r".*DA.*",
            DA
            )   

        def star(match):
            _line = match[0][1:].split(",")
            self.sections[self.current_section][self.current_conf] = self.sections[self.current_section][self.current_conf][:-1]
            self.sections[self.current_section][self.current_conf].extend(_line)

        self.add_analysis_rule(
            r"\*.*",
            star
            )   


    def header_gen(self):
        try:
            self.main_programme = self.sections['EINRICHTEPLAN_INFO']["'TC2000'"][4]
            ret = ""
            ret += ';Machine name:    Trumpf TC200R\n'
            ret += ';Pragrammer name: {0}\n'.format(self.sections['EINRICHTEPLAN_INFO']["'TC2000'"][5][1:-1])
            ret += ';Date:            {0}\n'.format(self.sections['EINRICHTEPLAN_INFO']["'TC2000'"][6][1:-1])
            ret += ';File:            {0}\n'.format(self.sections['EINRICHTEPLAN_INFO']["'TC2000'"][9][1:-1])
            ret += ';Material:        {0}\n'.format(self.sections['EINRICHTEPLAN_INFO']["'TC2000'"][11][1:-1])
            return ret
        except Exception as e:
            self.status = 'error'
            self.errors.append(f'Failed to generate header: {e}')

    def move_prepare(self, line):
            """
            encode moving frame intro o2sub notation
            """
            try:
                move_params  = {}
                _line = line.split(' ')
                for _ in _line:
                    if _[0] != 'G':
                        move_params[_[0]] = _[1:]
                    else:
                        move_params[_] = 1
                call = 'o2 call '
                code_8, code_9 = 0, 0
                for symbol in range(1, 100):
                    if symbol not in symbols:
                        continue
                    if symbols[symbol] not in move_params:
                        if symbols[symbol][0] != 'G' and symbols[symbol][0] != 'M':
                            move_params[symbols[symbol]] = 123456789987654321228
                        else:
                            move_params[symbols[symbol]] = 0
                        
                    if symbol < 10:
                        call += '[{0}] '.format(move_params[symbols[symbol]])
                    else:
                        po = symbol % 10
                        if (symbol // 10  == 8):
                            code_8 += move_params[symbols[symbol]] * 2 ** po
                        elif (symbol // 10  == 9):
                            code_9 += move_params[symbols[symbol]] * 2 ** po
                call += '[{0}] [{1}]'.format(code_8, code_9)
                return call
            except Exception as e:
                self.errors.append(f"Move prepare error: {e}")
                self.errors.append(f"while parsing {line}")
                self.status = 'error'

    def analysis(self):
        try:

            self.current_conf = ""
            self.current_section=""
            text = False

            #checking for the whole delimeters
            if "BD" not in self.code[0]:
                self.errors.append("Broken file! BD is missing")
            for line in self.code[::-1]:
                line = line.translate({ord(c): None for c in string.whitespace})
                if len(line) == 0:
                    continue
                if line != "ED":
                    self.errors.append("Broken file! ED is missing or text after ED")
                break

            self.build_analysator()
            super().analysis()

        except Exception as e:
            errors.append(f"Ananlysis error {e}")




    def synthesis(self):
        try:
            self.unparsible = []
            self.toolchange_cntr = 0
            self.ngcode += "%\n"
            self.ngcode += self.header_gen()
            self.ngcode += self.move_subroutine
            subr = 3
            punch_on     = False
            trail_on     = True

            for section in self.sections:
                if section == "PROGRAMM" or section == "EINRICHTEPLAN_INFO" \
                or section == 'WZG_CALLS' or 'DA' not in self.sections[section]\
                or section == "WZG_STAMM":
                    continue
                total_datas = 0
                for config in self.sections[section]:
                    if config == "MM" or config == 'DA' or config == 'pname' or config == 'param_file_name':
                        continue
                    if len(self.sections[section][config]) != int(self.sections[section]["MM"])- 1:
                        self.errors.append("Bad number of parameters of section {0} of group {1}".format(section, config))
                        continue
                    self.ngcode += 'o{0} sub\n'.format(subr)
                    self.ngcode += "; apply parameters of section {0} of group {1}\n".format(section, config)
                    self.ngcode += 'M199 P{0}\n'.format(self.sections[section]["param_file_name"])
                    for i in range(len(self.sections[section][config])):
                        if not self.sections[section][config][i].replace('.', '', 1).replace('-', '', 1).isdigit():
                            self.ngcode += ';'
                        # ngcode += 'N{2} #<_{3}_{0}> = {1}'.format(i + 1, sections[section][config][i], i+1, sections[section]['pname'])
                        self.ngcode += 'N{2} M198 P{0} Q{1}'.format(i + 1, self.sections[section][config][i], i+1)
                        self.ngcode +='\n'
                        if not self.sections[section][config][i].replace('.', '', 1).replace('-', '', 1).isdigit():
                            self.ngcode += ';'
                        self.ngcode += 'N{2} #<_{3}_{0}> =  {1}'.format(i + 1, self.sections[section][config][i], 
                                                                   i + 2, self.sections[section]['pname'])
                        self.ngcode +='\n'
                    self.ngcode += 'o{0} endsub\n'.format(subr)
                    self.subroutines[config] = subr
                    subr += 1
                    total_datas += 1
                if total_datas != int(self.sections[section]["DA"]):
                    self.errors.append("Bad number of groups in of section {0} ".format(section))
        
        # subroutines (wtf)

            self.subroutines_num = 0
            for sub in self.sections['PROGRAMM']:
                if sub == "WZG_STAMM":
                    continue
                if sub == self.main_programme or sub == "MM" or sub == 'DA' or sub == 'pname' or sub == 'param_file_name':
                    continue
                # sections['PROGRAMM'][sub].append(subr)
                self.subroutines[sub] = subr
                sub_pattern = f'([^\"]|^){sub[1:-1]}([^\"]|$)'
                sub_f = lambda x, sub=copy(sub) : ('\no{0} call\n'.format(self.subroutines[sub]), x[1]+x[2], "OK" )
                self.add_rule(sub_pattern, sub_f)

                self.ngcode += '; subroutine {0}: \n'.format(sub)
                self.ngcode += 'o{0} sub\n'.format(subr)
                for line in self.sections["PROGRAMM"][sub][-1]:
                    verdict, processed_line = self.process_re(line)
                    if re.sub("skip", "", verdict) == "":
                        continue
                    if "unparsible" in verdict:
                        self.unparsible.append(line)

                    if "TRAILON" in verdict:
                        trail_on  = True

                    if  "MOVE" in verdict:
                        processed_line = self.move_prepare(processed_line)

                    self.ngcode += processed_line + '\n'

                    
                self.ngcode += 'o{0} endsub\n'.format(subr)
                subr += 1
                self.subroutines_num += 1


            self.ngcode += self.defaults
            for line in self.sections["PROGRAMM"][self.main_programme][-1]:
                verdict, processed_line = self.process_re(line)
                if re.sub("skip", "", verdict) == "":
                    continue
                if "unparsible" in verdict:
                    self.unparsible.append(line)

                if "TRAILON" in verdict:
                    trail_on  = True

                if  "MOVE" in verdict:
                    processed_line = self.move_prepare(processed_line)

                self.ngcode += processed_line + '\n'


            # ngcode += 'o{0} endsub\n'.format(1)
            if self.toolchange_cntr > 0:
                self.ngcode +=f" o{100 + self.toolchange_cntr} endif \n"

            self.ngcode += "%\n"  
        except Exception as e:
            self.errors.append(f"Synthesis error: {e}")