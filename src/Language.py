# -*- coding: utf-8 -*-
#####################################################################
#                                                                   #
# Frets on Fire X (FoFiX)                                           #
# Copyright (C) 2009-2010 FoFiX Team                                #
# See CREDITS for a full list of contributors                       #
#                                                                   #
# This program is free software; you can redistribute it and/or     #
# modify it under the terms of the GNU General Public License       #
# as published by the Free Software Foundation; either version 2    #
# of the License, or (at your option) any later version.            #
#                                                                   #
# This program is distributed in the hope that it will be useful,   #
# but WITHOUT ANY WARRANTY; without even the implied warranty of    #
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the     #
# GNU General Public License for more details.                      #
#                                                                   #
# You should have received a copy of the GNU General Public License #
# along with this program; if not, write to the Free Software       #
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,        #
# MA  02110-1301, USA.                                              #
#####################################################################

import Config
import Version
import Log
import locale
import gettext
import os
import glob

Config.define("game", "language", str, "")

def dummyTranslator(string):
  return string

encoding = Config.load(Version.PROGRAM_UNIXSTYLE_NAME + ".ini").get("game", "encoding")
language = Config.load(Version.PROGRAM_UNIXSTYLE_NAME + ".ini").get("game", "language")
_ = dummyTranslator

# Automatic language detection.

if language == "auto":
  lc = locale.getdefaultlocale()[0]
  if lc.partition('_')[0] == 'en':
    Config.define("game", "language", str, "")
    Config.load(Version.PROGRAM_UNIXSTYLE_NAME + ".ini").set("game", "language", "")
  elif lc == 'zh_CN' or 'zh_SG': # Chinese Simplified
    Config.define("game", "language", str, "zh_CN")
    Config.load(Version.PROGRAM_UNIXSTYLE_NAME + ".ini").set("game", "language", "zh_CN")
  elif lc == 'zh_TW' or 'zh_HK' or 'zh_MO': # Chinese Traditional
    Config.define("game", "language", str, "zh_TW")
    Config.load(Version.PROGRAM_UNIXSTYLE_NAME + ".ini").set("game", "language", "zh_TW")
  else:
    Config.define("game", "language", str, lc.partition('_')[0])
    Config.load(Version.PROGRAM_UNIXSTYLE_NAME + ".ini").set("game", "language", lc.partition('_')[0])

if language:
  try:
    trFile = os.path.join(Version.dataPath(), "translations", "%s.mo" % language.lower().replace(" ", "_"))
    catalog = gettext.GNUTranslations(open(trFile, "rb"))
    def translate(m):
      if encoding == "None":
        return catalog.gettext(m).decode("utf-8")
      else:
        return catalog.gettext(m).decode("utf-8")
    _ = translate
  except Exception, x:
    Log.warn("Unable to select language '%s': %s" % (language, x))
    #language = None
    Config.load(Version.PROGRAM_UNIXSTYLE_NAME + ".ini").set("game", "language", "")

# Define the config key again now that we have some options for it
# Set new languages manually here. getAvailableLanguages was quirky and didn't really fit.
langOptions = {"af": "Afrikaans", "sq": "Shqiptar", "ar": "العربية", "be": "Беларуская", "bg": "Български", "ca": "Català",
                "zh_CN": "中文（简体）", "zh_TW": "中文（繁體）", "hr": "Hrvatski", "cs": "Český", 
                "da": "Danske", "nl": "Nederlands", "et": "Eesti", "tl": "Filipino", "fi": "Suomi", "fr": "Français", 
                "gl": "Galego", "de": "Deutsch", "el": "Ελληνικά", "iw": "עברית", "hi": "हिन्दी", "hu": "Magyar", 
                "is": "Íslenska", "id": "Indonesia", "ga": "Gaeilge", "it": "Italiano", "ja": "日本語", "ko": "한국의", 
                "lv": "Latvijā", "lt": "Lietuvos", "mk": "Македонски", "ms": "Melayu", "mt": "Malti", "no": "Norske", 
                "fa": "فارسی", "pl": "Polska", "pt": "Português", "ro": "Română", "ru": "Россию", "sr": "Српска", 
                "sk": "Slovenskému", "sl": "Slovenščina", "es": "Español", "sw":"Swahili", "sv": "Svenska", "th": "ไทย", 
                "tr": "Türk", "uk": "Українське", "vi": "Việt", "cy": "Cymraeg", "yi": "ייִדיש", 
                "": "English", "auto": "Automatic"}
Config.define("game", "language", str, "", _("Language"), langOptions, tipText=_("Change the game language!"))

