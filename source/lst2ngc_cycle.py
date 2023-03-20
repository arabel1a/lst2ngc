#!/usr/bin/env python
# coding: utf-8

# In[1]:


# main.py
import PySimpleGUI as sg
import ast
import os.path
import threading
import string
import codecs

number_lines = False
fname_ngc   = ''
fname_lst   = ''
errors      = []
subroutines = {}
delimeters = {}
sections = { }
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

#simple replaces
file = codecs.open('data/simple_replacements.txt','r',encoding='utf-8')
contents = file.read()
codes_renames = ast.literal_eval(contents)
file.close()

#Tech parameters
file = codecs.open('data/technology_groups.txt','r',encoding='utf-8')
contents = file.read()
groups = ast.literal_eval(contents)
file.close()




# In[2]:


def del_check(line):
    # Разделители
    global delimeters
    for delim in delimeters:
        if delim in line:
            delimeters[delim] = True
    


# In[3]:


#f = codecs.open('data/o2sub.txt','r',encoding='utf-8')
#code = f.readlines()
#f.close()
#move_subroutine = "".join(code)
#print(move_subroutine)


# In[4]:


def process( line ):
    global subroutines
    goodline = ""
    N_word   = ""
    # remove comments
    i = line.find(';')
    if i >= 0:
        line = line[:i]
    if line[-1] == '\n':
        line = line[:-1]
    if len(line) == 0:
        return "skip", line
    i = 0 # число обработанных символов
    ll = len(line)
    # номер кадра
    if line[0] == "N":   
        i=1
        while i < ll and line[i].isdigit():
            i+=1
        if number_lines:
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
    
    for code in codes_renames.keys():
        left = line.find(code)   
        if(left >= 0 and left < ll and (left+len(code) == ll or not line[left+len(code)].isdigit())):
            goodline += codes_renames[code]
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
    coord_rename = {"C1":" A", "C2":" B"}
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
            goodline+= coord_rename[coord] + line[left:right]
            i += right - left + 7
            verd += 'MOVE'
    
    # Tool select
    if 'TC_TOOL_NO' in line:
        left     = line.find('"')
        right    = line.find('"', left + 1)
        toolcode = "'" + line[left+1: right ] + "'"
        goodline +=' T' + f"#<_TOOL_{sections['WZG_CALLS'][toolcode][0]}>"
        i = ll
        
   
    for key in groups:
        values = groups[key]
        if key in line:
            left     = line.find('"')
            right    = line.find('"', left + 1)
            ttcode = "'" + line[left + 1: right] + "'"
            goodline +=' ;appply ' + key + ' parameters \n'
            goodline +=' o{0} call\n'.format(str(subroutines[ttcode])) 
            if number_lines:
                goodline += "N" + str(N_word + 1)
            goodline += values[1] # + '\n';
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
#         goodline += ' ;start punching'
        goodline += " #<_PUNCH> = 1\n";
        if number_lines:
            goodline += "N" + str(N_word + 2) 
        goodline += " M165" # + '\n';
        
    if 'PUNCH_OFF' in line:
        i+=9
        verd += "POFF"
#         goodline += ' ;stop punching'
        goodline += " #<_PUNCH> = 0\n"
        if number_lines:
            goodline +='N' + str(N_word + 2)
        goodline += " M164" # + '\n';

        
    #NIBBLE_ON / NIBBLE_ON
    if 'NIBBLE_ON' in line:
        i+=9
        verd += "NON"
#         goodline += ' ;start punching'
        goodline += " #<_NIBBLING> = 1\n"
        if number_lines:
            goodline +='N' + str(N_word + 2)
        goodline += " M165" # + '\n';
        
    if 'NIBBLE_OFF' in line:
        i+=10
        verd += "NOFF"
#         goodline += ' ;stop punching'
        goodline += " #<_NIBBLING> = 0\n"
        if number_lines:
            goodline +='N' + str(N_word + 2)
        goodline += "M164" # + '\n';

    
    if "TC_TANGTOOL_OFF" in line:
        i+=15
        goodline += " #<_TANGTOOL_EN>=0\n"
        if number_lines:
            goodline += 'N' + str(N_word + 1)
        goodline += " #<_TANGTOOL_P>=0"

    if "TC_TANGTOOL_ON" in line:
        left = line.find("TC_TANGTOOL_ON(")
        left  = left + 15
        right = line.find(")", left)
        goodline += " #<_TANGTOOL_EN>=1\n"
        if number_lines:
            goodline += 'N' + str(N_word + 1)
        goodline += " #<_TANGTOOL_P>=" + line[left:right]
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

        
    ################################################################
    
    
    # subroutine call
    for sub in subroutines:
        if sub[1:-1] in line and not '"' + sub[1:-1] + '"' in line:
            goodline += '\n o{0} call'.format(subroutines[sub])
            i += len(sub) - 2
    
    
    if(i == ll):
        return verd, (goodline, N_word)
    
    return "unparsible", line


# In[5]:


main_programme = ""
def header_gen():
    global main_programme
    main_programme = sections['EINRICHTEPLAN_INFO']["'TC2000'"][4]
    ret = ""
    ret += ';Machine name:    Trumpf TC200R\n'
    ret += ';Pragrammer name: {0}\n'.format(sections['EINRICHTEPLAN_INFO']["'TC2000'"][5][1:-1])
    ret += ';Date:            {0}\n'.format(sections['EINRICHTEPLAN_INFO']["'TC2000'"][6][1:-1])
    ret += ';File:            {0}\n'.format(sections['EINRICHTEPLAN_INFO']["'TC2000'"][9][1:-1])
    ret += ';Material:        {0}\n'.format(sections['EINRICHTEPLAN_INFO']["'TC2000'"][11][1:-1])
    return ret


def move_prepare(line):
    move_params  = {}
    _line = line.split(' ')
    print(_line)
    for _ in _line:
        if _.strip() == "":
            continue
        if _[0] != 'G':
            move_params[_[0]] = _[1:]
        else:
            move_params[_] = 1
    call = 'G11 '
    code_8, code_9 = 0, 0
    for symbol in range(1, 100):
        if symbol not in symbols:
            continue
        if symbols[symbol] not in move_params:
            if symbols[symbol][0] != 'G' and symbols[symbol][0] != 'M':
                pass
            else:
                move_params[symbols[symbol]] = 0
        
        if symbol < 10:
            if symbols[symbol] in move_params:
                call += f'{symbols[symbol]}{move_params[symbols[symbol]]} '
        else:
            po = symbol % 10
            if (symbol // 10  == 8):
                code_8 += move_params[symbols[symbol]] * 2 ** po
            elif (symbol // 10  == 9):
                code_9 += move_params[symbols[symbol]] * 2 ** po
    if code_8 > 0:
        call += f'R{code_8}'
    if code_9 > 0:
        call += f'S{code_9}'
    return call
    
move_prepare("G2 N8000 X-30.432 Y-114.771 I100 J399 F13251615")
    
            
        
        
    
# 560 = 512 + 32 + 16
# sections['EINRICHTEPLAN_INFO']["'TC2000'"]
# print(header_gen())
# sections['PROGRAMM']["'L10000001'"]


# In[6]:


def synthesis(ngc):
    global errors
    global sections
    global subroutines
    punch_on     = False
    trail_on     = True
    ngcode = ""
    unparsible = []
    ngcode += "%\n"
    ngcode += header_gen()
    #ngcode += move_subroutine
    subr = 3;
    
    #parameters
    for section in sections:
        if section == "PROGRAMM" or section == "EINRICHTEPLAN_INFO" \
        or section == 'WZG_CALLS' or 'DA' not in sections[section]\
        or section == "WZG_STAMM":
            continue
        total_datas = 0
        for config in sections[section]:
            if config == "MM" or config == 'DA' or config == 'pname' or config == 'param_file_name':
                continue
            if len(sections[section][config]) != int(sections[section]["MM"])- 1:
                errors.append("Bad number of parameters of section {0} of group {1}".format(section, config))
                continue
            ngcode += 'o{0} sub\n'.format(subr)
            ngcode += "; apply parameters of section {0} of group {1}\n".format(section, config)
            ngcode += 'M199 P{0}\n'.format(sections[section]["param_file_name"])
            for i in range(len(sections[section][config])):
                if not sections[section][config][i].replace('.', '', 1).replace('-', '', 1).isdigit():
                    ngcode += ';'
#                 ngcode += 'N{2} #<_{3}_{0}> = {1}'.format(i + 1, sections[section][config][i], i+1, sections[section]['pname'])
                if number_lines:
                    ngcode += 'N{2} '
                ngcode += 'M198 P{0} Q{1}'.format(i + 1, sections[section][config][i], i+1)
                ngcode +='\n'
                if not sections[section][config][i].replace('.', '', 1).replace('-', '', 1).isdigit():
                    ngcode += ';'
                if number_lines:
                    ngcode += 'N{2}'

                ngcode +=' #<_{3}_{0}> =  {1}'.format(i + 1, sections[section][config][i], 
                                                           i+2, sections[section]['pname'])
                ngcode +='\n'
            ngcode += 'o{0} endsub\n'.format(subr)
            subroutines[config] = subr
            subr += 1
            total_datas += 1
        if total_datas != int(sections[section]["DA"]):
                errors.append("Bad number of groups in of section {0} ".format(section))
    # subroutines
    subroutines_num = 0
    for sub in sections['PROGRAMM']:
        if sub == "WZG_STAMM":
            continue
        if sub == main_programme or sub == "MM" or sub == 'DA' or sub == 'pname' or sub == 'param_file_name':
            continue
#         sections['PROGRAMM'][sub].append(subr)
        subroutines[sub] = subr
        ngcode += '; subroutine {0}: \n'.format(sub)
        ngcode += 'o{0} sub\n'.format(subr)
        for line in sections["PROGRAMM"][sub][-1]:
            (verdict, cl) = process(line)
            if(type(cl) == tuple):
                NW = cl[1]
                cl = cl[0]
            if(verdict == "skip"):
                continue
            if(verdict == "unparsible"):
                unparsible.append(line)

            if "TRAILON" in verdict:
                trail_on  = True
            if trail_on:
                left = cl.find('A')
                print(cl, left, len(cl))
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
                cl = move_prepare(cl)

            ngcode += cl + '\n'

            
        ngcode += 'o{0} endsub\n'.format(subr)
        subr += 1
        subroutines_num += 1
        
    # основная программа
    
    ngcode += '; MAIN PROGRAMM: subroutine {0}: \n'.format(1)
    ngcode += '#<_nibbling> = 0\n'
    ngcode += '#<_punch> = 0 \n'
    ngcode += '#<_spp> = 0 \n'
    ngcode += 'G90 \n'
    ngcode += '#<_TANGTOOL_EN> = 0 \n'
    ngcode += 'M666\n'
    ngcode += 'M777\n'
    ngcode += 'M665\n'
    ngcode += 'M128\n'




#     ngcode += 'o{0} sub\n'.format(1)
    for line in sections["PROGRAMM"][main_programme][-1]:
        (verdict, cl) = process(line)
        print(cl)
        if(type(cl) == tuple):
            NW = cl[1]
            cl = cl[0]
        if(verdict == "skip"):
            continue
        if(verdict == "unparsible"):
            unparsible.append(line)

        if "TRAILON" in verdict:
            trail_on  = True
        if trail_on:
            left = cl.find('A')
            print(cl, left, len(cl))
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
            cl = move_prepare(cl)
        ngcode += cl + '\n'

#     ngcode += 'o{0} endsub\n'.format(1)
    ngcode += "M107\n" # возврат инструмента
    ngcode += "%\n"  
    print(ngcode)
    window["-UNPARSIBLE-"].update(unparsible)
    window["-ERRERS-"].update(errors)
    window["READY"].update(visible=True)
    window["progress"].update(100)
    window.refresh()


    if len(errors) == 0 and len(unparsible) == 0:
        f = codecs.open(ngc,'w',encoding='utf-8')
        f.writelines(ngcode)
    f.close()
    
    
# synthesis(10)


# In[7]:


def analysis(lst, ngc):
    global delimeters
    global sections
    global subroutines
    global errors
    global free_nests
    ngcode = []
    current_conf = ""
    text = False
    
    errors      = []
    subroutines = {}
    delimeters = {}
    sections = { }

    with open(lst) as f:
        code = f.readlines()
    f.close()
    
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
    
    for section in sections:
        delimeters["BEGIN_" + section]  = False
        delimeters["ENDE_" + section]  = False
    
    if "BD" not in code[0].translate({ord(c): None for c in string.whitespace}):
        errors.append("Broken file! BD is missing")
    for line in code[::-1]:
        line = line.translate({ord(c): None for c in string.whitespace})
        if len(line) == 0:
            continue
        if line != "ED":
            errors.append("Broken file! ED is missing or text after ED")
        break
                            

    
    for line in code[1:-1]:
        # removing newline characters and whitespaces
        line = line.translate({ord(c): None for c in string.whitespace})
        # throwing the trash away
        if 'MM,AT,1,' in line or line == 'C\n' or len(line) == 0:
            continue
         # check for file delimeters 
        del_check(line)
        current_section = ""
        for section in sections:
            if delimeters["BEGIN_" + section] and not delimeters["ENDE_" + section]:
                current_section = section
#         if current_section == "WZG_STAMM":
#             continue
        
        if(line == "START_TEXT"):
            text = True            
            sections[current_section][current_conf].append([])
            continue
        if(line == "STOP_TEXT"):
            text = False
        if text:
            sections[current_section][current_conf][-1].append(line)
                     
                
        if("ZA" in line):
            _line = line.split(",")
            sections[current_section][_line[1]] = _line[2]
            continue
        if("DA" in line):
            _line = line.split(",")
            current_conf  = _line[1]
            sections[current_section][current_conf] = _line[2:]
            continue
        if(line[0] == '*'):
            _line = line[1:].split(",")
            sections[current_section][current_conf] = sections[current_section][current_conf][:-1]
            sections[current_section][current_conf].extend(_line)
            continue
        
    synthesis(ngc)
             
        


# In[8]:


_file_lst =[
        sg.Text("LST File"),
        sg.In(size=(25, 1), enable_events=True, key="-LST FILE-"),
        sg.FilesBrowse(
            initial_folder="",
            file_types=(("TOPS file", ("*.LST", "*.lst")),("ALL Files", ". *"))
                       ),
    ],


_file_ngc =[
        sg.Text("Convert to"),
        sg.In(size=(25, 1), enable_events=True, key="-NGC FILE-"),
        sg.SaveAs(
            initial_folder="",
            file_types=(("LINUXCNC file", ("*.ngc", "*.NGC")),("ALL Files", ". *"))
                       ),
    ],

# For now will only show the name of the file that was chosen
_convert =[
        sg.Button("Convert", key = "-CONVERT-"),
        sg.Column([
                [sg.Text("Progress:"), sg.Text("READY", key = "READY", visible = False)], 
                [sg.ProgressBar(100, key = "progress")]
            ])       
    ]

_bad_functions =[
    sg.Column([
        [sg.Text("Bad characters:")],
        [sg.Listbox( size = (60, 10), values=[], enable_events=True, key="-UNPARSIBLE-")]
    ])
]

_errors =[
    sg.Column([
        [sg.Text("Errors:")],
        [sg.Listbox( size = (60, 10), values=[], enable_events=True, key="-ERRERS-")]
    ])
]

# ----- Full layout -----

layout = [
    _file_lst,
    _file_ngc,
    _convert,
    _bad_functions,
    _errors
]


window = sg.Window("LST2NGC Converter", layout, auto_size_text=True)

while True:
    # Закрытие окна
    
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break 
    if event == "-LST FILE-":
        fname_lst = values["-LST FILE-"]
        window["progress"].update(0)
        window["READY"].update(visible=False)
        window.refresh()
        
    elif event == "-NGC FILE-":  # A file was chosen from the listbox
        fname_ngc = values["-NGC FILE-"]
#         fname_ngc = sg.tk.filedialog.asksaveasfilename(
#             defaultextension='ngc',
#             filetypes=(("LINUXCNC file", "*.ngc"), ("All Files", "*.*")),
#             initialdir=script_path,
#             initialfile="azazaz.ngc",             # Option added here
#             parent=window.TKroot,
#             title="Save As"
#         )

    elif event == "-CONVERT-":
#         if fname_ngc != '' and fname_lst!="":
        thr = threading.Thread(target=analysis, args=(fname_lst,fname_ngc))
        thr.start()
        
window.close()

