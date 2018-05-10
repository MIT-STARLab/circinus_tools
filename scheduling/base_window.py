from datetime import timedelta

from circinus_tools  import  constants as const

class EventWindow():

    def __init__(self, start, end, window_ID):
        '''
        Creates an activity window

        :param datetime start: start time of the window
        :param datetime end: end time of the window
        :param int window_ID:  unique window ID used for hashing and comparing windows
        '''

        self.start = start
        self.end = end
        self.window_ID = window_ID

        self._center_cache = None

    def __hash__(self):
        return self.window_ID

    def __eq__(self, other):
        return self.window_ID ==  other.window_ID

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

    def __init__(self, start, end, window_ID):
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
        self.scheduled_data_vol = const.UNASSIGNED
        self.remaining_data_vol = const.UNASSIGNED

        # This holds a reference to the original window if this window was copied from another one.  used for restoring the original window from a copy
        self.original_wind_ref = None

        # Average data rate is assumed to be in seconds (for now)
        self._ave_data_rate_cache = None

        #  keeps track of if the start and end times of this window have been updated, for use as a safeguard
        self.timing_updated = False

        super().__init__(start, end, window_ID)

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
            self._ave_data_rate_cache =  self.data_vol / ( self.end - self.start).total_seconds ()
        return self._ave_data_rate_cache

    def update_duration_from_scheduled_dv( self,min_duration_s=10):
        """ update duration based on schedule data volume
        
        updates the schedule duration for the window based upon the assumption that the data volume scheduled for the window is able to be transferred at an average data rate. Updated window times are based off of the center time of the window.
        """
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

    def set_executable_properties(self,t_utilization,dv_utilization):
        """Set properties for final execution of the window"""

        if not t_utilization == dv_utilization:
            raise RuntimeWarning("Saw different t_utilization (%f) than dv_utilization (%f). This is not supported in current scheduling approach"%(t_utilization,dv_utilization))

        old_duration = self.end - self.start

        executable_duration = old_duration*t_utilization

        self.executable_start = self.center - executable_duration/2
        self.executable_end = self.center + executable_duration/2

        self.executable_data_vol = self.scheduled_data_vol*dv_utilization


def standard_time_accessor(wind,time_prop):
    if time_prop == 'start':
        return wind.start
    elif time_prop == 'end':
        return wind.end

def find_window_in_wind_list(curr_time_dt,start_windex,wind_list,time_accessor=standard_time_accessor):
    """ Step through a list of windows sorted by start time and figure out which window/window index we are currently in
    
    :param curr_time_dt: current time
    :type curr_time_dt: datetime.datetime
    :param start_windex: intial index in wind_list at which to start search
    :type start_windex: int
    :param wind_list: list of event windows
    :type wind_list: list(EventWindow)
    :returns: current window (if curr_time_dt falls within a window), current index in window list (index of first window that temporally follows or contains curr_time_dt)
    :rtype: {EventWindow,int}
    """

    if start_windex is None:
        return None, None

    # move current act window possibility forward if we're past it, and we're not yet at end of schedule
    # -1 so we only advance if we're not yet at the end
    while start_windex < len(wind_list)-1 and  curr_time_dt > wind_list[start_windex].end:
        start_windex += 1

    wind_possible = wind_list[start_windex]
    # we've found the first window for which curr_time_dt is not past its end. Check if we're actually in that wind
    if curr_time_dt >= time_accessor(wind_possible,'start') and curr_time_dt <= time_accessor(wind_possible,'end'):
        curr_wind = wind_possible
        return curr_wind,start_windex
    # if we're not in the wind, we've still found the relevant window index
    else:
        return None,start_windex
