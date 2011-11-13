#!/usr/bin/env python

#  single_serv.py -- an ad-hoc single file webserver
#  allows a count to be added on how many times the file can be downloaded

import os, sys, select, getopt, commands, urllib, BaseHTTPServer, SimpleHTTPServer

maxdownloads = 1
cpid = -1

# Function to guess the IP (as a string) - that can be reached from outside
def find_ip():
    os.environ["PATH"] = "/sbin:/usr/sbin:/usr/local/sbin:" + os.environ["PATH"]
    netstat = commands.getoutput("LC_MESSAGES=C netstat -rn")
    defiface = [i.split ()[-1] 
        for i in netstat.split ('\n')
            if i.split ()[0] == "0.0.0.0"]
    if not defiface:
        return None
    ifcfg = commands.getoutput ("LC_MESSAGES=C ifconfig "
                               + defiface[0]).split ("inet addr:")
    if len (ifcfg) != 2:
        return None
    ip_addr = ifcfg[1].split ()[0]

    # sanity check
    try:
        ints = [ i for i in ip_addr.split (".") if 0 <= int(i) <= 255]
        if len (ints) != 4:
            return None
    except ValueError:
        return None

    return ip_addr

   
# Main class implementing a HTTP-Requesthandler, that serves just a single
# file and redirects all other requests to this file (this passes the actual
# filename to the client).
# impossible to serve different files with different instances of this class.

class FileServHTTPRequestHandler (BaseHTTPServer.BaseHTTPRequestHandler):
    server_version = "maK's File Server"
    protocol_version = "HTTP/1.0"

    filename = "."

    def log_request (self, code='-', size='-'):
        if code == 200:
            BaseHTTPServer.BaseHTTPRequestHandler.log_request (self, code, size)


    def do_GET (self):
        global maxdownloads, cpid
        # Redirect any request to the filename of the file to serve.
        # This hands over the filename to the client.

        self.path = urllib.quote(urllib.unquote (self.path))
        location = "/" + urllib.quote(os.path.basename (self.filename))
        if os.path.isdir (self.filename):
            location += ".tar.gz"

        if self.path != location:
            txt = """\
                    <html>
                    <head><title>302 Found</title></head>
                    <body>302 Found <a href="%s">here</a>.</body>
                    </html>\n""" % location
            self.send_response (302)
            self.send_header ("Location", location)
            self.send_header ("Content-type", "text/html")
            self.send_header ("Content-Length", str (len (txt)))
            self.end_headers ()
            self.wfile.write (txt)
            return

        maxdownloads -= 1
        # let a separate process handle the actual download, so that
        # multiple downloads can happen simultaneously.

        cpid = os.fork ()
        if cpid == 0:
        # Child process
            size = -1
            datafile = None
         
            if os.path.isfile (self.filename):
                size = os.path.getsize (self.filename)
                datafile = open (self.filename)
            elif os.path.isdir (self.filename):
                os.environ['fileserv_dir'], os.environ['fileserv_file'] = os.path.split (self.filename)
                datafile = os.popen ('cd "$fileserv_dir";tar cfz - "$fileserv_file"')

            self.send_response (200)
            self.send_header ("Content-type", "application/octet-stream")
            if size >= 0:
                self.send_header ("Content-Length", size)
            self.end_headers ()

            while 1:
                if select.select ([datafile], [], [], 2)[0]:
                    c = datafile.read (1024)
                if c:
                    self.wfile.write (c)
                else:
                    datafile.close ()
                    return
               

def serve_files (filename, maxdown = 1, port = 8080):
    global maxdownloads
    
    maxdownloads = maxdown

    # We have to somehow push the filename of the file to serve to the
    # class handling the requests. This is an evil way to do this...

    FileServHTTPRequestHandler.filename = filename

    httpd = BaseHTTPServer.HTTPServer (('', port),
                                      FileServHTTPRequestHandler)

    ip = find_ip ()
    if ip:
        print "Now serving on http://%s:%s/" % (ip, httpd.server_port)

    while cpid != 0 and maxdownloads > 0:
        httpd.handle_request ()



def usage (errmsg = None):
    if errmsg:
        print >>sys.stderr, errmsg
        print >>sys.stderr
    print >>sys.stderr, "Usage: %s [-p <port>] [-c <count>] [file]" % sys.argv[0]
    print >>sys.stderr, "       %s [-p <port>] [-c <count>] -s\n" % sys.argv[0]
    print >>sys.stderr, "  serves a single file <count> times via http on port <port>."
    print >>sys.stderr, "  When -s is specified instead of a filename, fileserv distributes itself.\n"
    print >>sys.stderr, "  defaults: count = 1, port = 8080\n"
    sys.exit (1)



def main ():
    global cpid

    maxdown = 1
    port = 8080

    try:
        options, filenames = getopt.getopt (sys.argv[1:], "hsc:p:")
    except getopt.GetoptError, desc:
        usage (desc)

    for option, val in options:
        if option == '-c':
            try:
                maxdown = int (val)
                if maxdown <= 0:
                    raise ValueError
            except ValueError:
                usage ("invalid download count: %r. "
                        "Please specify an integer >= 0." % val)

        elif option == '-p':
            try:
                port = int (val)
            except ValueError:
                usage ("invalid port number: %r. Please specify an integer" % value)

        elif option == '-s':
            filenames.append (__file__)

        elif option == '-h':
            usage ()

        else:
            usage ("Unknown option: %r" % option)

    if len (filenames) == 1:
        filename = os.path.abspath (filenames[0])
    else:
        usage ("Can only serve single files/directories.")

    if not os.path.exists (filename):
        usage ("%s: No such file or directory" % filenames[0])

    if not (os.path.isfile (filename) or os.path.isdir (filename)):
        usage ("%s: Neither file nor directory" % filenames[0])

    serve_files (filename, maxdown, port)

    # wait for child processes to terminate
    if cpid != 0:
        try:
            while 1:
                os.wait ()
        except OSError:
            pass

if __name__=='__main__':
    try:
        main ()
    except KeyboardInterrupt:
        pass

