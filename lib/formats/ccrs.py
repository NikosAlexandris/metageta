#Regular expression list of file formats
format_regex=[r'imag_[0-9]*\.dat$']#Landsat 5/SPOT 1-4 CCRS

#import base dataset module
import __dataset__

# import other modules (use "_"  prefix to import privately)
import sys, os, re, glob, time, math, string
import utilities
import geometry

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
    
class Dataset(__dataset__.Dataset): #Subclass of base Dataset class
    def __init__(self,f):
        """Read georeferencing information for a ACRES Landsat CCRS/SPOT 1-4 format image as GDAL doesn't"""
        gdalDataset = geometry.OpenDataset(f)

        p=re.compile(r'\\imag_*', re.I)
        led=p.sub(r'\\lead_',f)
        filelist=[r for r in utilities.rglob(os.path.dirname(f))]

        meta = open(led,'rb').read()

        """
        metadata has 4 records, each is 4320 (LS) or 6120 (SPOT) bytes long:
        File descriptor record;
        Scene header record;
        Map projection (scene-related) ancillary record;
        Radiometric transformation ancillary record.
        """

        #Record 2 - Scene header record
        record=2
        recordlength=4320 #LS 5
        satellite=utilities.readbinary(meta,(record-1)*recordlength,309,324)
        if not satellite == 'LANDSAT-5':
            recordlength=6120 #SPOT recordlength=6120
            satellite=utilities.readbinary(meta,(record-1)*recordlength,309,324)
            if not satellite[0:4] == 'SPOT':
                raise IOError, 'Unable to process '+f+'\nUnknown CEOS file'

        #Scene ID, path/row & image date/time
        start,stop=37,52
        sceneid=utilities.readbinary(meta,(record-1)*recordlength,start,stop)
        start,stop=165,180
        pathrow=utilities.readbinary(meta,(record-1)*recordlength,start,stop)[1:]
        start,stop=117,148
        imgdate=utilities.readbinary(meta,(record-1)*recordlength,start,stop)
        self.metadata['imgdate']=time.strftime('%Y-%m-%d',time.strptime(imgdate[0:8],'%Y%m%d')) #ISO 8601 
        #self.metadata['imgdate']=imgdate[0:8]
        #self.metadata['imgtime']=imgdate[8:14]
        
        #Ascending/descending flag
        start,stop=357,372
        if utilities.readbinary(meta,(record-1)*recordlength,start,stop) == 'D':self.metadata['orbit']='Descending'
        else:self.metadata['orbit']='Ascending'

        #Processing level
        start,stop=1573,1588
        self.metadata['level']=utilities.readbinary(meta,(record-1)*recordlength,start,stop)

        #Bands
        start,stop=1653,1659
        bands=[]
        actbands=utilities.readbinary(meta,(record-1)*recordlength,start,stop)
        for i in range(0,7): #Loop thru the 7 LS 5 bands
            if actbands[i]=='1':bands.append(str(i+1))
        
        #Record 3 - Map projection (scene-related) ancillary record
        record=3

        #Bands, rows & columns and rotation
        nbands = int(gdalDataset.RasterCount)
        start,stop=333,348
        ncols=float(utilities.readbinary(meta,(record-1)*recordlength,start,stop))
        start,stop=349,364
        nrows=float(utilities.readbinary(meta,(record-1)*recordlength,start,stop))
        start,stop =  445,460
        self.metadata['rotation']=float(utilities.readbinary(meta,(record-1)*recordlength,start,stop))
        if abs(self.metadata['rotation']) < 1:
            self.metadata['orientation']='Map oriented'
            self.metadata['rotation']=0.0
        else:self.metadata['orientation']='Path oriented'

        #Sun elevation and azimuth
        start,stop=605,620
        self.metadata['sunelevation']=float(utilities.readbinary(meta,(record-1)*recordlength,start,stop))
        start,stop=621,636
        self.metadata['sunazimuth']=float(utilities.readbinary(meta,(record-1)*recordlength,start,stop))
        
        #geometry.CellSizes
        start,stop = 365,396
        (cellx,celly) = map(float,utilities.readbinary(meta,(record-1)*recordlength,start,stop).split())
        start,stop = 397,412
        projection = utilities.readbinary(meta,(record-1)*recordlength,start,stop).split()
        datum = projection[0]
        zone = projection[1]

        # lat/lons
        start,stop =  765,892
        coords = utilities.readbinary(meta,(record-1)*recordlength,start,stop).split()
        uly,ulx,ury,urx,lry,lrx,lly,llx = map(float, coords)
        ext=[[ulx,uly],[urx,ury],[lrx,lry],[llx,lly],[ulx,uly]]
        
        if int(zone) != 0:
            # UTM
            type='UTM'
            units='m'
            #start,stop =  637,764
            #coords = utilities.readbinary(meta,(record-1)*recordlength,start,stop).split()
            #uly,ulx,ury,urx,lry,lrx,lly,llx = map(float, coords)
            #ext=[[ulx,uly],[urx,ury],[lrx,lry],[llx,lly],[ulx,uly]]

            if   datum == 'GDA94':epsg=int('283'+zone)
            elif datum == 'AGD66':epsg=int('202'+zone)
            elif datum == 'WGS84':epsg=int('327'+zone)
            
        else: #Assume
            type='GEO'
            units='deg'
            if datum=='GDA94':epsg=4283
            else:epsg=4326 #Assume WGS84
            gcps=[];i=0
            lr=[[0,0],[ncols,0],[ncols,nrows],[0,nrows]]
            while i < len(ext)-1: #don't need the last xy pair
                gcp=gdal.GCP()
                gcp.GCPPixel,gcp.GCPLine=lr[i]
                gcp.GCPX,gcp.GCPY=ext[i]
                gcp.Id=str(i)
                gcps.append(gcp)
                i+=1
            geotransform = gdal.GCPsToGeoTransform(gcps)
            cellx,celly=geometry.CellSize(geotransform)
            rotation=geometry.Rotation(geotransform)

        srs = osr.SpatialReference()
        srs.ImportFromEPSG(epsg)
        srs=srs.ExportToWkt()

        self.metadata['satellite']=satellite
        if satellite == 'LANDSAT-5':
            self.metadata['sensor']='TM'
            self.metadata['filetype'] ='CEOS/Landsat CCRS Format'
        else:
            self.metadata['sensor']='HRV'
            self.metadata['filetype'] ='CEOS/SPOT CCRS Format'
        self.metadata['filesize']=sum([os.path.getsize(file) for file in filelist])
        self.metadata['filelist']=','.join(utilities.fixSeparators(filelist))
        self.metadata['srs'] = srs
        self.metadata['epsg'] = epsg
        self.metadata['units'] = units
        self.metadata['cols'] = ncols
        self.metadata['rows'] = nrows
        self.metadata['nbands'] = nbands
        self.metadata['bands'] = ','.join(bands)
        self.metadata['nbits'] = 8
        self.metadata['datatype'] = 'Byte'
        self.metadata['nodata'] = 0
        self.metadata['cellx'],self.metadata['celly']=map(float,[cellx,celly])
        self.metadata['UL']='%s,%s' % tuple(ext[0])
        self.metadata['UR']='%s,%s' % tuple(ext[1])
        self.metadata['LR']='%s,%s' % tuple(ext[2])
        self.metadata['LL']='%s,%s' % tuple(ext[3])
        metadata=gdalDataset.GetMetadata()
        self.metadata['metadata']='\n'.join(['%s: %s' %(m,hdf_self.metadata[m]) for m in metadata])
        self.metadata['compressionratio']=0
        self.metadata['compressiontype']='None'
        self.extent=ext