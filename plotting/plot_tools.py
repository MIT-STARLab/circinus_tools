from math import floor
from functools import partial

import matplotlib.pyplot as plt
from matplotlib.pyplot import savefig
from matplotlib.patches import Rectangle, Circle

from circinus_tools import debug_tools

def plot_window_schedule(current_axis,winds,get_start_func,get_end_func,sat_plot_params,label_getter,color_getter=None):

    viz_object_rotator_hist = sat_plot_params['viz_object_rotator_hist']
    label_rotator_hist = sat_plot_params['label_rotator_hist']

    base_time_dt = sat_plot_params['base_time_dt']

    viz_objects = []

    viz_object_rotator = 0
    label_rotator = 0

    # plot the activity Windows
    if winds and len(winds) > 0:
        for wind in winds:

            act_start = (get_start_func(wind)-base_time_dt).total_seconds()/sat_plot_params['time_divisor']
            act_end = (get_end_func(wind)-base_time_dt).total_seconds()/sat_plot_params['time_divisor']

            #  check if the activity is out of the time bounds for the plot or overlapping them
            out_of_bounds = get_end_func(wind) < sat_plot_params['plot_start_dt'] or get_start_func(wind) > sat_plot_params['plot_end_dt']
            overlapping_bounds = get_start_func(wind) < sat_plot_params['plot_start_dt'] or get_end_func(wind) > sat_plot_params['plot_end_dt']

            if out_of_bounds:
                continue

            # This vertically rotates the location of the visualization object on the plot (e.g. the rectangle drawn for an activity)
            #  update the rotator value if we've already added this window to the plot in the "choices" code above
            viz_object_rotator = viz_object_rotator_hist.get(wind,viz_object_rotator)
            bottom_base_vert_loc = viz_object_rotator
            bottom_vert_loc= bottom_base_vert_loc + sat_plot_params['viz_object_vert_bottom_base_offset']

            hatch = None
            fill = True
            if sat_plot_params['plot_hatch']:
                fill = False
                hatch = '///////'
                if overlapping_bounds:
                    hatch = '.'

            if color_getter:
                color = color_getter(wind)
            else:
                color = sat_plot_params['plot_color']

            # plot the task duration
            viz_object = Rectangle((act_start, bottom_vert_loc), act_end-act_start, bottom_vert_loc+1,alpha=1,fill=fill,color=color,hatch=hatch)
            current_axis.add_patch(viz_object)
            viz_objects.append(viz_object)

            #  update viz object rotator
            viz_object_rotator_hist.setdefault(wind,viz_object_rotator)
            viz_object_rotator = (viz_object_rotator+1)% sat_plot_params['viz_object_rotation_rollover']

            if sat_plot_params['include_labels']:
                if not label_getter: 
                    raise RuntimeError('Expected label generator function')

                label_text = label_getter(wind)

                #  figure out label location
                #   put label in desired vertical spot
                left_horizontal_loc = act_start + sat_plot_params['label_horz_offset']
                #  update the rotator value if we've already added this window to the plot before
                if label_rotator_hist:
                    label_rotator = label_rotator_hist.get(wind,label_rotator)
                bottom_vert_loc= bottom_base_vert_loc + sat_plot_params['label_vert_bottom_base_offset'] + label_rotator * sat_plot_params['label_vert_spacing']

                #  add label
                plt.text(left_horizontal_loc, bottom_vert_loc, label_text , fontsize=sat_plot_params['fontsize'], color = 'k')

                #  update label rotator
                label_rotator = (label_rotator+1)% sat_plot_params['label_rotation_rollover']
                label_rotator_hist.setdefault(wind,label_rotator)

    return viz_objects

def get_start(wind):
    return wind.start
def get_start_original(wind):
    return wind.original_start

def get_end(wind):
    return wind.end
def get_end_original(wind):
    return wind.original_end

def plot_all_agents_acts(
    agents_ids_list,
    agents_obs_winds_choices,
    agents_obs_winds,
    agents_dlnk_winds_choices,
    agents_dlnk_winds, 
    agents_xlnk_winds_choices,
    agents_xlnk_winds,
    plot_params):
    '''
    Displays a 2D plot of assignments for each agent with respect to time

    '''

    # input params dict handling
    route_ids_by_wind = plot_params.get('route_ids_by_wind',None)
    plot_start_dt = plot_params['plot_start_dt']
    plot_end_dt = plot_params['plot_end_dt']
    base_time_dt = plot_params['base_time_dt']
    agent_id_order = plot_params['agent_id_order']

    plot_title = plot_params.get('plot_title','Activities Plot')
    y_label = plot_params.get('y_label','Satellite Index')
    plot_size_inches = plot_params.get('plot_size_inches',(12,12))
    plot_include_obs_labels = plot_params.get('plot_include_obs_labels',False)
    plot_include_xlnk_labels = plot_params.get('plot_include_xlnk_labels',False)
    plot_include_dlnk_labels = plot_params.get('plot_include_dlnk_labels',False)
    show = plot_params.get('show',False)
    fig_name = plot_params.get('fig_name','plots/xlnk_dlnk_plot.pdf')
    time_units = plot_params.get('time_units','minutes')
    plot_fig_extension = plot_params.get('plot_fig_extension','pdf')

    plot_xlnks_choices = plot_params.get('plot_xlnks_choices',True)
    plot_dlnks_choices = plot_params.get('plot_dlnks_choices',True)
    plot_obs_choices = plot_params.get('plot_obs_choices',True)
    plot_xlnks = plot_params.get('plot_xlnks',True)
    plot_dlnks = plot_params.get('plot_dlnks',False)
    plot_obs = plot_params.get('plot_obs',False)

    xlnk_label_getter = plot_params.get('xlnk_label_getter_func',None)
    dlnk_label_getter = plot_params.get('dlnk_label_getter_func',None)
    obs_label_getter = plot_params.get('obs_label_getter_func',None)

    xlnk_color_getter = plot_params.get('xlnk_color_getter_func',None)
    dlnk_color_getter = plot_params.get('dlnk_color_getter_func',None)
    obs_color_getter = plot_params.get('obs_color_getter_func',None)

    start_getter_reg = plot_params.get('start_getter_reg',get_start)
    start_getter_choices = plot_params.get('start_getter_choices',get_start_original)
    end_getter_reg = plot_params.get('end_getter_reg',get_end)
    end_getter_choices = plot_params.get('end_getter_choices',get_end_original)

    xlnk_route_index_to_use = plot_params.get('xlnk_route_index_to_use',0)
    xlnk_color_rollover = plot_params.get('xlnk_color_rollover',1)
    xlnk_colors = plot_params.get('xlnk_colors',['#FF0000'])

    fontsize_obs = 10
    fontsize_dlnk = 7

    if time_units == 'hours':
        time_divisor = 3600
    if time_units == 'minutes':
        time_divisor = 60
    
    # time_to_end = (plot_end_dt-plot_start_dt).total_seconds()/time_divisor
    start_time = (plot_start_dt-base_time_dt).total_seconds()/time_divisor
    end_time = (plot_end_dt-base_time_dt).total_seconds()/time_divisor

    num_agents = len(agents_ids_list)

    #  make a new figure
    plt.figure()

    #  create subplots for satellites
    fig = plt.gcf()
    fig.set_size_inches( plot_size_inches)
    # print fig.get_size_inches()

    # have to sort before applying axis labels, otherwise x label shows up in a weird place
    # agents.sort(key=lambda x: x.agent_ID)

    # keep a running list of all the window IDs seen,  which we'll use for a sanity check
    all_wind_ids = []

    #  these hold the very last plot object of a given type added. Used for legend below
    d_w_obj = None
    d_obj = None
    x_w_obj = None
    x_obj = None
    o_w_obj = None
    o_obj = None

    first_agent = True

    # for each agent
    obs_count = 0
    for  plot_indx, agent_id in enumerate (agents_ids_list):
        #  get the index for this ID
        agent_indx = agent_id_order.index(str(agent_id))

        SMALL_SIZE = 8
        MEDIUM_SIZE = 10
        BIGGER_SIZE = 15

        plt.rc('font', size=BIGGER_SIZE)          # controls default text sizes
        plt.rc('axes', titlesize=BIGGER_SIZE)     # fontsize of the axes title
        plt.rc('axes', labelsize=BIGGER_SIZE)    # fontsize of the x and y labels
        plt.rc('xtick', labelsize=BIGGER_SIZE)    # fontsize of the tick labels
        plt.rc('ytick', labelsize=BIGGER_SIZE)    # fontsize of the tick labels
        plt.rc('legend', fontsize=SMALL_SIZE)    # legend fontsize
        plt.rc('figure', titlesize=BIGGER_SIZE)  # fontsize of the figure title

        axes = plt.subplot( num_agents,1,plot_indx+1)
        if plot_indx == floor(num_agents/2):
            plt.ylabel('%s\n\n%d'%(y_label,agent_indx))
        else:
            plt.ylabel('' + str(agent_indx))

        # no y-axis labels
        plt.tick_params(
            axis='y',
            which='both',
            left='off',
            right='off',
            labelleft='off'
        )

        # set axis length.
        plt.axis((start_time, end_time, 0, 2))

        current_axis = plt.gca()

        #  this is used to alternate the vertical position of the window rectangles, labels
        obs_rectangle_rotator_hist = {}
        dlnk_rectangle_rotator_hist = {}
        xlnk_rectangle_rotator_hist = {}
        obs_label_rotator_hist = {}
        dlnk_label_rotator_hist = {}
        xlnk_label_rotator_hist = {}

        obs_rotation_rollover = 2
        obs_label_rotation_rollover = 2
        xlnk_rotation_rollover = 2
        xlnk_label_rotation_rollover = 3
        dlnk_rotation_rollover = 2
        dlnk_label_rotation_rollover = 3

        ##########################
        # plot window choices
        ##########################

        # plot the crosslink "choices" -  meant to represent the windows that could have been chosen
        #  plot cross-links first, so that they are the furthest back (lowest z value) on the plot, and observations and downlinks will appear on top ( because there are generally a lot more cross-links than observations and down links)
        if plot_xlnks_choices and agents_xlnk_winds_choices is not None:
            agent_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                "plot_color": "#FFBCBC",
                "plot_hatch": False,
                "include_labels": False,
                "fontsize": 7,
                "base_time_dt": base_time_dt,
                "time_divisor": time_divisor,
                "viz_object_vert_bottom_base_offset": 0,
                "viz_object_rotator_hist": xlnk_rectangle_rotator_hist,
                "viz_object_rotation_rollover": 2,
                "label_horz_offset": -0.3,
                "label_vert_bottom_base_offset": 0.5,
                "label_vert_spacing": 0.2,
                "label_rotator_hist": xlnk_label_rotator_hist,
                "label_rotation_rollover": xlnk_label_rotation_rollover,
            }
            xlnk_viz_objects = plot_window_schedule(current_axis,agents_xlnk_winds_choices[agent_indx],start_getter_choices,end_getter_choices,agent_plot_params,label_getter=None,color_getter=None)
            if len(xlnk_viz_objects) > 0:
                x_w_obj = xlnk_viz_objects[-1]

        # plot the downlink "choices" -  meant to represent the windows that could have been chosen
        if plot_dlnks_choices and agents_dlnk_winds_choices is not None:
            agent_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                "plot_color": "#BFBFFF",
                "plot_hatch": False,
                "include_labels": False,
                "fontsize": 7,
                "base_time_dt": base_time_dt,
                "time_divisor": time_divisor,
                "viz_object_vert_bottom_base_offset": 0,
                "viz_object_rotator_hist": dlnk_rectangle_rotator_hist,
                "viz_object_rotation_rollover": 2,
                "label_horz_offset": -0.3,
                "label_vert_bottom_base_offset": 0.5,
                "label_vert_spacing": 0.2,
                "label_rotator_hist": dlnk_label_rotator_hist,
                "label_rotation_rollover": dlnk_label_rotation_rollover,
            }

            dlnk_viz_objects = plot_window_schedule(current_axis,agents_dlnk_winds_choices[agent_indx],start_getter_choices,end_getter_choices,agent_plot_params,label_getter=None,color_getter=None)
            if len(dlnk_viz_objects) > 0:
                d_w_obj = dlnk_viz_objects[-1]

        # plot the observation "choices" -  meant to represent the windows that could have been chosen
        if plot_obs_choices and agents_obs_winds_choices is not None:
            agent_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                "plot_color": "#BFFFBF",
                "plot_hatch": False,
                "include_labels": False,
                "fontsize": 7,
                "base_time_dt": base_time_dt,
                "time_divisor": time_divisor,
                "viz_object_vert_bottom_base_offset": 0,
                "viz_object_rotator_hist": obs_rectangle_rotator_hist,
                "viz_object_rotation_rollover": 2,
                "label_horz_offset": -0.3,
                "label_vert_bottom_base_offset": 0.1,
                "label_vert_spacing": 0.2,
                "label_rotator_hist": obs_label_rotator_hist,
                "label_rotation_rollover": obs_label_rotation_rollover,
            }

            obs_viz_objects = plot_window_schedule(current_axis,agents_obs_winds_choices[agent_indx],start_getter_choices,end_getter_choices,agent_plot_params,label_getter=None,color_getter=None)
            if len(obs_viz_objects) > 0:
                o_w_obj = obs_viz_objects[-1]



        ##########################
        # plot windows executed
        ##########################

        #  plot the executed cross-links
        #  plot cross-links first, so that they are the furthest back (lowest z value) on the plot, and observations and downlinks will appear on top ( because there are generally a lot more cross-links than observations and down links)
        if plot_xlnks and agents_xlnk_winds is not None:
            def label_getter(xlnk,sat_indx=agent_indx):
                dr_id = None
                if route_ids_by_wind:
                    dr_indcs = route_ids_by_wind.get(xlnk,None)
                    if not dr_indcs is None:
                        dr_id = dr_indcs[xlnk_route_index_to_use]

                other_agent_indx = xlnk.get_xlnk_partner(agent_indx)
                if not dr_id is None:
                    label_text = "%d,%d" %(dr_id.get_indx(),other_agent_indx)
                    label_text = "%s" %(dr_indcs)
                else:         
                    label_text = "%d" %(other_agent_indx)

                return label_text

            def color_getter(xlnk):
                xlnk_color_indx = 0
                if route_ids_by_wind:
                    dr_indcs = route_ids_by_wind.get(xlnk,None)
                    if not dr_indcs is None:
                        dr_id = dr_indcs[xlnk_route_index_to_use]
                        xlnk_color_indx = dr_id.get_indx() %  xlnk_color_rollover
                return xlnk_colors[xlnk_color_indx]

            agent_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                "plot_color": None,
                "plot_hatch": True,
                "include_labels": plot_include_xlnk_labels,
                "fontsize": 7,
                "base_time_dt": base_time_dt,
                "time_divisor": time_divisor,
                "viz_object_vert_bottom_base_offset": 0,
                "viz_object_rotator_hist": xlnk_rectangle_rotator_hist,
                "viz_object_rotation_rollover": 2,
                "label_horz_offset": -0.3,
                "label_vert_bottom_base_offset": 0.605,
                "label_vert_spacing": 0.1,
                "label_rotator_hist": xlnk_label_rotator_hist,
                "label_rotation_rollover": xlnk_label_rotation_rollover,
            }

            label_getter = xlnk_label_getter if xlnk_label_getter else label_getter
            color_getter = xlnk_color_getter if xlnk_color_getter else color_getter
            # supply the function with the agent index (freezes the current agent indx as an argument)
            label_getter_agent = partial(label_getter, sat_indx=agent_indx)

            xlnk_viz_objects = plot_window_schedule(current_axis,agents_xlnk_winds[agent_indx],start_getter_reg,end_getter_reg,agent_plot_params,label_getter_agent,color_getter)
            if len(xlnk_viz_objects) > 0:
                x_obj = xlnk_viz_objects[-1]

        # plot the executed down links
        if plot_dlnks and agents_dlnk_winds is not None:
            def label_getter(dlnk):
                # todo: scheduled data vol here is deprecated
                return "g%d,dv %d/%d"%(dlnk.gs_indx,dlnk.scheduled_data_vol,dlnk.data_vol) 

            def color_getter(dlnk):
                return "#0000FF"

            agent_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                # "plot_color": "#0000FF",
                "plot_hatch": True,
                "include_labels": plot_include_dlnk_labels,
                "fontsize": 7,
                "base_time_dt": base_time_dt,
                "time_divisor": time_divisor,
                "viz_object_vert_bottom_base_offset": 0,
                "viz_object_rotator_hist": dlnk_rectangle_rotator_hist,
                "viz_object_rotation_rollover": 2,
                "label_horz_offset": -0.3,
                "label_vert_bottom_base_offset": 0.305,
                "label_vert_spacing": 0.1,
                "label_rotator_hist": dlnk_label_rotator_hist,
                "label_rotation_rollover": dlnk_label_rotation_rollover,
            }

            label_getter = dlnk_label_getter if dlnk_label_getter else label_getter
            color_getter = dlnk_color_getter if dlnk_color_getter else color_getter

            dlnk_viz_objects = plot_window_schedule(current_axis,agents_dlnk_winds[agent_indx],start_getter_reg,end_getter_reg,agent_plot_params,label_getter,color_getter=color_getter)
            if len(dlnk_viz_objects) > 0:
                d_obj = dlnk_viz_objects[-1]

        # plot the observations that are actually executed
        if plot_obs and agents_obs_winds is not None:
            def label_getter(obs):
                # todo: scheduled data vol here is deprecated
                return "obs %d, dv %d/%d"%(obs_count,obs.scheduled_data_vol,obs.data_vol)

            def color_getter(obs):
                return "#00FF00"

            agent_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                # "plot_color": "#00FF00",
                "plot_hatch": True,
                "include_labels": plot_include_obs_labels,
                "fontsize": 7,
                "base_time_dt": base_time_dt,
                "time_divisor": time_divisor,
                "viz_object_vert_bottom_base_offset": 0,
                "viz_object_rotator_hist": obs_rectangle_rotator_hist,
                "viz_object_rotation_rollover": 2,
                "label_horz_offset": -0.3,
                "label_vert_bottom_base_offset": 0.05,
                "label_vert_spacing": 0.1,
                "label_rotator_hist": obs_label_rotator_hist,
                "label_rotation_rollover": obs_label_rotation_rollover,
            }

            label_getter = obs_label_getter if obs_label_getter else label_getter
            color_getter = obs_color_getter if obs_color_getter else color_getter

            obs_viz_objects = plot_window_schedule(current_axis,agents_obs_winds[agent_indx],start_getter_reg,end_getter_reg,agent_plot_params,label_getter,color_getter=color_getter)
            if len(obs_viz_objects) > 0:
                o_obj = obs_viz_objects[-1]

            obs_count += 1

        #  if were at the last agentellite ( at the bottom of all the plots), then add X axis labels
        if not plot_indx+1 == num_agents:
            ax = plt.gca()
            plt.setp(ax.get_xticklabels(), visible=False)

        if first_agent:
            plt.title(plot_title)

        first_agent = False


    legend_objects = []
    legend_objects_labels = []
    if d_w_obj: 
        legend_objects.append(d_w_obj)
        legend_objects_labels.append('D all')
    if d_obj: 
        legend_objects.append(d_obj)
        legend_objects_labels.append('Dlnk')
    if x_w_obj: 
        legend_objects.append(x_w_obj)
        legend_objects_labels.append('X all')
    if x_obj: 
        legend_objects.append(x_obj)
        legend_objects_labels.append('Xlnk')
    if o_w_obj: 
        legend_objects.append(o_w_obj)
        legend_objects_labels.append('O all')
    if o_obj: 
        legend_objects.append(o_obj)
        legend_objects_labels.append('Obs')

    plt.legend(legend_objects, legend_objects_labels ,bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)

    plt.xlabel('Time (%s)'%(time_units))

    # use the last axes to set the entire plot background color
    axes.patch.set_facecolor('w')

    if show:
        plt.show()
    else:
        savefig(fig_name,format=plot_fig_extension)


def plot_energy_usage(
        sats_ids_list,
        energy_usage,
        ecl_winds,
        plot_params):

    plot_labels = {
        "e usage": "e usage",
        "e max": "e max",
        "e min": "e min",
        "ecl": "ecl"
    }

    plot_start_dt = plot_params['plot_start_dt']
    plot_end_dt = plot_params['plot_end_dt']
    base_time_dt = plot_params['base_time_dt']
    sat_id_order = plot_params['sat_id_order']
    sats_emin_Wh = plot_params['sats_emin_Wh']
    sats_emax_Wh = plot_params['sats_emax_Wh']
    energy_usage_plot_params = plot_params['energy_usage_plot_params']

    plot_title = plot_params.get('plot_title','Activities Plot')
    plot_size_inches = plot_params.get('plot_size_inches',(12,12))
    show = plot_params.get('show',False)
    fig_name = plot_params.get('fig_name','plots/energy_plot.pdf')
    time_units = plot_params.get('time_units','minutes')
    plot_fig_extension = plot_params.get('plot_fig_extension','pdf')


    if time_units == 'hours':
        time_divisor = 3600
    if time_units == 'minutes':
        time_divisor = 60
    
    # time_to_end = (plot_end-plot_start_dt).total_seconds()/time_divisor
    start_time = (plot_start_dt-base_time_dt).total_seconds()/time_divisor
    end_time = (plot_end_dt-base_time_dt).total_seconds()/time_divisor

    num_sats = len(sats_ids_list)

    #  make a new figure
    plt.figure()

    #  create subplots for satellites
    fig = plt.gcf()
    fig.set_size_inches( plot_size_inches)
    # print fig.get_size_inches()

    #  these hold the very last plot object of a given type added. Used for legend below
    e_usage_plot = None
    e_max_plot = None
    e_min_plot = None
    ecl_plot = None

    # for each agent
    first_sat = True
    for  plot_indx, sat_id in enumerate (sats_ids_list):
        #  get the index for this ID
        sat_indx = sat_id_order.index(str(sat_id))

        #  make a subplot for each
        axes = plt.subplot( num_sats,1,plot_indx+1)
        if plot_indx == floor(num_sats/2):
            plt.ylabel('Satellite Index\n\n' + str(sat_indx))
        else:
            plt.ylabel('' + str(sat_indx))


        # no y-axis labels
        plt.tick_params(
            axis='y',
            which='both',
            left='off',
            right='off',
            labelleft='off'
        )

        # set axis length.
        vert_min = energy_usage_plot_params['plot_bound_e_min_Wh_delta']+sats_emin_Wh[sat_indx]
        vert_max = energy_usage_plot_params['plot_bound_e_max_Wh_delta']+sats_emax_Wh[sat_indx]
        plt.axis((start_time, end_time, vert_min, vert_max))

        current_axis = plt.gca()

        # the first return value is a handle for our line, everything else can be ignored
        if energy_usage:
            e_time = [e_t + start_time for e_t in energy_usage['time_mins'][sat_indx]]
            e_usage_plot,*dummy = plt.plot(e_time,energy_usage['e_sats'][sat_indx], label =  plot_labels["e usage"])

        if energy_usage_plot_params['include_eclipse_windows']:
            for ecl_wind in ecl_winds[sat_indx]:
                ecl_wind_start = (ecl_wind.start- base_time_dt).total_seconds()/time_divisor
                ecl_wind_end = (ecl_wind.end-base_time_dt).total_seconds()/time_divisor

                height = vert_max-vert_min
                ecl_plot = Rectangle((ecl_wind_start, vert_min), ecl_wind_end-ecl_wind_start, vert_min+height,alpha=0.3,fill=True,color='#202020',label= plot_labels["ecl"])

                current_axis.add_patch(ecl_plot)

        if energy_usage_plot_params['show_min_max_bounds']:
            e_min = sats_emin_Wh[sat_indx]
            e_max = sats_emax_Wh[sat_indx]
            e_max_plot,*dummy = plt.plot([start_time,end_time],[e_max,e_max], linestyle=':',label =  plot_labels["e max"])
            e_min_plot,*dummy = plt.plot([start_time,end_time],[e_min,e_min], linestyle=':',label =  plot_labels["e min"])


        #  if were at the last satellite ( at the bottom of all the plots), then add X axis labels
        if not plot_indx+1 == num_sats:
            ax = plt.gca()
            plt.setp(ax.get_xticklabels(), visible=False)

        if first_sat:
            plt.title(plot_title)

        first_sat = False


    legend_objects = []
    if e_usage_plot: 
        legend_objects.append(e_usage_plot)
    if e_max_plot: 
        legend_objects.append(e_max_plot)
    if e_min_plot: 
        legend_objects.append(e_min_plot)
    if ecl_plot: 
        legend_objects.append(ecl_plot)

    plt.legend(handles=legend_objects ,bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)

    plt.xlabel('Time (%s)'%(time_units))

    # use the last axes to set the entire plot background color
    axes.patch.set_facecolor('w')

    if show:
        plt.show()
    else:
        savefig(fig_name,format=plot_fig_extension)


def plot_data_usage(
        sats_ids_list,
        data_usage,
        ecl_winds,
        plot_params):

    plot_labels = {
        "d usage": "d usage",
        "d max": "d max",
        "d min": "d min",
        "ecl": "ecl"
    }

    plot_start_dt = plot_params['plot_start_dt']
    plot_end_dt = plot_params['plot_end_dt']
    base_time_dt = plot_params['base_time_dt']
    sat_id_order = plot_params['sat_id_order']
    sats_dmin_Gb = plot_params['sats_dmin_Gb']
    sats_dmax_Gb = plot_params['sats_dmax_Gb']
    data_usage_plot_params = plot_params['data_usage_plot_params']

    plot_title = plot_params.get('plot_title','Activities Plot')
    plot_size_inches = plot_params.get('plot_size_inches',(12,12))
    show = plot_params.get('show',False)
    fig_name = plot_params.get('fig_name','plots/data_plot.pdf')
    time_units = plot_params.get('time_units','minutes')
    plot_fig_extension = plot_params.get('plot_fig_extension','pdf')


    if time_units == 'hours':
        time_divisor = 3600
    if time_units == 'minutes':
        time_divisor = 60
    
    # time_to_end = (plot_end-plot_start_dt).total_seconds()/time_divisor
    start_time = (plot_start_dt-base_time_dt).total_seconds()/time_divisor
    end_time = (plot_end_dt-base_time_dt).total_seconds()/time_divisor

    num_sats = len(sats_ids_list)

    #  make a new figure
    plt.figure()

    #  create subplots for satellites
    fig = plt.gcf()
    fig.set_size_inches( plot_size_inches)
    # print fig.get_size_inches()

    #  these hold the very last plot object of a given type added. Used for legend below
    d_usage_plot = None
    d_max_plot = None
    d_min_plot = None
    ecl_plot = None

    # for each agent
    first_sat = True
    for  plot_indx, sat_id in enumerate (sats_ids_list):
        #  get the index for this ID
        sat_indx = sat_id_order.index(str(sat_id))

        #  make a subplot for each
        axes = plt.subplot( num_sats,1,plot_indx+1)
        if plot_indx == floor(num_sats/2):
            plt.ylabel('Satellite Index\n\n' + str(sat_indx))
        else:
            plt.ylabel('' + str(sat_indx))


        # no y-axis labels
        plt.tick_params(
            axis='y',
            which='both',
            left='off',
            right='off',
            labelleft='off'
        )

        # set axis length.
        vert_min = data_usage_plot_params['plot_bound_d_min_Gb_delta']+sats_dmin_Gb[sat_indx]
        vert_max = data_usage_plot_params['plot_bound_d_max_Gb_delta']+sats_dmax_Gb[sat_indx]
        plt.axis((start_time, end_time, vert_min, vert_max))

        current_axis = plt.gca()

        # the first return value is a handle for our line, everything else can be ignored
        if data_usage:
            d_time = [d_t + start_time for d_t in data_usage['time_mins'][sat_indx]]
            # adjust from Mb to Gb
            sat_data_usage_Gb = [num/1000 for num in data_usage['d_sats'][sat_indx]]
            d_usage_plot,*dummy = plt.plot(d_time,sat_data_usage_Gb, label =  plot_labels["d usage"])

        if data_usage_plot_params['include_eclipse_windows']:
            for ecl_wind in ecl_winds[sat_indx]:
                ecl_wind_start = (ecl_wind.start- base_time_dt).total_seconds()/time_divisor
                ecl_wind_end = (ecl_wind.end-base_time_dt).total_seconds()/time_divisor

                height = vert_max-vert_min
                ecl_plot = Rectangle((ecl_wind_start, vert_min), ecl_wind_end-ecl_wind_start, vert_min+height,alpha=0.3,fill=True,color='#202020',label= plot_labels["ecl"])

                current_axis.add_patch(ecl_plot)

        if data_usage_plot_params['show_min_max_bounds']:
            d_min = sats_dmin_Gb[sat_indx]
            d_max = sats_dmax_Gb[sat_indx]
            d_max_plot,*dummy = plt.plot([start_time,end_time],[d_max,d_max], linestyle=':',label =  plot_labels["d max"])
            d_min_plot,*dummy = plt.plot([start_time,end_time],[d_min,d_min], linestyle=':',label =  plot_labels["d min"])


        #  if were at the last satellite ( at the bottom of all the plots), then add X axis labels
        if not plot_indx+1 == num_sats:
            ax = plt.gca()
            plt.setp(ax.get_xticklabels(), visible=False)

        if first_sat:
            plt.title(plot_title)

        first_sat = False


    legend_objects = []
    if d_usage_plot: 
        legend_objects.append(d_usage_plot)
    if d_max_plot: 
        legend_objects.append(d_max_plot)
    if d_min_plot: 
        legend_objects.append(d_min_plot)
    if ecl_plot: 
        legend_objects.append(ecl_plot)

    plt.legend(handles=legend_objects ,bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)

    plt.xlabel('Time (%s)'%(time_units))

    # use the last axes to set the entire plot background color
    axes.patch.set_facecolor('w')

    if show:
        plt.show()
    else:
        savefig(fig_name,format=plot_fig_extension)