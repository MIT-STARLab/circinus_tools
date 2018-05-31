
from circinus_tools  import io_tools
from circinus_tools.scheduling.custom_window import   DlnkWindow
from .schedulers import PyomoMILPScheduling

class AgentScheduling(PyomoMILPScheduling):
    """ provides scheduling algorithm utilities used across global and local planners, using pyomo"""
    
    def __init__(self):
        """initializes based on parameters
        
        initializes based on parameters
        :param lp_params: global namespace parameters created from input files (possibly with some small non-structural modifications to params). The name spaces here should trace up all the way to the input files.
        :type params: dict
        """

        super().__init__()


        # to be instantiated in subclass
        self.min_act_duration_s = None
        self.sat_activity_params = None



        #####################
        #  activity constraint violation stuff

        # allow activities to overlap, and penalize them for doing so. The code should work, but hasn't been extensively vetted for its usefulness (does seem surprisingly unresponsive to changing weights for constraint violation in the obj function...). Note having these violations allowed generally won't play well with extracting routes in coupled AS due to data route validation checks. 
        self.allow_act_timing_constr_violations = False

        #  stores all of the lower bounds of the constraint violation variables, for use in normalization for objective function
        self.min_var_intra_sat_act_constr_violation_list = [] 
        self.min_var_inter_sat_act_constr_violation_list = [] 

        self.constraint_violation_model_objs = {}
        self.constraint_violation_model_objs['intra_sat_act_constr_violation_acts_list'] = []
        self.constraint_violation_model_objs['inter_sat_act_constr_violation_acts_list'] = []
        #  the below objects need to be created in the subclass
        self.constraint_violation_model_objs['var_intra_sat_act_constr_violations'] = None
        self.constraint_violation_model_objs['var_inter_sat_act_constr_violations'] = None
        self.constraint_violation_model_objs['intra_sat_act_constr_bounds'] = None
        self.constraint_violation_model_objs['inter_sat_act_constr_bounds'] = None
        self.constraint_violation_model_objs['min_var_intra_sat_act_constr_violation_list'] = self.min_var_intra_sat_act_constr_violation_list 
        self.constraint_violation_model_objs['min_var_inter_sat_act_constr_violation_list'] = self.min_var_inter_sat_act_constr_violation_list 

    @staticmethod
    def get_act_model_objs(act,model):
        """ get the pyomo model objects used for modeling activity utilization. meant to be implemented in subclass"""

        raise NotImplementedError

        # note: the below code provides an example implementation
        # model_objs_act = {
        #     'act_object': act,
        #     'var_dv_utilization': model.var_activity_utilization[act.window_ID]*model.par_act_capacity[act.window_ID],
        #     'par_dv_capacity': model.par_act_capacity[act.window_ID],
        #     'var_act_indic': model.var_act_indic[act.window_ID],
        # }

        # return model_objs_act

    def gen_inter_act_constraint(self,var_list,constr_list,transition_time_req,model_objs_act1,model_objs_act2):
        """ generate the constraints between two individual activity windows"""

        #  the regular constraint is the constraint that is enforced in the mixed integer linear program
        #  the "binding expression"  is the expression that, when evaluated after MILP solution, will be zero if the constraint is binding and greater than zero if the constraint is not binding ( i.e., if the constraint is not binding, there is room for one of the variables to grow). The constraint should have any big M factors removed in the binding expression, because those obfuscate information about whether the constraint is binding or not. The binding expression shall may be negative if big M components are normally present.

        var_constr_violation = None
        min_constr_violation = None

        act1 = model_objs_act1['act_object']
        act2 = model_objs_act2['act_object']

        center_time_diff = (act2.center - act1.center).total_seconds()
        # var is a variable, the amount of dv used for the link
        time_adjust_1 = model_objs_act1['var_dv_utilization']/2/act1.ave_data_rate
        time_adjust_2 = model_objs_act2['var_dv_utilization']/2/act2.ave_data_rate
        # par is a parameter
        max_time_adjust_1 = model_objs_act1['par_dv_capacity']*1/2/act1.ave_data_rate
        max_time_adjust_2 = model_objs_act2['par_dv_capacity']*1/2/act2.ave_data_rate

        if not self.allow_act_timing_constr_violations:
            #  if the activities overlap in center time (including  transition time), then it's not possible to have sufficient transition time between them.  only allow one
            if (act2.center - act1.center).total_seconds() <= transition_time_req:
                constr = model_objs_act1['var_act_indic']+ model_objs_act2['var_act_indic'] <= 1
                binding_expr = 1 - model_objs_act1['var_act_indic'] - model_objs_act2['var_act_indic']

            # If they don't overlap in center time, but they do overlap to some amount, then we need to constrain their end and start times to be consistent with one another
            else:
                M = max(act1.duration,act2.duration).total_seconds()
                constr_disable_1 = M*(1-model_objs_act1['var_act_indic'])
                constr_disable_2 = M*(1-model_objs_act2['var_act_indic'])
    
                constr = center_time_diff - time_adjust_1 - time_adjust_2 + constr_disable_1 + constr_disable_2 >= transition_time_req
                binding_expr = center_time_diff - time_adjust_1 - time_adjust_2 - transition_time_req 

        else:
            # time_adjust_N can go as low as zero, so the constraint violation can be this at its lowest
            min_constr_violation = center_time_diff - max_time_adjust_1 - max_time_adjust_2 - transition_time_req

            assert(min_constr_violation < 0)

            # deal with adding a variable to represent this constraint violation. ( I hate that I have to do it this way, deep within this function, but it seems like the approach you have to use for dynamically generating variable lists in pyomo, bizarrely. refer to: https://projects.coin-or.org/Coopr/browser/pyomo/trunk/pyomo/core/base/var.py?rev=11067, https://groups.google.com/forum/#!topic/pyomo-forum/modS1VkPxW0
            var_list.add()
            var_constr_violation = var_list[len(var_list)]

            #  bounds on range of constraint violation variable

            # bound minimum of the constraint violation (where both activities have 1.0 utilization), to keep the problem formulation as tight as possible
            var_constr_violation.setlb(min_constr_violation)
            # want the constraint violation only to go to zero at its maximum, because we don't want to reward times where there is no constraint violation, only penalize
            var_constr_violation.setub(0)

            #  the actual time constraint that bounds the constraint violation
            constr = center_time_diff - time_adjust_1 - time_adjust_2 - transition_time_req >= var_constr_violation
            binding_expr = center_time_diff - time_adjust_1 - time_adjust_2 - transition_time_req - var_constr_violation

        return constr, binding_expr,var_constr_violation, min_constr_violation

    def gen_sat_act_duration_constraints(self,model,c_duration,sats_acts,num_sats,act_model_objs_getter=get_act_model_objs):
        """ generate constraints on activity duration"""

        binding_expr_duration_by_act = {}
    
        for sat_indx in range (num_sats):
            num_sat_acts = len(sats_acts[sat_indx])
            for  first_act_indx in  range (num_sat_acts):
                act = sats_acts[sat_indx][first_act_indx]
                model_objs_act1 = act_model_objs_getter(act,model)

                length = model_objs_act1['var_dv_utilization']/act.ave_data_rate
                c_duration.add( length >= model_objs_act1['var_act_indic'] * self.min_act_duration_s[type(act)])
                binding_expr_duration_by_act[act] = length - model_objs_act1['var_act_indic'] * self.min_act_duration_s[type(act)]

        return binding_expr_duration_by_act


    def gen_intra_sat_act_overlap_constraints(self,model,c_overlap,sats_acts,num_sats,act_model_objs_getter=get_act_model_objs):

        intra_sat_act_constr_violation_acts_list = self.constraint_violation_model_objs['intra_sat_act_constr_violation_acts_list']
        var_intra_sat_act_constr_violations = self.constraint_violation_model_objs['var_intra_sat_act_constr_violations']
        intra_sat_act_constr_bounds = self.constraint_violation_model_objs['intra_sat_act_constr_bounds']
        min_var_intra_sat_act_constr_violation_list = self.constraint_violation_model_objs['min_var_intra_sat_act_constr_violation_list']

        binding_expr_overlap_by_act = {}

        for sat_indx in range (num_sats):
            num_sat_acts = len(sats_acts[sat_indx])
            for  first_act_indx in  range (num_sat_acts):
                act1 = sats_acts[sat_indx][first_act_indx]
                model_objs_act1 = act_model_objs_getter(act1,model)
                
                for  second_act_indx in  range (first_act_indx+1,num_sat_acts):
                    act2 = sats_acts[sat_indx][second_act_indx]

                    # act list should be sorted
                    assert(act2.center >= act1.center)

                    # get the transition time requirement between these activities
                    transition_time_req = io_tools.get_transition_time_req(act1,act2,sat_indx,sat_indx,self.sat_activity_params)

                    # if there is enough transition time between the two activities, no constraint needs to be added
                    #  note that we are okay even if for some reason Act 2 starts before Act 1 ends, because time deltas return negative total seconds as well
                    if (act2.original_start - act1.original_end).total_seconds() >= transition_time_req:
                        #  don't need to do anything,  continue on to next activity pair
                        continue

                    else:
                        model_objs_act2 = act_model_objs_getter(act2,model)

                        constr, binding_expr, var_constr_violation, min_constr_violation = self.gen_inter_act_constraint(
                            var_intra_sat_act_constr_violations,
                            intra_sat_act_constr_bounds,
                            transition_time_req,
                            model_objs_act1,
                            model_objs_act2
                        )

                        #  add the constraint, regardless of whether or not it's a "big M" constraint, or a constraint violation constraint - they're handled the same
                        c_overlap.add( constr )
                        binding_expr_overlap_by_act.setdefault(act1,[]).append(binding_expr)
                        binding_expr_overlap_by_act.setdefault(act2,[]).append(binding_expr)

                        #  if it's a constraint violation constraint, then we have a variable to deal with
                        if not min_constr_violation is None:
                            min_var_intra_sat_act_constr_violation_list.append(min_constr_violation)
                            intra_sat_act_constr_violation_acts_list.append((act1,act2))

        return binding_expr_overlap_by_act


    def gen_inter_sat_act_overlap_constraints(self,model,c_overlap,sats_dlnks,num_sats,act_model_objs_getter=get_act_model_objs):

        inter_sat_act_constr_violation_acts_list = self.constraint_violation_model_objs['inter_sat_act_constr_violation_acts_list']
        var_inter_sat_act_constr_violations = self.constraint_violation_model_objs['var_inter_sat_act_constr_violations']
        inter_sat_act_constr_bounds = self.constraint_violation_model_objs['inter_sat_act_constr_bounds']
        min_var_inter_sat_act_constr_violation_list = self.constraint_violation_model_objs['min_var_inter_sat_act_constr_violation_list']

        binding_expr_overlap_by_act = {}

        for sat_indx in range (num_sats):
            num_sat_acts = len(sats_dlnks[sat_indx])
            
            for other_sat_indx in range (num_sats):
                if other_sat_indx == sat_indx:
                    continue

                num_other_sat_acts = len(sats_dlnks[other_sat_indx])

                for  sat_act_indx in  range (num_sat_acts):

                    act1 = sats_dlnks[sat_indx][sat_act_indx]
                    
                    for  other_sat_act_indx in  range (num_other_sat_acts):
                        act2 = sats_dlnks[other_sat_indx][other_sat_act_indx]

                        assert(type(act1) == DlnkWindow and type(act2) == DlnkWindow)

                        # this line is pretty important - only consider overlap if they're looking at the same GS. I forgot to add this before and spent days wondering why the optimization process was progressing so slowly (hint: it's really freaking constrained and there's not much guidance for finding a good objective value if no downlink can overlap in time with any other downlink)
                        if act1.gs_indx != act2.gs_indx:
                            continue

                        # we're considering windows across satellites, so they could be out of order temporally. These constraints are only valid if act2 is after act1 (center time). Don't worry, as we loop through satellites, we consider both directions (i.e. act1 and act2 will be swapped in another iteration, and we'll get past this check and impose the required constraints)
                        if (act2.center - act1.center).total_seconds() < 0:
                            continue

                        # get the transition time requirement between these activities
                        transition_time_req = io_tools.get_transition_time_req(act1,act2,sat_indx,other_sat_indx,self.sat_activity_params)                   

                        # if there is enough transition time between the two activities, no constraint needs to be added
                        #  note that we are okay even if for some reason Act 2 starts before Act 1 ends, because time deltas return negative total seconds as well
                        if (act2.original_start - act1.original_end).total_seconds() >= transition_time_req:
                            #  don't need to do anything,  continue on to next activity pair
                            continue

                        else:
                            model_objs_act1 = act_model_objs_getter(act1,model)
                            model_objs_act2 = act_model_objs_getter(act2,model)
                        
                            constr, binding_expr, var_constr_violation, min_constr_violation = self.gen_inter_act_constraint(
                                var_inter_sat_act_constr_violations,
                                inter_sat_act_constr_bounds,
                                transition_time_req,
                                model_objs_act1,
                                model_objs_act2
                            )

                            #  add the constraint, regardless of whether or not it's a "big M" constraint, or a constraint violation constraint - they're handled the same
                            c_overlap.add( constr )
                            binding_expr_overlap_by_act.setdefault(act1,[]).append(binding_expr)
                            binding_expr_overlap_by_act.setdefault(act2,[]).append(binding_expr)

                            #  if it's a constraint violation constraint, then we have a variable to deal with
                            if not min_constr_violation is None:
                                # model.var_inter_sat_act_constr_violations.add(var_constr_violation)
                                min_var_inter_sat_act_constr_violation_list.append(min_constr_violation)
                                inter_sat_act_constr_violation_acts_list.append((act1,act2))

        return binding_expr_overlap_by_act




