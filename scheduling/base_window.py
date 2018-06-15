from datetime import timedelta
from scipy.optimize import linprog
from functools import lru_cache

from circinus_tools  import  constants as const

from circinus_tools import debug_tools

class EventWindow():

    def __init__(self, start, end, window_ID, wind_obj_type='default'):
        '''
        Creates an activity window

        :param datetime start: start time of the window
        :param datetime end: end time of the window
        :param int window_ID:  unique window ID used for hashing and comparing windows
        :param wind_obj_type: an optional identifier for the type of window object - to allow multiple namespaces of window_IDs
        '''

        self.start = start
        self.end = end
        self.window_ID = window_ID
        self.wind_obj_type = wind_obj_type

        self._center_cache = None

        self.output_date_str_format = 'short'

    # See:
    # https://docs.python.org/3.4/reference/datamodel.html#object.__hash__
    # https://stackoverflow.com/questions/29435556/how-to-combine-hash-codes-in-in-python3
    def __hash__(self):
        # xor the components together ( include window object type so that we can a multiple window ID name spaces)
        return hash(self.window_ID) ^ hash(self.wind_obj_type)

    def __eq__(self, other):
        return hash(self) == hash(other)

    @property
    def center(self):
        #  adding this try except to deal with already pickled activity Windows
        if not self._center_cache:
            self._center_cache = self.calc_center()
        return self._center_cache

    @property
    def duration(self):
        return self.end - self.start

    def calc_center ( self):
        return self.start + ( self.end -  self.start)/2


class ActivityWindow(EventWindow):
    """ specifies an activity that occurs from a start to an end time
    
    note that the hash function for this class uses the window_ID attribute. This should be globally unique across all  activity window instances and subclass instances created in the simulation
    """

    def __init__(self, start, end, window_ID,wind_obj_type='default'):
        '''
        Creates an activity window

        :param datetime start: start time of the window
        :param datetime end: end time of the window
        :param int window_ID:  unique window ID used for hashing and comparing windows
        '''

        # preserving a copy of original start/end for use later
        self.original_start = start
        self.original_end = end
        self.data_vol = const.UNASSIGNED
        # this will be populated first time dv is calced
        self.original_data_vol = None
        #  scheduled data volume is the amount of data volume used for this window in the global planner.
        #  note that this value should NEVER be used in constellation sim code, directly or indirectly.  it is updated in the global planner, so if it is accessed on a satellite that could constitute "instantaneous" propagation of information from the global planner to the satellite
        self.scheduled_data_vol = const.UNASSIGNED

        # This holds a reference to the original window if this window was copied from another one.  used for restoring the original window from a copy
        self.original_wind_ref = None

        # Average data rate is assumed to be in seconds (for now)
        self._ave_data_rate_cache = None

        #  keeps track of if the start and end times of this window have been updated, for use as a safeguard
        self.timing_updated = False

        super().__init__(start, end, window_ID,wind_obj_type)

    def modify_time(self,new_dt,time_opt):
        if time_opt == 'start':
            #  populate the average data rate cache
            ave_data_rate = self.ave_data_rate
            self.timing_updated = True

            center = self.center  # note: also populates _center cache
            if new_dt > center:
                raise RuntimeWarning('should not set start to after center time')

            self.start = new_dt
            self.end = center + (center-self.start)

            # assuming linear reduction in data volume
            self.data_vol = ave_data_rate * (self.end-self.start).total_seconds()

        else:
            raise NotImplementedError

    @property
    def ave_data_rate(self):
        if not self._ave_data_rate_cache:
            if self.timing_updated: raise RuntimeWarning('Trying to calculate average data rate after window timing has been updated')
            self._ave_data_rate_cache =  self.original_data_vol / ( self.original_end - self.original_start).total_seconds ()
        return self._ave_data_rate_cache

    def has_gs_indx(self,gs_indx):
        """Check if this window has given ground station index. for general activity windows this is false"""
        return False

    def update_duration_from_scheduled_dv( self,min_duration_s=10):
        """ update duration based on schedule data volume
        
        updates the schedule duration for the window based upon the assumption that the data volume scheduled for the window is able to be transferred at an average data rate. Updated window times are based off of the center time of the window.
        """
        #  note this function should never be used in the constellation sim code, because the self.scheduled_data_vol value can't be trusted

        original_duration = self.original_end - self.original_start

        if original_duration.total_seconds() < min_duration_s:
            raise RuntimeWarning('Original duration (%f) is less than minimum allowed duration (%f) for %s'%(original_duration.total_seconds(),min_duration_s,self))

        # note that accessing ave_data_rate below either uses the cached the original ave data rate, or caches it now
        scheduled_time_s = self.scheduled_data_vol/self.ave_data_rate
        scheduled_time_s = max(scheduled_time_s,min_duration_s)

        self.start = self.center - timedelta ( seconds = scheduled_time_s/2)
        self.end = self.center + timedelta ( seconds = scheduled_time_s/2)
        #  probably good to clear the cache here for consistency after a timing update, though not strictly necessary with the way the code is implemented right now (center time stays the same)
        self._center_cache = None

        # mark that timing has been updated
        self.timing_updated = True

    def set_executable_properties(self,dv_used,act_min_duration_s=0,dv_epsilon=1e-5):
        """Set properties for scheduled execution of the window"""

        assert(dv_used <= self.data_vol + dv_epsilon)

        old_duration = self.original_end - self.original_start

        #  assume for now a linear correlation between time utilization and data volume utilization
        t_utilization = dv_used/self.data_vol if self.data_vol > dv_epsilon else 0.0
        executable_duration = max(old_duration*t_utilization,timedelta(seconds=act_min_duration_s))

        self.executable_start = self.center - executable_duration/2
        self.executable_end = self.center + executable_duration/2

        self.executable_data_vol = dv_used

    def set_executed_properties(self,start_time,end_time,dv_used,dv_epsilon=1e-5):
        """Set properties for scheduled execution of the window"""
        #  note that this code does not keep the activity centered about its original time, as we usually do. for that reason the executed attributes should never be used in scheduling code

        assert(dv_used <= self.data_vol + dv_epsilon)

        #  to verify that we are setting these to the same values if they already exist
        if hasattr(self, 'executed_start'):
            assert(self.executed_start == start_time) 
        if hasattr(self, 'executed_end'):
            assert(self.executed_end == end_time) 
        if hasattr(self, 'executed_data_vol'):
            assert(self.executed_data_vol == dv_used) 

        self.executed_start = start_time
        self.executed_end = end_time

        # todo: update center time?

        self.executed_data_vol = dv_used

    def get_dv_for_end_time(self,end_time):
        """get data volume assuming a new start time between original start time and center time"""
        # the factor of 2 is here because we assume the act is symmetric
        new_dv = (end_time - self.center).total_seconds()*self.ave_data_rate*2
        assert(new_dv >= 0)
        return new_dv

    def get_dv_for_start_time(self,start_time):
        """get data volume assuming a new end time between original end time and center time"""
        # the factor of 2 is here because we assume the act is symmetric
        new_dv = (self.center - start_time).total_seconds()*self.ave_data_rate*2
        assert(new_dv >= 0)
        return new_dv



def standard_time_accessor(wind,time_prop):
    if time_prop == 'start':
        return wind.start
    elif time_prop == 'end':
        return wind.end


def find_windows_in_wind_list(curr_time_dt,start_windex,wind_list,time_accessor=standard_time_accessor):
    """ Step through a list of windows sorted by start time and figure out which windows we are currently in.
    
    :param curr_time_dt: current time
    :type curr_time_dt: datetime.datetime
    :param start_windex: intial index in wind_list at which to start search
    :type start_windex: int
    :param wind_list: list of event windows
    :type wind_list: list(EventWindow)
    :returns: current windows (if curr_time_dt falls within a window), inclusive indices for slice within list containing these windows (index of first wind, index of last wind - NOT one past the last index!)
    :rtype: {list(EventWindow),tuple(int,int)}
    """

    if start_windex is None or len(wind_list) == 0:
        return [], (None,None)

    # move current act window possibility forward if we're past it, and we're not yet at end of schedule
    # -1 so we only advance if we're not yet at the end
    while start_windex < len(wind_list)-1 and curr_time_dt > time_accessor(wind_list[start_windex],'end'):
        start_windex += 1

    first_windex_found = start_windex
    last_windex_found = start_windex
    winds_found = []


    wind_possible = wind_list[last_windex_found]
    # continue iterating through the list, as long time still is within a window
    while curr_time_dt >= time_accessor(wind_possible,'start') and curr_time_dt <= time_accessor(wind_possible,'end'):

        winds_found.append(wind_possible)
        last_windex_found += 1

        # have to check here and not in while statement because we want to add the window to winds_found if relevant
        if last_windex_found == len(wind_list):
            break

        wind_possible = wind_list[last_windex_found]


    #  if we have found any windows at all, the last index will be one past the index of the last window found
    if len(winds_found) > 0:
        last_windex_found = last_windex_found - 1

    return winds_found,(first_windex_found,last_windex_found)


# run this function with caching, because this function is midly expensive and might be called a bunch of times (this essentially just adds the overhead of a dict mapping previous inputs to previous outputs)
# disable the actual LRU mechanism - the dict will be augmented for every new set of args
# see: https://docs.python.org/3/library/functools.html
@lru_cache(maxsize=None)
def get_pairwise_overlap_max_dv(act1,act2,transition_time_req_s):
    """determines the max amount of dv that can be moved through act 1 and then act 2 when we factor in timing overlap"""

    # notes: act2 is assumed to follow act1, and we assume that we're looking at a single contiguous stream of data volume that we're trying to move through both windows. For this reason, the max dv means that both windows carry the same dv. Assume a linear model of dv utilization change as time utilization changes. 

    assert(act2.center >= act1.center)

    # figure out when each activity ends given that 1. we utilize all of the time we possibly can from the act (up to the center time of the other act) and 2. we (symmetrically) utilize all of the time we possibly can from the OTHER act
    transition_time_req_dt = timedelta(seconds=transition_time_req_s)

    act1_end_max_act2_utilization = max(act1.center,act2.original_start-transition_time_req_dt)
    act2_start_max_act2_utilization = min(act1_end_max_act2_utilization+transition_time_req_dt,act2.center)

    act2_start_max_act1_utilization = min(act1.original_end+transition_time_req_dt,act2.center)
    act1_end_max_act1_utilization = max(act1.center,act2_start_max_act1_utilization-transition_time_req_dt)

    act1_dv_max_act1_utilization = act1.get_dv_for_end_time(act1_end_max_act1_utilization)
    act1_dv_max_act2_utilization = act1.get_dv_for_end_time(act1_end_max_act2_utilization)

    act2_dv_max_act1_utilization = act2.get_dv_for_start_time(act2_start_max_act1_utilization)
    act2_dv_max_act2_utilization = act2.get_dv_for_start_time(act2_start_max_act2_utilization)

    # figure out the best "middle point" of overlap between the two acts that maximizes dv availability for both. Solve this as a linear program because it's essentially a max(min(act1 dv, act2 dv)) problem that varies linearly with the overlap time

    # variables are: 1. dv used by BOTH act1 and act2 (trying to solve for the same dv in both) and the fractional amount of the overlap time allocated to act2
    cost = [-1,0] # negative for dv because linprog assumes minimization. No cost for the overlap fraction
    bounds = [(0,None),(0,1.0)]  # don't bound the dv term, because that is enforced in constraints
    A_ub = [[1,-1*(act1_dv_max_act2_utilization-act1_dv_max_act1_utilization)],
            [1,-1*(act2_dv_max_act2_utilization-act2_dv_max_act1_utilization)]]
    b_ub = [[act1_dv_max_act1_utilization],[act2_dv_max_act1_utilization]]

    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, bounds = bounds,method='simplex')

    if not res['status'] == 0:
        # for time being, error out...
        raise RuntimeWarning('LP not solved successfully')

    act_1_and_2_max_overlap_dv = res['x'][0]

    return act_1_and_2_max_overlap_dv

