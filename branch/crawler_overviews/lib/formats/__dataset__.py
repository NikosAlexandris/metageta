'''
Base Dataset class
==================
Defines the metadata fields and populates some basic info
'''

import os,time,sys,glob,time,math
import UserDict 
import utilities, geometry, uuid

#Import fieldnames
import __fields__

try:
    from osgeo import gdal
    from osgeo import gdalconst
    from osgeo import osr
    from osgeo import ogr
except ImportError:
    import gdal
    import gdalconst
    import osr
    import ogr
class Dataset(object):
    '''A base Dataset class'''
    def __new__(self,f):
        ##Initialise the class object
        self=object.__new__(self)
        
        self._gdaldataset=None
        self._metadata={}
        self._extent=[]
        self._filelist=[]
        
        ##Populate some basic info
        self.fileinfo=utilities.FileInfo(f)
        #self.guid=str(uuid.uuid4())
        #Make the guid reproducible based on filename
        self.guid=str(uuid.uuid3(uuid.NAMESPACE_DNS,f))
        self.fileinfo['filename']=os.path.basename(f)
        self.fileinfo['filepath']=f
        self.fileinfo['guid']=self.guid
        self.fileinfo['metadatadate']=time.strftime(utilities.dateformat+utilities.timeformat,time.localtime())

        ##Initialise the fields
        self.fields=idict(__fields__.fields)#We don't want any fields added/deleted

        return self

    # ==================== #
    # Public Class Methods
    # ==================== #
    #def getoverview(self,*args,**kwargs):
    #    '''In case subclasses don't override...'''
    #    pass
##    def getoverview(self,outfile=None,width=800,format='JPG'): 
##        '''
##        Generate overviews for generic imagery
##
##        @type  outfile: string
##        @param outfile: a filepath to the output overview image. If supplied, format is determined from the file extension
##        @type  width:   integer
##        @param width:   image width
##        @type  format:  string
##        @param format:  format to generate overview image, one of ['JPG','PNG','GIF','BMP','TIF']. Not required if outfile is supplied.
##        @return:        filepath (if outfile is supplied)/binary image data (if outfile is not supplied)
##        '''
##        import overviews
##
##        #mapping table for file extension -> GDAL format code
##        formats={'JPG':'JPEG', #JPEG JFIF (.jpg)
##                 'PNG':'PNG',  #Portable Network Graphics (.png)
##                 'GIF':'GIF',  #Graphics Interchange Format (.gif)
##                 'BMP':'BMP',  #Microsoft Windows Device Independent Bitmap (.bmp)
##                 'TIF':'GTiff' #Tagged Image File Format/GeoTIFF (.tif)
##                }
##
##        if outfile:format=os.path.splitext(outfile)[1].replace('.','') #overrides "format" arg if supplied
##        ovdriver=gdal.GetDriverByName(formats.get(format.upper(), 'JPEG')) #Get format code, default to 'JPEG' if supplied format doesn't match the predefined ones...
##        md=self.metadata
##        ds=self._gdaldataset
##        if not ds:raise AttributeError, 'No GDALDataset object available, overview image can not be generated'
##
##        nodata=md['nodata']
##        nbands=md['nbands']
##        cols=md['cols']
##        rows=md['rows']
##
##        #Default stretch type and additional args
##        stretch_type='NONE'
##        stretch_args=[]
##
##        if nbands < 3:
##            #Assume greyscale
##            bands=[1]
##        elif nbands == 3:
##            #Assume RGB 
##            bands=[1,2,3]
##        elif nbands >= 4:
##            bands=[3,2,1]
##            #test if any bands have R,G or B color interps
##            for i in range(1,nbands+1):
##                gci=ds.GetRasterBand(i).GetRasterColorInterpretation()
##                if   gci == gdal.GCI_RedBand:
##                    bands[0]=i
##                elif gci == gdal.GCI_GreenBand:
##                    bands[1]=i
##                elif gci == gdal.GCI_BlueBand:
##                    bands[2]=i
##            if bands==[3,2,1]:#Assume unstretched multispectral B,G,R,etc... 
##                stretch_type='PERCENT'
##                stretch_args=[2,98]
##
##        vrtcols=width
##        vrtrows=int(math.ceil(width*float(rows)/cols))
##        vrtxml=overviews.stretch(stretch_type,vrtcols,vrtrows,ds,bands,nodata,*stretch_args)
##        vrtds=geometry.OpenDataset(vrtxml)
##        if outfile:
##            ovdriver.CreateCopy(outfile, vrtds)
##        else:
##            from tempfile import mkstemp
##            fd,fn=mkstemp(suffix='.'+format.lower(), prefix=self.fileinfo['guid'])
##            ovdriver.CreateCopy(fn, vrtds)
##            outfile=os.fdopen(fd).read()
##            os.unlink(fn)
##        return outfile
    def getoverview(self,outfile=None,width=800,format='JPG'): 
        '''
        Generate overviews for generic imagery

        @type  outfile: string
        @param outfile: a filepath to the output overview image. If supplied, format is determined from the file extension
        @type  width:   integer
        @param width:   image width
        @type  format:  string
        @param format:  format to generate overview image, one of ['JPG','PNG','GIF','BMP','TIF']. Not required if outfile is supplied.
        @return:        filepath (if outfile is supplied)/binary image data (if outfile is not supplied)
        '''
        import overviews

        md=self.metadata
        ds=self._gdaldataset
        if not ds:raise AttributeError, 'No GDALDataset object available, overview image can not be generated'

        nodata=md['nodata']
        nbands=md['nbands']
        cols=md['cols']
        rows=md['rows']

        #Default stretch type and additional args
        stretch_type='NONE'
        stretch_args=[]

        if nbands < 3:
            #Assume greyscale
            bands=[1]
        elif nbands == 3:
            #Assume RGB 
            bands=[1,2,3]
        elif nbands >= 4:
            bands=[3,2,1]
            #test if any bands have R,G or B color interps
            for i in range(1,nbands+1):
                gci=ds.GetRasterBand(i).GetRasterColorInterpretation()
                if   gci == gdal.GCI_RedBand:
                    bands[0]=i
                elif gci == gdal.GCI_GreenBand:
                    bands[1]=i
                elif gci == gdal.GCI_BlueBand:
                    bands[2]=i
            if bands==[3,2,1]:#Assume unstretched multispectral B,G,R,etc... 
                stretch_type='PERCENT'
                stretch_args=[2,98]

        return overviews.getoverview(ds,outfile,width,format,bands,stretch_type,stretch_args)

    # ===================== #
    # Private Class Methods
    # ===================== #
    def __getfilelist__(self,*args,**kwargs):
        '''Get all files that have the same name (sans .ext), or are related according to gdalinfo
            special cases may be handled separately in their respective format drivers'''
        f=self.fileinfo['filepath']
        files=glob.glob(os.path.splitext(f)[0]+'.*')
        if os.path.exists(os.path.splitext(f)[0]):files.append(os.path.splitext(f)[0])
        hdr_dir=os.path.join(os.path.split(f)[0], 'headers') #Cause ACRES creates a 'headers' directory
        if os.path.exists(hdr_dir):
            files.extend(glob.glob(os.path.join(hdr_dir,'*')))

        if self._gdaldataset:
            files.extend(self._gdaldataset.GetFileList())

        self._filelist=list(set(utilities.fixSeparators(files))) #list(set([])) filters out duplicates
        
    def __getmetadata__(self,*args,**kwargs):
        '''In case subclasses don't override...'''
        pass
    def __init__(self,*args,**kwargs):
        '''In case subclasses don't override...'''
        pass 


    # ================ #
    # Class Properties
    # ================ #
    def __classproperty__(fcn):
        '''The class property decorator function'''
        try:return property( **fcn() )
        except:pass

    @__classproperty__
    def metadata():
        '''The metadata property.'''

        def fget(self):
            if not self._metadata:
                #Initialise the metadata idict
                for field in self.fields:
                    if field in self.fileinfo:self._metadata[field]=self.fileinfo[field]
                    else:self._metadata[field]=''
                self._metadata=idict(self._metadata) #We don't want any fields added/deleted
                self.__getmetadata__()
            return self._metadata

        def fset(self, *args, **kwargs):
            if len(args) == 1:raise AttributeError('Can\'t overwrite metadata property')
            elif len(args) == 2:self._metadata[args[0]] = args[1]

        def fdel(self):pass #raise AttributeError('Can\'t delete metadata property')???????

        return locals()

    @__classproperty__
    def extent():
        '''The extent property.'''

        def fget(self, *args, **kwargs):
            if not self._extent:self.__getmetadata__() #extent gets set during metadata extraction
            return self._extent

        def fset(self, *args, **kwargs):
            if len(args) == 1:self._extent = args[0]
            elif len(args) == 2:self._extent[args[0]] = args[1]

        def fdel(self, *args, **kwargs):pass

        return locals()

    @__classproperty__
    def filelist():
        '''The filelist property.'''

        def fget(self):
            if not self._filelist:self.__getfilelist__()
            return self._filelist

        def fset(self, *args, **kwargs):
            if len(args) == 1:self._filelist = args[0]
            elif len(args) == 2:self._filelist[args[0]] = args[1]

        def fdel(self):pass

        return locals()

class idict(UserDict.IterableUserDict):
    '''The idict class. An immutable dictionary.
       modified from http://code.activestate.com/recipes/498072/
       to inherit UserDict.IterableUserDict
    '''
    def __setitem__(self, key, val):
        if key in self.data.keys():
            self.data[key]=val
        else:raise KeyError("Can't add keys")

    def __delitem__(self, key):
        raise KeyError("Can't delete keys")

    def pop(self, key):
        raise KeyError("Can't delete keys")

    def popitem(self):
        raise KeyError("Can't delete keys")