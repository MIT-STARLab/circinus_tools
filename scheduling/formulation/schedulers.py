from pyomo import environ  as pe
from pyomo import opt  as po

class PyomoMILPScheduling:
    """ superclass for MILP schedulers implemented with pyomo, intended to unify mechanisms across CIRCINUS codebases"""

    # how close a binary variable must be to zero or one to be counted as that
    binary_epsilon = 0.1

    def __init__(self):

        # records if the formulation model has been constructed successfully
        self.model_constructed = False

    def make_model ( self):
        """ make the pyomo model to be solved"""

        #  intended to be implemented in the subclass
        raise NotImplementedError


    def solve(self):
        """ solve the pyomo model"""

        if not self.model_constructed:
            return

        solver = po.SolverFactory(self.solver_name)
        if self.solver_name == 'gurobi':
            # note default for this is 1e-4, or 0.01%
            solver.options['TimeLimit'] = self.solver_params['max_runtime_s']
            solver.options['MIPGap'] = self.solver_params['optimality_gap']
            solver.options['IntFeasTol'] = self.solver_params['integer_feasibility_tolerance']
            # solver.options['IterationLimit'] = 100  # limit on simplex iterations (ends Gurobi solving at this point - not great)
            # other options...
            # solver.options['Cuts'] = 0
            # solver.options['MIPFocus'] = 1 #for finding feasible solutions quickly
            # solver.options['MIPFocus'] = 3 #for lowering the mip gap

        elif self.solver_name == 'cplex':
            solver.options['timelimit'] = self.solver_params['max_runtime_s']

            # these params don't seem to work remotely...
            if not self.solver_params['run_remotely']:
                solver.options['mip_tolerances_mipgap'] = self.solver_params['optimality_gap']
                solver.options['mip_tolerances_integrality'] = self.solver_params['integer_feasibility_tolerance']
            else:
                print('AS solve() - warning, not setting params mip_tolerances_mipgap and mip_tolerances_integrality')

        elif self.solver_name == 'glpk':
            raise NotImplementedError('glpk (v4.47) runs, but takes forever and seems to have numerical instability issues right now')

        # if we're running things remotely, then we will use the NEOS server (https://neos-server.org/neos/)
        if self.solver_params['run_remotely']:
            solver_manager = po.SolverManagerFactory('neos')
            results = solver_manager.solve(self.model, opt= solver)
        else:
            # tee=True displays solver output in the terminal
            # keepfiles=True  keeps files passed to and from the solver
            results =  solver.solve(self.model, tee=True, keepfiles= False)

        if (results.solver.status == po.SolverStatus.ok) and (results.solver.termination_condition == po.TerminationCondition.optimal):
            print('this is feasible and optimal')
        elif results.solver.termination_condition == po.TerminationCondition.infeasible:
            print ('infeasible')
            raise RuntimeError('Model is infeasible with current parameters')
        else:
            # something else is wrong
            print (results.solver)

    def print_sol_all(self):
        """ basic solution printer that prints the values of all of the decision variables in the model"""

        for v in self.model.component_objects(pe.Var, active=True):
            print ("Variable",v)
            varobject = getattr(self.model, str(v))
            for index in varobject:
                print (" ",index, varobject[index].value)
