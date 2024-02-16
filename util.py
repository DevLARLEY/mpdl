import json
import re
import requests
import urllib.request
import xmltodict
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


def getPSSH(mpd_url):
    pssh = ''
    correct = True
    try:
        r = requests.get(url=mpd_url)
        r.raise_for_status()
        xml = xmltodict.parse(r.text)
        mpd = json.loads(json.dumps(xml))
        periods = mpd['MPD']['Period']
    except Exception:
        correct = False
    try:
        if isinstance(periods, list):
            for idx, period in enumerate(periods):
                if isinstance(period['AdaptationSet'], list):
                    for ad_set in period['AdaptationSet']:
                        if ad_set['@mimeType'] == 'video/mp4':
                            try:
                                for t in ad_set['ContentProtection']:
                                    if t['@schemeIdUri'].lower() == "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed":
                                        pssh = t["cenc:pssh"]
                            except Exception:
                                pass
                else:
                    if period['AdaptationSet']['@mimeType'] == 'video/mp4':
                        try:
                            for t in period['AdaptationSet']['ContentProtection']:
                                if t['@schemeIdUri'].lower() == "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed":
                                    pssh = t["cenc:pssh"]
                        except Exception:
                            pass
        else:
            for ad_set in periods['AdaptationSet']:
                if ad_set['@mimeType'] == 'video/mp4':
                    try:
                        for t in ad_set['ContentProtection']:
                            if t['@schemeIdUri'].lower() == "urn:uuid:edef8ba9-79d6-4ace-a3c8-27dcd51d21ed":
                                pssh = t["cenc:pssh"]
                    except Exception:
                        pass
    except Exception:
        correct = False
    return correct, pssh


def getPSSH2(mpd_url):
    pssh = []
    try:
        name, headers = urllib.request.urlretrieve(mpd_url)
    except Exception:
        return []
    f = open(name, "r").read()
    res = re.findall('<cenc:pssh.*>.*<.*/cenc:pssh>', f)
    for r in res:
        try:
            r = r.split('>')[1].split('<')[0]
            pssh.append(r)
        except Exception:
            return []
    if pssh:
        return min(pssh, key=len)
    else:
        return []
