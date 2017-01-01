#!/usr/bin/python

import shelve
import time
import json
from multiprocessing import Lock
mutex = Lock()

class ShelveStore(object):
    def start(self):
        self.db = shelve.open('store.db')
        
    def save(self, timestamp, mph, imgname, vidname):
        t = int(time.mktime(timestamp.timetuple())*1000)
        tid = timestamp
        with mutex:
            self.db[str(tid)] = json.dumps({
                'tid':str(tid), 
                'timestamp':t, 
                'mph':mph, 
                'imgname':imgname, 
                'vidname':vidname
            })

    def list(self):
        outdata = []
        with mutex:
            for k,v in self.db.iteritems():
                outdata.append((k, json.loads(v)))
        return outdata

    def get(self, timestamp):
        with mutex:
            if self.db.has_key(timestamp):
                return self.db[timestamp]

    def rm(self, timestamp):
        del self.db[str(timestamp)]
    
    def stop(self):
        self.db.close()

