import datetime

import config
import util

import os.path
import sys
import re
import shutil
from subprocess import Popen, PIPE

import ffmpeg
import uuid

import requests
import yt_dlp
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRunnable, pyqtSlot, QThreadPool, QSize
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import QAbstractItemView, QMessageBox, QFileDialog, QProgressBar, QLabel, QSizePolicy

from seleniumwire import webdriver
from sys import platform
from pathlib import Path

# Config
# Selenium Version 3.4.1
VERSION = "1.0.0"

app = QtWidgets.QApplication(sys.argv)
driverType = None
headermap = {}


def getHeaders(url):
    try:
        return headermap[url]
    except Exception:
        return None


def writeHeaders(headers, url):
    with open("headers.py", 'w') as file:
        file.write("import requests\n")
        file.write("headers = {\n")
        file.write(headers)
        file.write("\n}\n")
        file.write(f"response = requests.post('{url}', headers=headers)\n")


def getKeys(self, pssh, lic_url):
    import headers
    from data.pywidevine.L3.cdm import deviceconfig
    from base64 import b64encode
    from data.pywidevine.L3.decrypt.wvdecryptcustom import WvDecrypt
    try:
        wvdecrypt = WvDecrypt(init_data_b64=pssh, cert_data_b64=None, device=deviceconfig.device_android_generic)
        widevine_license = requests.post(url=lic_url, data=wvdecrypt.get_challenge(), headers=headers.headers)
        license_b64 = b64encode(widevine_license.content)
        wvdecrypt.update_license(license_b64)
        correct, keyswvdecrypt = wvdecrypt.start_process()
        return correct, keyswvdecrypt
    except Exception as ex:
        errorDialog(self, f"Unable to obtain decryption keys:\n{ex}")
        return False, None


def checkcdm(self) -> bool:
    path = "data/pywidevine/L3/cdm/devices/android_generic/"
    if not os.path.exists(path + "device_client_id_blob") or not os.path.exists(path + "device_private_key"):
        errorDialog(self, 'No Content Decryption Module found.\n'
                          'Please select the following\n'
                          'files in the Settings Menu:\n'
                          'device_client_id_blob, device_private_key')
        return False
    else:
        return True


def errorDialog(self, desc):
    QMessageBox.critical(
        self,
        "MPDL/Error",
        desc,
        buttons=QMessageBox.Ok,
        defaultButton=QMessageBox.Ok,
    )


def getMp4Decrypt() -> str:
    c = config.parser
    mp4decrypt = "mp4decrypt"
    if not c.getboolean("MAIN", "mp4decryptfrompath"):
        mp4decrypt = c.get("MAIN", "mp4decryptpath")
    return mp4decrypt


class Signals(QObject):
    started = pyqtSignal(list)
    completed = pyqtSignal(str)
    progress = pyqtSignal(list)
    error = pyqtSignal(str)


class BrowserSignals(QObject):
    started = pyqtSignal()
    ended = pyqtSignal()
    links = pyqtSignal(list)
    error = pyqtSignal(str)


class Worker(QRunnable):
    def __init__(self, link, pssh, lic, uuid, sniffer):
        super().__init__()
        self.sniffer = sniffer
        self.keys = None
        self.link = link
        self.pssh = pssh
        self.lic = lic
        self.uuid = uuid
        self.videosize = ''
        self.audiosize = ''
        self.signals = Signals()
        self.typ = 'video'
        self.src = [None, None]

    @pyqtSlot()
    def run(self):
        def log(d):
            status = None
            if 'status' in d:
                statusT = d['status']
                if statusT is not None:
                    status = statusT

            name = None
            if 'filename' in d:
                nameT = d['filename']
                if nameT is not None:
                    name = nameT

            perc = '0'
            if 'total_bytes_estimate' in d and 'downloaded_bytes' in d:
                tbeT, tbT = d['total_bytes_estimate'], d['downloaded_bytes']
                if tbeT is not None and tbT is not None:
                    perc = str(tbT / tbeT * 100)

            size = '0'
            if 'total_bytes_estimate' in d:
                tbeT = d['total_bytes_estimate']
                if tbeT is not None:
                    size = str(int(tbeT / 1000000))

            eta = 'N/A'
            if 'eta' in d:
                etaT = d['eta']
                if etaT is not None:
                    m, s = divmod(etaT, 60)
                    h, m = divmod(m, 60)
                    eta = ('{}h {}m {}s'.format(int(h), int(m), int(s)))

            speed = '0.0'
            if 'speed' in d:
                sT = d['speed']
                if sT is not None:
                    speed = str(int(sT / 1000))

            if perc == '0' and status == 'finished':
                to = self.uuid + "." + self.typ + "." + name.split(".")[len(name.split(".")) - 1]
                try:
                    os.replace(name, to)
                except Exception as ex:
                    self.signals.error.emit(str(ex))
                if self.typ == 'video':
                    self.src[0] = to
                    self.videosize = size
                elif self.typ == 'audio':
                    self.src[1] = to
                    self.audiosize = size
                self.typ = 'audio'
            self.signals.progress.emit(
                [self.uuid, f"{status.capitalize()} ({self.typ.capitalize()})", size + " MB", perc, eta,
                 speed + " KB/s", self.link])

        try:
            self.signals.started.emit([self.uuid, self.link])

            # get keys
            self.signals.progress.emit(
                [self.uuid, f"Obtaining Keys", '', '0', '', '', self.link])
            writeHeaders(getHeaders(self.link), self.link)
            correct, self.keys = getKeys(self.sniffer, self.pssh, self.lic)
            if not correct or self.keys is None:
                self.signals.error.emit("Unable to obtain decryption keys.")
                return
            self.signals.progress.emit(
                [self.uuid, f"Obtaining Keys", '', '100', '', '', self.link])

            # download data
            ydl_opts = {
                'allow_unplayable_formats': True,
                'noprogress': True,
                'quiet': True,
                'fixup': 'never',
                'format': 'bv,ba',
                'no_warnings': True,
                'outtmpl': {'default': self.uuid + '.f%(format_id)s.%(ext)s'},
                'progress_hooks': [log]
            }
            yt_dlp.YoutubeDL(ydl_opts).download(self.link)

            # decrypt
            for i in range(len(self.src)):
                s = self.src[i]
                if s is not None:
                    size = self.videosize
                    typ = 'video'
                    if i == 1:
                        size = self.audiosize
                        typ = 'audio'
                    out = self.uuid + "." + typ + "_decrypted." + s.split(".")[len(s.split(".")) - 1]
                    self.signals.progress.emit(
                        [self.uuid, f"Decrypting ({typ.capitalize()})", size + " MB", '0', '', '', self.link])
                    command = getMp4Decrypt() + " --key " + " --key ".join(self.keys) + ' ' + s + ' ' + out
                    process = Popen(command, stdout=PIPE, stderr=PIPE)
                    stdout, stderr = process.communicate()
                    self.signals.progress.emit(
                        [self.uuid, f"Decrypting ({typ.capitalize()})", size + " MB", '100', '', '', self.link])
                    if stderr.decode('utf-8'):
                        errorDialog(self.sniffer, "Failed decrypting " + s + ": " + stderr.decode('utf-8'))
                        return
                    self.src[i] = out
                    if os.path.exists(s):
                        os.remove(s)

            # combine
            totalsize = str(int(float(self.videosize) + float(self.audiosize)))
            self.signals.progress.emit(
                [self.uuid, f"Combining", totalsize + " MB", '0', '', '', self.link])
            t = datetime.datetime.now()
            out = (self.uuid + '.{}-{}-{}_{}-{}-{}'.format(t.day, t.month, t.year, t.hour, t.minute, t.second) + '.mkv')
            if len(self.src) == 2:
                v = ffmpeg.input(self.src[0])
                a = ffmpeg.input(self.src[1])
                c = config.parser
                if not c.getboolean("MAIN", "ffmpegfrompath"):
                    ffmpeg.output(v, a, out, vcodec='copy', acodec='copy').run(quiet=True, overwrite_output=True, cmd=c.get("MAIN", "ffmpegpath"))
                else:
                    ffmpeg.output(v, a, out, vcodec='copy', acodec='copy').run(quiet=True, overwrite_output=True)
                if os.path.exists(self.src[0]):
                    os.remove(self.src[0])
                if os.path.exists(self.src[1]):
                    os.remove(self.src[1])
            self.signals.progress.emit(
                [self.uuid, f"Combining", totalsize + " MB", '100', '', '', self.link])
            #time.sleep(1)
            self.signals.progress.emit(
                [self.uuid, f"Finished", totalsize + " MB", '100', '', '', self.link])
            if config.parser.getboolean("MAIN", "downloadfrompath"):
                shutil.copy(out, config.parser.get("MAIN", "downloadpath"))
            self.signals.completed.emit(self.uuid)
        except Exception as ex:
            self.signals.error.emit(str(ex))


def close(self):
    self.setWindowTitle("MPDL/Main - Closing ...")
    self.hide()
    self.sniffer.hide()
    self.downloads.hide()
    app.closeAllWindows()
    try:
        if driverType is not None:
            driverType.quit()
    except Exception:
        pass
    sys.exit(0)


class Browser(QRunnable):

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.signals = BrowserSignals()

    @pyqtSlot()
    def run(self):
        options = webdriver.FirefoxOptions()
        if config.parser.getboolean("BROWSER", "drmenabled"):
            profile = webdriver.FirefoxProfile('data/firefox')
        else:
            profile = webdriver.FirefoxProfile()
        options.profile = profile
        driver = webdriver.Firefox(options=options)
        for addon in util.getAddons(config.parser):
            try:
                driver.install_addon(addon, temporary=True)
            except Exception as ex:
                self.signals.error.emit(f"Unable to install addon:\n{addon}\nCheck the Addons section in Settings for "
                                        f"incorrect paths.\n\n{str(ex)}")
                driver.close()
                self.signals.ended.emit()
                return
        driver.get(config.parser.get("BROWSER", "startpage"))
        global driverType
        driverType = driver
        logs = []
        curr = ''
        self.signals.started.emit()
        while True:
            try:
                driver.window_handles
            except Exception:
                self.signals.ended.emit()
                break
            try:
                if curr != driver.current_url:
                    logs = []
                    curr = driver.current_url
                log = driver.requests
                for x in log:
                    if x.url not in logs:
                        logs.append(x.url)
                        headermap[str(x.url)] = util.formatCURL(str(x.headers))
                        if x.url.startswith('http') and len(re.findall("mpd|manifest|ism", x.url)) >= 1:
                            self.signals.links.emit([0, x.url])
                        # elif x.url.startswith('http') and len(re.findall("license|widevine|cenc|pssh|bitmovin", x.url)) >= 1:
                        elif x.method == 'POST':
                            self.signals.links.emit([1, x.url])
            except Exception:
                pass


class About(QtWidgets.QWidget):

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setWindowTitle("MPDL/About")
        self.resize(380, 120)
        self.setFixedSize(380, 120)
        self.setWindowIcon(util.getIcon())

        self.image = QLabel(self)
        self.image.setPixmap(QPixmap("icon.png"))
        self.image.setGeometry(10, 10, 100, 100)
        self.image.setScaledContents(True)
        self.image.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.image.show()

        self.label = QLabel("MPDL", self)
        self.label.setGeometry(QtCore.QRect(127, 10, 150, 40))
        self.label.setFont(util.getFont(36, True, True))

        self.version = QLabel("v" + VERSION, self)
        self.version.setGeometry(QtCore.QRect(130, 39, 150, 40))

        self.description = QLabel("MPD Downloader for DRM Protected content.\ngithub.com/DevLARLEY/mpdl", self)
        self.description.setGeometry(QtCore.QRect(130, 40, 370, 100))

    def closeEvent(self, event):
        self.main.pushButton_5.setEnabled(True)


class Settings(QtWidgets.QWidget):

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setWindowTitle("MPDL/Settings")
        self.resize(440, 323)
        self.setFixedSize(440, 323)
        self.setWindowIcon(util.getIcon())

        self.label = QtWidgets.QLabel("Settings", self)
        self.label.setGeometry(QtCore.QRect(20, 10, 151, 31))
        self.label.setFont(util.getFont(17, False, True))

        self.okbutton = QtWidgets.QPushButton("Apply", self)
        self.okbutton.setGeometry(QtCore.QRect(355, 14, 75, 31))
        self.okbutton.clicked.connect(self.okbuttonclicked)

        self.listWidget = QtWidgets.QListWidget(self)
        self.listWidget.setGeometry(QtCore.QRect(10, 54, 80, 260))
        item = QtWidgets.QListWidgetItem("Main")
        item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
        self.listWidget.addItem(item)
        item = QtWidgets.QListWidgetItem("Browser")
        self.listWidget.addItem(item)
        self.listWidget.itemSelectionChanged.connect(self.itemselection)

        # Main
        self.groupBox_3 = QtWidgets.QGroupBox("External Programs", self)
        self.groupBox_3.setGeometry(QtCore.QRect(100, 135, 330, 180))

        self.groupBox = QtWidgets.QGroupBox("ffmpeg", self.groupBox_3)
        self.groupBox.setGeometry(QtCore.QRect(10, 20, 310, 71))

        self.radioButton = QtWidgets.QRadioButton("From PATH", self.groupBox)
        self.radioButton.setGeometry(QtCore.QRect(10, 20, 82, 17))
        self.radioButton.setChecked(True)

        self.radioButton_2 = QtWidgets.QRadioButton("", self.groupBox)
        self.radioButton_2.setGeometry(QtCore.QRect(10, 42, 82, 17))

        self.textEdit = QtWidgets.QLineEdit(self.groupBox)
        self.textEdit.setGeometry(QtCore.QRect(30, 40, 221, 21))

        self.toolButton = QtWidgets.QToolButton(self.groupBox)
        self.toolButton.setGeometry(QtCore.QRect(254, 42, 25, 19))
        self.toolButton.setText("...")
        self.toolButton.clicked.connect(self.chooseffmpeg)

        self.groupBox_2 = QtWidgets.QGroupBox("mp4decrypt", self.groupBox_3)
        self.groupBox_2.setGeometry(QtCore.QRect(10, 100, 310, 71))

        self.radioButton_3 = QtWidgets.QRadioButton("From PATH", self.groupBox_2)
        self.radioButton_3.setGeometry(QtCore.QRect(10, 20, 82, 17))
        self.radioButton_3.setChecked(True)

        self.radioButton_4 = QtWidgets.QRadioButton("", self.groupBox_2)
        self.radioButton_4.setGeometry(QtCore.QRect(10, 42, 82, 17))

        self.textEdit_2 = QtWidgets.QLineEdit(self.groupBox_2)
        self.textEdit_2.setGeometry(QtCore.QRect(30, 40, 221, 21))

        self.toolButton_2 = QtWidgets.QToolButton(self.groupBox_2)
        self.toolButton_2.setGeometry(QtCore.QRect(254, 42, 25, 19))
        self.toolButton_2.setText("...")
        self.toolButton_2.clicked.connect(self.choosemp4decrypt)

        self.groupBox_4 = QtWidgets.QGroupBox("General", self)
        self.groupBox_4.setGeometry(QtCore.QRect(100, 50, 330, 78))

        self.groupBox_7 = QtWidgets.QGroupBox(" "*39, self.groupBox_4)
        self.groupBox_7.setGeometry(QtCore.QRect(10, 20, 200, 50))

        self.groupBox_8 = QtWidgets.QGroupBox("CDM", self.groupBox_4)
        self.groupBox_8.setGeometry(QtCore.QRect(220, 20, 100, 50))

        self.downloadpathenabled = QtWidgets.QCheckBox("Download Directory", self.groupBox_7)
        self.downloadpathenabled.setGeometry(QtCore.QRect(12, -3, 200, 20))
        self.downloadpathenabled.clicked.connect(self.enableDownloadDirectory)

        self.downloadpath = QtWidgets.QLineEdit(self.groupBox_7)
        self.downloadpath.setGeometry(QtCore.QRect(10, 20, 150, 21))

        self.toolButton_4 = QtWidgets.QToolButton(self.groupBox_7)
        self.toolButton_4.setGeometry(QtCore.QRect(165, 22, 25, 19))
        self.toolButton_4.setText("...")
        self.toolButton_4.clicked.connect(self.chooseOutputDirectory)

        self.toolButton_3 = QtWidgets.QPushButton(self.groupBox_8)
        self.toolButton_3.setGeometry(QtCore.QRect(10, 18, 80, 23))
        self.toolButton_3.setText("Select")
        self.toolButton_3.clicked.connect(self.choosecdm)

        # Browser
        self.groupBox_5 = QtWidgets.QGroupBox("General", self)
        self.groupBox_5.setGeometry(QtCore.QRect(100, 50, 330, 265))

        self.label_3 = QtWidgets.QLabel("Start Page (Full Link):", self.groupBox_5)
        self.label_3.setGeometry(QtCore.QRect(17, 20, 120, 16))

        self.textEdit_3 = QtWidgets.QLineEdit(self.groupBox_5)
        self.textEdit_3.setGeometry(QtCore.QRect(12, 40, 301, 20))
        self.textEdit_3.setText("https://duckduckgo.com/")

        self.groupBox_6 = QtWidgets.QGroupBox("Addons", self.groupBox_5)
        self.groupBox_6.setGeometry(QtCore.QRect(10, 100, 311, 156))

        self.listWidget_2 = QtWidgets.QListWidget(self.groupBox_6)
        self.listWidget_2.setGeometry(QtCore.QRect(10, 50, 291, 97))

        self.pushButton = QtWidgets.QPushButton("+", self.groupBox_6)
        self.pushButton.setGeometry(QtCore.QRect(10, 20, 23, 23))
        self.pushButton.clicked.connect(self.addAddon)

        self.pushButton_2 = QtWidgets.QPushButton("-", self.groupBox_6)
        self.pushButton_2.setGeometry(QtCore.QRect(40, 20, 23, 23))
        self.pushButton_2.clicked.connect(self.removeAddon)

        self.checkBox_2 = QtWidgets.QCheckBox("Enable DRM", self.groupBox_5)
        self.checkBox_2.setGeometry(QtCore.QRect(16, 70, 81, 17))
        self.checkBox_2.setChecked(True)

        c = config.parser
        # Main
        self.downloadpath.setText(c.get("MAIN", "downloadpath"))
        self.downloadpath.setEnabled(c.getboolean("MAIN", "downloadfrompath"))
        self.toolButton_4.setEnabled(c.getboolean("MAIN", "downloadfrompath"))
        self.downloadpathenabled.setChecked(c.getboolean("MAIN", "downloadfrompath"))
        self.radioButton.setChecked(c.getboolean("MAIN", "ffmpegfrompath"))
        self.radioButton_2.setChecked(not c.getboolean("MAIN", "ffmpegfrompath"))
        self.textEdit.setText(c.get("MAIN", "ffmpegpath"))
        self.radioButton_3.setChecked(c.getboolean("MAIN", "mp4decryptfrompath"))
        self.radioButton_4.setChecked(not c.getboolean("MAIN", "mp4decryptfrompath"))
        self.textEdit_2.setText(c.get("MAIN", "mp4decryptpath"))
        if c.getboolean("MAIN", "cdmselected"):
            self.toolButton_3.setText("Change")
        else:
            self.toolButton_3.setText("Select")
        # Browser
        self.textEdit_3.setText(c.get("BROWSER", "startpage"))
        self.checkBox_2.setChecked(c.getboolean("BROWSER", "drmenabled"))
        self.listWidget_2.addItems(util.getAddons(c))

    def enableDownloadDirectory(self):
        self.downloadpath.setEnabled(self.downloadpathenabled.isChecked())
        self.toolButton_4.setEnabled(self.downloadpathenabled.isChecked())

    def removeAddon(self):
        self.listWidget_2.takeItem(self.listWidget_2.currentRow())

    def addAddon(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Add Addon(s):")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setDirectory(str(Path.home()).replace("\\", "/"))
        if dialog.exec_():
            selected = dialog.selectedFiles()
            if len(selected) > 0:
                self.listWidget_2.addItems(selected)
            else:
                errorDialog(self, "At least one file must be selected.")

    def chooseOutputDirectory(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select output directory:")
        dialog.setFileMode(QFileDialog.FileMode.DirectoryOnly)
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setDirectory(str(Path.home()).replace("\\", "/"))
        if dialog.exec_():
            selected = dialog.selectedFiles()
            if len(selected) == 1:
                self.downloadpath.setText(selected[0].replace("\\", "/"))
            else:
                errorDialog(self, "Only one directory can be selected.")

    def chooseffmpeg(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select ffmpeg:")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setDirectory(str(Path.home()).replace("\\", "/"))
        if dialog.exec_():
            selected = dialog.selectedFiles()
            if len(selected) == 1:
                self.textEdit.setText(selected[0].replace("\\", "/"))
                self.radioButton.setChecked(False)
                self.radioButton_2.setChecked(True)
            else:
                errorDialog(self, "Only one file can be selected.")

    def choosemp4decrypt(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select mp4decrypt:")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setDirectory(str(Path.home()).replace("\\", "/"))
        if dialog.exec_():
            selected = dialog.selectedFiles()
            if len(selected) == 1:
                self.textEdit_2.setText(selected[0].replace("\\", "/"))
                self.radioButton_3.setChecked(False)
                self.radioButton_4.setChecked(True)
            else:
                errorDialog(self, "Only one file can be selected.")

    def choosecdm(self):
        path = "data/pywidevine/L3/cdm/devices/android_generic/"
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select Content Decryption Module:")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setViewMode(QFileDialog.Detail)
        dialog.setDirectory(str(Path.home()).replace("\\", "/"))
        if dialog.exec_():
            selected = dialog.selectedFiles()
            if len(selected) == 2:
                if any("device_client_id_blob" in item for item in selected) and any(
                        "device_private_key" in item for item in selected):
                    shutil.copy(selected[0], path)
                    shutil.copy(selected[1], path)
                    self.toolButton_3.setText("Change")
                else:
                    errorDialog(self, "Invalid file names.")
            else:
                errorDialog(self, "Please select two files.")

    def okbuttonclicked(self):
        c = config.parser
        if not os.path.isfile(self.textEdit.text()) and self.radioButton_2.isChecked():
            errorDialog(self, "ffmpeg path is invalid.")
            return
        if not os.path.isfile(self.textEdit_2.text()) and self.radioButton_4.isChecked():
            errorDialog(self, "mp4decrypt path is invalid.")
            return
        if not self.textEdit_3.text().startswith("http"):
            errorDialog(self, "A full link starting with 'http' must be provided.")
            return
        c["MAIN"]["downloadpath"] = self.downloadpath.text()
        c["MAIN"]["downloadfrompath"] = str(self.downloadpathenabled.isChecked())
        c["MAIN"]["ffmpegfrompath"] = str(self.radioButton.isChecked())
        c["MAIN"]["ffmpegpath"] = self.textEdit.text()
        c["MAIN"]["mp4decryptfrompath"] = str(self.radioButton_3.isChecked())
        c["MAIN"]["mp4decryptpath"] = self.textEdit_2.text()
        c["MAIN"]["cdmselected"] = str(self.toolButton_3.text() == "Change")

        c["BROWSER"]["startpage"] = self.textEdit_3.text()
        c["BROWSER"]["drmenabled"] = str(self.checkBox_2.isChecked())
        c["BROWSER"]["addons"] = util.setAddons(self.listWidget_2)
        config.writeConfig()
        QMessageBox.information(self, "MPDL/Settings", "Settings saved successfully.")

    def itemselection(self):
        i = self.listWidget.selectedIndexes()[0].row()
        if i == 0:
            self.groupBox.show()
            self.groupBox_2.show()
            self.groupBox_3.show()
            self.groupBox_4.show()
            self.groupBox_7.show()
            self.groupBox_8.show()
            self.groupBox_5.hide()
            self.groupBox_6.hide()
        elif i == 1:
            self.groupBox.hide()
            self.groupBox_2.hide()
            self.groupBox_3.hide()
            self.groupBox_4.hide()
            self.groupBox_7.hide()
            self.groupBox_8.hide()
            self.groupBox_5.show()
            self.groupBox_6.show()

    def closeEvent(self, event):
        self.main.pushButton_4.setEnabled(True)


class Downloads(QtWidgets.QWidget):

    def getText(self, text):
        return QtWidgets.QLabel(text)

    def getLine(self):
        line = QtWidgets.QFrame(self)
        line.setFrameShape(QtWidgets.QFrame.VLine)
        return line

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setWindowTitle("MPDL/Downloads")
        self.resize(700, 300)
        self.setFixedSize(700, 300)
        self.setWindowIcon(util.getIcon())
        self.label = QtWidgets.QLabel("Downloads", self)
        self.label.setGeometry(QtCore.QRect(20, 10, 151, 31))
        self.label.setFont(util.getFont(17, False, True))
        self.table = QtWidgets.QTableWidget(self)
        self.table.setGeometry(QtCore.QRect(10, 50, 680, 240))
        self.table.setColumnCount(7)
        arr = {"UUID": "0", "Status": "1", "Size": "2", "Progress": "3", "ETA": "4", "Speed": "5", "URL": "6"}
        self.table.setHorizontalHeaderLabels(arr.keys())
        self.table.setEditTriggers(self.table.NoEditTriggers)

    def closeEvent(self, event):
        self.main.pushButton_3.setEnabled(True)


class Sniffer(QtWidgets.QWidget):

    def hanldebutton(self):
        i = self.main.sniffer.combobox.currentIndex()
        if i == 0:
            if len(self.listView.selectedItems()) >= 1:
                mpd = self.listView.selectedItems()[0].text()
                fin = ''
                correct, pssh = util.getPSSH(mpd)
                if correct and pssh != '':
                    fin = pssh
                else:
                    pssh = util.getPSSH2(mpd)
                    if pssh:
                        fin = pssh
                if fin == '':
                    QMessageBox.information(
                        self,
                        "MPDL/Information",
                        "No PSSH found in URL.",
                        buttons=QMessageBox.Ok,
                        defaultButton=QMessageBox.Ok,
                    )
                else:
                    lic = ''
                    for item in [self.listView2.item(x) for x in range(self.listView2.count())]:
                        if item.font().bold():
                            lic = item.text()
                    if lic == '':
                        ok = QMessageBox.question(
                            self,
                            "MPDL/Information",
                            "No License URL selected.\nDo you wish to continue?",
                            buttons=QMessageBox.Yes | QMessageBox.No,
                            defaultButton=QMessageBox.Yes,
                        )
                        if ok != QMessageBox.Yes:
                            return  # TODO if yes was chosen, don't decrypt
                    #print("Found PSSH => " + fin)
                    #print("License URL => " + lic)
                    #print("Headers => \n" + getHeaders(mpd))

                    self.listView.selectedItems()[0].setForeground(Qt.lightGray)

                    pool = QThreadPool.globalInstance()
                    worker = Worker(mpd, fin, lic, str(uuid.uuid4()), self)
                    worker.signals.completed.connect(self.main.complete)
                    worker.signals.started.connect(self.main.start)
                    worker.signals.progress.connect(self.main.progress)
                    worker.signals.error.connect(self.main.error)
                    pool.start(worker)
        elif i == 1:
            if len(self.listView2.selectedIndexes()) >= 1:
                font2 = QFont()
                font2.setBold(False)
                for item in [self.listView2.item(x) for x in range(self.listView2.count())]:
                    item.setFont(font2)
                font = QFont()
                font.setBold(True)
                self.listView2.selectedItems()[0].setFont(font)

    def clearListView(self):
        i = self.main.sniffer.combobox.currentIndex()
        if i == 0:
            self.main.sniffer.listView.clear()
        elif i == 1:
            self.main.sniffer.listView2.clear()

    def combobox_change(self, index):
        if index == 0:
            self.listView.setVisible(True)
            self.listView2.setVisible(False)
            self.pushButton.setText("Download")
        elif index == 1:
            self.listView.setVisible(False)
            self.listView2.setVisible(True)
            self.pushButton.setText("Select")

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setWindowTitle("MPDL/URL Sniffer")
        self.resize(700, 300)
        self.setFixedSize(700, 300)
        self.setWindowIcon(util.getIcon())
        self.listView = QtWidgets.QListWidget(self)
        self.listView.setGeometry(QtCore.QRect(10, 50, 680, 240))
        self.listView.setDragEnabled(False)
        self.listView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.listView.setVisible(True)
        self.listView2 = QtWidgets.QListWidget(self)
        self.listView2.setGeometry(QtCore.QRect(10, 50, 680, 240))
        self.listView2.setDragEnabled(False)
        self.listView2.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.listView2.setVisible(False)
        self.combobox = QtWidgets.QComboBox(self)
        self.combobox.setGeometry(QtCore.QRect(455, 13, 92, 29))
        self.combobox.addItems(["MPD URLs", "License URLs"])
        if platform == "win32":
            self.combobox.setStyleSheet("QComboBox::drop-down {"
                                        "image: url(data/drop.png);"
                                        "margin-right: 6px;"
                                        "margin-top: 11px;"
                                        "}"
                                        "QComboBox {"
                                        "border-radius: 4px;"
                                        "border: 1px solid #d2d2d2;"
                                        "padding-left: 7px"
                                        "}"
                                        "QComboBox::hover {"
                                        "border-radius: 4px;"
                                        "border: 1px solid #0078d4;"
                                        "background-color: #e0eef9;"
                                        "padding-left: 7px"
                                        "}")
        self.combobox.currentIndexChanged.connect(self.combobox_change)
        self.label = QtWidgets.QLabel("URL Sniffer", self)
        self.label.setGeometry(QtCore.QRect(20, 10, 151, 31))
        self.label.setFont(util.getFont(17, False, True))
        self.pushButton = QtWidgets.QPushButton("Download", self)
        self.pushButton.setEnabled(True)
        self.pushButton.setGeometry(QtCore.QRect(615, 12, 75, 31))
        self.pushButton.clicked.connect(self.hanldebutton)
        self.pushButton2 = QtWidgets.QPushButton("Clear", self)
        self.pushButton2.setEnabled(True)
        self.pushButton2.setGeometry(QtCore.QRect(562, 12, 50, 31))
        self.pushButton2.clicked.connect(self.clearListView)
        self.line = QtWidgets.QFrame(self)
        self.line.setGeometry(QtCore.QRect(547, 13, 16, 30))
        self.line.setFrameShape(QtWidgets.QFrame.VLine)

    def closeEvent(self, event):
        self.main.pushButton_2.setEnabled(True)


class Main(QtWidgets.QWidget):

    def startBrowser(self):
        if not checkcdm(self):
            return

        self.pushButton.setEnabled(False)
        self.pushButton.setText("Starting ...")
        pool = QThreadPool.globalInstance()
        browser = Browser(self)
        browser.signals.ended.connect(self.ended)
        browser.signals.started.connect(self.browserstart)
        browser.signals.links.connect(self.link)
        browser.signals.error.connect(self.error)
        pool.start(browser)

    def ended(self):
        self.pushButton.setEnabled(True)
        self.pushButton.setText("Browser")

    def browserstart(self):
        self.pushButton.setText("Browser")

    def link(self, arr):
        if arr[0] == 0:
            self.sniffer.listView.addItem(arr[1])
            if self.sniffer.listView.verticalScrollBar().value() == self.sniffer.listView.verticalScrollBar().maximum():
                self.sniffer.listView.scrollToBottom()
        elif arr[0] == 1:
            self.sniffer.listView2.addItem(arr[1])
            if self.sniffer.listView2.verticalScrollBar().value() == self.sniffer.listView2.verticalScrollBar().maximum():
                self.sniffer.listView2.scrollToBottom()

    def startSniffer(self):
        self.pushButton_2.setEnabled(False)
        self.sniffer.show()

    def startDownloads(self):
        self.pushButton_3.setEnabled(False)
        self.downloads.show()

    def startSettings(self):
        self.pushButton_4.setEnabled(False)
        self.settings.listWidget.item(0).setSelected(True)
        self.settings.show()

    def startAbout(self):
        self.pushButton_5.setEnabled(False)
        self.about.show()

    def closeEvent(self, event):
        close(self)

    def error(self, error):
        QMessageBox.critical(
            self,
            "MPDL/Error",
            error,
            buttons=QMessageBox.Ok,
            defaultButton=QMessageBox.Ok,
        )

    def start(self, arr):
        self.downloads.table.insertRow(0)
        self.downloads.table.setCellWidget(0, 0, QLabel(arr[0]))
        self.downloads.table.setCellWidget(0, 1, QLabel("Starting"))
        self.downloads.table.setCellWidget(0, 2, QLabel("0 MB"))
        self.downloads.table.setCellWidget(0, 3, QProgressBar())
        self.downloads.table.setCellWidget(0, 4, QLabel())
        self.downloads.table.setCellWidget(0, 5, QLabel("0 KB/s"))
        self.downloads.table.setCellWidget(0, 6, QLabel(arr[1]))
        self.downloads.table.scrollToBottom()

    def progress(self, arr):
        for i in range(self.downloads.table.rowCount()):
            if arr[0] == self.downloads.table.cellWidget(i, 0).text():
                self.downloads.table.cellWidget(i, 0).setText(arr[0])
                self.downloads.table.cellWidget(i, 1).setText(arr[1])
                self.downloads.table.cellWidget(i, 2).setText(arr[2])
                self.downloads.table.cellWidget(i, 3).setValue(int(float(arr[3])))
                self.downloads.table.cellWidget(i, 4).setText(arr[4])
                self.downloads.table.cellWidget(i, 5).setText(arr[5])
                self.downloads.table.cellWidget(i, 6).setText(arr[6])

    def complete(self, uuid):
        for i in range(self.downloads.table.rowCount()):
            if uuid == self.downloads.table.cellWidget(i, 0).text():
                self.downloads.table.removeRow(i)

    def __init__(self):
        super().__init__()
        config.setupConfig()

        self.setWindowTitle("MPDL/Main")
        self.resize(341, 167)
        self.setFixedSize(341, 167)
        self.setWindowIcon(util.getIcon())

        self.sniffer = Sniffer(self)
        self.downloads = Downloads(self)
        self.settings = Settings(self)
        self.about = About(self)

        self.label_2 = QtWidgets.QLabel("MPDL", self)
        self.label_2.setGeometry(QtCore.QRect(180, 14, 141, 51))

        self.label_2.setFont(util.getFont(43, True, True))
        self.label_3 = QtWidgets.QLabel("v" + VERSION, self)
        self.label_3.setGeometry(QtCore.QRect(225, 63, 31, 16))
        self.groupBox_2 = QtWidgets.QGroupBox("Panels", self)
        self.groupBox_2.setGeometry(QtCore.QRect(11, 4, 120, 153))
        self.pushButton = QtWidgets.QPushButton("Browser", self.groupBox_2)
        self.pushButton.setGeometry(QtCore.QRect(10, 18, 101, 23))
        self.pushButton.clicked.connect(self.startBrowser)
        self.pushButton_2 = QtWidgets.QPushButton("URL Sniffer", self.groupBox_2)
        self.pushButton_2.setGeometry(QtCore.QRect(10, 44, 101, 23))
        self.pushButton_2.clicked.connect(self.startSniffer)
        self.pushButton_3 = QtWidgets.QPushButton("Downloads", self.groupBox_2)
        self.pushButton_3.setGeometry(QtCore.QRect(10, 70, 101, 23))
        self.pushButton_3.clicked.connect(self.startDownloads)
        self.pushButton_4 = QtWidgets.QPushButton("Settings", self.groupBox_2)
        self.pushButton_4.setGeometry(QtCore.QRect(10, 96, 101, 23))
        self.pushButton_4.clicked.connect(self.startSettings)
        self.pushButton_5 = QtWidgets.QPushButton("About", self.groupBox_2)
        self.pushButton_5.setGeometry(QtCore.QRect(10, 122, 101, 23))
        self.pushButton_5.clicked.connect(self.startAbout)
        self.line = QtWidgets.QFrame(self)
        self.line.setGeometry(QtCore.QRect(132, 10, 16, 146))
        self.line.setFrameShape(QtWidgets.QFrame.VLine)
        self.line_2 = QtWidgets.QFrame(self)
        self.line_2.setGeometry(QtCore.QRect(150, 81, 180, 16))
        self.line_2.setFrameShape(QtWidgets.QFrame.HLine)
        self.groupBox = QtWidgets.QGroupBox("About", self)
        self.groupBox.setGeometry(QtCore.QRect(150, 96, 181, 61))
        self.label = QtWidgets.QLabel("(c)", self.groupBox)
        self.label.setGeometry(QtCore.QRect(10, 32, 16, 16))
        self.label.setOpenExternalLinks(False)
        self.label_4 = QtWidgets.QLabel("github.com/DevLARLEY/mpdl", self.groupBox)
        self.label_4.setGeometry(QtCore.QRect(27, 32, 161, 16))
        self.label_4.setOpenExternalLinks(True)
        self.label_5 = QtWidgets.QLabel("Downloader for DRM Content", self.groupBox)
        self.label_5.setGeometry(QtCore.QRect(10, 16, 161, 16))


def mainGUI():
    main = Main()
    main.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    mainGUI()
