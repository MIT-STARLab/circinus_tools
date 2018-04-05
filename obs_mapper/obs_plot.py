# Tools for plotting observation targets
# 
# @author Kit Kennedy

import json
from collections import namedtuple

import matplotlib.pyplot as plt
from matplotlib.pyplot import savefig
from matplotlib.patches import Rectangle

# need to "pip install pillow" for this import to work
from scipy.misc import imread

GeoPoint = namedtuple('GeoPoint', 'ID lat lon')
GeoRectangle = namedtuple('GeoRectangle', 'ID lat lon h_lat w_lon')

ANNOTATION_X_PAD = 1
ANNOTATION_Y_PAD = 1

def grok_spec_rect(rect,item_uid,spec_option='solid'):

    grect = GeoRectangle(
            ID = item_uid,
            lat = rect['lat_bottom_deg'],
            lon = rect['lon_left_deg'],
            h_lat = rect['lat_upper_deg'] - rect['lat_bottom_deg'],
            w_lon = rect['lon_right_deg'] - rect['lon_left_deg'],
        )
    gpnts = []

    if spec_option == 'points':
        num_lat = rect['num_lat_points']
        num_lon = rect['num_lon_points']
        lat_spacing =  (rect['lat_upper_deg'] - rect['lat_bottom_deg']) / num_lat
        lon_spacing =  (rect['lon_right_deg'] - rect['lon_left_deg']) / num_lon

        ID = 0
        for lat_indx in range(num_lat):
            for lon_indx in range(num_lon):
                lat = rect['lat_bottom_deg'] + lat_spacing*lat_indx
                lon = rect['lon_left_deg'] + lon_spacing*lon_indx
                gpnts.append(GeoPoint(ID=ID, lat = lat,lon = lon))
                ID += 1

    return grect,gpnts


def grok_spec_pnt(pnt,item_uid,spec_option='default'):

    if spec_option == 'default':
        return GeoPoint(ID = item_uid,lat = pnt['lat'],lon = pnt['lon'])
    else:
        raise NotImplementedError

def add_annotation(ax,lat,lon,annotation):
    xy = (lon+ANNOTATION_Y_PAD,lat+ANNOTATION_X_PAD)
    ax.annotate(annotation, xy=xy)

def plot_geo_point(plt,ax,gpnt):
    plt.plot(gpnt.lon,gpnt.lat,marker='.',color='black')
    add_annotation(ax,gpnt.lat,gpnt.lon,str(gpnt.ID))

def plot_rect(plt,ax,rect, item_uid):
    spec_option = rect['spec_option']

    if spec_option == 'solid':
        grect,_ = grok_spec_rect(rect,item_uid,spec_option)
        rect_patch = Rectangle((grect.lon, grect.lat), grect.w_lon, grect.h_lat,alpha=1,fill=False)
        ax.add_patch(rect_patch)
        add_annotation(ax,grect.lat,grect.lon,'r'+str(grect.ID))

    elif spec_option == 'points':
        grect,gpnts = grok_spec_rect(rect,item_uid,spec_option)
        add_annotation(ax,grect.lat-2,grect.lon-7,'r'+str(grect.ID))

        for gpnt in gpnts:
            plot_geo_point(plt, ax, gpnt)

    else:
        raise NotImplementedError

    


def plot_targets(targets_spec):
    
    plt.figure()
    plt.title('Observation target regions and points')
    
    fig = plt.gcf()
    fig.set_size_inches(16,12)

    plt.axis((-180, 180, -90, 90))
    plt.ylabel('Latitude')
    plt.xlabel('Longitude') 
    
    # plot the earth background
    # image lifted from http://www.wavemetrics.com/products/igorpro/dataaccess/gissupport.htm, accessed 5/3/2015
    img = imread("world_map.png")
    # plot image from bottom left corner
    plt.imshow(img,extent=[-180, 180, -90, 90])
        

    ax = plt.gca()    
    
    item_uid = 0

    rect_items = targets_spec['rectangles']
    for rect in rect_items:
        plot_rect(plt,ax,rect, item_uid)
        item_uid += 1


    pnt_items = targets_spec['points']
    for point in pnt_items:
        gpnt = grok_spec_pnt(point,item_uid)
        plot_geo_point(plt,ax,gpnt)
        item_uid += 1
    
    


    # plt.show()
    savefig('targets.pdf',format='pdf',bbox_inches='tight', transparent="True")

if __name__ == '__main__':
    targets_spec_file = 'targets_spec/targets_1.json'

    with open(targets_spec_file,'r') as f:
        targets_spec = json.load(f)

    plot_targets(targets_spec)