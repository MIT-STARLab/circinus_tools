# Data structures for use in routing planning code
# 
# @author Kit Kennedy

from copy import copy,deepcopy

from circinus_tools  import  constants as const
from .custom_window import   ObsWindow,  DlnkWindow, XlnkWindow
from collections import namedtuple

DATE_STRING_FORMAT = 'short'
# DATE_STRING_FORMAT = 'iso'

SatStorageInterval = namedtuple('SatStorageInterval','sat_indx start end')

def short_date_string(dt):
    return dt.strftime("%H:%M:%S")

def date_string(dt):
    if DATE_STRING_FORMAT == 'iso':
        return dt.isoformat()
    if DATE_STRING_FORMAT == 'short':
        return  short_date_string(dt)

    # multi:  there are forks and convergences in the route; data can split out from one window to travel through multiple windows and converge back on another window.  temporal consistency must still be maintained though

class RoutingObjectID():

    def __init__(self,creator_agent_ID,creator_agent_ID_indx):
        """constructor
        
        [description]
        :param creator_agent_ID: the ID of the sim agent that created the route with this ID (e.g. ground network (GP), satellite)
        :type creator_agent_ID: str
        :param creator_agent_ID_indx: index of the route for the creator agent. This generally should increase by one every time a new route object is created
        :type creator_agent_ID_indx: int
        """
        self.creator_agent_ID = creator_agent_ID
        self.creator_agent_ID_indx = creator_agent_ID_indx

    # See:
    # https://docs.python.org/3.4/reference/datamodel.html#object.__hash__
    # https://stackoverflow.com/questions/29435556/how-to-combine-hash-codes-in-in-python3
    def __hash__(self):
        # xor the components together
        return hash(self.creator_agent_ID) ^ hash(self.creator_agent_ID_indx)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __repr__(self):
        if type(self.creator_agent_ID) == str:
            return "ro_ID('%s',%s)"%(self.creator_agent_ID,self.creator_agent_ID_indx)
        else: 
            return "ro_ID(%s,%s)"%(self.creator_agent_ID,self.creator_agent_ID_indx)

    # makes IDs sortable
    def __lt__(self,other):
        # if not equal agent IDs, then compare the agent IDs
        if not self.creator_agent_ID == other.creator_agent_ID:
            return self.creator_agent_ID < other.creator_agent_ID

        # if agent IDs are equal, want to compare indices
        else:
            return self.creator_agent_ID_indx < other.creator_agent_ID_indx

    def get_indx(self):
        return self.creator_agent_ID_indx

class DataRoute():
    '''
    Contains all the relevant information about the path taken by a single data packet traveling through the satellite network
    '''

    # note this route is simple:  there are no forks in the route; there is a simple linear path from an observation to a downlink through which data flows. all windows must be in temporal order.

    def __init__(self, agent_ID,agent_ID_index, route  =[], window_start_sats={},dv=0,dv_epsilon=1e-5,obs_dv_multiplier=1,ro_ID=None):

        if ro_ID:
            self.ID = ro_ID
        else:
            self.ID = RoutingObjectID(agent_ID,agent_ID_index)

        # the list storing all objects in the route; a list ObsWindow, XlnkWindow, XlnkWindow...DlnkWindow
        self.route =  route

        # this keeps track, for each window along the route, of the satellite (sat_indx) that the data was on at the beginning of the window. This is necessary because the window objects themselves are used across paths and do not store information about which sense they are used in
        #  dictionary with keys being the window objects themselves
        self.window_start_sats = window_start_sats

        self.data_vol = dv

        #  the amount of capacity on the path that actually ends up scheduled for usage
        self.scheduled_dv = const.UNASSIGNED

        # self.sort_windows()   

        # The data route is allowed to push through obs_dv * obs_dv_multiplier total throughput. While there is not actually more observation data volume available to route then is present in the observation window, we can still allow the route to be larger. This is used as a bit of a hack in route selection v2. The very first data route on the observing sat is marked as having more dv capacity than the obs actually has, so that it can be used to fork a multitude of routes through crosslinks that, when put together, provide more total throughput than the obs. This helps add more potential routability for any given obs, and was added as a fix for the situation where two observations would like to arrive at a single destination sat, but they're close enough together in time that almost all of the xlnk windows in their data routes from RS will overlap. If those xlnks carry more than the obs dv, then AS can select different subsets of xlnk windows for each obs. 
        self.obs_dv_multiplier = obs_dv_multiplier

        self.dv_epsilon = dv_epsilon

    def set_id(self,agent_ID,agent_ID_index):
        self.ID = RoutingObjectID(agent_ID,agent_ID_index)

    def __copy__(self):
        newone = type(self)(None,None,dv=self.data_vol,obs_dv_multiplier=self.obs_dv_multiplier,ro_ID=copy(self.ID))
        #  make a shallow copy of these container objects -  we want to refer to the same nested objects within the containers, but want a new container in both cases
        newone.route = copy(self.route)
        newone.window_start_sats = copy(self.window_start_sats)
        return newone

    def append_wind_to_route( self,wind,window_start_sat_indx):
        self.route.append(wind)
        self.window_start_sats[wind] = window_start_sat_indx

    def get_winds(self):
        return (wind for wind in self.route)

    def get_obs( self):
        return self.route[0]

    def get_dlnk( self):
        return self.route[-1]

    def has_xlnk(self):
        for wind in self.route:
            if type(wind) == XlnkWindow:
                return True

        return False

    @staticmethod
    def calc_latency(obs,dlnk,units='minutes',obs_option = 'end', dlnk_option = 'center'):
        lat_start = getattr(obs,obs_option)
        lat_end = getattr(dlnk,dlnk_option)
    
        if units == 'minutes':
            return (lat_end-lat_start).total_seconds()/60
        else:
            raise NotImplementedError

    def get_latency( self,units='minutes',obs_option = 'end', dlnk_option = 'center'):
        obs =  self.route[0]
        dlnk =  self.route[-1]

        return self.calc_latency(obs,dlnk,units,obs_option,dlnk_option)

    def  sort_windows(self):
        self.route.sort(key=lambda x: x.start)

    def  get_route_string( self,  time_base= None):
        out_string = ""

        for wind in self.route:

            if type (wind)  == ObsWindow:
                start_str =  "%.0fs" % ( wind.start-time_base).total_seconds() if  time_base else  date_string(wind.start)
                end_str =  "%.0fs" % ( wind.end-time_base).total_seconds() if  time_base else  date_string(wind.end)
                out_string  +=  "o %d s%d dv %.0f %s,%s" % (wind.window_ID,wind.sat_indx, wind.data_vol,start_str,end_str)
            elif type (wind)  == XlnkWindow:
                start_str =  "%.0fs" % ( wind.start-time_base).total_seconds() if  time_base else  date_string(wind.start)
                end_str =  "%.0fs" % ( wind.end-time_base).total_seconds() if  time_base else  date_string(wind.end)
                sat_indx=self.window_start_sats[wind]
                # xsat_indx=wind.xsat_indx  if self.window_start_sats[wind] == wind.sat_indx else wind.sat_indx
                xsat_indx=wind.get_xlnk_partner(self.window_start_sats[wind])
                out_string  +=  " -> x %d s%d,xs%d dv %.0f %s,%s" % (wind.window_ID,sat_indx, xsat_indx, wind.data_vol,start_str,end_str)
            elif type (wind)  == DlnkWindow:
                start_str =  "%.0fs" % ( wind.start-time_base).total_seconds() if  time_base else  date_string(wind.start)
                end_str =  "%.0fs" % ( wind.end-time_base).total_seconds() if  time_base else  date_string(wind.end)
                sat_indx= wind.sat_indx
                out_string  +=  " -> d %d s%d dv %.0f %s,%s" % (wind.window_ID,sat_indx, wind.data_vol,start_str,end_str)
        
        return out_string

    def __repr__(self):
        if not self.scheduled_dv:
            return  '(dr %s: %s)'%(self.ID,self.get_route_string())
        else:
            if self.scheduled_dv == const.UNASSIGNED:
                return  '(dr %s: %s; sched dv: %s/%.0f Mb)'%( self.ID,self.get_route_string(),'none', self.data_vol)
            else:
                return  '(dr %s: %s; sched dv: %.0f/%.0f Mb)'%( self.ID,self.get_route_string(),self.scheduled_dv, self.data_vol)

    def __getitem__(self, key):
        """ getter for internal route by index"""
        return self.route[key]

    def restore_route_objects(self,obs_winds_dict,dlnk_winds_dict,xlnk_winds_dict):
        """grab the original route objects from the input dicts (using hash lookup)"""

        for windex in range(len(self.route)):
            wind = self.route[windex]
            if type(wind) == ObsWindow:
                self.route[windex] = obs_winds_dict[wind]
            if type(wind) == DlnkWindow:
                self.route[windex] = dlnk_winds_dict[wind]
            elif type(wind) == XlnkWindow:
                self.route[windex] = xlnk_winds_dict[wind]

    def validate (self,time_option='start_end'):
        """ validates timing and ordering of route
        
        [description]
        :raises: Exception, Exception, Exception
        """

        # todo: remove this hack! It's for dealing with already-pickled RS outputs
        try:
            self.dv_epsilon
        except AttributeError:
            self.dv_epsilon = 1

        if len( self.route) == 0:
            return

        obs = self.route[0]
        if not type (obs) is ObsWindow:
            raise Exception('First window on route was not an ObsWindow instance. Route string: %s'%( self.get_route_string()))

        if not self.scheduled_dv <= self.data_vol + self.dv_epsilon:
            string = 'routing_objects.py: scheduled data volume (%f) is more than available data volume (%f). Route string: %s'%( self.scheduled_dv, self.data_vol, self.get_route_string())
            raise RuntimeError(string)

        curr_sat_indx = obs.sat_indx
        next_sat_indx = obs.sat_indx
        last_time = obs.start

        #  trace through the route and make sure: 1. we cross through satellites in order and 2.  every activity along the path starts after the last activity ended
        for windex, wind in  enumerate(self.route):
            if self.window_start_sats[wind] != next_sat_indx:
                string = 'routing_objects.py: Found the incorrect sat indx at window indx %d in route. Route string: %s'%( windex, self.get_route_string())
                raise RuntimeError(string)
            
            if time_option=='start_end':
                time_valid = wind.start >= last_time and wind.end >= last_time
            elif time_option=='center':
                time_valid = wind.center >= last_time
            else:
                raise NotImplementedError

            if not time_valid:
                string ='routing_objects.py: Found a bad start time at window indx %d in route. Route string: %s'%( windex, self.get_route_string())
                raise RuntimeError( string)

            #  note the assumption here that every data route's data volume will be less than or equal to the data volume of the observation, all of the cross-links, and the downlink
            if not self.data_vol <= wind.data_vol + self.dv_epsilon:
                string ='routing_objects.py: Found bad dv at window indx %d in route. Allowable dv: %f. Route string: %s'%( windex, obs.data_vol*self.obs_dv_multiplier,str(self))
                raise RuntimeError( string)

            #  note that we manually trace the satellite index through cross-link window here. This is a bit redundant with the functionality of window_start_sats,  but adds a little bit more of a warm, happy, comfortable feeling in the area checking
            if type (wind) is XlnkWindow:
                curr_sat_indx = next_sat_indx
                next_sat_indx=wind.get_xlnk_partner(curr_sat_indx)
                # next_sat_indx = wind.xsat_indx if not wind.xsat_indx == curr_sat_indx else wind.sat_indx

                #  if this happens to be a unidirectional window, and the current satellite index is not the transmitting satellite for that window, there's a problem
                if not wind.symmetric and curr_sat_indx != wind.tx_sat:
                    string ='routing_objects.py: Found incorrect tx sat at window indx %d in route. Route string: %s'%( windex, self.get_route_string())
                    raise RuntimeError(string)

            if time_option=='start_end':
                last_time = wind.end
            elif time_option=='center':
                last_time = wind.center


    def get_split(self,other):
        """ return the last window in common with other data route
        
        iterate through the windows in both routes in temporal order and return the last window that is the same for the two routes
        :param other:  another data route
        :type other: DataRoute
        :returns:  last common window
        :rtype: {ActivityWindow}
        """

        #  route should always start the same place, the initial observation window
        assert self.route[0] == other.route[0]

        len_other = len(other.route)

        #  this will record the index of the last common window of the two routes
        #  increment every time a window is proven to be contained in both routes
        split_windex = -1
        for windex,wind in enumerate(self.route):

            #  if we reached a window in self that is longer than the route for other
            if windex+1 > len_other:
                break

            #  note that this tests the window ID for equality
            if wind != other.route[windex]:
                break

            #  if we've made it here, then both of the data routes must have this window in common
            split_windex += 1

        return self.route[split_windex]

    def count_overlap(self,other,window_option ='shared_window'):

        overlap_count = 0
        for wind1 in self.route:
            if type(wind1) != XlnkWindow:
                continue

            for wind2 in  other.route:
                if type(wind2) != XlnkWindow:
                    continue

                if wind1 == wind2:
                    if window_option =='shared_window':
                        #  only count true overlaps, meaning there's not enough space in the window for both routes
                        if self.data_vol + other.data_vol > wind1.data_vol: 
                            overlap_count += 1
                    elif window_option == 'mutex_window':
                        overlap_count += 1
                    else:
                        raise NotImplementedError


        return overlap_count

    def is_overlapping(self,other,window_option ='shared_window'):

        overlap_count = 0
        for wind1 in self.route:
            if type(wind1) != XlnkWindow:
                continue

            for wind2 in  other.route:
                if type(wind2) != XlnkWindow:
                    continue

                if wind1 == wind2:
                    if window_option =='shared_window':
                        #  only count true overlaps, meaning there's not enough space in the window for both routes
                        if self.data_vol + other.data_vol > wind1.data_vol: 
                            return True
                    elif window_option == 'mutex_window':
                        return True
                    else:
                        raise NotImplementedError

        return False

    def get_data_storage_intervals(self):
        storage_intervals = []

        # teehee, I like this variable name...
        for windex in range(len(self.route)-1):
            wind1 = self.route[windex]
            wind2 = self.route[windex+1]
            # the satellite storing the data is the satellite at which wind2 starts this is true for all cases along a route (wind2 is either an xlnk or a dlnk)
            # the storage interval we define as being from the start of the first window to the end of the second - this means that the data can arrive on the storage sat anywhere during the first window, and can leave anywhere during the second. Note this is conservative.
            storage_intervals.append( SatStorageInterval(self.window_start_sats[wind2],wind1.start,wind2.end) )

        return storage_intervals

class DataMultiRoute():
    """ aggregates multiple DataRoute objects
    
    Meant to represent the aggregation of multiple "simple" routes from a given observation to a given downlink. in general it's good to keep these data routes separate for the activity scheduling algorithm so that there is less potential for overlap with the Windows in other data routes. however, in the case where the data routes and activity scheduling need to have a higher minimum data volume than is achievable with the routes delivered by the route selection algorithm, then we need to aggregate multiple simple routes into a multi-route

    note that it is still valid to multiply the entire data volume of this route by a single utilization number from 0 to 1 to represent how much data volume is used from this multi-route. When constructing the multi-route, we ensure that no data volume from any given activity window is spoken for by multiple DataRoute objects within the multi-route; i.e.,  It's perfectly allowable to schedule all of the data routes within from a throughput perspective. the utilization number effectively carries through to multiply the data volumes of the individual data route objects.
    """

    def __init__(self,agent_ID,agent_ID_index,data_routes,dv_epsilon=1e-5,ro_ID=None):

        if ro_ID:
            self.ID = ro_ID
        else:
            self.ID = RoutingObjectID(agent_ID,agent_ID_index)

        #  all of the "simple"  data route objects contained within this multi-route
        self.data_routes = data_routes
        #  this map holds the amount of data volume we have allocated to each of the data routes within this multi-route. we initially create it with all of the data volume from the initializer data routes, but it is not necessarily the case that the data volume numbers within this dict will be the same as the data volume numbers within the individual data route objects
        self.data_vol_by_dr = {dr:dr.data_vol for dr in data_routes}
        self.scheduled_dv_by_dr = {dr:const.UNASSIGNED for dr in data_routes}
        self.has_scheduled_dv = False

        self.dv_epsilon=dv_epsilon

        for dr in data_routes:
            if not type(dr) == DataRoute:
                raise RuntimeError('only data route objects should be used to construct a new data multi-route')

    def __hash__(self):
        return hash(self.ID)

    def __eq__(self, other):
        return self.ID == other.ID

    @property
    def data_vol(self):
        return sum(self.data_vol_by_dr.values())

    def data_vol_for_wind(self,wind):
        wind_sum = sum(dv for dr,dv in self.data_vol_by_dr.items() if wind in dr.get_winds())

        if wind_sum == 0:
            raise KeyError('Found zero data volume for window, which assumedly means it is not in the route. self: %s, wind: %s'%(self,wind))

        return wind_sum

    @property
    def scheduled_dv(self):
        if self.has_scheduled_dv:
            if const.UNASSIGNED in self.scheduled_dv_by_dr.values():
                raise RuntimeWarning('Saw unassigned scheduled data volume for dr in self: %s'%(self))

            return sum(self.scheduled_dv_by_dr.values())
        else:
            return const.UNASSIGNED

    def scheduled_dv_for_wind(self,wind):
        if self.has_scheduled_dv:
            # note: don't check minimum data volume here because scheduled data volume could go to zero
            return sum(s_dv for dr,s_dv in self.scheduled_dv_by_dr.items() if wind in dr.get_winds())
        else:
            return const.UNASSIGNED    

    def set_scheduled_dv_frac(self,fraction):
        for dr in self.data_routes:
            self.scheduled_dv_by_dr[dr] = self.data_vol_by_dr[dr]*fraction

        self.has_scheduled_dv = True


    def get_winds(self):
        """ get the set of windows from all of the routes contained within this multi-route
        
        Returns the set of all windows from all the DataRoutes within. Note that this is a set, so each window only shows up once
        :returns: [description]
        :rtype: {[type]}
        """

        return set(wind for dr in self.data_routes for wind in dr.get_winds())

    def get_obs( self):
        #  use first route because all routes should have the same observation
        return self.data_routes[0].get_obs()

    def get_dlnk(self):
        #  use first route because all routes should have the same downlink
        return self.data_routes[0].get_dlnk()

    def has_xlnk(self):
        return any(dr.has_xlnk() for dr in self.data_routes)

    def get_latency( self,units='minutes',obs_option = 'end', dlnk_option = 'center'):
        return self.data_routes[0].get_latency(units,obs_option,dlnk_option)

    def get_display_string(self):
        return 'sched/poss_dv_by_dr: %s'%({'DR - '+dr.get_route_string():'%d/%d'%(dv,self.data_vol_by_dr[dr]) for dr,dv in self.scheduled_dv_by_dr.items()})

    def __repr__(self):
        # return  '(DataMultiRoute %s, routes: %s)'%(self.ID,{dr.ID: self.data_vol_by_dr[dr] for dr in self.data_routes})
        return  '(DataMultiRoute %s: %s)'%(self.ID,self.get_display_string())

    def validate (self,time_option='start_end'):

        # todo: remove this hack! It's for dealing with already-pickled RS outputs
        try:
            self.dv_epsilon
        except AttributeError:
            self.dv_epsilon = 1  # Mb

        for dr in self.data_routes:
            #  validate the data routes individually - this checks for temporal and data volume consistency within those routes
            dr.validate(time_option)
            #  validate that they all have the same initial observation and the same final downlink
            assert(dr.get_obs() == self.get_obs())
            assert(dr.get_dlnk() == self.get_dlnk())

        avail_dv_by_wind = {}
        # figure out what window data volume is already occupied by the data routes within self        
        for dr in self.data_routes:
            
            for wind in dr.get_winds():
                #  if we didn't yet encounter this window in any of the routes in self
                avail_dv_by_wind.setdefault(wind,wind.data_vol)

                avail_dv_by_wind[wind] -= dr.data_vol

        #  check that for all of the windows in all of the routes, no window is oversubscribed
        #  note the assumption here that every data route's data volume will be less than or equal to the data volume of the observation, all of the cross-links, and the downlink
        for dv in avail_dv_by_wind.values():
            assert(dv >= 0 - self.dv_epsilon)


    def accumulate_dr( self, candidate_dr,min_dmr_candidate_dv=0):
        """ add a simple data route to this data multi route
        
        [description]
        :param dmrs: data multi routes to combine into a new multiroute
        :type dmrs: list(DataMultiRoute)
        """

        # need to have matching observation and downlink for candidate to be added on to the multi-route
        if not candidate_dr.get_obs() == self.get_obs():
            return False
        if not candidate_dr.get_dlnk() == self.get_dlnk():
            return False

        avail_dv_by_wind = {}
         # figure out what window data volume is already occupied by the data routes within self        
        for dr in self.data_routes:
            for wind in dr.get_winds():
                #  if we didn't yet encounter this window in any of the routes in self
                avail_dv_by_wind.setdefault(wind,wind.data_vol)
                avail_dv_by_wind[wind] -= dr.data_vol

        #  figure out how much data volume can be allotted to the candidate data route
        candidate_dv =candidate_dr.data_vol
        for wind in candidate_dr.get_winds():
            usable_wind_dv = min(avail_dv_by_wind.get(wind,wind.data_vol),candidate_dr.data_vol)

            candidate_dv = min(candidate_dv, usable_wind_dv)

        #  if there is enough data volume left, then add the data  route
        if candidate_dv > min_dmr_candidate_dv:
            self.data_routes.append(candidate_dr)
            self.data_vol_by_dr[candidate_dr] = candidate_dv
            self.scheduled_dv_by_dr[candidate_dr] = const.UNASSIGNED
            return True
        else:
            return False

    def get_data_storage_intervals(self):
        storage_intervals = []

        # we can do this independently because if this is a valid DMR, then the data volume (or bandwidth usage) for each route is mutex, and we don't have to worry about overlap
        for dr in self.data_routes:
            storage_intervals += dr.get_data_storage_intervals()

        return storage_intervals

class SimRouteContainer():
    """ This contains lower level data route objects, for use in the constellation simulation. It effectively allows the simulation to easily vary the amount of data volume, time scheduled for a data route, in order to flexibly replan in realtime. 

    The use of this container is an artifact of the choice to model data routes as a series of activity windows of fixed start/end times. If we wish to change any of those start/end times, that would be reflected as a change in the underlying window object, but not in the data route object itself, which is not great. So we'd have to create a new data route object - which is not great for rescheduling because its harder to track the data route object as it gets passed around the constellation. By wrapping the data route in a container that can change its state, we have both timing/dv flexibility and persistent object indexing"""

    def __init__(self,agent_ID,agent_ID_index,data_routes,t_utilization_by_dr,dv_utilization_by_dr,update_dt,ro_ID=None):

        # handle case where we're only passed a single route (standard)
        if type(data_routes) == DataMultiRoute:
            dmr = data_routes

            assert(type(t_utilization_by_dr) == float)
            t_utilization_by_dr = {dmr:t_utilization_by_dr}
            assert(type(dv_utilization_by_dr) == float)
            dv_utilization_by_dr = {dmr:dv_utilization_by_dr}

            # make it a list
            data_routes = [dmr]

        # todo: relax this type constraint?
        for dmr in data_routes:
            if not type(dmr) == DataMultiRoute:
                raise RuntimeWarning('Expected a DataMultiRoute, found %s'%(dmr))

        if ro_ID:
            self.ID = ro_ID
        else:
            self.ID = RoutingObjectID(agent_ID,agent_ID_index)

        self.data_routes = data_routes if type(data_routes) == list else list(data_routes)

        # this is the "time utilization" for the data route (DMR), which is a number from 0 to 1.0 by which the duration for every window in the route should be multiplied to determine how long the window will actually be executed in the real, final schedule
        self.t_utilization_by_dr = t_utilization_by_dr
        # this is the "data volume utilization" for the data route (DMR), which is a number from 0 to 1.0 by which the scheduled data volume for every window in the route should be multiplied to determine how much data volume will actually be throughput on this dr in the real, final schedule
        self.dv_utilization_by_dr = dv_utilization_by_dr
        self.update_dt = update_dt

    @property
    def end():
        # get latest end of all dmrs
        return max(dmr.get_dlnk().end for dmr in self.data_routes)

    def __repr__(self):
        return '(SRC %s: %s)'%(self.ID,self.get_display_string())

    def get_display_string(self):
        return 'utilization_by_dmr: %s'%({'DMR - '+dr.get_display_string():util for dr,util in self.dv_utilization_by_dr.items()})


    def get_winds_executable(self):
        winds_executable = []

        for dmr in self.data_routes:
            winds = dmr.get_winds()

            for wind in winds:
                # make a deepcopy so we don't risk information crossing the ether in the simulation...
                wind = deepcopy(wind)
                wind.set_executable_properties(self,t_utilization_by_dr[dmr],dv_utilization_by_dr[dmr])
                winds_executable.append(wind)

        return winds_executable


class LinkInfo():
    """docstring fos  LinkInfo"""
    def __init__(self,data_routes=[],total_data_vol=0,used_data_vol=0):
        self.data_routes = data_routes
        self.total_data_vol = total_data_vol
        self.used_data_vol = used_data_vol

    def __str__( self):
        return  "routes: "+str(self.data_routes) + " ; dv %.0f/%.0f Mb" % ( self.used_data_vol, self.total_data_vol)

















