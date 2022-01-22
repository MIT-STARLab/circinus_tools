from collections import namedtuple

# used for storing TT&C update times. Note that it's implemented as two lists (t,last_update_time) of numbers as opposed to a single list of entries - inconsistent with some other history representations. Did this because I'm trying to maximize code reuse from GP.
UpdateHistory = namedtuple('UpdateHistory', 't last_update_time')

def fix_update_times(t_lut_zip_sorted,last_time):
    """[summary]
    
    this algorithm is the same as that in gp_metrics.py, get_av_aoi_routing(). "last_update_time" is the most recent time that the originating entity updated itself (i.e.  it's a creation time) and "t" is the time at which this last update time was delivered to self (i.e. it's a delivery time). We're producing a delivery/creation matrix with this code

    todo: this is suboptimal code reuse.  should merge with the stuff in GP metrics
    :param t_lut_zip_sorted: [description]
    :type t_lut_zip_sorted: [type]
    :param last_time: [description]
    :type last_time: [type]
    """

    #  start things off with the very first point
    merged_t = [t_lut_zip_sorted[0][0]]
    merged_lut = [t_lut_zip_sorted[0][1]]

    curr_time = merged_t[-1]
    curr_lut = merged_lut[-1]
    for next_item in t_lut_zip_sorted:
        next_time = next_item[0]
        next_lut = next_item[1]
        # if we received a more recent last update time at the current time, then we need to fix the last update time in the merged list
        if next_time == curr_time:
            if next_lut > curr_lut:
                curr_lut = next_lut
                merged_lut[-1] = curr_lut

        #  if the next point is a later time and also has a more recent last update time, then add to merged
        if next_time > curr_time:
            if next_lut > curr_lut:
                curr_time = next_time
                curr_lut = next_lut
                merged_t.append(curr_time)
                merged_lut.append(curr_lut)

    # want to bookend this with a last time so it's explicit what time window we're looking at
    if last_time > curr_time:
        merged_t.append(last_time)
        merged_lut.append(curr_lut)            

    return merged_t,merged_lut

def  merge_update_histories ( update_hists, end_time):
    merged_t_dirty = []
    # lut = last update time
    merged_lut_dirty = []

    #  first merge the update time histories
    for update_hist in update_hists:
        merged_t_dirty += update_hist.t
        merged_lut_dirty += update_hist.last_update_time

    # sort by t value
    zip_sorted = sorted(zip(merged_t_dirty,merged_lut_dirty),key= lambda z: z[0])

    #  there could still be duplicate t values, so let's get rid of those. Want to grab the best (most recent) lut value at each t
    merged_t,merged_lut =  fix_update_times(zip_sorted, end_time)
    
    return UpdateHistory(t=merged_t,last_update_time=merged_lut)

def get_all_sats_cmd_update_hist(sim_sats,gs_agents,gs_id_ignore_list):
    """ get command update history for all satellites
    
    for each satellite, gets the merged command update history (over all ground stations) from the satellite simulation object
    :param sim_sats: The list of Satellites, ordered by index
    :type sim_sats: list

    :param gs_agents: The list of Ground Stations, ordered by index
    :type gs_agents: list

    :param gs_id_ignore_list: The list of ground station ids to ignore
    :type gs_id_ignore_list: list

    :returns: The combined command update histogram of all satellites
    :rtype: list
    """

    all_sats_update_hist = []

    for sim_sat in sim_sats:
        cmd_update_hist = sim_sat.get_merged_cmd_update_hist(gs_agents,gs_id_ignore_list)
        all_sats_update_hist.append (cmd_update_hist)

    return all_sats_update_hist

def get_all_sats_cmd_update_hist_removed(sat_in_index_order, post_run_data):
    """
    get command update history for all satellites

    :param sat_in_index_order: The list of satellite ids in index order
    :type sat_in_index_order: list
    :param post_run_data: Post run data of all satellites
    :type post_run_data: dict
    :return: Combined command update history of all satellites
    :rtype: list
    """
    all_sats_update_hist = []
    for sat_id in sat_in_index_order:
        all_sats_update_hist.append(post_run_data[sat_id]['cmd_update_hist'])

    return all_sats_update_hist

def get_all_sats_tlm_update_hist(sim_sats,gs_agents,gs_id_ignore_list,end_time_getter):
    """ get telemetry update history for all satellites
    
    for each satellite, gets the update histories for each ground station ( from the ground station simulation object), then merges them to form a single global telemetry update history for the full ground station network
    :returns: [description]
    :rtype: {[type]}
    """

    all_sats_update_hist = []

    for sim_sat in sim_sats:
        update_hists = []
        
        # grab the update time histories from all the ground stations, for this satellite
        for sim_gs in gs_agents:
            # if we're ignoring this ground station, then continue
            if sim_gs.ID in gs_id_ignore_list:
                continue

            update_hists.append (sim_gs.get_sat_tlm_update_hist(sim_sat))

        #  merge across all ground stations
        #  By merging across all ground stations, we get a recording of when the full ground station network last heard from the satellite, which we assume is a good proxy for when satellite telemetry was last updated on the ground. ( note the underlying assumption that  telemetry arriving at any ground station is equally as valid as any other one)
        all_sats_update_hist. append ( merge_update_histories ( update_hists,end_time_getter(sim_sat)))

    return all_sats_update_hist


def get_all_sats_tlm_update_hist_removed(sat_id_order, gs_agents, gs_id_ignore_list, postRunData):
    """ get telemetry update history for all satellites

    for each satellite, gets the update histories for each ground station ( from the ground station simulation object), then merges them to form a single global telemetry update history for the full ground station network
    :param sat_id_order: The ordered list of satellite ids
    :type sat_id_order: list
    :param gs_agents: The ordered list of Ground Stations by index
    :type: list
    :param gs_id_ignore_list: List of gs ids to ignore
    :type: list
    :param postRunData: The dictionary mapping sat_ids to post run data
    :type: dict
    :returns: The combined telemetry update history
    :rtype: list
    """

    all_sats_update_hist = []

    for sat_id in sat_id_order:
        update_hists = []

        # grab the update time histories from all the ground stations, for this satellite
        for sim_gs in gs_agents:
            # if we're ignoring this ground station, then continue
            if sim_gs.ID in gs_id_ignore_list:
                continue

            update_hists.append(sim_gs.get_sat_tlm_update_hist(sat_id))

        #  merge across all ground stations
        #  By merging across all ground stations, we get a recording of when the full ground station network last heard from the satellite, which we assume is a good proxy for when satellite telemetry was last updated on the ground. ( note the underlying assumption that  telemetry arriving at any ground station is equally as valid as any other one)
        all_sats_update_hist.append(merge_update_histories(update_hists, postRunData[sat_id]['end_time']))

    return all_sats_update_hist