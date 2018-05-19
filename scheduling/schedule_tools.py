
from copy import deepcopy

def synthesize_executable_acts(rt_conts,filter_start_dt=None,filter_end_dt=None,sat_indx=None):
    """ go through all of the route containers and synthesize a list of unique windows to execute with the correct time and the data volume utilization"""

    # First we need to find all of the executable versions of each activity window contained anywhere in the data routes in the route containers.
    exec_winds_by_wind = {}
    for rt_cont in rt_conts:
        # this is an iterable of type SimRouteContainer.ExecutableWind
        rt_cont_exec_winds = rt_cont.get_winds_executable(filter_start_dt,filter_end_dt,sat_indx)
        for exec_wind in rt_cont_exec_winds:
            exec_winds_by_wind.setdefault(exec_wind.wind, [])
            exec_winds_by_wind[exec_wind.wind].append(exec_wind)

    #  then we need to synthesize these possibly disagreeing executable versions of each activity window into a single executable version; that is, we need to figure out the time utilization and DV utilization from every Sim route container and take the maximum over those. we take the sum because every route only accounts for how much of the activity window IT needs to use. if we take the sum over all routes, then we know how much of the window we actually need to use across all routes
    executable_acts_sythesized = []
    for wind,exec_winds in exec_winds_by_wind.items():
        if len(exec_winds)>1:
            from circinus_tools import debug_tools
            debug_tools.debug_breakpt()

        # exec_wind is of type SimRouteContainer.ExecutableWind
        
        t_utils = [exec_wind.t_utilization for exec_wind in exec_winds]
        dv_utils = [exec_wind.dv_utilization for exec_wind in exec_winds]

        # make a deepcopy so we don't risk information crossing the ether in the simulation...
        wind = deepcopy(wind)
        wind.set_executable_properties(sum(t_utils),sum(dv_utils))

        executable_acts_sythesized.append(wind)

        #  do some quick sanity checks. every window should be the same, and the sum of the time and data volume utilizations should be less than or equal to full utilization (100%)
        #  note that this window equality check checks the hash of the window (window ID). they don't have to be exactly the same python runtime object, just the same activity in the simulation
        assert(all(wind == exec_wind.wind for exec_wind in exec_winds))
        assert(sum(t_utils) <= 1.0)
        assert(sum(dv_utils) <= 1.0)

    return executable_acts_sythesized


