# lst2ngc
This is a converter from TRUMPH's TOPS to linuxcnc's RS274 NC languags. 

After my NC control unit burned down, i decided to use open-source one. Hovewer, original TRUMPH's CNC unit comes with proprietary CAM system (named TOPS) that is used to convert drawings to programs. Repository code's goal is to convert TOPS output intro LinuxCNC programs. 

I do not believe that someone will face the same problem and would need this code. But It can be usefull as a template for converter program between different numeric control verdor's languages. It's pretty simple, modular and can be customized in a simple way. More over, it's contains base  "Converter" class, which might be useful to write arbitrary converter between CNC languages, and a simple GUI gor user.

# install

In linux, go to project folder and install dependencies by executuing
```
python3 -m pip install -r requirements
```
In windows install this packages with common way you insatll python packages :) [i've never done this]

# configure
There is a bit of configuratuion in file data/conf
If i find enough time, i'll write al comments and file description. But anyway you can contact me via Telegram @arabel1a. I can help adapting this code for your converter task.

# run
```
python3 source/gui.py
```

# Feel free to contribute ^-^
