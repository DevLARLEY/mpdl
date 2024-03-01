import re
from PyQt5 import QtGui


def getFont(size, italic, bold):
    font = QtGui.QFont()
    font.setFamily("Cascadia Code")
    font.setPointSize(size)
    font.setBold(bold)
    font.setItalic(italic)
    return font


def setAddons(lw) -> str:
    items = [lw.item(x).text() for x in range(lw.count())]
    return "|".join(items)


def getAddons(c) -> list:
    if len(c["BROWSER"]["addons"]) <= 1:
        return []
    else:
        return c["BROWSER"]["addons"].split("|")


def getIcon():
    icon = QtGui.QIcon()
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Normal, QtGui.QIcon.On)
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Disabled, QtGui.QIcon.Off)
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Disabled, QtGui.QIcon.On)
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Active, QtGui.QIcon.Off)
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Active, QtGui.QIcon.On)
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Selected, QtGui.QIcon.Off)
    icon.addPixmap(QtGui.QPixmap("icon.png"), QtGui.QIcon.Selected, QtGui.QIcon.On)
    return icon


curlexclude = ["te", "accept-encoding"]


def formatCURL(header):
    st = header.split("\n")
    r = ''
    for s in st:
        if s == '' or s == ' ' or s.split(": ")[0].lower() in curlexclude:
            continue
        r += "    '"
        r += s.replace(": ", "': '")
        r += "',\n"
    return r.rsplit(",", 1)[0]


def clearHeaders():
    file = open("headers.py", 'w')
    file.write("headers = {}\n")
    file.close()


def getPSSH(file):
    f = open(file, "r").read()
    res = re.findall('<cenc:pssh.*>.*<.*/cenc:pssh>', f)
    return str(min([x[11:-12] for x in res], key=len)).split(">")[-1].split("<")[-1] if res else None
