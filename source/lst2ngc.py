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

N_automata = re.compile("\s*N(\d+).*")
comm_automata = re.compile(";.*")


symbols = {
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


class Converter:
    """
    This class is used to end-to-end converting LST trumph file intro rs274 .ngc file
    """
    def __init__(self, lst_filepath=None, ngc_filepath=None):
        self.lineno         = True
        self.errors         = []
        self.unparsible     = []
        self.subroutines    = {}
        self.delimeters     = {}
        self.sections       = {}
        self.input_file     = lst_filepath
        self.output_file    = ngc_filepath
        self.toolchange_cntr = 0
        self.status         = "ready"
        self.ngcode         = ""
        self.code           = ""
        sections ={
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

       
        self.load_data()
        self.processor = self.build_processor()

    def build_processor(self):
        """
        Returns a dict of type 
            matcher(regexp) : function(match object)

        when matcher is found in program line, the function
        Function must return a tuple (what we want to add to NGC code, with what we want to replace out match with, verdict)
        """

        processor = {}
        
        # removing comments
        Commment     = r"\s*(;.*)"
        def Comm_proc(match):
            # return match[1] + '\n', ""
            return "", "", "skip"
        processor[Commment] = Comm_proc

        # handling line numbers
        N_word       = r"^\s*N(\d+)"
        def N_proc(match):
            N_word = match[1]
            if self.lineno:
                return match[0], "", "skip"
            return "", ""
        processor[N_word] = N_proc

        #operator's messages
        Message      = r'\s*MSG\s*\(\s*"([^"]*)"\s*\)'
        def Message_proc(match):
            message = match[1]
            return f"(MSG, {message})\n", "", "skip"
        
        # simple bijective replacements
        for code in self.codes_renames.keys():
            processor[f"({code})(\D)"] = lambda x, code=copy(code): (self.codes_renames[code],  x[2], "OK")
            
        #coordinates
        float_patern = r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
        
        for coord in ["F", "X", "Y", "I", "J", "SPP="]:
            coord_pattern = coord + float_patern
            verd = "OK"
            if coord != 'F' and coord != "SPP=":
                verd = "MOVE"
            processor[coord_pattern] = lambda x,coord=copy(coord), verd=copy(verd): (f"{coord}{x[1]}", "", verd )

        #rotary coordinates -- forced to move simultaneously
        rotary_pattern = r"C[12]\s*=DC\(" + float_patern + "\s*)"
        processor[coord_pattern] = lambda x: ("A" + x[1] + "B" + x[1], "", "MOVE" )

        # tool selection
        toolno_pattern = 'TC_TOOL_NO\s*\(\s*\"(\d+)\"\s*\)'
        def Toolno_proc(match):
            goodline=""
            toolcode = "'" + match[1] + "'"
            if self.toolchange_cntr > 0:
                goodline +=f" o{100 + self.toolchange_cntr} endif \n"
            self.toolchange_cntr += 1
            goodline +=f" o{100 + self.toolchange_cntr} if [#<_start_from> LE {self.toolchange_cntr}]\n"
            goodline +=f"T#<_TOOL_{self.sections['WZG_CALLS'][toolcode][0]}>"
            return goodline, "", "OK"
        processor[toolno_pattern] = Toolno_proc
                    
       
        for key in self.groups:
            values = self.groups[key]
            pattern = key + "\s*\(\s*\"([^\"]+)\"\s*\)"
            goodline = ' ;appply {0} parameters {1} \n o{2} call\n{3}'
            processor[pattern] = lambda x, key=copy(key),values=copy(values): (goodline.format((
                key,
                x[1],
                str(self.subroutines[x[1]]),
                values[1]
                )),
                "",
                "OK"
                ) 
        
        #TC_POS_ACCEL
        accel_patern = r"TC_POS_ACCEL\s*\(\s*"+ float_patern + r"\s*,\s*" + float_patern + r"\s*,\s*" + float_patern + r"\s*,\s*" + float_patern + r"\s*\)"
        
        processor[accel_patern] = lambda x: (f' ;acceleration: {x[1]},{x[5]},{x[9]},{x[13]}\n', "", "OK")

            
        # trailon pattern
        trailon_pattern=r"TRAILON\(C[12],C[12]\)"
        processor[trailon_pattern] = lambda x: ("","", "TRAILON")
            
        #PUNCH_ON / PUNCH_OFF
        processor['PUNCH_ON']=lambda x: (" #<_PUNCH> = 1\n", "", "PON")
        processor['PUNCH_OFF']=lambda x: (" #<_PUNCH> = 0\n", "", "POFF")
            
        # NIBBLE_ON / NIBBLE_ON
        processor['NIBBLE_ON']=lambda x: (" #<_NIBBLING> = 1\n", "", "NON")
        processor['NIBBLE_OFF']=lambda x: (" #<_NIBBLING> = 0\n", "", "NOFF")
        
        
        # TANGTOOL
        processor["TC_TANGTOOL_OFF"] = lambda x: ("#<_TANGTOOL_EN>=0\n#<_TANGTOOL_P>=0", "", "OK")
        processor[r"TC_TANGTOOL_ON\s*\(\s*("+float_patern+r")\s*"] = lambda x: (f"#<_TANGTOOL_EN>=1\n#<_TANGTOOL_P>={x[1]}", "", "OK")

        #skipped codes
        processor["TC_CLAMP_CYC"] = lambda x: ("","", "skip")
        processor["M17"] = lambda x: ("","", "skip")
        
        # subroutine call
        for sub in self.subroutines:
            sub_pattern = f'[^\"]{sub[1:-1]}[^\"]'
            processor[sub_pattern] = lambda x, sub=copy(sub) : ('o{0} call'.format(self.subroutines[sub]), "", "OK" )
        
        return processor


    def process_re(self, line):
        line = line + " "
        goodline = ""
        verdict  = ""
        for pattern in self.processor:
            match = re.search(pattern, line)
            if match:
                gl, rep, verd = self.processor[pattern](match)
                line = re.sub(pattern, rep, line, count=1)
                goodline += gl + " "
                verdict  += verd

                # replacing many whitespaces with 1 space and check if line is not empty
                line = re.sub("\s+", " ", line)

        if len(line) == 0 or re.fullmatch("\s*", line):
            return verd, goodline, 100

        return "unparsible", (line, 100)


    def load_data(self):
        try:
            # Simple replacements
            file = codecs.open(f'{os.path.realpath(os.path.dirname(__file__))}/../data/simple_replacements.txt','r',encoding='utf-8')
            contents = file.read()
            self.codes_renames = ast.literal_eval(contents)
            file.close()

            # Tech parameters
            file = codecs.open(f'{os.path.realpath(os.path.dirname(__file__))}/../data/technology_groups.txt','r',encoding='utf-8')
            contents = file.read()
            self.groups = ast.literal_eval(contents)
            file.close()

            # o2 subroutine
            f = codecs.open(f'{os.path.realpath(os.path.dirname(__file__))}/../data/o2sub.txt','r',encoding='utf-8')
            code = f.readlines()
            f.close()
            self.move_subroutine = "".join(code)
            # print(move_subroutine)

            f = codecs.open(f'{os.path.realpath(os.path.dirname(__file__))}/../data/defaults.txt','r',encoding='utf-8')
            code = f.readlines()
            f.close()
            self.defaults = "".join(code)

            # Regexpr's
            # TODO

            self.coord_rename = {"C1":" A", "C2":" B"}

        except:
            self.errors.append("can not open data file")
            self.status = "error"

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
        except:
            self.errors.append("failed to process move__prepare")
            self.status = 'error'

    def del_check(self, line : str):
        for delim in self.delimeters:
            if delim in line:
                self.delimeters[delim] = True

    def process(self, line ):
        # need to be rewritten with regexp
        goodline = ""
        N_word   = ""
        
        # removing comments
        i = line.find(';')
        if i >= 0:
            line = line[:i]
        if line[-1] == '\n':
            line = line[:-1]
        if len(line) == 0:
            return "skip", line
        i = 0 # число обработанных символов
        ll = len(line)
        # line numbers
        if line[0] == "N":   
            i=1
            while i < ll and line[i].isdigit():
                i+=1
            goodline+= line[:i] + "00"
            N_word = int(line[1:i], 10)*100

        if i >= ll:
            return  "skip" ,goodline
        # сообщение оператору
        if 'MSG' in line:
            i += 1
            left = line.find('"')
            right = line.find('"', left + 1)
            msg = line[left + 1: right]
            goodline += ' (MSG, ' + msg + ')'
            return 'OK', goodline
        
        # собственно кадр:
        verd = "OK"
        
        for code in self.codes_renames.keys():
            left = line.find(code)   
            if(left >= 0 and left < ll and (left+len(code) == ll or not line[left+len(code)].isdigit())):
                goodline += self.codes_renames[code]
                i+=len(code)
        
        # common coordinates
        for coord in ["F", "X", "Y", "I", "J", "SPP="]:
            left = line.find(coord)
            lc = len(coord)
            if left >= 0 and left + lc< ll and (left == 0 or line[left-1].isdigit()) and (line[left+lc].isdigit() or line[left+lc] == '-') :
                right = left + lc
                if right < ll and line[right] =='-':
                    right+=1
                while right < ll and line[right].isdigit():
                    right+=1
                if right < ll and line[right] =='.':
                    right+=1
                    while right < ll and line[right].isdigit():
                        right+=1
                if coord == "SPP=":
                    goodline+= ' #<_SPP> = ' + line[left + lc:right]
                else:
                    goodline+= ' ' + line[left:right]
                i += right - left
                if coord != 'F' and coord != "SPP=":
                    verd += "MOVE"
                
        # rotary coordinates
        for coord in ["C1", "C2"]:
            left = line.find(coord)
            if left >= 0 and left + 1< ll and (left == 0 or line[left-1].isdigit()) and (line[left+1].isdigit() or line[left+1] == '-') :
                left = line.find('(', left) + 1 #работает только когда C1 задается исключительно в виде DC(...)
                right = left + 1
                if right < ll and line[right] =='-':
                    right+=1
                while right < ll and line[right].isdigit():
                    right+=1
                if right < ll and line[right] =='.':
                    right+=1
                    while right < ll and line[right].isdigit():
                        right+=1
                goodline+= self.coord_rename[coord] + line[left:right]
                i += right - left + 7
                verd += 'MOVE'
        
        # Tool select
        if 'TC_TOOL_NO' in line:
            left     = line.find('"')
            right    = line.find('"', left + 1)
            toolcode = "'" + line[left+1: right ] + "'"
            if self.toolchange_cntr > 0:
                goodline +=f" o{100 + self.toolchange_cntr} endif \n"
            self.toolchange_cntr += 1
            goodline +=f" o{100 + self.toolchange_cntr} if [#<_start_from> LE {self.toolchange_cntr}]\n"
            goodline +=' T' + f"#<_TOOL_{self.sections['WZG_CALLS'][toolcode][0]}>"
            i = ll
            
       
        for key in self.groups:
            values = self.groups[key]
            if key in line:
                left     = line.find('"')
                right    = line.find('"', left + 1)
                ttcode = "'" + line[left + 1: right] + "'"
                goodline +=' ;appply ' + key + ' parameters' + ttcode + ' \n'
                goodline +=' o{0} call\n'.format(str(self.subroutines[ttcode])) 
                goodline +='N' + str(N_word + 1) + values[1] # + '\n';
                i = ll
        
        
        #TC_POS_ACCEL
        if 'TC_POS_ACCEL' in line:
            left     = line.find('(')
            right    = line.find(')', left + 1)
            toolcode = line[left + 1: right]
            goodline +=' ;acceleration: ' + toolcode
            i = ll
            
        left = line.find("TRAILON(C2,C1)")
        if(left >= 0 and left < ll and left+14==ll):
            i+=14
            goodline += " ;TRAILON"
            verd += "TRAILON"
            
        #PUNCH_ON / PUNCH_OFF
        if 'PUNCH_ON' in line:
            i+=8
            verd += "PON"
            # goodline += ' ;start punching'
            goodline += " #<_PUNCH> = 1\n";
           # goodline +='N' + str(N_word + 2) + " M165" # + '\n';
            
        if 'PUNCH_OFF' in line:
            i+=9
            verd += "POFF"
            # goodline += ' ;stop punching'
            goodline += " #<_PUNCH> = 0\n"
           # goodline +='N' + str(N_word + 2) + " M164" # + '\n';

            
        #NIBBLE_ON / NIBBLE_ON
        if 'NIBBLE_ON' in line:
            i+=9
            verd += "NON"
            # goodline += ' ;start punching'
            goodline += " #<_NIBBLING> = 1\n"
           # goodline +='N' + str(N_word + 2) + " M165" # + '\n';
            
        if 'NIBBLE_OFF' in line:
            i+=10
            verd += "NOFF"
            # goodline += ' ;stop punching'
            goodline += " #<_NIBBLING> = 0\n"
           # goodline +='N' + str(N_word + 2) + "M164" # + '\n';

        
        if "TC_TANGTOOL_OFF" in line:
            i+=15
            goodline += " #<_TANGTOOL_EN>=0\n"
            goodline += 'N' + str(N_word + 1) + " #<_TANGTOOL_P>=0"

        if "TC_TANGTOOL_ON" in line:
            left = line.find("TC_TANGTOOL_ON(")
            left  = left + 15
            right = line.find(")", left)
            goodline += " #<_TANGTOOL_EN>=1\n"
            goodline += 'N' + str(N_word + 1) + " #<_TANGTOOL_P>=" + line[left:right]
            i+= right - left + 16

        
         ################ ТО ЧТО ПОКА ПРОПУСКАЕТСЯ ######################
        
        
        left = line.find("TC_CLAMP_CYC")
        if(left >= 0 and left < ll and left+12==ll):
            i+=12
            goodline += " ;TC_CLAMP_CYC"
        
        left = line.find("M17")
        if(left >= 0 and left < ll and left+3==ll):
            i+=3
            goodline += " \n;M17\n"
        
        # subroutine call
        for sub in self.subroutines:
            if sub[1:-1] in line and not '"' + sub[1:-1] + '"' in line:
                goodline += '\n o{0} call'.format(self.subroutines[sub])
                i += len(sub) - 2
        
        
        if(i == ll):
            return verd, (goodline, N_word)
        
        return "unparsible", line

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

            subroutines_num = 0
            for sub in self.sections['PROGRAMM']:
                if sub == "WZG_STAMM":
                    continue
                if sub == self.main_programme or sub == "MM" or sub == 'DA' or sub == 'pname' or sub == 'param_file_name':
                    continue
                # sections['PROGRAMM'][sub].append(subr)
                self.subroutines[sub] = subr
                self.ngcode += '; subroutine {0}: \n'.format(sub)
                self.ngcode += 'o{0} sub\n'.format(subr)
                for line in self.sections["PROGRAMM"][sub][-1]:
                    verdict, processed_line = process_re(line)
                    if re.sub("skip", "", verdict) == "":
                        continue
                    if "unparsible" in verdict:
                        self.unparsible.append(line)

                    if "TRAILON" in verdict:
                        trail_on  = True

                    if  "MOVE" in verdict:
                        cl = move_prepare(processed_line)

                    self.ngcode += cl + '\n'

                    
                self.ngcode += 'o{0} endsub\n'.format(subr)
                subr += 1
                self.subroutines_num += 1

            self.ngcode += self.defaults

            for line in self.sections["PROGRAMM"][self.main_programme][-1]:
                (verdict, cl) = self.process(line)
                # print(cl)
                if(type(cl) == tuple):
                    NW = cl[1]
                    cl = cl[0]
                if(verdict == "skip"):
                    continue
                if(verdict == "unparsible"):
                    self.unparsible.append(line)

                if "TRAILON" in verdict:
                    trail_on  = True
                if trail_on:
                    left = cl.find('A')
                    # print(cl, left, len(cl))
                    if left >= 0 and left + 1< len(cl) and (left == 0 or cl[left-1] == ' ') and (cl[left+1].isdigit() or cl[left+1] == '-') :
                        right = left + 1
                        if right < len(cl) and cl[right] =='-':
                            right+=1
                        while right < len(cl) and cl[right].isdigit():
                            right+=1
                        if right < len(cl) and cl[right] =='.':
                            right+=1
                        while right < len(cl) and cl[right].isdigit():
                            right+=1
                        cl+= ' B' + cl[left+1:right]
                if  "MOVE" in verdict:
                    cl = self.move_prepare(cl)
                self.ngcode += cl + '\n'

            # ngcode += 'o{0} endsub\n'.format(1)
            if self.toolchange_cntr > 0:
                self.ngcode +=f" o{100 + self.toolchange_cntr} endif \n"

            self.ngcode += "%\n"  
        except Exception as e:
            self.errors.append(f"Synthesis error: {e}")
                            
    def analysis(self):
        """
        Read the file and fills internal structures
        """
        try:
            self.delimeters = {}
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

            current_conf = ""
            text = False
            
            for section in self.sections:
                self.delimeters["BEGIN_" + section]  = False
                self.delimeters["ENDE_" + section]  = False
            
            if "BD" not in self.code[0].translate({ord(c): None for c in string.whitespace}):
                self.errors.append("Broken file! BD is missing")
            for line in self.code[::-1]:
                line = line.translate({ord(c): None for c in string.whitespace})
                if len(line) == 0:
                    continue
                if line != "ED":
                    self.errors.append("Broken file! ED is missing or text after ED")
                break
                                    

            
            for line in self.code[1:-1]:
                # removing newline characters and whitespaces
                line = line.translate({ord(c): None for c in string.whitespace})
                # throwing the trash away
                if 'MM,AT,1,' in line or line == 'C\n' or len(line) == 0:
                    continue
                 # check for file delimeters 
                self.del_check(line)
                current_section = ""
                for section in self.sections:
                    if self.delimeters["BEGIN_" + section] and not self.delimeters["ENDE_" + section]:
                        current_section = section
                # if current_section == "WZG_STAMM":
                    # continue
                
                if(line == "START_TEXT"):
                    text = True            
                    self.sections[current_section][current_conf].append([])
                    continue
                if(line == "STOP_TEXT"):
                    text = False
                if text:
                    self.sections[current_section][current_conf][-1].append(line)
                             
                        
                if("ZA" in line):
                    _line = line.split(",")
                    self.sections[current_section][_line[1]] = _line[2]
                    continue
                if("DA" in line):
                    _line = line.split(",")
                    current_conf  = _line[1]
                    self.sections[current_section][current_conf] = _line[2:]
                    continue
                if(line[0] == '*'):
                    _line = line[1:].split(",")
                    self.sections[current_section][current_conf] = self.sections[current_section][current_conf][:-1]
                    self.sections[current_section][current_conf].extend(_line)
                    continue
        except Exception as e:
            self.errors.append(f"Analysis failed: {e} ")
            
    def load_lst(self, lst_filename):
        try:
            with open(lst_filename) as f:
                self.code = f.readlines()
                f.close()
        except:
            self.errors.append(f"can not load LST file {lst_filename}")
            self.status = "error"

    def save_ngc(self, ngc_filename):
        try:
            f = codecs.open(ngc_filename,'w',encoding='utf-8')
            f.writelines(self.ngcode)
            f.close()
        except:
            self.errors.append(f"can not load LST file {lst_filename}")
            self.status = "error"

    def convert(self, lst_filename, ngc_filename):
        try:
            self.__init__(lst_filename, ngc_filename)
            
            self.load_lst(self.input_file)
            if len(self.errors) == 0:
                print("loading ok")
            
            self.analysis()
            if len(self.errors) == 0:
                print("analysis ok")
            
            self.synthesis()
            if len(self.errors) == 0:
                print("synthesis ok")
            
            self.save_ngc(self.output_file)
            if len(self.errors) == 0:
                print("saving ok")
            
            self.status = 'ok'
        except:
            self.status = "error"

