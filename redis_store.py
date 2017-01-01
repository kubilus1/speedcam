import time
import json
import redis

REDIS_HOST = "localhost"
REDIS_PORT = 6379

r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)

class RedisStore(object):
    def start(self):
        self.r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0)

    def save(self, timestamp, mph, imgname, vidname):
        t = int(time.mktime(timestamp.timetuple())*1000)
        tid = timestamp
        self.r.set("tid:%s" % str(tid), json.dumps({
            'tid':str(tid), 
            'timestamp':t, 
            'mph':mph, 
            'imgname':imgname, 
            'vidname':vidname
        }))

        self.r.rpush("tids", "tid:%s" % str(tid))

    def list(self):
        outdata = []
        for tid in self.r.lrange("tids", 0, -1):
            data = self.r.get(tid)
            if data:
                outdata.append((tid, json.loads(data)))
            else:
                continue
                #self.r.lrem("tids", 1, tid)
            
        return outdata

    def get(self, tid):
        return self.r.get(tid)

    def rm(self, tid):
        self.r.lrem("tids", 1, tid)
        self.r.delete(tid)

    def stop(self):
        pass

