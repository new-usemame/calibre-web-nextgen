#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Copyright (c) 2021-2023 Leseratte10
This file is part of the ACSM Input Plugin by Leseratte10
ACSM Input Plugin for Calibre / acsm-calibre-plugin

For more information, see: 
https://github.com/Leseratte10/acsm-calibre-plugin
'''


#@@CALIBRE_COMPAT_CODE_START@@
import sys, os

# Compatibility code taken from noDRM's DeDRM fork. 
# This fixes the weird import issues with Calibre 2, 
# and it allows me to get rid of a ton of try-except blocks.

if "calibre" in sys.modules:

    # Explicitly allow importing everything ...
    if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Bugfix for Calibre < 5:
    if sys.version_info[0] == 2:
        from calibre.utils.config import config_dir
        for filename in ["ACSM Input.zip", "DeACSM.zip"]:
            __zip_path = os.path.join(config_dir, "plugins", filename)
            if __zip_path not in sys.path and os.path.exists(__zip_path):
                sys.path.insert(0, __zip_path)

            if os.path.exists(__zip_path):
                # If we already included the new ZIP, don't also include the new one. 
                # Maybe that helps with the update issues?
                continue

#@@CALIBRE_COMPAT_CODE_END@@

import sys, binascii, traceback

def GetMasterKey(wineprefix): 
    import subprocess, os, re

    verbose_logging = False
    try: 
        import calibre_plugins.deacsm.prefs as prefs
        deacsmprefs = prefs.ACSMInput_Prefs()
        verbose_logging = deacsmprefs["detailed_logging"]
    except:
        pass

    print("Asking WINE to decrypt encrypted key for us ...")
        
    if wineprefix == "" or not os.path.exists(wineprefix):
        print("Wineprefix not found!")
        return None


    # Default to win32 binary, unless we find arch in registry
    winearch = "win32"

    try: 
        system_registry_path = os.path.join(wineprefix, "system.reg")
        regfile = open(system_registry_path, "r")
        while True:
            line = regfile.readline()
            if not line:
                break

            archkey = re.match(r'#arch=(win32|win64)', line)
            if (archkey):
                winearch = archkey.groups()[0]
                break
        regfile.close()
    except:
        pass

    
    env_dict = os.environ
    env_dict["PYTHONPATH"] = ""
    env_dict["WINEPREFIX"] = wineprefix
    #env_dict["WINEDEBUG"] = "-all,+crypt"
    env_dict["WINEDEBUG"] = "+err,+fixme"

    try: 
        from calibre.utils.config import config_dir
        from calibre_plugins.deacsm.__init__ import maindir as plg_maindir
        
        if plg_maindir is not None: 
            print("FOUND MOD DIR!")
            moddir = os.path.join(plg_maindir,"modules")
        else: 
            pluginsdir = os.path.join(config_dir,"plugins")
            maindir = os.path.join(pluginsdir,"ACSMInput")
            moddir = os.path.join(maindir,"modules")
    except: 
        import os
        moddir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keyextract")

    
    # extract the EXE file from Python code:
    # EXE files are obfuscated with base64 so that stupid AV programs
    # don't flag this whole plugin as malicious. 
    # See keyextractDecryptor.py and the folder "keyextract" for more information.

    try: 
        print("Extracting WINE key tools ...")
        from keyextractDecryptor import get_win32_data, get_win64_data

        if winearch == "win32":
            file32 = os.path.join(moddir, "decrypt_win32.exe")
            f = open(file32, "wb")
            f.write(get_win32_data())
            f.close()

        elif winearch == "win64":
            file64 = os.path.join(moddir, "decrypt_win64.exe")
            f = open(file64, "wb")
            f.write(get_win64_data())   
            f.close()
        
        else: 
            print("Invalid winearch: " + str(winearch))
            
    except:
        print("Error while extracting packed WINE ADE key extraction EXE files ")
        traceback.print_exc()

    # calls decrypt_win32.exe or decrypt_win64.exe
    proc = subprocess.Popen(["wine", "decrypt_" + winearch + ".exe"], shell=False, cwd=moddir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    prog_stdout, prog_stderr = proc.communicate()

    if verbose_logging:
        print("Stderr log:\n{}".format(prog_stderr.decode("utf-8")))
        print("Stdout log: {}".format(prog_stdout.decode("utf-8")))
        print("Exit code: {}".format(proc.returncode))

    if proc.returncode == 0:
        if verbose_logging:
            print("Successfully got encryption key from WINE: {}".format(prog_stdout.decode("utf-8")))
        else:
            print("Successfully got encryption key from WINE.")
        master_key = binascii.unhexlify(prog_stdout)
        return master_key
    else: 
        print("Failed to extract encryption key from WINE.")
        print("Exit code: {}".format(proc.returncode))


        return None


if __name__ == "__main__":
    print("Do not execute this directly!")
    exit()
