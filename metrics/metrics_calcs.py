#  contains code for assessing metrics of global planner output
#
# @author Kit Kennedy
#

# todo: clean up terminology in here

import time
from datetime import datetime, timedelta
import numpy as np

from circinus_tools  import io_tools

from circinus_tools import debug_tools

class MetricsCalcs():
    """docstring for MetricsCalcs"""

    def __init__(self, sim_params):
        """initializes based on parameters
        
        initializes based on parameters
        :param gp_params: global namespace parameters created from input files (possibly with some small non-structural modifications to params). The name spaces here should trace up all the way to the input files.
        :type params: dict
        """
        scenario_params = sim_params['orbit_prop_params']['scenario_params']
        sat_params = sim_params['orbit_prop_params']['sat_params']
        obs_params = sim_params['orbit_prop_params']['obs_params']
        sim_metrics_params = sim_params['const_sim_inst_params']['sim_metrics_params']
        sim_plot_params = sim_params['const_sim_inst_params']['sim_plot_params']
        as_params = sim_params['gp_general_params']['activity_scheduling_params']

        # these are used for AoI calculation
        self.met_obs_start_dt  = sim_params['const_sim_inst_params']['sim_run_params']['start_utc_dt']
        self.met_obs_end_dt  = sim_params['const_sim_inst_params']['sim_run_params']['end_utc_dt']

        # gp_inst_planning_params = gp_params['gp_instance_params']['planning_params']
        # gp_general_other_params = gp_params['gp_general_params']['other_params']
        # metrics_params = gp_params['gp_general_params']['metrics_params']
        # plot_params = gp_params['gp_general_params']['plot_params']

        # self.scenario_start_dt  = scenario_params['start_utc_dt']
        self.num_sats=sat_params['num_sats']
        self.num_targ = obs_params['num_targets']
        self.all_targ_IDs = [targ['id'] for targ in obs_params['targets']]
        self.min_obs_dv_dlnk_req = as_params['min_obs_dv_dlnk_req_Mb']

        self.latency_calculation_params = sim_metrics_params['latency_calculation']
        self.targ_id_ignore_list = sim_metrics_params['targ_id_ignore_list']
        self.aoi_units = sim_metrics_params['aoi_units']
        self.aoi_plot_t_units=sim_plot_params['aoi_plots']['a_axis_time_units']

        self.sats_emin_Wh = []
        self.sats_emax_Wh = []        
        for p_params in sat_params['power_params_by_sat_id'].values():
            sat_edot_by_mode,sat_batt_storage,power_units,charge_eff,discharge_eff = io_tools.parse_power_consumption_params(p_params)

        # self.sats_emin_Wh = [p_params['battery_storage_Wh']['e_min'][p_params['battery_option']] for p_params in self.power_params]
        # self.sats_emax_Wh = [p_params['battery_storage_Wh']['e_max'][p_params['battery_option']] for p_params in self.power_params]
            self.sats_emin_Wh.append(sat_batt_storage['e_min'])
            self.sats_emax_Wh.append(sat_batt_storage['e_max'])

        # the amount by which the minimum data volume is allowed to be lower than self.min_obs_dv_dlnk_req
        self.min_obs_dv_dlnk_req_slop = self.min_obs_dv_dlnk_req*0.01

        # if two downlink times are within this number of seconds, then they are counted as being at the same time for the purposes of AoI calculation
        self.dlnk_same_time_slop_s = scenario_params['timestep_s'] - 1

    def assess_dv_all_routes(self, routes,  verbose  = False):
        stats = {}

        dvs = []
        for dr in routes:
            dvs.append(dr.scheduled_dv)

        valid = len(dvs) > 0

        stats['total_dv'] = sum(dvs) if valid else 0
        stats['ave_rt_dv'] = np.mean(dvs) if valid else 0
        stats['min_rt_dv'] = np.min(dvs) if valid else 0
        stats['max_rt_dv'] = np.max(dvs) if valid else 0

        if verbose:
            print('data volume for routes')
            print("%s: %f"%('total_dv',stats['total_dv']))
            print("%s: %f"%('ave_rt_dv',stats['ave_rt_dv']))
            print("%s: %f"%('min_rt_dv',stats['min_rt_dv']))
            print("%s: %f"%('max_rt_dv',stats['max_rt_dv']))

        return stats

    @staticmethod
    def get_routes_by_obs(routes):
        rts_by_obs = {}
        for dr in routes:
            obs = dr.get_obs()
            if not obs in rts_by_obs.keys ():
                rts_by_obs[obs] = []
                
            rts_by_obs[obs].append (dr)

        return rts_by_obs

    def dr_possible_dv_getter(dr):
        return dr.data_vol
    def dr_scheduled_dv_getter(dr):
        return dr.scheduled_dv

    def assess_dv_by_obs(self, 
            possible_routes_by_obs, 
            executed_routes, 
            dr_poss_dv_getter = dr_possible_dv_getter, 
            dr_exec_dv_getter= dr_scheduled_dv_getter, 
            verbose=False):
        """ assess data volume downlinked as grouped by observation
        
        pretty straightforward, we figure out all the data routes for each observation, and calculate statistics on data volumes for each observation. We do this for both "possible" routes (e.g. all routes from route selection) and "executed" routes (e.g. scheduled routes in GP, data container routes in const sim)
        :param routes: [description]
        :type routes: [type]
        :param verbose: [description], defaults to False
        :type verbose: bool, optional
        :returns: [description]
        :rtype: {[type]}
        """

        stats = {}

        exec_rts_by_obs = self.get_routes_by_obs (executed_routes)

        dlnk_dv_check = {}

        poss_dvs_by_obs =  {}
        exec_dvs_by_obs =  {}
        num_exec_obs = 0
        num_poss_obs_dv_not_zero = 0

        for obs in possible_routes_by_obs.keys():
            poss_dvs_by_obs[obs] = min(obs.data_vol,sum (dr_poss_dv_getter(rt) for rt in possible_routes_by_obs[obs]))
            if poss_dvs_by_obs[obs] > 0:
                num_poss_obs_dv_not_zero += 1

        for obs in exec_rts_by_obs.keys():
            exec_dvs_by_obs[obs] = sum (dr_exec_dv_getter(rt) for rt in exec_rts_by_obs[obs])
            num_exec_obs +=1


        poss_dvs = [dv for dv in poss_dvs_by_obs. values ()]
        exec_dvs = [dv for dv in exec_dvs_by_obs. values ()]
        
        valid_poss = len(poss_dvs) > 0
        valid_exec = len(exec_dvs) > 0

        stats['num_obs_poss'] = len(poss_dvs)
        stats['num_obs_poss_nonzero_dv'] = num_poss_obs_dv_not_zero
        stats['num_obs_exec'] = num_exec_obs
        stats['total_poss_dv'] = sum(poss_dvs) if valid_poss else 0
        stats['total_exec_dv'] = sum(exec_dvs) if valid_exec else 0
        stats['ave_obs_dv_poss'] = np.mean(poss_dvs) if valid_poss else 0
        stats['ave_obs_dv_exec'] = np.mean(exec_dvs) if valid_exec else 0
        stats['std_obs_dv_poss'] = np.std(poss_dvs) if valid_poss else 0
        stats['std_obs_dv_exec'] = np.std(exec_dvs) if valid_exec else 0
        stats['min_obs_dv_poss'] = np.min(poss_dvs) if valid_poss else 0
        stats['min_obs_dv_exec'] = np.min(exec_dvs) if valid_exec else 0
        stats['max_obs_dv_poss'] = np.max(poss_dvs) if valid_poss else 0
        stats['max_obs_dv_exec'] = np.max(exec_dvs) if valid_exec else 0

        stats['poss_dvs_by_obs'] = poss_dvs_by_obs

        if verbose:
            print('------------------------------')
            print('data volume by observation')

            if not (valid_poss or valid_exec):
                print('no routes found, no valid statistics to display')
                return stats

            if not valid_poss:
                print('no RS routes found')
            if not valid_exec:
                print('no scheduled routes found')

            if valid_poss:
                print("%s: %f"%('num_obs_poss',stats['num_obs_poss']))
                print("%s: \t\t\t %f"%('num_obs_poss_nonzero_dv',stats['num_obs_poss_nonzero_dv']))
            if valid_exec:
                print("%s: \t\t\t\t %f"%('num_obs_exec',stats['num_obs_exec']))
            if valid_poss:
                print("%s: \t\t %f"%('total_poss_dv',stats['total_poss_dv']))
            if valid_exec:
                print("%s: \t\t\t %f"%('total_exec_dv',stats['total_exec_dv']))
            if valid_poss:
                print("%s: %f"%('ave_obs_dv_poss',stats['ave_obs_dv_poss']))
                print("%s: %f"%('std_obs_dv_poss',stats['std_obs_dv_poss']))
                print("%s: %f"%('min_obs_dv_poss',stats['min_obs_dv_poss']))
                print("%s: %f"%('max_obs_dv_poss',stats['max_obs_dv_poss']))
            if valid_exec:
                print("%s: %f"%('ave_obs_dv_exec',stats['ave_obs_dv_exec']))
                print("%s: %f"%('std_obs_dv_exec',stats['std_obs_dv_exec']))
                print("%s: %f"%('min_obs_dv_exec',stats['min_obs_dv_exec']))
                print("%s: %f"%('max_obs_dv_exec',stats['max_obs_dv_exec']))

            # for obs, dv in dvs_by_obs.items ():
            #     print("%s: %f"%(obs,dv))

        return stats

    def assess_latency_all_routes(self, routes,verbose  = False):
        """ assess latency for all routes
        
        pretty straightforward, just calculate latency for every route and then do statistics on that
        :param routes: [description]
        :type routes: [type]
        :param verbose: [description], defaults to False
        :type verbose: bool, optional
        :returns: [description]
        :rtype: {[type]}
        """
        stats = {}

        latencies = []
        for dr in routes:
            latencies.append(
                dr.get_latency(
                    'minutes',
                    obs_option = self.latency_calculation_params['obs'], 
                    dlnk_option = self.latency_calculation_params['dlnk']
                )
            )

        valid = len(latencies) > 0

        stats['ave_lat_mins'] = np.mean(latencies) if valid else None
        stats['min_lat_mins'] = np.min(latencies) if valid else None
        stats['max_lat_mins'] = np.max(latencies) if valid else None

        if verbose and valid:
            print('------------------------------')
            print('latency for routes')

            if not valid:
                print('no routes found, no valid statistics to display')
                return stats

            print("%s: %f"%('ave_lat_mins',stats['ave_lat_mins']))
            print("%s: %f"%('min_lat_mins',stats['min_lat_mins']))
            print("%s: %f"%('max_lat_mins',stats['max_lat_mins']))


        return stats

    def assess_latency_by_obs(self, rs_routes_by_obs,sched_routes, verbose=False):
        """ assess downlink latency as grouped by observation
        
        less straightforward than latency by route. First we group by observation,  then we find out how long it took to downlink the first minimum desired amount of data for each observation. based on how long this took we determin the latency of downlink for the observation.
        :param sched_routes: [description]
        :type sched_routes: [type]
        :param verbose: [description], defaults to False
        :type verbose: bool, optional
        :returns: [description]
        :rtype: {[type]}
        """
        sched_rts_by_obs = self.get_routes_by_obs (sched_routes)
        sched_obs = sched_rts_by_obs.keys()

        stats = {}

        #  for selected routes
        initial_lat_by_obs_rs =  {}
        for obs, rts in rs_routes_by_obs.items ():

            # want to make this a fair comparison. Only consider latency in rs for those obs that show up in AS
            if not obs in sched_obs:
                continue

            # start, center, end...whichever we're using for the latency calculation
            time_option = self.latency_calculation_params['dlnk']

            #  want to sort these by earliest time so that we favor earlier downlinks
            rts.sort (key=lambda rt: getattr(rt.get_dlnk(),time_option))

            #  figure out the latency for the initial minimum DV downlink
            #  have to accumulate data volume because route selection minimum data volume might be less than that for activity scheduling
            cum_dv = 0
            for dr in rts:
                cum_dv += dr.data_vol
                
                #  if we have reached our minimum required data volume amount to deem the observation downlinked for the purposes of latency calculation...
                if cum_dv >= self.min_obs_dv_dlnk_req - self.min_obs_dv_dlnk_req_slop :

                    initial_lat_by_obs_rs[obs] = dr.get_latency(
                        'minutes',
                        obs_option = self.latency_calculation_params['obs'], 
                        dlnk_option = self.latency_calculation_params['dlnk']
                    )

                    #  break so that we don't continue considering the rest of the data volume
                    break

        #  for scheduled routes
        initial_lat_by_obs =  {}
        final_lat_by_obs =  {}
        for obs, rts in sched_rts_by_obs.items ():
            # start, center, end...whichever we're using for the latency calculation
            time_option = self.latency_calculation_params['dlnk']

            #  want to sort these by earliest time so that we favor earlier downlinks
            rts.sort (key=lambda rt: getattr(rt.get_dlnk(),time_option))

            #  figure out the latency for the first route that got downlinked.
            # sanity check that its scheduled data volume meets the minimum requirement
            # assert(rts[0].scheduled_dv >= self.min_obs_dv_dlnk_req - self.min_obs_dv_dlnk_req_slop)

            #  figure out the latency for the initial minimum DV downlink
            #  have to accumulate data volume because route selection minimum data volume might be less than that for activity scheduling
            cum_dv = 0
            for dr in rts:
                cum_dv += dr.data_vol
                
                #  if we have reached our minimum required data volume amount to deem the observation downlinked for the purposes of latency calculation...
                if cum_dv >= self.min_obs_dv_dlnk_req - self.min_obs_dv_dlnk_req_slop :
                    initial_lat_by_obs[obs] = rts[0].get_latency(
                        'minutes',
                        obs_option = self.latency_calculation_params['obs'], 
                        dlnk_option = self.latency_calculation_params['dlnk']
                    )

                    #  break so that we don't continue considering the rest of the data volume
                    break

            # figure out the latency for downlink of all observation data that we chose to downlink
            final_lat_by_obs[obs] = rts[-1].get_latency(
                'minutes',
                obs_option = self.latency_calculation_params['obs'], 
                dlnk_option = self.latency_calculation_params['dlnk']
            )

        i_lats_rs = [lat for lat in initial_lat_by_obs_rs. values ()]
        i_lats_sched = [lat for lat in initial_lat_by_obs. values ()]
        f_lats_sched = [lat for lat in final_lat_by_obs. values ()]
        
        i_valid_rs = len(i_lats_rs) > 0
        i_valid_sched = len(i_lats_sched) > 0
        f_valid_sched = len(f_lats_sched) > 0

        # debug_tools.debug_breakpt()

        #  note that if center times are not used  with both the observation and downlink for calculating latency, then the route selection and scheduled the numbers might differ. this is because the scheduled numbers reflect the updated start and end time for the Windows
        stats['ave_obs_initial_lat_rs'] = np.mean(i_lats_rs) if i_valid_rs else None
        stats['std_obs_initial_lat_rs'] = np.std(i_lats_rs) if i_valid_rs else None
        stats['min_obs_initial_lat_rs'] = np.min(i_lats_rs) if i_valid_rs else None
        stats['max_obs_initial_lat_rs'] = np.max(i_lats_rs) if i_valid_rs else None
        stats['ave_obs_initial_lat_sched'] = np.mean(i_lats_sched) if i_valid_sched else None
        stats['std_obs_initial_lat_sched'] = np.std(i_lats_sched) if i_valid_sched else None
        stats['min_obs_initial_lat_sched'] = np.min(i_lats_sched) if i_valid_sched else None
        stats['max_obs_initial_lat_sched'] = np.max(i_lats_sched) if i_valid_sched else None
        stats['ave_obs_final_lat_sched'] = np.mean(f_lats_sched) if f_valid_sched else None
        stats['min_obs_final_lat_sched'] = np.min(f_lats_sched) if f_valid_sched else None
        stats['max_obs_final_lat_sched'] = np.max(f_lats_sched) if f_valid_sched else None

        stats['initial_lat_by_obs_rs'] = initial_lat_by_obs_rs
        stats['initial_lat_by_obs'] = initial_lat_by_obs
        stats['final_lat_by_obs'] = final_lat_by_obs

        if verbose:
            print('------------------------------')
            print('latencies by observation (only considering scheduled obs windows)')

            if not (i_valid_rs or i_valid_sched):
                print('no routes found, no valid statistics to display')
                return stats

            if not i_valid_rs:
                print('no RS routes found')
            if not i_valid_sched:
                print('no scheduled routes found')

            if i_valid_rs:
                print("%s: \t\t %f"%('ave_obs_initial_lat_rs',stats['ave_obs_initial_lat_rs']))
                print("%s: \t\t %f"%('std_obs_initial_lat_rs',stats['std_obs_initial_lat_rs']))
                print("%s: %f"%('min_obs_initial_lat_rs',stats['min_obs_initial_lat_rs']))
                print("%s: %f"%('max_obs_initial_lat_rs',stats['max_obs_initial_lat_rs']))

            if i_valid_sched:
                print("%s: \t\t %f"%('ave_obs_initial_lat_sched',stats['ave_obs_initial_lat_sched']))
                print("%s: \t\t %f"%('std_obs_initial_lat_sched',stats['std_obs_initial_lat_sched']))
                print("%s: %f"%('min_obs_initial_lat_sched',stats['min_obs_initial_lat_sched']))
                print("%s: %f"%('max_obs_initial_lat_sched',stats['max_obs_initial_lat_sched']))
                print("%s: %f"%('ave_obs_final_lat_sched',stats['ave_obs_final_lat_sched']))
                print("%s: %f"%('min_obs_final_lat_sched',stats['min_obs_final_lat_sched']))
                print("%s: %f"%('max_obs_final_lat_sched',stats['max_obs_final_lat_sched']))

        return stats

    @staticmethod
    def t_conv_func(t_end,t_start,input_type='datetime',output_units='hours'):
        """ converts input time range to a float difference in desired output units """
        if input_type == "datetime":
            diff = (t_end-t_start).total_seconds ()
        elif input_type == "seconds":
            diff =  t_end-t_start
        else:
            raise NotImplementedError

        if output_units == 'seconds':
            return diff
        elif output_units == 'minutes':
            return diff/60.0
        elif output_units == 'hours':
            return diff/3600.0
        else:
            raise NotImplementedError

    @staticmethod
    def calc_av_aoi( d_c_mat, start_calc_window, end_calc_window,input_type="datetime",output_units='hours'):
        """ performs AoI calculation on a formatted input matrix
        
        calculates Age of Information (AoI) based on the data in input matrix.  this is the integration process  performed by summing up the triangular sections representing an AoI curve.

        d_c_mat ( delivery creation matrix) is formatted as such:
            col0        col1
        |    0       |     0      |
        |  t_{d,1}   |  t_{c,1}   |
        |  t_{d,2}   |  t_{c,2}   |
        |  t_{d,3}   |  t_{c,3}   |
        |   ...      |   ...      |    
        |  t_{d,T-1} |  t_{c,T-1} |
        |  t_{d,T}   | dont care  |

        where 'd' stands for delivery, 'c' stands for creation, and T  is the number of time points.

        These points are shown notionally below

        |             /|                         
        |      /|    / |                       /.
        |     / |   /  |  /|                  / .
        |    /  |  /   | / |       (etc)     /  .
        |   /   | /    |/  | /                  .
        |  /    |/     .   |/                   .
        | /     .     ..   .                    .
        |/_____..____._.__..____________________.___
        0      ^^    ^ ^  ^^                    ^
              1a,b   2a,b 3a,b                  Ta
             
        1a: t_{c,1}
        1b: t_{d,1}
        2a: t_{c,2}
        2b: t_{d,2}
        3a: t_{c,3}
        3b: t_{d,3}
        ...
        Ta: t_{d,T}

        When calculating AOI, we sum up a series of triangles defined by the creation and delivery times for data. For each of the time points above, at 'b' new data is being delivered to a destination. At 'a', this data was created. Therefore  the data is already as old as the time between 'a' and 'b' when it arrives at the destination. During the time between 't-1 b' and 't b' the data that was delivered at 't-1 b' is aging, without any updates. At 't b' we receive updated data, that again, already has some age. So we go through all the timepoints summing up the triangle specified by 't-1 b' and 't b', with the tip from 't-1 a' to 't-1 b' subtracted (which actually leaves us with a trapezoid).  once we sum up all of these trapezoids, we divide by the total time to get a time-averaged age of data (or AoI).

        TODO:  update this reference when I  actually publish the equation...
        This calculation is performed per equation ? in ?

        :param d_c_mat: [description]
        :type d_c_mat: [type]
        :param start_calc_window: [description]
        :type start_calc_window: [type]
        :param end_calc_window: [description]
        :type end_calc_window: [type]
        :param input_type: [description], defaults to "datetime"
        :type input_type: str, optional
        :param output_units: [description], defaults to 'hours'
        :type output_units: str, optional
        :returns: [description]
        :rtype: {[type]}
        """

        # Now sum up trapezoidal sections of AoI curve (integration)

        conv_func = MetricsCalcs.t_conv_func

        aoi_summation = 0
        for t in range(1,len(d_c_mat)):
            trap_addition = (conv_func(d_c_mat[t][0],d_c_mat[t-1][1],input_type,output_units)**2 - conv_func(d_c_mat[t-1][0],d_c_mat[t-1][1],input_type,output_units)**2)/2
            aoi_summation += trap_addition

        av_aoi = aoi_summation / conv_func(end_calc_window,start_calc_window,input_type,output_units)
        return av_aoi

    @staticmethod
    def get_aoi_curve(d_c_mat,base_time,input_type="datetime",x_units='minutes',y_units='hours'):
        """get X and Y for plotting AoI
        
        [description]
        :param d_c_mat: [description]
        :type d_c_mat: [type]
        :param base_time: [description]
        :type base_time: [type]
        :param input_type: [description], defaults to "datetime"
        :type input_type: str, optional
        :param x_units: [description], defaults to 'minutes'
        :type x_units: str, optional
        :param y_units: [description], defaults to 'hours'
        :type y_units: str, optional
        """
        
        conv_func = MetricsCalcs.t_conv_func

        x = []
        y = []
        for indx, row in  enumerate (d_c_mat):
            if indx==0:
                x.append(conv_func(row[0],base_time,input_type,x_units))
                y.append(conv_func(row[0],row[1],input_type,y_units))
            else:
                last_row = d_c_mat[indx-1]
                x.append(conv_func(row[0],base_time,input_type,x_units))
                y.append(conv_func(row[0],last_row[1],input_type,y_units))
                x.append(conv_func(row[0],base_time,input_type,x_units))
                y.append(conv_func(row[0],row[1],input_type,y_units))

        aoi_curve = {
            'x': x,
            'y': y
        }
        return aoi_curve

    @staticmethod
    def get_av_aoi_routing(d_c_mat_targ,start_calc_window,end_calc_window,dlnk_same_time_slop_s,aoi_units='hours',aoi_plot_t_units='minutes'):
        """ preprocess delivery creation matrix and do AoI calculation, with routing
        
        this code first pre-processes the matrix to get rid of superfluous information that would throw off the AoI calculation. This essentially smooths down the data to the saw-like shape expected for an AoI (versus time) curve.  in the preprocessing we progress through delivery (downlink) times, looking for the earliest creation (observation) time for each delivery time. Here we account for the fact that it can take time to deliver data after its creation
        :param d_c_mat_targ:  the delivery creation matrix for a given target (list of lists, each of two elements - delivery, creation time)
        :type d_c_mat_targ: list(list)
        :param start_calc_window: the start of the window for calculating AoI
        :type start_calc_window: datetime or float
        :param end_calc_window: the end of the window for calculating AoI
        :type end_calc_window: datetime or float
        :param dlnk_same_time_slop_s:  the time delta by which delivery times can differ and still be considered the same time
        :type dlnk_same_time_slop_s: float
        :param output_units:  the time output units used for AoI, defaults to 'hours'
        :type output_units: str, optional
        """

        #  this builds in the assumption that AoI starts at zero time zero
        d_c_mat_filt = [[start_calc_window,start_calc_window]]

        current_time = start_calc_window
        last_creation_time = start_calc_window

        for mat_indx, row in enumerate(d_c_mat_targ):
            if row[0] > current_time:
                current_time = row[0]  # update to most recent delivery (downlink) time

                # the check here with last_creation_time is what ensures that creation (observation) times are always increasing - we want this when looking at data routing for the following reason: it's not helpful to hear later about an earlier event than we previously knew about - because that information does not help us make better TIME SENSITIVE decisions
                if (row[1] > last_creation_time):
                    last_creation_time = row[1]
                    #  add data delivery time (the current time) and the creation time of that data
                    d_c_mat_filt.append([current_time,last_creation_time])

            # if this next row has the same delivery time as previous one
            elif (row[0]-current_time).total_seconds() <= dlnk_same_time_slop_s:

                # but if the creation time of this row is BEFORE what's currently in the d_c mat...
                # (have to check this because we only sorted by delivery time before - not assuming that we also sorted by creation time under each distinct delivery time)
                if (row[1] > last_creation_time):
                    last_creation_time = row[1]
                    d_c_mat_filt[-1][1] = last_creation_time  #replace the last creation time, because it turns out we've seen it more recently

        # add on end time - important for getting proper AoI over whole scenario (first point (start_calc_window,start_calc_window) was already added on matrix)
        d_c_mat_filt.append([end_calc_window,end_calc_window])


        avaoi = MetricsCalcs.calc_av_aoi( d_c_mat_filt, start_calc_window, end_calc_window,input_type="datetime",output_units=aoi_units)
        aoi_curve = MetricsCalcs.get_aoi_curve(d_c_mat_filt,start_calc_window,input_type="datetime",x_units=aoi_plot_t_units,y_units=aoi_units)

        return avaoi, aoi_curve

    

    @staticmethod
    def get_av_aoi_no_routing(d_c_mat_targ,start_calc_window,end_calc_window,aoi_units='hours',aoi_plot_t_units='minutes'):
        """ preprocess delivery creation matrix and do AoI calculation, without routing
        
        this code first pre-processes the matrix to get rid of superfluous information that would throw off the AoI calculation. This essentially smooths down the data to the saw-like shape expected for an AoI (versus time) curve.  in the preprocessing we progress through delivery (downlink) times, looking for the earliest creation (observation) time for each delivery time. Here we assume that delivery time equals creation time
        :param d_c_mat_targ:  the delivery creation matrix for a given target (list of lists, each of two elements - delivery, creation time)
        :type d_c_mat_targ: list(list)
        :param start_calc_window: the start of the window for calculating AoI
        :type start_calc_window: datetime or float
        :param end_calc_window: the end of the window for calculating AoI
        :type end_calc_window: datetime or float
        :param dlnk_same_time_slop_s:  the time delta by which delivery times can differ and still be considered the same time
        :type dlnk_same_time_slop_s: float
        :param output_units:  the time output units used for AoI, defaults to 'hours'
        :type output_units: str, optional
        """

        #  this builds in the assumption that AoI starts at zero time zero
        d_c_mat_filt = [[start_calc_window,start_calc_window]]

        last_creation_time = start_calc_window

        for mat_indx, row in enumerate(d_c_mat_targ):
            if row[1] > last_creation_time:
                last_creation_time = row[1]
                # right here we're effectively saying that delivery time is the same as creation time
                # (this will cause a cancellation of the second term in the AoI summation equation)
                d_c_mat_filt.append([last_creation_time,last_creation_time])

        # add on end time - important for getting proper AoI over whole scenario (first point (start_calc_window) was already added on matrix)
        d_c_mat_filt.append([end_calc_window,end_calc_window])

        avaoi = self.calc_av_aoi( d_c_mat_filt, start_calc_window, end_calc_window,input_type="datetime",output_units=aoi_units)
        aoi_curve = self.get_aoi_curve(d_c_mat_filt,start_calc_window,input_type="datetime",x_units=aoi_plot_t_units,y_units=aoi_units)

        return avaoi, aoi_curve

    def preprocess_and_get_aoi(self,rts_by_obs,include_routing,dv_option='scheduled_dv'):
        #  note: I'm not particularly happy with how the code in this function and called by this function turned out ( it's messy). someday should try to re-factor it. TODO: refactor it

        av_aoi_by_targID = {}
        aoi_curves_by_targID = {}

        # First we need to seperate downlink time and creation time of all obs taken for this target. Put these into a matrix for convenient sorting.
        # for each row of dlnk_obs_times_mat[targ_indx]:
        # column 1 is downlink time
        # column 2 is observation time
        dlnk_obs_times_mat = [[] for targ_indx in range(self.num_targ)]

        # start, center, end...whichever we're using for the latency calculation
        time_option = self.latency_calculation_params['dlnk']


        for obs_wind,rts in rts_by_obs.items():

            for targ_ID in obs_wind.target_IDs:

                # skip explicitly ignored targets
                if targ_ID in  self.targ_id_ignore_list:
                    continue

                targ_indx = self.all_targ_IDs.index(targ_ID)

                if not include_routing:
                    # add row for this observation. Note: there should be no duplicate observations in obs_winds
                    dlnk_obs_times_mat[targ_indx].append([None,obs_wind.start])

                else:
                    #  want to sort these by earliest time so that we favor earlier downlinks
                    rts.sort (key=lambda rt: getattr(rt.get_dlnk(),time_option))

                    # figure out at which data route we meet the minimum DV downlink requirement
                    cum_dv = 0
                    for dr in rts:
                        if dv_option == 'scheduled_dv':
                            cum_dv += dr.scheduled_dv
                        elif dv_option == 'possible_dv':
                            cum_dv += dr.data_vol
                        else:
                            raise NotImplementedError

                        #  if we have reached our minimum required data volume amount...
                        if cum_dv >= self.min_obs_dv_dlnk_req - self.min_obs_dv_dlnk_req_slop:

                            dlnk_obs_times_mat[targ_indx].append([getattr(dr.get_dlnk(),time_option), obs_wind.start])
                            #  break because we shouldn't count additional down links from the same observation ( they aren't delivering updated information)
                            break

        if len(rts_by_obs.keys()) > 0:
            for targ_indx in range(self.num_targ):

                targ_ID = self.all_targ_IDs[targ_indx]

                # skip explicitly ignored targets
                if targ_ID in  self.targ_id_ignore_list:
                    continue

                dlnk_obs_times_mat_targ = dlnk_obs_times_mat[targ_indx]

                if not include_routing:
                    dlnk_obs_times_mat_targ.sort(key=lambda row: row[1])  # sort by creation time

                    av_aoi,aoi_curve = self.get_av_aoi_no_routing(dlnk_obs_times_mat_targ, self.met_obs_start_dt, self.met_obs_end_dt,aoi_units=self.aoi_units,aoi_plot_t_units=self.aoi_plot_t_units)

                else:
                    dlnk_obs_times_mat_targ.sort(key=lambda row: row[0])  # sort by downlink time

                    av_aoi,aoi_curve = self.get_av_aoi_routing(dlnk_obs_times_mat_targ,  self.met_obs_start_dt,self.met_obs_end_dt,self.dlnk_same_time_slop_s,aoi_units=self.aoi_units,aoi_plot_t_units=self.aoi_plot_t_units)
                
                av_aoi_by_targID[targ_ID] = av_aoi
                aoi_curves_by_targID[targ_ID] = aoi_curve

        return av_aoi_by_targID,aoi_curves_by_targID

    def assess_aoi_by_obs_target(self,rs_routes_by_obs,sched_routes,verbose = True):

        sched_rts_by_obs = self.get_routes_by_obs (sched_routes)

        include_routing=True

        rs_targIDs_found = list(set([targ_ID for obs in rs_routes_by_obs.keys() for targ_ID in obs.target_IDs]))
        as_targIDs_found = list(set([targ_ID for obs in sched_rts_by_obs.keys() for targ_ID in obs.target_IDs]))

        av_aoi_by_targID_rs,aoi_curves_by_targID_rs = self.preprocess_and_get_aoi(rs_routes_by_obs,include_routing,dv_option='possible_dv')
        av_aoi_by_targID_sched,aoi_curves_by_targID_sched = self.preprocess_and_get_aoi(sched_rts_by_obs,include_routing,dv_option='scheduled_dv')

        valid_rs = len(av_aoi_by_targID_rs.keys()) > 0
        valid_sched = len(av_aoi_by_targID_sched.keys()) > 0

        stats =  {}
        av_aoi_vals_rs = [av_aoi for targID,av_aoi in av_aoi_by_targID_rs.items() if targID in rs_targIDs_found]
        av_aoi_vals_sched = [av_aoi for targID,av_aoi in av_aoi_by_targID_sched.items() if targID in as_targIDs_found]
        stats['av_av_aoi_rs'] = np.mean(av_aoi_vals_rs) if valid_rs else None
        stats['av_av_aoi_sched'] = np.mean(av_aoi_vals_sched) if valid_sched else None
        stats['std_av_aoi_rs'] = np.std(av_aoi_vals_rs) if valid_rs else None
        stats['std_av_aoi_sched'] = np.std(av_aoi_vals_sched) if valid_sched else None
        stats['min_av_aoi_rs'] = np.min(av_aoi_vals_rs) if valid_rs else None
        stats['min_av_aoi_sched'] = np.min(av_aoi_vals_sched) if valid_sched else None
        stats['max_av_aoi_rs'] = np.max(av_aoi_vals_rs) if valid_rs else None
        stats['max_av_aoi_sched'] = np.max(av_aoi_vals_sched) if valid_sched else None

        stats['rs_targIDs_found'] = rs_targIDs_found
        stats['as_targIDs_found'] = as_targIDs_found
        stats['av_aoi_by_targID_rs'] = av_aoi_by_targID_rs
        stats['av_aoi_by_targID_sched'] = av_aoi_by_targID_sched
        stats['aoi_curves_by_targID_rs'] = aoi_curves_by_targID_rs
        stats['aoi_curves_by_targID_sched'] = aoi_curves_by_targID_sched

        if verbose:
            print('------------------------------')
            print('AoI values (considering all obs windows from RS)')

            if not (valid_rs or valid_sched):
                print('no routes found, no valid statistics to display')
                return stats

            if not valid_rs:
                print('no RS routes found')
            if not valid_sched:
                print('no scheduled routes found')

            if valid_rs:
                print('num rs targ IDs: %d'%(len(rs_targIDs_found)))
                print("%s: \t\t\t\t %f"%('av_av_aoi_rs',stats['av_av_aoi_rs']))
                print("%s: %f"%('std_av_aoi_rs',stats['std_av_aoi_rs']))
                print("%s: %f"%('min_av_aoi_rs',stats['min_av_aoi_rs']))
                print("%s: %f"%('max_av_aoi_rs',stats['max_av_aoi_rs']))
            if valid_sched:
                print('num as targ IDs: %d'%(len(as_targIDs_found)))
                print("%s: \t\t\t %f"%('av_av_aoi_sched',stats['av_av_aoi_sched']))
                print("%s: %f"%('std_av_aoi_sched',stats['std_av_aoi_sched']))
                print("%s: %f"%('min_av_aoi_sched',stats['min_av_aoi_sched']))
                print("%s: %f"%('max_av_aoi_sched',stats['max_av_aoi_sched']))

            # for targ_ID in av_aoi_by_targID.keys ():
            #     avaoi = av_aoi_by_targID.get(targ_ID,None)
            #     print("targ_ID %d: av aoi %f"%(targ_ID,avaoi))

        return stats

    @staticmethod
    def  get_aoi_results(update_hists, num_entities,aoi_units,t_units):
        av_aoi_vals = []
        av_aoi_by_ent_indx = {}
        aoi_curves_vals = []
        aoi_curves_by_ent_indx = {}

        for ent_indx in range(num_entities):

            update_hist = update_hists[ent_indx]
            d_c_mat = [[t,lut] for t,lut in zip(update_hist.t,update_hist.last_update_time)]

            start_time = d_c_mat[0][0]
            end_time = d_c_mat[-1][0]
            av_aoi = MetricsCalcs.calc_av_aoi( d_c_mat, start_time, end_time,input_type="seconds",output_units=aoi_units)
            aoi_curve = MetricsCalcs.get_aoi_curve(d_c_mat,start_time,input_type="seconds",x_units=t_units,y_units=aoi_units)
            
            av_aoi_vals.append(av_aoi)
            aoi_curves_vals.append(aoi_curve)
            av_aoi_by_ent_indx[ent_indx] = av_aoi
            aoi_curves_by_ent_indx[ent_indx] = aoi_curve

        return av_aoi_vals,av_aoi_by_ent_indx,aoi_curves_vals,aoi_curves_by_ent_indx


    def assess_aoi_sat_cmd(self,sats_cmd_update_hist,verbose = True):
        (av_aoi_vals,
            av_aoi_by_sat_indx,
            aoi_curves_vals,
            aoi_curves_by_sat_indx) = self.get_aoi_results(
                sats_cmd_update_hist,
                self.num_sats,
                self.aoi_units,
                self.aoi_plot_t_units)

        valid = len(av_aoi_vals) > 0

        stats =  {}
        stats['av_av_aoi'] = np.mean(av_aoi_vals) if valid else None
        stats['min_av_aoi'] = np.min(av_aoi_vals) if valid else None
        stats['max_av_aoi'] = np.max(av_aoi_vals) if valid else None
        stats['std_av_aoi'] = np.std(av_aoi_vals) if valid else None

        stats['av_aoi_by_sat_indx'] = av_aoi_by_sat_indx
        stats['aoi_curves_by_sat_indx'] = aoi_curves_by_sat_indx

        if verbose:
            print('------------------------------')
            print('Sat CMD AoI values')
            print("%s: \t\t\t\t %f"%('av_av_aoi',stats['av_av_aoi']))
            print("%s: %f"%('min_av_aoi',stats['min_av_aoi']))
            print("%s: %f"%('max_av_aoi',stats['max_av_aoi']))
            print("%s: %f"%('std_av_aoi',stats['std_av_aoi']))

            # for sat_indx in range(self.num_sats):
            #     avaoi = av_aoi_by_sat_indx.get(sat_indx,None)
            #     print("sat_indx %d: av aoi %f"%(sat_indx,avaoi))

        return stats

    def assess_aoi_sat_tlm(self,sats_tlm_update_hist,verbose = True):
        (av_aoi_vals,
            av_aoi_by_sat_indx,
            aoi_curves_vals,
            aoi_curves_by_sat_indx) =  self.get_aoi_results(
                sats_tlm_update_hist,
                self.num_sats,
                self.aoi_units,
                self.aoi_plot_t_units)

        valid = len(av_aoi_vals) > 0

        stats =  {}
        stats['av_av_aoi'] = np.mean(av_aoi_vals) if valid else None
        stats['min_av_aoi'] = np.min(av_aoi_vals) if valid else None
        stats['max_av_aoi'] = np.max(av_aoi_vals) if valid else None
        stats['std_av_aoi'] = np.std(av_aoi_vals) if valid else None

        stats['av_aoi_by_sat_indx'] = av_aoi_by_sat_indx
        stats['aoi_curves_by_sat_indx'] = aoi_curves_by_sat_indx

        if verbose:
            print('------------------------------')
            print('Sat TLM AoI values')
            print("%s: \t\t\t\t %f"%('av_av_aoi',stats['av_av_aoi']))
            print("%s: %f"%('min_av_aoi',stats['min_av_aoi']))
            print("%s: %f"%('max_av_aoi',stats['max_av_aoi']))
            print("%s: %f"%('std_av_aoi',stats['std_av_aoi']))

            # for sat_indx in range(self.num_sats):
            #     avaoi = av_aoi_by_sat_indx.get(sat_indx,None)
            #     print("sat_indx %d: av aoi %f"%(sat_indx,avaoi))

        return stats



    def assess_resource_margin(self,energy_usage,verbose = True):

        e_margin_by_sat_indx = {}
        ave_e_margin = []
        ave_e_margin_prcnt = []
        min_e_margin = []
        min_e_margin_prcnt = []
        max_e_margin = []
        max_e_margin_prcnt = []
        if energy_usage:
            for sat_indx in range (self.num_sats):
                e_margin = [e - self.sats_emin_Wh[sat_indx] for e in energy_usage['e_sats'][sat_indx]]
                max_margin = self.sats_emax_Wh[sat_indx]-self.sats_emin_Wh[sat_indx]
                e_margin_prcnt = [100*(e - self.sats_emin_Wh[sat_indx])/max_margin for e in energy_usage['e_sats'][sat_indx]]

                e_ave = np.mean(e_margin)
                e_ave_prcnt = np.mean(e_margin_prcnt)
                e_max = np.max(e_margin)
                e_max_prcnt = np.max(e_margin_prcnt)
                e_min = np.min(e_margin)
                e_min_prcnt = np.min(e_margin_prcnt)
                e_margin_by_sat_indx[sat_indx] = {
                    "ave": e_ave,
                    "max": e_max,
                    "min": e_min
                }

                ave_e_margin.append(e_ave)
                ave_e_margin_prcnt.append(e_ave_prcnt)
                min_e_margin.append(e_min)
                min_e_margin_prcnt.append(e_min_prcnt)
                max_e_margin.append(e_max)
                max_e_margin_prcnt.append(e_max_prcnt)

        valid = len(ave_e_margin) > 0

        stats =  {}
        stats['av_ave_e_margin'] = np.mean(ave_e_margin) if valid else None
        stats['av_ave_e_margin_prcnt'] = np.mean(ave_e_margin_prcnt) if valid else None
        stats['min_ave_e_margin'] = np.min(ave_e_margin) if valid else None
        stats['min_ave_e_margin_prcnt'] = np.min(ave_e_margin_prcnt) if valid else None
        stats['max_ave_e_margin'] = np.max(ave_e_margin) if valid else None
        stats['max_ave_e_margin_prcnt'] = np.max(ave_e_margin_prcnt) if valid else None
        stats['std_ave_e_margin'] = np.std(ave_e_margin) if valid else None
        stats['std_ave_e_margin_prcnt'] = np.std(ave_e_margin_prcnt) if valid else None
        stats['min_min_e_margin'] = np.min(min_e_margin) if valid else None
        stats['min_min_e_margin_prcnt'] = np.min(min_e_margin_prcnt) if valid else None


        if verbose:
            print('------------------------------')
            print('Sat energy margin values')

            if not valid:
                print('no routes found, no valid statistics to display')
                return stats

            # print("%s: %f"%('av_ave_e_margin',stats['av_ave_e_margin']))
            print("%s: %f%%"%('av_ave_e_margin_prcnt',stats['av_ave_e_margin_prcnt']))
            # print("%s: %f"%('min_ave_e_margin',stats['min_ave_e_margin']))
            print("%s: %f%%"%('min_ave_e_margin_prcnt',stats['min_ave_e_margin_prcnt']))
            # print("%s: %f"%('max_ave_e_margin',stats['max_ave_e_margin']))
            print("%s: %f%%"%('max_ave_e_margin_prcnt',stats['max_ave_e_margin_prcnt']))
            # print("%s: %f"%('std_ave_e_margin',stats['std_ave_e_margin']))
            print("%s: %f%%"%('std_ave_e_margin_prcnt',stats['std_ave_e_margin_prcnt']))
            # print("%s: %f"%('min_min_e_margin',stats['min_min_e_margin']))
            print("%s: %f%%"%('min_min_e_margin_prcnt',stats['min_min_e_margin_prcnt']))

            # for sat_indx in range(self.num_sats):
            #     print("sat_indx %d: av e margin %f"%(sat_indx,e_margin_by_sat_indx[sat_indx]['ave']))
            #     print("sat_indx %d: min e margin %f"%(sat_indx,e_margin_by_sat_indx[sat_indx]['min']))
            #     print("sat_indx %d: max e margin %f"%(sat_indx,e_margin_by_sat_indx[sat_indx]['max']))

        return stats