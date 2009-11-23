'''
Metadata driver for ESRI GRIDs
==============================
@see:Format specification
    U{http://home.gdal.org/projects/aigrid/aigrid_format.html}
'''

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

format_regex=[r'hdr\.adf$']
'''Regular expression list of file formats'''

#import base dataset modules
import __default__

# import other modules (use "_"  prefix to import privately)
import sys, os,glob

class Dataset(__default__.Dataset): 
    '''Subclass of __default__.Dataset class so we get a load of metadata populated automatically'''
    def __init__(self,f):
        ''' Set the filename from <path>\hdr.adf to <path>'''
        grddir=os.path.dirname(f)
        self.fileinfo['filepath']=grddir
        self.fileinfo['filename']=os.path.basename(grddir)
        self.filelist=glob.glob(grddir+'*')
        self.filelist.extend(glob.glob(grddir+'/*'))
    def __getmetadata__(self):
        '''Read Metadata for a ESRI GRID dataset'''
        __default__.Dataset.__getmetadata__(self, self.fileinfo['filepath']) #autopopulate basic metadata
        if self.metadata['compressiontype']=='Unknown':self.metadata['compressiontype']='RLE'