# coding:utf-8

import os
import re
import threading
from functools import partial
from time import sleep
from . import clogging as logging
from .compat import thread, ConfigParser
from .common import config_dir, isip, isipv4, isipv6, classlist
from .GlobalConfig import GC

BLOCK     = 1
FORWARD   = 2
DIRECT    = 3
GAE       = 4
FAKECERT  = 5
PROXY     = 6
REDIRECT  = 7
IREDIRECT = 8

numToAct = {
    BLOCK     : 'do_BLOCK',
    FORWARD   : 'do_FORWARD',
    DIRECT    : 'do_DIRECT',
    REDIRECT  : 'do_REDIRECT',
    IREDIRECT : 'do_IREDIRECT',
    PROXY     : 'do_PROXY',
    FAKECERT  : 'do_DIRECT',
    GAE       : 'do_GAE',
}
numToSSLAct = {
    BLOCK     : 'do_FAKECERT',
    FORWARD   : 'do_FORWARD',
    DIRECT    : 'do_FAKECERT',
    REDIRECT  : 'do_FAKECERT',
    IREDIRECT : 'do_FAKECERT',
    PROXY     : 'do_PROXY',
    FAKECERT  : 'do_FAKECERT',
    GAE       : 'do_FAKECERT',
}
actToNum = {
    'BLOCK'     : BLOCK,
    'FORWARD'   : FORWARD,
    'DIRECT'    : DIRECT,
    'REDIRECT'  : REDIRECT,
    'IREDIRECT' : IREDIRECT,
    'PROXY'     : PROXY,
    'FAKECERT'  : FAKECERT,
    'GAE'       : GAE,
}

isfiltername = re.compile(r'(?P<order>\d+)-(?P<action>\w+)').match
isempty = re.compile(r'^\s*$').match
if GC.LINK_PROFILE == 'ipv4':
    pickip = re.compile(r'(?<=\s|\|)(?:\d+\.){3}\d+(?=$|\s|\|)').findall
    ipnotuse = isipv6
elif GC.LINK_PROFILE == 'ipv46':
    pickip = re.compile(r'(?<=\s|\|)((?:\d+\.){3}\d+|(?:(?:[a-f\d]{1,4}:){1,6}|:)(?:[a-f\d]{1,4})?(?::[a-f\d]{1,4}){1,6})(?=$|\s|\|)').findall
    #还要使用字符名称，所以不用验证
    ipnotuse = lambda x: False
elif GC.LINK_PROFILE == 'ipv6':
    pickip = re.compile(r'(?<=\s|\|)(?:(?:[a-f\d]{1,4}:){1,6}|:)(?:[a-f\d]{1,4})?(?::[a-f\d]{1,4}){1,6}(?=$|\s|\|)').findall
    ipnotuse = isipv4

class actionfilterlist(list):

    CONFIG_FILENAME = os.path.join(config_dir, 'ActionFilter.ini')

    def __init__(self):
        list.__init__(self)
        self.readconfig()
        self.FILE_MTIME = os.path.getmtime(self.CONFIG_FILENAME)
        self.RESET = False
        thread.start_new_thread(self.check_modify, ())

    def readconfig(self):
        CONFIG = ConfigParser(inline_comment_prefixes=('#', ';'))
        CONFIG._optcre = re.compile(r'(?P<option>[^\s]+)(?P<vi>\s+=)?\s*(?P<value>.*)')
        CONFIG.read(self.CONFIG_FILENAME)

        sections = CONFIG.sections()
        sections.sort()
        self.clear()
        for s in sections:
            try:
                order, action = isfiltername(s).group('order', 'action')
            except:
                continue
            action = action.upper()
            if action not in actToNum:
                continue
            filters = classlist()
            filters.action = actToNum[action]
            for k, v in CONFIG.items(s):
                scheme = ''
                if k.find('://', 0, 9) > 0 :
                    scheme, _, k = k.partition('://')
                if  '/' in  k:
                    host, _, path = k.partition('/')
                else:
                    host, path = k, ''
                if host.find('@') == 0:
                    host = re.compile(host[1:]).search
                else:
                    host = host.lower()
                if path.find('@') == 0:
                    path = re.compile(path[1:]).search
                if filters.action in (FORWARD, DIRECT):
                    if isempty(v):
                        v = None
                    elif '|' in v:
                        v = pickip(' '+v.lower()) or None
                    elif ipnotuse(v) or not (v in GC.IPLIST_MAP or isip(v)):
                        v = None
                elif filters.action in (REDIRECT, IREDIRECT) and '>>' in v:
                    patterns, _, replaces = v.partition('>>')
                    patterns = patterns.rstrip(' \t')
                    replaces = replaces.lstrip(' \t')
                    if patterns[0] == '@':
                        patterns = patterns[1:].lstrip(' \t')
                        if replaces[0] == '@':
                            replaces = replaces[1:].lstrip(' \t')
                            v = partial(re.compile(patterns).sub, replaces), True
                        else:
                            v = partial(re.compile(patterns).sub, replaces), False
                    else:
                        if replaces[0] == '@':
                            replaces = replaces[1:].lstrip(' \t')
                            v = (patterns, replaces, 1), True
                        else:
                            v = (patterns, replaces, 1), False
                filters.append((scheme.lower(), host, path, v))
            self.append(filters)

    def check_modify(self):
        while True:
            sleep(10)
            filemtime = os.path.getmtime(self.CONFIG_FILENAME)
            if filemtime > self.FILE_MTIME and not self.RESET:
                try:
                    self.readconfig()
                    self.FILE_MTIME = filemtime
                    self.RESET = True
                except Exception as e:
                    logging.warning('%r 内容被修改，重新加载时出现错误，请检查后重新修改：\n%r', self.CONFIG_FILENAME, e)

ACTION_FILTERS = actionfilterlist()
