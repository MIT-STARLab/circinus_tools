# Code that handles activity transition times and such
# 
# @author Kit Kennedy

from .scheduling.custom_window import   ObsWindow,  DlnkWindow, XlnkWindow

from circinus_tools import debug_tools

class ActivityTimingHelper:
    SUPPORTED_ORBIT_PROP_INPUTS_VERSIONS = ['0.7']

    def __init__(self,activity_params,sat_ids_by_orbit_name,sat_id_order,orbit_prop_inputs_version):
        self.sat_ids_by_orbit_name = sat_ids_by_orbit_name
        self.activity_params = activity_params
        self.activity_params_option = activity_params['params_option']
        self.sat_id_order = sat_id_order

        self.last_sat_id_by_orbit_name = {orbit_name:sats[-1] for orbit_name,sats in sat_ids_by_orbit_name.items()}
        self.first_sat_id_by_orbit_name = {orbit_name:sats[0] for orbit_name,sats in sat_ids_by_orbit_name.items()}

        #  this code very much depends on the structure of the orbit prop inputs json file, so we want to do a quick version check
        if not orbit_prop_inputs_version in self.SUPPORTED_ORBIT_PROP_INPUTS_VERSIONS:
            raise NotImplementedError


    def get_sat_orbit_name(self,sat_id):
        for orbit_name,sats in self.sat_ids_by_orbit_name.items():
            if sat_id in sats:
                return orbit_name

    def get_xlnk_orbit_crossing(self,xlnk):
        sat_id = self.sat_id_order[xlnk.sat_indx]
        xsat_id = self.sat_id_order[xlnk.xsat_indx]

        sat_orbit_name = self.get_sat_orbit_name(sat_id)
        xsat_orbit_name = self.get_sat_orbit_name(xsat_id)

        if sat_orbit_name is None:
            raise RuntimeError("Couldn't find orbit for sat_id %s"%(sat_id))
        if xsat_orbit_name is None:
            raise RuntimeError("Couldn't find orbit for sat_id %s"%(xsat_id))

        if sat_orbit_name == xsat_orbit_name:
            return "intra-orbit"
        else:
            return "inter-orbit"

    def get_xlnk_intra_orbit_direction(self,xlnk):
        tx_sat_id = self.sat_id_order[xlnk.tx_sat]
        rx_sat_id = self.sat_id_order[xlnk.rx_sat]

        #  in this case, direction is determined by increasing satellite ID ( with a wraparound for last satellite ID in the orbit). "increasing" is is determined by checking inequality of strings
        if self.activity_params['intra-orbit_neighbor_direction_method'] == 'by_increasing_id':
            tx_sat_orbit_name = self.get_sat_orbit_name(tx_sat_id)
            rx_sat_orbit_name = self.get_sat_orbit_name(rx_sat_id)

            if tx_sat_orbit_name == rx_sat_orbit_name:
                direction = "intra-orbit_decreasing"

                if tx_sat_id < rx_sat_id:
                    direction = "intra-orbit_increasing"
                #  wrap around at the last id in the orbit is also considered increasing
                if tx_sat_id == self.last_sat_id_by_orbit_name[tx_sat_orbit_name] and rx_sat_id == self.first_sat_id_by_orbit_name[rx_sat_orbit_name]:
                    direction = "intra-orbit_increasing"

                return direction

            else:
                raise RuntimeWarning('This code should not be used for a non-intra-orbit crosslink')
               
        else:
            raise NotImplementedError

    def get_xlnk_transition_type(self,xlnk1,xlnk2):
        """Very bespoke code for describing different xlnk transition conditions in a lookup table"""
        # todo: this code really should be replaced with a pointing model in future work...

        #  make sure that cross-link 2 comes after cross-link one, because the code assumes this
        assert(xlnk2.center >= xlnk1.center)

        # an intra-orbit xlnk or inter-orbit
        orbit_crossing_xlnk1 = self.get_xlnk_orbit_crossing(xlnk1)
        orbit_crossing_xlnk2 = self.get_xlnk_orbit_crossing(xlnk2)

        #  the types returned below are dependent on the input file - this is why we did the version check above
        if orbit_crossing_xlnk1 != orbit_crossing_xlnk2:
            return "intra to inter-orbit/inter to intra-orbit"

        #  if they are both intra-orbit
        elif orbit_crossing_xlnk1 == 'intra-orbit':
            if self.get_xlnk_intra_orbit_direction(xlnk1) == self.get_xlnk_intra_orbit_direction(xlnk2):
                return "intra-orbit,same direction"
            else:
                return "intra-orbit,different direction"

        #  if they are both inter-orbit
        elif orbit_crossing_xlnk1 == 'inter-orbit':
            xlnk1_tx_sat_id = self.sat_id_order[xlnk1.tx_sat]
            xlnk2_rx_sat_id = self.sat_id_order[xlnk2.rx_sat]

            # if the crosslink is between the same sats (both rx and tx matching)
            if xlnk1.tx_sat == xlnk2.tx_sat and xlnk1.rx_sat == xlnk2.rx_sat:
                return "inter-orbit,same orbit,same satellite"

            # if not both rx and tx matching, check if tx on xlnk1 and rx on xlnk2 are the same orbit (so the satellite sitting in the middle of the xlnks is rxing and then txing to same orbit)
            elif self.get_sat_orbit_name(xlnk1_tx_sat_id) == self.get_sat_orbit_name(xlnk2_rx_sat_id):
                if xlnk1_tx_sat_id == xlnk2_rx_sat_id:
                    return "inter-orbit,same orbit,same satellite"
                else:
                    return "inter-orbit,same orbit,different satellite"
            else:
                return "inter-orbit,different orbit"
        else:
            raise NotImplementedError


    def get_transition_time_req(self,act1,act2,sat_indx1,sat_indx2):
        # todo: this code needs update to deal with more context-dependent transition times

        trans_context = None
        if sat_indx1==sat_indx2:
            trans_context = 'intra-sat'
        else:
            trans_context = 'inter-sat'

        act_code1 = act1.get_codename()
        act_code2 = act2.get_codename()
        trans_activities_str = act_code1+'-'+act_code2

        act_transition_type = "default"

        if type(act1) == XlnkWindow and type(act2) == XlnkWindow:
            # Haven't yet dealt with the case where we're looking at cross-links from the perspective of different satellites (e.g. to test for tx interference)
            if not sat_indx1 == sat_indx2:
                raise NotImplementedError


            act_transition_type = self.get_xlnk_transition_type(act1,act2)

            # print(sat_indx1)
            # print(act1)
            # print(act2)
            # print(act_transition_type)
            # debug_tools.debug_breakpt()

        # get the transition time requirement between these activities
        transition_time_req_s = self.activity_params['transition_time_s'][trans_context][trans_activities_str][act_transition_type][self.activity_params_option]

        return transition_time_req_s

    # def get_max_transition_time_req(act1,sat_indx1,sat_indx2,sat_activity_params):
    #     # todo: this code needs update to deal with more context-dependent transition times

    #     trans_type = None
    #     if sat_indx1==sat_indx2:
    #         trans_type = 'intra-sat'
    #     else:
    #         trans_type = 'inter-sat'

    #     act_code1 = act1.get_codename(sat_indx1)
    #     trans_part_name = act_code1+'-'

    #      # get the max transition time requirement between these activities
    #     try:
    #         max_transition_time_req_s = max(time for key,time in sat_activity_params['transition_time_s'][trans_type].items() if trans_part_name in key)
    #     except ValueError:
    #         max_transition_time_req_s = sat_activity_params['transition_time_s']["default"]

    #     return max_transition_time_req_s      

    def get_act_min_duration(self,act):
        return self.activity_params['min_duration_s'][act.get_codename()]



