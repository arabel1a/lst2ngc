#!/usr/bin/env python
# coding: utf-8

import os.path
import string
import codecs
import re
from copy import copy


class Section:
    """
    This class describes section of input program file.
    """
    def __init__(self, name:str, converter, delimeters:tuple, post_processor:callable = None):
        assert len(delimeters)  == 2
        self.name       = name
        self.converter  = converter
        self.delimeters = delimeters
        self.processor_rules = {r"^\s*$" : lambda x:("","","ok")}
        self.i_code     = []
        self.o_code     = []
        self.data       = []
        self.subsections = {}
        self.metadata   = {}
        self.post_processor = self.dummy_pp
        if post_processor is not None:
            self.post_processor=post_processor

    def dummy_pp(self, verdict, line):
        if 'unparsible' in verdict:
            self.converter.unparsible.append(line)
            return ""
        return line

    def process(self) -> None:
        try:
            for line in self.i_code:
                line = line.strip()
                verdict, processed  = self.process_line(line)
                good_line = self.post_processor(verdict, processed)
                if not re.fullmatch(r"\s*", good_line):
                    self.o_code.append(good_line)
                if(len(self.converter.errors) > 0):
                    return
        except Exception as e:
            self.converter.errors.append(f"Synthesis section {self.name} error: {e}")

    def process_line(self, line:str) -> tuple:
        goodline=""
        verdict=""
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
                return verdict, goodline[:-1]

            return "unparsible", f"from {line} can extract only {goodline}"
        except Exception as e:
            self.converter.errors.append(f"Processing section {self.name} error {e}")
            self.converter.errors.append(f"while parsing >{line}<")

    def add_processor_rule(self, pattern, f):
        # if pattern in self.processor_rules:
        #     self.converter.errors.append(f"Synthesis error: pattern >{pattern}< is used twice in section >{self.name}<")
        self.processor_rules[pattern] = f

    def post_analyse(self):
        pass


class Converter:
    """
    This is the base class
    This class is used to ...
    """
    def __init__(self, config={}, input_file=None, output_file=None):

        self.lineno         = "keep"    
        self.config         = config
        if "use_line_numbers" in config:
            self.lineno = "new"
        if "keep_old_line_numbers" in config:
            self.lineno = "keep"
        self.analysator     = {}
        self.input_file     = input_file
        self.output_file    = output_file
        self.errors         = []
        self.unparsible     = []
        self.delimeters     = {}
        self.sections       = {}
        self.i_code         = []
        self.o_code         = []
        self.status         = "ready"
        self.sections_ordered = []
        self.current_section = "main"

    def add_section(self, name:str, delimeters:tuple, rules:dict=None, post_processor=None):
        try:
            if name in self.sections:
                self.errors.append(f"section {name} is added twice")
            self.sections[name] = Section(name, self, delimeters,post_processor=post_processor)
            self.sections_ordered.append(name)
            if rules is not None:
                for rule in rules:
                    self.sections[name].add_processor_rule(rule, rules[rule])
        except Exception as e:
            self.errors.append(f"Error adding section {name}: {e}")
            self.status = "error"
            
    def add_analysis_rule(self, pattern:str, f:callable):
        # print(f"adding rule {pattern} to analysator")
        if pattern in self.analysator:
            self.errors.append(f"Analysis error: pattern >{pattern}< is used twice")
            self.status = "error"
        self.analysator[pattern] = f


    def analyse_line(self, line:str):
        try:
            # removing newline characters and whitespaces
            line = re.sub(r"\s+", " ", line)
            for pattern in self.analysator:
                match = re.match(pattern, line)                                
                if match:
                    self.analysator[pattern](match)
        except Exception as e:
            self.errors.append(f"Error analysing: {e} while looking at line {line}")
            self.status = "error"

    def analysis(self):
        """
            Read the file and fills internal structures, such as sections, toolchange number, etc
        """
        try:
            for line in self.i_code:
                cs = self.current_section
                self.analyse_line(line)
                if cs!=self.current_section:
                    continue
                if self.current_section == "":
                    self.unparsible.append(line)
                else:
                    self.sections[self.current_section].i_code.append(line)
                if(len(self.errors) > 0):
                    return
        except Exception as e:
            self.errors.append(f"Analysis failed: {e} ")
            self.status = "error"

    def synthesis(self):
            for section in self.sections_ordered:
                self.sections[section].process()
                self.o_code.extend(self.sections[section].o_code)
                               
    def load(self, input_file=None):
        if input_file is None and self.input_file is not None:
            input_file = self.input_file
        try:
            with open(input_file) as f:
                self.i_code = f.readlines()
                f.close()
        except:
            self.errors.append(f"can not load LST file {input_file}")
            self.status = "error"

    def save(self, output_file=None):
        # print()
        if output_file is None and not self.output_file is None:
            output_file = self.output_file
        try:
            f = codecs.open(output_file,'w',encoding='utf-8')
            f.writelines("\n".join(self.o_code))
            f.close()
        except:
            self.errors.append(f"can not load LST file {output_file}")
            self.status = "error"


    def prepare(self):
        try:
            for section_name in self.sections:
                section = self.sections[section_name]
                def start_section(match, section=section_name):
                    self.current_section = section
                
                def stop_section(match):
                    self.sections[self.current_section].post_analyse()
                    self.current_section = "main"

                self.add_analysis_rule(
                    section.delimeters[0],
                    start_section
                    )

                self.add_analysis_rule(
                    section.delimeters[1],
                    stop_section
                    )
            self.add_section("main",(None,None))

        except Exception as e:
            self.errors.append(f"Preparation error: {e}")

    def convert(self, in_fname, out_fname):
        try:
            assert self.status == "ready"
            # self.__init__(in_fname, out_fname)

            self.prepare()
            if len(self.errors) == 0:
                print("preparations ok")
            else:
                return
            
            print(f"operating file {in_fname}")
            
            self.load(in_fname)
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

            if len(self.unparsible) > 0:
                self.errors.append("Not all symbold were parsed correctly")
                print(self.unparsible)
                return

            self.save(out_fname)
            if len(self.errors) == 0:
                print("saving ok")
            else:
                return
            self.status = 'ok'
        except Exception as e:
            self.status = "error"
            self.errors.append(f"Internal error {e}")





