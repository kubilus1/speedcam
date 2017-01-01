#!/usr/bin/python

import os
import sys
import cv2
import math
import time
import json
import numpy
import shelve
import urllib2
import datetime
import subprocess
from Queue import Queue, Full, Empty
from threading import Thread
from collections import deque
from shelve_store import ShelveStore

FPS=30


class CamStream(object):
    q = Queue(250)
    def __init__(self, src):
        print "Init Stream for ", src
        self.stream = cv2.VideoCapture(src)
        #self.stream.set(3,1280)
        #self.stream.set(4,720)
        self.stream.set(3,640)
        self.stream.set(4,480)
        #self.stream.set(cv2.cv.CV_CAP_PROP_EXPOSURE,0.7)
        self.stream.set(5,FPS)
        #self.stream.set(cv2.cv.CV_CAP_PROP_FOURCC, cv2.cv.CV_FOURCC('M', 'J', 'P', 'G'))
        #print "FOURCC:", self.stream.get(cv2.cv.CV_CAP_PROP_FOURCC)

        self.showprops()

        (self.ret, self.frame) = self.stream.read()
        self.running = True

    def showprops(self):
        for i in xrange(22):
            print self.stream.get(i)

    def start(self):
        print "Starting CamStream..."
        Thread(target=self.update, args=()).start()
        print "Started..."
        return self

    def update(self):
        while self.running:
            #print "^",
            (self.ret, frame) = self.stream.read()
            t = datetime.datetime.now()
            #print "V"
            if self.ret:
                try:
                    qsize = self.q.qsize()
                    if qsize > 0:
                        print "QSIZE:", qsize
                #print "Put a frame"
                    self.q.put((t, frame))
                except Full:
                    print "Queue is full"
                #print "Putted"
        print "Exiting CamStream loop"

    def read(self):
        return self.q.get(True, 5)

    def stop(self):
        print "Stopping CamStream..."
        self.running = False



class TrackObj(object):

    last_x = -1
    init_x = -1
    scanwidth = -1
    init_time = -1
    direction = "NONE"
    frames = []
    mphs = []
    altmph = -1
    ftperpixel = -1
    mph = -1
    writer = None

    def __init__(self, x, w, scanwidth, t, img, fpp_lr, fpp_rl):
        self.init_x = x
        self.last_x = x
        self.scanwidth = scanwidth
        self.init_time = t

        if x < (self.scanwidth/4):
            # Found on left side
            self.direction = "LEFT_TO_RIGHT"
            self.ftperpixel = fpp_lr
        elif x > ((self.scanwidth/4)*3):
            # Found on right side
            self.direction = "RIGHT_TO_LEFT"
            self.ftperpixel = fpp_rl
        else:
            self.direciton = "INVALID"

        if w >= (self.scanwidth/4):
            self.direction = "INVALID"

        print "START: x: %s  w: %s sw: %s d: %s" % (
                x,
                w,
                scanwidth,
                self.direction
        )
        
        self.frames.append({
            "img": img,
            "time": t
        })

    def close(self):
        del self.frames[:]
        del self.mphs[:]
        self.frames = []
        self.mphs = []

    def update(self, x, w, t, img):
        self.stamp_img(img)
        self.frames.append({
            "img": img,
            "time": t
        })
       
        if self.direction == "DONE":
            return "DONE"

        if (x >= self.last_x) and (self.direction == "RIGHT_TO_LEFT"):
            return "JUNK"
        elif (x <= self.last_x) and (self.direction == "LEFT_TO_RIGHT"):
            return "JUNK"

        if self.direction == "RIGHT_TO_LEFT":
            abs_chg = self.init_x - x
        else:
            abs_chg = x + w - self.init_x

        secs = (t - self.init_time).total_seconds()
        mph = self.calc_mph(abs_chg, secs)
        altsec = float(len(self.frames))/float(FPS)
        self.altmph = self.calc_mph(abs_chg, altsec)
        if mph < 0 or mph > 75:
            return "JUNK"

        self.mphs.append(mph)
        self.last_x = x
        
        print "UPDATE: x: %s  w: %s mph: %s (%s) d: %s" % (
                x,
                w,
                mph,
                self.altmph,
                self.direction
        )

        edge = self.scanwidth/10

        if ((x <= edge) and (self.direction == "RIGHT_TO_LEFT")) \
            or ((x+w >= self.scanwidth - edge) \
            and (self.direction == "LEFT_TO_RIGHT")):
                
            print "Done tracking.  Final MPH:", mph, self.altmph
            self.direction = "DONE"
            
        return self.direction


    def calc_mph(self, abs_chg, secs):
        mph = 0.0
        if secs:
            mph = ((abs_chg * self.ftperpixel)/secs) * 0.681818
        return mph


    def stamp_img(self, img):
        cv2.putText(
            img, 
            "%.0f mph   %s" % (self.altmph, self.init_time),
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 
            1.0,
            (0, 255, 0),
            3
        )

    def save_img(self):
        img = self.frames[-1].get('img')
        self.imgname = "ps_%s_%.0f.jpg" % (
            self.init_time.strftime("%Y%m%d_%H%M%S"),
            self.altmph
        )
        #self.stamp_img(img)
        #outimg = self.catimg([inimg, thresh, self.baseline_img])
        cv2.imwrite(
            "data/%s" % self.imgname,
            img
        )

    def save_vid(self):
        print "SAVE VID:"
        numframes = len(self.frames)
        print "FRAMES:", numframes
        startt = self.frames[0].get('time')
        endt = self.frames[-1].get('time')
        spant = (endt - startt).total_seconds()
        print "TIMESPAN:", spant
        fps = float(numframes)/spant
        print "FPS:", fps
        frame_period = spant/float(numframes)
        print "FRAME PERIOD: ", frame_period

        lastt = startt
        for f in self.frames:
            t = f.get('time')    
            period = (t-lastt).total_seconds()
            print "JITTER: ", (frame_period - period) 
            lastt = t

        vidpath = "/tmp/ps_%s_%.0f.avi" % (self.init_time.strftime("%Y%m%d_%H%M%S"),self.altmph)
        fourcc = cv2.cv.CV_FOURCC('M','J','P','G')
        #fourcc = cv2.cv.CV_FOURCC('X','V','I','D')
        #fourcc = cv2.cv.CV_FOURCC('V','P','8','0')
        #fourcc = cv2.cv.CV_FOURCC('T','H','E','O')
        if self.writer is not None:
            self.writer.release()
        self.writer = None
        h,w,c = self.frames[0].get('img').shape
        self.writer = cv2.VideoWriter(
            vidpath,
            fourcc,
            FPS,
            (w,h)
            # W,H backawards sometimes
        )
        for f in self.frames:
            img = f.get('img')
            print "IMG: ", img.shape
            self.writer.write(img)
        self.writer.release()
        self.writer = None
        print "Done saving video: ", vidpath
        return vidpath


class SpeedImg(object):
    drawing = False
    sX = -1
    sY = -1
    eX = -1
    eY = -1
    motion = False
    state = "WAIT"
    minarea = 1000
    threshold = 20
    waiting = 100
    curobj = None
    show_t = 0
    run_t = 0
    display_queue = Queue(1)
    conv_q = Queue()
    outimg = None
    #display_queue = deque(maxlen=1)

    def __init__(
            self, 
            url, 
            do_display=True, 
            FOV=53, 
            DISTANCE=44,
            datastore=ShelveStore
        ):

        #self.cam = cv2.VideoCapture(url)
        self.datastore = datastore()
        self.datastore.start()
        self.cam_s = CamStream(url)
        self.cam_s.start()
        self.do_display = do_display
        if self.do_display:
            print "Will display"
            cv2.namedWindow('cam')
            cv2.setMouseCallback('cam', self.draw_rect)

        print "Prime the camera.."
        for i in xrange(30):
            self.cam_s.read()
        print "Read"
        self.img = self.cam_s.read()
        #self.display_queue.put(self.img)
        #img = self.cap()
        h,w,c = self.img[1].shape
        print "IMAGE SHAPE: %sx%s" % (h,w)

        self.fpp_lr = self.calc_ftpp(FOV, DISTANCE, w)
        self.fpp_rl = self.calc_ftpp(FOV, DISTANCE+11, w)

        print "FPP_LR:", self.fpp_lr
        print "FPP_RL:", self.fpp_rl

        self.load()
        self.running = True

    #def __del__(self):
    #    self.stop()
  
    def calc_ftpp(self, fov, distance, imgw):
        frame_width_ft = 2*(math.tan(math.radians(fov*0.5))*distance)
        ftperpixel = frame_width_ft / float(imgw)
        return ftperpixel

    def load(self):
        db = shelve.open('pyspeed.db')
        try:
            if db.has_key('data'):
                print "Loading settings...."
                data = db['data']
                self.sX = data.get('sX')
                self.sY = data.get('sY')
                self.eX = data.get('eX')
                self.eY = data.get('eY')
                self.width = self.eX - self.sX
                self.height = self.eY - self.sY
                self.baseline_img = self.check_img()
                #print self.baseline_img
                #cv2.imshow('baseline', self.baseline_img)
        finally:
            db.close()

    def save(self):
        db = shelve.open('pyspeed.db')
        try:
            data = {}
            data['sX'] = self.sX
            data['sY'] = self.sY
            data['eX'] = self.eX
            data['eY'] = self.eY
            db['data'] = data
            print "Saved settings."
        finally:
            db.close()

    def draw_rect(self, event, x, y, flags, param):
        #print "draw_rect:", x, y 
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.baseline_img = None
            self.sX = x
            self.sY = y
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.eX = x
            self.eY = y
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.eX = x
            self.eY = y

            if self.sX > self.eX:
                tX = self.sX
                self.sX = self.eX
                self.eX = tX
            self.width = self.eX - self.sX
            
            if self.sY > self.eY:
                tY = self.sY
                self.sY = self.eY
                self.eY = tY
            self.height = self.eY - self.sY

            self.baseline_img = self.check_img()
            #cv2.imshow('baseline', self.baseline_img)

            print "RECT: (%s,%s) x (%s,%s) " % (self.sX,self.sY,self.eX,self.eY)    
            self.save()

    def check_img(self):
        gray = self.img[1][self.sY:self.eY,self.sX:self.eX]
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (15,15), 0)
        return gray

    def compare(self):
        timestamp = self.img[0]
        
        img = self.check_img()

        frameDelta = cv2.absdiff(img, cv2.convertScaleAbs(self.baseline_img))
        thresh = cv2.threshold(frameDelta, self.threshold, 255, cv2.THRESH_BINARY)[1]
        # Dilate seems to take a lot of CPU
        thresh = cv2.dilate(thresh, None, iterations=3)

        if self.state == "DONE":
            # Finished tracking, clear out frames 
            ret = self.curobj.update(-1, -1, timestamp, self.img[1])
            # Combine the images
            self.outimg = self.catimg([self.img[1], thresh, self.baseline_img])

            self.endcounter += 1
            if self.endcounter >= FPS:
                self.state = "WAIT"
                vidpath = self.curobj.save_vid()
                self.conv_q.put(vidpath)
                vidname = "ps_%s_%.0f.webm" % (
                    self.curobj.init_time.strftime("%Y%m%d_%H%M%S"),
                    self.curobj.altmph
                )
                self.datastore.save(
                        self.curobj.init_time, 
                        self.curobj.altmph, 
                        self.curobj.imgname, 
                        vidname
                ) 
                print "Remove curobj"
                self.curobj.close()
                del self.curobj
            return

        (cnts, h) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        #cv2.drawContours(inimg, cnts, -1, (0,0,255), 3)

        self.motion = False
        biggest_area = 0
        biggest = (0,0,0,0)
        for c in cnts:

            ret = cv2.boundingRect(c)
            (x,y,w,h) = ret
            
            found_area = w*h
            if(found_area > self.minarea) and (found_area > biggest_area):
                biggest_area = found_area
                biggest = ret
                self.motion = True

        if self.motion:
            print "MOTION"
            (x,y,w,h) = biggest
            cv2.rectangle(
                self.img[1], 
                (self.sX+x,self.sY+y), 
                (self.sX+x+w,self.sY+y+h), 
                (0,0,255), 
                2
            )

            print "BIGGEST:", biggest, self.state
            #print "FOUND AREA:", biggest_area
            #self.baseline_img = self.check_img()
            if self.state == "WAIT":
                
                if self.curobj is not None:
                    print "Remove curobj"
                    self.curobj.close()
                    del self.curobj

                self.curobj = TrackObj(
                        x,
                        w,
                        self.width, 
                        timestamp, 
                        self.img[1],
                        self.fpp_lr,
                        self.fpp_rl
                )

                if self.curobj.direction == "INVALID":
                    self.state = "WAIT"
                    self.waiting += 5
                else:    
                    self.state = "TRACK"
                    self.waiting = 0
                    print "Begin Tracking..."

            elif self.state == "TRACK":

                # Save every tracked event
                ret = self.curobj.update(x, w, timestamp, self.img[1])

                if ret == "DONE":
                    self.state = "DONE"
                    self.endcounter = 0
                    #self.state = "WAIT"
                    #self.curobj.save_img()
                    #mph = self.curobj.mphs[-1]
                    self.curobj.save_img()
                    #self.save_img(self.img[1], thresh, self.baseline_img)
                elif ret == "NONE" or ret == "JUNK" or ret == "INVALID":
                    self.waiting += 5
                else:
                    self.waiting = 0

            else:
                self.waiting += 5

        else:
            # No Motion, so reset tracking
            self.state = "WAIT"
            self.waiting += 1

        if self.waiting > 200:
            print "Resetting background image"
            self.baseline_img = img
            self.waiting = 0
            self.state = "WAIT"
        
        # Combine the images
        self.outimg = self.catimg([self.img[1], thresh, self.baseline_img])


    def save_img(self, img, thresh, baseline):
        mph = self.curobj.altmph
        timestamp = self.curobj.init_time
        outimg = self.catimg([img, thresh, baseline])
        self.imgname = "ps_%s_%.0f.jpg" % (
            timestamp.strftime("%Y%m%d_%H%M%S"),
            mph
        )
        cv2.imwrite(
            os.path.join('data', self.imgname),
            outimg
        )

    def catimg(self, imgs):
        hlist = [ x.shape[0] for x in imgs ]
        wlist = [ x.shape[1] for x in imgs ]

        outimg = numpy.zeros((sum(hlist), max(wlist), 3), numpy.uint8)
        h=0
        for i in imgs:
            try:
                ih,iw,ic = i.shape
            except ValueError:
                i = cv2.cvtColor(i, cv2.cv.CV_GRAY2BGR)
                ih,iw,ic = i.shape
            outimg[h:ih+h, :iw, :3] = i
            h+=ih

        return outimg
    
    def start(self):
        print "Starting SpeedImg..."
        self.run_t = Thread(target=self.run, args=())
        self.run_t.start()
        self.conv_t = Thread(target=self.convert, args=())
        self.conv_t.start()
        if self.do_display:
            self.show_t = Thread(target=self.show, args=())
            self.show_t.start()
        return self

    def run(self):
        counter = 0
        DISPFPS = 6
        targetc = FPS/DISPFPS
        while self.running:
            try: 
                self.img = self.cam_s.read()
            except Empty:
                continue
            if self.baseline_img is not None:
                self.compare()
                cv2.rectangle(self.img[1],(self.sX,self.sY),(self.eX,self.eY),(0,255,0),2)
                outimg = self.outimg
            else:
                outimg = self.img[1]
            
            counter += 1
            if counter >= targetc: 
                counter = 0
                try:
                    self.display_queue.put_nowait(outimg)
                except Full:
                    pass
        print "Exiting SpeedImg loop"

    def show(self):
        while self.running:
            #img = self.display_queue.pop()
            try:
                img = self.display_queue.get(True,5)
            except Empty:
                continue
            if self.drawing:
                cv2.rectangle(img,(self.sX,self.sY),(self.eX,self.eY),(255,0,0),2)
            cv2.imshow('cam', img)
            if cv2.waitKey(1) == 27:
                self.running = False
            time.sleep(0.05)
        print "Exiting display loop"

    def convert(self):
        while self.running:

            # Check thermal load
            with open('/sys/class/thermal/thermal_zone0/temp') as h:
                temp = int(h.read())
            if temp >= 79500:
                print "Too hot (%s C), wait a few" % (temp/1000)
                time.sleep(5)
                continue

            try:
                vidpath = self.conv_q.get(True,5)
            except Empty:
                continue
            vidname = os.path.basename(vidpath)
            vid,ext = os.path.splitext(vidname)
            ret = subprocess.call(
                "avconv -i %s -vcodec libvpx -crf 5 -b:v 1M data/%s.webm & PID=$!; cpulimit -l 50 -p $PID; wait $PID" % (vidpath, vid), shell=True
            )
            os.unlink(vidpath)
            print "Converted %s to %s ret:(%s)" % (vidpath, "%s.webm" % vid, ret)
        print "Exiting convert loop"

    def stop(self):
        self.running = False
        self.cam_s.stop()

    def wait(self):
        if self.run_t:
            self.run_t.join()
        if self.conv_t:
            self.conv_t.join()
        if self.show_t:
            self.show_t.join()
        self.datastore.stop()
        if self.do_display:
            print "Stop displays"
            cv2.destroyAllWindows()
        print "Wait complete"

def main():
    si = SpeedImg(0)
    si.start()
    si.wait()

if __name__ == "__main__":
    main()
