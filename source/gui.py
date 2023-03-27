#!/usr/bin/env python
# coding: utf-8

import PySimpleGUI as sg
import os.path
from lst2ngc import LST2NGC
import codecs
import configparser
import re

if __name__ == "__main__":
	lsts = []
	ngcs = []
	gui_errors = []
	try: 
		config = configparser.ConfigParser(comment_prefixes=("///", "###"))
		config.read(f'{os.path.realpath(os.path.dirname(__file__))}/../config.txt')
	except Exception as e:
		gui_errors.append(f"Error opening сonfig file: {e}")

	try:
		folder_ngc = config['defaults']['output_folder']
		in_extensions 	= tuple(["*." + x.strip() for x in config['defaults']['input_extension'].split(',')])
		out_extensions 	= tuple(["*." + x.strip() for x in config['defaults']['output_extension'].split(',')])

		_file_lst =[
        sg.Text("LST File"),
        sg.In(size=(25, 1), enable_events=True, key="-LST FILE-"),
        sg.FileBrowse(
            initial_folder=config['defaults']['input_folder'],
            file_types=(("TOPS file", in_extensions),("ALL Files", "*.*"))
                       ),
	    ],


		_file_ngc =[
		        sg.Text("Convert to"),
		        sg.In(size=(25, 1), enable_events=True, key="-NGC FILE-"),
		        sg.SaveAs(
                    initial_folder=config['defaults']['output_folder'],
		            file_types=(
		            	("LINUXCNC file", out_extensions),
		            ("ALL Files", ". *"))
		                       ),
	    ],

		_files_lst =[
				sg.Text("LST Files"),
				sg.In(size=(25, 1), enable_events=True, key="-LST FILES-"),
				sg.FilesBrowse(
					initial_folder=config['defaults']['input_folder'],
					file_types=(("TOPS file", in_extensions),("ALL Files", "*.*"))
							),
				]

		_folder_ngc =[
				sg.Text("NGC folder"),
				sg.In(size=(25, 1), enable_events=True, key="-NGC FOLDER-"),
				sg.FolderBrowse(
					initial_folder=config['defaults']['output_folder'],
					),
				]
		
		_num_files = [sg.Text("Selected 0 files", key="NUM_FILES")]


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

		



		# stacking them
		layout = []
		
		if config['behaviour'].getboolean("multple_files_allowed"):
			layout = [
				_files_lst,
				_folder_ngc,
				_num_files,
				_convert,
				_bad_functions,
				_errors
			]
		else:
			layout = [
				_file_lst,
				_file_ngc,
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

   			########## Single file mode ###########
			if event == "-LST FILE-":
				fname_lst = values["-LST FILE-"]
				lsts = [ fname_lst ]
				ngcs = []
				window["progress"].update(0)
				window["READY"].update(visible=False)
				window.refresh()
			    
			elif event == "-NGC FILE-":  # A file was chosen from the listbox
				fname_ngc = values["-NGC FILE-"]
				ngcs = [fname_ngc]
				window["progress"].update(0)
				window["READY"].update(visible=False)
				window.refresh()


			########## Multiple file mode ###########        
			
			elif event == "-LST FILES-":
				fname_lst_string = values["-LST FILES-"]
				lsts = fname_lst_string.split(";")
				ngcs = []
				files_ok = True
				for fname in lsts:
					if not os.path.isfile(fname):
						gui_errors.append(f"{fname} does not exist or isn't a file")
						files_ok = False
					
				window["-ERRERS-"].update(gui_errors)
				gui_errors = []
				if not files_ok:
					lsts = []
					continue
				for fname in lsts:

					ngc_name = os.path.join(folder_ngc, fname.split("/")[-1])
					for ex in in_extensions: 
						ngc_name = re.sub(ex[1:] + r"$", out_extensions[0][1:], ngc_name)
					ngcs.append(ngc_name)
				
				window["NUM_FILES"].update(f"Selected {len(lsts)} files")
				window["progress"].update(0)
				window["READY"].update(visible=False)
				window.refresh()
				
			elif event == "-NGC FOLDER-":  # A file was chosen from the listbox
				folder_ngc = values["-NGC FOLDER-"]
				ngcs = []
				for fname in lsts:
					ngc_name = os.path.join(folder_ngc, fname.split("/")[-1].replace(".LST", ".ngc").replace(".lst", ".ngc"))
					ngcs.append(ngc_name)
				window["progress"].update(0)
				window["READY"].update(visible=False)
				window.refresh()
				

			elif event == "Exit" or event == sg.WIN_CLOSED:
				break 

			elif event == "-CONVERT-":
				print(lsts, ngcs)
				assert  len(lsts) == len(ngcs)
				fileno = len(lsts)
				if fileno == 0:
					window["-ERRERS-"].update(["File not choosen"] + gui_errors)
				else:	
					ok = True
					for i, lst in enumerate(lsts):
						converter = LST2NGC(config=config)
						converter.convert(lst, ngcs[i])
						if converter.status != "ok" or len(converter.errors) > 0 or len(converter.unparsible) > 0:
							print(converter.status)
							errors = [f"Error in file {lst}"] + gui_errors + converter.errors
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