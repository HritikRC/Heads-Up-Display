# Web streaming example
# Source code from the official PiCamera package
# http://picamera.readthedocs.io/en/latest/recipes2.html#web-streaming

import io
import picamera
import logging
import socketserver
from threading import Condition
from http import server

PAGE="""\
<html>
<head>
<title>HUD</title>
<style>
    #img1 {
        position : absolute;
        top : 25%;
	left : 0px;
	transform : rotate(180deg);
	width:50%;
    }
    #img2 {
        position : absolute;
        top : 25%;
        left : 50%;
        transform : rotate(180deg);
        width:50%;
    }
    body {
        margin: 0;
        background: black;
    }
    #hud1 {
        position : absolute;
        top : 25%;
	left : 0px;
	width:50%;
	z-index: 10;
    }
    #hud2 {
        position : absolute;
        top : 25%;
        left : 50%;
        width:50%;
        z-index: 11;
    }
    canvas {
        position: absolute;
        z-index: 12;
        top: 25%;
        left:0px;
    }
</style>
</head>
<body>
<script src = "p5.min.js"></script>
<script src = "ml5.min.js"></script>
<img src="stream.mjpg" width="640" height="480" id = "img1">
<img src="stream.mjpg" width="640" height="480" id = "img2">
<img src = "hud.png" id = "hud1" width="640" height="480">
<img src = "hud.png" id = "hud2" width="640" height="480">
<script>
    var preview = document.getElementById("img1");
    let detector;
    let detections = [];
    function modelLoaded(){
      console.log("Coco-SSD model loaded");
      alert("Coco-SSD model loaded")
    }
    function preload() {
      detector = ml5.objectDetector('cocossd', modelLoaded);
    }

    function gotDetections(error, results) {
      if (error) {
        console.error(error);
      }
      detections = results;
    }
    
    function setup() {
      createCanvas(preview.width * 2, preview.height);
      detector.detect(preview, gotDetections);
    }

    function draw() {
      clear();
      for (let i = 0; i < detections.length; i++) {
        let object = detections[i];
        stroke(0, 0, 220);
        strokeWeight(4);
        noFill();
        var x = width - (object.x + object.width);
        var y = height - (object.y + object.height);
        rect(x, y, object.width, object.height);
        rect(x - preview.width, y, object.width, object.height);
        
        noStroke();
        fill(255);
        textSize(24);
        text(object.label, x + 10, y + 24);
        text(object.label, x + 10 - preview.width, y + 24);
      }
      if(frameCount % 120 == 0){
        detector.detect(preview, gotDetections);
      }
    }
</script>
</body>
</html>
"""

class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/hud.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            f = open("hud.png", "rb")
            for line in f:
                self.wfile.write(line)
            return
        elif self.path == "/p5.min.js":
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            f = open("p5.min.js", "rb")
            for line in f:
                self.wfile.write(line)
            return
        elif self.path == "/ml5.min.js":
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            f = open("ml5.min.js", "rb")
            for line in f:
                self.wfile.write(line)
            return
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

with picamera.PiCamera(resolution='640x480', framerate=30) as camera:
    output = StreamingOutput()
    #Uncomment the next line to change your Pi's Camera rotation (in degrees)
    #camera.rotation = 90
    camera.start_recording(output, format='mjpeg')
    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        camera.stop_recording()
