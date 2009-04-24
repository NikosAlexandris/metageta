import os,math,warnings

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

def OpenDataset(f,mode=gdalconst.GA_ReadOnly): #Open & return a gdalDataset object
    gdal.ErrorReset()
    gdal.PushErrorHandler( 'CPLQuietErrorHandler' )
    gdalDataset = gdal.Open(f, mode)
    gdal.PopErrorHandler()
    return gdalDataset
    
def Rotation(gt):   #Get rotation angle from a geotransform
    try:return math.degrees(math.tanh(gt[2]/gt[5]))
    except:return 0

def CellSize(gt):   #Get cell size from a geotransform
    cellx=round(math.hypot(gt[1],gt[4]),7)
    celly=round(math.hypot(gt[2],gt[5]),7)
    return (cellx,celly)

def SceneCentre(gt,cols,rows):#Get scene centre from a geotransform
    px = cols/2
    py = rows/2
    x=gt[0]+(px*gt[1])+(py*gt[2])
    y=gt[3]+(px*gt[4])+(py*gt[5])
    return x,y

def GeoTransformToGCPs(gt,cols,rows):
    """ Form a gcp list from a geotransform using the 4 corners.
        This function is meant to be used to convert a geotransform
        to gcp's so that the geocoded information can be reprojected.

        Inputs: gt   - geotransform to convert to gcps
                cols - number of columns in the dataset
                rows - number of rows in the dataset
        
    """
    
    gcp_list=[]
    parr=[0,cols]
    larr=[0,rows]
    id=0
    for px in parr:
        for py in larr:
            cgcp=gdal.GCP()
            cgcp.Id=str(id)
            cgcp.GCPX=gt[0]+(px*gt[1])+(py*gt[2])
            cgcp.GCPY=gt[3]+(px*gt[4])+(py*gt[5])
            cgcp.GCPZ=0.0
            cgcp.GCPPixel=px
            cgcp.GCPLine=py
            id+=1
            gcp_list.append(cgcp)
        larr.reverse()
    return gcp_list

def GeomFromExtent(ext,srs=None,srs_wkt=None):
    if type(ext[0]) is list or type(ext[0]) is tuple: #is it a list of xy pairs
        wkt = 'POLYGON ((%s))' % ','.join(map(' '.join, [map(str, i) for i in ext]))
    else: #it's a list of xy values
        xmin,ymin,xmax,ymax=ext
        template = 'POLYGON ((%(minx)f %(miny)f, %(minx)f %(maxy)f, %(maxx)f %(maxy)f, %(maxx)f %(miny)f, %(minx)f %(miny)f))'
        r1 = {'minx': xmin, 'miny': ymin, 'maxx':xmax, 'maxy':ymax}
        wkt = template % r1
    if srs_wkt is not None:srs=osr.SpatialReference(wkt=srs_wkt)
    geom = ogr.CreateGeometryFromWkt(wkt,srs)
    return geom

def ReprojectGeom(geom,src_srs,tgt_srs):
    gdal.ErrorReset()
    gdal.PushErrorHandler( 'CPLQuietErrorHandler' )
    geom.AssignSpatialReference(src_srs)
    geom.TransformTo(tgt_srs)
    err = gdal.GetLastErrorMsg()
    if err:warnings.warn(err.replace('\n',' '))
    gdal.PopErrorHandler()
    gdal.ErrorReset()
    return geom

class ShapeWriter:
    """A class for writing geometry and fields to ESRI shapefile format"""
    def __init__(self,shapefile,fields,srs_wkt=None,overwrite=True):
        try:
            gdal.ErrorReset()
            self._srs=osr.SpatialReference()
            self.fields=[]
            if srs_wkt:self._srs.ImportFromWkt(wkt)
            else:self._srs.ImportFromEPSG(4283) #default=GDA94 Geographic
            self._shape=self.OpenShapefile(shapefile,fields,overwrite)
        except Exception, err:
            self.__error__(err)

    def __del__(self):
        gdal.ErrorReset()
        self._shape.Release()

    def __error__(self, err):
        gdalerr=gdal.GetLastErrorMsg();gdal.ErrorReset()
        errmsg = str(err)
        if gdalerr:errmsg += '\n%s' % gdalerr
        raise err.__class__, errmsg
        
    def WriteRecord(self,extent,attributes):
        try:
            geom=GeomFromExtent(extent,self._srs)
            if self._srs.IsGeographic(): #basic coordinate bounds test. Can't do for projected though
                srs=osr.SpatialReference()
                srs.ImportFromEPSG(4283)#4326)
                valid = GeomFromExtent([-180,-90,180,90], srs=srs)
                if not valid.Contains(geom): raise ValueError, 'Invalid extent coordinates'

            lyr=self._shape.GetLayer(0)
            
            feat = ogr.Feature(lyr.GetLayerDefn())
            for a in attributes:
                if a in self.fields:feat.SetField(a, attributes[a])
            feat.SetGeometryDirectly(geom)
            lyr.CreateFeature(feat)

        except Exception, err:
            self.__error__(err)

    def OpenShapefile(self, shapefile,fields,overwrite):
        try:
            driver = ogr.GetDriverByName('ESRI Shapefile')
            if os.path.exists(shapefile):
                if overwrite:
                    driver.DeleteDataSource(shapefile)
                else:
                    shp=driver.Open(shapefile,update=1)
                    lyr=shp.GetLayer(0)
                    self._srs=lyr.GetSpatialRef()
                    return shp

            shp = driver.CreateDataSource(shapefile)
            lyr=os.path.splitext(os.path.split(shapefile)[1])[0]
            lyr = shp.CreateLayer(lyr,geom_type=ogr.wkbPolygon,srs=self._srs)
            for f in fields:
                #Get field types
                if type(fields[f]) in [list,tuple]:
                    ftype=fields[f][0]
                    fwidth=fields[f][1]
                else:
                    ftype=fields[f]
                    fwidth=0
                if ftype.upper()=='STRING':
                    fld = ogr.FieldDefn(f, ogr.OFTString)
                    fld.SetWidth(fwidth)
                    lyr.CreateField(fld)
                    self.fields.append(f)
                elif ftype.upper()=='INT':
                    fld = ogr.FieldDefn(f, ogr.OFTInteger)
                    lyr.CreateField(fld)
                    self.fields.append(f)
                elif ftype.upper()=='FLOAT':
                    fld = ogr.FieldDefn(f, ogr.OFTReal)
                    lyr.CreateField(fld)
                    self.fields.append(f)
                else:pass
                    #raise AttributeError, 'Invalid field definition'

            return shp

        except Exception, err:
            self.__error__(err)