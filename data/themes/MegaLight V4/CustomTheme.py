from Theme import *

class CustomTheme(Theme):
  menuRB = True
  loadingPhrase = ["Made to run on almost ANY system!","MegaLight has always been the Standard theme for FoFiX.","FoFiX v4.0 brings the level of customizability to a whole new level never seen before in Frets On Fire.","What do you mean where's Jurgen?  You're crazy.","If you find yourself getting bored, feel free to stand up while you play instead of continuing to jam on your couch.","Rock On, not off.  Off isn't as much fun."]
  
  menuX = {'default': .3}
  menuY = {'default': .15}
  menuScale = {'default': .002}
  menuVSpace = {'default': 0}
  menuButtons = {'default': 1}
  menuBoxes = {'default': 1}
  
  buttonBackX = {'default': (.8,.84)}
  buttonBackY = {'default': (.15,.19)}
  buttonUpX = {'default': (.18,.22)}
  buttonUpY = {'default': (.2,.24)}
  buttonDownX = {'default': (.18,.22)}
  buttonDownY = {'default': (.7,.74)}
  
  #menuX['main'] = .12
  #menuY['main'] = .52
  menuX['main'] = .25
  menuY['main'] = .32
  menuScale['main'] = .5
  menuVSpace['main'] = .05
  menuButtons['main'] = 2
  menuBoxes['main'] = 2
  
  buttonBackX['main'] = (.9,.94)
  buttonBackY['main'] = (.05,.09)
  buttonUpX['main']   = (.02,.06)
  buttonUpY['main']   = (.65,.69)
  buttonDownX['main'] = (.02,.06)
  buttonDownY['main'] = (.85,.89)
  
  fail_text_yPos = .4
  
  displayAllGreyStars = False
  menuTipTextDisplay = True
  use_solo_submenu = True
  
  starFillupCenterX = 139
  starFillupCenterY = 151
  starFillupInRadius = 121
  starFillupOutRadius = 138
  starFillupColor = (1,.9490,.3686)
  