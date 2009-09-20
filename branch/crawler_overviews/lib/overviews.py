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
import geometry,vrtutils
import sys, os.path, os, csv, re, struct, math, glob, string, time,shutil, tempfile

def getoverview(ds,outfile,width,format,bands,stretch_type,*stretch_args):
    '''
    Generate overviews for imagery

    @type  ds:      GDALDataset
    @param ds:      a GDALDataset object
    @type  outfile: string
    @param outfile: a filepath to the output overview image. If supplied, format is determined from the file extension
    @type  width:   integer
    @param width:   output image width
    @type  format:  string
    @param format:  format to generate overview image, one of ['JPG','PNG','GIF','BMP','TIF']. Not required if outfile is supplied.
    @type  bands:   list
    @param bands:   list of band numbers (base 1) in processing order - e.g [3,2,1]
    @type  stretch_type:  string
    @param stretch_type:  format to generate overview image, one of ['JPG','PNG','GIF','BMP','TIF']. Not required if outfile is supplied.
    @type  stretch_args:  string
    @param stretch_args:  format to generate overview image, one of ['JPG','PNG','GIF','BMP','TIF']. Not required if outfile is supplied.

    @return:        filepath (if outfile is supplied)/binary image data (if outfile is not supplied)
    '''
    #mapping table for file extension -> GDAL format code
    formats={'JPG':'JPEG', #JPEG JFIF (.jpg)
             'PNG':'PNG',  #Portable Network Graphics (.png)
             'GIF':'GIF',  #Graphics Interchange Format (.gif)
             'BMP':'BMP',  #Microsoft Windows Device Independent Bitmap (.bmp)
             'TIF':'GTiff' #Tagged Image File Format/GeoTIFF (.tif)
            }

    if outfile:format=os.path.splitext(outfile)[1].replace('.','') #overrides "format" arg if supplied
    ovdriver=gdal.GetDriverByName(formats.get(format.upper(), 'JPEG')) #Get format code, default to 'JPEG' if supplied format doesn't match the predefined ones...

    cols=ds.RasterXSize
    rows=ds.RasterYSize

    vrtcols=width
    vrtrows=int(math.ceil(width*float(rows)/cols))
    vrtxml=stretch(stretch_type,vrtcols,vrtrows,ds,bands,*stretch_args)
    vrtds=geometry.OpenDataset(vrtxml)
    if outfile:
        ovdriver.CreateCopy(outfile, vrtds)
    else:
        from tempfile import mkstemp
        fd,fn=mkstemp(suffix='.'+format.lower(), prefix='getoverviewtempimage')
        ovdriver.CreateCopy(fn, vrtds)
        outfile=os.fdopen(fd).read()
        os.unlink(fn)
    return outfile
#========================================================================================================
#Stretch algorithms
#========================================================================================================
def stretch(stretchType,vrtcols,vrtrows,*args):
    vrt=globals()['_stretch_'+stretchType.upper()](vrtcols,vrtrows,*args)
    return geometry.CreateCustomVRT(vrt,vrtcols,vrtrows)

def _stretch_NONE(vrtcols,vrtrows,ds,bands):
    vrt=[]
    for bandnum, band in enumerate(bands):
        srcband=ds.GetRasterBand(band)
        vrt.append('  <VRTRasterBand dataType="Byte" band="%s">' % str(bandnum+1))
        vrt.append('    <SimpleSource>')
        vrt.append('      <SourceFilename relativeToVRT="0">%s</SourceFilename>' % ds.GetDescription())
        vrt.append('      <SourceBand>%s</SourceBand>' % band)
        vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (ds.RasterXSize,ds.RasterYSize))
        vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (vrtcols,vrtrows))
        vrt.append('    </SimpleSource>')
        vrt.append('  </VRTRasterBand>')
    return '\n'.join(vrt)

def _stretch_PERCENT(vrtcols,vrtrows,ds,bands,low,high):
    if low >=1:
        low=low/100.0
        high=high/100.0
    vrt=[]
    for bandnum, band in enumerate(bands):
        srcband=ds.GetRasterBand(band)
        nbits=gdal.GetDataTypeSize(srcband.DataType)
        dfScaleSrcMin,dfScaleSrcMax=GetDataTypeRange(srcband.DataType)
        dfBandMin,dfBandMax,dfBandMean,dfBandStdDev = srcband.GetStatistics(1,1)
        if nbits == 8:binsize=1
        else:binsize=2**(nbits/2)
        nbins=int(math.ceil((dfBandMax-dfBandMin)/binsize))
        hs=srcband.GetHistogram(dfBandMin-0.5,dfBandMax+0.5, nbins)
        dfScaleSrcMin=max([dfScaleSrcMin, HistPercentileValue(hs, low, binsize,dfBandMin)])
        dfScaleSrcMax=min([dfScaleSrcMax, HistPercentileValue(hs, high, binsize,dfBandMin)])
        dfScaleDstMin,dfScaleDstMax=0.0,255.0 #Always going to be Byte for output jpegs
        dfScale = (dfScaleDstMax - dfScaleDstMin) / (dfScaleSrcMax - dfScaleSrcMin)
        dfOffset = -1 * dfScaleSrcMin * dfScale + dfScaleDstMin

        vrt.append('  <VRTRasterBand dataType="Byte" band="%s">' % str(bandnum+1))
        vrt.append('    <ComplexSource>')
        vrt.append('      <SourceFilename relativeToVRT="0">%s</SourceFilename>' % ds.GetDescription())
        vrt.append('      <SourceBand>%s</SourceBand>' % band)
        vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (ds.RasterXSize,ds.RasterYSize))
        vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (vrtcols,vrtrows))
        vrt.append('      <ScaleOffset>%s</ScaleOffset>' % dfOffset)
        vrt.append('      <ScaleRatio>%s</ScaleRatio>' % dfScale)
        vrt.append('    </ComplexSource>')
        vrt.append('  </VRTRasterBand>')
    return '\n'.join(vrt)

def _stretch_MINMAX(vrtcols,vrtrows,ds,bands):
    vrt=[]
    for bandnum, band in enumerate(bands):
        srcband=ds.GetRasterBand(band)
        dfScaleSrcMin,dfScaleSrcMax=GetDataTypeRange(srcband.DataType)
        dfBandMin,dfBandMax,dfBandMean,dfBandStdDev = srcband.GetStatistics(1,1)
        dfScaleDstMin,dfScaleDstMax=0.0,255.0 #Always going to be Byte for output jpegs
        dfScale = (dfScaleDstMax - dfScaleDstMin) / (dfScaleSrcMax - dfScaleSrcMin)
        dfOffset = -1 * dfScaleSrcMin * dfScale + dfScaleDstMin

        vrt.append('  <VRTRasterBand dataType="Byte" band="%s">' % str(bandnum+1))
        vrt.append('    <ComplexSource>')
        vrt.append('      <SourceFilename relativeToVRT="0">%s</SourceFilename>' % ds.GetDescription())
        vrt.append('      <SourceBand>%s</SourceBand>' % band)
        vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (ds.RasterXSize,ds.RasterYSize))
        vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (vrtcols,vrtrows))
        vrt.append('      <ScaleOffset>%s</ScaleOffset>' % dfOffset)
        vrt.append('      <ScaleRatio>%s</ScaleRatio>' % dfScale)
        vrt.append('    </ComplexSource>')
        vrt.append('  </VRTRasterBand>')
    return '\n'.join(vrt)

def _stretch_STDDEV(vrtcols,vrtrows,ds,bands,std):
    vrt=[]
    for bandnum, band in enumerate(bands):
        srcband=ds.GetRasterBand(band)
        dfScaleSrcMin,dfScaleSrcMax=GetDataTypeRange(srcband.DataType)
        dfBandMin,dfBandMax,dfBandMean,dfBandStdDev = srcband.GetStatistics(1,1)
        dfScaleDstMin,dfScaleDstMax=0.0,255.0 #Always going to be Byte for output jpegs
        dfScaleSrcMin=max([dfScaleSrcMin, math.floor(dfBandMean-std*dfBandStdDev)])
        dfScaleSrcMax=min([dfScaleSrcMax, math.ceil(dfBandMean+std*dfBandStdDev)])
        
        dfScale = (dfScaleDstMax - dfScaleDstMin) / (dfScaleSrcMax - dfScaleSrcMin)
        dfOffset = -1 * dfScaleSrcMin * dfScale + dfScaleDstMin

        vrt.append('  <VRTRasterBand dataType="Byte" band="%s">' % str(bandnum+1))
        vrt.append('    <ComplexSource>')
        vrt.append('      <SourceFilename relativeToVRT="0">%s</SourceFilename>' % ds.GetDescription())
        vrt.append('      <SourceBand>%s</SourceBand>' % band)
        vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (ds.RasterXSize,ds.RasterYSize))
        vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (vrtcols,vrtrows))
        vrt.append('      <ScaleOffset>%s</ScaleOffset>' % dfOffset)
        vrt.append('      <ScaleRatio>%s</ScaleRatio>' % dfScale)
        vrt.append('    </ComplexSource>')
        vrt.append('  </VRTRasterBand>')
    return '\n'.join(vrt)

def _stretch_COLORTABLE(vrtcols,vrtrows,ds,bands,clr):
    vrt=[]
    srcband=ds.GetRasterBand(1)
    nvals=2**(gdal.GetDataTypeSize(srcband.DataType))
    lut=ExpandedColorLUT(clr,nvals)
    #lut=ParseColorLUT(clr)
    for band,clr in enumerate(['Red','Green','Blue']):
        vrt.append('  <VRTRasterBand dataType="Byte" band="%s">' % str(band+1))
        vrt.append('    <ColorInterp>%s</ColorInterp>' % clr)
        vrt.append('    <ComplexSource>')
        vrt.append('      <SourceFilename relativeToVRT="0">%s</SourceFilename>' % ds.GetDescription())
        vrt.append('      <SourceBand>1</SourceBand>')
        vrt.append('      <SrcRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (ds.RasterXSize,ds.RasterYSize))
        vrt.append('      <DstRect xOff="0" yOff="0" xSize="%s" ySize="%s"/>' % (vrtcols,vrtrows))
        vrt.append('      <LUT>\n        %s\n      </LUT>' % ',\n        '.join(['%s:%s' % (v[0], v[band+1]) for v in lut]))
        vrt.append('    </ComplexSource>')
        vrt.append('  </VRTRasterBand>')
    return '\n'.join(vrt)

#========================================================================================================
#Helper functions
#========================================================================================================
def GetDataTypeRange(datatype):
    nbits   =gdal.GetDataTypeSize(datatype)
    datatype=gdal.GetDataTypeName(datatype)
    if datatype[0:4] in ['Byte','UInt']:
        dfScaleSrcMin=0             #Unsigned
        dfScaleSrcMax=2**(nbits)-1
    else:
        dfScaleSrcMin=-2**(nbits-1) #Signed
        dfScaleSrcMax= 2**(nbits-1)
    return (dfScaleSrcMin,dfScaleSrcMax)
def HistPercentileValue(inhist, percent, binsize,lowerlimit):
    """
    Returns the score at a given percentile relative to the distribution
    given by inhist.

    Usage:   histpercentilevalue(inhist, percent, binsize,lowerlimit)
    """
    
    # NOTE this function is from "python-statlib" - http://code.google.com/p/python-statlib/
    #
    # Copyright (c) 1999-2007 Gary Strangman; All Rights Reserved.
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
    #
    # Comments and/or additions are welcome (send e-mail to:
    # strang@nmr.mgh.harvard.edu).
    # 
    if percent > 1:
        percent = percent / 100.0
    targetcf = percent*len(inhist)
    total=sum(inhist)
    cumulsum=0.0
    for i in range(len(inhist)):
        cumulsum+=inhist[i]
        if cumulsum/total >= percent:break
    score = lowerlimit+binsize*i-binsize
    return score

def ParseColorLUT(f):
    """Open and parse a colour lookup table, stripping out comment characters
       Lines must be space separated
       Format is: pixel red green blue [optional alpha]
       Pixel value may be a range (eg 15-20)
       The following comment characters may be used '#' '//' ';' '/*'
       Example:
                #value   R   G   B   A
                 11-15   255 0   0   255 #(red)
                 16      255 165 0   255 #(orange)
                 18      255 255 0   255 #(yellow)
                 19      0   255 0   255 /*(green)
                 21      0   0   255 255 /*(blue)
                 98      0   255 255 255 ;(cyan)
                 99-255  160 32  240 255 ;(purple)           
    """
    commentchars=['#','//',';','/*']
    lut=open(f,'r')
    clr=[]
    for line in lut:
        line=line.strip()

        #strip out comment characters
        for char in commentchars:
            if line.find(char) >= 0:
                line=line.split(char)[0].strip()
                
        #Split into pixel, red, green, blue, alpha values
        #if optional alpha value was not included, add it in (255 = non-transparent)
        line=line.split()
        if len(line) > 0: #If it's not a comment line
            if len(line) < 4 or len(line) > 5: raise Exception, 'Unable to process %s' % (f)
            elif len(line) == 4: line.append('255') #Is it just pixel, r, g, b?

            #Check for range of pixel values
            if line[0].find('-') > 0:
                r,g,b,a=line[1:]
                i,j=[int(val) for val in line[0].split('-')]
                for val in range(i,j+1):
                    line=[str(val),r,g,b,a]
                    #yield line
                    clr.append(line)
            else:
                #yield line
                clr.append(line)
    #close and exit
    lut.close() 
    return clr

def ExpandedColorLUT(f,nvals):
    #lut=parseColorLUT(f)
    lut=iter(ParseColorLUT(f))
    tbl=[]
    rng=range(0,nvals)
    val,red,green,blue,alpha=lut.next()
    for r in rng:
        if int(val) == r:
            clr = (str(r),red,green,blue,alpha)
            try:val,red,green,blue,alpha=lut.next()
            except:pass #No more color table entries
        else:clr = (str(r),'255','255','255','0') #default - white/transparent
        #yield clr
        tbl.append(clr)
    return tbl

