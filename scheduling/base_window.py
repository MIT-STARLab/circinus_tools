from datetime import timedelta

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

    def set_executable_properties(self,dv_used,dv_epsilon=1e-5):
        """Set properties for scheduled execution of the window"""

        assert(dv_used <= self.data_vol + dv_epsilon)

        old_duration = self.original_end - self.original_start

        #  assume for now a linear correlation between time utilization and data volume utilization
        t_utilization = dv_used/self.data_vol if self.data_vol > dv_epsilon else 0.0
        executable_duration = old_duration*t_utilization

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