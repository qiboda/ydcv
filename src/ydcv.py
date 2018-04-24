#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function
from subprocess import check_output
from subprocess import call
from subprocess import Popen
from os.path import expanduser, join
from time import sleep
from datetime import datetime
from distutils import spawn
from tempfile import NamedTemporaryFile
from collections import namedtuple
import json
import re
import sys
import platform
import argparse

try:
    # Py3
    from urllib.parse import quote
    from urllib.request import urlopen
except ImportError:
    # Py 2.7
    from urllib import quote
    from urllib2 import urlopen
    reload(sys)
    sys.setdefaultencoding('utf8')


API = "YouDaoCV"
API_KEY = "659600698"

HISTORY_DIR = '~'
HISTORY_FILENAME = '.ydcv_history'
DELIMITER = '!'


class GlobalOptions(object):
    def __init__(self, options=None):
        self._options = options

    def __getattr__(self, name):
        if name in dir(GlobalOptions) or name in self.__dict__:
            return getattr(self, name)
        elif name in self._options.__dict__:
            return getattr(self._options, name)
        else:
            raise AttributeError("'%s' has no attribute '%s'" % (
                self.__class__.__name__, name))


options = GlobalOptions()


def touchOpen(filename, *args, **kwargs):
    open(filename, "at").close()  # "touch" file
    return open(filename, *args, **kwargs)


class HistroyRecord(object):
    word = None
    timestamp = None

    def __init__(self, word):
        self.word = word.replace(DELIMITER, DELIMITER + DELIMITER)
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def __str__(self):
        return self.word + DELIMITER + self.timestamp

    @classmethod
    def parse(cls, record):
        word, timestamp = record.rsplit(DELIMITER, 1)
        record = namedtuple('record', ['word', 'timestamp'])
        return record(word.replace(DELIMITER+DELIMITER, DELIMITER), timestamp.rstrip('\n'))


class HistoryRecords(object):
    def __init__(self):
        global HISTORY_DIR
        if HISTORY_DIR == '~':
            HISTORY_DIR = expanduser('~')
        self.history_path = join(HISTORY_DIR, HISTORY_FILENAME)

    def add(self, word):
        history_record = HistroyRecord(word)
        with touchOpen(self.history_path, 'at') as f:
            f.write(str(history_record) + '\n')

    def get(self, iword):
        records = []
        with touchOpen(self.history_path, 'rt') as f:
            for record in f:
                rcrd = HistroyRecord.parse(record)

                if iword and rcrd.word != iword:
                    continue
                records.append(rcrd)

        return records


history_records = HistoryRecords()


class Colorizing(object):
    colors = {
        'none': "",
        'default': "\033[0m",
        'bold': "\033[1m",
        'underline': "\033[4m",
        'blink': "\033[5m",
        'reverse': "\033[7m",
        'concealed': "\033[8m",

        'black': "\033[30m",
        'red': "\033[31m",
        'green': "\033[32m",
        'yellow': "\033[33m",
        'blue': "\033[34m",
        'magenta': "\033[35m",
        'cyan': "\033[36m",
        'white': "\033[37m",

        'on_black': "\033[40m",
        'on_red': "\033[41m",
        'on_green': "\033[42m",
        'on_yellow': "\033[43m",
        'on_blue': "\033[44m",
        'on_magenta': "\033[45m",
        'on_cyan': "\033[46m",
        'on_white': "\033[47m",

        'beep': "\007",
    }

    @classmethod
    def colorize(cls, s, color=None):
        if options.color == 'never':
            return s
        if options.color == 'auto' and not sys.stdout.isatty():
            return s
        if color in cls.colors:
            return "{0}{1}{2}".format(
                cls.colors[color], s, cls.colors['default'])
        else:
            return s


def online_resources(query):

    english = re.compile('^[a-z]+$', re.IGNORECASE)
    chinese = re.compile('^[\u4e00-\u9fff]+$', re.UNICODE)

    res_list = [
        (english, 'http://www.ldoceonline.com/search/?q={0}'),
        (english, 'http://dictionary.reference.com/browse/{0}'),
        (english, 'http://www.urbandictionary.com/define.php?term={0}'),
        (chinese, 'http://www.zdic.net/sousuo/?q={0}')
    ]

    return [url.format(quote(query.encode('utf-8')))
            for lang, url in res_list if lang.match(query) is not None]


def print_history(records):
    cnt = options.number if not options.all else len(records)
    for record in records:
        row = record[0]
        if options.count:
            row += "\t" + str(record[2])
        if options.date:
            row += "\t" + record[1]
        print(row)
        cnt -= 1
        if cnt == 0:
            break


def print_explanation(data, options):
    _c = Colorizing.colorize
    _d = data
    has_result = False
    _accent_urls = dict()

    query = _d['query']
    print(_c(query, 'underline'), end='')

    if 'basic' in _d:
        has_result = True
        _b = _d['basic']

        try:
            if 'uk-phonetic' in _b and 'us-phonetic' in _b:
                print(" UK: [{0}]".format(_c(_b['uk-phonetic'], 'yellow')), end=',')
                print(" US: [{0}]".format(_c(_b['us-phonetic'], 'yellow')))
            elif 'phonetic' in _b:
                print(" [{0}]".format(_c(_b['phonetic'], 'yellow')))
            else:
                print()
        except UnicodeEncodeError:
            print(" [ ---- ] ")

        if options.speech and 'speech' in _b:
            print(_c('  Text to Speech:', 'cyan'))
            if 'us-speech' in _b and 'uk-speech' in _b:
                print("     * UK:", _b['uk-speech'])
                print("     * US:", _b['us-speech'])
            elif 'speech' in _b:
                print("     *", _b['speech'])
            for _accent in ('speech', 'uk-speech', 'us-speech'):
                if _accent in _b:
                    _accent_urls.update({_accent.split('-')[0]: _b[_accent]})
            print()

        if 'explains' in _b:
            print(_c('  Word Explanation:', 'cyan'))
            print(*map("     * {0}".format, _b['explains']), sep='\n')
        else:
            print()
    elif 'translation' in _d:
        has_result = True
        print(_c('\n  Translation:', 'cyan'))
        print(*map("     * {0}".format, _d['translation']), sep='\n')
    else:
        print()

    if options.simple is False:
        # Web reference
        if 'web' in _d:
            has_result = True
            print(_c('\n  Web Reference:', 'cyan'))

            web = _d['web'] if options.full else _d['web'][:3]
            print(*['     * {0}\n       {1}'.format(
                _c(ref['key'], 'yellow'), '; '.join(map(_c('{0}', 'magenta').format, ref['value']))) for ref in web], sep='\n')

        # Online resources
        ol_res = online_resources(query)
        if len(ol_res) > 0:
            print(_c('\n  Online Resource:', 'cyan'))
            res = ol_res if options.full else ol_res[:1]
            print(*map(('     * ' + _c('{0}', 'underline')).format, res), sep='\n')

        # read out the word
        if options.read:
            print()
            sys_name = platform.system()
            if 'Darwin' == sys_name:
                call(['say', query])
            elif 'Linux' == sys_name:
                if not spawn.find_executable(options.player):
                    print(_c(' -- Player ' + options.player + ' is not found in system, ', 'red'))
                    print(_c('    acceptable players are: festival, mpg123, sox and mpv', 'red'))
                    print(_c(' -- Please install your favourite player: ', 'blue'))
                    print(_c('    - festival (http://www.cstr.ed.ac.uk/projects/festival/),'))
                    print(_c('    - mpg123 (http://www.mpg123.de/),'))
                    print(_c('    - SoX (http://sox.sourceforge.net/),'))
                    print(_c('    - mpv (https://mpv.io).'))
                else:
                    if options.player == 'festival':
                        Popen('echo ' + query + ' | festival --tts', shell=True)
                    else:
                        accent = options.accent if options.accent != 'auto' else 'speech'
                        accent_url = _accent_urls.get(accent, '')
                        if not accent_url:
                            print(_c(' -- URL to speech audio for accent {} not found.'.format(options.accent), 'red'))
                            if not options.speech:
                                print(_c(' -- Maybe you forgot to add -S option?'), 'red')
                        else:
                            with NamedTemporaryFile(suffix=".mp3") as accent_file:
                                if call('curl -s "{0}" -o {1}'.format(accent_url, accent_file.name), shell=True) != 0:
                                    print(_c('Network unavailable or permission error to write file: {}'
                                             .format(accent_file), 'red'))
                                else:
                                    if options.player == 'mpg123':
                                        call('mpg123 -q ' + accent_file.name, shell=True)
                                    elif options.player == 'sox':
                                        call('play -q ' + accent_file.name, shell=True)
                                    elif options.player == 'mpv':
                                        call('mpv --really-quiet ' + accent_file.name, shell=True)

    if not has_result:
        print(_c(' -- No result for this query.', 'red'))

    print()


def lookup_history(word):
    records = history_records.get(word)

    if options.count:
        post_records = {}
        for record in records:
            if post_records.get(record.word) is None:
                post_records[record.word] = (record.timestamp, 1)
            else:
                post_records[record.word] = (max(record.timestamp, post_records[record.word][0]),
                                             post_records[record.word][1] + 1)

        records = []
        for key, value in post_records.items():
            records.append([key, value[0], value[1]])

    if options.sort == 'word':
        records.sort(key=lambda k: k[0], reverse=options.reverse)
    elif options.sort == 'date':
        records.sort(key=lambda k: k[1], reverse=options.reverse)
    elif options.sort == 'count':
        records.sort(key=lambda k: k[2], reverse=options.reverse)

    print_history(records)


def lookup_word(word):
    qword = quote(word)
    if qword == '%5Cq' or qword == '%3Aq':
        sys.exit("Thanks for using, goodbye!")
    else:
        pass
    try:
        data = urlopen("http://fanyi.youdao.com/openapi.do?keyfrom={0}&"
                       "key={1}&type=data&doctype=json&version=1.2&q={2}".format(
                           API, API_KEY, qword)).read().decode("utf-8")
    except IOError:
        print("Network is unavailable")
    else:
        print_explanation(json.loads(data), options)
        history_records.add(word)


class DefaultSubcommandArgParse(argparse.ArgumentParser):
    __default_subparser = None

    def set_default_subparser(self, name):
        self.__default_subparser = name

    def _parse_known_args(self, arg_strings, *args, **kwargs):
        in_args = set(arg_strings)
        d_sp = self.__default_subparser
        if d_sp is not None and not {'-h', '--help'}.intersection(in_args):
            for x in self._subparsers._actions:
                subparser_found = (
                    isinstance(x, argparse._SubParsersAction) and
                    in_args.intersection(x._name_parser_map.keys())
                )
                if subparser_found:
                    break
            else:
                # insert default in first position, this implies no
                # global options without a sub_parsers specified
                arg_strings = [d_sp] + arg_strings
        return super(DefaultSubcommandArgParse, self)._parse_known_args(
            arg_strings, *args, **kwargs
        )


def check_positive(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return ivalue


def arg_parse():
    parser = DefaultSubcommandArgParse(description="Youdao Console Version")
    subparser = parser.add_subparsers(description="ydcv subcommand", dest="subcommand")

    parser_lookup = subparser.add_parser("lookup", help="lookup word")
    parser_lookup.add_argument('-f', '--full',
                               action="store_true",
                               default=False,
                               help="print full web reference, only the first 3 "
                               "results will be printed without this flag.")
    parser_lookup.add_argument('-s', '--simple',
                               action="store_true",
                               default=False,
                               help="only show explainations. "
                               "argument \"-f\" will not take effect.")
    parser_lookup.add_argument('-S', '--speech',
                               action="store_true",
                               default=False,
                               help="print URL to speech audio.")
    parser_lookup.add_argument('-r', '--read',
                               action="store_true",
                               default=False,
                               help="read out the word with player provided by \"-p\" option.")
    parser_lookup.add_argument('-p', '--player',
                               choices=['festival', 'mpg123', 'sox', 'mpv'],
                               default='festival',
                               help="read out the word with this play."
                               "Default to 'festival' or can be 'mpg123', 'sox', 'mpv'."
                               "-S option is required if player is not festival.")
    parser_lookup.add_argument('-a', '--accent',
                               choices=['auto', 'uk', 'us'],
                               default='auto',
                               help="set default accent to read the word in. "
                               "Default to 'auto' or can be 'uk', or 'us'.")
    parser_lookup.add_argument('-x', '--selection',
                               action="store_true",
                               default=False,
                               help="show explaination of current selection.")
    parser_lookup.add_argument('--color',
                               choices=['always', 'auto', 'never'],
                               default='auto',
                               help="colorize the output. "
                               "Default to 'auto' or can be 'never' or 'always'.")
    parser_lookup.add_argument('words',
                               nargs='*',
                               help="words to lookup, or quoted sentences to translate.")

    parser_hist = subparser.add_parser("history", help="show the history records.")
    # 关于 ydcv history -a -n 10 不显示冲突问题，
    # 参见Issue18943: https://bugs.python.org/issue18943 。
    count_group = parser_hist.add_mutually_exclusive_group()
    count_group.add_argument('-a', '--all',
                             action="store_true",
                             default=False,
                             help="show the all history records.")
    count_group.add_argument('-n', '--number',
                             default=10,
                             type=check_positive,
                             metavar='number',
                             help="show the n history records.")
    parser_hist.add_argument('-s', '--sort',
                             choices=['date', 'word', 'count'],
                             default='date',
                             help="sort the history records.")
    parser_hist.add_argument('-r', '--reverse',
                             action="store_true",
                             default=False,
                             help="reverse the history records.")
    parser_hist.add_argument('-c', '--count',
                             action="store_true",
                             default=False,
                             help="show the word counts in history records.")
    parser_hist.add_argument('-d', '--date',
                             action="store_true",
                             default=False,
                             help="show the date of looking up word in history records.")
    parser_hist.add_argument('-x', '--selection',
                             action="store_true",
                             default=False,
                             help="show history of current selection.")
    parser_hist.add_argument('words',
                             nargs='*',
                             help="words to history, or quoted sentences to history record.")

    parser.set_default_subparser("lookup")
    return parser.parse_args()


def main():
    options._options = arg_parse()

    if options.words:
        for word in options.words:
            if options.subcommand == 'lookup':
                lookup_word(word)
            elif options.subcommand == 'history':
                lookup_history(word)
    else:
        if options.selection:
            last = check_output(["xclip", "-o"], universal_newlines=True)
            while True:
                try:
                    sleep(0.1)
                    curr = check_output(["xclip", "-o"], universal_newlines=True)
                    if curr != last:
                        last = curr
                        if last.strip():
                            if options.subcommand == 'lookup':
                                lookup_word(last)
                            elif options.subcommand == 'history':
                                lookup_history(last)
                        print("Waiting for selection>")
                except (KeyboardInterrupt, EOFError):
                    break
        else:
            if options.subcommand == 'history':
                lookup_history(None)
            elif options.subcommand == 'lookup':
                try:
                    import readline
                except ImportError:
                    pass
                while True:
                    try:
                        if sys.version_info[0] == 3:
                            word = input('> ')
                        else:
                            word = raw_input('> ')
                        if word.strip():
                            lookup_word(word)
                    except KeyboardInterrupt:
                        print()
                        continue
                    except EOFError:
                        break
        if options.subcommand == 'lookup':
            print("\nBye")


if __name__ == "__main__":
    main()
