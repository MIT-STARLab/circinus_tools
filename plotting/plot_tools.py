from math import floor

import matplotlib.pyplot as plt
from matplotlib.pyplot import savefig
from matplotlib.patches import Rectangle, Circle

def plot_window_schedule(current_axis,winds,get_start_func,get_end_func,sat_plot_params,label_getter,color_getter=None):

    viz_object_rotator_hist = sat_plot_params['viz_object_rotator_hist']
    label_rotator_hist = sat_plot_params['label_rotator_hist']

    base_time_dt = sat_plot_params['base_time_dt']
    t_choice = sat_plot_params['plot_original_times']

    viz_objects = []

    viz_object_rotator = 0
    label_rotator = 0

    # plot the activity Windows
    if winds and len(winds) > 0:
        for wind in winds:

            act_start = (get_start_func(wind,t_choice)-base_time_dt).total_seconds()/sat_plot_params['time_divisor']
            act_end = (get_end_func(wind,t_choice)-base_time_dt).total_seconds()/sat_plot_params['time_divisor']

            #  check if the activity is out of the time bounds for the plot or overlapping them
            out_of_bounds = get_end_func(wind,t_choice) < sat_plot_params['plot_start_dt'] or get_start_func(wind,t_choice) > sat_plot_params['plot_end_dt']
            overlapping_bounds = get_start_func(wind,t_choice) < sat_plot_params['plot_start_dt'] or get_end_func(wind,t_choice) > sat_plot_params['plot_end_dt']

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

            color = sat_plot_params['plot_color']
            if color_getter:
                color = color_getter(wind)

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


def plot_all_sats_acts(
    sats_ids_list,
    sats_obs_winds_choices,
    sats_obs_winds,
    sats_dlnk_winds_choices,
    sats_dlnk_winds, 
    sats_xlnk_winds_choices,
    sats_xlnk_winds,
    plot_params):
    '''
    Displays a 2D plot of assignments for each agent with respect to time

    '''

    # input params dict handling
    route_ids_by_wind = plot_params.get('route_ids_by_wind',None)
    plot_start_dt = plot_params['plot_start_dt']
    plot_end_dt = plot_params['plot_end_dt']
    base_time_dt = plot_params['base_time_dt']
    sat_id_order = plot_params['sat_id_order']

    plot_title = plot_params.get('plot_title','Activities Plot')
    plot_size_inches = plot_params.get('plot_size_inches',(12,12))
    plot_include_labels = plot_params.get('plot_include_labels',False)
    plot_original_times_choices = plot_params.get('plot_original_times_choices',True)
    plot_original_times_regular = plot_params.get('plot_original_times_regular',False)
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

    num_sats = len(sats_ids_list)

    #  make a new figure
    plt.figure()

    #  create subplots for satellites
    fig = plt.gcf()
    fig.set_size_inches( plot_size_inches)
    # print fig.get_size_inches()

    # have to sort before applying axis labels, otherwise x label shows up in a weird place
    # sats.sort(key=lambda x: x.agent_ID)

    # keep a running list of all the window IDs seen,  which we'll use for a sanity check
    all_wind_ids = []

    def get_start(wind,plot_original_times):
        if plot_original_times:
            return wind.original_start
        else:
            return wind.start

    def get_end(wind,plot_original_times):
        if plot_original_times:
            return wind.original_end
        else:
            return wind.end

    #  these hold the very last plot object of a given type added. Used for legend below
    d_w_obj = None
    d_obj = None
    x_w_obj = None
    x_obj = None
    o_w_obj = None
    o_obj = None

    first_sat = True

    # for each agent
    obs_count = 0
    for  plot_indx, sat_id in enumerate (sats_ids_list):
        #  get the index for this ID
        sat_indx = sat_id_order.index(str(sat_id))

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
        obs_label_rotation_rollover = 3
        xlnk_rotation_rollover = 2
        xlnk_label_rotation_rollover = 3
        dlnk_rotation_rollover = 2
        dlnk_label_rotation_rollover = 3

        ##########################
        # plot window choices
        ##########################

        # plot the crosslink "choices" -  meant to represent the windows that could have been chosen
        #  plot cross-links first, so that they are the furthest back (lowest z value) on the plot, and observations and downlinks will appear on top ( because there are generally a lot more cross-links than observations and down links)
        if plot_xlnks_choices and sats_xlnk_winds_choices is not None:
            sat_plot_params = {
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
                "plot_original_times": plot_original_times_choices,
            }

            xlnk_viz_objects = plot_window_schedule(current_axis,sats_xlnk_winds_choices[sat_indx],get_start,get_end,sat_plot_params,label_getter=None,color_getter=None)
            if len(xlnk_viz_objects) > 0:
                x_w_obj = xlnk_viz_objects[-1]

        # plot the downlink "choices" -  meant to represent the windows that could have been chosen
        if plot_dlnks_choices and sats_dlnk_winds_choices is not None:
            sat_plot_params = {
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
                "plot_original_times": plot_original_times_choices,
            }

            dlnk_viz_objects = plot_window_schedule(current_axis,sats_dlnk_winds_choices[sat_indx],get_start,get_end,sat_plot_params,label_getter=None,color_getter=None)
            if len(dlnk_viz_objects) > 0:
                d_w_obj = dlnk_viz_objects[-1]

        # plot the observation "choices" -  meant to represent the windows that could have been chosen
        if plot_obs_choices and sats_obs_winds_choices is not None:
            sat_plot_params = {
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
                "label_vert_bottom_base_offset": 0.5,
                "label_vert_spacing": 0.2,
                "label_rotator_hist": obs_label_rotator_hist,
                "label_rotation_rollover": obs_label_rotation_rollover,
                "plot_original_times": plot_original_times_choices,
            }

            obs_viz_objects = plot_window_schedule(current_axis,sats_obs_winds_choices[sat_indx],get_start,get_end,sat_plot_params,label_getter=None,color_getter=None)
            if len(obs_viz_objects) > 0:
                o_w_obj = obs_viz_objects[-1]


        ##########################
        # plot windows executed
        ##########################

        #  plot the executed cross-links
        #  plot cross-links first, so that they are the furthest back (lowest z value) on the plot, and observations and downlinks will appear on top ( because there are generally a lot more cross-links than observations and down links)
        if plot_xlnks and sats_xlnk_winds is not None:
            def label_getter(xlnk):
                dr_id = None
                if route_ids_by_wind:
                    dr_indcs = route_ids_by_wind.get(xlnk,None)
                    if not dr_indcs is None:
                        dr_id = dr_indcs[xlnk_route_index_to_use]

                other_sat_indx = xlnk.get_xlnk_partner(sat_indx)
                if not dr_id is None:
                    label_text = "%d,%d" %(dr_id.get_indx(),other_sat_indx)
                    label_text = "%s" %(dr_indcs)
                else:         
                    label_text = "%d" %(other_sat_indx)

                return label_text

            def color_getter(xlnk):
                xlnk_color_indx = 0
                if route_ids_by_wind:
                    dr_indcs = route_ids_by_wind.get(xlnk,None)
                    if not dr_indcs is None:
                        dr_id = dr_indcs[xlnk_route_index_to_use]
                        xlnk_color_indx = dr_id.get_indx() %  xlnk_color_rollover
                return xlnk_colors[xlnk_color_indx]

            sat_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                "plot_color": None,
                "plot_hatch": True,
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
                "label_rotation_rollover": xlnk_label_rotation_rollover,
                "plot_original_times": plot_original_times_regular,
            }

            xlnk_viz_objects = plot_window_schedule(current_axis,sats_xlnk_winds[sat_indx],get_start,get_end,sat_plot_params,label_getter,color_getter)
            if len(xlnk_viz_objects) > 0:
                x_obj = xlnk_viz_objects[-1]

        # plot the executed down links
        if plot_dlnks and sats_dlnk_winds is not None:
            def label_getter(dlnk):
                return "g%d,dv %d/%d"%(dlnk.gs_indx,dlnk.scheduled_data_vol,dlnk.data_vol) 

            sat_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                "plot_color": "#0000FF",
                "plot_hatch": True,
                "include_labels": plot_include_labels,
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
                "plot_original_times": plot_original_times_regular,
            }

            dlnk_viz_objects = plot_window_schedule(current_axis,sats_dlnk_winds[sat_indx],get_start,get_end,sat_plot_params,label_getter,color_getter=None)
            if len(dlnk_viz_objects) > 0:
                d_obj = dlnk_viz_objects[-1]

        # plot the observations that are actually executed
        if plot_obs and sats_obs_winds is not None:
            def label_getter(obs):
                return "obs %d, dv %d/%d"%(obs_count,obs.scheduled_data_vol,obs.data_vol)

            sat_plot_params = {
                "plot_start_dt": plot_start_dt,
                "plot_end_dt": plot_end_dt,
                "plot_color": "#00FF00",
                "plot_hatch": True,
                "include_labels": plot_include_labels,
                "fontsize": 7,
                "base_time_dt": base_time_dt,
                "time_divisor": time_divisor,
                "viz_object_vert_bottom_base_offset": 0,
                "viz_object_rotator_hist": obs_rectangle_rotator_hist,
                "viz_object_rotation_rollover": 2,
                "label_horz_offset": -0.3,
                "label_vert_bottom_base_offset": 0.5,
                "label_vert_spacing": 0.2,
                "label_rotator_hist": obs_label_rotator_hist,
                "label_rotation_rollover": obs_label_rotation_rollover,
                "plot_original_times": plot_original_times_regular,
            }

            obs_viz_objects = plot_window_schedule(current_axis,sats_obs_winds[sat_indx],get_start,get_end,sat_plot_params,label_getter,color_getter=None)
            if len(obs_viz_objects) > 0:
                o_obj = obs_viz_objects[-1]

            obs_count += 1

        #  if were at the last satellite ( at the bottom of all the plots), then add X axis labels
        if not plot_indx+1 == num_sats:
            ax = plt.gca()
            plt.setp(ax.get_xticklabels(), visible=False)

        if first_sat:
            plt.title(plot_title)

        first_sat = False


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