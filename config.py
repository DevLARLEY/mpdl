import configparser
import os.path

parser = configparser.ConfigParser()


def setupConfig():
    if not os.path.isfile("config.ini"):
        fp = open("config.ini", 'x')
        fp.close()
        parser.read("config.ini")
        parser["MAIN"] = {"downloadpath": "", "downloadfrompath": "False", "ffmpegfrompath": "True", "ffmpegpath": "",
                          "mp4decryptfrompath": "True", "mp4decryptpath": "", "cdmselected": "False"}
        parser["BROWSER"] = {"startpage": "https://duckduckgo.com/", "drmenabled": "True", "addons": ""}
        writeConfig()
    parser.read("config.ini")


def resetConfig():
    if os.path.isfile("config.ini"):
        fp = open("config.ini", 'x')
        fp.close()
        parser.read("config.ini")
        parser["MAIN"] = {"downloadpath": "", "downloadfrompath": "False", "ffmpegfrompath": "True", "ffmpegpath": "",
                          "mp4decryptfrompath": "True", "mp4decryptpath": "", "cdmselected": "False"}
        parser["BROWSER"] = {"startpage": "https://duckduckgo.com/", "drmenabled": "True", "addons": ""}
        writeConfig()


def writeConfig():
    with open('config.ini', 'w') as configfile:
        parser.write(configfile)
