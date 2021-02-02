#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#   PhishingKitHunter - Find phishing kits which use your brand/organization's files and image
#   Copyright (C) 2017-2019 Thomas Damonneville
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import time
import getopt
import sys
import csv
import configparser
import hashlib
import urllib.request
import socks
import whois
from sockshandler import SocksiPyHandler
from urllib.parse import urlparse
from tqdm import tqdm

VERSION = "0.8.1"


# Graceful banner  :)
def banner():
    banner = '''
  _ \  |  / |   |             |            
 |   | ' /  |   | |   | __ \  __|  _ \  __|
 ___/  . \  ___ | |   | |   | |    __/ |   
_|    _|\_\_|  _|\__,_|_|  _|\__|\___|_|   
'''
    print (banner)
    print ("-= Phishing Kit Hunter - v" + VERSION + " =-\n")


# Parse config file
def read_config(Conf):
    global RegRequest
    global RegRequest2
    global RegReferer
    global CompRegEx
    global http_proxy
    global socks_proxy_server
    global socks_proxy_port
    global proxy_type

    config = configparser.ConfigParser()
    with open(Conf, 'r', encoding='utf-8') as f:
        config.read_file(f)
    try:
        RegRequest = re.compile(config.get("DEFAULT", "tracking_file_request")).search
        RegRequest2 = re.compile(config.get("DEFAULT", "tracking_file_request"))
        RegReferer = re.compile(config.get("DEFAULT", "legitimate_referer")).search
        CompRegEx = re.compile(config.get("DEFAULT", "log_pattern"), re.X)

        # If Proxy configured
        if config.get("CONNECT", "http_proxy", fallback=None):
            # If SOCKS proxy
            if urlparse(config.get("CONNECT", "http_proxy")).scheme in 'socks':
                proxy_type = 'socks'
                socks_proxy = urlparse(config.get("CONNECT", "http_proxy")).netloc.split(':')
                socks_proxy_server = socks_proxy[0]
                socks_proxy_port = socks_proxy[1]
            # If HTTP proxy
            elif urlparse(config.get("CONNECT", "http_proxy")).scheme in 'http':
                proxy_type = 'http'
                http_proxy = config.get("CONNECT", "http_proxy")

    except:
        err = sys.exc_info()[0]
        print(err)


# RegEx pattern
def LogPattern_search(Line):
    global ResTimestamp
    global ResRequestEx
    global ResRefererEx
    try:
        # Group is [0]: timestamp, [1]: file request, [2]: referer
        ResRegEx = CompRegEx.match(Line).group(1, 2, 3)
        ResTimestamp = ResRegEx[0]
        ResRequestEx = ResRegEx[1]
        if ResRegEx[2] is not '-':
            ResRefererEx = ResRegEx[2]

    except:
        # Except direct connexion
        pass


# Domain extraction (for whois)
# TODO: find a way for whois request behind a HTTP proxy
def dom_extract(ref):
    global ex_url
    refurl = urlparse(ref)
    ex_url = refurl.netloc


# WHOIS informations
def whois_enrich(ex_url):
    global domain_registrar
    global domain_creat_date
    global domain_expi_date
    global resolv_dns
    resolv_dns = 'NOK'
    try:
        domreq = whois.whois(ex_url)
        if domreq.registrar is not None:
            domain_registrar = domreq.registrar
        else:
            domain_registrar = 'Not found'

        if domreq.creation_date is not None:
            if type(domreq.creation_date) is list:
                # First occurence is UTC creation date
                domain_creat_date = str(domreq.creation_date[0])
            else:
                domain_creat_date = domreq.creation_date
        else:
            domain_creat_date = 'None found'

        if domreq.expiration_date is not None:
            if type(domreq.expiration_date) is list:
                # First occurence is UTC expiration date
                domain_expi_date = str(domreq.expiration_date[0])
            else:
                domain_expi_date = domreq.expiration_date
        else:
            domain_expi_date = 'None found'
        resolv_dns = 'OK'
    except Exception as e:
        print(e)
        pass


# HTTP Get
def get_page(ResRefererEx):
    global PK_status
    global htmlshash
    # Use a proxy if declared in config file
    try:
        # Use a HTTP proxy
        if proxy_type in 'http':
            http_proxy
            proxy_support = urllib.request.ProxyHandler({'http': http_proxy})
            opener = urllib.request.build_opener(proxy_support)
            urllib.request.install_opener(opener)
        # Use a SOCKS5 proxy
        elif proxy_type in 'socks':
            socks_proxy_server
            socks_proxy_port
            opener = urllib.request.build_opener(SocksiPyHandler(socks.SOCKS5, socks_proxy_server, int(socks_proxy_port), True))
            urllib.request.install_opener(opener)

    except NameError:
        pass

    try:
        request = urllib.request.Request(url=ResRefererEx, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36'})
        response = urllib.request.urlopen(request, timeout=5)
        resp_code = response.getcode()
        htmldata = str(response.read().decode('utf-8'))

        if resp_code == 200:
            try:
                # If page contains tracking_file_request
                if RegRequest2.finditer(htmldata):
                    PK_status = 'UP'
                    # Create SHA256 hash of HTML page content
                    htmlshash = hashlib.sha256(htmldata.encode('utf-8')).hexdigest()
                else:
                    PK_status = 'Probably removed'
            except:
                err = sys.exc_info()
                print(err)
                pass
        else:
            PK_status = 'DOWN'

    except:
        err = sys.exc_info()[1]
        PK_status = ('can\'t connect (' + str(err) + ')')
        pass


# Usage
def usage():
    banner()
    usage = """
    -h --help       Prints this
    -i --ifile      Input logfile to analyse
    -o --ofile      Output CSV report file (default: ./PKHunter-report-'date'-'hour'.csv)
    -c --config     Configuration file to use (default: ./conf/defaults.conf)
    """
    print (usage)
    sys.exit(0)


# Commandline options
# TODO: gestion erreurs
def args_parse():
    global CSVFile
    global LogFile
    global ConfFile
    ConfFile = './conf/defaults.conf'
    CSVFile = './PKHunter-report-' + time.strftime("%Y%m%d-%H%M%S") + '.csv'

    if not len(sys.argv[1:]):
        usage()
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:c:o:", ["help", "infile=", "configfile=", "reportfile="])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)
        usage()
        sys.exit(2)

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
        elif o in ("-i", "--ifile"):
            LogFile = a
        elif o in ("-o", "--ofile"):
            CSVFile = a
        elif o in ("-c", "--config"):
            ConfFile = a
        else:
            assert False, "Unhandled Option"

    return


# Main
def main():
    banner()
    # Open CSV report file
    with open(CSVFile, 'w', encoding='utf-8', newline='\r\n') as csvfile:
        writer = csv.writer(csvfile, delimiter=';')
        # CSV file first line
        row = ("PK_URL", "Domain", "HTTP_sha256", "HTTP_status", "date", "domain registrar", "domain creation date", "domain creation date", "domain expiration date")
        writer.writerow(row)
        # Parse logs file
        try:
            # Open logs file and replace non-utf8 chars
            with open(LogFile, 'r', errors='replace') as f:
                for line in tqdm(f):
                    try:
                        # Parse logfile to extract strings
                        LogPattern_search(line)
                        # If request found and referer is what your looking for
                        if RegRequest(ResRequestEx):
                            dom_extract(ResRefererEx)
                            if not RegReferer(ex_url) and ResRefererEx is not None:
                                tqdm.write('\n[+] ' + ResRefererEx)
                                tqdm.write('\t|   Timestamp: ' + ResTimestamp)
                                get_page(ResRefererEx)
                                tqdm.write('\t| HTTP status: ' + PK_status)
                                if PK_status is 'UP':
                                    tqdm.write('\t| HTTP shash : ' + htmlshash)
                                    # if resolv_dns in 'OK':
                                    try:
                                        whois_enrich(ex_url)
                                        tqdm.write('\t| DOMAIN registrar: ' + domain_registrar)
                                        tqdm.write('\t| DOMAIN creation date: ' + str(domain_creat_date))
                                        tqdm.write('\t| DOMAIN expiration date: ' + str(domain_expi_date))

                                        row = (ResRefererEx, ex_url, htmlshash, PK_status, ResTimestamp, domain_registrar, domain_creat_date, domain_expi_date)
                                        writer.writerow(row)
                                    except NameError:
                                        row = (ResRefererEx, ex_url, htmlshash, PK_status, ResTimestamp, '', '', '')
                                        writer.writerow(row)
                                    # else:
                                    #     row = (ResRefererEx, ex_url, htmlshash, PK_status, ResTimestamp, '', '', '')
                                    #     writer.writerow(row)

                                else:
                                    # CSV Report
                                    row = (ResRefererEx, ex_url, '', PK_status, ResTimestamp, '', '', '')
                                    writer.writerow(row)
                    except:
                        err = sys.exc_info()
                        tqdm.write(err)

        except IOError:
            print ("Error: Log file does not appear to exist.")
            return 0


if __name__ == '__main__':
    args_parse()
    read_config(ConfFile)
    main()
