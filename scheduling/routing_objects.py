# Data structures for use in routing planning code
# 
# @author Kit Kennedy

from copy import copy

from circinus_tools  import  constants as const
from circinus_tools  import  time_tools as tt
from .custom_window import   ObsWindow,  DlnkWindow, XlnkWindow
from collections import namedtuple


SatStorageInterval = namedtuple('SatStorageInterval','sat_indx start end')


class RoutingObjectID():

    def __init__(self,creator_agent_ID,creator_agent_ID_indx,rt_obj_type='default'):
        """constructor
        
        [description]
        :param creator_agent_ID: the ID of the sim agent that created the route with this ID (e.g. ground network (GP), satellite)
        :type creator_agent_ID: str
        :param creator_agent_ID_indx: index of the route for the creator agent. This generally should increase by one every time a new route object is created
        :type creator_agent_ID_indx: int
        :param rt_obj_type: an optional identifier for the type of routing object - not currently used in hash/equality computations
        :type creator_agent_ID_indx: str
        """
        self.creator_agent_ID = creator_agent_ID
        self.creator_agent_ID_indx = creator_agent_ID_indx
        self.rt_obj_type = rt_obj_type

    # See:
    # https://docs.python.org/3.4/reference/datamodel.html#object.__hash__
    # https://stackoverflow.com/questions/29435556/how-to-combine-hash-codes-in-in-python3
    def __hash__(self):
        # xor the components together
        return hash(self.creator_agent_ID) ^ hash(self.creator_agent_ID_indx) ^ hash(self.rt_obj_type)

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

    @property
    def indx(self):
        return self.creator_agent_ID_indx
    
    def get_indx(self):
        return self.creator_agent_ID_indx

class DataRoute:
    '''
    Contains all the relevant information about the path taken by a single data packet traveling through the satellite network
    '''

    # note this route is simple:  there are no forks in the route; there is a simple linear path from an observation to a downlink through which data flows. all windows must be in temporal order.

    def __init__(self, agent_ID,agent_ID_index, route  =[], window_start_sats={},dv=0,dv_epsilon=1e-5,obs_dv_multiplier=1,ro_ID=None):

        if ro_ID:
            if not type(ro_ID) == RoutingObjectID:
                raise RuntimeWarning(' should not use anything but a RoutingObjectID as the ID for a DataRoute')

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
        # BIG FAT NOTE: this value can go stale, and should not be relied upon anywhere in the constellation sim code as the amount of dv available for this route - rather, the vanilla data_vol of the route should be multiplied by utilization to figure out how much is usable. The LPs DO NOT update the scheduled dv number, which is why it can go stale
        self.scheduled_dv = const.UNASSIGNED

        # self.sort_windows()   

        # The data route is allowed to push through obs_dv * obs_dv_multiplier total throughput. While there is not actually more observation data volume available to route then is present in the observation window, we can still allow the route to be larger. This is used as a bit of a hack in route selection v2. The very first data route on the observing sat is marked as having more dv capacity than the obs actually has, so that it can be used to fork a multitude of routes through crosslinks that, when put together, provide more total throughput than the obs. This helps add more potential routability for any given obs, and was added as a fix for the situation where two observations would like to arrive at a single destination sat, but they're close enough together in time that almost all of the xlnk windows in their data routes from RS will overlap. If those xlnks carry more than the obs dv, then AS can select different subsets of xlnk windows for each obs. 
        self.obs_dv_multiplier = obs_dv_multiplier

        self.dv_epsilon = dv_epsilon

        #  this maintains a list of the windows for which we've allowed an overlap at their start to exist in the route. this is used in the validation step
        self.allowed_overlaps_start_wind = []

        self.output_date_str_format = 'short'

    # @property
    # def simple_data_routes(self):
    #     #  this provides a consistent API with DataMultiRoute
    #     return [self]
    
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

    def __hash__(self):
        return hash(self.ID)

    def __eq__(self, other):
        return self.ID == other.ID

    def __copy__(self):
        newone = type(self)(None,None,dv=self.data_vol,obs_dv_multiplier=self.obs_dv_multiplier,ro_ID=copy(self.ID))
        #  make a shallow copy of these container objects -  we want to refer to the same nested objects within the containers, but want a new container in both cases
        newone.route = copy(self.route)
        newone.window_start_sats = copy(self.window_start_sats)
        newone.dv_epsilon = self.dv_epsilon
        newone.allowed_overlaps_start_wind = copy(self.allowed_overlaps_start_wind)
        newone.scheduled_dv = self.scheduled_dv
        return newone

    def set_id(self,agent_ID,agent_ID_index):
        self.ID = RoutingObjectID(agent_ID,agent_ID_index)

    def append_wind_to_route( self,wind,window_start_sat_indx):
        self.route.append(wind)
        self.window_start_sats[wind] = window_start_sat_indx

    def get_winds(self):
        return (wind for wind in self.route)

    def get_inflow_winds_rx_sat(self,sat_indx):
        """ find all the windows in this route up to and including the window that delivers data to the satellite of interest"""

        relevant_winds = []
        found_rx_sat = False
        # iterate through the windows in this route...
        for wind in self.get_winds():
            #  check if the window is an rx activity for the satellite of interest
            wind_is_rx_for_sat = wind.has_sat_indx(sat_indx) and wind.is_rx(sat_indx)

            relevant_winds.append(wind)

            #  if we have found a window that receives for the satellite, mark that and stop the loop, because we have found up to and including the rx sat
            if wind_is_rx_for_sat: 
                found_rx_sat = True
                break

        if not found_rx_sat:
            raise RuntimeWarning('Did not find rx sat indx %d in route %s'%(sat_indx,self))

        return relevant_winds

    def get_outflow_winds_tx_sat(self,sat_indx):
        """ find all the windows in this route after (and including) the window that carries data from the satellite of interest to the end of the route"""

        relevant_winds = []
        found_tx_sat = False
        # iterate through the windows in this route...
        for wind in self.get_winds():
            #  check if the window is an tx activity for the satellite of interest
            wind_is_tx_for_sat = wind.has_sat_indx(sat_indx) and wind.is_tx(sat_indx)

            #  if we have found the window that transmits from the satellite, mark that and add that window as well as all windows after that
            if wind_is_tx_for_sat or found_tx_sat: 
                relevant_winds.append(wind)
                found_tx_sat = True

        if not found_tx_sat:
            raise RuntimeWarning('Did not find tx sat indx %d in route %s'%(sat_indx,self))

        return relevant_winds


    def get_obs( self):
        return self.route[0]

    def get_dlnk( self):
        assert(type(self.route[-1]) == DlnkWindow)
        return self.route[-1]

    def get_end( self):
        return self.route[-1]

    def has_xlnk(self):
        for wind in self.route:
            if type(wind) == XlnkWindow:
                return True

        return False

    def has_sat_indx(self,sat_indx):
        for wind in self.route:
            if wind.has_sat_indx(sat_indx): return True
        return False

    def has_gs_indx(self,gs_indx):
        for wind in self.route:
            if type(wind) == DlnkWindow and wind.has_gs_indx(gs_indx): return True
        return False

    @staticmethod
    def calc_latency(obs,dlnk,units='minutes',obs_option = 'original_end', dlnk_option = 'center'):
        lat_start = getattr(obs,obs_option)
        lat_end = getattr(dlnk,dlnk_option)
    
        if units == 'minutes':
            return (lat_end-lat_start).total_seconds()/60
        else:
            raise NotImplementedError

    def get_latency( self,units='minutes',obs_option = 'original_end', dlnk_option = 'center'):
        #  the regular start and end for these Windows gets changed by the global planner, so on subsequent passes the calculation will be different. want to avoid this
        if obs_option in ['start','end']:
            raise RuntimeWarning('Warning: should not use obs start/end for latency calculation (use original start/end)')
        if dlnk_option in ['start','end']:
            raise RuntimeWarning('Warning: should not use dlnk start/end for latency calculation (use original start/end)')

        obs =  self.route[0]
        dlnk =  self.route[-1]

        return self.calc_latency(obs,dlnk,units,obs_option,dlnk_option)

    def sort_windows(self):
        self.route.sort(key=lambda x: x.start)

    def get_route_string( self,  time_base= None):
        #  note that this function uses the mutable start and end for all the windows.  because activity windows are shared across the whole constellation simulation, these won't necessarily be correct times for every satellite

        out_string = ""

        for wind in self.route:

            if type (wind)  == ObsWindow:
                start_str =  "%.0fs" % ( wind.start-time_base).total_seconds() if  time_base else  tt.date_string(wind.start,self.output_date_str_format)
                end_str =  "%.0fs" % ( wind.end-time_base).total_seconds() if  time_base else  tt.date_string(wind.end,self.output_date_str_format)
                out_string  +=  "o %d s%d dv %.0f %s,%s" % (wind.window_ID,wind.sat_indx, wind.data_vol,start_str,end_str)
            elif type (wind)  == XlnkWindow:
                start_str =  "%.0fs" % ( wind.start-time_base).total_seconds() if  time_base else  tt.date_string(wind.start,self.output_date_str_format)
                end_str =  "%.0fs" % ( wind.end-time_base).total_seconds() if  time_base else  tt.date_string(wind.end,self.output_date_str_format)
                sat_indx=self.window_start_sats[wind]
                # xsat_indx=wind.xsat_indx  if self.window_start_sats[wind] == wind.sat_indx else wind.sat_indx
                xsat_indx=wind.get_xlnk_partner(self.window_start_sats[wind])
                out_string  +=  " -> x %d s%d,xs%d dv %.0f %s,%s" % (wind.window_ID,sat_indx, xsat_indx, wind.data_vol,start_str,end_str)
            elif type (wind)  == DlnkWindow:
                start_str =  "%.0fs" % ( wind.start-time_base).total_seconds() if  time_base else  tt.date_string(wind.start,self.output_date_str_format)
                end_str =  "%.0fs" % ( wind.end-time_base).total_seconds() if  time_base else  tt.date_string(wind.end,self.output_date_str_format)
                sat_indx= wind.sat_indx
                out_string  +=  " -> d %d s%d dv %.0f %s,%s" % (wind.window_ID,sat_indx, wind.data_vol,start_str,end_str)
        
        return out_string

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

    def validate (self,time_option='start_end',dv_epsilon=None):
        """ validates timing and ordering of route
        
        This function is used to validate the correctness of a data route within the global planner. note that it should not be used in the constellation simulation for data validation, because it relies on start and end times in the underlying activity windows,  which are not safe to use outside the global planner
        :raises: Exception, Exception, Exception
        """

        if dv_epsilon is None:
            dv_epsilon = self.dv_epsilon

        if len( self.route) == 0:
            return

        obs = self.route[0]
        if not type (obs) is ObsWindow:
            raise Exception('First window on route was not an ObsWindow instance. Route string: %s'%( self.get_route_string()))

        if not self.scheduled_dv <= self.data_vol + dv_epsilon:
            string = 'routing_objects.py: scheduled data volume (%f) is more than available data volume (%f). Route string: %s'%( self.scheduled_dv, self.data_vol, self.get_route_string())
            raise RuntimeError(string)

        curr_sat_indx = obs.sat_indx
        next_sat_indx = obs.sat_indx
        last_time = obs.start

        #  trace through the route and make sure: 1. we cross through satellites in order and 2.  every activity along the path starts after the last activity ended
        for windex, wind in  enumerate(self.route):
            if wind.original_wind_ref is not None:
                RuntimeWarning('found a copied window in data route (dr: %s)'%(self))

            if self.window_start_sats[wind] != next_sat_indx:
                string = 'routing_objects.py: Found the incorrect sat indx at window indx %d in route. Route string: %s'%( windex, self.get_route_string())
                raise RuntimeWarning(string)
            
            if time_option=='start_end':
                time_valid = wind.start >= last_time and wind.end >= last_time
            elif time_option=='center':
                time_valid = wind.center >= last_time
            else:
                raise NotImplementedError

            #  check if we have explicitly allowed this time overlap at the beginning of wind.  the overlap will be fixed in activity scheduling,  but for now we're explicitly allowing it because it was useful during route selection
            if not time_valid and wind in self.allowed_overlaps_start_wind:
                time_valid = True

            if not time_valid:
                string ='routing_objects.py: Found a bad start time at window indx %d in route. Route string: %s'%( windex, self.get_route_string())
                raise RuntimeWarning( string)

            #  note the assumption here that every data route's data volume will be less than or equal to the data volume of the observation, all of the cross-links, and the downlink
            if not self.data_vol <= wind.data_vol + dv_epsilon:
                string ='routing_objects.py: Found bad dv at window indx %d in route. Allowable dv: %f. Route string: %s'%( windex, obs.data_vol*self.obs_dv_multiplier,str(self))
                raise RuntimeWarning( string)

            #  note that we manually trace the satellite index through cross-link window here. This is a bit redundant with the functionality of window_start_sats,  but adds a little bit more of a warm, happy, comfortable feeling in the area checking
            if type (wind) is XlnkWindow:
                curr_sat_indx = next_sat_indx
                next_sat_indx=wind.get_xlnk_partner(curr_sat_indx)
                # next_sat_indx = wind.xsat_indx if not wind.xsat_indx == curr_sat_indx else wind.sat_indx

                #  if this happens to be a unidirectional window, and the current satellite index is not the transmitting satellite for that window, there's a problem
                if not wind.symmetric and curr_sat_indx != wind.tx_sat:
                    string ='routing_objects.py: Found incorrect tx sat at window indx %d in route. Route string: %s'%( windex, self.get_route_string())
                    raise RuntimeWarning(string)

            if time_option=='start_end':
                last_time = wind.end
            elif time_option=='center':
                last_time = wind.center

    @staticmethod
    def determine_window_start_sats(wind_list):
        """ trace through windows, figuring out the initial sat indx for each wind."""

        #  sort the window list first, in case it has not been already
        wind_list.sort(key=lambda w:w.start)

        window_start_sats = {}

        obs= wind_list[0]
        dlnk= wind_list[-1]
        #  a couple sanity checks that the start and end windows are correct
        assert(type(obs) == ObsWindow)
        assert(type(dlnk) == DlnkWindow)

        #  trace from the first window to the last window, storing off the initial satellite index at each window
        curr_sat_indx = obs.sat_indx
        next_sat_indx = obs.sat_indx
        for wind in wind_list:
            window_start_sats[wind] = curr_sat_indx
            if type (wind) is XlnkWindow:
                next_sat_indx=wind.get_xlnk_partner(curr_sat_indx)
            curr_sat_indx = next_sat_indx

        return window_start_sats

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

    def fix_window_copies(self,reason='allow_overlap_start_wind'):
        fixed_route = []
        fixed_window_start_sats = {}
        for wind in self.route:
            fix_wind = wind
            while fix_wind.original_wind_ref is not None:
                fix_wind = fix_wind.original_wind_ref
            fixed_route.append(fix_wind)

            if reason == 'allow_overlap_start_wind':
                #  we are replacing the copy window with its original.  the reason that we did this in the first place is contained within 'reason'
                self.allowed_overlaps_start_wind.append(fix_wind)
            else:
                raise NotImplementedError

            # This is to fix the keys in the window start sats struct. before fixing, the keys will still be be copied windows.  this isn't supercritical because the windows are looked up by hash, but could be confusing for developers down the road, so fix it now.
            fixed_window_start_sats[fix_wind] = self.window_start_sats[fix_wind]

        self.route = fixed_route
        self.window_start_sats = fixed_window_start_sats

    def add_dv(self,delta_dv):
        """Add data to the data route, without any validation"""
        self.data_vol += delta_dv

    def remove_dv(self,delta_dv):
        """Remove data from the data route, without any validation"""
        if delta_dv > self.data_vol:
            raise ValueError('Delta dv (%f) is greater than remaining dv (%f)'%(delta_dv,self.data_vol))

        self.data_vol -= delta_dv


    def contains_route(self, input_dr):
        """ check if this data route contains, at least partly, the input data route"""

        #  if the length of the other route is longer than this route, then it's impossible to contain the other route
        if len(input_dr.route) > len(self.route):
            return False

        #  check every window in both of the routes, up to the end of the other route, for equality
        contains = True
        for windex in range(len(input_dr.route)):
            contains &= input_dr.route[windex] == self.route[windex]

        return contains



class DataMultiRoute:
    """ aggregates multiple DataRoute objects
    
    Meant to represent the aggregation of multiple "simple" routes from a given observation to a given downlink. in general it's good to keep these data routes separate for the activity scheduling algorithm so that there is less potential for overlap with the Windows in other data routes. however, in the case where the data routes and activity scheduling need to have a higher minimum data volume than is achievable with the routes delivered by the route selection algorithm, then we need to aggregate multiple simple routes into a multi-route

    note that it is still valid to multiply the entire data volume of this route by a single utilization number from 0 to 1 to represent how much data volume is used from this multi-route. When constructing the multi-route, we ensure that no data volume from any given activity window is spoken for by multiple DataRoute objects within the multi-route; i.e.,  It's perfectly allowable to schedule all of the data routes within from a throughput perspective. the utilization number effectively carries through to multiply the data volumes of the individual data route objects.
    """

    # multi:  there are forks and convergences in the route; data can split out from one window to travel through multiple windows and converge back on another window.  temporal consistency must still be maintained though


    def __init__(self,ro_ID,data_routes,dv_epsilon=1e-5):

        if not type(ro_ID) == RoutingObjectID:
            raise RuntimeWarning(' should not use anything but a RoutingObjectID as the ID for a DataMultiRoute')
            
        self.ID = ro_ID

        #  all of the "simple"  data route objects contained within this multi-route
        self.data_routes = [data_route for data_route in data_routes] 
        #  this map holds the amount of data volume we have allocated to each of the data routes within this multi-route. we initially create it with all of the data volume from the initializer data routes, but it is not necessarily the case that the data volume numbers within this dict will be the same as the data volume numbers within the individual data route objects
        self.data_vol_by_dr = {dr:dr.data_vol for dr in data_routes}
        self.scheduled_dv_by_dr = {dr:const.UNASSIGNED for dr in data_routes}
        self.has_scheduled_dv = False

        self.dv_epsilon=dv_epsilon

        #  the fraction to which all the route utilizations must agree to be correct
        self.epsilon_utilization = 0.001

        for dr in data_routes:
            if not type(dr) == DataRoute:
                raise RuntimeError('only data route objects should be used to construct a new data multi-route')

    def __copy__(self):

        data_routes = [copy(data_route) for data_route in self.data_routes]
        # note: no need to copy ID
        newone = type(self)(self.ID,data_routes,self.dv_epsilon)
        newone.scheduled_dv_by_dr = {dr:self.scheduled_dv_by_dr[dr] for dr in data_routes}
        newone.has_scheduled_dv = self.has_scheduled_dv
        return newone

    def __hash__(self):
        return hash(self.ID)

    def __eq__(self, other):
        return self.ID == other.ID

    def __repr__(self):
        # return  '(DataMultiRoute %s, routes: %s)'%(self.ID,{dr.ID: self.data_vol_by_dr[dr] for dr in self.data_routes})
        return  '(DataMultiRoute %s: %s)'%(self.ID,self.get_display_string())

    def get_display_string(self):
        return 'sched/poss_dv_by_dr: %s'%({'DR - '+dr.get_route_string():'%d/%d'%(dv,self.data_vol_by_dr[dr]) for dr,dv in self.scheduled_dv_by_dr.items()})

    @property
    def data_vol(self):
        return sum(self.data_vol_by_dr.values())

    @property
    def scheduled_dv(self):
        """the scheduled data volume for this route (<= the possible data_vol for the route)"""
        # BIG FAT NOTE: this value can go stale, and should not be relied upon anywhere in the constellation sim code as the amount of dv available for this route - rather, the vanilla data_vol of the route should be multiplied by utilization to figure out how much is usable. The LPs DO NOT update the scheduled dv number, which is why it can go stale

        if self.has_scheduled_dv:
            if const.UNASSIGNED in self.scheduled_dv_by_dr.values():
                raise RuntimeWarning('Saw unassigned scheduled data volume for dr in self: %s'%(self))

            return sum(self.scheduled_dv_by_dr.values())
        else:
            return const.UNASSIGNED

    @property
    def simple_data_routes(self):
        return [dr for dr in self.data_routes]

    def get_start(self,time_opt='regular'):
        #  note the use of original time here. This is because activity windows are stored as shared objects across all routes in the sim, and original start will never change, so there's no use of "information leak"
        if time_opt == 'regular':
            return self.get_obs().start
        elif time_opt == 'original':
            return self.get_obs().original_start
        else:
            raise NotImplementedError

    def get_end(self,time_opt='regular'):
        #  note the use of original time here. This is because activity windows are stored as shared objects across all routes in the sim, and original start will never change, so there's no use of "information leak"
        if time_opt == 'regular':
            return self.get_dlnk().end
        elif time_opt == 'original':
            return self.get_dlnk().original_end
        else:
            raise NotImplementedError

    # todo: I was a little carless before and used dmr.data_vol in places to get the data vol for windows, where i should have been using data_vol_for_wind(). I think I got most of these, but it would be good to do another sweep of the code later to check. Also it would be good in general if, when getting the data volume for a window from a data route, even just a plain DataRoute, data_vol_for_wind() were used. This points to the need to make DR and DMR actually have an inheritence relationship...
    def data_vol_for_wind(self,wind):
        """Get the amount of data volume of wind used within this route"""
        wind_sum = sum(dv for dr,dv in self.data_vol_by_dr.items() if wind in dr.get_winds())

        if wind_sum == 0:
            raise KeyError('Found zero data volume for window, which assumedly means it is not in the route. self: %s, wind: %s'%(self,wind))

        return wind_sum


    def has_sat_indx(self,sat_indx):
        for dr in self.data_routes:
            if dr.has_sat_indx(sat_indx): return True
        return False

    def has_gs_indx(self,gs_indx):
        for dr in self.data_routes:
            if dr.has_gs_indx(gs_indx): return True
        return False

    def scheduled_dv_for_wind(self,wind):
        if self.has_scheduled_dv:
            # note: don't check minimum data volume here because scheduled data volume could go to zero
            return sum(s_dv for dr,s_dv in self.scheduled_dv_by_dr.items() if wind in dr.get_winds())
        else:
            return const.UNASSIGNED    

    def set_scheduled_dv(self,scheduled_dv):
        """ set the scheduled data volume for this route"""

        if scheduled_dv > self.data_vol:
            raise RuntimeWarning('Attempted to set a larger scheduled data volume (%f) than the capacity of this route (%f) (route: %s)'%(scheduled_dv,self.data_vol,self))

        sched_dv_frac = scheduled_dv/self.data_vol

        #  key assumption of the DataMultiRoute object is that data volume is distributed evenly across Windows; we want to set schedule data volume safely by using a fractional utilization
        self.set_scheduled_dv_frac(sched_dv_frac)

    def set_scheduled_dv_frac(self,fraction):
        """ set the schedule data volume for this dmr based on the utilization fraction"""
        # Note that "fraction" is really the same as utilization

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
        python_ids_by_wind = {} 
        # figure out what window data volume is already occupied by the data routes within self        
        for dr in self.data_routes:
            
            for wind in dr.get_winds():
                # make sure that all winds within the DMR are unique objects
                python_ids_by_wind.setdefault(wind, id(wind))
                if wind in python_ids_by_wind.keys():
                    assert(id(wind) == python_ids_by_wind[wind])

                #  if we didn't yet encounter this window in any of the routes in self
                avail_dv_by_wind.setdefault(wind,wind.data_vol)

                avail_dv_by_wind[wind] -= self.data_vol_by_dr[dr]

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

    def get_sched_utilization(self):
        """ get the utilization for this route is determined by its scheduled data volume"""
        # note that this utilization number is only valid for routes immediately after scheduling by the global planner ( the utilization number may be changed by the local planner)

        utilizations = [self.scheduled_dv_by_dr[dr]/self.data_vol_by_dr[dr] for dr in self.data_routes]

        util_expect = utilizations[0] 
        for util in utilizations:
            assert(abs(util - util_expect) < self.epsilon_utilization)

        #  both utilizations are the same for now
        dv_utilization = util_expect
        return dv_utilization

    def contains_route(self, input_dr):
        """ check if one of the routes within the state a multi-route  at least partly contains input data route"""
        assert(type(input_dr) == DataRoute)

        for dr in self.data_routes:
            if dr.contains_route(input_dr):
                return True

    
class LinkInfo:
    """docstring fos  LinkInfo"""
    def __init__(self,data_routes=[],total_data_vol=0,used_data_vol=0):
        self.data_routes = data_routes
        self.total_data_vol = total_data_vol
        self.used_data_vol = used_data_vol

    def __str__( self):
        return  "routes: "+str(self.data_routes) + " ; dv %.0f/%.0f Mb" % ( self.used_data_vol, self.total_data_vol)

















