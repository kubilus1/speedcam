#!/usr/bin/python

from flask import Flask, jsonify, render_template, Response, request, redirect, url_for, g
from pyspeed import SpeedImg
import cv2
from multiprocessing import Lock
from threading import Thread
import time
import json
import os
import sys
from Queue import Empty
from dateutil import parser
from redis_store import RedisStore


#CAM = "http://192.168.1.135:8080/video"
CAM = 0

mutex = Lock()

app = Flask(__name__)

si = None
frame = None
ff_t = None
running = True

#def del_time(timestamp):
#    global si
#    print "Delete ", timestamp
#    si.datastore.rm(timestamp)


#@flask_app.context_processor
#def ps_utility_processor():
#    return dict(
#        del_time=del_time,
#    )

@app.route('/speeddata')
@app.route('/speeddata/<data>/')
def speeddata(lastid=None):
    global si
    lastid = request.args.get('lastid')
    items = si.datastore.list()
    items.sort()
    outitems = []

    start = False
    if lastid is None:
        start = True

    for item in items:
        tid = item[0]
        data = item[1]
       
        timestamp = data.get('tid')
        if start:
            ts = parser.parse(timestamp)
            t = int(time.mktime(ts.timetuple())*1000)
            mph = data['mph']
            if mph < 20:
                color = "green"
            elif mph >= 20 and mph < 28:
                color = "yellow"
            elif mph >= 28 and mph < 35:
                color = "orange"
            else:
                color = "red"
            data['color'] = color
            data['t'] = t
            data['id'] = tid

            if data.has_key('filename'):
                fn = data.get('filename')
                data['imgname'] = fn
            elif data.has_key('vidname'):
                fn = data.get('vidname')

            n,e = os.path.splitext(fn)
            data['vidname'] = "%s.%s" % (n, 'webm')

            outitems.append(data)

        if timestamp == lastid:
            start = True

    return jsonify(items=outitems)


@app.route('/')
def index():
    outitems = []
    #print outitems
    return render_template('index.html', items=outitems)

@app.route('/del_time', methods=['POST'])
def del_time():
    print "Del_time"
    if request.method != 'POST':
        print "NOT POST", request.method
        return redirect(url_for('index'))

    timestamp = request.form['timestamp']
    global si
    print "Delete ", timestamp
    si.datastore.rm(timestamp)
    #return redirect(url_for('index'))
    return 'deleted'

import random

anid=0
@app.route('/ajaxtest')
def ajaxtest():
    global anid
    print "Ajaxtest called"
    time.sleep(2)
    anid+=1
    tdata = [{'id':anid,'col1':random.randint(1,20), 'col2':
        random.randint(1,20)}]
    return jsonify(items=tdata)
    #return Response(gen(si),
    #                mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/ajax')
def ajax():
    return render_template('ajax.html')

    
@app.route('/video_feed')
def video_feed():
    global si
    if si is None:
        print "NO SI"
        return
    return Response(gen(si),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

    
def gen(si):
    global frame
    global mutex
    global running
    if si is None:
        print "NO SI"
        return
    while running:
        time.sleep(0.1)
        #frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

def frame_factory():
    global frame
    global mutex
    while running:
        try:
            #img = si.display_queue.pop()
            img = si.display_queue.get(True, 2)
        except Empty:
            continue
       
        ret, jpg = cv2.imencode('.jpg', img)
        #f = jpg.tobytes()
        f = jpg.tostring()
        frame = f
    print "Stopping frame_factory"

def app_main():
    global si
    global running
    global ff_t
    
    if si is None:
        si = SpeedImg(CAM, False, datastore=RedisStore)
        si.start()
    
    ff_t = Thread(target=frame_factory)
    ff_t.start()

    app.run(host='0.0.0.0', debug=True, threaded=True, use_reloader=False)

    print "Stopping...."
    running = False
    ff_t.join()
    si.stop()
    si.wait()
    si = None
    del si
    print "SpeedImg stopped.  Exiting"

if __name__ == "__main__":
    app_main()
    sys.exit(0)
