#!/usr/bin/env python
# coding: utf-8

import PySimpleGUI as sg
import os.path
from lst2ngc import Converter
import codecs
import ast

if __name__ == "__main__":
	lsts = []
	ngcs = []
	gui_errors = []
	try: 
		# Configuration
		file = codecs.open(f'{os.path.realpath(os.path.dirname(__file__))}/../data/config.txt','r',encoding='utf-8')
		contents = file.read()
		config = ast.literal_eval(contents)
		file.close()
	except Exception as e:
		gui_errors.append(f"Error opening vonfig file: {e}")

	try:
		_file_lst =[
				sg.Text("LST File"),
				sg.In(size=(25, 1), enable_events=True, key="-LST FILE-"),
				sg.FilesBrowse(
					initial_folder=config["initial_file_path"],
					file_types=(("TOPS file", ("*.LST", "*.lst")),("ALL Files", "*.*"))
							),
				]

		_num_files = [sg.Text("Selected 0 files", key="NUM_FILES")]
		# _file_ngc =[
		#		 sg.Text("Convert to"),
		#		 sg.In(size=(25, 1), enable_events=True, key="-NGC FILE-"),
		#		 sg.SaveAs(
		#			 initial_folder="/home/tc2000r/Desktop/TC2000R/nc_files",
		#			 file_types=(("LINUXCNC file", ("*.ngc", "*.NGC")),("ALL Files", ". *"))
		#						),
		#	 ],

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
			# _file_ngc,
			_num_files,
			_convert,
			_bad_functions,
			_errors
		]

		window = sg.Window("LST2NGC Converter", layout, auto_size_text=True)
	except Exception as e:
		gui_errors.append(f"Error initializing gui: {e}")


	for err in gui_errors:
		print(err)

	try:
		while True:	
			event, values = window.read()

			# Закрытие окна
			if event == "Exit" or event == sg.WIN_CLOSED:
				break 

			# выбрали файл LST
			elif event == "-LST FILE-":
				fname_lst_string = values["-LST FILE-"]
				lsts = fname_lst_string.split(";")
				ngcs = []
				files_ok = True
				for fname in lsts:
					if fname == "":
						files_ok=False
						continue
					if not os.path.isfile(fname):
						gui_errors.append(f"{fname} does not exist or isn't a file")
						files_ok = False
					fname = "/".join(fname.split("/")[:-1] + [fname.split("/")[-1].replace(".LST", ".ngc").replace(".lst", ".ngc")])
					ngcs.append(fname)

				window["-ERRERS-"].update(gui_errors)
				gui_errors = []
				if not files_ok:
					lsts = []
					ngcs = []
					continue
				
				window["NUM_FILES"].update(f"Selected {len(lsts)} files")
				window["progress"].update(0)
				window["READY"].update(visible=False)
				window.refresh()
				
			elif event == "-NGC FILE-":  # A file was chosen from the listbox
				fname_ngc = values["-NGC FILE-"]
		#		 fname_ngc = sg.tk.filedialog.asksaveasfilename(
		#			 defaultextension='ngc',
		#			 filetypes=(("LINUXCNC file", "*.ngc"), ("All Files", "*.*")),
		#			 initialdir=script_path,
		#			 initialfile="azazaz.ngc",			 # Option added here
		#			 parent=window.TKroot,
		#			 title="Save As"
		#		 )

			elif event == "-CONVERT-":
		#		 if fname_ngc != '' and fname_lst!="":
				fileno = len(lsts)
				if fileno == 0:
					window["-ERRERS-"].update(["File not choosen"] + gui_errors)
				else:	
					ok = True
					for i, lst in enumerate(lsts):
						converter = Converter()
						# print(lst, ngcs[i])
						# thr = threading.Thread(target=analysis, args=(lst, ngcs[i]))
						# thr.start()
						converter.convert(lst, ngcs[i])

						if converter.status != "ok" or len(converter.errors) > 0 or len(converter.unparsible) > 0:
							errors = [f"Error in file {fname}"] + gui_errors + converter.errors
							window["-ERRERS-"].update(errors)
							window["-UNPARSIBLE-"].update(converter.unparsible)
							ok = False
							break

						window["progress"].update(100 * (i+1) // len(ngcs))
					if ok:
						window["READY"].update(visible=True)
						window["progress"].update(100)
					window.refresh()
		window.close()

	except Exception as e:
		print(f"Error: {e}")