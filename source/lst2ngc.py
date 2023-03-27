from general_converter import Converter
from copy import copy
import pandas as pd
import re

float_patern = r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"

symbols = {     0: 'N',
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

def param_section_process(self=None):
    try:
        if self.metadata['config_num'] == 0:
            return
        # TODO: add check for number of config and number of parameters in config
        for conf_name in self.config.index:
            # print(f"CONFIG: {conf_name}")

            assert self.converter.subroutines[self.name, conf_name] == self.config.loc[conf_name].subroutine_no, "internal error qith planning subr no"
            # subr = self.converter.subroutines[conf[1]]
            subr = self.config.loc[conf_name].subroutine_no
            self.o_code += [f'o{subr} sub']
            self.o_code += [f"    ; apply parameters of section {self.name} of group {conf_name}"]
            self.o_code += [f'    M199 P{self.param_fileno}']
            for param_name in self.required_params:
                assert param_name in self.config.loc[conf_name].index, f"required param {param_name} not found in conf {conf_name}"
                # check if param is correct
                param_no    = self.required_params[param_name]
                param_value = self.config.loc[conf_name, param_name]
                # print(param_name, param_no, param_value)
                assert re.match(float_patern, param_value), "param excepted to be float"
                
                # adding parameter to file storage
                self.o_code += [ f'    M198 P{param_no} Q{param_value}' ]
                
                # adding parameter to interpreter memory
                self.o_code += [ f'    #<_{self.pname}_{param_no}> =  {param_value}' ]

            self.o_code += [ f'o{subr} endsub\n' ]            
    except Exception as e:
        self.converter.errors.append(f"Error processing section {self.name}: {e}")



def PROGRAMM_process(self=None):
    try:
        for subr_name in self.config.index:
            conf = self.config.loc[subr_name,'Bearbeitungszeit'].split("\n")
            assert re.match(r"\s*START_TEXT\s*", conf[0]), f"START_TEXT missing in sub {subr_name}"
            assert re.match(r"\s*STOP_TEXT\s*", conf[-1]), f"STOP_TEXT missing in sub {subr_name}"
            assert self.name, subr_name in self.converter.subroutines
            self.o_code.append(f"\no{self.converter.subroutines[self.name, subr_name]} sub")
            self.o_code.append(f"    ;definition of {subr_name} subroutine")
            for line in conf[1:-1]:
                line = line.strip()
                verdict, processed  = self.process_line(line)
                good_line = self.post_processor(verdict, processed)
                if not re.fullmatch(r"\s*", good_line):
                    self.o_code.append("   " + good_line)
                if(len(self.converter.errors) > 0):
                    return
            self.o_code.append(f"\n o{self.converter.subroutines[self.name, subr_name]} endsub")
    except Exception as e:
        self.converter.errors.append(f"Synthesis section {self.name} error: {e}")



def split_sections_data(self = None):
    try:
        assert "param_num" in self.metadata, f"param_num not found !"
        assert self.metadata["param_num"] == len(self.param_names), "bad number of params"
        assert "config_num" in self.metadata and  len(self.data) == self.metadata['config_num'], f"conf_num mismatched with parsed number of configs !"
        
        self.conf_names = []
        self.param_names += ["subroutine_no"]

        if self.name == "WZG_STAMM":
            self.param_names = self.param_names[1:]
            self.metadata['param_num'] -= 1

        for i, conf in enumerate(self.data):
            assert len(conf) - 1 == self.metadata['param_num'], f"parsed param number {len(conf)} mismatches with declared one{self.metadata['param_num']}"
            
            c_name = conf[1]
            self.data[i] = conf[2:]
            
            assert c_name not in self.conf_names or self.name == 'WZG_CALLS', f"non-unique conf {c_name} in section {self.name}"
            self.conf_names.append(c_name)
            
            subr = self.converter.subroutines[(self.name, c_name)]
            self.data[i].append(subr)

        self.config =  pd.DataFrame(data=self.data, index=self.conf_names, columns=self.param_names[1:])


    except Exception as e:
        self.converter.errors.append(f"Error while splitting confs of section {self.name}: {e}")


def header_gen(self = None):
        try:
            assert len(self.converter.sections['EINRICHTEPLAN_INFO'].data) == 1, "main programm number is not 1"
            self.o_code += [ self.converter.config['defaults']['move_subroutine'] ]
            self.o_code += [ "\n\n;###############################################################################" ]
            self.o_code += [ f";Machine name:    {self.converter.sections['EINRICHTEPLAN_INFO'].config.iloc[0].loc['Firma']}" ]
            self.o_code += [ f";Pragrammer name: {self.converter.sections['EINRICHTEPLAN_INFO'].config.iloc[0].loc['Bearbeiter']}" ]
            self.o_code += [ f";Date:            {self.converter.sections['EINRICHTEPLAN_INFO'].config.iloc[0].loc['Datum']}" ]
            self.o_code += [ f";File:            {self.converter.sections['EINRICHTEPLAN_INFO'].config.iloc[0].loc['Tafelname']}" ]
            self.o_code += [ f";Material:        {self.converter.sections['EINRICHTEPLAN_INFO'].config.iloc[0].loc['Material-ID']}" ]
            self.o_code += [ self.converter.config['defaults']['g_code_defaults'] ]
            main_subr_name = self.converter.sections['EINRICHTEPLAN_INFO'].config.iloc[0].loc['Programmnummer (ohne P!)']
            main_subr_no = self.converter.subroutines["PROGRAMM",   main_subr_name]
            self.o_code += [ f"o{main_subr_no} call" ]
            self.o_code += [ "M2" ]
        except Exception as e:
            self.converter.status = 'error'
            self.converter.errors.append(f'Failed to generate header: {e}')

def postprocessor(verdict, line, conv= None):
    '''
        Handling or vericts
    '''
    try:
        if re.fullmatch(r"\s*(?:N\d+)?\s*", line):
            return ""
        if "MOVE" in verdict:
            line = re.sub(r"\s+", " ", line)
            move_params  = {}
            _line = line.strip().split(' ')
            for _ in _line:
                if _[0] != 'G':
                    move_params[_[0]] = _[1:]
                else:
                    move_params[_] = 1
            call = ' o2 call '
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
        return line
    except Exception as e:
        if conv is not None:
            conv.errors.append(f"Error during move_prepare: {e} while processing {_line}")
        else:
            print(f"Error during move_prepare: {e}")


class LST2NGC(Converter):
    def __init__(self, config={}):
        try:
            super().__init__(config=config)
            self.toolchange_cntr = 0
            self.text = False
            self.subroutine_no  = 3
            self.subroutines  = {"'1'":1, "move":2}
            self.restore_defaults()
            self.build_analysator()
        except:
            self.errors.append("unable to init LST2NGC")

    def restore_defaults(self):
        try:    
            self.sections = {}
            default_sections ={
                        "WZG_CALLS" : { 
                            "pname":0,
                            "param_file_name": -1,
                            "required": {
                                'Werkzeugaufrufnummer':1
                                }
                            }, 

                        "PTT"       : {
                            "pname":"PTT", 
                            "param_file_name": 1,
                            "required": {
                                            'OT-Offset':5,
                                            'UT-Offset':6,
                                            'TRUMPF-Kennung':8
                                        }
                            
                            },

                        "SHEET_TECH": {
                            "pname":"SHT", 
                            "param_file_name": 2,
                            "required": {
                                            'Blechmass Z' : 3,
                                            'Magazinplatz Pratze 1':9, 
                                            'Magazinplatz Pratze 2':10,
                                            'Magazinplatz Pratze 3':11, 
                                            'Magazinplatz Pratze 4':12,
                                            'Magazinplatz Pratze 5':15, 
                                            'Magazinplatz Pratze 6':16,  
                                        }
                            },

                        "SHEET_LOAD": {
                            "pname":"SHL", 
                            "param_file_name": 4,
                            "required": {
                                            'Beladeposition X':1,
                                            'Beladeposition Y':2,
                                            'Vorschub zur Beladeposition':3,
                                            'Anschlagstift':19
                                        }
                            }, 
                        "SHEET_UNLOAD"        : {
                            "pname": "SHU",
                            "param_file_name": 5,
                            "required": {
                                            'Entladeposition X':1,
                                            'Entladeposition Y':2,
                                            'Vorschub zur Entladeposition':3
                                        } 
                            },
                        
                        "PART_UNLOAD"         : {
                            "pname": "PAU",
                            "param_file_name": 6,
                            "required": {
                                            'Ausschiebeweg X':4,
                                            'Ausschiebeweg Y':5,
                                            'Ausschiebevorschub':6,
                                            'Handentsorgung':12,
                                            'Kuebel Ablageort':20
                                        }
                            },
                        
                        "EINRICHTEPLAN_INFO"  : {
                            "pname": "",
                            "param_file_name": -1,
                            "required":{}
                            },
                        
                        "PROGRAMM"            : {
                            "pname": 0,
                            "param_file_name": -1,
                            "required":{}
                            },
                        
                        "WZG_STAMM"           : {
                            "pname": "WST",
                            "param_file_name": -1,
                            "required":{                                        }
                            },
                        
                        "SHEET_REPOSIT"       : {
                            "pname": "RPO",
                            "param_file_name": 7,
                            "required":{
                                            'Nachsetzweg X':1,
                                            'Nachsetzweg Y':2,
                                            'Nachsetzvorschub':3
                                       }
                            }
                     }
            for section_name in default_sections:
                self.add_section(
                    section_name,
                    (
                        "BEGIN_"+section_name,
                        "ENDE_"+section_name
                    ),
                    )
                self.sections[section_name].pname = default_sections[section_name]["pname"]
                self.sections[section_name].param_fileno = default_sections[section_name]["param_file_name"]
                self.sections[section_name].required_params = default_sections[section_name]["required"]

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
                'PRESSERFOOT_ON':' #<_PRESSERFOOT_ON> = 1\n   M165 P#<_PRESSERFOOT_ON>',
                'PRESSERFOOT_OFF':' #<_PRESSERFOOT_ON> = 0\n   M165 P#<_PRESSERFOOT_ON>',
                'G90':' G90',
                'G91':' G91',
                'G53':' G53'
            }
            self.groups = {
                'TC_TOOL_TECH'     : ["PTT", "M153 \n    M165 P#<_PRESSERFOOT_ON>"],
                'TC_SHEET_TECH'   : ["SHEET_TECH", "M153"],
                'TC_SHEET_LOAD'   : ["SHEET_LOAD", "M651"],
                'TC_SHEET_UNLOAD' : ["SHEET_UNLOAD", "M652"],
                'TC_PART_UNLOAD'  : ["PART_UNLOAD", "M667"],
                'TC_SHEET_REPOSIT': ['SHEET_REPOSIT', " M610"]
            }
            self.coord_rename = {"C1":" A", "C2":" B"}
            
            
        except Exception as e:
            self.errors.append(f"Error in loading consts: {e}")
            self.status = "error"

    def prepare(self):
        super().prepare()

        # for normal G-code lines
        program_rules = self.PROGRAMM_rules()
        for rule in program_rules:
            self.sections["PROGRAMM"].add_processor_rule(rule, program_rules[rule])
        self.sections["PROGRAMM"].process = lambda self=self.sections["PROGRAMM"]: PROGRAMM_process(self)
        self.sections["PROGRAMM"].post_processor = lambda verd, line, conv=self: postprocessor(verd, line, conv=conv)
        # for TRUMPH param sections
        for section_name in ["PTT", "SHEET_TECH", "SHEET_LOAD", "SHEET_UNLOAD", "PART_UNLOAD",  "SHEET_REPOSIT"]:
            self.sections[section_name].process = lambda sec=self.sections[copy(section_name)]: param_section_process(self=sec)

        for section_name in self.sections:
            self.sections[section_name].metadata = {'param_num': 0, 'config_num': 0}
            self.sections[section_name].param_names = []
            self.sections[section_name].add_processor_rule(r"^\s*C\s*$", lambda x:("","","ok"))
            self.sections[section_name].post_analyse = lambda sec=self.sections[copy(section_name)]: split_sections_data(self=sec)
            if section_name != 'main' and section_name != "PROGRAMM":
                self.sections[section_name].add_processor_rule(r"^.*\n? ?$", lambda x:("","","ok"))
        
        self.sections["main"].process = lambda ss=self.sections['main']: header_gen(ss)   


    def PROGRAMM_rules(self):
        """
            Prepares a dict of type 
                (regexp) : function(match object)

                specifed to operate with TOPS LST

            when matcher is found in program line, the function is called.

            Function must return a tuple (what we want to add to NGC code, with what we want to replace out match with, verdict)
            """            
            

        try:
            rules = {}
            
            # removing comments
            rules[r"\s*(;.*)"] = lambda x: ("","", "skip")

            # handling line numbers
            def N_proc(match):
                N_word = match[1]
                if self.lineno == "keep":
                    return match[0], "", "skip"
                return "", "","skip"
            rules[r"^\s*N(\d+)"] = N_proc

            #operator's messages
            rules[ r'\s*MSG\s*\(\s*"([^"]*)"\s*\)' ] = lambda x: (f"(MSG, {x[1].replace(',','')})", "", "skip")
            
            # simple bijective replacements
            for code in self.codes_renames.keys():
                rules[f"({code})(\D)"] = lambda x, code=copy(code): (self.codes_renames[code],  x[2], "OK")                
                
            #coordinates
            for coord in ["F", "X", "Y", "I", "J", "SPP="]:
                coord_pattern = coord + float_patern
                verd = "OK"
                if coord != 'F' and coord != "SPP=":
                    verd = "MOVE"
                rules[ coord_pattern ] = lambda x,coord=copy(coord), verd=copy(verd): (f"{coord}{x[1]}", "", verd )

            #rotary coordinates -- forced to move simultaneously
            rules[ r"C[12]\s*=DC\(" + float_patern + r"\s*\)"] = lambda x: ("A" + x[1] + " B" + x[1], "", "MOVE" )

            # tool selection
            def Toolno_proc(match):
                goodline=""
                toolcode = "'" + match[1] + "'"
                # goodline += f"    T#<_TOOL_{tool_code}>"
                if self.config != {}  and self.config['behaviour'].getboolean("start_from"):
                    if self.toolchange_cntr > 0:
                        goodline +=f" o{100 + self.toolchange_cntr} endif \n"
                    self.toolchange_cntr += 1
                    goodline += f" o{100 + self.toolchange_cntr} if [#<_hal[start_from]> LE {self.toolchange_cntr}]\n"
                tool_code = self.sections['WZG_CALLS'].config.loc[toolcode, 'Werkzeugaufrufnummer']
                if type(tool_code) is not str:
                    tool_code = tool_code.max()
                goodline += "    (MSG, " + self.sections['WZG_STAMM'].config.loc[toolcode, "Bemerkung"][1:-1] + ")\n"
                goodline += f"    T#<_TOOL_{tool_code}>"
                return goodline, "", "OK"
            rules[r'TC_TOOL_NO\s*\(\s*\"(\d+)\"\s*\)'] = Toolno_proc
                        
            
            # technology applying
            for key in self.groups:
                values = self.groups[key]
                pattern = key + r'\s*\(\s*\"([^\"]+)\"\s*\)'
                goodline = "   ;appply {0} parameters '{1}' \n    o{2} call\n    {3}"
                rules[pattern] = lambda x, key=copy(key),values=copy(values), goodline=copy(goodline): (goodline.format(
                                        key,
                                        x[1],
                                        str(self.subroutines[values[0], "'" + x[1]+ "'"] ),
                                        values[1]
                                        ),
                                        "",
                                        "OK"
                                        )               

            #TC_POS_ACCEL TC_POS_ACCEL(12.0,5.6,11.7,3.5)

            accel_pattern = r"TC_POS_ACCEL\s*\(\s*"+ float_patern + r"\s*,\s*" + float_patern + r"\s*,\s*" + float_patern + r"\s*,\s*" + float_patern + r"\s*\)"
            rules[accel_pattern] = lambda x: (f' ;acceleration: {x[0]},{x[1]},{x[2]},{x[3]}\n', "", "OK")
            
            

                
            # trailon pattern
            trailon_pattern=r"TRAILON\(C[12],C[12]\)"
            rules[ trailon_pattern] = lambda x: ("","", "TRAILON")
                
            #PUNCH_ON / PUNCH_OFF
            rules['PUNCH_ON']   = lambda x: (" #<_PUNCH> = 1", "", "PON")
            rules['PUNCH_OFF']  = lambda x: (" #<_PUNCH> = 0", "", "POFF")
                
            # NIBBLE_ON / NIBBLE_ON
            rules['NIBBLE_ON']  = lambda x: (" #<_NIBBLING> = 1", "", "NON")
            rules['NIBBLE_OFF'] = lambda x: (" #<_NIBBLING> = 0", "", "NOFF")        
            
            # TANGTOOL
            rules["TC_TANGTOOL_OFF"] = lambda x: ("#<_TANGTOOL_EN>=0\n#<_TANGTOOL_P>=0", "", "OK")
            rules[r"TC_TANGTOOL_ON\s*\(\s*("+float_patern+r")\s*"] = lambda x: (f"#<_TANGTOOL_EN>=1\n#<_TANGTOOL_P>={x[1]}", "", "OK")

            #skipped codes
            rules["TC_CLAMP_CYC"] = lambda x: ("","", "skip")
            rules["M17"] = lambda x: ("","", "skip")
            
            return rules
            
        except Exception as e:
            self.errors.append(f"building processor error : {e}")

    def build_analysator(self):

        try:
            def start_text(match):
                if self.current_section != "PROGRAMM":
                    self.errors.append("START_TEXT in section different with PROGRAMM")
                else:            
                    self.text = True
                    self.temp_text = ""
                    # self.sections[self.current_section].data.append([match[0]])
                    # self.sections[self.current_section].data[-1].append(match[0])


            self.add_analysis_rule(
                r"^\s*START_TEXT\s*$",
                start_text
                ) 

            def stop_text(match):
                if self.current_section != "PROGRAMM":
                    self.errors.append("START_TEXT in section different with PROGRAMM")
                else:           
                    self.sections[self.current_section].data[-1].append(self.temp_text + "STOP_TEXT")
                    self.text = False

            self.add_analysis_rule(
                r"^\s*STOP_TEXT\s*$",
                stop_text
                )


            def add_to_section(match):
                if self.text:
                    if self.current_section != "PROGRAMM":
                        self.errors.append(f"Section changed from PROGRAMM to {self.current_section} before STOP_TEXT")
                    else:
                        self.temp_text += match[0]+ "\n"

            self.add_analysis_rule(
                r".*",
                add_to_section
                )
                

            def set_pnum(match):
                if  self.sections[self.current_section].metadata["param_num"] == 0:
                    self.sections[self.current_section].metadata["param_num"] = int(match[1])
                else:
                    self.errors.append(f">1 ZA,DA in section {self.current_section}")            
            
            self.add_analysis_rule(
                r"^\s*ZA,MM,(\d+)\s*$",
                set_pnum
                )


            def set_confnum(match):
                if self.sections[self.current_section].metadata["config_num"] == 0:
                    self.sections[self.current_section].metadata["config_num"] = int(match[1])
                else:
                    self.errors.append(f">1 ZA,DA in section {self.current_section}")

            self.add_analysis_rule(
                r"^\s*ZA,DA,(\d+)\s*$",
                set_confnum
                )


            def add_conf(match):
                conf_str = match[0].split(",")
                if self.current_section == "WZG_STAMM":
                    conf_str = conf_str[1:]

                if re.fullmatch(r"\s*", conf_str[-1]):
                    conf_str = conf_str[:-1]
                self.sections[self.current_section].data.append(conf_str)

                
                sub = conf_str[1]
                if len(sub) <= 2:
                    print(match[0])
                sub_id = self.current_section, sub

                assert sub_id not in self.subroutines or self.current_section == "WZG_CALLS" , f"subroutine {sub} already defined"
                if self.current_section != "WZG_CALLS" or sub_id not in self.subroutines:
                    self.subroutines[sub_id] = len(self.subroutines) + 1

                sub_pattern = f'([^\"]|^){sub[1:-1]}([^\"]|$)'
                self.sections["PROGRAMM"].add_processor_rule(
                    sub_pattern,
                    lambda x, sub=copy(sub_id) : ('\n    o{0} call\n'.format(self.subroutines[sub_id]), x[1]+x[2], "OK" )
                    )

            self.add_analysis_rule(
                r"^DA,.*$",
                add_conf
                )


            def star(match):
                conf_str = match[0][1:].split(",")
                if re.fullmatch(r"\s*", conf_str[-1]):
                    conf_str = conf_str[:-1]
                self.sections[self.current_section].data[-1].extend(conf_str)


            self.add_analysis_rule(
                r"\*.*",
                star
                )

            def par_name(match):
                match2 = re.search(r"\s*'\s*((?:\S*\s*)+)'\s*", match[1])
                match = match2 if match2 else match
                # print( match[1].strip() )

                self.sections[self.current_section].param_names.append(match[1].strip())

            self.add_analysis_rule(
                r"MM,AT,1,[^,]*,[^,]*,[^,]*,[^,]*,([^,]*),[^,]*,[^,]*,[^,]*",
                par_name
                )
  
        except Exception as e:
            self.errors.append(f"Failed to build analysator: {e}")