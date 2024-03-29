# use this to activate default environment
# import activate_default

# or if you require a different environment from the default, use this
from activate import activate_venv_or_die
activate_venv_or_die('py2')

import sys
import os
import socket
import csv
from collections import OrderedDict
if sys.version < '3':
    from urllib import unquote
else:
    from urllib.parse import unquote

input_buf = sys.stdin
results = []
settings = {}
attr = last_attr = None
while True:
    line = input_buf.readline()
    line = line[:-1]
    if len(line) == 0:
        break

    colon = line.find(':')
    if colon < 0:
        if last_attr:
            pass
        else:
            continue
    last_attr = attr = line[:colon]
    val = unquote(line[colon+1:])
csvr = csv.reader(input_buf)
header = []
first = True
for line in csvr:
    if first:
        header = line
        first = False
        continue
    result = OrderedDict()
    i = 0
    for val in line:
        result[header[i]] = val
        i += 1

    results.append(result)

for result in results:
    result["message"] = "host:{} executable:{} version:{} cwd:{}".format(socket.gethostname(), sys.executable, sys.version, os.getcwd())
    try:
        import splunklib
    except ImportError:
        result["foundSDK"] = "false"
    else:
        result["foundSDK"] = "true"

outputfile = sys.stdout
s = set()
header = []
for i in range(len(results)):
    for k in results[i].keys():
        if k not in s:
            s.add(k)
            header.append(k)

dw = csv.DictWriter(outputfile, header, extrasaction='ignore')
dw.writerow(dict(zip(header, header)))
dw.writerows(results)
