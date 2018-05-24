from datetime import timedelta

from circinus_tools.scheduling.base_window  import find_windows_in_wind_list

def propagate_sat_ES(start_time_dt,end_time_dt,sat_indx,curr_ES_state,executable_acts,sat_ecl_winds,parsed_sat_power_params,delta_t_s):
    """ propagate energy storage state forward from start time to end time, given lists of scheduled/executable activities and eclipse windows"""

    # note:  executable acts and eclipse windows should be sorted
    # note: this  code duplicates some of the functionality in SatStateSimulator update()

    delta_t_h = delta_t_s/3600.0
    delta_t_td = timedelta(seconds= delta_t_s)

    if start_time_dt > end_time_dt:
        raise RuntimeWarning('start_time_dt should not be > end_time_dt')

    # "new" is simply the next time step
    curr_time_dt = start_time_dt
    new_time_dt = start_time_dt + delta_t_td

    curr_act_windex = 0
    curr_ecl_windex = 0

    ES_state_went_below_min = False

    while new_time_dt <= end_time_dt:

        #  update time step if this is the last iteration, because the step might be smaller
        if new_time_dt == end_time_dt:
            delta_t_h = (end_time_dt-curr_time_dt).total_seconds()/3600.0

        #  find current activity, current eclipse ( if available)
        curr_acts,act_windices = find_windows_in_wind_list(curr_time_dt,curr_act_windex,executable_acts)
        curr_ecl_winds,ecl_windices = find_windows_in_wind_list(curr_time_dt,curr_ecl_windex,sat_ecl_winds)
        last_act_windex = act_windices[1]
        last_ecl_windex = ecl_windices[1]

        act_edot = 0
        for act in curr_acts:
            act_edot += parsed_sat_power_params['sat_edot_by_mode'][act.get_code(sat_indx)]

        #  base-level satellite energy usage (not including additional activities)
        base_edot = parsed_sat_power_params['sat_edot_by_mode']['base']

        if len(curr_ecl_winds) > 1:
            raise RuntimeWarning('Found more than one valid eclipse window at current time')

        #  check if we're in eclipse in which case were not charging
        charging = True
        if len(curr_ecl_winds) == 1:
            charging = False

        # add in charging energy contribution (if present)
        # assume charging is constant in sunlight
        charging_edot = parsed_sat_power_params['sat_edot_by_mode']['orbit_insunlight_average_charging'] if charging else 0

        # note: do not add noise to this state propagation (as opposed to SatStateSimulator)

        curr_ES_state =  (base_edot + charging_edot + act_edot) * delta_t_h + curr_ES_state

        # deal with cases where charging us above max batt storage
        curr_ES_state = min(curr_ES_state,parsed_sat_power_params['sat_batt_storage']['e_max'])

        #  Mark the case where the energy storage state goes below the minimum. 
        if curr_ES_state < parsed_sat_power_params['sat_batt_storage']['e_min']:
            ES_state_went_below_min = True

        if new_time_dt >= end_time_dt:
            break

        curr_time_dt = new_time_dt
        new_time_dt += delta_t_td
        new_time_dt = min(new_time_dt, end_time_dt)

    return curr_ES_state,ES_state_went_below_min