#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Kyöstilä                                  #
#               2008 myfingershurt                                  #
#               2008 evilynux <evilynux@gmail.com>                  #
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

import pygame
from OpenGL.GL import *
import math
import os

from View import Layer, BackgroundLayer
from Input import KeyListener, MouseListener
from Language import _
import Data
import Dialogs
import Player
import Config
import Mod
import Version

import Log

menuList = ["main", "solo", "multiplayer", "training", "settings", "gameplay", "control", \
            "display", "audio", "setlist", "advanced", "mcai", "mods", "quickset", \
            "advgame", "vocal", "hopo", "battle", "testcontrol", "stage", "neck", \
            "fretboard", "fretboardalpha", "ingame", "advvideo", "shaders", "volume", \
            "advaudio", "log", "debug", "ai"]

menuDict = {"main": None}
#menuDict needs to hold: choices, callbacks, breadcrumb

class MenuItem(object):
  def __init__(self, name, choices, breadcrumb = [], onClose = None, onCancel = None, append_submenu_char = True, selectedIndex = 0):
    self.name    = name
    self.choices = []
    for c in choices:
      if not isinstance(c, Choice):
        print "Fixing List"
        try:
          text, callback = c
          if isinstance(text, tuple):
            if len(text) == 2: # a submenu's name
              c = Choice(text[0], callback, name = text[1], append_submenu_char = append_submenu_char)
            else: # Dialogs menus - FileChooser, NeckChooser, ItemChooser - this last to be changed soon
              c = Choice(text[0], callback, values = text[2], valueIndex = text[1], append_submenu_char = append_submenu_char)
          else:
            c = Choice(text, callback, append_submenu_char = append_submenu_char)
        except ValueError:
          text, callback, tipText = c
          if isinstance(text, tuple):
            if len(text) == 2: # a submenu's name
              c = Choice(text[0], callback, name = text[1], append_submenu_char = append_submenu_char, tipText = tipText)
            else: # Dialogs menus - FileChooser, NeckChooser, ItemChooser - this last to be changed soon
              c = Choice(text[0], callback, values = text[2], valueIndex = text[1], append_submenu_char = append_submenu_char, tipText = tipText)
          else:
            c = Choice(text, callback, append_submenu_char = append_submenu_char, tipText = tipText)
        except TypeError:
          pass
      self.choices.append(c)
    
    self.onClose = onClose
    self.onCancel = onCancel
    self.selectedIndex = selectedIndex
    self.breadcrumb = breadcrumb

#load all images in menu; load individual folders on menu open;
#store in menu layer (which persists from open to GuitarScene)
#on cancel, last menu from world (such as "solo" is loaded immediately); "main" on quit.
#Menu becomes a 'scene'; in-game menus are separate

class Choice:
  def __init__(self, text, callback, name = None, values = None, valueIndex = 0, append_submenu_char = True, tipText = None, display = True):
    self.text       = unicode(text)
    self.callback   = callback
    self.name       = name
    self.values     = values
    self.valueIndex = valueIndex
    self.append_submenu_char = append_submenu_char
    self.tipText    = tipText
    self.display    = display

    if self.text.endswith(" >"):
      self.text = text[:-2]
      self.isSubMenu = True
    else:
      self.isSubMenu = isinstance(self.callback, MenuItem) or isinstance(self.callback, list)
    
  def trigger(self, engine = None):
    # if engine and isinstance(self.callback, list):
      # nextMenu = MenuItem(self.name, self.callback)
    # el
    if engine and isinstance(self.callback, MenuItem):
      nextMenu = engine.mainMenu.menu.enterMenu(self.callback)
    elif self.values:
      nextMenu = self.callback(self.values[self.valueIndex])
    else:
      nextMenu = self.callback()
    if isinstance(nextMenu, MenuItem):
     engine.mainMenu.menu.enterMenu(nextMenu)
      
  def selectNextValue(self):
    if self.values:
      self.valueIndex = (self.valueIndex + 1) % len(self.values)
      self.trigger()

  def selectPreviousValue(self):
    if self.values:
      self.valueIndex = (self.valueIndex - 1) % len(self.values)
      self.trigger()
      
  def getText(self, selected):
    if not self.values:
      if self.isSubMenu and self.append_submenu_char:
        return "%s >" % self.text
      return self.text
    if selected:
      return "%s: %s%s%s" % (self.text, Data.LEFT, self.values[self.valueIndex], Data.RIGHT)
    else:
      return "%s: %s" % (self.text, self.values[self.valueIndex])

class Button(object):
  def __init__(self, name, area, onClick = None, onHover = None, imgRange = None):
    self.name = name
    self.xRange, self.yRange = area
    self.onClick = onClick
    self.onHover = onHover
    self.hovered = False
    self.visible = True
    self.pressed = 0
    if imgRange:
      self.imgXRange, self.imgYRange = imgRange
    else:
      self.imgXRange, self.imgYRange = area
  
  def click(self):
    return self.onClick()
  
  def hover(self):
    return self.onHover()

class ConfigChoice(Choice):
  def __init__(self, engine, config, section, option, autoApply = False, isQuickset = 0):
    self.engine    = engine
    self.config    = config
    
    self.logClassInits = self.engine.config.get("game", "log_class_inits")
    if self.logClassInits == 1:
      Log.debug("ConfigChoice class init (Settings.py)...")
    
    self.section    = section
    self.option     = option
    self.changed    = False
    self.value      = None
    self.autoApply  = autoApply
    self.isQuickset = isQuickset
    tipText = config.getTipText(section, option)
    o = config.prototype[section][option]
    v = config.get(section, option)
    if isinstance(o.options, dict):
      values     = o.options.values()
      values.sort()
      try:
        valueIndex = values.index(o.options[v])
      except KeyError:
        valueIndex = 0
    elif isinstance(o.options, list):
      values     = o.options
      try:
        valueIndex = values.index(v)
      except ValueError:
        valueIndex = 0
    else:
      raise RuntimeError("No usable options for %s.%s." % (section, option))
    Choice.__init__(self, text = o.text, callback = self.change, values = values, valueIndex = valueIndex, tipText = tipText)
    
  def change(self, value):
    o = self.config.prototype[self.section][self.option]
    
    if isinstance(o.options, dict):
      for k, v in o.options.items():
        if v == value:
          value = k
          break
    
    self.changed = True
    self.value   = value
    
    if self.isQuickset == 1: # performance quickset
      self.config.set("quickset","performance",0)
      self.engine.quicksetPerf = 0
    elif self.isQuickset == 2: # gameplay quickset
      self.config.set("quickset","gameplay",0)
    
    if self.section == "quickset":
      if self.option == "performance":
        if self.value == self.engine.quicksetPerf or self.value == 0:
          self.engine.quicksetRestart = False
        else:
          self.engine.quicksetRestart = True
    
    self.apply()  #stump: it wasn't correctly saving some "restart required" settings
    if not self.autoApply:
      self.engine.restartRequired = True

  def apply(self):
    if self.changed:
      self.config.set(self.section, self.option, self.value)

class ActiveConfigChoice(ConfigChoice):
  """
  ConfigChoice with an additional callback function.
  """
  def __init__(self, engine, config, section, option, onChange, autoApply = True, volume = False):
    ConfigChoice.__init__(self, engine, config, section, option, autoApply = autoApply)
    self.engine   = engine
    self.onChange = onChange
    self.volume   = volume
    
    self.logClassInits = self.engine.config.get("game", "log_class_inits")
    if self.logClassInits == 1:
      Log.debug("ActiveConfigChoice class init (Settings.py)...")
  
  def change(self, value):
    ConfigChoice.change(self, value)
    if self.volume:
      sound = self.engine.data.screwUpSound
      sound.setVolume(self.value)
      sound.play()
  
  def apply(self):
    ConfigChoice.apply(self)
    self.onChange()

class VolumeConfigChoice(ConfigChoice):
  def __init__(self, engine, config, section, option, autoApply = False):
    ConfigChoice.__init__(self, engine, config, section, option, autoApply)
    self.engine = engine

    self.logClassInits = self.engine.config.get("game", "log_class_inits")
    if self.logClassInits == 1:
      Log.debug("VolumeConfigChoice class init (Settings.py)...")
    

  def change(self, value):
    ConfigChoice.change(self, value)
    sound = self.engine.data.screwUpSound
    sound.setVolume(self.value)
    sound.play()

class KeyConfigChoice(Choice):
  def __init__(self, engine, config, section, option, noneOK = False, shift = None):
    self.engine  = engine

    self.logClassInits = self.engine.config.get("game", "log_class_inits")
    if self.logClassInits == 1:
      Log.debug("KeyConfigChoice class init (Settings.py)...")

    self.config  = config
    self.section = section
    self.option  = option
    self.changed = False
    self.value   = None
    self.noneOK  = noneOK
    self.shift   = shift
    self.type    = self.config.get("controller", "type")
    self.name    = self.config.get("controller", "name")
    self.frets   = []
    
    def keycode(k):
      try:
        return int(k)
      except:
        return getattr(pygame, k)
    
    if self.shift:
      self.frets.append(keycode(self.config.get("controller", "key_1")))
      self.frets.append(keycode(self.config.get("controller", "key_2")))
      self.frets.append(keycode(self.config.get("controller", "key_3")))
      self.frets.append(keycode(self.config.get("controller", "key_4")))
      self.frets.append(keycode(self.config.get("controller", "key_5")))

    self.keyCheckerMode = self.config.get("game","key_checker_mode")

    self.option = self.option
      
    Choice.__init__(self, text = "", callback = self.change)

  def getText(self, selected):
    def keycode(k):
      try:
        return int(k)
      except:
        return getattr(pygame, k)
    o = self.config.prototype[self.section][self.option]
    v = self.config.get(self.section, self.option)
    if isinstance(o.text, tuple):
      type = self.type
      if len(o.text) == 5:
        text = o.text[type]
      else:
        if type == 4:
          type = 0
      if len(o.text) == 4:
        text = o.text[type]
      elif len(o.text) == 3:
        text = o.text[max(0, type-1)]
      elif len(o.text) == 2:
        if type < 2:
          text = o.text[0]
        else:
          text = o.text[1]
    else:
      text = o.text
    if v == "None":
      keyname = "Disabled"
    else:
      keyname = pygame.key.name(keycode(v)).capitalize()
    return "%s: %s" % (text, keyname)
    
  def change(self):
    o = self.config.prototype[self.section][self.option]

    if isinstance(o.options, dict):
      for k, v in o.options.items():
        if v == value:
          value = k
          break
    if isinstance(o.text, tuple):
      type = self.type
      if len(o.text) == 5:
        text = o.text[type]
      else:
        if type == 4:
          type = 0
      if len(o.text) == 4:
        text = o.text[type]
      elif len(o.text) == 3:
        text = o.text[max(0, type-1)]
      elif len(o.text) == 2:
        if type < 2:
          text = o.text[0]
        else:
          text = o.text[1]
    else:
      text = o.text
    if self.shift:
      key = Dialogs.getKey(self.engine, self.shift, specialKeyList = self.frets)
    else:
      if self.noneOK:
        key = Dialogs.getKey(self.engine, _("Press a key for '%s' or hold Escape to disable.") % text)
      else:
        key = Dialogs.getKey(self.engine, _("Press a key for '%s' or hold Escape to cancel.") % text)
    
    if key:
      #------------------------------------------
      
      #myfingershurt: key conflict checker operation mode
      #if self.keyCheckerMode == 2:    #enforce; do not allow conflicting key assignments, force reversion
        # glorandwarf: sets the new key mapping and checks for a conflict
        #if self.engine.input.setNewKeyMapping(self.section, self.option, key) == False:
          # key mapping would conflict, warn the user
          #Dialogs.showMessage(self.engine, _("That key is already in use. Please choose another."))
        #self.engine.input.reloadControls()

      #elif self.keyCheckerMode == 1:    #just notify, but allow the change
        # glorandwarf: sets the new key mapping and checks for a conflict
        #if self.engine.input.setNewKeyMapping(self.section, self.option, key) == False:
          # key mapping would conflict, warn the user
          #Dialogs.showMessage(self.engine, _("A key conflict exists somewhere. You should fix it."))
        #self.engine.input.reloadControls()
      
      #else:   #don't even check.
      temp = Player.setNewKeyMapping(self.engine, self.config, self.section, self.option, key)
      if self.name in self.engine.input.controls.controlList:
        self.engine.input.reloadControls()
    else:
      if self.noneOK:
        temp = Player.setNewKeyMapping(self.engine, self.config, self.section, self.option, "None")
        if self.name in self.engine.input.controls.controlList:
          self.engine.input.reloadControls()
      
      
      #------------------------------------------

  def apply(self):
    pass

def chooseControl(engine, mode = "edit", refresh = None):
  """
  Ask the user to choose a controller for editing or deletion.
  
  @param engine:    Game engine
  @param mode:      "edit" or "delete" controller
  """
  mode     = mode == "delete" and 1 or 0
  options  = []
  for i in Player.controllerDict.keys():
    if i != "defaultg" and i != "None" and i != "defaultd" and i != "defaultm":
      options.append(i)
  options.sort()
  if len(options) == 0:
    Dialogs.showMessage(engine, _("No Controllers Found."))
    return
  d = ControlChooser(engine, mode, options)
  Dialogs._runDialog(engine, d)
  if refresh:
    refresh()

def createControl(engine, control = "", edit = False, refresh = None):
  d = ControlCreator(engine, control, edit = edit)
  Dialogs._runDialog(engine, d)
  if refresh:
    refresh()

class Menu(Layer, KeyListener, MouseListener):
  def __init__(self, engine, firstMenu, mainMenu = None, append_submenu_char = True, showTips = True):
    self.engine       = engine

    self.logClassInits = self.engine.config.get("game", "log_class_inits")
    if self.logClassInits == 1:
      Log.debug("Menu class init (Menu.py)...")

    #Get theme
    self.themename = self.engine.data.themeLabel
    
    self.time         = 0
    
    self.choices      = []
    self.currentIndex = 0
    
    self.buttons      = {}
    
    xS, yS = self.engine.view.geometry[2:4]
    self.buttons["up"] = Button("up", ((xS*.18,xS*.22),(yS*.2,yS*.24)), self.mouseScrollUp)
    self.buttons["down"] = Button("down", ((xS*.18,xS*.22),(yS*.7,yS*.74)), self.mouseScrollDown)
    self.buttons["back"] = Button("back", ((xS*.8,xS*.84),(yS*.15,yS*.19)), self.cancel)
    
    self.onClose      = None
    self.onCancel     = None
    
    self.viewOffset = 0
    self.scrolling  = 0
    self.delay      = 0
    self.rate       = 0
    self.scroller   = [0, self.scrollUp, self.scrollDown, self.scrollLeft, self.scrollRight]
    
    self.graphicMenu = False
    self.theme = 2
    self.oneLoop = False
    
    self.textColor     = self.engine.theme.baseColor#textColor
    self.selectedColor = self.engine.theme.selectedColor
    self.tipColor      = self.engine.theme.menuTipTextColor
    
    self.engine.data.loadAllImages(self, os.path.join("themes",self.themename,"menu"))
    
    # if not pos:
    self.sub_menu_x = self.engine.theme.sub_menu_xVar
    self.sub_menu_y = self.engine.theme.sub_menu_yVar

    pos = (self.sub_menu_x, self.sub_menu_y)

    self.pos          = pos
    self.viewSize     = 10
    self.fadeScreen   = False
    self.font         = self.engine.data.font
    self.menuName     = ""
    self.menuItem     = None
    if self.font == "font":
      self.font = self.engine.data.font
    self.tipFont = self.engine.theme.menuTipTextFont
    if self.tipFont == "None":
      self.tipFont = self.font
    else:
      self.tipFont = self.engine.data.fontDict[self.tipFont]
    self.active = False
    self.mainMenu = self.engine.mainMenu
    self.breadcrumb = []
    self.loadedMenus = []
    # self.menuDict = {}
    
    self.showTips = showTips
    if self.showTips:
      self.showTips = self.engine.theme.menuTipTextDisplay
    self.tipDelay = 700
    self.tipTimerEnabled = False
    self.tipScroll = 0
    self.tipScrollB = None
    self.tipScrollSpace = self.engine.theme.menuTipTextScrollSpace
    self.tipScale = self.engine.theme.menuTipTextScale
    self.tipDir = 0
    self.tipSize = 0
    self.tipY = self.engine.theme.menuTipTextY
    self.tipScrollMode = self.engine.theme.menuTipTextScrollMode # - 0 for constant scroll; 1 for back and forth
    self.setupSettings()
    #self.menuDict[firstMenu.name] = firstMenu
    self.enterMenu(firstMenu)
  
  def setupSettings(self):
    engine = self.engine
    self.keyCheckerMode = Config.get("game", "key_checker_mode")
    
    self.opt_text_x = self.engine.theme.opt_text_xPos
    self.opt_text_y = self.engine.theme.opt_text_yPos


    self.opt_text_color = self.engine.theme.hexToColor(self.engine.theme.opt_text_colorVar)
    self.opt_selected_color = self.engine.theme.hexToColor(self.engine.theme.opt_selected_colorVar)

    if self.opt_text_color == None:
      self.opt_text_color = (1,1,1)
    if self.opt_selected_color == None:
      self.opt_selected_color = (1,0.75,0)

    modSettings = [
      ConfigChoice(engine, engine.config, "mods",  "mod_" + m) for m in Mod.getAvailableMods(engine)
    ]
    self.modSettings = MenuItem("mods", modSettings, ["main", "settings", "mcai"])
    self.mainMenu.menuDict["mods"] = self.modSettings
    
    self.stageOptions = MenuItem("stage", [
      ConfigChoice(self.engine, self.engine.config, "game", "stage_mode", autoApply = True),   #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "animated_stage_folder", autoApply = True),   #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "song_stage", autoApply = True),   #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "rotate_stages", autoApply = True),   #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "stage_rotate_delay", autoApply = True),   #myfingershurt - user defined stage rotate delay
      ConfigChoice(self.engine, self.engine.config, "game", "stage_animate", autoApply = True),   #myfingershurt - user defined stage rotate delay
      ConfigChoice(self.engine, self.engine.config, "game", "stage_animate_delay", autoApply = True),   #myfingershurt - user defined stage rotate delay
      ConfigChoice(self.engine, self.engine.config, "game", "miss_pauses_anim", autoApply = True),
    ], ["main","settings","video"])
    self.mainMenu.menuDict["stage"] = self.stageOptions
    
    self.hopoSettings = MenuItem("hopo", [
       ConfigChoice(self.engine, self.engine.config, "game", "hopo_system", autoApply = True),      #myfingershurt
       ConfigChoice(self.engine, self.engine.config, "game", "song_hopo_freq", autoApply = True),      #myfingershurt
       ConfigChoice(self.engine, self.engine.config, "game", "hopo_after_chord", autoApply = True),      #myfingershurt
    ], ["main","settings","gameplay"])
    self.mainMenu.menuDict["hopo"] = self.hopoSettings
    
    self.lyricsSettings = MenuItem("vocal", [
       ConfigChoice(self.engine, self.engine.config, "game", "midi_lyric_mode", autoApply = True, isQuickset = 1),      #myfingershurt
       ConfigChoice(self.engine, self.engine.config, "game", "vocal_scroll", autoApply = True, isQuickset = 1),      #akedrou
       ConfigChoice(self.engine, self.engine.config, "game", "vocal_speed", autoApply = True, isQuickset = 1),      #akedrou
       ConfigChoice(self.engine, self.engine.config, "game", "rb_midi_lyrics", autoApply = True, isQuickset = 1),      #myfingershurt
       ConfigChoice(self.engine, self.engine.config, "game", "rb_midi_sections", autoApply = True, isQuickset = 1),      #myfingershurt
       ConfigChoice(self.engine, self.engine.config, "game", "lyric_mode", autoApply = True, isQuickset = 1),      #myfingershurt
       ConfigChoice(self.engine, self.engine.config, "game", "script_lyric_pos", autoApply = True),      #myfingershurt
    ], ["main", "settings", "gameplay"])
    self.mainMenu.menuDict["vocal"] = self.lyricsSettings
    
    self.jurgenSettings = MenuItem("jurgen", self.refreshJurgenSettings(init = True), ["main", "settings", "mcai"])
    self.mainMenu.menuDict["jurgen"] = self.jurgenSettings
           
    self.advancedGameSettings = MenuItem("advgame", [
      ConfigChoice(self.engine, self.engine.config, "performance", "star_score_updates", autoApply = True, isQuickset = 1),   #MFH
      ConfigChoice(self.engine, self.engine.config, "game", "bass_groove_enable", autoApply = True, isQuickset = 2),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "mark_solo_sections", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "decimal_places", autoApply = True), #MFH
      ConfigChoice(self.engine, self.engine.config, "game", "ignore_open_strums", autoApply = True),      #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "big_rock_endings", autoApply = True, isQuickset = 2),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "starpower_mode", autoApply = True),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "party_time", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "keep_play_count", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "lost_focus_pause", autoApply = True),
    ], ["main", "settings", "gameplay"])
    self.mainMenu.menuDict["advgame"] = self.advancedGameSettings
    
    self.battleSettings = MenuItem("battle", [
      ConfigChoice(engine, engine.config, "game", "battle_Whammy", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_Diff_Up", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_String_Break", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_Double", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_Death_Drain", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_Amp_Overload", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_Switch_Controls", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_Steal", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "battle_Tune", autoApply = True),
    ], ["main", "settings", "gameplay"])
    self.mainMenu.menuDict["battle"] = self.battleSettings
    
    # self.battleSettings = [
      # (_("Battle Objects"), self.battleObjectSettingsMenu, _("Set which objects can appear in Battle Mode")),
    # ]
    
    self.basicSettings = MenuItem("gameplay", [
      ConfigChoice(self.engine, self.engine.config, "game",  "language"),
      ConfigChoice(self.engine, self.engine.config, "game", "T_sound", autoApply = True), #Faaa Drum sound
      ConfigChoice(self.engine, self.engine.config, "game", "star_scoring", autoApply = True),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "career_star_min", autoApply = True), #akedrou
      ConfigChoice(self.engine, self.engine.config, "game", "resume_countdown", autoApply = True), #akedrou
      ConfigChoice(self.engine, self.engine.config, "game", "sp_notes_while_active", autoApply = True, isQuickset = 2),   #myfingershurt - setting for gaining more SP while active
      ConfigChoice(self.engine, self.engine.config, "game", "drum_sp_mode", autoApply = True),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "network",  "uploadscores", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "audio",  "delay", autoApply = True),     #myfingershurt: so a/v delay can be set without restarting FoF
      Choice(_("Advanced Gameplay Settings"), self.advancedGameSettings, tipText = _("Set advanced gameplay settings that affect the game rules.")),
      Choice(_("Vocal Mode Settings"), self.lyricsSettings, tipText = _("Change settings that affect lyrics and in-game vocals.")),
      Choice(_("HO/PO Settings"), self.hopoSettings, tipText = _("Change settings that affect hammer-ons and pull-offs (HO/PO).")),
      Choice(_("Battle Settings"), self.battleSettings, tipText = _("Change settings that affect battle mode.")),
    ], ["main", "settings"])
    self.mainMenu.menuDict["gameplay"] = self.basicSettings

    self.keyChangeSettings = MenuItem("key", [
      Choice(_("Test Controller 1"), lambda: self.keyTest(0), tipText = _("Test the controller configured for slot 1.")),
      Choice(_("Test Controller 2"), lambda: self.keyTest(1), tipText = _("Test the controller configured for slot 2.")),
      Choice(_("Test Controller 3"), lambda: self.keyTest(2), tipText = _("Test the controller configured for slot 3.")),
      Choice(_("Test Controller 4"), lambda: self.keyTest(3), tipText = _("Test the controller configured for slot 4.")),
    ], ["main", "settings", "control"])
    self.mainMenu.menuDict["key"] = self.keyChangeSettings
    
    self.keySettings = MenuItem("control", self.refreshKeySettings(init = True), ["main", "settings"], onClose = self.controlCheck)
    self.mainMenu.menuDict["control"] = self.keySettings
    
    self.neckTransparency = MenuItem("fretboardalpha", [
      ConfigChoice(self.engine, self.engine.config, "game", "necks_alpha", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "neck_alpha", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "solo_neck_alpha", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "bg_neck_alpha", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "fail_neck_alpha", autoApply = True), 
      ConfigChoice(self.engine, self.engine.config, "game", "overlay_neck_alpha", autoApply = True),  
    ], ["main", "settings", "video", "fretboard"])
    self.mainMenu.menuDict["fretboardalpha"] = self.neckTransparency
    
    self.shaderSettings = MenuItem("shaders", [      #volshebnyi
      ConfigChoice(self.engine, self.engine.config, "video", "shader_use", autoApply = True), 
      ConfigChoice(self.engine, self.engine.config, "video", "shader_neck", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "video", "shader_stage", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "video", "shader_sololight", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "video", "shader_tail", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "video", "shader_notes", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "video", "shader_cd", autoApply = True),
    ], ["main", "settings", "video"])
    self.mainMenu.menuDict["shaders"] = self.shaderSettings
    
    self.advancedVideoSettings = MenuItem("advvideo", [
      ConfigChoice(self.engine, self.engine.config, "engine", "highpriority", isQuickset = 1),
      ConfigChoice(self.engine, self.engine.config, "video",  "fps", isQuickset = 1),
      ConfigChoice(self.engine, self.engine.config, "video",  "multisamples", isQuickset = 1),
      Choice(_("More Effects"), self.shaderSettings, tipText = _("Change the settings of the shader system.")), #volshebnyi
    ], ["main", "settings", "video"])
    self.mainMenu.menuDict["advvideo"] = self.advancedVideoSettings
    
    self.fretSettings = MenuItem("fretboard", [
      ConfigChoice(self.engine, self.engine.config, "game", "notedisappear", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "frets_under_notes", autoApply = True), #MFH
      ConfigChoice(self.engine, self.engine.config, "game", "nstype", autoApply = True),      #blazingamer
      ConfigChoice(self.engine, self.engine.config, "coffee", "neckSpeed", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "large_drum_neck", autoApply = True),      #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "bass_groove_neck", autoApply = True),      #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "guitar_solo_neck", autoApply = True),      #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "fretboard", "ovrneckoverlay", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "incoming_neck_mode", autoApply = True, isQuickset = 1),
      #myfingershurt 
      Choice(_("Change Neck Transparency"), self.neckTransparency, tipText = _("Change the transparency of the various in-game necks.")), #volshebnyi
    ], ["main", "settings", "video"])
    self.mainMenu.menuDict["fretboard"] = self.fretSettings
    
    # self.themeDisplaySettings = [
      # ConfigChoice(self.engine, self.engine.config, "game", "rb_sp_neck_glow", autoApply = True),
      # ConfigChoice(self.engine, self.engine.config, "game",   "small_rb_mult", autoApply = True), #blazingamer
      # ConfigChoice(self.engine, self.engine.config, "game", "starfx", autoApply = True),
      # ConfigChoice(self.engine, self.engine.config, "performance", "starspin", autoApply = True, isQuickset = 1),
    # ]
    # self.themeDisplayMenu = Menu.Menu(self.engine, self.themeDisplaySettings, pos = (self.opt_text_x, self.opt_text_y), textColor = self.opt_text_color, selectedColor = self.opt_selected_color)
    
    self.inGameDisplaySettings = MenuItem("ingame", [
      # (_("Theme Display Settings"), self.themeDisplayMenu, _("Change settings that only affect certain theme types.")),
      ConfigChoice(self.engine, self.engine.config, "game", "in_game_stars", autoApply = True, isQuickset = 2),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "partial_stars", autoApply = True, isQuickset = 1),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "coffee", "game_phrases", autoApply = True, isQuickset = 1),
      ConfigChoice(self.engine, self.engine.config, "game", "hopo_indicator", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "game", "accuracy_mode", autoApply = True),
      ConfigChoice(self.engine, self.engine.config, "performance", "in_game_stats", autoApply = True, isQuickset = 1),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "gsolo_accuracy_disp", autoApply = True, isQuickset = 1), #MFH
      ConfigChoice(self.engine, self.engine.config, "game", "solo_frame", autoApply = True),      #myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game", "game_time", autoApply = True),  
      ConfigChoice(self.engine, self.engine.config, "video", "counting", autoApply = True, isQuickset = 2),
    ], ["main", "settings", "video"])
    self.mainMenu.menuDict["ingame"] = self.inGameDisplaySettings
    
    modes = self.engine.video.getVideoModes()
    modes.reverse()
    Config.define("video",  "resolution", str,   "1024x768", text = _("Video Resolution"), options = ["%dx%d" % (m[0], m[1]) for m in modes], tipText = _("Set the resolution of the game. In windowed mode, higher values mean a larger screen."))
    self.videoSettings = MenuItem("video", [
      ConfigChoice(engine, engine.config, "coffee", "themename"), #was autoapply... why?
      ConfigChoice(engine, engine.config, "video",  "resolution"),
      ConfigChoice(engine, engine.config, "video",  "fullscreen"),
      ConfigChoice(engine, engine.config, "video", "disable_screensaver"),  #stump
      ConfigChoice(engine, engine.config, "game", "use_graphical_submenu", autoApply = True, isQuickset = 1),
      Choice(_("Stages Options"), self.stageOptions, tipText = _("Change settings related to the in-game background.")),
      Choice(_("Choose Default Neck >"), lambda: Dialogs.chooseNeck(self.engine), tipText = _("Choose your default neck. You still have to choose which neck you use for your character in the character select screen.")),
      Choice(_("Fretboard Settings"), self.fretSettings, tipText = _("Change settings related to the fretboard.")),
      Choice(_("In-Game Display Settings"), self.inGameDisplaySettings, tipText = _("Change what and where things appear in-game.")),
      Choice(_("Advanced Video Settings"), self.advancedVideoSettings, tipText = _("Change advanced video settings.")),
    ], ["main", "settings"])
    self.mainMenu.menuDict["video"] = self.videoSettings
    
    self.volumeSettings = MenuItem("volume", [
      VolumeConfigChoice(engine, engine.config, "audio",  "guitarvol", autoApply = True),
      VolumeConfigChoice(engine, engine.config, "audio",  "songvol", autoApply = True),
      VolumeConfigChoice(engine, engine.config, "audio",  "screwupvol", autoApply = True),
      VolumeConfigChoice(engine, engine.config, "audio",  "miss_volume", autoApply = True),
      VolumeConfigChoice(engine, engine.config, "audio",  "single_track_miss_volume", autoApply = True),
      VolumeConfigChoice(engine, engine.config, "audio",  "crowd_volume", autoApply = True), #akedrou
      VolumeConfigChoice(engine, engine.config, "audio",  "kill_volume", autoApply = True), #MFH
      ActiveConfigChoice(engine, engine.config, "audio",  "SFX_volume", autoApply = True, onChange = self.engine.data.SetAllSoundFxObjectVolumes, volume = True), #MFH
      ActiveConfigChoice(engine, engine.config, "audio",  "menu_volume", autoApply = True, onChange = self.engine.mainMenu.setMenuVolume),
    ], ["main", "settings", "audio"])
    self.mainMenu.menuDict["volume"] = self.volumeSettings
    
    self.advancedAudioSettings = MenuItem("advaudio", [
       ConfigChoice(engine, engine.config, "audio",  "buffersize"),
       ConfigChoice(engine, engine.config, "game", "result_cheer_loop", autoApply = True), #MFH
       ConfigChoice(engine, engine.config, "game", "cheer_loop_delay", autoApply = True), #MFH
    ], ["main", "settings", "audio"])
    self.mainMenu.menuDict["advaudio"] = self.advancedAudioSettings
    
    self.audioSettings = MenuItem("audio", [
      Choice(_("Volume Settings"),    self.volumeSettings, tipText = _("Change the volume of game sounds.")),
      ConfigChoice(engine, engine.config, "game", "sustain_muting", autoApply = True),   #myfingershurt
      ConfigChoice(engine, engine.config, "game", "mute_drum_fill", autoApply = True),
      ConfigChoice(engine, engine.config, "audio", "mute_last_second", autoApply = True), #MFH
      ConfigChoice(engine, engine.config, "game", "bass_kick_sound", autoApply = True),   #myfingershurt
      ConfigChoice(engine, engine.config, "game", "star_claps", autoApply = True),      #myfingershurt
      ConfigChoice(engine, engine.config, "game", "beat_claps", autoApply = True), #racer
      ConfigChoice(engine, engine.config, "audio",  "whammy_effect", autoApply = True),     #MFH
      ConfigChoice(engine, engine.config, "audio", "enable_crowd_tracks", autoApply = True), 
      Choice(_("Advanced Audio Settings"), self.advancedAudioSettings, tipText = _("Change advanced audio settings.")),
    ], ["main", "settings"])
    self.mainMenu.menuDict["audio"] = self.audioSettings
    
    #MFH - new menu
    # self.logfileSettings = MenuItem("log", [
      # ConfigChoice(engine, engine.config, "game", "log_ini_reads", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "game", "log_class_inits", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "game", "log_loadings", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "game", "log_sections", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "game", "log_undefined_gets", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "game", "log_marker_notes", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "game", "log_starpower_misses", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "log",   "log_unedited_midis", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "log",   "log_lyric_events", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "log",   "log_tempo_events", autoApply = True),#myfingershurt
      # ConfigChoice(engine, engine.config, "log",   "log_image_not_found", autoApply = True),
    # ], ["main", "settings", "advanced"])
    # self.mainMenu.menuDict["log"] = self.logfileSettings
    
    self.debugSettings = MenuItem("debug", [
      ConfigChoice(engine, engine.config, "video", "show_fps"),#evilynux
      ConfigChoice(engine, engine.config, "game", "kill_debug", autoApply = True),#myfingershurt
      ConfigChoice(engine, engine.config, "game", "hopo_debug_disp", autoApply = True),#myfingershurt
      ConfigChoice(engine, engine.config, "game", "show_unused_text_events", autoApply = True),#myfingershurt
      ConfigChoice(engine, engine.config, "debug",   "use_unedited_midis", autoApply = True),#myfingershurt
      #ConfigChoice(engine.config, "game", "font_rendering_mode", autoApply = True),#myfingershurt
      ConfigChoice(engine, engine.config, "debug", "show_raw_vocal_data", autoApply = True), #akedrou
      ConfigChoice(engine, engine.config, "debug",   "show_freestyle_active", autoApply = True),#myfingershurt
      ConfigChoice(engine, engine.config, "debug",   "show_bpm", autoApply = True),#myfingershurt
      ConfigChoice(engine, engine.config, "debug",   "use_new_vbpm_beta", autoApply = True),#myfingershurt
      ConfigChoice(engine, engine.config, "debug",   "use_new_song_database", autoApply = True),  #stump
      ConfigChoice(engine, engine.config, "game", "use_new_pitch_analyzer", autoApply = True),  #stump
    ], ["main", "settings", "advanced"])
    self.mainMenu.menuDict["debug"] = self.debugSettings
    
    self.quicksetMenu = MenuItem("quickset", [
      ConfigChoice(engine, engine.config, "quickset", "performance", autoApply = True),
      ConfigChoice(engine, engine.config, "quickset", "gameplay", autoApply = True),
    ], ["main", "settings"])
    self.mainMenu.menuDict["quickset"] = self.quicksetMenu
    
    self.listSettings = MenuItem("setlist", [
      Choice(_("Change Setlist Path >"), self.baseLibrarySelect, tipText = _("Set the path to a folder named 'songs' that contains your songs.")),
      #ConfigChoice(engine, engine.config, "coffee", "song_display_mode", autoApply = True),
      ConfigChoice(engine, engine.config, "game",  "sort_order", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "sort_direction", autoApply = True),
      #ConfigChoice(engine, engine.config, "game", "song_listing_mode", autoApply = True, isQuickset = 2),
      ConfigChoice(engine, engine.config, "game", "quickplay_tiers", autoApply = True),  #myfingershurt
      ConfigChoice(engine, engine.config, "coffee", "songfilepath", autoApply = True),
      #(_("Select List All Folder >"), self.listAllFolderSelect), #- Not Working Yet - Qstick
      ConfigChoice(engine, engine.config, "game", "songcovertype", autoApply = True),
      #ConfigChoice(engine, engine.config, "game", "songlistrotation", autoApply = True, isQuickset = 1),
      #ConfigChoice(engine, engine.config, "performance", "disable_librotation", autoApply = True),
      #ConfigChoice(engine, engine.config, "game", "song_icons", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "queue_parts", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "queue_diff", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "preload_labels", autoApply = True),
      ConfigChoice(engine, engine.config, "audio", "disable_preview", autoApply = True),  #myfingershurt
      ConfigChoice(engine, engine.config, "game", "songlist_instrument", autoApply = True), #MFH
      ConfigChoice(engine, engine.config, "game", "songlist_difficulty", autoApply = True), #evilynux
      ConfigChoice(engine, engine.config, "game",  "whammy_changes_sort_order", autoApply = True), #stump
      #ConfigChoice(engine, engine.config, "game", "songlist_extra_stats", autoApply = True), #evilynux
      ConfigChoice(engine, engine.config, "game", "HSMovement", autoApply = True), #racer
      ConfigChoice(engine, engine.config, "performance", "disable_libcount", autoApply = True, isQuickset = 1), 
      ConfigChoice(engine, engine.config, "performance", "cache_song_metadata", autoApply = True, isQuickset = 1), #stump
      ConfigChoice(engine, engine.config, "songlist",  "nil_show_next_score", autoApply = True), #MFH
    ], ["main", "settings"])
    self.mainMenu.menuDict["setlist"] = self.listSettings
    
    advancedSettings = MenuItem("advanced", [
      ConfigChoice(engine, engine.config, "performance", "game_priority", autoApply = True, isQuickset = 1),
      ConfigChoice(engine, engine.config, "performance", "restrict_to_first_processor"),  #stump
      ConfigChoice(engine, engine.config, "performance", "use_psyco"),
      Choice(_("Debug Settings"), self.debugSettings, tipText = _("Settings for coders to debug. Probably not worth changing.")),
      #Choice(_("Log Settings"),    self.logfileSettings, tipText = _("Adds junk information to the logfile. Probably not useful in bug reports.")),
    ], ["main", "settings"])
    self.mainMenu.menuDict["advanced"] = advancedSettings
    
    self.cheats = MenuItem("mcai", [
      Choice(_("AI Settings"), self.jurgenSettings, tipText = _("Change the settings of the AI")),
      ConfigChoice(engine, engine.config, "game", "gh2_sloppy", autoApply = True),
      ConfigChoice(engine, engine.config, "game", "whammy_saves_starpower", autoApply = True),#myfingershurt
      ConfigChoice(self.engine, self.engine.config, "game",   "note_hit_window", autoApply = True), #alarian: defines hit window
      ConfigChoice(engine, engine.config, "coffee", "hopo_frequency", autoApply = True),
      ConfigChoice(engine, engine.config, "coffee", "failingEnabled", autoApply = True),
      ConfigChoice(engine, engine.config, "audio",  "speed_factor", autoApply = True),     #MFH
      ConfigChoice(engine, engine.config, "handicap",  "early_hit_window", autoApply = True),     #MFH
      ConfigChoice(engine, engine.config, "handicap", "detailed_handicap", autoApply = True),
      Choice(_("Mod settings"), self.modSettings, tipText = _("Enable or disable any mods you have installed."), display = bool(len(modSettings))),
    ], ["main", "settings"])
    self.mainMenu.menuDict["mcai"] = self.cheats
    
    settings = [
      Choice(_("Gameplay Settings"),   self.basicSettings, tipText = _("Settings that affect the rules of the game.")),
      Choice(_("Control Settings"),     self.keySettings, tipText = _("Create, delete, and edit your controls.")),
      Choice(_("Display Settings"),     self.videoSettings, tipText = _("Theme, neck, resolution, etc.")),
      Choice(_("Audio Settings"),      self.audioSettings, tipText = _("Volume controls, etc.")),
      Choice(_("Setlist Settings"),   self.listSettings, tipText = _("Settings that affect the setlist.")),
      Choice(_("Advanced Settings"), self.advancedSettings, tipText = _("Settings that probably don't need to be changed.")),
      Choice(_("Mods, Cheats, AI"), self.cheats, tipText = _("Set Jurgen to play for you, or other cheats.")),
      Choice(_("%s Credits") % (Version.PROGRAM_NAME), lambda: Dialogs.showCredits(engine), tipText = _("See who made this game.")),
      Choice(_("Quickset"), self.quicksetMenu, tipText = _("A quick way to set many advanced settings.")),
      Choice(_("Hide Advanced Options"), self.advancedSettings)
    ]
  
    self.settingsToApply = self.videoSettings.choices + \
                           self.advancedAudioSettings.choices + \
                           self.advancedVideoSettings.choices + \
                           self.basicSettings.choices + \
                           self.keySettings.choices + \
                           self.inGameDisplaySettings.choices + \
                           self.debugSettings.choices + \
                           self.quicksetMenu.choices + \
                           self.modSettings.choices

    self.settingsMenu = MenuItem("settings", settings, ["main"], onCancel = self.applySettings)
    self.mainMenu.menuDict["settings"] = self.settingsMenu
  
  def enterMenu(self, nextMenu):
    if isinstance(nextMenu, list):
      index = nextMenu[1]
      nextMenu = nextMenu[0]
    else:
      if isinstance(nextMenu, str):
        nextMenu = self.mainMenu.menuDict[nextMenu]
      index = nextMenu.selectedIndex
    self.menuName   = nextMenu.name
    self.menuItem   = nextMenu
    self.breadcrumb = nextMenu.breadcrumb
    if self.menuName:
      if self.menuName not in self.loadedMenus:
        self.engine.data.loadAllImages(self, os.path.join("themes",self.themename,"menu",self.menuName), "img_%s" % self.menuName)
        self.loadedMenus.append(self.menuName)
      try:
        self.gfxText = "%stext%d" % (self.menuName, len(nextMenu.choices))
        self.menuText = self.__dict__["img_%s" % self.gfxText]
        try:
          self.menuBackground = self.__dict__["img_%sbackground" % self.menuName]
        except KeyError:
          self.menuBackground = None
        self.menux = self.engine.theme.submenuX[self.gfxText]
        self.menuy = self.engine.theme.submenuY[self.gfxText]
        self.menuScale = self.engine.theme.submenuScale[self.gfxText]
        self.vSpace = self.engine.theme.submenuVSpace[self.gfxText]
        if str(self.menux) != "None" and str(self.menuy) != "None":
          self.menux = float(self.menux)
          self.menuy = float(self.menuy)
        else:
          self.menux = .4
          self.menuy = .4
        if str(self.menuScale) != "None":
          self.menuScale = float(self.menuScale)
        else:
          self.menuScale = .5
        if str(self.vSpace) != "None":
          self.vSpace = float(self.vSpace)
        else:
          self.vSpace = .08
        self.graphicMenu = True
      except KeyError:
        Log.warn("Your theme does not appear to properly support the %s graphical submenu. Check to be sure you have the latest version of your theme." % self.menuName)
        self.menuBackground = None
        self.menuText = None
        self.graphicMenu = False
    else:
      self.menuBackground = None
      self.menuText = None
      self.graphicMenu = False
    if self.menuName == "main": self.graphicMenu = False
    if index:
      self.currentIndex = index
    else:
      self.currentIndex = 0
    self.onClose = nextMenu.onClose
    self.onCancel = nextMenu.onCancel
    self.choices = nextMenu.choices
    
    self.itemBoxArea = []
    x, y = self.pos
    wS, hS = self.engine.view.geometry[2:4]
    for i, c in enumerate(self.choices):
      if self.graphicMenu:
        Iw = self.menuText.width1()
        Ih = self.menuText.height1()
        xA = wS*(1.0-self.menux)-(Iw*.5*self.menuScale)
        xB = wS*(1.0-self.menux)+(Iw*.5*self.menuScale)
        yA = hS*(self.menuy+self.vSpace*i)-(Ih*self.menuScale*(1/float(len(self.choices))))
        yB = hS*(self.menuy+self.vSpace*i)+(Ih*self.menuScale*(1/float(len(self.choices))))
        self.itemBoxArea.append(((xA, xB), (yA, yB)))
      else:
        Tw, Th = self.font.getStringSize(c.text, .002)
        lineSpacing = self.font.getLineSpacing(.002)
        xA = x*wS
        xB = xA + (Tw*wS)
        yA = ((y*4.0/3.0)-Th*.5)*hS
        yB = yA + (Th*1.0*hS)
        y += Th
        self.itemBoxArea.append(((xA, xB), (yA, yB)))
    if self.graphicMenu:
      self.lineH = self.vSpace*hS
    else:
      self.lineH = (Th + lineSpacing)*hS
    
    self.setTipScroll()
  
  def selectItem(self, index):
    self.currentIndex = index
    
  def shown(self):
    self.engine.input.addKeyListener(self)
    self.engine.input.addMouseListener(self)
    self.engine.input.showMouse()
    
  def hidden(self):
    self.engine.input.removeKeyListener(self)
    self.engine.input.removeMouseListener(self)
    self.engine.input.hideMouse()
    if self.onClose:
      self.onClose()

  def updateSelection(self):
    self.setTipScroll()
    if self.currentIndex > self.viewOffset + self.viewSize - 1:
      self.viewOffset = self.currentIndex - self.viewSize + 1
    if self.currentIndex < self.viewOffset:
      self.viewOffset = self.currentIndex
    if self.viewOffset > 0:
      self.buttons["up"].visible = True
    else:
      self.buttons["up"].visible = False
    if self.viewOffset + self.viewSize < len(self.choices):
      self.buttons["down"].visible = True
    else:
      self.buttons["down"].visible = False
  
  def cancel(self):
    if self.onCancel:
      self.onCancel()
    if len(self.breadcrumb) > 0:
      nextMenu = self.breadcrumb.pop()
      self.enterMenu(nextMenu)
      self.engine.data.cancelSound.play()
    else:
      self.engine.view.popLayer(self)
      self.engine.input.removeKeyListener(self)
      self.engine.data.cancelSound.play()
  
  def keyPressed(self, key, unicode):
    choice = self.choices[self.currentIndex]
    c = self.engine.input.controls.getMapping(key)
    if c in Player.menuYes or key == pygame.K_RETURN:
      self.scrolling = 0
      self.mainMenu.menuDict[self.menuName].selectedIndex = self.currentIndex
      choice.trigger(self.engine)
      self.engine.data.acceptSound.play()
    elif c in Player.menuNo or key == pygame.K_ESCAPE:
      self.cancel()
    elif c in Player.menuDown or key == pygame.K_DOWN:
      self.scrolling = 2
      self.delay = self.engine.scrollDelay
      self.scrollDown()
    elif c in Player.menuUp or key == pygame.K_UP:
      self.scrolling = 1
      self.delay = self.engine.scrollDelay
      self.scrollUp()
    elif c in Player.menuNext or key == pygame.K_RIGHT:
      self.scrolling = 4
      self.delay = self.engine.scrollDelay
      self.scrollRight()
    elif c in Player.menuPrev or key == pygame.K_LEFT:
      self.scrolling = 3
      self.delay = self.engine.scrollDelay
      self.scrollLeft()
    elif key == pygame.K_m:
      print self.itemBoxArea
    return True
  
  def scrollDown(self):
    self.engine.data.selectSound.play()
    self.currentIndex = (self.currentIndex + 1) % len(self.choices)
    self.updateSelection()
  
  def scrollUp(self):
    self.engine.data.selectSound.play()
    self.currentIndex = (self.currentIndex - 1) % len(self.choices)
    self.updateSelection()
  
  def scrollLeft(self):
    self.choices[self.currentIndex].selectPreviousValue()
    
  def scrollRight(self):
    self.choices[self.currentIndex].selectNextValue()
  
  def keyReleased(self, key):
    self.scrolling = 0
  
  def mouseMoved(self, pos, rel):
    x, y = pos
    for button in self.buttons.values():
      xA, xB = button.xRange
      yA, yB = button.yRange
      if x > xA and x < xB and y > yA and y < yB:
        button.hovered = True
      else:
        button.hovered = False
    for i, box in enumerate(self.itemBoxArea):
      y += self.lineH*self.viewOffset
      if i < self.viewOffset:
        continue
      elif i > self.viewOffset+self.viewSize:
        break
      xS, yS = box
      xA, xB = xS
      yA, yB = yS
      if x > xA and x < xB and y > yA and y < yB:
        self.currentIndex = i
        self.updateSelection()
        return
    return True
  
  def mouseButtonPressed(self, button, pos):
    if button == 1:
      for box in self.buttons.values():
        if box.hovered:
          box.pressed = True
  
  def mouseButtonReleased(self, button, pos):
    if button == 1:
      ret = None
      click = False #allows all buttons to set to "not pressed"
      for box in self.buttons.values():
        if box.pressed and box.hovered and not click:
          ret = box.click()
          click = True
      else:
        for box in self.buttons.values():
          box.pressed = False
        if click:
          return ret
        box = self.itemBoxArea[self.currentIndex]
        x, y   = pos
        xS, yS = box
        xA, xB = xS
        yA, yB = yS
        if x > xA and x < xB and y > yA and y < yB:
          self.scrolling = 0
          self.choices[self.currentIndex].trigger(self.engine)
          self.engine.data.acceptSound.play()
    elif button == 4:
      self.mouseScrollUp()
    elif button == 5:
      self.mouseScrollDown()
    return True
  
  def mouseScrollUp(self):
    self.viewOffset -= 3
    if self.viewOffset < 0:
      self.viewOffset = 0
    if self.currentIndex >= self.viewOffset + self.viewSize:
      self.currentIndex = self.viewOffset + self.viewSize - 1
    self.updateSelection()
  
  def mouseScrollDown(self):
    self.viewOffset += 3
    if self.viewOffset > len(self.choices) - self.viewSize:
      self.viewOffset = len(self.choices) - self.viewSize
      if self.viewOffset < 0:
        self.viewOffset = 0
    if self.currentIndex < self.viewOffset:
      self.currentIndex = self.viewOffset
    self.updateSelection()
  
  def run(self, ticks):
    self.time += ticks / 50.0
    if self.scrolling > 0:
      self.delay -= ticks
      self.rate += ticks
      if self.delay <= 0 and self.rate >= self.engine.scrollRate:
        self.rate = 0
        self.scroller[self.scrolling]()
    if self.tipTimerEnabled:
      if self.tipDelay > 0:
        self.tipDelay -= ticks
        if self.tipDelay <= 0:
          self.tipDelay = 0
          self.tipDir = (self.tipDir+1)&1
      elif self.tipDir == 1 and self.tipScrollMode == 1:
        self.tipScroll -= ticks/8000.0
        if self.tipScroll < -(self.tipSize-.98):
          self.tipScroll = -(self.tipSize-.98)
          self.tipDelay = 900
      elif self.tipDir == 0 and self.tipScrollMode == 1:
        self.tipScroll += ticks/8000.0
        if self.tipScroll > .02:
          self.tipScroll = .02
          self.tipDelay = 900
      elif self.tipScrollMode == 0:
        self.tipScroll  -= ticks/8000.0
        self.tipScrollB -= ticks/8000.0
        if self.tipScroll < -(self.tipSize):
          self.tipScroll = self.tipScrollB + self.tipSize + self.tipScrollSpace
        if self.tipScrollB < -(self.tipSize):
          self.tipScrollB = self.tipScroll + self.tipSize + self.tipScrollSpace

  def renderTriangle(self, up = (0, 1), s = .2):
    left = (-up[1], up[0])
    glBegin(GL_TRIANGLES)
    glVertex2f( up[0] * s,  up[1] * s)
    glVertex2f((-up[0] + left[0]) * s, (-up[1] + left[1]) * s)
    glVertex2f((-up[0] - left[0]) * s, (-up[1] - left[1]) * s)
    glEnd()
  
  def setTipScroll(self):
    if self.choices[self.currentIndex].tipText is None:
      return
    tipW, tipH = self.tipFont.getStringSize(self.choices[self.currentIndex].tipText, self.tipScale)
    if tipW > .99:
      self.tipSize = tipW
      self.tipDelay = 1000
      self.tipTimerEnabled = True
      self.tipScroll = 0.02
      self.tipScrollB = 0.02 + self.tipSize + self.tipScrollSpace
      self.tipWait = False
      self.tipDir = 0
    else:
      self.tipScroll = .5 - tipW/2
      self.tipScrollB = None
      self.tipTimerEnabled = False
      self.tipDir = 0
      self.tipSize = tipW
  
  def applySettings(self):
    quickset(self.engine.config)
    if self.engine.restartRequired or self.engine.quicksetRestart:
      Dialogs.showMessage(self.engine, _("FoFiX needs to restart to apply setting changes."))
      for option in self.settingsToApply:
        if isinstance(option, ConfigChoice):
          option.apply()
      self.engine.restart()
  
  def refreshJurgenSettings(self, init = False):
    choices = []
    maxplayer = self.engine.config.get("performance", "max_players")
    for i in range(maxplayer):
      choices.append(ConfigChoice(self.engine, self.engine.config, "game", "jurg_p%d" % i, autoApply = True))
      choices.append(ConfigChoice(self.engine, self.engine.config, "game", "jurg_skill_p%d" % i, autoApply = True))
      choices.append(ConfigChoice(self.engine, self.engine.config, "game", "jurg_logic_p%d" % i, autoApply = True))
    if init:
      return choices
    self.engine.mainMenu.settingsMenuObject.jurgenSettingsMenu.choices = choices
  
  def refreshKeySettings(self, init = False):
    choices = [ #the reacharound
      Choice(_("Test Controls"), self.keyChangeSettings, tipText = _("Go here to test your controllers.")),
      ActiveConfigChoice(self.engine, self.engine.config, "game", "control0", onChange = self.engine.input.reloadControls),
      ActiveConfigChoice(self.engine, self.engine.config, "game", "control1", onChange = self.engine.input.reloadControls),
      ActiveConfigChoice(self.engine, self.engine.config, "game", "control2", onChange = self.engine.input.reloadControls),
      ActiveConfigChoice(self.engine, self.engine.config, "game", "control3", onChange = self.engine.input.reloadControls),
      Choice(_("New Controller"),    lambda: createControl(self.engine, refresh = self.refreshKeySettings), tipText = _("Create a new controller to use.")),
      Choice(_("Edit Controller"),   lambda: chooseControl(self.engine, refresh = self.refreshKeySettings), tipText = _("Edit a controller you have created.")),
      Choice(_("Delete Controller"), lambda: chooseControl(self.engine, "delete", refresh = self.refreshKeySettings), tipText = _("Delete a controller you have created.")),
      ActiveConfigChoice(self.engine, self.engine.config, "performance", "max_players", onChange = self.refreshJurgenSettings), #akedrou
      ActiveConfigChoice(self.engine, self.engine.config, "game", "scroll_delay", onChange = self.scrollSet),
      ActiveConfigChoice(self.engine, self.engine.config, "game", "scroll_rate", onChange = self.scrollSet),
      ActiveConfigChoice(self.engine, self.engine.config, "game", "p2_menu_nav", onChange = self.engine.input.reloadControls),#myfingershurt
      ActiveConfigChoice(self.engine, self.engine.config, "game", "drum_navigation", onChange = self.engine.input.reloadControls),#myfingershurt
      ActiveConfigChoice(self.engine, self.engine.config, "game", "key_checker_mode", onChange = self.engine.input.reloadControls),#myfingershurt
    ]
    if init:
      return choices
    self.engine.mainMenu.settingsMenuObject.keySettingsMenu.choices = choices
  
  def controlCheck(self):
    control = [self.engine.config.get("game", "control0")]
    self.keyCheckerMode = Config.get("game", "key_checker_mode")
    if str(control[0]) == "None":
      Dialogs.showMessage(self.engine, _("You must specify a controller for slot 1!"))
      self.enterMenu(self.keySettings)
    else:
      for i in range(1,4):
        c = self.engine.config.get("game", "control%d" % i)
        if c in control and str(c) != "None":
          Dialogs.showMessage(self.engine, _("Controllers in slots %d and %d conflict. Setting %d to None.") % (control.index(c)+1, i+1, i+1))
          self.engine.config.set("game", "control%d" % i, None)
        else:
          control.append(c)
      self.engine.input.reloadControls()
      if len(self.engine.input.controls.overlap) > 0 and self.keyCheckerMode > 0:
        n = 0
        for i in self.engine.input.controls.overlap:
          if n > 2 and len(self.engine.input.controls.overlap) > 4:
            Dialogs.showMessage(self.engine, _("%d more conflicts.") % (len(self.engine.input.controls.overlap)-3))
            break
          Dialogs.showMessage(self.engine, i)
          n+= 1
        if self.keyCheckerMode == 2:
          self.enterMenu(self.keySettings)
      self.refreshKeySettings()
  
  def advancedSettings(self):
    Config.set("game", "adv_settings", False)
    self.engine.advSettings = False
    if not self.engine.restartRequired:
      self.engine.view.popLayer(self)
      self.engine.input.removeKeyListener(self)
    else:
      self.applySettings()

  def keyTest(self, controller):
    if str(self.engine.input.controls.controls[controller]) == "None":
      Dialogs.showMessage(self.engine, "No controller set for slot %d" % (controller+1))
    else:
      Dialogs.testKeys(self.engine, controller)
  
  def scrollSet(self):
    self.engine.scrollRate = self.engine.config.get("game", "scroll_rate")
    self.engine.scrollDelay = self.engine.config.get("game", "scroll_delay")

  def resetLanguageToEnglish(self):
    Log.debug("settings.resetLanguageToEnglish function call...")
    if self.engine.config.get("game", "language") != "":
      self.engine.config.set("game", "language", "")
      self.engine.restart()

  def baseLibrarySelect(self):
    Log.debug("settings.baseLibrarySelect function call...")
    newPath = Dialogs.chooseFile(self.engine, masks = ["*/*"], prompt = _("Choose a new songs directory."), dirSelect = True)
    if newPath != None:
      Config.set("setlist", "base_library", os.path.dirname(newPath))
      Config.set("setlist", "selected_library", os.path.basename(newPath))
      Config.set("setlist", "selected_song", "")
      self.engine.resource.refreshBaseLib()   #myfingershurt - to let user continue with new songpath without restart
  
  def getButtonImage(self, button):
    if button.pressed:
      try:
        try:
          return self.__dict__["img_%s%sp" % (self.menuName, button.name)]
        except KeyError:
          return self.__dict__["img_%sp" % button.name]
      except KeyError:
        pass
    if button.hovered:
      try:
        try:
          return self.__dict__["img_%s%sh" % (self.menuName, button.name)]
        except KeyError:
          return self.__dict__["img_%sh" % button.name]
      except KeyError:
        pass
    try:
      return self.__dict__["img_%s%sb" % (self.menuName, button.name)]
    except KeyError:
      return self.__dict__["img_%sb" % button.name]
  
  def render(self, visibility, topMost):
    #MFH - display version in any menu:

    if not visibility:
      self.active = False
      return

    self.active = True
    if self.graphicMenu and self.menuBackground:
      self.engine.graphicMenuShown = True
    else:
      self.engine.graphicMenuShown = False
    
    self.engine.view.setOrthogonalProjection(normalize = True)
    try:
      v = (1 - visibility) ** 2
      # Default to this font if none was specified

      font = self.font
      tipFont = self.tipFont

      if self.fadeScreen:
        Dialogs.fadeScreen(v)
        
      wS, hS = self.engine.view.geometry[2:4]
        
      if self.graphicMenu and self.menuBackground:
        #volshebnyi - better menu scaling
        self.engine.drawImage(self.menuBackground, scale = (1.0,-1.0), coord = (wS/2,hS/2), stretched = 3)
      else:
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_COLOR_MATERIAL)

      n = len(self.choices)
      x, y = self.pos

      for i, choice in enumerate(self.choices[self.viewOffset:self.viewOffset + self.viewSize]):
        if self.graphicMenu:
          if self.currentIndex == i:
            xpos = (.5,1)
          else:
            xpos = (0,.5)
          ypos = float(i+self.viewOffset)
          self.menuText.transform.reset()
          self.menuText.transform.scale(.5*self.menuScale,(-1.0/n*self.menuScale))
          self.menuText.transform.translate(wS*self.menux,(hS*self.menuy)-(hS*self.vSpace)*i)
          self.menuText.draw(rect = (xpos[0],xpos[1],ypos/n,(ypos+1.0)/n))
          #self.engine.drawImage(self.menuText, scale = (self.menuScale,-self.menuScale*2/n), coord = (wS*self.menux,hS*(self.menuy-self.vSpace*i)), rect = (xpos[0],xpos[1],ypos/n,(ypos+1.0)/n), stretched = 11)
        else:
          text = choice.getText(i + self.viewOffset == self.currentIndex)
          glPushMatrix()
          glRotate(v * 45, 0, 0, 1)

          scale = 0.002
          # if self.mainMenu and self.theme < 2 and i % 2 == 1:#8bit
              # scale = 0.0016

          w, h = font.getStringSize(" ", scale = scale)

          # Draw arrows if scrolling is needed to see all items
          if i == 0 and self.viewOffset > 0:
            self.engine.theme.setBaseColor((1 - v) * max(.1, 1 - (1.0 / self.viewOffset) / 3))
            glPushMatrix()
            glTranslatef(x - v / 4 - w * 2, y + h / 2, 0)
            self.renderTriangle(up = (0, -1), s = .015)
            glPopMatrix()
          elif i == self.viewSize - 1 and self.viewOffset + self.viewSize < n:
            self.engine.theme.setBaseColor((1 - v) * max(.1, 1 - (1.0 / (n - self.viewOffset - self.viewSize)) / 3))
            glPushMatrix()
            glTranslatef(x - v / 4 - w * 2, y + h / 2, 0)
            self.renderTriangle(up = (0, 1), s = .015)
            glPopMatrix()

          if i + self.viewOffset == self.currentIndex:
            if choice.tipText and self.showTips:
              if self.tipColor:
                c1, c2, c3 = self.tipColor
                glColor3f(c1,c2,c3)
              elif self.textColor:
                c1, c2, c3 = self.textColor
                glColor3f(c1,c2,c3)
              else:
                self.engine.theme.setBaseColor(1-v)
              tipScale = self.tipScale
              if self.tipScroll > -(self.tipSize) and self.tipScroll < 1:
                tipFont.render(choice.tipText, (self.tipScroll, self.tipY), scale = tipScale)
              if self.tipScrollMode == 0:
                if self.tipScrollB > -(self.tipSize) and self.tipScrollB < 1:
                  tipFont.render(choice.tipText, (self.tipScrollB, self.tipY), scale = tipScale)
            a = (math.sin(self.time) * .15 + .75) * (1 - v * 2)
            self.engine.theme.setSelectedColor(a)
            a *= -.005
            glTranslatef(a, a, a)
          else:
            self.engine.theme.setBaseColor(1 - v)      
        
          #MFH - settable color through Menu constructor
          if i + self.viewOffset == self.currentIndex and self.selectedColor:
            c1,c2,c3 = self.selectedColor
            glColor3f(c1,c2,c3)
          elif self.textColor:
            c1,c2,c3 = self.textColor
            glColor3f(c1,c2,c3)
        
          #MFH - now to catch " >" main menu options and blank them:
          if text == " >":
            text = ""
            
          font.render(text, (x - v / 4, y), scale = scale)
        
        
          v *= 2
          if self.theme == 1 and self.font == self.engine.data.pauseFont: # evilynux - Ugly workaround for Gh3
            y += h*.70      #Worldrave - Changed Pause menu spacing back to .70 from .65 for now.
          else:
            y += h
          glPopMatrix()
    
      for button in self.buttons.values():
        if button.visible:
          img = self.getButtonImage(button)
          imgwidth = img.width1()
          wfactor = (button.imgXRange[1]-button.imgXRange[0])/imgwidth
          self.engine.drawImage(img, scale = (wfactor, -wfactor), coord = ((button.imgXRange[0] + button.imgXRange[1])*.5, hS-((button.imgYRange[0])+(button.imgYRange[1]))*.5))
    finally:
      self.engine.view.resetProjection()

class ControlChooser(Menu):
  def __init__(self, engine, mode, options):
    self.engine  = engine
    self.mode    = mode
    self.options = options
    self.default = self.engine.config.get("game", "control0")
    
    self.logClassInits = self.engine.config.get("game", "log_class_inits")
    if self.logClassInits == 1:
      Log.debug("ControlChooser class init (Settings.py)...")
    
    self.selected = None
    self.d        = None
    self.creating = False
    self.time     = 0.0

    Menu.__init__(self, self.engine, choices = [(c, self._callbackForItem(c)) for c in options])
    if self.default in options:
      self.selectItem(options.index(self.default))
    
  def _callbackForItem(self, item):
    def cb():
      self.choose(item)
    return cb
    
  def choose(self, item):
    self.selected = item
    if self.mode == 0:
      createControl(self.engine, self.selected, edit = True)
      self.engine.view.popLayer(self)
    else:
      self.delete(self.selected)
  
  def delete(self, item):
    tsYes = _("Yes")
    q = Dialogs.chooseItem(self.engine, [tsYes, _("No")], _("Are you sure you want to delete this controller?"))
    if q == tsYes:
      Player.deleteControl(item)
      self.engine.view.popLayer(self)

class ControlCreator(BackgroundLayer, KeyListener):
  def __init__(self, engine, control = "", edit = False):
    self.engine  = engine
    self.control = control
    self.edit    = edit
    self.logClassInits = self.engine.config.get("game", "log_class_inits")
    if self.logClassInits == 1:
      Log.debug("ControlCreator class init (Settings.py)...")
    
    self.time   = 0.0
    self.badname     = ["defaultg", "defaultd", "defaultm"] #ensures that defaultm is included - duplicate is ok
    for i in Player.controllerDict.keys():
      self.badname.append(i.lower())
    
    self.menu = None
    self.config = None
  
  def shown(self):
    while (self.control.strip().lower() in self.badname or self.control.strip() == "") and not self.edit:
      self.control = Dialogs.getText(self.engine, _("Please name your controller"), self.control)
      if self.control.strip().lower() in self.badname:
        Dialogs.showMessage(self.engine, _("That name is already taken."))
      elif self.control.strip() == "":
        Dialogs.showMessage(self.engine, _("Canceled."))
        self.cancel()
        break
    else:
      self.setupMenu()
  
  def cancel(self):
    Player.loadControls()
    self.engine.input.reloadControls()
    self.engine.view.popLayer(self.menu)
    self.engine.view.popLayer(self)
  
  def setupMenu(self):
    self.config = None
    if not os.path.isfile(os.path.join(Player.controlpath, self.control + ".ini")):
      cr = open(os.path.join(Player.controlpath, self.control + ".ini"),"w")
      cr.close()
    self.config = Config.load(os.path.join(Player.controlpath, self.control + ".ini"), type = 1)
    name = self.config.get("controller", "name")
    if name != self.control:
      self.config.set("controller", "name", self.control)
    type = self.config.get("controller", "type")
    
    if type != 5:
      if str(self.config.get("controller", "key_1")) == "None":
        self.config.set("controller", "key_1", self.config.getDefault("controller", "key_1"))
      if str(self.config.get("controller", "key_2")) == "None":
        self.config.set("controller", "key_2", self.config.getDefault("controller", "key_2"))
      if str(self.config.get("controller", "key_3")) == "None":
        self.config.set("controller", "key_3", self.config.getDefault("controller", "key_3"))
      if str(self.config.get("controller", "key_4")) == "None":
        self.config.set("controller", "key_4", self.config.getDefault("controller", "key_4"))
      if str(self.config.get("controller", "key_action1")) == "None":
        self.config.set("controller", "key_action1", self.config.getDefault("controller", "key_action1"))
      if str(self.config.get("controller", "key_action2")) == "None":
        self.config.set("controller", "key_action2", self.config.getDefault("controller", "key_action2"))
    
    if type == 0:
      self.config.set("controller", "key_1a", None)
      if str(self.config.get("controller", "key_5")) == "None":
        self.config.set("controller", "key_5", self.config.getDefault("controller", "key_5"))
      if str(self.config.get("controller", "key_kill")) == "None":
        self.config.set("controller", "key_kill", self.config.getDefault("controller", "key_kill"))
      controlKeys = [
        ActiveConfigChoice(self.engine, self.config, "controller", "type", self.changeType),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_5"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_5a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_left", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_right", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_up", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_down", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_cancel"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_start"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_star", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_kill"),
        ConfigChoice(   self.engine, self.config, "controller", "analog_kill", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_threshold", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_sensitivity", autoApply = True),
        #ConfigChoice(   self.engine, self.config, "controller", "analog_fx", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "two_chord_max", autoApply = True),
        (_("Rename Controller"), self.renameController),
      ]
    elif type == 1:
      self.config.set("controller", "key_2a", None)
      self.config.set("controller", "key_3a", None)
      self.config.set("controller", "key_4a", None)
      self.config.set("controller", "key_5a", None)
      if str(self.config.get("controller", "key_5")) == "None":
        self.config.set("controller", "key_5", self.config.getDefault("controller", "key_5"))
      if str(self.config.get("controller", "key_1a")) == "None":
        self.config.set("controller", "key_1a", self.config.getDefault("controller", "key_1a"))
      if str(self.config.get("controller", "key_kill")) == "None":
        self.config.set("controller", "key_kill", self.config.getDefault("controller", "key_kill"))
      
      controlKeys = [
        ActiveConfigChoice(self.engine, self.config, "controller", "type", self.changeType),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_5"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1a", shift = _("Press the solo shift key. Be sure to assign the frets first! Hold Escape to cancel.")),
        KeyConfigChoice(self.engine, self.config, "controller", "key_left", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_right", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_up", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_down", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_cancel"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_start"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_star", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_kill"),
        ConfigChoice(   self.engine, self.config, "controller", "analog_kill", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_threshold", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_sensitivity", autoApply = True),
        #ConfigChoice(   self.engine, self.config, "controller", "analog_fx", autoApply = True),
        (_("Rename Controller"), self.renameController),
      ]
    elif type == 2:
      self.config.set("controller", "key_5", None)
      self.config.set("controller", "key_5a", None)
      self.config.set("controller", "key_kill", None)
        
      controlKeys = [
        ActiveConfigChoice(self.engine, self.config, "controller", "type", self.changeType),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action2", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_left", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_right", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_up", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_down", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_cancel"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_start"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_star", True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_threshold", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_sensitivity", autoApply = True),
        #ConfigChoice(   self.engine, self.config, "controller", "analog_drum", autoApply = True),
        (_("Rename Controller"), self.renameController),
      ]
    elif type == 3:
      self.config.set("controller", "key_kill", None)
      controlKeys = [
        ActiveConfigChoice(self.engine, self.config, "controller", "type", self.changeType),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_5"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_5a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1a", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action2", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_left", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_right", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_up", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_down", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_cancel"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_start"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_star", True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_threshold", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_sensitivity", autoApply = True),
        #ConfigChoice(   self.engine, self.config, "controller", "analog_drum", autoApply = True),
        (_("Rename Controller"), self.renameController),
      ]
    elif type == 4:
      self.config.set("controller", "key_2a", None)
      self.config.set("controller", "key_3a", None)
      self.config.set("controller", "key_4a", None)
      self.config.set("controller", "key_5a", None)
      if str(self.config.get("controller", "key_5")) == "None":
        self.config.set("controller", "key_5", self.config.getDefault("controller", "key_5"))
      if str(self.config.get("controller", "key_1a")) == "None":
        self.config.set("controller", "key_1a", self.config.getDefault("controller", "key_1a"))
      if str(self.config.get("controller", "key_kill")) == "None":
        self.config.set("controller", "key_kill", self.config.getDefault("controller", "key_kill"))
      
      controlKeys = [
        ActiveConfigChoice(self.engine, self.config, "controller", "type", self.changeType),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_action2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_2"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_3"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_4"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_5"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_1a", shift = _("Press the highest fret on the slider. Hold Escape to cancel.")),
        KeyConfigChoice(self.engine, self.config, "controller", "key_left", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_right", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_up", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_down", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_cancel"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_start"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_star"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_kill"),
        ConfigChoice(   self.engine, self.config, "controller", "analog_kill", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_slide", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_threshold", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "analog_sp_sensitivity", autoApply = True),
        #ConfigChoice(   self.engine, self.config, "controller", "analog_fx", autoApply = True),
        (_("Rename Controller"), self.renameController),
      ]
    elif type == 5:
      self.config.set("controller", "key_1", None)
      self.config.set("controller", "key_2", None)
      self.config.set("controller", "key_3", None)
      self.config.set("controller", "key_4", None)
      self.config.set("controller", "key_5", None)
      self.config.set("controller", "key_1a", None)
      self.config.set("controller", "key_2a", None)
      self.config.set("controller", "key_3a", None)
      self.config.set("controller", "key_4a", None)
      self.config.set("controller", "key_5a", None)
      self.config.set("controller", "key_kill", None)
      self.config.set("controller", "key_star", None)
      self.config.set("controller", "key_action1", None)
      self.config.set("controller", "key_action2", None)
      controlKeys = [
        ActiveConfigChoice(self.engine, self.config, "controller", "type", self.changeType),
        ConfigChoice(   self.engine, self.config, "controller", "mic_device", autoApply = True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_left", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_right", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_up", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_down", True),
        KeyConfigChoice(self.engine, self.config, "controller", "key_cancel"),
        KeyConfigChoice(self.engine, self.config, "controller", "key_start"),
        ConfigChoice(   self.engine, self.config, "controller", "mic_tap_sensitivity", autoApply = True),
        ConfigChoice(   self.engine, self.config, "controller", "mic_passthrough_volume", autoApply = True),
        (_("Rename Controller"), self.renameController),
      ]
    self.menu = Menu.Menu(self.engine, controlKeys, onCancel = self.cancel)
    self.engine.view.pushLayer(self.menu)
  
  def changeType(self):
    self.engine.view.popLayer(self.menu)
    self.setupMenu()
  
  def renameController(self):
    newControl = ""
    while newControl.strip().lower() in self.badname or newControl.strip() == "":
      newControl = Dialogs.getText(self.engine, _("Please rename your controller"), self.control)
      if newControl.strip().lower() in self.badname and not newControl.strip() == self.control:
        Dialogs.showMessage(self.engine, _("That name is already taken."))
      elif newControl.strip() == "" or newControl.strip() == self.control:
        Dialogs.showMessage(self.engine, _("Canceled."))
        break
    else:
      Player.renameControl(self.control, newControl)
      self.control = newControl
      self.engine.view.popLayer(self.menu)
      self.setupMenu()
  
  def run(self, ticks):
    self.time += ticks/50.0
    
  def render(self, visibility, topMost):
    pass

def quickset(config):
  #akedrou - quickset (based on Fablaculp's Performance Autoset)
  perfSetNum = config.get("quickset","performance")
  gameSetNum = config.get("quickset","gameplay")
  
  if gameSetNum == 1:
    config.set("game", "sp_notes_while_active", 1)
    config.set("game", "bass_groove_enable", 1)
    config.set("game", "big_rock_endings", 1)
    config.set("game", "in_game_stars", 1)
    config.set("coffee", "song_display_mode", 4)
    config.set("game", "mark_solo_sections", 2)
    Log.debug("Quickset Gameplay - Theme-Based")
    
  elif gameSetNum == 2:
    config.set("game", "sp_notes_while_active", 2)
    config.set("game", "bass_groove_enable", 2)
    config.set("game", "big_rock_endings", 2)
    config.set("game", "mark_solo_sections", 3)
    Log.debug("Quickset Gameplay - MIDI-Based")
    
  elif gameSetNum == 3:
    config.set("game", "sp_notes_while_active", 3)
    config.set("game", "bass_groove_enable", 3)
    config.set("game", "big_rock_endings", 2)
    config.set("game", "in_game_stars", 2)
    config.set("game", "counting", True)
    config.set("game", "mark_solo_sections", 1)
    Log.debug("Quickset Gameplay - RB style")
    
  elif gameSetNum == 4:
    config.set("game", "sp_notes_while_active", 0)
    config.set("game", "bass_groove_enable", 0)
    config.set("game", "big_rock_endings", 0)
    config.set("game", "in_game_stars", 0)
    config.set("coffee", "song_display_mode", 1)
    config.set("game", "counting", False)
    config.set("game", "mark_solo_sections", 0)
    Log.debug("Quickset Gameplay - GH style")
    
  elif gameSetNum == 5: # This needs work.
    config.set("game", "sp_notes_while_active", 0)
    config.set("game", "bass_groove_enable", 0)
    config.set("game", "big_rock_endings", 0)
    config.set("game", "in_game_stars", 0)
    config.set("coffee", "song_display_mode", 1)
    config.set("game", "counting", True)
    config.set("game", "mark_solo_sections", 1)
    Log.debug("Quickset Gameplay - WT style")
    
  # elif gameSetNum == 6: #FoFiX mode - perhaps soon.
    
  else:
    Log.debug("Quickset Gameplay - Manual")
  
  if perfSetNum == 1:
    config.set("engine", "highpriority", False)
    config.set("performance", "game_priority", 2)
    config.set("performance", "starspin", False)
    config.set("game", "rb_midi_lyrics", 0)
    config.set("game", "rb_midi_sections", 0)
    config.set("game", "gsolo_acc_disp", 0)
    config.set("game", "incoming_neck_mode", 0)
    config.set("game", "midi_lyric_mode", 2)
    config.set("video", "fps", 60)
    config.set("video", "multisamples", 0)
    config.set("video", "use_shaders", False)
    config.set("coffee", "game_phrases", 0)
    config.set("game", "partial_stars", 0)
    config.set("game", "songlistrotation", False)
    config.set("game", "song_listing_mode", 0)
    config.set("game", "song_display_mode", 1)
    config.set("game", "stage_animate", 0)
    config.set("game", "lyric_mode", 0)
    config.set("game", "use_graphical_submenu", 0)
    config.set("audio", "enable_crowd_tracks", 0)
    config.set("performance", "in_game_stats", 0)
    config.set("performance", "static_strings", True)
    config.set("performance", "disable_libcount", True)
    config.set("performance", "killfx", 2)
    config.set("performance", "star_score_updates", 0)
    config.set("performance", "cache_song_metadata", False)
    Log.debug("Quickset Performance - Fastest")
    
  elif perfSetNum == 2:
    config.set("engine", "highpriority", False)
    config.set("performance", "game_priority", 2)
    config.set("performance", "starspin", False)
    config.set("game", "rb_midi_lyrics", 1)
    config.set("game", "rb_midi_sections", 1)
    config.set("game", "gsolo_acc_disp", 1)
    config.set("game", "incoming_neck_mode", 1)
    config.set("game", "midi_lyric_mode", 2)
    config.set("video", "fps", 60)
    config.set("video", "multisamples", 2)
    config.set("coffee", "game_phrases", 1)
    config.set("game", "partial_stars", 1)
    config.set("game", "songlistrotation", False)
    config.set("game", "song_listing_mode", 0)
    config.set("game", "stage_animate", 0)
    config.set("game", "lyric_mode", 2)
    config.set("game", "use_graphical_submenu", 0)
    config.set("audio", "enable_crowd_tracks", 1)
    config.set("performance", "in_game_stats", 0)
    config.set("performance", "static_strings", True)
    config.set("performance", "disable_libcount", True)
    config.set("performance", "killfx", 0)
    config.set("performance", "star_score_updates", 0)
    config.set("performance", "cache_song_metadata", True)
    Log.debug("Quickset Performance - Fast")
    
  elif perfSetNum == 3:
    config.set("engine", "highpriority", False)
    config.set("performance", "game_priority", 2)
    config.set("performance", "starspin", True)
    config.set("game", "rb_midi_lyrics", 2)
    config.set("game", "rb_midi_sections", 2)
    config.set("game", "gsolo_acc_disp", 1)
    config.set("game", "incoming_neck_mode", 2)
    config.set("game", "midi_lyric_mode", 2)
    config.set("video", "fps", 80)
    config.set("video", "multisamples", 4)
    config.set("coffee", "game_phrases", 2)
    config.set("game", "partial_stars", 1)
    config.set("game", "songlistrotation", True)
    config.set("game", "lyric_mode", 2)
    config.set("game", "use_graphical_submenu", 1)
    config.set("audio", "enable_crowd_tracks", 1)
    config.set("performance", "in_game_stats", 2)
    config.set("performance", "static_strings", True)
    config.set("performance", "disable_libcount", True)
    config.set("performance", "killfx", 0)
    config.set("performance", "star_score_updates", 1)
    config.set("performance", "cache_song_metadata", True)
    Log.debug("Quickset Performance - Quality")
    
  elif perfSetNum == 4:
    config.set("engine", "highpriority", False)
    config.set("performance", "game_priority", 2)
    config.set("performance", "starspin", True)
    config.set("game", "rb_midi_lyrics", 2)
    config.set("game", "rb_midi_sections", 2)
    config.set("game", "gsolo_acc_disp", 2)
    config.set("game", "incoming_neck_mode", 2)
    config.set("game", "midi_lyric_mode", 0)
    config.set("video", "fps", 80)
    config.set("video", "multisamples", 4)
    config.set("video", "use_shaders", True)
    config.set("coffee", "game_phrases", 2)
    config.set("game", "partial_stars", 1)
    config.set("game", "songlistrotation", True)
    config.set("game", "lyric_mode", 2)
    config.set("game", "use_graphical_submenu", 1)
    config.set("audio", "enable_crowd_tracks", 1)
    config.set("performance", "in_game_stats", 2)
    config.set("performance", "static_strings", False)
    config.set("performance", "disable_libcount", False)
    config.set("performance", "killfx", 0)
    config.set("performance", "star_score_updates", 1)
    config.set("performance", "cache_song_metadata", True)
    Log.debug("Quickset Performance - Highest Quality")
    
  else:
    Log.debug("Quickset Performance - Manual")