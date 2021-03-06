#!/usr/bin/python3
###########################################
#
#    Binding of Isaac: Rebirth Stage Editor
#		by Colin Noga
#		   Chronometrics / Tempus
#
 #
  #
  #		UI Elements
  #			Main Scene: Click to select, right click to paint. Auto resizes to match window zoom. Renders background.
  #			Entity: A QGraphicsItem to be added to the scene for drawing.
  #			Room List: Shows a list of rooms with mini-renders as icons. Needs add and remove buttons. Should drag and drop re-sort.
  #			Entity Palette: A palette from which to choose entities to draw.
  #			Properties: Possibly a contextual menu thing?
  #
 #
#
#   Afterbirth Todo:
#		Fix up Rebirth/Afterbirth detection
#
#	Low priority
#		Clear Corner Rooms Grid
#		Fix icon for win_setup.py
#		Bosscolours for the alternate boss entities
#


from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from collections import OrderedDict
from copy import deepcopy

import traceback, sys
import struct, os, subprocess, platform, webbrowser, urllib, re, shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom
import psutil


########################
#       XML Data       #
########################

def getEntityXML():
    tree = ET.parse('resources/EntitiesAfterbirthPlus.xml')
    root = tree.getroot()

    return root

def getStageXML():
    tree = ET.parse('resources/StagesAfterbirthPlus.xml')
    root = tree.getroot()

    return root

def findInstallPath():
    installPath = ''
    cantFindPath = False

    if QFile.exists(settings.value('InstallFolder')):
        installPath = settings.value('InstallFolder')

    else:
        # Windows path things
        if "Windows" in platform.system():
            basePath = QSettings('HKEY_CURRENT_USER\\Software\\Valve\\Steam', QSettings.NativeFormat).value('SteamPath')
            if not basePath:
                cantFindPath = True

            installPath = os.path.join(basePath, "steamapps", "common", "The Binding of Isaac Rebirth")
            if not QFile.exists(installPath):
                cantFindPath = True

                libconfig = os.path.join(basePath, "steamapps", "libraryfolders.vdf")
                if os.path.isfile(libconfig):
                    libLines = list(open(libconfig, 'r'))
                    matcher = re.compile(r'"\d+"\s*"(.*?)"')
                    installDirs = map(lambda res: os.path.normpath(res.group(1)),
                                        filter(lambda res: res,
                                            map(lambda line: matcher.search(line), libLines)))
                    for root in installDirs:
                        installPath = os.path.join(root, 'steamapps', 'common', 'The Binding of Isaac Rebirth')
                        if QFile.exists(installPath):
                            cantFindPath = False
                            break

        # Mac Path things
        elif "Darwin" in platform.system():
            installPath = os.path.expanduser("~/Library/Application Support/Steam/steamapps/common/The Binding of Isaac Rebirth/The Binding of Isaac Rebirth.app/Contents/Resources")
            if not QFile.exists(installPath):
                cantFindPath = True

        # Linux and others
        elif "Linux" in platform.system():
            installPath = os.path.expanduser("~/.local/share/Steam/steamapps/common/The Binding of Isaac Rebirth")
            if not QFile.exists(installPath):
                cantFindPath = True
        else:
            cantFindPath = True

        # Looks like nothing was selected
        if cantFindPath or installPath == '' or not os.path.isdir(installPath):
            print(f"Could not find The Binding of Isaac: Afterbirth+ install folder ({installPath})")
            return ''

        settings.setValue('InstallFolder', installPath)

    return installPath

def findModsPath(installPath=None):
    modsPath = ''
    cantFindPath = False

    if QFile.exists(settings.value('ModsFolder')):
        modsPath = settings.value('ModsFolder')

    else:
        installPath = installPath or findInstallPath()
        if len(installPath) > 0:
            modd = os.path.join(installPath, "savedatapath.txt")
            if os.path.isfile(modd):
                lines = list(open(modd, 'r'))
                modDirs = list(filter(lambda parts: parts[0] == 'Modding Data Path',
                                map(lambda line: line.split(': '), lines)))
                if len(modDirs) > 0:
                    modsPath = os.path.normpath(modDirs[0][1].strip())

    if modsPath == '' or not os.path.isdir(modsPath):
        cantFindPath = True

    if cantFindPath:
        cantFindPath = False
        # Windows path things
        if "Windows" in platform.system():
            modsPath = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "Binding of Isaac Afterbirth+ Mods")
            if not QFile.exists(modsPath):
                cantFindPath = True

        # Mac Path things
        elif "Darwin" in platform.system():
            modsPath = os.path.expanduser("~/Library/Application Support/Binding of Isaac Afterbirth+ Mods")
            if not QFile.exists(modsPath):
                cantFindPath = True

        # Linux and others
        else:
            modsPath = os.path.expanduser("~/.local/share/binding of isaac afterbirth+ mods/")
            if not QFile.exists(modsPath):
                cantFindPath = True

        # Fallback Resource Folder Locating
        if cantFindPath:
            modsPathOut = QFileDialog.getExistingDirectory(None, 'Please Locate The Binding of Isaac: Afterbirth+ Mods Folder')
            if not modsPathOut:
                QMessageBox.warning(None, "Error", "Couldn't locate Mods folder and no folder was selected.")
                return
            else:
                modsPath = modsPathOut
            if modsPath == "":
                QMessageBox.warning(None, "Error", "Couldn't locate Mods folder and no folder was selected.")
                return
            if not QDir(modsPath).exists:
                QMessageBox.warning(None, "Error", "Selected folder does not exist or is not a folder.")
                return

        # Looks like nothing was selected
        if modsPath == '' or not os.path.isdir(modsPath):
            QMessageBox.warning(None, "Error", f"Could not find The Binding of Isaac: Afterbirth+ Mods folder ({modsPath})")
            return ''

        settings.setValue('ModsFolder', modsPath)

    return modsPath

def linuxPathSensitivityTraining(path):

    path = path.replace("\\", "/")

    directory, file = os.path.split(os.path.normpath(path))

    if not os.path.isdir(directory):
        return None

    contents = os.listdir(directory)

    for item in contents:
        if item.lower() == file.lower():
            return os.path.normpath(os.path.join(directory, item))

    return os.path.normpath(path)

def loadFromModXML(modPath, name, entRoot, resourcePath, fixIconFormat=False):

    cleanUp = re.compile('[^\w\d]')
    outputDir = f"resources/Entities/ModTemp/{cleanUp.sub('', name)}"
    if not os.path.isdir(outputDir): os.mkdir(outputDir)

    anm2root = entRoot.get("anm2root")

    # Iterate through all the entities
    enList = entRoot.findall("entity")

    # Skip if the mod is empty
    if len(enList) == 0:
        return

    print(f'-----------------------\nLoading entities from "{name}"')

    def mapEn(en):
        # Fix some shit
        i = int(en.get("id"))
        if i == 1000: i = 999
        s = en.get("subtype") or '0'
        v = en.get("variant") or '0'

        if i >= 1000 or i in (0, 1, 3, 7, 8, 9):
            print('Skipping: Invalid entity type %d: %s' % (i, en.get("name")))
            return None

        # Grab the anm location
        anmPath = linuxPathSensitivityTraining(os.path.join(modPath, "resources", anm2root, en.get("anm2path"))) or ''
        print('LOADING: %s' % anmPath)
        if not os.path.isfile(anmPath):
            anmPath = linuxPathSensitivityTraining(os.path.join(resourcePath, anm2root, en.get('anm2path'))) or ''

            print('REDIRECT LOADING: %s' % anmPath)
            if not os.path.isfile(anmPath):
                print('Skipping: Invalid anm2!')
                return None

        anm2Dir, anm2File = os.path.split(anmPath)

        # Grab the first frame of the anm
        anmTree = ET.parse(anmPath)
        spritesheets = anmTree.findall(".Content/Spritesheets/Spritesheet")
        layers = anmTree.findall(".Content/Layers/Layer")
        default = anmTree.find("Animations").get("DefaultAnimation")

        anim = anmTree.find(f"./Animations/Animation[@Name='{default}']")
        framelayers = anim.findall(".//LayerAnimation[Frame]")

        imgs = []
        ignoreCount = 0
        for layer in framelayers:
            if layer.get('Visible') == 'false':
                ignoreCount += 1
                continue

            frame = layer.find('Frame')
            if frame.get('Visible') == 'false':
                ignoreCount += 1
                continue

            sheetPath = spritesheets[int(layers[int(layer.get("LayerId"))].get("SpritesheetId"))].get("Path")
            image = os.path.abspath(os.path.join(anm2Dir, sheetPath))
            imgPath = linuxPathSensitivityTraining(image)
            if not (imgPath and os.path.isfile(imgPath)):
                image = re.sub(r'.*resources', resourcePath, image)
                imgPath = linuxPathSensitivityTraining(image)

            if imgPath and os.path.isfile(imgPath):
                # Here's the anm specs
                xp = -int(frame.get("XPivot")) # applied before rotation
                yp = -int(frame.get("YPivot"))
                r = int(frame.get("Rotation"))
                x = int(frame.get("XPosition")) # applied after rotation
                y = int(frame.get("YPosition"))
                xc = int(frame.get("XCrop"))
                yc = int(frame.get("YCrop"))
                #xs = float(frame.get("XScale")) / 100
                #ys = float(frame.get("YScale")) / 100
                xs, ys = 1, 1 # this ended up being a bad idea since it's usually used for squash and stretch
                w = int(frame.get("Width"))
                h = int(frame.get("Height"))

                imgs.append([imgPath, x, y, xc, yc, w, h, xs, ys, r, xp, yp])

        filename = "resources/Entities/questionmark.png"
        if len(imgs) == 0:
            print(f'Entity Icon could not be generated due to {ignoreCount > 0 and "visibility" or "missing files"}')
        else:

            # Fetch each layer and establish the needed dimensions for the final image
            finalRect = QRect()
            for img in imgs:
                imgPath, x, y, xc, yc, w, h, xs, ys, r, xp, yp = img
                cropRect = QRect(xc, yc, w, h)

                mat = QTransform()
                mat.rotate(r)
                mat.scale(xs, ys)
                mat.translate(xp, yp)

                # Load the Image
                qimg = QImage(imgPath)
                sourceImage = qimg.copy(cropRect).transformed(mat)
                img.append(sourceImage)

                if fixIconFormat:
                    qimg.save(imgPath)

                cropRect.moveTopLeft(QPoint())
                cropRect = mat.mapRect(cropRect)
                cropRect.translate(QPoint(x, y))
                finalRect = finalRect.united(cropRect)
                img.append(cropRect)

            # Create the destination
            pixmapImg = QImage(finalRect.width(), finalRect.height(), QImage.Format_ARGB32)
            pixmapImg.fill(0)

            # Paint all the layers to it
            RenderPainter = QPainter(pixmapImg)
            for imgPath, x, y, xc, yc, w, h, xs, ys, r, xp, yp, sourceImage, boundingRect in imgs:
                # Transfer the crop area to the pixmap
                boundingRect.translate(-finalRect.topLeft())
                RenderPainter.drawImage(boundingRect, sourceImage)
            RenderPainter.end()

            # Save it to a Temp file - better than keeping it in memory for user retrieval purposes?
            resDir = os.path.join(outputDir, 'icons')
            if not os.path.isdir(resDir): os.mkdir(resDir)
            filename = os.path.join(resDir, f'{en.get("id")}.{v}.{s} - {en.get("name")}.png')
            pixmapImg.save(filename, "PNG")

        # Write the modded entity to the entityXML temporarily for runtime
        etmp = ET.Element("entity")
        etmp.set("Name", en.get("name"))
        etmp.set("ID", str(i))
        etmp.set("Subtype", s)
        etmp.set("Variant", v)
        etmp.set("Image", filename)

        def condSet(setName, name):
            val = en.get(name)
            if val is not None:
                etmp.set(setName, val)

        condSet("BaseHP", "baseHP")
        condSet("Boss", 'boss')
        condSet("Champion", 'champion')

        i = int(i)
        etmp.set("Group", "(Mod) %s" % name)
        etmp.set("Kind", "Mods")
        if i == 5: # pickups
            if v == 100: # collectible
                return None
            etmp.set("Kind", "Pickups")
        elif i in (2, 4, 6): # tears, live bombs, machines
            etmp.set("Kind", "Stage")
        elif en.get("boss") == '1':
            etmp.set("Kind", "Bosses")
        else:
            etmp.set("Kind", "Enemies")

        return etmp

    result = list(filter(lambda x: x != None, map(mapEn, enList)))

    outputRoot = ET.Element('data')
    outputRoot.extend(result)
    with open(os.path.join(outputDir, 'EntitiesMod.xml'), 'w') as out:
        xml = minidom.parseString(ET.tostring(outputRoot)).toprettyxml(indent="    ")
        s = str.replace(xml, outputDir + os.path.sep, '').replace(os.path.sep, '/')
        out.write(s)

    return result

def loadFromMod(modPath, brPath, name, entRoot, fixIconFormat=False):
    entFile = os.path.join(brPath, 'EntitiesMod.xml')
    if not os.path.isfile(entFile):
        return

    print(f'-----------------------\nLoading entities from "{name}"')

    root = None
    try:
        tree = ET.parse(entFile)
        root = tree.getroot()
    except Exception as e:
        print('Error loading BR xml:', e)
        return

    enList = root.findall('entity')
    if len(enList) == 0:
        return

    cleanUp = re.compile('[^\w\d]')
    def mapEn(en):
        imgPath = en.get('Image') and linuxPathSensitivityTraining(os.path.join(brPath, en.get('Image')))

        i = en.get('ID')
        v = en.get('Variant') or '0'
        s = en.get('Subtype') or '0'

        entXML = None

        if en.get('Metadata') != '1':
            adjustedId = i == '999' and '1000' or i
            query = f"entity[@id='{adjustedId}'][@variant='{v}']"

            validMissingSubtype = False

            entXML = entRoot.find(query + f"[@subtype='{s}']")
            if entXML is None:
                entXML = entRoot.find(query)
                validMissingSubtype = entXML is not None

            if entXML == None:
                print('Loading invalid entity (no entry in entities2 xml): ' + str(en.attrib))
                en.set('Invalid', '1')
            else:
                foundName = entXML.get('name')
                givenName = en.get('Name')
                foundNameClean, givenNameClean = list(map(lambda s: cleanUp.sub('', s).lower(), (foundName, givenName)))
                if not (foundNameClean == givenNameClean or ( validMissingSubtype and (foundNameClean in givenNameClean or givenNameClean in foundNameClean) )):
                    print('Loading entity, found name mismatch! In entities2: ', foundName, '; In BR: ', givenName)

        # Write the modded entity to the entityXML temporarily for runtime
        if not en.get('Group'):
            en.set('Group', '(Mod) %s' % name)
        en.set("Image", imgPath)

        if fixIconFormat:
            formatFix = QImage(imgPath)
            formatFix.save(imgPath)

        en.set("Subtype", s)
        en.set("Variant", v)

        en.set('BaseHP',   entXML and entXML.get('baseHP') or en.get('BaseHP'))
        en.set('Boss',     entXML and entXML.get('boss') or en.get('Boss'))
        en.set('Champion', entXML and entXML.get('champion') or en.get('Champion'))

        return en

    return list(map(mapEn, enList))

def loadStagesFromMod(modPath, brPath, name):
    stageFile = os.path.join(brPath, 'StagesMod.xml')
    if not os.path.isfile(stageFile):
        return

    print(f'-----------------------\nLoading stages from "{name}"')

    root = None
    try:
        tree = ET.parse(stageFile)
        root = tree.getroot()
    except Exception as e:
        print('Error loading BR xml:', e)
        return

    stageList = root.findall('stage')
    if len(stageList) == 0: return

    def mapStage(stage):
        if stage.get('Stage') is None or stage.get('StageType') is None or stage.get('Name') is None:
            print('Tried to load stage, but had missing stage, stage type, or name!', str(stage.attrib))
            return None

        prefix = stage.get('BGPrefix')
        if prefix is not None:
            prefixPath = linuxPathSensitivityTraining(os.path.join(brPath, prefix))
            stage.set('BGPrefix', prefixPath)

        return stage

    return list(filter(lambda x: x != None, map(mapStage, stageList)))

def loadMods(autogenerate, installPath, resourcePath):
    global entityXML
    global stageXML

    # Each mod in the mod folder is a Group
    modsPath = findModsPath(installPath)
    if not os.path.isdir(modsPath):
        print('Could not find Mods Folder! Skipping mod content!')
        return

    modsInstalled = os.listdir(modsPath)

    fixIconFormat = settings.value('FixIconFormat') == '1'

    autogenPath = 'resources/Entities/ModTemp'
    if autogenerate and not os.path.exists(autogenPath):
        os.mkdir(autogenPath)

    print('LOADING MOD CONTENT')
    for mod in modsInstalled:
        modPath = os.path.join(modsPath, mod)
        brPath = os.path.join(modPath, 'basementrenovator')

        # Make sure we're a mod
        if not os.path.isdir(modPath) or os.path.isfile(os.path.join(modPath, 'disable.it')):
            continue

        # simple workaround for now
        if not (autogenerate or os.path.exists(brPath)):
            continue

        # Get the mod name
        modName = mod
        try:
            tree = ET.parse(os.path.join(modPath, 'metadata.xml'))
            root = tree.getroot()
            modName = root.find("name").text
        except ET.ParseError:
            print(f'Failed to parse mod metadata "{modName}", falling back on default name')

        # add dedicated entities
        entPath = os.path.join(modPath, 'content/entities2.xml')
        if os.path.exists(entPath):
            # Grab their Entities2.xml
            entRoot = None
            try:
                entRoot = ET.parse(entPath).getroot()
            except ET.ParseError as e:
                print(f'ERROR parsing entities2 xml for mod "{modName}": {e}')
                continue

            ents = None
            if autogenerate:
                ents = loadFromModXML(modPath, modName, entRoot, resourcePath, fixIconFormat=fixIconFormat)
            else:
                ents = loadFromMod(modPath, brPath, modName, entRoot, fixIconFormat=fixIconFormat)

            if ents:
                for ent in ents:
                    name, i, v, s = ent.get('Name'), int(ent.get('ID')), int(ent.get('Variant')), int(ent.get('Subtype'))

                    if i >= 1000:
                        print(f'Entity "{name}" has a type outside the 0 - 999 range! ({i}) It will not load properly from rooms!')
                    if v >= 4096:
                        print(f'Entity "{name}" has a variant outside the 0 - 4095 range! ({v})')
                    if s >= 256:
                        print(f'Entity "{name}" has a subtype outside the 0 - 255 range! ({s})')

                    existingEn = entityXML.find(f"entity[@ID='{i}'][@Subtype='{s}'][@Variant='{v}']")
                    if existingEn != None:
                        print(f'Entity "{name}" in "{ent.get("Kind")}" > "{ent.get("Group")}" ({i}.{v}.{s}) is overriding "{existingEn.get("Name")}" from "{existingEn.get("Kind")}" > "{existingEn.get("Group")}"!')
                        entityXML.remove(existingEn)
                        ent.set('Invalid', existingEn.get('Invalid'))

                    entityXML.append(ent)

            stages = loadStagesFromMod(modPath, brPath, modName)
            if stages:
                stageXML.extend(stages)

########################
#      Scene/View      #
########################

class RoomScene(QGraphicsScene):

    def __init__(self):
        QGraphicsScene.__init__(self, 0, 0, 0, 0)
        self.newRoomSize(1)

        # Make the bitfont
        q = QImage()
        q.load('resources/UI/Bitfont.png')

        self.bitfont = [ QPixmap.fromImage(q.copy(i * 12, j * 12, 12, 12)) for j in range(int(q.height() / 12)) for i in range(int(q.width() / 12)) ]
        self.bitText = True

        self.tile = None

    def newRoomSize(self, shape):
        self.roomInfo = Room.Info(shape=shape)
        if not self.roomInfo.shapeData: return

        self.roomWidth, self.roomHeight = self.roomInfo.dims

        self.setSceneRect(-1 * 26, -1 * 26, (self.roomWidth + 2) * 26, (self.roomHeight + 2) * 26)

    def clearDoors(self):
        for item in self.items():
            if isinstance(item, Door):
                item.remove()

    def drawForeground(self, painter, rect):

        # Bitfont drawing: moved to the RoomEditorWidget.drawForeground for easier anti-aliasing

        # Grey out the screen to show it's inactive if there are no rooms selected
        if mainWindow.roomList.selectedRoom() == None:
            b = QBrush(QColor(255, 255, 255, 100))
            painter.setPen(Qt.white)
            painter.setBrush(b)

            painter.fillRect(rect, b)
            return

        if settings.value('GridEnabled') == '0': return

        gs = 26

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        white = QColor.fromRgb(255, 255, 255, 100)
        bad = QColor.fromRgb(100, 255, 255, 100)

        showOutOfBounds = settings.value('BoundsGridEnabled') == '1'
        showGridIndex = settings.value('ShowGridIndex') == '1'
        showCoordinates = settings.value('ShowCoordinates') == '1'
        for y in range(self.roomHeight):
            for x in range(self.roomWidth):
                if self.roomInfo.isInBounds(x,y):
                    painter.setPen(QPen(white, 1, Qt.DashLine))
                else:
                    if not showOutOfBounds: continue
                    painter.setPen(QPen(bad, 1, Qt.DashLine))

                painter.drawLine(x * gs, y * gs, (x + 1) * gs, y * gs)
                painter.drawLine(x * gs, (y + 1) * gs, (x + 1) * gs, (y + 1) * gs)
                painter.drawLine(x * gs, y * gs, x * gs, (y + 1) * gs)
                painter.drawLine((x + 1) * gs, y * gs, (x + 1) * gs, (y + 1) * gs)

                if showGridIndex:
                    painter.drawText(x * gs + 2, y * gs + 13, f"{Room.Info.gridIndex(x, y, self.roomWidth)}" )
                if showCoordinates:
                    painter.drawText(x * gs + 2, y * gs + 24, f"{x - 1},{y - 1}" )

        # Draw Walls (Debug)
        # painter.setPen(QPen(Qt.green, 5, Qt.SolidLine))
        # h = gs / 2
        # walls = self.roomInfo.shapeData['Walls']
        # for wmin, wmax, wlvl, wdir in walls['X']:
        #     painter.drawLine(wmin * gs + h, wlvl * gs + h, wmax * gs + h, wlvl * gs + h)
        # for wmin, wmax, wlvl, wdir in walls['Y']:
        #     painter.drawLine(wlvl * gs + h, wmin * gs + h, wlvl * gs + h, wmax * gs + h)


    def loadBackground(self):
        gs = 26

        roomBG = None
        if mainWindow.roomList.selectedRoom():
            roomBG = mainWindow.roomList.selectedRoom().roomBG
        else:
            roomBG = stageXML.find('stage[@Name="Basement"]')

        self.tile = QImage()
        self.tile.load(roomBG.get('OuterBG'))

        # grab the images from the appropriate parts of the spritesheet
        self.corner = self.tile.copy(QRect(0,      0,      gs * 7, gs * 4))
        self.vert   = self.tile.copy(QRect(gs * 7, 0,      gs * 2, gs * 6))
        self.horiz  = self.tile.copy(QRect(0,      gs * 4, gs * 9, gs * 2))

        self.innerCorner = QImage()
        self.innerCorner.load(roomBG.get('InnerBG'))

    def drawBackground(self, painter, rect):

        self.loadBackground()

        if not self.roomInfo.shapeData:
            print (f"This room has an unknown shape: {self.roomInfo.shape}")
            self.drawBGRegularRooms(painter, rect)

        ########## SHAPE DEFINITIONS
        # w x h
        # 1 = 1x1, 2 = 1x0.5, 3 = 0.5x1, 4 = 2x1, 5 = 2x0.5, 6 = 1x2, 7 = 0.5x2, 8 = 2x2
        # 9 = DR corner, 10 = DL corner, 11 = UR corner, 12 = UL corner

        # Regular Rooms
        if self.roomInfo.shape in [1, 4, 6, 8]:
            self.drawBGRegularRooms(painter, rect)

        # Slim Rooms
        elif self.roomInfo.shape in [2, 3, 5, 7]:
            self.drawBGSlimRooms(painter, rect)

        # L Rooms
        elif self.roomInfo.shape in [9, 10, 11, 12]:
            self.drawBGCornerRooms(painter, rect)

    def drawBGRegularRooms(self, painter, rect):
        gs = 26

        width = self.roomWidth - 2
        height = self.roomHeight - 2

        t = -1 * gs
        xm = gs * (width - 4)
        ym = gs * (height - 1)

        # Corner Painting
        painter.drawPixmap(t,  t,  QPixmap().fromImage(self.corner.mirrored(False, False)))
        painter.drawPixmap(xm, t,  QPixmap().fromImage(self.corner.mirrored(True, False)))
        painter.drawPixmap(t,  ym, QPixmap().fromImage(self.corner.mirrored(False, True)))
        painter.drawPixmap(xm, ym, QPixmap().fromImage(self.corner.mirrored(True, True)))

        # Mirrored Textures
        uRect = QImage(gs * 4, gs * 6, QImage.Format_RGB32)
        lRect = QImage(gs * 9, gs * 4, QImage.Format_RGB32)

        uRect.fill(1)
        lRect.fill(1)

        # setup the image tiles
        vp = QPainter()
        vp.begin(uRect)
        vp.drawPixmap(0,  0, QPixmap().fromImage(self.vert))
        vp.drawPixmap(gs * 2, 0, QPixmap().fromImage(self.vert.mirrored(True, False)))
        vp.end()

        vh = QPainter()
        vh.begin(lRect)
        vh.drawPixmap(0, 0,  QPixmap().fromImage(self.horiz))
        vh.drawPixmap(0, gs * 2, QPixmap().fromImage(self.horiz.mirrored(False, True)))
        vh.end()

        # paint the tiles onto the scene
        painter.drawTiledPixmap(
            gs * 5,
            -1 * gs,
            gs * (width - 9),
            gs * 6,
            QPixmap().fromImage(uRect)
        )
        painter.drawTiledPixmap(
            -1 * gs,
            gs * 2,
            gs * 9,
            gs * (height - 3),
            QPixmap().fromImage(lRect)
        )
        painter.drawTiledPixmap(
            gs * 5,
            gs * (height - 3),
            26 * (width - 9),
            26 * 6,
            QPixmap().fromImage(uRect.mirrored(False, True))
        )
        painter.drawTiledPixmap(
            gs * (width - 6),
            gs * 2,
            gs * 9,
            gs * (height - 3),
            QPixmap().fromImage(lRect.mirrored(True, False))
        )

        if height == 14 and width == 26:

            self.center = self.tile.copy(QRect(gs * 3, gs * 3, gs * 6, gs * 3))

            painter.drawPixmap	(gs * 8,  gs * 5, QPixmap().fromImage(self.center.mirrored(False, False)))
            painter.drawPixmap	(gs * 14, gs * 5, QPixmap().fromImage(self.center.mirrored(True, False)))
            painter.drawPixmap	(gs * 8,  gs * 8, QPixmap().fromImage(self.center.mirrored(False, True)))
            painter.drawPixmap	(gs * 14, gs * 8, QPixmap().fromImage(self.center.mirrored(True, True)))

    def drawBGSlimRooms(self, painter, rect):
        gs = 26

        width = self.roomWidth - 2
        height = self.roomHeight - 2

        t = -1 * gs
        yo = 0
        xo = 0

        # Thin in Height
        if self.roomInfo.shape in [2, 7]:
            height = 3
            yo = (2 * gs)

        # Thin in Width
        if self.roomInfo.shape in [3, 5]:
            width = 5
            xo = (4 * gs)

        xm = gs * (width - 4)
        ym = gs * (height - 1)

        # Corner Painting
        painter.drawPixmap(t + xo,  t + yo,  QPixmap().fromImage(self.corner.mirrored(False, False)))
        painter.drawPixmap(xm + xo, t + yo,  QPixmap().fromImage(self.corner.mirrored(True, False)))
        painter.drawPixmap(t + xo,  ym + yo, QPixmap().fromImage(self.corner.mirrored(False, True)))
        painter.drawPixmap(xm + xo, ym + yo, QPixmap().fromImage(self.corner.mirrored(True, True)))

        # Mirrored Textures
        uRect = QImage(gs * 4, gs * 4, QImage.Format_RGB32)
        lRect = QImage(gs * 7, gs * 4, QImage.Format_RGB32)

        uRect.fill(1)
        lRect.fill(1)

        vp = QPainter()
        vp.begin(uRect)
        vp.drawPixmap(0,  0, QPixmap().fromImage(self.vert))
        vp.drawPixmap(gs * 2, 0, QPixmap().fromImage(self.vert.mirrored(True, False)))
        vp.end()

        vh = QPainter()
        vh.begin(lRect)
        vh.drawPixmap(0, 0,  QPixmap().fromImage(self.horiz))
        vh.drawPixmap(0, gs * 2, QPixmap().fromImage(self.horiz.mirrored(False, True)))
        vh.end()

        painter.drawTiledPixmap(
            xo + gs * 5,
            yo - 1 * gs,
            gs * (width - 9),
            gs * 4,
            QPixmap().fromImage(uRect)
        )
        painter.drawTiledPixmap(
            xo - 1 * gs,
            yo + gs * 2,
            gs * 7,
            gs * (height - 3),
            QPixmap().fromImage(lRect)
        )
        painter.drawTiledPixmap(
            xo + gs * 5,
            yo + gs * (height - 1),
            gs * (width - 9),
            gs * 4,
            QPixmap().fromImage(uRect.mirrored(False, True))
        )
        painter.drawTiledPixmap(
            xo + gs * (width - 4),
            yo + gs * 3,
            gs * 7,
            gs * (height - 3),
            QPixmap().fromImage(lRect.mirrored(True, False))
        )

        if height == 14 and width == 26:

            self.center = self.tile.copy(QRect(gs * 3, gs * 3, gs * 6, gs * 3))

            painter.drawPixmap(xo + gs * 8,  yo + gs * 5, QPixmap().fromImage(self.center.mirrored(False, False)))
            painter.drawPixmap(xo + gs * 14, yo + gs * 5, QPixmap().fromImage(self.center.mirrored(True, False)))
            painter.drawPixmap(xo + gs * 8,  yo + gs * 8, QPixmap().fromImage(self.center.mirrored(False, True)))
            painter.drawPixmap(xo + gs * 14, yo + gs * 8, QPixmap().fromImage(self.center.mirrored(True, True)))

    def drawBGCornerRooms(self, painter, rect):
        gs = 26

        width = self.roomWidth - 2
        height = self.roomHeight - 2

        t = -1 * gs
        xm = gs * (width - 4)
        ym = gs * (height - 1)

        # Mirrored Textures
        uRect = QImage(gs * 4, gs * 6, QImage.Format_RGB32)
        lRect = QImage(gs * 9, gs * 4, QImage.Format_RGB32)

        uRect.fill(1)
        lRect.fill(1)

        vp = QPainter()
        vp.begin(uRect)
        vp.drawPixmap(0,      0, QPixmap().fromImage(self.vert))
        vp.drawPixmap(gs * 2, 0, QPixmap().fromImage(self.vert.mirrored(True, False)))
        vp.end()

        vh = QPainter()
        vh.begin(lRect)
        vh.drawPixmap(0, 0,      QPixmap().fromImage(self.horiz))
        vh.drawPixmap(0, gs * 2, QPixmap().fromImage(self.horiz.mirrored(False, True)))
        vh.end()

        # Exterior Corner Painting
        painter.drawPixmap(t,  t,  QPixmap().fromImage(self.corner.mirrored(False, False)))
        painter.drawPixmap(xm, t,  QPixmap().fromImage(self.corner.mirrored(True, False)))
        painter.drawPixmap(t,  ym, QPixmap().fromImage(self.corner.mirrored(False, True)))
        painter.drawPixmap(xm, ym, QPixmap().fromImage(self.corner.mirrored(True, True)))

        # Exterior Wall Painting
        painter.drawTiledPixmap(gs * 5, gs * -1, gs * (width - 9), gs * 6, QPixmap().fromImage(uRect))
        painter.drawTiledPixmap(-gs * 1, gs * 2, gs * 9, gs * (height - 3), QPixmap().fromImage(lRect))
        painter.drawTiledPixmap(gs * 5, gs * (height - 3), gs * (width - 9), gs * 6, QPixmap().fromImage(uRect.mirrored(False, True)))
        painter.drawTiledPixmap(gs * (width - 6), gs * 2, gs * 9, gs * (height - 3), QPixmap().fromImage(lRect.mirrored(True, False)))

        # Center Floor Painting
        self.center = self.tile.copy(QRect(gs * 3, gs * 3, gs * 6, gs * 3))

        painter.drawPixmap(gs * 8,  gs * 5, QPixmap().fromImage(self.center.mirrored(False, False)))
        painter.drawPixmap(gs * 14, gs * 5, QPixmap().fromImage(self.center.mirrored(True, False)))
        painter.drawPixmap(gs * 8,  gs * 8, QPixmap().fromImage(self.center.mirrored(False, True)))
        painter.drawPixmap(gs * 14, gs * 8, QPixmap().fromImage(self.center.mirrored(True, True)))

        # Interior Corner Painting (This is the annoying bit)
        # New midpoints
        xm = gs * (width / 2)
        ym = gs * (height / 2)

        # New half-lengths/heights
        xl = xm + gs * 2
        yl = ym + gs * 2


        if self.roomInfo.shape == 9:
            # Clear the dead area
            painter.fillRect(t, t, xl, yl, QColor(0, 0, 0, 255))

            # Draw the horizontal wall
            painter.drawTiledPixmap(xm - gs * 7, ym + t, gs * 6, gs * 6, QPixmap().fromImage(uRect))

            # Draw the vertical wall
            painter.drawTiledPixmap(xm + t, ym - gs * 4, gs * 9, gs * 3, QPixmap().fromImage(lRect))

            # Draw the three remaining corners
            painter.drawPixmap(t,      ym + t, QPixmap().fromImage(self.corner.mirrored(False, False)))
            painter.drawPixmap(xm + t, t,      QPixmap().fromImage(self.corner.mirrored(False, False)))
            painter.drawPixmap(xm + t, ym + t, QPixmap().fromImage(self.innerCorner.mirrored(False, False)))

        elif self.roomInfo.shape == 10:
            # Clear the dead area
            painter.fillRect(xm - t, t, xl, yl, QColor(0, 0, 0, 255))

            # Draw the horizontal wall
            painter.drawTiledPixmap(xm + gs * 3, ym + t, gs * 6, gs * 6, QPixmap().fromImage(uRect))

            # Draw the vertical wall
            painter.drawTiledPixmap(xm - gs * 6, ym - gs * 4, gs * 9, gs * 3, QPixmap().fromImage(lRect.mirrored(True, False)))

            # Draw the three remaining corners
            painter.drawPixmap(gs * (width - 4), ym + t, QPixmap().fromImage(self.corner.mirrored(True, False)))
            painter.drawPixmap(xm - gs * 4, t, QPixmap().fromImage(self.corner.mirrored(True, False)))
            painter.drawPixmap(xm + gs, ym + t, QPixmap().fromImage(self.innerCorner.mirrored(True, False)))

        elif self.roomInfo.shape == 11:
            # Clear the dead area
            painter.fillRect(t, ym - t, xl, yl, QColor(0, 0, 0, 255))

            # Draw the horizontal wall
            painter.drawTiledPixmap(xm - gs * 7, ym + t * 3, gs * 6, gs * 6, QPixmap().fromImage(uRect.mirrored(False, True)))

            # Draw the vertical wall
            painter.drawTiledPixmap(xm + t, ym - t * 2, gs * 9, gs * 4, QPixmap().fromImage(lRect))

            # Draw the three remaining corners
            painter.drawPixmap(t,      ym + t,     QPixmap().fromImage(self.corner.mirrored(False, True)))
            painter.drawPixmap(xm + t, ym * 2 + t, QPixmap().fromImage(self.corner.mirrored(False, True)))
            painter.drawPixmap(xm + t, ym - t,     QPixmap().fromImage(self.innerCorner.mirrored(False, True)))

        elif self.roomInfo.shape == 12:
            # Clear the dead area
            painter.fillRect(xm - t, ym - t, xl, yl, QColor(0, 0, 0, 255))

            # Draw the horizontal wall
            painter.drawTiledPixmap(xm + gs * 3, ym + t * 3, gs * 6, gs * 6, QPixmap().fromImage(uRect.mirrored(False, True)))

            # Draw the vertical wall
            painter.drawTiledPixmap(xm - gs * 6, ym - t * 2, gs * 9, gs * 4, QPixmap().fromImage(lRect.mirrored(True, False)))

            # Draw the three remaining corners
            painter.drawPixmap(xm + gs * 9, ym + t,      QPixmap().fromImage(self.corner.mirrored(True, True)))
            painter.drawPixmap(xm - gs * 4, ym + gs * 6, QPixmap().fromImage(self.corner.mirrored(True, True)))
            painter.drawPixmap(xm + gs,     ym - t,      QPixmap().fromImage(self.innerCorner.mirrored(True, True)))

class RoomEditorWidget(QGraphicsView):

    def __init__(self, scene, parent=None):
        QGraphicsView.__init__(self, scene, parent)

        self.setViewportUpdateMode(self.FullViewportUpdate)
        self.setDragMode(self.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.assignNewScene(scene)

        self.canDelete = True

    def assignNewScene(self, scene):
        self.setScene(scene)
        self.centerOn(0, 0)

        self.objectToPaint = None
        self.lastTile = None

    def tryToPaint(self, event):
        '''Called when a paint attempt is initiated'''

        paint = self.objectToPaint
        if paint == None: return

        clicked = self.mapToScene(event.x(), event.y())
        x, y = clicked.x(), clicked.y()

        x = int(x / 26)
        y = int(y / 26)

        xmax, ymax = self.scene().roomWidth, self.scene().roomHeight

        x = min(max(x, 0), xmax - 1)
        y = min(max(y, 0), ymax - 1)

        if settings.value('SnapToBounds') == '1':
            x, y = self.scene().roomInfo.snapToBounds(x, y)

        for i in self.scene().items():
            if isinstance(i, Entity):
                if i.entity.x == x and i.entity.y == y:
                    if i.stackDepth == EntityStack.MAX_STACK_DEPTH:
                        return

                    i.hideWeightPopup()

                    # Don't stack multiple grid entities
                    if int(i.entity.Type) > 999 and int(self.objectToPaint.ID) > 999:
                        return

        # Make sure we're not spawning oodles
        if (x, y) in self.lastTile: return
        self.lastTile.add((x, y))

        en = Entity(x, y, int(paint.ID), int(paint.variant), int(paint.subtype), 1.0)

        self.scene().addItem(en)
        mainWindow.dirt()

    def mousePressEvent(self, event):
        if event.buttons() == Qt.RightButton:
            if mainWindow.roomList.selectedRoom() is not None:
                self.lastTile = set()
                self.tryToPaint(event)
                event.accept()
        else:
            self.lastTile = None
        # not calling this for right click + adding items to the scene causes crashes
        QGraphicsView.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        if self.lastTile:
            if mainWindow.roomList.selectedRoom() is not None:
                self.tryToPaint(event)
                event.accept()
        QGraphicsView.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        self.lastTile = None
        QGraphicsView.mouseReleaseEvent(self, event)

    def keyPressEvent(self, event):
        if self.canDelete and (event.key() == Qt.Key_Delete):
            scene = self.scene()
            selection = scene.selectedItems()

            if len(selection) > 0:
                for obj in selection:
                    obj.setSelected(False)
                    obj.remove()
                scene.update()
                self.update()
                mainWindow.dirt()

        QGraphicsView.keyPressEvent(self, event)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor(0, 0, 0))

        QGraphicsView.drawBackground(self, painter, rect)

    def resizeEvent(self, event):
        QGraphicsView.resizeEvent(self, event)

        w = self.scene().roomWidth
        h = self.scene().roomHeight

        xScale = event.size().width()  / (26 * (w + 2))
        yScale = event.size().height() / (26 * (h + 2))
        newScale = min([xScale, yScale])

        tr = QTransform()
        tr.scale(newScale, newScale)

        self.setTransform(tr)

        if newScale == yScale:
            self.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        else:
            self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

    def paintEvent(self, event):
        # Purely handles the status overlay text
        QGraphicsView.paintEvent(self, event)

        if settings.value('StatusEnabled') == '0': return

        # Display the room status in a text overlay
        painter = QPainter()
        painter.begin(self.viewport())

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setPen(QPen(Qt.white, 1, Qt.SolidLine))

        room = mainWindow.roomList.selectedRoom()
        if room:
            # Room Type Icon
            q = QPixmap()
            q.load('resources/UI/RoomIcons.png')

            painter.drawPixmap(2, 3, q.copy(room.info.type * 16, 0, 16, 16))

            # Top Text
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(20, 16, f"{room.info.variant} - {room.data(0x100)}" )

            # Bottom Text
            font = painter.font()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(8, 30, f"Difficulty: {room.difficulty}, Weight: {room.weight}, Subtype: {room.info.subtype}")

        # Display the currently selected entity in a text overlay
        selectedEntities = self.scene().selectedItems()

        if len(selectedEntities) == 1:
            e = selectedEntities[0]
            r = event.rect()

            # Entity Icon
            i = QIcon()
            painter.drawPixmap(QRect(r.right() - 32, 2, 32, 32), e.entity.pixmap)

            # Top Text
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(r.right() - 34 - 400, 2, 400, 16, Qt.AlignRight | Qt.AlignBottom,
                                f'{e.entity.Type}.{e.entity.Variant}.{e.entity.Subtype} - {e.entity.name}')

            # Bottom Text
            font = painter.font()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(r.right() - 34 - 400, 20, 400, 12, Qt.AlignRight | Qt.AlignBottom, f"Boss: {e.entity.boss}, Champion: {e.entity.champion}")
            painter.drawText(r.right() - 34 - 200, 36, 200, 12, Qt.AlignRight | Qt.AlignBottom, f"Base HP : {e.entity.baseHP}")

        elif len(selectedEntities) > 1:
            e = selectedEntities[0]
            r = event.rect()

            # Case Two: more than one type of entity
            # Entity Icon
            i = QIcon()
            painter.drawPixmap(QRect(r.right() - 32, 2, 32, 32), e.entity.pixmap)

            # Top Text
            font = painter.font()
            font.setPixelSize(13)
            painter.setFont(font)
            painter.drawText(r.right() - 34 - 200, 2, 200, 16, Qt.AlignRight | Qt.AlignBottom, f"{len(selectedEntities)} Entities Selected" )

            # Bottom Text
            font = painter.font()
            font.setPixelSize(10)
            painter.setFont(font)
            painter.drawText(r.right() - 34 - 200, 20, 200, 12, Qt.AlignRight | Qt.AlignBottom, ", ".join(set([x.entity.name or 'INVALID' for x in selectedEntities])) )

            pass

        painter.end()

    def drawForeground(self, painter, rect):
        QGraphicsView.drawForeground(self, painter, rect)

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Display the number of entities on a given tile, in bitFont or regular font
        tiles = [ [ 0 for x in range(self.scene().roomWidth) ] for y in range(self.scene().roomHeight) ]
        for e in self.scene().items():
            if isinstance(e, Entity):
                tiles[e.entity.y][e.entity.x] += 1

        useAliased = settings.value('BitfontEnabled') == '0'

        if useAliased:
            painter.setPen(Qt.white)
            painter.font().setPixelSize(5)

        for y, row in enumerate(tiles):
            yc = (y + 1) * 26 - 12

            for x, count in enumerate(row):
                if count <= 1: continue

                if not useAliased:
                    xc = (x + 1) * 26 - 12

                    digits = [ int(i) for i in str(count) ]

                    fontrow = count == EntityStack.MAX_STACK_DEPTH and 1 or 0

                    numDigits = len(digits) - 1
                    for i, digit in enumerate(digits):
                        painter.drawPixmap( xc - 12 * (numDigits - i), yc, self.scene().bitfont[digit + fontrow * 10] )
                else:
                    if count == EntityStack.MAX_STACK_DEPTH: painter.setPen(Qt.red)

                    painter.drawText( x * 26, y * 26, 26, 26, Qt.AlignBottom | Qt.AlignRight, str(count) )

                    if count == EntityStack.MAX_STACK_DEPTH: painter.setPen(Qt.white)

class Entity(QGraphicsItem):
    GRID_SIZE = 26

    class Info:
        def __init__(self, x=0, y=0, t=0, v=0, s=0, weight=0, changeAtStart=True):
            # Supplied entity info
            self.x = x
            self.y = y
            self.weight = weight

            if changeAtStart:
                self.changeTo(t, v, s)

        def changeTo(self, t, v, s):
            self.Type = t
            self.Variant = v
            self.Subtype = s

            # Derived Entity Info
            self.name = None
            self.isGridEnt = False
            self.baseHP = None
            self.boss = None
            self.champion = None
            self.pixmap = None
            self.known = False
            self.invalid = False
            self.placeVisual = None

            self.mirrorX = None
            self.mirrorY = None

            self.getEntityInfo(t, v, s)

        def getEntityInfo(self, t, variant, subtype):

            en = None
            try:
                global entityXML
                en = entityXML.find(f"entity[@ID='{t}'][@Subtype='{subtype}'][@Variant='{variant}']")
            except:
                print (f"Entity {t}, Variant {variant}, Subtype {subtype} expected, but was not found")
                en = None

            if en == None:
                self.pixmap = QPixmap("resources/Entities/questionmark.png")
                return

            self.name = en.get('Name')
            self.isGridEnt = en.get('Kind') == 'Stage' and \
                            en.get('Group') in [ 'Grid', 'Poop', 'Fireplaces', 'Other', 'Props', 'Special Exits', 'Broken' ]

            self.baseHP = en.get('BaseHP')
            self.boss = en.get('Boss') == '1'
            self.champion = en.get('Champion') == '1'
            self.placeVisual = en.get('PlaceVisual')

            def getEnt(s):
                return list(map(int, s.split('.')))

            mirrorX, mirrorY = en.get('MirrorX'), en.get('MirrorY')
            if mirrorX: self.mirrorX = getEnt(mirrorX)
            if mirrorY: self.mirrorY = getEnt(mirrorY)

            if t == 5 and variant == 100:
                i = QImage()
                i.load('resources/Entities/5.100.0 - Collectible.png')
                i = i.convertToFormat(QImage.Format_ARGB32)

                d = QImage()
                d.load(en.get('Image'))

                p = QPainter(i)
                p.drawImage(0, 0, d)
                p.end()

                self.pixmap = QPixmap.fromImage(i)

            else:
                self.pixmap = QPixmap(en.get('Image'))

            def checkNum(s):
                try:
                    float(s)
                    return True
                except ValueError:
                    return False

            if self.placeVisual:
                parts = list(map(lambda x: x.strip(), self.placeVisual.split(',')))
                if len(parts) == 2 and checkNum(parts[0]) and checkNum(parts[1]):
                    self.placeVisual = (float(parts[0]), float(parts[1]))
                else:
                    self.placeVisual = parts[0]

            self.invalid = en.get('Invalid') == '1'
            self.known = True


    def __init__(self, x, y, mytype, variant, subtype, weight):
        QGraphicsItem.__init__(self)
        self.setFlags(
            self.ItemSendsGeometryChanges |
            self.ItemIsSelectable |
            self.ItemIsMovable
        )

        self.stackDepth = 1
        self.popup = None
        mainWindow.scene.selectionChanged.connect(self.hideWeightPopup)

        self.entity = Entity.Info(x, y, mytype, variant, subtype, weight)
        self.updateTooltip()

        self.updatePosition()
        if self.entity.Type < 999:
            self.setZValue(1)
        else:
            self.setZValue(0)

        if not hasattr(Entity, 'SELECTION_PEN'):
            Entity.SELECTION_PEN = QPen(Qt.green, 1, Qt.DashLine)
            Entity.OFFSET_SELECTION_PEN = QPen(Qt.red, 1, Qt.DashLine)
            Entity.INVALID_ERROR_IMG = QPixmap('resources/UI/ent-error.png')
            Entity.OUT_OF_RANGE_WARNING_IMG = QPixmap('resources/UI/ent-warning.png')

        self.setAcceptHoverEvents(True)

    def setData(self, t, v, s):
        self.entity.changeTo(t, v, s)
        self.updateTooltip()

    def updateTooltip(self):
        e = self.entity
        tooltipStr = f"{e.name} @ {e.x-1} x {e.y-1} - {e.Type}.{e.Variant}.{e.Subtype}; HP: {e.baseHP}"

        if e.Type >= 1000 and not e.isGridEnt:
            tooltipStr += '\nType is outside the valid range of 0 - 999! This will not load properly in-game!'
        if e.Variant >= 4096:
            tooltipStr += '\nVariant is outside the valid range of 0 - 4095!'
        if e.Subtype >= 255:
            tooltipStr += '\nSubtype is outside the valid range of 0 - 255!'
        if e.invalid:
            tooltipStr += '\nMissing entities2.xml entry! Trying to spawn this WILL CRASH THE GAME!!'
        if not e.known:
            tooltipStr += '\nMissing BR entry! Trying to spawn this entity might CRASH THE GAME!!'

        self.setToolTip(tooltipStr)

    def itemChange(self, change, value):

        if change == self.ItemPositionChange:

            currentX, currentY = self.x(), self.y()

            xc, yc = value.x(), value.y()

            # TODO fix this hack, this is only needed because we don't have a scene on init
            w, h = 28, 16
            if self.scene():
                w = self.scene().roomWidth
                h = self.scene().roomHeight

            # should be round, but python is dumb and
            # arbitrarily decides when it wants to be
            # a normal programming language
            x = int(xc / Entity.GRID_SIZE + 0.5)
            y = int(yc / Entity.GRID_SIZE + 0.5)

            x = min(max(x, 0), w - 1)
            y = min(max(y, 0), h - 1)

            # TODO above hack is here too
            if settings.value('SnapToBounds') == '1' and self.scene():
                x, y = self.scene().roomInfo.snapToBounds(x, y)

            xc = x * Entity.GRID_SIZE
            yc = y * Entity.GRID_SIZE

            if xc != currentX or yc != currentY:
                self.entity.x = x
                self.entity.y = y

                self.updateTooltip()
                if self.isSelected():
                    mainWindow.dirt()

            value.setX(xc)
            value.setY(yc)

            self.getStack()
            if self.popup: self.popup.update(self.stack)

            return value

        return QGraphicsItem.itemChange(self, change, value)

    def boundingRect(self):
        #if self.entity.pixmap:
        #	return QRectF(self.entity.pixmap.rect())
        #else:
        return QRectF(0.0, 0.0, 26.0, 26.0)

    def updatePosition(self):
        self.setPos(self.entity.x * 26, self.entity.y * 26)

    def paint(self, painter, option, widget):

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        painter.setBrush(Qt.Dense5Pattern)
        painter.setPen(QPen(Qt.white))

        if self.entity.pixmap:
            w, h = self.entity.pixmap.width(), self.entity.pixmap.height()
            xc, yc = 0, 0

            typ, var, sub = self.entity.Type, self.entity.Variant, self.entity.Subtype

            def WallSnap():
                ex = self.entity.x
                ey = self.entity.y

                shape = self.scene().roomInfo.shapeData

                walls = shape['Walls']
                distancesY = [ ((ex < w[0] or ex > w[1]) and 100000 or abs(ey - w[2]), w) for w in walls['X'] ]
                distancesX = [ ((ey < w[0] or ey > w[1]) and 100000 or abs(ex - w[2]), w) for w in walls['Y'] ]

                closestY = min(distancesY, key=lambda w: w[0])
                closestX = min(distancesX, key=lambda w: w[0])

                # TODO match up with game when distances are equal
                wx, wy = 0, 0
                if closestY[0] < closestX[0]:
                    w = closestY[1]
                    wy = w[2] - ey
                else:
                    w = closestX[1]
                    wx = (w[2] - ex) * 2

                return wx, wy

            customPlaceVisuals = {
                'WallSnap': WallSnap
            }

            recenter = self.entity.placeVisual
            if recenter:
                if isinstance(recenter, str):
                    recenter = customPlaceVisuals.get(recenter, None)
                    if recenter:
                        xc, yc = recenter()
                else:
                    xc, yc = recenter

            xc += 1
            yc += 1
            x = (xc * 26 - w) / 2
            y = (yc * 26 - h)

            def drawGridBorders():
                painter.drawLine(0, 0, 0, 4)
                painter.drawLine(0, 0, 4, 0)

                painter.drawLine(26, 0, 26, 4)
                painter.drawLine(26, 0, 22, 0)

                painter.drawLine(0, 26, 4, 26)
                painter.drawLine(0, 26, 0, 22)

                painter.drawLine(26, 26, 22, 26)
                painter.drawLine(26, 26, 26, 22)

            # Curse room special case
            if typ == 5 and var == 50 and mainWindow.roomList.selectedRoom().info.type == 10:
                self.entity.pixmap = QPixmap('resources/Entities/5.360.0 - Red Chest.png')

            # Crawlspace special case
            if (typ == 0 or typ == 1900) and mainWindow.roomList.selectedRoom().info.type == 16:
                if typ == 1900 and var == 0:
                    self.entity.pixmap = QPixmap('resources/Entities/1900.0.0 - Crawlspace Brick.png')
                    self.setZValue(-1 * self.entity.y)
                    recenter = (0, 0)
                elif typ == 0:
                    if var == 10:
                        self.entity.pixmap = QPixmap('resources/Entities/0.10.0 - Ladder.png')
                    elif var == 20:
                        self.entity.pixmap = QPixmap('resources/Entities/0.20.0 - Ladder Base.png')
                    elif var == 30:
                        self.entity.pixmap = QPixmap('resources/Entities/0.30.0 - Ladder Through.png')

            painter.drawPixmap(x, y, self.entity.pixmap)

            # if the offset is high enough, draw an indicator of the actual position
            if abs(1 - yc) > 0.5 or abs(1 - xc) > 0.5:
                painter.setPen(self.OFFSET_SELECTION_PEN)
                painter.setBrush(Qt.NoBrush)
                painter.drawLine(13, 13, x + w / 2, y + h - 13)
                drawGridBorders()
                painter.fillRect(x + w / 2 - 3, y + h - 13 - 3, 6, 6, Qt.red)

            if self.isSelected():
                painter.setPen(self.SELECTION_PEN)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(x, y, w, h)

                # Grid space boundary
                painter.setPen(Qt.green)
                drawGridBorders()

        if not self.entity.known:
            painter.setFont(QFont("Arial", 6))

            painter.drawText(2, 26, "%d.%d.%d" % (typ, var, sub))

        warningIcon = None
        # applies to entities that do not have a corresponding entities2 entry
        if self.entity.invalid or not self.entity.known:
            warningIcon = Entity.INVALID_ERROR_IMG
        # entities have 12 bits for type and variant, 8 for subtype
        # common mod error is to make them outside that range
        elif var >= 4096 or sub >= 256 or (typ >= 1000 and not self.entity.isGridEnt):
            warningIcon = Entity.OUT_OF_RANGE_WARNING_IMG

        if warningIcon:
            painter.drawPixmap(18, -8, warningIcon)

    def remove(self):
        if self.popup:
            self.popup.remove()
            self.scene().views()[0].canDelete = True
        self.scene().removeItem(self)

    def mouseReleaseEvent(self, event):
        self.hideWeightPopup()
        QGraphicsItem.mouseReleaseEvent(self, event)

    def hoverEnterEvent(self, event):
        self.createWeightPopup()

    def hoverLeaveEvent(self, event):
        self.hideWeightPopup()

    def getStack(self):
        # Get the stack
        stack = self.collidingItems(Qt.IntersectsItemBoundingRect)
        stack.append(self)

        # Make sure there are no doors or popups involved
        self.stack = [x for x in stack if isinstance(x,Entity)]

        # 1 is not a stack.
        self.stackDepth = len(self.stack)

    def createWeightPopup(self):
        self.getStack()
        if self.stackDepth <= 1 or any(x.popup and x != self and x.popup.isVisible() for x in self.stack):
            self.hideWeightPopup()
            return

        # If there's no popup, make a popup
        if self.popup:
            if self.popup.activeSpinners != self.stackDepth:
                self.popup.update(self.stack)
            self.popup.setVisible(True)
            return

        self.scene().views()[0].canDelete = False
        self.popup = EntityStack(self.stack)
        self.scene().addItem(self.popup)

    def hideWeightPopup(self):
        if self.popup and self not in mainWindow.scene.selectedItems():
            self.popup.setVisible(False)
            if self.scene(): self.scene().views()[0].canDelete = True

class EntityStack(QGraphicsItem):
    MAX_STACK_DEPTH = 25

    class WeightSpinner(QDoubleSpinBox):
        def __init__(self):
            QDoubleSpinBox.__init__(self)

            self.setRange(0.0, 100.0)
            self.setDecimals(2)
            self.setSingleStep(0.1)
            self.setFrame(False)
            self.setAlignment(Qt.AlignHCenter)

            self.setFont(QFont("Arial", 10))

            palette = self.palette()
            palette.setColor(QPalette.Base, Qt.transparent)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Window, Qt.transparent)

            self.setPalette(palette)
            self.setButtonSymbols(QAbstractSpinBox.NoButtons)

    class Proxy(QGraphicsProxyWidget):
        def __init__(self, button, parent):
            QGraphicsProxyWidget.__init__(self, parent)

            self.setWidget(button)

    def __init__(self, items):
        QGraphicsItem.__init__(self)
        self.setZValue(1000)

        self.spinners = []
        self.activeSpinners = 0
        self.update(items)

    def update(self, items):
        activeSpinners = len(items)

        for i in range(activeSpinners - len(self.spinners)):
            weight = self.WeightSpinner()
            weight.valueChanged.connect(lambda: self.weightChanged(i))
            self.spinners.append(self.Proxy(weight, self))

        for i in range(activeSpinners, len(self.spinners)):
            self.spinners[i].setVisible(False)

        if activeSpinners > 1:
            for i, item in enumerate(items):
                spinner = self.spinners[i]
                spinner.widget().setValue(item.entity.weight)
                spinner.setVisible(True)
        else:
            self.setVisible(False)

        # it's very important that this happens AFTER setting up the spinners
        # it greatly increases the odds of races with weightChanged if items are updated first
        self.items = items
        self.activeSpinners = activeSpinners

    def weightChanged(self, idx):
        if idx < self.activeSpinners:
            self.items[idx].entity.weight = self.spinners[idx].widget().value()

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        brush = QBrush(QColor(0,0,0,80))
        painter.setPen(QPen(Qt.transparent))
        painter.setBrush(brush)

        r = self.boundingRect().adjusted(0,0,0,-16)

        path = QPainterPath()
        path.addRoundedRect(r, 4, 4)
        path.moveTo(r.center().x()-6, r.bottom())
        path.lineTo(r.center().x()+6, r.bottom())
        path.lineTo(r.center().x(), r.bottom()+12)
        painter.drawPath(path)

        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Arial", 8))

        w = 0
        for i, item in enumerate(self.items):
            pix = item.entity.pixmap
            self.spinners[i].setPos(w-8, r.bottom()-26)
            w += 4
            painter.drawPixmap(w, r.bottom()-20-pix.height(), pix)

            # painter.drawText(w, r.bottom()-16, pix.width(), 8, Qt.AlignCenter, "{:.1f}".format(item.entity.weight))
            w += pix.width()

    def boundingRect(self):
        width = 0
        height = 0

        # Calculate the combined size
        for item in self.items:
            dx, dy = 26, 26
            pix = item.entity.pixmap
            if pix:
                dx, dy = pix.rect().width(), pix.rect().height()
            width = width + dx
            height = max(height, dy)

        # Add in buffers
        height = height + 8 + 8 + 8 + 16 # Top, bottom, weight text, and arrow
        width = width + 4 + len(self.items)*4 # Left and right and the middle bits

        self.setX(self.items[-1].x() - width/2 + 13)
        self.setY(self.items[-1].y() - height)

        return QRectF(0.0, 0.0, width, height)

    def remove(self):
        # Fix for the nullptr left by the scene parent of the widget, avoids a segfault from the dangling pointer
        for spin in self.spinners:
            # spin.widget().setParent(None)
            spin.setWidget(None)	# Turns out this function calls the above commented out function
            self.scene().removeItem(spin)
        #del self.spinners # causes crashes

        self.scene().removeItem(self)

class Door(QGraphicsItem):

    def __init__(self, doorItem):
        QGraphicsItem.__init__(self)

        # Supplied entity info
        self.doorItem = doorItem

        self.setPos(self.doorItem[0] * 26 - 13, self.doorItem[1] * 26 - 13)

        tr = QTransform()
        if doorItem[0] in [0, 13]:
            tr.rotate(270)
            self.moveBy(-13, 0)
        elif doorItem[0] in [14, 27]:
            tr.rotate(90)
            self.moveBy(13, 0)
        elif doorItem[1] in [8, 15]:
            tr.rotate(180)
            self.moveBy(0, 13)
        else:
            self.moveBy(0, -13)

        self.image = QImage('resources/Backgrounds/Door.png').transformed(tr)
        self.disabledImage = QImage('resources/Backgrounds/DisabledDoor.png').transformed(tr)

    @property
    def exists(self): return self.doorItem[2]

    @exists.setter
    def exists(self, val): self.doorItem[2] = val

    def paint(self, painter, option, widget):

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self.exists:
            painter.drawImage(0, 0, self.image)
        else:
            painter.drawImage(0, 0, self.disabledImage)

    def boundingRect(self):
        return QRectF(0.0, 0.0, 64.0, 52.0)

    def mouseDoubleClickEvent(self, event):

        self.exists = not self.exists

        event.accept()
        self.update()
        mainWindow.dirt()

    def remove(self):
        self.scene().removeItem(self)



########################
#     Dock Widgets     #
########################

# Room Selector
########################

class Room(QListWidgetItem):

    # contains concrete room information necessary for examining a room's game qualities
    # such as type, variant, subtype, and shape information
    class Info:
        ########## SHAPE DEFINITIONS
        # w x h
        # 1 = 1x1, 2 = 1x0.5, 3 = 0.5x1, 4 = 1x2, 5 = 0.5x2, 6 = 2x1, 7 = 2x0.5, 8 = 2x2
        # 9 = DR corner, 10 = DL corner, 11 = UR corner, 12 = UL corner
        # all coords must be offset -1, -1 when saving
        Shapes = {
            1: { # 1x1
                'Doors': [[7, 0], [0, 4], [14, 4], [7, 8]],
                # format: min, max on axis, cross axis coord, normal direction along cross axis
                'Walls': {
                    'X': [ (0, 14, 0, 1), (0, 14, 8, -1) ],
                    'Y': [ (0, 8, 0, 1), (0, 8, 14, -1) ]
                },
                'Dims': (15, 9)
            },
            2: { # horizontal closet (1x0.5)
                'Doors': [[0, 4], [14, 4]],
                'Walls': {
                    'X': [ (0, 14, 2, 1), (0, 14, 6, -1) ],
                    'Y': [ (2, 6, 0, 1), (2, 6, 14, -1) ]
                },
                'TopLeft': 30, # Grid coord
                'BaseShape': 1, # Base Room shape this is rendered over
                'Dims': (15, 5)
            },
            3: { # vertical closet (0.5x1)
                'Doors': [[7, 0], [7, 8]],
                'Walls': {
                    'X': [ (4, 10, 0, 1), (4, 10, 8, -1) ],
                    'Y': [ (0, 8, 4, 1), (0, 8, 10, -1) ]
                },
                'TopLeft': 4,
                'BaseShape': 1,
                'Dims': (7, 9)
            },
            4: { # 1x2 room
                'Doors': [[7, 0], [14, 4], [0, 4], [14, 11], [0, 11], [7, 15]],
                'Walls': {
                    'X': [ (0, 14, 0, 1), (0, 14, 15, -1) ],
                    'Y': [ (0, 15, 0, 1), (0, 15, 14, -1) ]
                },
                'Dims': (15, 16)
            },
            5: { # tall closet (0.5x2)
                'Doors': [[7, 0], [7, 15]],
                'Walls': {
                    'X': [ (4, 10, 0, 1), (4, 10, 15, -1) ],
                    'Y': [ (0, 15, 4, 1), (0, 15, 10, -1) ]
                },
                'TopLeft': 4,
                'BaseShape': 4,
                'Dims': (7, 16)
            },
            6: { # 2x1 room
                'Doors': [[7, 0], [0, 4], [7, 8], [20, 8], [27, 4], [20, 0]],
                'Walls': {
                    'X': [ (0, 27, 0, 1), (0, 27, 8, -1) ],
                    'Y': [ (0, 8, 0, 1), (0, 8, 27, -1) ]
                },
                'Dims': (28, 9)
            },
            7: { # wide closet (2x0.5)
                'Doors': [[0, 4], [27, 4]],
                'Walls': {
                    'X': [ (0, 27, 2, 1), (0, 27, 6, -1) ],
                    'Y': [ (2, 6, 0, 1), (2, 6, 27, -1) ]
                },
                'TopLeft': 56,
                'BaseShape': 6,
                'Dims': (28, 5)
            },
            8: { # 2x2 room
                'Doors': [[7, 0], [0, 4], [0, 11], [20, 0], [7, 15], [20, 15], [27, 4], [27, 11]],
                'Walls': {
                    'X': [ (0, 27, 0, 1), (0, 27, 15, -1) ],
                    'Y': [ (0, 15, 0, 1), (0, 15, 27, -1) ]
                },
                'Dims': (28, 16)
            },
            9: { # mirrored L room
                'Doors': [[20, 0], [27, 4], [7, 15], [20, 15], [13, 4], [0, 11], [27, 11], [7, 7]],
                'Walls': {
                    'X': [ (0, 13, 7, 1), (13, 27, 0, 1), (0, 27, 15, -1) ],
                    'Y': [ (7, 15, 0, 1), (0, 7, 13, 1), (0, 15, 27, -1) ]
                },
                'BaseShape': 8,
                'MirrorX': 10,
                'MirrorY': 11,
                'Dims': (28, 16)
            },
            10: { # L room
                'Doors': [[0, 4], [14, 4], [7, 0], [20, 7], [7, 15], [20, 15], [0, 11], [27, 11]],
                'Walls': {
                    'X': [ (0, 14, 0, 1), (14, 27, 7, 1), (0, 27, 15, -1) ],
                    'Y': [ (0, 15, 0, 1), (0, 7, 14, -1), (7, 15, 27, -1) ]
                },
                'BaseShape': 8,
                'MirrorX': 9,
                'MirrorY': 12,
                'Dims': (28, 16)
            },
            11: { # mirrored r room
                'Doors': [[0, 4], [7, 8], [7, 0], [13, 11], [20, 0], [27, 4], [20, 15], [27, 11]],
                'Walls': {
                    'X': [ (0, 27, 0, 1), (0, 13, 8, -1), (13, 27, 15, -1) ],
                    'Y': [ (0, 8, 0, 1), (8, 15, 13, 1), (0, 15, 27, -1) ]
                },
                'BaseShape': 8,
                'MirrorX': 12,
                'MirrorY': 9,
                'Dims': (28, 16)
            },
            12: { # r room
                'Doors': [[0, 4], [7, 0], [20, 0], [14, 11], [27, 4], [7, 15], [0, 11], [20, 8]],
                'Walls': {
                    'X': [ (0, 27, 0, 1), (14, 27, 8, -1), (0, 14, 15, -1) ],
                    'Y': [ (0, 15, 0, 1), (8, 15, 14, -1), (0, 8, 27, -1) ]
                },
                'BaseShape': 8,
                'MirrorX': 11,
                'MirrorY': 10,
                'Dims': (28, 16)
            }
        }

        for shape in Shapes.values():
            for door in shape['Doors']:
                door.append(True)

        def __init__(self, t=0, v=0, s=0, shape=1):
            self.type = t
            self.variant = v
            self.subtype = s
            self.shape = shape

        @property
        def shape(self):
            return self._shape

        @shape.setter
        def shape(self, val):
            self._shape = val
            self.shapeData = Room.Info.Shapes[self.shape]
            bs = self.shapeData.get('BaseShape')
            self.baseShapeData = bs and Room.Info.Shapes[bs]
            self.makeNewDoors()

        # represents the actual dimensions of the room, including out of bounds
        @property
        def dims(self): return (self.baseShapeData or self.shapeData)['Dims']

        @property
        def width(self): return self.shapeData['Dims'][0]

        @property
        def height(self): return self.shapeData['Dims'][1]

        def makeNewDoors(self):
            self.doors = [ door[:] for door in self.shapeData['Doors'] ]

        def gridLen(self):
            dims = self.dims
            return dims[0] * dims[1]

        def gridIndex(x,y,w):
            return y * w + x

        def _axisBounds(a, c, w):
            wmin, wmax, wlvl, wdir = w
            return a < wmin or a > wmax or ((c > wlvl) - (c < wlvl)) == wdir

        def isInBounds(self, x,y):
            return all(Room.Info._axisBounds(x,y,w) for w in self.shapeData['Walls']['X']) and \
                   all(Room.Info._axisBounds(y,x,w) for w in self.shapeData['Walls']['Y'])

        def snapToBounds(self, x,y,dist=1):
            for w in self.shapeData['Walls']['X']:
                if not Room.Info._axisBounds(x,y,w):
                    y = w[2] + w[3] * dist

            for w in self.shapeData['Walls']['Y']:
                if not Room.Info._axisBounds(y,x,w):
                    x = w[2] + w[3] * dist

            return (x, y)


    def __init__(self, name="New Room", spawns=[], difficulty=1, weight=1.0, mytype=1, variant=0, subtype=0, shape=1, doors=None):
        """Initializes the room item."""

        QListWidgetItem.__init__(self)

        self.setData(0x100, name)

        self.info = Room.Info(mytype, variant, subtype, shape)
        if doors:
            if len(self.info.doors) != len(doors):
                print(f'{name} ({variant}): Invalid doors!', doors)
            self.info.doors = doors

        self.gridSpawns = spawns or [ [] for x in range(self.info.gridLen()) ]
        if self.info.gridLen() != len(self.gridSpawns):
            print(f'{name} ({variant}): Invalid grid spawns!')

        self.difficulty = difficulty
        self.weight = weight

        self.setRoomBG()

        self.setFlags(self.flags() | Qt.ItemIsEditable)
        self.setToolTip()

        self.renderDisplayIcon()

    @property
    def difficulty(self): return self._difficulty

    @difficulty.setter
    def difficulty(self, d):
        self._difficulty = d
        self.setForeground(QColor.fromHsvF(1, 1, min(max(d / 15, 0), 1), 1))

    @property
    def gridSpawns(self): return self._gridSpawns

    @gridSpawns.setter
    def gridSpawns(self, g):
        self._gridSpawns = g

        self._spawnCount = 0
        for entStack in self.gridSpawns:
            if entStack: self._spawnCount += 1

    DoorSortKey = lambda door: (door[0], door[1])

    def clearDoors(self):
        mainWindow.scene.clearDoors()
        for door in self.info.doors:
            mainWindow.scene.addItem(Door(door))

    def getSpawnCount(self):
        return self._spawnCount

    def reshape(self, shape, doors=None):
        spawnIter = self.spawns()

        self.info.shape = shape
        if doors: self.info.doors = doors
        realWidth = self.info.dims[0]

        gridLen = self.info.gridLen()
        newGridSpawns = [ [] for x in range(gridLen) ]

        for stack, x, y in spawnIter:
            idx = Room.Info.gridIndex(x, y, realWidth)
            if idx < gridLen:
                newGridSpawns[idx] = stack

        self.gridSpawns = newGridSpawns

    def getDesc(info, name, difficulty, weight):
        return f'{name} ({info.type}.{info.variant}.{info.subtype}) ({info.width-2}x{info.height-2}) - Difficulty: {difficulty}, Weight: {weight}, Shape: {info.shape}'

    def setToolTip(self):
        self.setText(f"{self.info.variant} - {self.data(0x100)}")
        tip = Room.getDesc(self.info, self.data(0x100), self.difficulty, self.weight)
        QListWidgetItem.setToolTip(self, tip)

    def renderDisplayIcon(self):
        """Renders the mini-icon for display."""

        q = QImage()
        q.load('resources/UI/RoomIcons.png')

        i = QIcon(QPixmap.fromImage(q.copy(self.info.type * 16, 0, 16, 16)))

        self.setIcon(i)

    class _SpawnIter:
        def __init__(self, gridSpawns, dims):
            self.idx = -1
            self.spawns = gridSpawns
            self.width, self.height = dims

        def __iter__(self): return self

        def __next__(self):
            stack = None
            while True:
                self.idx += 1
                if self.idx >= self.width * self.height or self.idx >= len(self.spawns):
                    raise StopIteration

                stack = self.spawns[self.idx]
                if stack: break
            x = int(self.idx % self.width)
            y = int(self.idx / self.width)
            return (stack, x, y)

    def spawns(self):
        return Room._SpawnIter(self.gridSpawns, self.info.dims)

    SpecialBG = [
        "0a_library", "0b_shop", "0c_isaacsroom", "0d_barrenroom",
        "0e_arcade", "0e_diceroom", "0f_secretroom"
    ]

    for i in range(len(SpecialBG)):
        prefix = SpecialBG[i]
        SpecialBG[i] = ET.Element('room', {
            "OuterBG": os.path.join("resources/Backgrounds", prefix + ".png"),
            "InnerBG": os.path.join("resources/Backgrounds", prefix + "Inner.png")
        })

    def setRoomBG(self):
        global stageXML

        roomsByStage = stageXML.findall('stage')

        getBG = lambda name: stageXML.find(f'stage[@Name="{name}"]')

        self.roomBG = getBG('Basement')

        for room in roomsByStage:
            if room.get('Pattern') in mainWindow.path:
                self.roomBG = room

        c = self.info.type
        v = self.info.variant

        if c == 12: # library
            self.roomBG = Room.SpecialBG[0]
        elif c == 2: # shop
            self.roomBG = Room.SpecialBG[1]
        elif c == 18: # bedroom
            self.roomBG = Room.SpecialBG[2]
        elif c == 19: # barren room
            self.roomBG = Room.SpecialBG[3]
        elif c == 9: # arcade
            self.roomBG = Room.SpecialBG[4]
        elif c == 21: # dice room
            self.roomBG = Room.SpecialBG[5]
        elif c == 7: # secret room
            self.roomBG = Room.SpecialBG[6]

        # curse, challenge, sacrifice, devil, boss rush, black market
        elif c in [10, 11, 13, 14, 17, 22]:
            self.roomBG = getBG('Sheol')
        # angel
        elif c in [15]:
            self.roomBG = getBG('Cathedral')
        # chest room
        elif c in [20]:
            self.roomBG = getBG('Chest')
        # error, crawlspace
        elif c in [3, 16]:
            self.roomBG = getBG('Dark Room')

        # super secret
        elif c in [8]:
            if v in [0, 11, 15]:
                self.roomBG = getBG('Womb')
            elif v in [1, 12, 16]:
                self.roomBG = getBG('Cathedral')
            elif v in [2, 13, 17]:
                self.roomBG = getBG('Sheol')
            elif v in [3]:
                self.roomBG = getBG('Necropolis')
            elif v in [4]:
                self.roomBG = getBG('Cellar')
            elif v in [5, 19]:
                self.roomBG = getBG('Basement')
            elif v in [6]:
                self.roomBG = Room.SpecialBG[0]
            elif v in [7]:
                self.roomBG = getBG('Dark Room')
            elif v in [8]:
                self.roomBG = getBG('Burning Basement')
            elif v in [9]:
                self.roomBG = getBG('Flooded Caves')
            elif v in [14, 18]:
                self.roomBG = Room.SpecialBG[1]
            else:
                self.roomBG = getBG('Dark Room')
        # grave rooms
        elif c == 1 and v > 2 and 'special rooms' in mainWindow.path:
            self.roomBG = getBG('Dark Room')

    def mirrorX(self):
        # Flip Spawns
        width, height = self.info.dims
        for y in range(height):
            for x in range(int(width / 2)):
                ox = Room.Info.gridIndex(x,y,width)
                mx = Room.Info.gridIndex(width-x-1,y,width)
                oxs = self.gridSpawns[ox]
                self.gridSpawns[ox] = self.gridSpawns[mx]
                self.gridSpawns[mx] = oxs

        # Flip Doors
        for door in self.info.doors:
            door[0] = width - door[0] - 1

        # Flip Directional Entities
        info = Entity.Info(changeAtStart=False)
        for stack, x, y in self.spawns():
            for spawn in stack:
                info.changeTo(spawn[0], spawn[1], spawn[2])
                if info.mirrorX:
                    for i in range(3):
                        spawn[i] = info.mirrorX[i]

        # Flip Shape
        shape = self.info.shapeData.get('MirrorX')
        if shape:
            self.reshape(shape, self.info.doors)

    def mirrorY(self):
        # Flip Spawns
        width, height = self.info.dims
        for x in range(width):
            for y in range(int(height / 2)):
                oy = Room.Info.gridIndex(x,y,width)
                my = Room.Info.gridIndex(x,height-y-1,width)
                oys = self.gridSpawns[oy]
                self.gridSpawns[oy] = self.gridSpawns[my]
                self.gridSpawns[my] = oys


        # Flip Doors
        for door in self.info.doors:
            door[1] = height - door[1] - 1

        # Flip Directional Entities
        info = Entity.Info(changeAtStart=False)
        for stack, x, y in self.spawns():
            for spawn in stack:
                info.changeTo(spawn[0], spawn[1], spawn[2])
                if info.mirrorY:
                    for i in range(3):
                        spawn[i] = info.mirrorY[i]

        # Flip Shape
        shape = self.info.shapeData.get('MirrorY')
        if shape:
            self.reshape(shape, self.info.doors)

class RoomDelegate(QStyledItemDelegate):

    def __init__(self):

        self.pixmap = QPixmap('resources/UI/CurrentRoom.png')
        QStyledItemDelegate.__init__(self)

    def paint(self, painter, option, index):

        painter.fillRect(option.rect.right() - 19, option.rect.top(), 17, 16, QBrush(Qt.white))

        QStyledItemDelegate.paint(self, painter, option, index)

        item = mainWindow.roomList.list.item(index.row())
        if item and item.data(100):
            painter.drawPixmap(option.rect.right() - 19, option.rect.top(), self.pixmap)

class FilterMenu(QMenu):

    def __init__(self):

        QMenu.__init__(self)

    def paintEvent(self, event):

        QMenu.paintEvent(self, event)

        painter = QPainter(self)

        for act in self.actions():
            rect = self.actionGeometry(act)
            painter.fillRect(rect.right() / 2 - 12, rect.top() - 2, 24, 24, QBrush(Qt.transparent))
            painter.drawPixmap(rect.right() / 2 - 12, rect.top() - 2, act.icon().pixmap(24, 24))

class RoomSelector(QWidget):

    def __init__(self):
        """Initialises the widget."""

        QWidget.__init__(self)

        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)

        self.filterEntity = None

        self.setupFilters()
        self.setupList()
        self.setupToolbar()

        self.layout.addLayout(self.filter)
        self.layout.addWidget(self.list)
        self.layout.addWidget(self.toolbar)

        self.setLayout(self.layout)
        self.setButtonStates()

    def setupFilters(self):
        self.filter = QGridLayout()
        self.filter.setSpacing(4)

        fq = QImage()
        fq.load('resources/UI/FilterIcons.png')

        # Set the custom data
        self.filter.typeData = -1
        self.filter.weightData = -1
        self.filter.sizeData = -1

        # ID Filter
        self.IDFilter = QLineEdit()
        self.IDFilter.setPlaceholderText("ID / Name")
        self.IDFilter.textChanged.connect(self.changeFilter)

        # Entity Toggle Button
        self.entityToggle = QToolButton()
        self.entityToggle.setCheckable(True)
        self.entityToggle.checked = False
        self.entityToggle.setIconSize(QSize(24, 24))
        self.entityToggle.toggled.connect(self.setEntityToggle)
        self.entityToggle.toggled.connect(self.changeFilter)
        self.entityToggle.setIcon(QIcon(QPixmap.fromImage(fq.copy(0, 0, 24, 24))))

        # Type Toggle Button
        self.typeToggle = QToolButton()
        self.typeToggle.setIconSize(QSize(24, 24))
        self.typeToggle.setPopupMode(QToolButton.InstantPopup)

        typeMenu = QMenu()

        q = QImage()
        q.load('resources/UI/RoomIcons.png')

        self.typeToggle.setIcon(QIcon(QPixmap.fromImage(fq.copy(1 * 24 + 4, 4, 16, 16))))
        act = typeMenu.addAction(QIcon(QPixmap.fromImage(fq.copy(1 * 24 + 4, 4, 16, 16))), '')
        act.setData(-1)
        self.typeToggle.setDefaultAction(act)

        for i in range(24):
            act = typeMenu.addAction(QIcon(QPixmap.fromImage(q.copy(i * 16, 0, 16, 16))), '')
            act.setData(i)

        self.typeToggle.triggered.connect(self.setTypeFilter)
        self.typeToggle.setMenu(typeMenu)

        # Weight Toggle Button
        self.weightToggle = QToolButton()
        self.weightToggle.setIconSize(QSize(24, 24))
        self.weightToggle.setPopupMode(QToolButton.InstantPopup)

        weightMenu = FilterMenu()

        q = QImage()
        q.load('resources/UI/WeightIcons.png')

        self.weightToggle.setIcon(QIcon(QPixmap.fromImage(fq.copy(2 * 24, 0, 24, 24))))
        act = weightMenu.addAction(QIcon(QPixmap.fromImage(fq.copy(2 * 24, 0, 24, 24))), '')
        act.setData(-1)
        act.setIconVisibleInMenu(False)
        self.weightToggle.setDefaultAction(act)

        w = [0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 5.0, 1000.0]
        for i in range(9):
            act = weightMenu.addAction(QIcon(QPixmap.fromImage(q.copy(i * 24, 0, 24, 24))), '')
            act.setData(w[i])
            act.setIconVisibleInMenu(False)

        self.weightToggle.triggered.connect(self.setWeightFilter)
        self.weightToggle.setMenu(weightMenu)

        # Size Toggle Button
        self.sizeToggle = QToolButton()
        self.sizeToggle.setIconSize(QSize(24, 24))
        self.sizeToggle.setPopupMode(QToolButton.InstantPopup)

        sizeMenu = FilterMenu()

        q = QImage()
        q.load('resources/UI/ShapeIcons.png')

        self.sizeToggle.setIcon(QIcon(QPixmap.fromImage(fq.copy(3 * 24, 0, 24, 24))))
        act = sizeMenu.addAction(QIcon(QPixmap.fromImage(fq.copy(3 * 24, 0, 24, 24))), '')
        act.setData(-1)
        act.setIconVisibleInMenu(False)
        self.sizeToggle.setDefaultAction(act)

        for i in range(12):
            act = sizeMenu.addAction(QIcon(QPixmap.fromImage(q.copy(i * 16, 0, 16, 16))), '')
            act.setData(i + 1)
            act.setIconVisibleInMenu(False)

        self.sizeToggle.triggered.connect(self.setSizeFilter)
        self.sizeToggle.setMenu(sizeMenu)

        # Add to Layout
        self.filter.addWidget(QLabel("Filter by:"), 0, 0)
        self.filter.addWidget(self.IDFilter, 0, 1)
        self.filter.addWidget(self.entityToggle, 0, 2)
        self.filter.addWidget(self.typeToggle, 0, 3)
        self.filter.addWidget(self.weightToggle, 0, 4)
        self.filter.addWidget(self.sizeToggle, 0, 5)
        self.filter.setContentsMargins(4, 0, 0, 4)

        # Filter active notification and clear buttons

        # Palette
        self.clearAll = QToolButton()
        self.clearAll.setIconSize(QSize(24, 0))
        self.clearAll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.clearAll.clicked.connect(self.clearAllFilter)

        self.clearName = QToolButton()
        self.clearName.setIconSize(QSize(24, 0))
        self.clearName.setSizePolicy(self.IDFilter.sizePolicy())
        self.clearName.clicked.connect(self.clearNameFilter)

        self.clearEntity = QToolButton()
        self.clearEntity.setIconSize(QSize(24, 0))
        self.clearEntity.clicked.connect(self.clearEntityFilter)

        self.clearType = QToolButton()
        self.clearType.setIconSize(QSize(24, 0))
        self.clearType.clicked.connect(self.clearTypeFilter)

        self.clearWeight = QToolButton()
        self.clearWeight.setIconSize(QSize(24, 0))
        self.clearWeight.clicked.connect(self.clearWeightFilter)

        self.clearSize = QToolButton()
        self.clearSize.setIconSize(QSize(24, 0))
        self.clearSize.clicked.connect(self.clearSizeFilter)

        self.filter.addWidget(self.clearAll, 1, 0)
        self.filter.addWidget(self.clearName, 1, 1)
        self.filter.addWidget(self.clearEntity, 1, 2)
        self.filter.addWidget(self.clearType, 1, 3)
        self.filter.addWidget(self.clearWeight, 1, 4)
        self.filter.addWidget(self.clearSize, 1, 5)

    def setupList(self):
        self.list = QListWidget()
        self.list.setViewMode(self.list.ListMode)
        self.list.setSelectionMode(self.list.ExtendedSelection)
        self.list.setResizeMode(self.list.Adjust)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)

        self.list.setAutoScroll(True)
        self.list.setDragEnabled(True)
        self.list.setDragDropMode(4)

        self.list.setVerticalScrollBarPolicy(0)
        self.list.setHorizontalScrollBarPolicy(1)

        self.list.setIconSize(QSize(52, 52))
        d = RoomDelegate()
        self.list.setItemDelegate(d)

        self.list.itemSelectionChanged.connect(self.setButtonStates)
        self.list.doubleClicked.connect(self.activateEdit)
        self.list.customContextMenuRequested.connect(self.customContextMenu)

        self.list.itemDelegate().closeEditor.connect(self.editComplete)

    def setupToolbar(self):
        self.toolbar = QToolBar()

        self.addRoomButton       = self.toolbar.addAction(QIcon(), 'Add', self.addRoom)
        self.removeRoomButton    = self.toolbar.addAction(QIcon(), 'Delete', self.removeRoom)
        self.duplicateRoomButton = self.toolbar.addAction(QIcon(), 'Duplicate', self.duplicateRoom)
        self.exportRoomButton    = self.toolbar.addAction(QIcon(), 'Export...', self.exportRoom)

        self.mirror = False
        self.mirrorY = False
        # self.IDButton = self.toolbar.addAction(QIcon(), 'ID', self.turnIDsOn)
        # self.IDButton.setCheckable(True)
        # self.IDButton.setChecked(True)

    def activateEdit(self):
        room = self.selectedRoom()
        room.setText(room.data(0x100))
        self.list.editItem(self.selectedRoom())

    def editComplete(self, lineEdit):
        room = self.selectedRoom()
        room.setData(0x100, lineEdit.text())
        room.setText(f"{room.info.variant} - {room.data(0x100)}")
        mainWindow.dirt()

    #@pyqtSlot(bool)
    def turnIDsOn(self):
        return

    #@pyqtSlot(QPoint)
    def customContextMenu(self, pos):
        if not self.selectedRoom(): return

        menu = QMenu(self.list)

        # Type
        Type = QWidgetAction(menu)
        c = QComboBox()

        types= [
            "Null Room", "Normal Room", "Shop", "Error Room", "Treasure Room", "Boss Room",
            "Mini-Boss Room", "Secret Room", "Super Secret Room", "Arcade", "Curse Room", "Challenge Room",
            "Library", "Sacrifice Room", "Devil Room", "Angel Room", "Crawlspace", "Boss Rush Room",
            "Isaac's Room", "Barren Room", "Chest Room", "Dice Room", "Black Market", "Greed Mode Descent"
        ]

        q = QImage()
        q.load('resources/UI/RoomIcons.png')

        for i, t in enumerate(types):
            c.addItem(QIcon(QPixmap.fromImage(q.copy(i * 16, 0, 16, 16))), t)
        c.setCurrentIndex(self.selectedRoom().info.type)
        c.currentIndexChanged.connect(self.changeType)
        Type.setDefaultWidget(c)
        menu.addAction(Type)

        # Variant
        Variant = QWidgetAction(menu)
        s = QSpinBox()
        s.setRange(0, 65534)
        s.setPrefix("ID - ")

        s.setValue(self.selectedRoom().info.variant)

        Variant.setDefaultWidget(s)
        s.valueChanged.connect(self.changeVariant)
        menu.addAction(Variant)

        menu.addSeparator()

        # Difficulty
        Difficulty = QWidgetAction(menu)
        dv = QSpinBox()
        dv.setRange(0, 15)
        dv.setPrefix("Difficulty - ")

        dv.setValue(self.selectedRoom().difficulty)

        Difficulty.setDefaultWidget(dv)
        dv.valueChanged.connect(self.changeDifficulty)
        menu.addAction(Difficulty)

        # Weight
        weight = QWidgetAction(menu)
        s = QDoubleSpinBox()
        s.setPrefix("Weight - ")

        s.setValue(self.selectedRoom().weight)

        weight.setDefaultWidget(s)
        s.valueChanged.connect(self.changeWeight)
        menu.addAction(weight)

        # SubVariant
        Subtype = QWidgetAction(menu)
        st = QSpinBox()
        st.setRange(0, 256)
        st.setPrefix("Sub - ")

        st.setValue(self.selectedRoom().info.subtype)

        Subtype.setDefaultWidget(st)
        st.valueChanged.connect(self.changeSubtype)
        menu.addAction(Subtype)

        menu.addSeparator()

        # Room shape
        Shape = QWidgetAction(menu)
        c = QComboBox()

        q = QImage()
        q.load('resources/UI/ShapeIcons.png')

        for shapeName in range(1, 13):
            c.addItem(QIcon(QPixmap.fromImage(q.copy((shapeName - 1) * 16, 0, 16, 16))), str(shapeName))
        c.setCurrentIndex(self.selectedRoom().info.shape - 1)
        c.currentIndexChanged.connect(self.changeSize)
        Shape.setDefaultWidget(c)
        menu.addAction(Shape)

        # End it
        menu.exec(self.list.mapToGlobal(pos))

    #@pyqtSlot(bool)
    def clearAllFilter(self):
        self.IDFilter.clear()
        self.entityToggle.setChecked(False)
        self.filter.typeData = -1
        self.typeToggle.setIcon(self.typeToggle.defaultAction().icon())
        self.filter.weightData = -1
        self.weightToggle.setIcon(self.weightToggle.defaultAction().icon())
        self.filter.sizeData = -1
        self.sizeToggle.setIcon(self.sizeToggle.defaultAction().icon())
        self.changeFilter()

    def clearNameFilter(self):
        self.IDFilter.clear()
        self.changeFilter()

    def clearEntityFilter(self):
        self.entityToggle.setChecked(False)
        self.changeFilter()

    def clearTypeFilter(self):
        self.filter.typeData = -1
        self.typeToggle.setIcon(self.typeToggle.defaultAction().icon())
        self.changeFilter()

    def clearWeightFilter(self):
        self.filter.weightData = -1
        self.weightToggle.setIcon(self.weightToggle.defaultAction().icon())
        self.changeFilter()

    def clearSizeFilter(self):
        self.filter.sizeData = -1
        self.sizeToggle.setIcon(self.sizeToggle.defaultAction().icon())
        self.changeFilter()

    #@pyqtSlot(bool)
    def setEntityToggle(self, checked):
        self.entityToggle.checked = checked

    #@pyqtSlot(QAction)
    def setTypeFilter(self, action):
        self.filter.typeData = action.data()
        self.typeToggle.setIcon(action.icon())
        self.changeFilter()

    #@pyqtSlot(QAction)
    def setWeightFilter(self, action):
        self.filter.weightData = action.data()
        self.weightToggle.setIcon(action.icon())
        self.changeFilter()

    #@pyqtSlot(QAction)
    def setSizeFilter(self, action):
        self.filter.sizeData = action.data()
        self.sizeToggle.setIcon(action.icon())
        self.changeFilter()

    def colourizeClearFilterButtons(self):
        colour = "background-color: #F00;"

        all = False

        # Name Button
        if len(self.IDFilter.text()) > 0:
            self.clearName.setStyleSheet(colour)
            all = True
        else:
            self.clearName.setStyleSheet("")

        # Entity Button
        if self.entityToggle.checked:
            self.clearEntity.setStyleSheet(colour)
            all = True
        else:
            self.clearEntity.setStyleSheet("")

        # Type Button
        if self.filter.typeData is not -1:
            self.clearType.setStyleSheet(colour)
            all = True
        else:
            self.clearType.setStyleSheet("")

        # Weight Button
        if self.filter.weightData is not -1:
            self.clearWeight.setStyleSheet(colour)
            all = True
        else:
            self.clearWeight.setStyleSheet("")

        # Size Button
        if self.filter.sizeData is not -1:
            self.clearSize.setStyleSheet(colour)
            all = True
        else:
            self.clearSize.setStyleSheet("")

        # All Button
        if all:
            self.clearAll.setStyleSheet(colour)
        else:
            self.clearAll.setStyleSheet("")

    #@pyqtSlot()
    def changeFilter(self):
        self.colourizeClearFilterButtons()

        uselessEntities = None

        # Here we go
        for room in self.getRooms():
            IDCond = entityCond = typeCond = weightCond = sizeCond = True

            IDCond = self.IDFilter.text().lower() in room.text().lower()

            # Check if the right entity is in the room
            if self.entityToggle.checked and self.filterEntity:
                entityCond = any(int(self.filterEntity.ID) == e[0] and \
                                 int(self.filterEntity.subtype) == e[2] and \
                                 int(self.filterEntity.variant) == e[1] \
                                 for stack, x, y in room.spawns() for e in stack)

            # Check if the room is the right type
            if self.filter.typeData is not -1:
                # All the normal rooms
                typeCond = self.filter.typeData == room.info.type

                # For null rooms, include "empty" rooms regardless of type
                if not typeCond and self.filter.typeData == 0:
                    if uselessEntities is None:
                        global entityXML
                        uselessEntities = list(map(lambda e: [ int(e.get('ID')), int(e.get('Variant') or 0), int(e.get('Subtype') or 0) ],
                                                entityXML.findall("entity[@InEmptyRooms='1']")))

                    hasUsefulEntities = any(entity[:3] not in uselessEntities \
                                            for stack, x, y in room.spawns() for entity in stack)

                    typeCond = not hasUsefulEntities


            # Check if the room is the right weight
            if self.filter.weightData is not -1:
                eps = 0.0001
                weightCond = abs(self.filter.weightData - room.weight) < eps

            # Check if the room is the right size
            if self.filter.sizeData is not -1:
                sizeCond = self.filter.sizeData == room.info.shape

            # Filter em' out
            isMatch = IDCond and entityCond and typeCond and weightCond and sizeCond
            room.setHidden(not isMatch)

    def setEntityFilter(self, entity):
        self.filterEntity = entity
        self.entityToggle.setIcon(entity.icon)
        self.changeFilter()

    def changeSize(self, shapeIdx):

        # Set the Size - gotta lotta shit to do here
        s = shapeIdx + 1

        # No sense in doing work we don't have to!
        if self.selectedRoom().info.shape == s:
            return

        info = Room.Info(shape=s)
        w, h = info.dims

        # Check to see if resizing will destroy any entities
        mainWindow.storeEntityList()

        warn = any(x >= w or y >= h for stack, x, y in self.selectedRoom().spawns())

        if warn:
            msgBox = QMessageBox(
                QMessageBox.Warning,
                "Resize Room?", "Resizing this room will delete entities placed outside the new size. Are you sure you want to resize this room?",
                QMessageBox.NoButton,
                self
            )
            msgBox.addButton("Resize", QMessageBox.AcceptRole)
            msgBox.addButton("Cancel", QMessageBox.RejectRole)
            if msgBox.exec_() == QMessageBox.RejectRole:
                # It's time for us to go now.
                return

        self.selectedRoom().reshape(s)

        # Clear the room and reset the size
        mainWindow.scene.clear()

        self.selectedRoom().clearDoors()

        mainWindow.scene.newRoomSize(s)

        mainWindow.editor.resizeEvent(QResizeEvent(mainWindow.editor.size(), mainWindow.editor.size()))

        # Spawn those entities
        for entStack, x, y in self.selectedRoom().spawns():
            if x >= w or y >= h: continue

            for entity in entStack:
                e = Entity(x, y, entity[0], entity[1], entity[2], entity[3])
                mainWindow.scene.addItem(e)

        self.selectedRoom().setToolTip()
        mainWindow.dirt()

    #@pyqtSlot(int)
    def changeType(self, rtype):
        for r in self.selectedRooms():
            r.info.type = rtype
            r.renderDisplayIcon()
            r.setRoomBG()

            r.setToolTip()

        mainWindow.scene.update()
        mainWindow.dirt()

    #@pyqtSlot(int)
    def changeVariant(self, var):
        for r in self.selectedRooms():
            r.info.variant = var
            r.setToolTip()
        mainWindow.dirt()
        mainWindow.scene.update()

    #@pyqtSlot(int)
    def changeSubtype(self, var):
        for r in self.selectedRooms():
            r.info.subtype = var
            r.setToolTip()
        mainWindow.dirt()
        mainWindow.scene.update()

    #@pyqtSlot(QAction)
    def changeDifficulty(self, var):
        for r in self.selectedRooms():
            r.difficulty = var
            r.setToolTip()
        mainWindow.dirt()
        mainWindow.scene.update()

    #@pyqtSlot(QAction)
    def changeWeight(self, action):
        for r in self.selectedRooms():
            #r.weight = float(action.text())
            r.weight = action
            r.setToolTip()
        mainWindow.dirt()
        mainWindow.scene.update()

    def keyPressEvent(self, event):
        self.list.keyPressEvent(event)

        if event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace:
            self.removeRoom()

    def addRoom(self):
        """Creates a new room."""

        r = Room()
        self.list.insertItem(self.list.currentRow()+1, r)
        self.list.setCurrentItem(r, QItemSelectionModel.ClearAndSelect)
        mainWindow.dirt()

    def removeRoom(self):
        """Removes selected room (no takebacks)"""

        rooms = self.selectedRooms()
        if rooms == None or len(rooms) == 0:
            return

        msgBox = QMessageBox(QMessageBox.Warning,
                "Delete Room?", "Are you sure you want to delete the selected rooms? This action cannot be undone.",
                QMessageBox.NoButton, self)
        msgBox.addButton("Delete", QMessageBox.AcceptRole)
        msgBox.addButton("Cancel", QMessageBox.RejectRole)
        if msgBox.exec_() == QMessageBox.AcceptRole:

            self.list.clearSelection()
            for item in rooms:
                self.list.takeItem(self.list.row(item))

            self.list.scrollToItem(self.list.currentItem())
            self.list.setCurrentItem(self.list.currentItem(), QItemSelectionModel.Select)
            mainWindow.dirt()

    def duplicateRoom(self):
        """Duplicates the selected room"""

        rooms = self.orderedSelectedRooms()
        if not rooms: return

        numRooms = len(rooms)

        mainWindow.storeEntityList()

        lastPlace = self.list.indexFromItem(rooms[-1]).row() + 1
        self.selectedRoom().setData(100, False)
        self.list.setCurrentItem(None, QItemSelectionModel.ClearAndSelect)

        for room in reversed(rooms):
            if self.mirrorY:
                v = 20000
                extra = ' (flipped Y)'
            elif self.mirror:
                v = 10000
                extra = ' (flipped X)'
            else:
                v = numRooms
                extra = ' (copy)'

            r = Room(
                deepcopy(room.data(0x100) + extra),
                deepcopy(room.gridSpawns),
                deepcopy(room.difficulty),
                deepcopy(room.weight),
                deepcopy(room.info.type),
                deepcopy(room.info.variant+v),
                deepcopy(room.info.subtype),
                deepcopy(room.info.shape),
                deepcopy([list(door) for door in room.info.doors])
            )

            # Mirror the room
            if self.mirror:
                if self.mirrorY:
                    r.mirrorY()
                else:
                    r.mirrorX()

            self.list.insertItem(lastPlace, r)
            self.list.setCurrentItem(r, QItemSelectionModel.Select)

        mainWindow.dirt()

    def mirrorButtonOn(self):
        self.mirror = True
        self.duplicateRoomButton.setText("Mirror X")

    def mirrorButtonOff(self):
        self.mirror = False
        self.mirrorY = False
        self.duplicateRoomButton.setText("Duplicate")

    def mirrorYButtonOn(self):
        if self.mirror:
            self.mirrorY = True
            self.duplicateRoomButton.setText("Mirror Y")

    def mirrorYButtonOff(self):
        if self.mirror:
            self.mirrorY = False
            self.duplicateRoomButton.setText("Mirror X")

    def exportRoom(self):

        dialogDir = mainWindow.getRecentFolder()

        target, match = QFileDialog.getSaveFileName(self, 'Select a new name or an existing STB', dialogDir, 'Stage Bundle (*.stb)', '', QFileDialog.DontConfirmOverwrite)
        mainWindow.restoreEditMenu()

        if len(target) == 0:
            return

        path = target

        # Append these rooms onto the new STB
        rooms = self.orderedSelectedRooms()
        if os.path.exists(path):
            oldRooms = mainWindow.open(path)
            oldRooms.extend(rooms)
            mainWindow.save(oldRooms, path)
        # Make a new STB with the selected rooms
        else:
            mainWindow.save(rooms, path)

    def setButtonStates(self):
        rooms = len(self.selectedRooms()) > 0

        self.removeRoomButton.setEnabled(rooms)
        self.duplicateRoomButton.setEnabled(rooms)
        self.exportRoomButton.setEnabled(rooms)

    def selectedRoom(self):
        return self.list.currentItem()

    def selectedRooms(self):
        return self.list.selectedItems()

    def orderedSelectedRooms(self):
        sortedIndexes = sorted(self.list.selectionModel().selectedIndexes(), key=lambda x: (x.column(), x.row()))
        return [ self.list.itemFromIndex(i) for i in sortedIndexes ]

    def getRooms(self):
        return [ self.list.item(i) for i in range(self.list.count()) ]

# Entity Palette
########################

class EntityGroupItem(object):
    """Group Item to contain Entities for sorting"""

    def __init__(self, name):

        self.objects = []
        self.startIndex = 0
        self.endIndex = 0

        self.name = name
        self.alignment = Qt.AlignCenter

    def getItem(self, index):
        ''' Retrieves an item of a specific index. The index is already checked for validity '''

        if index == self.startIndex:
            return self

        if (index <= self.startIndex + len(self.objects)):
            return self.objects[index - self.startIndex - 1]

    def calculateIndices(self, index):
        self.startIndex = index
        self.endIndex = len(self.objects) + index

class EntityItem(QStandardItem):
    """A single entity, pretty much just an icon and a few params."""

    def __init__(self, name, ID, subtype, variant, iconPath):
        QStandardItem.__init__(self)

        self.name = name
        self.ID = ID
        self.subtype = subtype
        self.variant = variant
        self.icon = QIcon(iconPath)

        self.setToolTip(name)

class EntityGroupModel(QAbstractListModel):
    """Model containing all the grouped objects in a tileset"""

    def __init__(self, kind, enList):
        QAbstractListModel.__init__(self)

        self.groups = {}
        self.kind = kind
        self.view = None

        self.filter = ""

        for en in enList:
            g = en.get('Group')
            k = en.get('Kind')

            if self.kind == k or self.kind == None:
                if g and g not in self.groups:
                    self.groups[g] = EntityGroupItem(g)

                imgPath = en.get('Image')
                if not (imgPath and os.path.exists(imgPath)):
                    en.set("Image", "resources/Entities/questionmark.png")

                e = EntityItem(en.get('Name'), en.get('ID'), en.get('Subtype'), en.get('Variant'), en.get('Image'))

                if g != None:
                    self.groups[g].objects.append(e)

        i = 0
        for key, group in sorted(self.groups.items()):
            group.calculateIndices(i)
            i = group.endIndex + 1

    def rowCount(self, parent=None):
        c = 0

        for group in self.groups.values():
            c += len(group.objects) + 1

        return c

    def flags(self, index):
        item = self.getItem(index.row())

        if isinstance(item, EntityGroupItem):
            return Qt.NoItemFlags
        else:
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def getItem(self, index):
        for group in self.groups.values():
            if (group.startIndex <= index) and (index <= group.endIndex):
                return group.getItem(index)

    def data(self, index, role=Qt.DisplayRole):
        # Should return the contents of a row when asked for the index
        #
        # Can be optimized by only dealing with the roles we need prior
        # to lookup: Role order is 13, 6, 7, 9, 10, 1, 0, 8

        if ((role > 1) and (role < 6)):
            return None

        elif role == Qt.ForegroundRole:
            return QBrush(Qt.black)

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter


        if not index.isValid(): return None
        n = index.row()

        if n < 0: return None
        if n >= self.rowCount(): return None

        item = self.getItem(n)

        if role == Qt.DecorationRole:
            if isinstance(item, EntityItem):
                return item.icon

        if role == Qt.ToolTipRole or role == Qt.StatusTipRole or role == Qt.WhatsThisRole:
            if isinstance(item, EntityItem):
                return "{0}".format(item.name)

        elif role == Qt.DisplayRole:
            if isinstance(item, EntityGroupItem):
                return item.name

        elif (role == Qt.SizeHintRole):
            if isinstance(item, EntityGroupItem):
                return QSize(self.view.viewport().width(), 24)

        elif role == Qt.BackgroundRole:
            if isinstance(item, EntityGroupItem):

                colour = 165

                if colour > 255:
                    colour = 255

                brush = QBrush(QColor(colour, colour, colour), Qt.Dense4Pattern)

                return brush

        elif (role == Qt.FontRole):
            font = QFont()
            font.setPixelSize(16)
            font.setBold(True)

            return font

        return None

class EntityPalette(QWidget):

    def __init__(self):
        """Initialises the widget. Remember to call setTileset() on it
        whenever the layer changes."""

        QWidget.__init__(self)

        # Make the layout
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)

        # Create the tabs for the default and mod entities
        self.tabs = QTabWidget()
        self.populateTabs()
        self.layout.addWidget(self.tabs)

        # Create the hidden search results tab
        self.searchTab = QTabWidget()

        global entityXML
        allEnts = entityXML.findall("entity")

        # Funky model setup
        listView = EntityList()
        listView.setModel(EntityGroupModel(None, allEnts))
        listView.model().view = listView
        listView.clicked.connect(self.objSelected)

        # Hide the search results
        self.searchTab.addTab(listView, "Search")
        self.searchTab.hide()

        self.layout.addWidget(self.searchTab)

        # Add the Search bar
        self.searchBar = QLineEdit()
        self.searchBar.setPlaceholderText("Search")
        self.searchBar.textEdited.connect(self.updateSearch)
        self.layout.addWidget(self.searchBar)

        # And Done
        self.setLayout(self.layout)

    def populateTabs(self):

        groups = {
            "Pickups": [],
            "Enemies": [],
            "Bosses": [],
            "Stage": [],
            "Collect": [],
            "Mods": []
        }

        global entityXML
        enList = entityXML.findall("entity")

        for en in enList:
            k = en.get('Kind')
            if k is None: continue

            if k not in groups:
                groups[k] = []
            groups[k].append(en)

        for group, ents in groups.items():
            numEnts = len(ents)
            if numEnts == 0: continue

            listView = EntityList()
            print(f'Populating palette tab "{group}" with {numEnts} entities')

            listView.setModel(EntityGroupModel(group, ents))
            listView.model().view = listView

            listView.clicked.connect(self.objSelected)

            if group == "Bosses":
                listView.setIconSize(QSize(52, 52))

            if group == "Collect":
                listView.setIconSize(QSize(32, 64))

            self.tabs.addTab(listView, group)

    def currentSelectedObject(self):
        """Returns the currently selected object reference, for painting purposes."""

        if len(self.searchBar.text()) > 0:
            index = self.searchTab.currentWidget().currentIndex().row()
            obj = self.searchTab.currentWidget().model().getItem(index)
        else:
            index = self.tabs.currentWidget().currentIndex().row()
            obj = self.tabs.currentWidget().model().getItem(index)

        return obj

    #@pyqtSlot()
    def objSelected(self):
        """Throws a signal emitting the current object when changed"""

        curr = self.currentSelectedObject()
        if curr == None: return

        # holding ctrl skips the filter change step
        kb = int(QGuiApplication.keyboardModifiers())

        holdCtrl = kb & Qt.ControlModifier != 0
        pinEntityFilter = settings.value('PinEntityFilter') == '1'
        self.objChanged.emit(curr, holdCtrl == pinEntityFilter)

        # Throws a signal when the selected object is used as a replacement
        if kb & Qt.AltModifier != 0:
            self.objReplaced.emit(curr)

    #@pyqtSlot()
    def updateSearch(self, text):
        if len(self.searchBar.text()) > 0:
            self.tabs.hide()
            self.searchTab.widget(0).filter = text
            self.searchTab.widget(0).filterList()
            self.searchTab.show()
        else:
            self.tabs.show()
            self.searchTab.hide()

    objChanged = pyqtSignal(EntityItem,bool)
    objReplaced = pyqtSignal(EntityItem)

class EntityList(QListView):

    def __init__(self):
        QListView.__init__(self)

        self.setFlow(QListView.LeftToRight)
        self.setLayoutMode(QListView.SinglePass)
        self.setMovement(QListView.Static)
        self.setResizeMode(QListView.Adjust)
        self.setWrapping(True)
        self.setIconSize(QSize(26, 26))

        self.setMouseTracking(True)

        self.filter = ""

    def mouseMoveEvent(self, event):

        index = self.indexAt(event.pos()).row()

        if index is not -1:
            item = self.model().getItem(index)

            if isinstance(item, EntityItem):
                QToolTip.showText(event.globalPos(), item.name)

    def filterList(self):
        m = self.model()
        rows = m.rowCount()

        # First loop for entity items
        for row in range(rows):
            item = m.getItem(row)

            if isinstance(item, EntityItem):
                if self.filter.lower() in item.name.lower():
                    self.setRowHidden(row, False)
                else:
                    self.setRowHidden(row, True)

        # Second loop for Group titles, check to see if all contents are hidden or not
        for row in range(rows):
            item = m.getItem(row)

            if isinstance(item, EntityGroupItem):
                self.setRowHidden(row, True)

                for i in range(item.startIndex, item.endIndex):
                    if not self.isRowHidden(i):
                        self.setRowHidden(row, False)


class ReplaceDialog(QDialog):

    class EntSpinners(QWidget):

        def __init__(self):
            super(QWidget, self).__init__()
            layout = QFormLayout()

            self.type = QSpinBox()
            self.type.setRange(1, 2**31-1)
            self.variant = QSpinBox()
            self.variant.setRange(-1, 2**31-1)
            self.subtype = QSpinBox()
            self.subtype.setRange(-1, 2**8-1)

            layout.addRow('&Type:', self.type)
            layout.addRow('&Variant:', self.variant)
            layout.addRow('&Subtype:', self.subtype)

            self.entity = Entity.Info(0,0,0,0,0,0,changeAtStart=False)

            self.type.valueChanged.connect(self.resetEnt)
            self.variant.valueChanged.connect(self.resetEnt)
            self.subtype.valueChanged.connect(self.resetEnt)

            self.setLayout(layout)

        def getEnt(self):
            return (self.type.value(),
                    self.variant.value(),
                    self.subtype.value())

        def setEnt(self, t, v, s):
            self.type.setValue(t)
            self.variant.setValue(v)
            self.subtype.setValue(s)
            self.entity.changeTo(t, v, s)

        valueChanged = pyqtSignal()

        def resetEnt(self):
            self.entity.changeTo(*self.getEnt())
            self.valueChanged.emit()

    def __init__(self):
        super(QDialog, self).__init__()
        self.setWindowTitle("Replace Entities")

        layout = QVBoxLayout()

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        cols = QHBoxLayout()

        def genEnt(name):
            spinners = ReplaceDialog.EntSpinners()
            info = QVBoxLayout()
            info.addWidget(QLabel(name))
            icon = QLabel()
            spinners.valueChanged.connect(lambda: icon.setPixmap(spinners.entity.pixmap))
            info.addWidget(icon)
            infoWidget = QWidget()
            infoWidget.setLayout(info)
            return infoWidget, spinners

        fromInfo, self.fromEnt = genEnt("From")
        toInfo, self.toEnt = genEnt("To")

        selection = mainWindow.scene.selectedItems()
        if len(selection) > 0:
            selection = selection[0].entity
            self.fromEnt.setEnt(int(selection.Type), int(selection.Variant), int(selection.Subtype))
        else:
            self.fromEnt.resetEnt()

        paint = mainWindow.editor.objectToPaint
        if paint:
            self.toEnt.setEnt(int(paint.ID), int(paint.variant), int(paint.subtype))
        else:
            self.toEnt.resetEnt()

        cols.addWidget(fromInfo)
        cols.addWidget(self.fromEnt)
        cols.addWidget(toInfo)
        cols.addWidget(self.toEnt)

        layout.addLayout(cols)
        layout.addWidget(buttonBox)
        self.setLayout(layout)


class HooksDialog(QDialog):

    class HookItem(QListWidgetItem):
        def __init__(self, text, setting, tooltip):
            super(QListWidgetItem, self).__init__(text)
            self.setToolTip(tooltip)
            self.setting = setting

        @property
        def val(self):
            settings =  QSettings('settings.ini', QSettings.IniFormat)
            return settings.value(self.setting, [])

        @val.setter
        def val(self, v):
            settings =  QSettings('settings.ini', QSettings.IniFormat)
            res = v
            if v == None:
                settings.remove(self.setting)
            else:
                settings.setValue(self.setting, res)

    def __init__(self, parent):
        super(QDialog, self).__init__(parent)
        self.setWindowTitle("Set Hooks")

        self.layout = QHBoxLayout()

        hookTypes = [
            ('On Save File', 'HooksSave', 'Runs on saved room files whenever a full save is performed'),
            ('On Test Room', 'HooksTest', 'Runs on output room xmls when preparing to test the current room')
        ]

        self.hooks = QListWidget()
        for hook in hookTypes:
            self.hooks.addItem(HooksDialog.HookItem(*hook))
        self.layout.addWidget(self.hooks)

        pane = QVBoxLayout()
        pane.setContentsMargins(0,0,0,0)
        paneWidget = QWidget()
        paneWidget.setLayout(pane)

        self.content = QListWidget()
        pane.addWidget(self.content)

        addButton = QPushButton("Add")
        editButton = QPushButton("Edit")
        deleteButton = QPushButton("Delete")

        buttons = QHBoxLayout()
        buttons.addWidget(addButton)
        buttons.addWidget(editButton)
        buttons.addWidget(deleteButton)
        pane.addLayout(buttons)

        self.layout.addWidget(paneWidget, 1)

        self.hooks.currentItemChanged.connect(self.displayHook)

        addButton.clicked.connect(self.addPath)
        editButton.clicked.connect(self.editPath)
        deleteButton.clicked.connect(self.deletePath)

        self.setLayout(self.layout)

    def contentPaths(self):
        return [ self.content.item(i).text() for i in range(self.content.count()) ] or None

    def setPaths(self, val):
        self.content.clear()
        if not val: return
        self.content.addItems(val)

    def displayHook(self, new, old):
        if old: old.val = self.contentPaths()
        self.setPaths(new.val)

    def insertPath(self, path=None):
        path = path or findModsPath()

        target, _ = QFileDialog.getOpenFileName(self, 'Select script', os.path.normpath(path), 'All files (*)')
        return target

    def addPath(self):
        path = self.insertPath()
        if path != '':
            self.content.addItem(path)

    def editPath(self):
        item = self.content.currentItem()
        if not item: return

        path = self.insertPath(item.text())
        if path != '':
            item.setText(path)

    def deletePath(self):
        if self.content.currentItem():
            self.content.takeItem(self.content.currentRow())

    def closeEvent(self, evt):
        curr = self.hooks.currentItem()
        if curr: curr.val = self.contentPaths()
        QWidget.closeEvent(self, evt)

class TestConfigDialog(QDialog):

    class ConfigItem(QLabel):
        def __init__(self, text, setting, tooltip, default = None):
            super(QLabel, self).__init__(text)
            self.setToolTip(tooltip)
            self.setting = setting
            self.default = default

        @property
        def val(self):
            settings =  QSettings('settings.ini', QSettings.IniFormat)
            return settings.value(self.setting, self.default)

        @val.setter
        def val(self, v):
            settings =  QSettings('settings.ini', QSettings.IniFormat)
            res = v
            if v == None:
                settings.remove(self.setting)
            else:
                settings.setValue(self.setting, res)

    def __init__(self, parent):
        super(QDialog, self).__init__(parent)
        self.setWindowTitle("Test Configuration")

        self.layout = QVBoxLayout()

        # character
        characterLayout = QHBoxLayout()
        self.characterConfig = TestConfigDialog.ConfigItem('Character', 'TestCharacter', "Character to switch to when testing. (Isaac, Magdalene, etc.) If omitted, use the game's default")
        self.characterEntry = QLineEdit()
        characterLayout.addWidget(self.characterConfig)
        characterLayout.addWidget(self.characterEntry)
        characterWidget = QWidget()
        characterWidget.setLayout(characterLayout)
        #self.layout.addWidget(characterWidget)

        # commands
        commandLayout = QVBoxLayout()
        self.commandConfig = TestConfigDialog.ConfigItem('Debug Commands', 'TestCommands', 'Debug Console Commands that will get run one at a time after other BR initialization has finished', [])
        pane = QVBoxLayout()
        pane.setContentsMargins(0,0,0,0)
        paneWidget = QWidget()
        paneWidget.setLayout(pane)

        self.commandList = QListWidget()
        pane.addWidget(self.commandList)

        addButton = QPushButton("Add")
        editButton = QPushButton("Edit")
        deleteButton = QPushButton("Delete")

        buttons = QHBoxLayout()
        buttons.addWidget(addButton)
        buttons.addWidget(deleteButton)
        pane.addLayout(buttons)

        commandLayout.addWidget(self.commandConfig)
        commandLayout.addWidget(paneWidget)

        commandWidget = QWidget()
        commandWidget.setLayout(commandLayout)

        self.layout.addWidget(commandWidget, 1)

        # enable/disable
        enableLayout = QHBoxLayout()
        self.enableConfig = TestConfigDialog.ConfigItem('Enabled', 'TestConfigDisabled', "Enable/disable the test config bonus settings")
        self.enableCheck = QCheckBox('Enabled')
        self.enableCheck.setToolTip(self.enableConfig.toolTip())
        enableLayout.addWidget(self.enableCheck)
        enableWidget = QWidget()
        enableWidget.setLayout(enableLayout)
        self.layout.addWidget(enableWidget)

        addButton.clicked.connect(self.addCommand)
        deleteButton.clicked.connect(self.deleteCommand)

        self.setValues()

        self.setLayout(self.layout)

    def enabled(self):
        return None if self.enableCheck.isChecked() else '1'

    def character(self):
        #return self.characterEntry.text() or None
        return None

    def commands(self):
        return [ self.commandList.item(i).text() for i in range(self.commandList.count()) ] or None

    def setValues(self):
        self.enableCheck.setChecked(self.enableConfig.val != '1')
        #self.characterEntry.setText(self.characterConfig.val)
        self.commandList.clear()
        self.commandList.addItems(self.commandConfig.val)
        for i in range(self.commandList.count()):
            item = self.commandList.item(i)
            item.setFlags(item.flags() | Qt.ItemIsEditable)

    def addCommand(self):
        item = QListWidgetItem('combo 2')
        item.setFlags(item.flags() | Qt.ItemIsEditable)
        self.commandList.addItem(item)

    def deleteCommand(self):
        if self.commandList.currentItem():
            self.commandList.takeItem(self.commandList.currentRow())

    def closeEvent(self, evt):
        self.enableConfig.val = self.enabled()
        #self.characterConfig.val = self.character()
        self.commandConfig.val = self.commands()
        QWidget.closeEvent(self, evt)

########################
#      Main Window     #
########################

class MainWindow(QMainWindow):

    def keyPressEvent(self, event):
        QMainWindow.keyPressEvent(self, event)
        if event.key() == Qt.Key_Alt:
            self.roomList.mirrorButtonOn()
        if event.key() == Qt.Key_Shift:
            self.roomList.mirrorYButtonOn()

    def keyReleaseEvent(self, event):
        QMainWindow.keyReleaseEvent(self, event)
        if event.key() == Qt.Key_Alt:
            self.roomList.mirrorButtonOff()
        if event.key() == Qt.Key_Shift:
            self.roomList.mirrorYButtonOff()

    def __init__(self):
        super(QMainWindow, self).__init__()

        self.setWindowTitle('Basement Renovator')
        self.setIconSize(QSize(16, 16))

        self.dirty = False

        self.wroteModFolder = False
        self.disableTestModTimer = None

        self.scene = RoomScene()
        self.clipboard = None

        self.editor = RoomEditorWidget(self.scene)
        self.setCentralWidget(self.editor)

        self.fixupStage()

        self.setupDocks()
        self.setupMenuBar()

        self.setGeometry(100, 500, 1280, 600)

        self.restoreState(settings.value('MainWindowState', self.saveState()), 0)
        self.restoreGeometry(settings.value('MainWindowGeometry', self.saveGeometry()))

        self.resetWindow = {"state" : self.saveState(), "geometry" : self.saveGeometry()}

        # Setup a new map
        self.newMap()
        self.clean()

    def fixupStage(self):
        global stageXML

        fixIconFormat = settings.value('FixIconFormat') == '1'

        for stage in stageXML.findall('stage'):
            prefix = stage.get('BGPrefix')
            if prefix is None:
                baseStage = stageXML.find(f"stage[@Stage='{stage.get('Stage')}'][@StageType='{stage.get('StageType')}'][@BGPrefix]")
                prefix = baseStage.get('BGPrefix')
            stage.set('OuterBG', prefix + '.png')
            stage.set('InnerBG', prefix + 'Inner.png')

            if fixIconFormat:
                for imgPath in [ stage.get('OuterBG'), stage.get('InnerBG') ]:
                    formatFix = QImage(imgPath)
                    formatFix.save(imgPath)


    def setupFileMenuBar(self):
        f = self.fileMenu

        f.clear()
        self.fa = f.addAction('New',                self.newMap, QKeySequence("Ctrl+N"))
        self.fc = f.addAction('Open',          		self.openMap, QKeySequence("Ctrl+O"))
        self.fb = f.addAction('Open by Stage',      self.openMapDefault, QKeySequence("Ctrl+Shift+O"))
        f.addSeparator()
        self.fd = f.addAction('Save',               self.saveMap, QKeySequence("Ctrl+S"))
        self.fe = f.addAction('Save As...',         self.saveMapAs, QKeySequence("Ctrl+Shift+S"))
        f.addSeparator()
        self.fg = f.addAction('Take Screenshot...', self.screenshot, QKeySequence("Ctrl+Alt+S"))
        f.addSeparator()
        self.fh = f.addAction('Set Resources Path',   self.setDefaultResourcesPath, QKeySequence("Ctrl+Shift+P"))
        self.fi = f.addAction('Reset Resources Path', self.resetResourcesPath, QKeySequence("Ctrl+Shift+R"))
        f.addSeparator()
        self.fj = f.addAction('Set Hooks', self.showHooksMenu)
        self.fl = f.addAction('Autogenerate mod content (discouraged)', lambda: self.toggleSetting('ModAutogen'))
        self.fl.setCheckable(True)
        self.fl.setChecked(settings.value('ModAutogen') == '1')
        f.addSeparator()

        recent = settings.value("RecentFiles", [])
        for r in recent:
            f.addAction(os.path.normpath(r), self.openRecent).setData(r)

        f.addSeparator()

        self.fj = f.addAction('Exit', self.close, QKeySequence.Quit)

    def setupMenuBar(self):
        mb = self.menuBar()

        self.fileMenu = mb.addMenu('&File')
        self.setupFileMenuBar()

        self.e = mb.addMenu('Edit')
        self.ea = self.e.addAction('Copy',                        self.copy, QKeySequence.Copy)
        self.eb = self.e.addAction('Cut',                         self.cut, QKeySequence.Cut)
        self.ec = self.e.addAction('Paste',                       self.paste, QKeySequence.Paste)
        self.ed = self.e.addAction('Select All',                  self.selectAll, QKeySequence.SelectAll)
        self.ee = self.e.addAction('Deselect',                    self.deSelect, QKeySequence("Ctrl+D"))
        self.e.addSeparator()
        self.ef = self.e.addAction('Clear Filters',               self.roomList.clearAllFilter, QKeySequence("Ctrl+K"))
        self.eg = self.e.addAction('Pin Entity Filter',           lambda: self.toggleSetting('PinEntityFilter'), QKeySequence("Ctrl+Alt+K"))
        self.eg.setCheckable(True)
        self.eg.setChecked(settings.value('PinEntityFilter') == '1')
        self.el = self.e.addAction('Snap to Room Boundaries', lambda: self.toggleSetting('SnapToBounds', onDefault=True))
        self.el.setCheckable(True)
        self.el.setChecked(settings.value('SnapToBounds') != '0')
        self.e.addSeparator()
        self.eh = self.e.addAction('Bulk Replace Entities',       self.showReplaceDialog, QKeySequence("Ctrl+R"))
        self.ei = self.e.addAction('Sort Rooms by ID',            self.sortRoomIDs)
        self.ej = self.e.addAction('Sort Rooms by Name',          self.sortRoomNames)
        self.ek = self.e.addAction('Recompute Room IDs',          self.recomputeRoomIDs, QKeySequence("Ctrl+B"))

        v = mb.addMenu('View')
        self.wa = v.addAction('Show Grid',                        lambda: self.toggleSetting('GridEnabled', onDefault=True), QKeySequence("Ctrl+G"))
        self.wa.setCheckable(True)
        self.wa.setChecked(settings.value('GridEnabled') != '0')
        self.wg = v.addAction('Show Out of Bounds Grid',          lambda: self.toggleSetting('BoundsGridEnabled'))
        self.wg.setCheckable(True)
        self.wg.setChecked(settings.value('BoundsGridEnabled') == '1')
        self.wh = v.addAction('Show Grid Indexes',                lambda: self.toggleSetting('ShowGridIndex'))
        self.wh.setCheckable(True)
        self.wh.setChecked(settings.value('ShowGridIndex') == '1')
        self.wi = v.addAction('Show Grid Coordinates',            lambda: self.toggleSetting('ShowCoordinates'))
        self.wi.setCheckable(True)
        self.wi.setChecked(settings.value('ShowCoordinates') == '1')
        v.addSeparator()
        self.we = v.addAction('Show Room Info',                   lambda: self.toggleSetting('StatusEnabled', onDefault=True), QKeySequence("Ctrl+I"))
        self.we.setCheckable(True)
        self.we.setChecked(settings.value('StatusEnabled') != '0')
        self.wd = v.addAction('Use Bitfont Counter',              lambda: self.toggleSetting('BitfontEnabled', onDefault=True))
        self.wd.setCheckable(True)
        self.wd.setChecked(settings.value('BitfontEnabled') != '0')
        v.addSeparator()
        self.wb = v.addAction('Hide Entity Painter',              self.showPainter, QKeySequence("Ctrl+Alt+P"))
        self.wc = v.addAction('Hide Room List',                   self.showRoomList, QKeySequence("Ctrl+Alt+R"))
        self.wf = v.addAction('Reset Window Defaults',            self.resetWindowDefaults)
        v.addSeparator()

        r = mb.addMenu('Test')
        self.ra = r.addAction('Test Current Room - InstaPreview',  self.testMapInstapreview, QKeySequence("Ctrl+P"))
        self.rb = r.addAction('Test Current Room - Replace Stage', self.testMap,             QKeySequence("Ctrl+T"))
        self.rc = r.addAction('Test Current Room - Replace Start', self.testStartMap,        QKeySequence("Ctrl+Shift+T"))
        r.addSeparator()
        self.re = r.addAction('Test Configuration', self.showTestConfigMenu)
        self.rd = r.addAction('Enable Test Mod Dialog',  lambda: self.toggleSetting('DisableTestDialog'))
        self.rd.setCheckable(True)
        self.rd.setChecked(settings.value('DisableTestDialog') != '1')

        h = mb.addMenu('Help')
        self.ha = h.addAction('About Basement Renovator',         self.aboutDialog)
        self.hb = h.addAction('Basement Renovator Documentation', self.goToHelp)
        # self.hc = h.addAction('Keyboard Shortcuts')

    def setupDocks(self):
        self.roomList = RoomSelector()
        self.roomListDock = QDockWidget('Rooms')
        self.roomListDock.setWidget(self.roomList)
        self.roomListDock.visibilityChanged.connect(self.updateDockVisibility)
        self.roomListDock.setObjectName("RoomListDock")

        self.roomList.list.currentItemChanged.connect(self.handleSelectedRoomChanged)

        self.addDockWidget(Qt.RightDockWidgetArea, self.roomListDock)

        self.EntityPalette = EntityPalette()
        self.EntityPaletteDock = QDockWidget('Entity Palette')
        self.EntityPaletteDock.setWidget(self.EntityPalette)
        self.EntityPaletteDock.visibilityChanged.connect(self.updateDockVisibility)
        self.EntityPaletteDock.setObjectName("EntityPaletteDock")

        self.EntityPalette.objChanged.connect(self.handleObjectChanged)
        self.EntityPalette.objReplaced.connect(self.handleObjectReplaced)

        self.addDockWidget(Qt.LeftDockWidgetArea, self.EntityPaletteDock)

    def restoreEditMenu(self):
        a = self.e.actions()
        self.e.insertAction(a[1], self.ea)
        self.e.insertAction(a[2], self.eb)
        self.e.insertAction(a[3], self.ec)
        self.e.insertAction(a[4], self.ed)
        self.e.insertAction(a[5], self.ee)

    def updateTitlebar(self):
        if self.path == '':
            effectiveName = 'Untitled Map'
        else:
            if "Windows" in platform.system():
                effectiveName = os.path.normpath(self.path)
            else:
                effectiveName = os.path.basename(self.path)

        self.setWindowTitle('%s - Basement Renovator' % effectiveName)

    def checkDirty(self):
        if self.dirty == False:
            return False

        msgBox = QMessageBox(QMessageBox.Warning,
                "File is not saved", "Completing this operation without saving could cause loss of data.",
                QMessageBox.NoButton, self)
        msgBox.addButton("Continue", QMessageBox.AcceptRole)
        msgBox.addButton("Cancel", QMessageBox.RejectRole)
        if msgBox.exec_() == QMessageBox.AcceptRole:
            self.clean()
            return False

        return True

    def dirt(self):
        self.setWindowIcon(QIcon('resources/UI/BasementRenovator-SmallDirty.png'))
        self.dirty = True

    def clean(self):
        self.setWindowIcon(QIcon('resources/UI/BasementRenovator-Small.png'))
        self.dirty = False

    def storeEntityList(self, room=None):
        room = room or self.roomList.selectedRoom()
        if not room: return

        eList = self.scene.items()

        spawns = [ [] for x in room.gridSpawns ]
        doors = []

        width = room.info.dims[0]

        for e in eList:
            if isinstance(e, Door):
                doors.append(e.doorItem)

            elif isinstance(e, Entity):
                spawns[Room.Info.gridIndex(e.entity.x, e.entity.y, width)].append([ e.entity.Type, e.entity.Variant, e.entity.Subtype, e.entity.weight ])

        room.gridSpawns = spawns
        room.info.doors = doors

    def closeEvent(self, event):
        """Handler for the main window close event"""

        self.disableTestMod()

        if self.checkDirty():
            event.ignore()
        else:
            settings = QSettings('settings.ini', QSettings.IniFormat)

            # Save our state
            settings.setValue('MainWindowGeometry', self.saveGeometry())
            settings.setValue('MainWindowState', self.saveState(0))

            event.accept()

            app.quit()


#####################
# Slots for Widgets #
#####################

    #@pyqtSlot(Room, Room)
    def handleSelectedRoomChanged(self, current, prev):

        if not current: return

        # Encode the current room, just in case there are changes
        if prev:
            self.storeEntityList(prev)

            # Clear the current room mark
            prev.setData(100, False)

        # Clear the room and reset the size
        self.scene.clear()
        self.scene.newRoomSize(current.info.shape)

        self.editor.resizeEvent(QResizeEvent(self.editor.size(), self.editor.size()))

        # Make some doors
        current.clearDoors()

        # Spawn those entities
        for stack, x, y in current.spawns():
            for ent in stack:
                self.scene.addItem(Entity(x, y, ent[0], ent[1], ent[2], ent[3]))

        # Make the current Room mark for clearer multi-selection
        current.setData(100, True)

    #@pyqtSlot(EntityItem)
    def handleObjectChanged(self, entity, setFilter=True):
        self.editor.objectToPaint = entity
        if setFilter:
            self.roomList.setEntityFilter(entity)

    #@pyqtSlot(EntityItem)
    def handleObjectReplaced(self, entity):
        for item in self.scene.selectedItems():
            item.setData(int(entity.ID), int(entity.variant), int(entity.subtype))
            item.update()

        self.dirt()


########################
# Slots for Menu Items #
########################

# File
########################

    def newMap(self):
        if self.checkDirty(): return
        self.roomList.list.clear()
        self.scene.clear()
        self.path = ''

        self.updateTitlebar()
        self.dirt()
        self.roomList.changeFilter()

    def setDefaultResourcesPath(self):
        settings = QSettings('settings.ini', QSettings.IniFormat)
        if not settings.contains("ResourceFolder"):
            settings.setValue("ResourceFolder", self.findResourcePath())
        resPath = settings.value("ResourceFolder")
        resPathDialog = QFileDialog()
        resPathDialog.setFilter(QDir.Hidden)
        newResPath = QFileDialog.getExistingDirectory(self, "Select directory", resPath)

        if newResPath != "":
            settings.setValue("ResourceFolder", newResPath)

    def resetResourcesPath(self):
        settings = QSettings('settings.ini', QSettings.IniFormat)
        settings.remove("ResourceFolder")
        settings.setValue("ResourceFolder", self.findResourcePath())

    def showHooksMenu(self):
        hooks = HooksDialog(self)
        hooks.show()

    def showTestConfigMenu(self):
        testConfig = TestConfigDialog(self)
        testConfig.show()

    def openMapDefault(self):
        if self.checkDirty(): return

        global stageXML
        selectMaps = {}
        for x in stageXML.findall("stage[@BaseGamePath]"):
            selectMaps[x.get('Name')] = x.get('BaseGamePath')

        selectedMap, selectedMapOk = QInputDialog.getItem(self, "Map selection", "Select floor", selectMaps.keys(), 0, False)
        self.restoreEditMenu()

        if not selectedMapOk: return

        mapFileName = selectMaps[selectedMap] + '.stb'
        roomPath = os.path.join(os.path.expanduser(self.findResourcePath()), "rooms", mapFileName)

        if not QFile.exists(roomPath):
            self.setDefaultResourcesPath()
            roomPath = os.path.join(os.path.expanduser(self.findResourcePath()), "rooms", mapFileName)
            if not QFile.exists(roomPath):
                QMessageBox.warning(self, "Error", "Failed opening stage. Make sure that the resources path is set correctly (see File menu) and that the proper STB file is present in the rooms directory.")
                return

        self.openWrapper(roomPath)

    def getRecentFolder(self):
        startPath = ""

        settings = QSettings('settings.ini', QSettings.IniFormat)

        # Get the folder containing the last open file if you can
        # and it's not a default stage
        stagePath = os.path.join(settings.value("ResourceFolder", ''), 'rooms')
        recent = settings.value("RecentFiles", [])
        for recPath in recent:
            lastPath, file = os.path.split(recPath)
            if lastPath != stagePath:
                startPath = lastPath
                break

        # Get the mods folder if you can, no sense looking in rooms for explicit open
        if startPath == "":
            modPath = findModsPath()
            if os.path.isdir(modPath):
                startPath = modPath

        return os.path.expanduser(startPath)

    def updateRecent(self, path):
        recent = settings.value("RecentFiles", [])
        while recent.count(path) > 0:
            recent.remove(path)

        recent.insert(0, path)
        while len(recent) > 10:
            recent.pop()

        settings.setValue("RecentFiles", recent)
        self.setupFileMenuBar()

    def openMap(self):
        if self.checkDirty(): return

        target = QFileDialog.getOpenFileName(
            self, 'Open Map', self.getRecentFolder(), "Stage Binary (*.stb);;TXT File (*.txt)")
        self.restoreEditMenu()

        # Looks like nothing was selected
        if len(target[0]) == 0:
            return

        self.openWrapper(target[0])

    def openRecent(self):
        if self.checkDirty(): return

        path = self.sender().data()
        self.restoreEditMenu()

        self.openWrapper(path)

    def openWrapper(self, path=None):
        print (path)
        self.path = path

        try:
            rooms = self.open()
        except Exception as e:
            rooms = None
            traceback.print_exception(*sys.exc_info())

        if not rooms:
            QMessageBox.warning(self, "Error", "This is not a valid Afterbirth+ STB file. It may be a Rebirth STB, or it may be one of the prototype STB files accidentally included in the AB+ release.")
            return

        self.roomList.list.clear()
        self.scene.clear()
        self.updateTitlebar()

        for room in rooms:
            self.roomList.list.addItem(room)

        self.clean()
        self.roomList.changeFilter()

    def open(self, path=None, addToRecent=True):
        path = path or self.path

        if os.path.splitext(path)[1] == '.txt':
            try:
                return self.openTXT(path)
            except Exception as e:
                traceback.print_exception(*sys.exc_info())
                QMessageBox.warning(self, "Error", "You done goofed.")
                return []

        # Let's read the file and parse it into our list items
        stb = None
        try:
            stb = open(path, 'rb').read()
        except:
            QMessageBox.warning(self, "Error", "Failed opening rooms. The file may not exist.")
            return

        # Header
        try:
            header = struct.unpack_from('<4s', stb, 0)[0].decode()
            if header != "STB1":
                return
        except:
            return

        off = 4

        # Room count
        rooms = struct.unpack_from('<I', stb, off)[0]
        off += 4
        ret = []

        seenSpawns = {}
        for room in range(rooms):

            # Room Type, Room Variant, Subtype, Difficulty, Length of Room Name String
            roomData = struct.unpack_from('<IIIBH', stb, off)
            rtype, rvariant, rsubtype, difficulty, nameLen = roomData
            off += 0xF
            #print ("Room Data: {0}".format(roomData))

            # Room Name
            roomName = struct.unpack_from('<{0}s'.format(nameLen), stb, off)[0].decode()
            off += nameLen
            #print ("Room Name: {0}".format(roomName))

            # Weight, width, height, shape, number of doors, number of entities
            entityTable = struct.unpack_from('<fBBBBH', stb, off)
            rweight, width, height, shape, numDoors, numEnts = entityTable
            off += 0xA
            #print ("Entity Table: {0}".format(entityTable))

            doors = []
            for door in range(numDoors):
                # X, Y, exists
                doorX, doorY, exists = struct.unpack_from('<hh?', stb, off)
                doors.append([ doorX + 1, doorY + 1, exists ])
                off += 5

            def sameDoorLocs(a, b):
                for ad, bd in zip(a, b):
                    if ad[0] != bd[0] or ad[1] != bd[1]:
                        return False
                return True

            roomInfo = Room.Info(rtype, rvariant, rsubtype, shape)
            def getRoomPrefix():
                return Room.getDesc(roomInfo, roomName, difficulty, rweight)

            normalDoors = sorted(roomInfo.shapeData['Doors'], key=Room.DoorSortKey)
            sortedDoors = sorted(doors, key=Room.DoorSortKey)
            if len(normalDoors) != numDoors or not sameDoorLocs(normalDoors, sortedDoors):
                print (f'Invalid doors in room {getRoomPrefix()}: Expected {normalDoors}, Got {sortedDoors}')

            realWidth = roomInfo.dims[0]
            gridLen = roomInfo.gridLen()
            spawns = [ [] for x in range(gridLen) ]
            for entity in range(numEnts):
                # x, y, number of entities at this position
                ex, ey, stackedEnts = struct.unpack_from('<hhB', stb, off)
                ex += 1
                ey += 1
                off += 5

                if not roomInfo.isInBounds(ex, ey):
                    print (f'Found entity with out of bounds spawn loc in room {getRoomPrefix()}: {ex-1}, {ey-1}')

                idx = Room.Info.gridIndex(ex, ey, realWidth)
                if idx >= gridLen:
                    print ('Discarding the current entity due to invalid position!')
                    off += 0xA * stackedEnts
                    continue

                spawnSquare = spawns[idx]

                for spawn in range(stackedEnts):
                    #  type, variant, subtype, weight
                    etype, evariant, esubtype, eweight = struct.unpack_from('<HHHf', stb, off)
                    spawnSquare.append([ etype, evariant, esubtype, eweight ])

                    if (etype, esubtype, evariant) not in seenSpawns:
                        global entityXML
                        en = entityXML.find(f"entity[@ID='{etype}'][@Subtype='{esubtype}'][@Variant='{evariant}']")
                        if en == None or en.get('Invalid') == '1':
                            print(f"Room {getRoomPrefix()} has invalid entity '{en is None and 'UNKNOWN' or en.get('Name')}'! ({etype}.{evariant}.{esubtype})")
                        seenSpawns[(etype, esubtype, evariant)] = en == None or en.get('Invalid') == '1'

                    off += 0xA


            r = Room(roomName, spawns, difficulty, rweight, rtype, rvariant, rsubtype, shape, doors)
            ret.append(r)

        # Update recent files
        if addToRecent:
            self.updateRecent(path)

        return ret

    # HA HA HA FUNNY MODE FUNNY MODE
    def openTXT(self, path=None):
        path = path or self.path

        try:
            text = Path(path).read_text('utf-8')
        except:
            QMessageBox.warning(self, "Error", "Failed opening rooms. The file may not exist.")
            return

        text = text.splitlines()
        numLines = len(text)

        def skipWS(i):
            for j in range(i, numLines):
                if text[j]: return j
            return numLines

        entMap = {}

        # Initial section: entity definitions
        # [Character]=[type].[variant].[subtype]
        # one per line, continues until it hits a line starting with ---
        roomBegin = 0
        for i in range(numLines):
            line = text[i]
            line = re.sub(r'\s', '', line)
            roomBegin = i

            if line.startswith('---'): break
            if not line: continue

            char, t, v, s = re.findall(r'(.)=(\d+).(\d+).(\d+)', line)[0]

            if char in [ '-', '|' ]:
                print("Can't use - or | for entities!")
                continue

            t = int(t)
            v = int(v)
            s = int(s)
            global entityXML
            en = entityXML.find(f"entity[@ID='{t}'][@Subtype='{s}'][@Variant='{v}']")
            if en == None or en.get('Invalid') == '1':
                print(f"Invalid entity for character '{char}': '{en is None and 'UNKNOWN' or en.get('Name')}'! ({t}.{v}.{s})")
                continue

            entMap[char] = (t, v, s, 0)

        shapeNames = {
            '1x1': 1,
            '2x2': 8,
            'closet': 2,
            'vertcloset': 3,
            '1x2': 4,
            'long': 7,
            'longvert': 5,
            '2x1': 6,
            'l': 10,
            'mirrorl': 9,
            'r': 12,
            'mirrorr': 11
        }

        ret = []

        # Main section: room definitions
        # First line: [id]: [name]
        # Second line, in no particular order: [Weight,] [Shape (within tolerance),] [Difficulty,] [Type[=1],] [Subtype[=0],]
        # Next [room height] lines: room layout
        # horizontal walls are indicated with -, vertical with |
        #   there will be no validation for this, but if lines are the wrong length it prints an error message and skips the line
        # coordinates to entities are 1:1, entity ids can be at most 1 char
        # place xs at door positions to turn them off
        roomBegin += 1
        while roomBegin < numLines:
            # 2 lines
            i = skipWS(roomBegin)
            if i == numLines: break

            id, name = text[i].split(':', 1)
            name = name.strip()
            id = int(id)

            infoParts = re.sub(r'\s', '', text[i+1]).lower().split(',')
            shape = 1
            difficulty = 5
            weight = 1
            rtype = 1
            rsubtype = 0
            for part in infoParts:
                prop, val = re.findall(r'(.+)=(.+)', part)[0]
                if prop == 'shape': shape = shapeNames.get(val) or int(val)
                elif prop == 'difficulty': difficulty = shapeNames.get(val) or int(val)
                elif prop == 'weight': weight = float(val)
                elif prop == 'type': rtype = int(val)
                elif prop == 'subtype': rsubtype = int(val)

            r = Room(name, None, difficulty, weight, rtype, id, rsubtype, shape)
            width, height = r.info.dims
            spawns = r.gridSpawns

            i = skipWS(i + 2)
            for j in range(i, i + height):
                if j == numLines:
                    print('Could not finish room!')
                    break

                y = j - i
                row = text[j]
                for x in range(len(row)):
                    char = row[x]
                    if char in [ '-', '|', ' ' ]:
                        continue
                    if char.lower() == 'x':
                        changed = False
                        for door in r.info.doors:
                            if door[0] == x and door[1] == y:
                                door[2] = False
                                changed = True
                        if changed: continue

                    ent = entMap.get(char)
                    if ent:
                        spawns[Room.Info.gridIndex(x,y,width)].append(ent[:])
                    else:
                        print(f"Unknown entity! '{char}'")

            ret.append(r)

            i = skipWS(i + height)
            if i == numLines: break

            if not text[i].strip().startswith('---'):
                print('Could not find separator after room!')
                break

            roomBegin = i + 1

        return ret

    def saveMap(self, forceNewName=False):
        target = self.path

        if target == '' or forceNewName:
            dialogDir = target == '' and self.getRecentFolder() or os.path.dirname(target)
            target, ext = QFileDialog.getSaveFileName(self, 'Save Map', dialogDir, 'Stage Binary (*.stb)')
            self.restoreEditMenu()

            if not target: return

            self.path = target
            self.updateTitlebar()

        try:
            self.save(self.roomList.getRooms())
        except Exception as e:
            traceback.print_exception(*sys.exc_info())
            QMessageBox.warning(self, "Error", "Saving failed. Try saving to a new file instead.")

        self.clean()
        self.roomList.changeFilter()

    def saveMapAs(self):
        self.saveMap(True)

    def save(self, rooms, path=None, updateRecent=True):
        path = path or self.path
        path = os.path.splitext(path)[0] + '.stb'

        self.storeEntityList()

        headerPacker = struct.Struct('<4sI')
        roomBegPacker = struct.Struct('<IIIBH')
        roomEndPacker = struct.Struct('<fBBB')
        doorHeaderPacker = struct.Struct('<BH')
        doorPacker = struct.Struct('<hh?')
        stackPacker = struct.Struct('<hhB')
        entPacker = struct.Struct('<HHHf')

        totalBytes = headerPacker.size
        totalBytes += len(rooms) * (roomBegPacker.size + roomEndPacker.size)
        for room in rooms:
            totalBytes += len(room.data(0x100))
            totalBytes += doorHeaderPacker.size + doorPacker.size * len(room.info.doors)
            totalBytes += room.getSpawnCount() * stackPacker.size
            for stack, x, y in room.spawns():
                totalBytes += len(stack) * entPacker.size

        out = bytearray(totalBytes)
        off = 0
        headerPacker.pack_into(out, off, "STB1".encode(), len(rooms))
        off += headerPacker.size

        for room in rooms:
            width, height = room.info.dims
            roomBegPacker.pack_into(out, off, room.info.type, room.info.variant, room.info.subtype, room.difficulty, len(room.data(0x100)))
            off += roomBegPacker.size
            nameLen = len(room.data(0x100))
            struct.pack_into(f'<{nameLen}s', out, off, room.data(0x100).encode())
            off += nameLen
            roomEndPacker.pack_into(out, off, room.weight, width - 2, height - 2, room.info.shape)
            off += roomEndPacker.size

            # Doors and Entities
            doorHeaderPacker.pack_into(out, off, len(room.info.doors), room.getSpawnCount())
            off += doorHeaderPacker.size

            for door in room.info.doors:
                doorPacker.pack_into(out, off, door[0] - 1, door[1] - 1, door[2])
                off += doorPacker.size

            for stack, x, y in room.spawns():
                numEnts = len(stack)
                stackPacker.pack_into(out, off, x - 1, y - 1, numEnts)
                off += stackPacker.size

                for entity in stack:
                    entPacker.pack_into(out, off, entity[0], entity[1], entity[2], entity[3])
                    off += entPacker.size

        with open(path, 'wb') as stb:
            stb.write(out)

        if updateRecent:
            self.updateRecent(path)

            # if a save doesn't update the recent list, it's probably not a real save
            # so only do hooks in this case
            settings = QSettings('settings.ini', QSettings.IniFormat)
            saveHooks = settings.value('HooksSave')
            if saveHooks:
                stbPath = os.path.abspath(path)
                for hook in saveHooks:
                    path, name = os.path.split(hook)
                    try:
                        subprocess.run([hook, stbPath, '--save'], cwd = path, timeout=60)
                    except Exception as e:
                        print('Save hook failed! Reason:', e)


    def replaceEntities(self, replaced, replacement):
        self.storeEntityList()

        numEnts = 0
        numRooms = 0

        def checkEq(a, b):
            return a[0] == b[0] \
              and (b[1] < 0 or a[1] == b[1]) \
              and (b[2] < 0 or a[2] == b[2])

        def fixEnt(a, b):
            a[0] = b[0]
            if b[1] >= 0: a[1] = b[1]
            if b[2] >= 0: a[2] = b[2]

        for i in range(self.roomList.list.count()):
            currRoom = self.roomList.list.item(i)

            n = 0
            for stack, x, y in currRoom.spawns():
                for ent in stack:
                    if checkEq(ent, replaced):
                        fixEnt(ent, replacement)
                        n += 1


            if n > 0:
                numRooms += 1
                numEnts += n

        room = self.roomList.selectedRoom()
        if room:
            self.handleSelectedRoomChanged(room, None)
            self.scene.update()

        self.dirt()
        QMessageBox.information(None, "Replace",
            numEnts > 0 and f"Replaced {numEnts} entities in {numRooms} rooms"
                        or "No entities to replace!")

    def sortRoomIDs(self):
        self.sortRoomsByKey(lambda x: (x.info.type,x.info.variant))

    def sortRoomNames(self):
        self.sortRoomsByKey(lambda x: (x.info.type,x.data(0x100),x.info.variant))

    def sortRoomsByKey(self, key):
        roomList = self.roomList.list
        selection = roomList.currentItem()
        roomList.setCurrentItem(None, QItemSelectionModel.ClearAndSelect)

        rooms = sorted([ roomList.takeItem(roomList.count() - 1) for x in range(roomList.count()) ], key=key)

        for room in rooms:
            roomList.addItem(room)

        self.dirt()
        roomList.setCurrentItem(selection, QItemSelectionModel.ClearAndSelect)
        roomList.scrollToItem(selection)


    def recomputeRoomIDs(self):
        roomsByType = {}

        roomList = self.roomList.list

        for i in range(roomList.count()):
            room = roomList.item(i)

            if room.info.type not in roomsByType:
                roomsByType[room.info.type] = room.info.variant

            room.info.variant = roomsByType[room.info.type]
            room.setToolTip()

            roomsByType[room.info.type] += 1

        self.dirt()
        self.scene.update()

    #@pyqtSlot()
    def screenshot(self):
        fn = QFileDialog.getSaveFileName(self, 'Choose a new filename', 'untitled.png', 'Portable Network Graphics (*.png)')[0]
        if fn == '': return

        g = settings.value('GridEnabled')
        setttings.setValue('GridEnabled', '0')

        ScreenshotImage = QImage(self.scene.sceneRect().width(), self.scene.sceneRect().height(), QImage.Format_ARGB32)
        ScreenshotImage.fill(Qt.transparent)

        RenderPainter = QPainter(ScreenshotImage)
        self.scene.render(RenderPainter, QRectF(ScreenshotImage.rect()), self.scene.sceneRect())
        RenderPainter.end()

        ScreenshotImage.save(fn, 'PNG', 50)

        setttings.setValue('GridEnabled', g)

    def getTestModPath(self):
        modFolder = findModsPath()
        name = 'basement-renovator-helper'
        return os.path.join(modFolder, name)

    def makeTestMod(self):
        folder = self.getTestModPath()
        roomPath = os.path.join(folder, 'resources', 'rooms')

        if not mainWindow.wroteModFolder and os.path.isdir(folder):
            try:
                shutil.rmtree(folder)
            except Exception as e:
                print('Error clearing old mod data: ', e)

        # delete the old files
        if os.path.isdir(folder):
            dis = os.path.join(folder, 'disable.it')
            if os.path.isfile(dis): os.unlink(dis)

            for f in os.listdir(roomPath):
                f = os.path.join(roomPath, f)
                try:
                    if os.path.isfile(f): os.unlink(f)
                except:
                    pass
        # otherwise, make it fresh
        else:
            try:
                shutil.copytree('./resources/modtemplate', folder)
                os.makedirs(roomPath)
                mainWindow.wroteModFolder = True
            except Exception as e:
                print('Could not copy mod template!', e)
                return '', e

        return folder, roomPath

    def writeTestData(self, folder, testType, floorInfo, testRoom):
        with open(os.path.join(folder, 'roomTest.lua'), 'w') as testData:

            quot = '\\"'
            bs = '\\'
            strFix = lambda x: f'''"{x.replace(bs, bs + bs).replace('"', quot)}"'''

            char = None
            commands = []
            if settings.value('TestConfigDisabled') != '1':
                char = settings.value('TestCharacter')
                if char: char = strFix(char)

                commands = settings.value('TestCommands', [])

            testData.write(f'''return {{
    TestType = {strFix(testType)},
    Character = {char or 'nil'}, -- currently unused due to instapreview limitations
    Commands = {{ {', '.join(map(strFix, commands))} }},
    Stage = {floorInfo.get('Stage')},
    StageType = {floorInfo.get('StageType')},
    StageName = {strFix(floorInfo.get('Name'))},
    IsModStage = {floorInfo.get('BaseGamePath') is None and 'true' or 'false'},
    RoomFile = {strFix(str(Path(self.path)) or 'N/A')},
    Name = {strFix(testRoom.data(0x100))},
    Type = {testRoom.info.type},
    Variant = {testRoom.info.variant},
    Subtype = {testRoom.info.subtype},
    Shape = {testRoom.info.shape}
}}
''')

    def disableTestMod(self, modPath=None):
        modPath = modPath or self.getTestModPath()
        if not os.path.isdir(modPath): return

        with open(os.path.join(modPath, 'disable.it'), 'w'):
            pass

    # Test by replacing the rooms in the relevant floor
    def testMap(self):
        def setup(modPath, roomsPath, floorInfo, room):
            basePath = floorInfo.get('BaseGamePath')
            if basePath is None:
                QMessageBox.warning(self, "Error", "Custom stages cannot be tested with Stage Replacement, since they don't have a room file to replace.")
                raise

            if floorInfo.get('Name') == 'Blue Womb':
                QMessageBox.warning(self, "Error", "Blue Womb cannot be tested with Stage Replacement, since it doesn't have normal room generation.")
                raise

            # Set the selected room to max weight, best spawn difficulty, default type, and enable all the doors
            testRoom = Room(room.data(0x100), room.gridSpawns, 5, 1000.0, 1, room.info.variant, room.info.subtype, room.info.shape)

            # Always pad these rooms
            padMe = testRoom.info.shape in [2, 3, 5, 7]

            # Needs a padded room
            newRooms = [testRoom]
            if padMe:
                newRooms.append(Room(difficulty=10, weight=0.1))

            # Make a new STB with a blank room
            path = os.path.join(roomsPath, basePath + '.stb')
            self.save(newRooms, path, updateRecent=False)

            # Prompt to restore backup
            message = 'This method will not work properly if you have other mods that add rooms to the floor.'
            if padMe:
                message += "\n\nAs the room has a non-standard shape, you may have to reset a few times for your room to appear."

            return [], testRoom, message

        self.testMapCommon('StageReplace', setup)

    # Test by replacing the starting room
    def testStartMap(self):
        def setup(modPath, roomsPath, floorInfo, testRoom):
            # Sanity check for 1x1 room
            if testRoom.info.shape in [2, 7, 9] :
                QMessageBox.warning(self, "Error", "Room shapes 2 and 7 (Long and narrow) and 9 (L shaped with upper right corner missing) can't be tested as the Start Room.")
                raise

            resourcePath = self.findResourcePath()
            if resourcePath == "":
                QMessageBox.warning(self, "Error", "The resources folder could not be found. Please try reselecting it.")
                raise

            roomPath = os.path.join(resourcePath, "rooms", "00.special rooms.stb")

            # Parse the special rooms, replace the spawns
            if not QFile.exists(roomPath):
                QMessageBox.warning(self, "Error", "Missing 00.special rooms.stb from resources. Please unpack your resource files.")
                raise

            startRoom = None
            rooms = self.open(roomPath, False)
            for room in rooms:
                if "Start Room" in room.data(0x100):
                    room.info.shape  = testRoom.info.shape
                    room.gridSpawns = testRoom.gridSpawns
                    startRoom = room
                    break

            if not startRoom:
                QMessageBox.warning(self, "Error", "00.special rooms.stb has been tampered with, and is no longer a valid STB file.")
                raise

            path = os.path.join(roomsPath, "00.special rooms.stb")

            # Resave the file
            self.save(rooms, path, updateRecent=False)

            return [], startRoom, ""

        self.testMapCommon('StartingRoom', setup)

    # Test by launching the game directly into the test room, skipping the menu
    def testMapInstapreview(self):
        def setup(modPath, roomPath, floorInfo, room):
            testfile = "instapreview.xml"
            path = Path(modPath) / testfile
            path = path.resolve()

            self.writeRoomXML(path, room, isPreview = True)

            return [ f"--load-room={path}",
                     f"--set-stage={floorInfo.get('Stage')}",
                     f"--set-stage-type={floorInfo.get('StageType')}" ], None, ""

        self.testMapCommon('InstaPreview', setup)

    def findExecutablePath(self):
        if "Windows" in platform.system():
            installPath = findInstallPath()
            if installPath:
                exeName = "isaac-ng.exe"
                if QFile.exists(os.path.join(installPath, "isaac-ng-rebirth.exe")):
                    exeName = "isaac-ng-rebirth.exe"
                return os.path.join(installPath, exeName)

        return ''

    def findResourcePath(self):

        resourcesPath = ''

        if QFile.exists(settings.value('ResourceFolder')):
            resourcesPath = settings.value('ResourceFolder')

        else:
            installPath = findInstallPath()

            if len(installPath) != 0:
                resourcesPath = os.path.join(installPath, 'resources')
            # Fallback Resource Folder Locating
            else:
                resourcesPathOut = QFileDialog.getExistingDirectory(self, 'Please Locate The Binding of Isaac: Afterbirth+ Resources Folder')
                if not resourcesPathOut:
                    QMessageBox.warning(self, "Error", "Couldn't locate resources folder and no folder was selected.")
                    return
                else:
                    resourcesPath = resourcesPathOut
                if resourcesPath == "":
                    QMessageBox.warning(self, "Error", "Couldn't locate resources folder and no folder was selected.")
                    return
                if not QDir(resourcesPath).exists:
                    QMessageBox.warning(self, "Error", "Selected folder does not exist or is not a folder.")
                    return
                if not QDir(os.path.join(resourcesPath, "rooms")).exists:
                    QMessageBox.warning(self, "Error", "Could not find rooms folder in selected directory.")
                    return

            # Looks like nothing was selected
            if len(resourcesPath) == 0:
                QMessageBox.warning(self, "Error", "Could not find The Binding of Isaac: Afterbirth+ Resources folder (%s)" % resourcesPath)
                return ''

            settings.setValue('ResourceFolder', resourcesPath)

        # Make sure 'rooms' exists
        roomsdir = os.path.join(resourcesPath, "rooms")
        if not QDir(roomsdir).exists:
            os.mkdir(roomsdir)
        return resourcesPath

    def killIsaac(self):
        for p in psutil.process_iter():
            try:
                if 'isaac' in p.name().lower():
                    p.terminate()
            except:
                # This is totally kosher, I'm just avoiding zombies.
                pass

    def writeRoomXML(self, path, room, isPreview = False):
        includeRooms = not isPreview
        with open(path, 'w') as out:
            if includeRooms:
                #out.write('<?xml version="1.0"?>\n<rooms>\n') # TODO restore this when BR has its own xml converter
                out.write('<stage>\n')
            # Room header
            width, height = room.info.dims
            out.write('<room type="%d" variant="%d" subtype="%d" name="%s" difficulty="%d" weight="%g" width="%d" height="%d" shape="%d">\n' % (
                room.info.type, room.info.variant, room.info.subtype, room.data(0x100), room.difficulty,
                room.weight, width - 2, height - 2, room.info.shape
            ))

            # Doors
            for x, y, exists in room.info.doors:
                out.write(f'\t<door x="{x-1}" y="{y-1}" exists="{exists and "True" or "false"}" />\n')

            # Spawns
            for entStack, x, y in room.spawns():
                out.write(f'\t<spawn x="{x-1}" y="{y-1}">\n')
                for t, v, s, weight in entStack:
                    out.write(f'\t\t<entity type="{t}" variant="{v}" subtype="{s}" weight="{weight}" />\n')
                out.write('\t</spawn>\n')

            out.write('</room>\n')
            if includeRooms:
                #out.write('</rooms>\n') # TODO same here
                out.write('</stage>\n')

    def testMapCommon(self, testType, setupFunc):
        room = self.roomList.selectedRoom()
        if not room:
            QMessageBox.warning(self, "Error", "No room was selected to test.")
            return

        # Floor type
        # TODO cache this when loading a file
        global stageXML
        floorInfo = stageXML.find('stage[@Name="Basement"]')
        for stage in stageXML.findall('stage'):
            if stage.get('Pattern') in mainWindow.path:
                floorInfo = stage

        modPath, roomPath = self.makeTestMod()
        if modPath == "":
            QMessageBox.warning(self, "Error", "The basement renovator mod folder could not be copied over: " + str(roomPath))
            return

        # Ensure that the room data is up to date before writing
        self.storeEntityList(room)

        # Call unique code for the test method
        launchArgs, extraMessage = None, None
        try:
            # setup raises an exception if it can't continue
            launchArgs, roomOverride, extraMessage = setupFunc(modPath, roomPath, floorInfo, room) or ([], None, '')
        except Exception as e:
            print('Problem setting up test:', e)
            return

        room = roomOverride or room
        self.writeTestData(modPath, testType, floorInfo, room)

        testfile = 'testroom.xml'
        testPath = Path(modPath) / testfile
        testPath = testPath.resolve()
        self.writeRoomXML(testPath, room)

         # Trigger test hooks
        settings = QSettings('settings.ini', QSettings.IniFormat)
        testHooks = settings.value('HooksTest')
        if testHooks:
            tp = str(testPath)
            for hook in testHooks:
                wd, script = os.path.split(hook)
                try:
                    subprocess.run([hook, tp, '--test'], cwd = wd, timeout=30)
                except Exception as e:
                    print('Test hook failed! Reason:', e)

        # Launch Isaac
        installPath = findInstallPath()
        if not installPath:
            QMessageBox.warning(self, "Error", "Your install path could not be found! You may have the wrong directory, reconfigure in settings.ini")
            return

        try:
            exePath = self.findExecutablePath()
            if exePath and QFile.exists(exePath):
                subprocess.run([exePath] + launchArgs, cwd = installPath)
            else:
                args = ' '.join(map(lambda x: ' ' in x and f'"{x}"' or x, launchArgs))
                urlArgs = urllib.parse.quote(args)
                urlArgs = re.sub(r'/', '%2F', urlArgs)
                webbrowser.open(f'steam://rungameid/250900//{urlArgs}')

        except Exception as e:
            traceback.print_exception(*sys.exc_info())
            QMessageBox.warning(self, "Error", f'Failed to test with {testType}: {e}')
            return

        settings = QSettings('settings.ini', QSettings.IniFormat)
        if settings.value('DisableTestDialog') == '1':
            # disable mod in 5 minutes
            if self.disableTestModTimer: self.disableTestModTimer.disconnect()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.disableTestMod(modPath))
            self.disableTestModTimer = timer
            timer.start(5 * 60 * 1000)

            if extraMessage:
                QMessageBox.information(self, 'BR Test', extraMessage)

        else:
            # Prompt to disable mod and perform cleanup
            # for some reason, if the dialog blocks on the button click,
            # e.g. QMessageBox.information() or msg.exec(), isaac crashes on launch.
            # This is probably a bug in python or Qt
            msg = QMessageBox(QMessageBox.Information,
                'Disable BR', (extraMessage and (extraMessage + '\n\n') or '') +
                'Press "OK" when done testing to disable the BR helper mod.'
                , QMessageBox.Ok, self)

            def fin(button):
                result = msg.standardButton(button)
                if result == QMessageBox.Ok:
                    self.disableTestMod(modPath)

                self.killIsaac()

            msg.buttonClicked.connect(fin)
            msg.open()

# Edit
########################

    #@pyqtSlot()
    def selectAll(self):

        path = QPainterPath()
        path.addRect(self.scene.sceneRect())
        self.scene.setSelectionArea(path)

    #@pyqtSlot()
    def deSelect(self):
        self.scene.clearSelection()

    #@pyqtSlot()
    def copy(self):
        self.clipboard = []
        for item in self.scene.selectedItems():
            self.clipboard.append([item.entity.x, item.entity.y, item.entity.Type, item.entity.Variant, item.entity.Subtype, item.entity.weight])

    #@pyqtSlot()
    def cut(self):
        self.clipboard = []
        for item in self.scene.selectedItems():
            self.clipboard.append([item.entity.x, item.entity.y, item.entity.Type, item.entity.Variant, item.entity.Subtype, item.entity.weight])
            item.remove()

    #@pyqtSlot()
    def paste(self):
        if not self.clipboard: return

        self.scene.clearSelection()
        for item in self.clipboard:
            ent = Entity(*item)
            ent.setSelected(True)
            self.scene.addItem(ent)

        self.dirt()

    def showReplaceDialog(self):
        replaceDialog = ReplaceDialog()
        if replaceDialog.exec() != QDialog.Accepted: return

        self.replaceEntities(replaceDialog.fromEnt.getEnt(), replaceDialog.toEnt.getEnt())

# Miscellaneous
########################

    def toggleSetting(self, setting, onDefault=False):
        settings = QSettings('settings.ini', QSettings.IniFormat)
        a, b = onDefault and ('0','1') or ('1','0')
        settings.setValue(setting, settings.value(setting) == a and b or a)
        self.scene.update()


    #@pyqtSlot()
    def showPainter(self):
        if self.EntityPaletteDock.isVisible():
            self.EntityPaletteDock.hide()
        else:
            self.EntityPaletteDock.show()

        self.updateDockVisibility()

    #@pyqtSlot()
    def showRoomList(self):
        if self.roomListDock.isVisible():
            self.roomListDock.hide()
        else:
            self.roomListDock.show()

        self.updateDockVisibility()

    #@pyqtSlot()
    def updateDockVisibility(self):

        if self.EntityPaletteDock.isVisible():
            self.wb.setText('Hide Entity Painter')
        else:
            self.wb.setText('Show Entity Painter')

        if self.roomListDock.isVisible():
            self.wc.setText('Hide Room List')
        else:
            self.wc.setText('Show Room List')

    #@pyqtSlot()
    def resetWindowDefaults(self):
        self.restoreState(self.resetWindow["state"], 0)
        self.restoreGeometry(self.resetWindow["geometry"])

# Help
########################

    #@pyqtSlot(bool)
    def aboutDialog(self):
        caption = "About the Basement Renovator"

        text = "<big><b>Basement Renovator</b></big><br><br>    The Basement Renovator Editor is an editor for custom rooms, for use with the Binding of Isaac Afterbirth. In order to use it, you must have unpacked the .stb files from Binding of Isaac Afterbirth.<br><br>    The Basement Renovator was programmed by Tempus (u/Chronometrics).<br><br>    Find the source on <a href='https://github.com/Tempus/Basement-Renovator'>github</a>."

        msg = QMessageBox.about(mainWindow, caption, text)

    #@pyqtSlot(bool)
    def goToHelp(self):
        QDesktopServices().openUrl(QUrl('http://www.reddit.com/r/themoddingofisaac'))


if __name__ == '__main__':

    import sys

    # Application
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('resources/UI/BasementRenovator.png'))

    cmdParser = QCommandLineParser()
    cmdParser.setApplicationDescription('Basement Renovator is a room editor for The Binding of Isaac: Afterbirth[+]')
    cmdParser.addHelpOption()

    cmdParser.addPositionalArgument('file', 'optional file to open on launch, otherwise opens most recent file')

    cmdParser.process(app)

    settings = QSettings('settings.ini', QSettings.IniFormat)

    # XML Globals
    entityXML = getEntityXML()
    stageXML = getStageXML()
    if settings.value('DisableMods') != '1':
        loadMods(settings.value('ModAutogen') == '1', findInstallPath(), settings.value('ResourceFolder', ''))

    print('-'.join([ '' for i in range(50) ]))
    print('INITIALIZING MAIN WINDOW')
    mainWindow = MainWindow()

    settings.setValue('FixIconFormat', '0')

    startFile = None

    args = cmdParser.positionalArguments()
    if args:
        startFile = args[0]
    else:
        recent = settings.value("RecentFiles", [])
        if recent:
            startFile = recent[0]

    if startFile and os.path.exists(startFile):
        mainWindow.openWrapper(startFile)

    mainWindow.show()

    sys.exit(app.exec())
