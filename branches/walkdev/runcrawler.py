# -*- coding: latin-1 -*-
# Copyright (c) 2009 Australian Government, Department of Environment, Heritage, Water and the Arts
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

'''
Script to run the MetaGeta Metadata Crawler

Contains code to show GUI to gather input arguments when none are provided
To run, call the eponymous batch file/shell script which sets the required environment variables

Usage::
    runcrawler.bat/sh -d dir -x xls -s shp -l log {-o} {--nogui} {--debug}

@newfield sysarg: Argument, Arguments
@sysarg: C{-d [dir]}: Directory to to recursively search for imagery
@sysarg: C{-x [xls]}: MS Excel spreadsheet to wrtite metadata to
@sysarg: C{-s [shp]}: ESRI Shapefile to write extents to
@sysarg: C{-l [log]}: Log file to write messages to
@sysarg: C{-o}      : Generate overview (quicklook/thumbnail) images")
@sysarg: C{--nogui} : Don't show the GUI progress dialog")
@sysarg: C{--debug} : Turn debug output on
'''

import sys, os, re,time

import progresslogger
import formats
import geometry
import utilities
import crawler

def main(dir,xls,shp,log, getovs=False, nogui=True, debug=False): 
    """ Run the Metadata Crawler

        @type  dir:    C{str}
        @param dir:    The directory to start the metadata crawl.
        @type  xls:    C{str}
        @param xls:    Excel spreadsheet to write metadata to
        @type  shp:    C{str}
        @param shp:    Shapefile to write extents to
        @type  log:    C{str}
        @param log:    Log file
        @type  getovs: C{boolean}
        @param getovs: Generate overview (quicklook/thumbnail) images
        @type  nogui:  C{boolean}
        @param nogui:  Don't show the GUI progress dialog
        @type  debug:  C{boolean}
        @param debug:  Turn debug output on
        @return:  C{None}
    """
    xls = utilities.checkExt(xls, ['.xls']).encode('latin-1')
    shp = utilities.checkExt(shp, ['.shp']).encode('latin-1')
    log = utilities.checkExt(shp, ['.log', '.txt']).encode('latin-1')

    format_regex  = formats.format_regex
    format_fields = formats.fields
    
    if debug:
        level=progresslogger.DEBUG
        formats.debug=debug
        crawler.debug=debug
    else:level=progresslogger.INFO
    
    windowicon=os.environ['CURDIR']+'/lib/wm_icon.ico'
    try:pl = progresslogger.ProgressLogger('MetadataCrawler',logfile=log, logToConsole=True, logToFile=True, logToGUI=nogui, level=level, windowicon=windowicon, callback=exit)
    except:pl = progresslogger.ProgressLogger('MetadataCrawler',logfile=log, logToConsole=True, logToFile=True, logToGUI=nogui, level=level, callback=exit)

    #pl.debug('%s %s %s %s %s %s' % (dir,xls,shp,log,nogui,debug))
    pl.debug(' '.join(sys.argv))

    try:
        ExcelWriter=utilities.ExcelWriter(xls,format_fields.keys())
        ShapeWriter=geometry.ShapeWriter(shp,format_fields,overwrite=True)
    except Exception,err:
        pl.error('%s' % utilities.ExceptionInfo())
        pl.debug(utilities.ExceptionInfo(10))
        del pl
        time.sleep(0.5)# So the progresslogger picks up the error message before this python process exits.
        sys.exit(1)

    pl.info('Searching for files...')
    now=time.time()
    Crawler=crawler.Crawler(dir)
    pl.info('Found %s files...'%Crawler.filecount)

    #Loop thru dataset objects returned by Crawler
    for ds in Crawler:
        try:
            pl.debug('Attempting to open %s'%Crawler.file)
            md=ds.metadata
            geom=ds.extent
            fi=ds.fileinfo
            fi['filepath']=utilities.convertUNC(fi['filepath'])
            fi['filelist']=','.join(utilities.convertUNC(ds.filelist))
            md.update(fi)
            pl.info('Extracted metadata from %s, %s of %s files remaining' % (Crawler.file,len(Crawler.files),Crawler.filecount))
            try:
                if getovs:
                    qlk=os.path.join(os.path.dirname(xls),'%s.%s.qlk.jpg'%(fi['filename'],fi['guid']))
                    thm=os.path.join(os.path.dirname(xls),'%s.%s.thm.jpg'%(fi['filename'],fi['guid']))
                    qlk=ds.getoverview(qlk, width=800)
                    thm=ds.getoverview(thm, width=150)
                    md['quicklook']=utilities.convertUNC(qlk)
                    md['thumbnail']=utilities.convertUNC(thm)
                    pl.info('Generated overviews from %s' % Crawler.file)
            except Exception,err:
                pl.error('%s\n%s' % (Crawler.file, utilities.ExceptionInfo()))
                pl.debug(utilities.ExceptionInfo(10))
            try:
                ExcelWriter.WriteRecord(md)
            except Exception,err:
                pl.error('%s\n%s' % (Crawler.file, utilities.ExceptionInfo()))
                pl.debug(utilities.ExceptionInfo(10))
            try:
                ShapeWriter.WriteRecord(geom,md)
            except Exception,err:
                pl.error('%s\n%s' % (Crawler.file, utilities.ExceptionInfo()))
                pl.debug(utilities.ExceptionInfo(10))


            pl.updateProgress(newMax=Crawler.filecount)
        except Exception,err:
            pl.error('%s\n%s' % (Crawler.file, utilities.ExceptionInfo()))
            pl.debug(utilities.ExceptionInfo(10))
    then=time.time()
    pl.debug(then-now)
    #Check for files that couldn't be opened
    for file,err,dbg in Crawler.errors:
       pl.error('%s\n%s' % (file, err))
       pl.debug(dbg)

    if Crawler.filecount == 0:
        pl.info("No data found")
        pl.updateProgress(newMax=1) #Just so the progress meter hits 100%
    else:
        pl.updateProgress(newMax=1) #Just so the progress meter hits 100%
        pl.info("Metadata extraction complete!")

    del pl
    del ExcelWriter
    del ShapeWriter
def exit(): 
    '''Force exit after closure of the ProgressBar GUI'''
    os._exit(0)

#========================================================================================================
#========================================================================================================
if __name__ == '__main__':
    import optparse,icons,getargs
    description='Run the metadata crawler'
    parser = optparse.OptionParser(description=description)
    opt=parser.add_option('-d', dest="dir", metavar="dir",help='The directory to crawl')
    opt.icon=icons.dir_img
    opt.argtype=getargs.DirArg
    
    opt=parser.add_option("-x", dest="xls", metavar="xls",help="Output metadata spreadsheet")
    opt.argtype=getargs.FileArg
    opt.icon=icons.xls_img
    opt.filter=[('Excel Spreadsheet','*.xls')]

    opt=parser.add_option("-u", "--update", action="store_true", dest="update",default=False,
                      help="Update existing spreadsheet")
    opt.argtype=getargs.BoolArg

    opt=parser.add_option("-s", dest="shp", metavar="shp",help="Output shapefile")
    opt.argtype=getargs.FileArg
    opt.icon=icons.shp_img
    opt.filter=[('ESRI Shapefile','*.shp')]

    opt=parser.add_option("-l", dest="log", metavar="log",help="Log file")
    opt.argtype=getargs.FileArg
    opt.icon=icons.log_img
    opt.filter=[('Log File',('*.txt','*.log'))]
    
    opt=parser.add_option("-o", "--overviews", action="store_true", dest="ovs",default=False,
                      help="Generate overview images")
    opt.argtype=getargs.BoolArg
    opt=parser.add_option("--debug", action="store_true", dest="debug",default=False,
                      help="Turn debug output on")
    opt=parser.add_option("--nogui", action="store_true", dest="nogui", default=False,
                      help="Don't show the GUI progress dialog")

    optvals,argvals = parser.parse_args()
    for opt in parser.option_list:
        if 'argtype' in vars(opt):
            opt.default=vars(optvals)[opt.dest]
    if not optvals.dir or not optvals.log or not optvals.shp or not optvals.xls:
        args=getargs.GetArgs(*[opt for opt in parser.option_list if 'argtype' in vars(opt)])
        if args:
            main(args.dir,args.xls,args.update,args.shp,args.log,args.ovs,optvals.nogui,optvals.debug)
    else:
        main(optvals.dir,optvals.xls,optvals.update,optvals.shp,optvals.log,optvals.ovs,optvals.nogui,optvals.debug)
