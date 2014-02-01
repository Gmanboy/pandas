#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re
import os
import time
import json
import base64

from iron_cache import *

key='KEY'+os.environ.get('JOB_NAME','')+"."
os.chdir(os.environ.get('HOME'))

cache = IronCache()

i=0

for i, fname in enumerate(sorted([x for x in os.listdir('.') if re.match("ccache.\d+$",x)])):
    print("Putting %s" % key+str(i))
    with open(fname,"rb") as f:
        s= f.read()
        value=base64.b64encode(s)
        if isinstance(value, bytes):
            value = value.decode('ascii')
    item = cache.put(cache="travis", key=key+str(i), value=value,options=dict(expires_in=24*60*60))

# print("foo")
for i in range(i+1,20):

    try:
        item = cache.delete(key+str(i),cache='travis')
        print("Deleted %s" % key+str(i))
    except:
        break
        pass
