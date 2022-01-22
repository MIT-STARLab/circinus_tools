#  uniform tools for doing I/O operations on parameter and data files in CIRCINUS pipeline
# 
# @author Kit Kennedy

# TODO: need to cast integer IDs to string in this code

import copy

sat_ids_spec_opts = ['duplicate','synthesize']

def parse_sat_ids(sat_ids_spec,sat_id_prefix,force_duplicate = False):
    if type (sat_ids_spec)==str:
        tokens = sat_ids_spec.split (',')
        if (tokens[0] in sat_ids_spec_opts) or force_duplicate:
            if  tokens[1] == 'range_inclusive':
                sat_ids = ["%s%s"%(sat_id_prefix,ID) for ID in range ( int(tokens[2]), int (tokens[3])+1)]
                return sat_ids
            else:
                raise NotImplementedError
        else:
            raise  Exception ("Expected 'duplicate' as first token for sat_ids (%s)"%(sat_ids_spec))
    raise NotImplementedError

def duplicate_entry_for_sat_ids(params_entry,force_duplicate = False):
    new_entries = []

    sat_id_prefix = params_entry['sat_id_prefix']
    sat_ids = parse_sat_ids(params_entry['sat_ids'],sat_id_prefix,force_duplicate)

    for sat_id in sat_ids:
        new_entry =  copy.copy (params_entry)
        del new_entry["sat_ids"]
        new_entry["sat_id"] = sat_id
        new_entries.append (new_entry)

    return new_entries

def unpack_sat_entry_list(entry_list,output_format='list',id_tag = 'sat_id',force_duplicate = False):
    """unpacks a list of parameter entries for a set of satellites
    
    a list of parameter entries can contain collapsed entries that specify the properties for more than one satellite ID. in this case we need to convert those collapsed entries into unique entries for each satellite ID. So this:

    "sat_orbit_params": [
        {
            "sat_id": 0,
            "blah1": {
                ...
            },
            "blah2": ...
        },
        {
            "sat_ids": "synthesize,range_inclusive,1,29",
            "blah1": {
                ...
            },
            "blah2": ...
        }
    ]

    turns into:
    "sat_orbit_params": [
        {
            "sat_id": 0,
            "blah1": {
                ...
            },
            "blah2": ...
        },
        {
            "sat_id": 1,
            "blah1": {
                ...
            },
            "blah2": ...
        },
        {
            "sat_id": 2,
            "blah1": {
                ...
            },
            "blah2": ...
        },
        ...
        {
            "sat_id": 29,
            "blah1": {
                ...
            },
            "blah2": ...
        }
    ]

    :param entry_list: a list of  dictionaries containing satellite parameters,  with each dictionary having a "sat_id" or "sat_ids" field
    :type entry_list: list
    :returns:  a list of dictionaries, where each dictionary is unique for each "sat_id" (each has that field; "sat_ids" field is no longer present). also returns a list of sat IDs found
    :rtype: {list, list}
    """

    id_tag_plural = id_tag+'s'

    new_entries = []

    for entry in entry_list:
        #  if this field is present, that means the parameter entry applies for more than one satellite ID.  need to unpack for all the relevant satellite ID
        if entry.get(id_tag_plural, None):
            new_entries += duplicate_entry_for_sat_ids ( entry,force_duplicate)
        else:
            new_entries.append(entry)

    ids_found = [str (entry[id_tag]) for entry in new_entries]

    if output_format=='list':
        return new_entries, ids_found
    elif output_format=='dict':
        new_entries_by_id_tag = {str(entry[id_tag]):entry for entry in new_entries}
        return new_entries_by_id_tag, ids_found
    else:
        raise NotImplementedError

## expand_planewise_sat_defs
#
#  Takes descriptors of a multi-satellite plane, and expands it to the 
#  default individual definitions. Primarily for ease of case description, 
#  otherwise should be handled the same once expanded.
#
#  In order to use this, the entry for each plane in constellation_config.json > "sat_orbital_elems" should look like:
#  {
#     "def_type":"plane",
#     "orbit_indx"    : 0,
#     "plane_def": {
#         "a_km"          : 7378,
#         "e"             : 0,
#         "i_deg"         : 97.86,
#         "RAAN_deg"      : 0,
#         "arg_per_deg"   : 0
#     },
#
#     "first_M_deg"   : 90,               "_comment1" : "anomaly of first sat, which subsequent will follow",
#     "spacing_type"  : "progressive",    "_comment2" : "spacing: 'even', or 'progressive', or 'set'; indicate whether the sats in the plane are evenly spaced (val ignored/not needed), or should space progressively by the subsequently provided 'spacing_val', or should fix each to a anomoly in a set (array) to allow arbitrary values ",
#     "spacing_val"   : 90,               "_comment3" : "for example, this combo would result in 3 sats in this plane, with the first at 90 deg anomaly, followed by 2 more at 180 and 270."
#
#     "first_sat_id"  : 0,                "_comment4" : "the comnbo of first_sat_id, and sats_in_plane must not result in conflicting indices, and should be 'in order' without gaps, and in total match 'num_satellites' and 'sat_ids' field above. Sorry for the restrictions for now, will make a validation function.",
#     "sats_in_plane" : 3,
#
#     "propagation_method": "matlab_delkep"
#  }
#  More detail: https://github.mit.edu/star-lab/SPRINT/blob/master/inputs/cases/case_config_READMEs/constellation_config.md
#  Additionally note the requirements for matching top-level fields in 'constellation_params', as described in _comment4
#  @param sat_orbital_elems   The field of the same name from constellation_config.json
def expand_planewise_sat_defs(sat_orbital_elems):
    expanded_elements = []

    # def_type added as a field in every sat_orbital_elems: "indv" is the old type found in zhou; "plane" is the type used here
    for elems in sat_orbital_elems:
        if elems['def_type'] == 'indv':
             expanded_elements.append(elems)
        elif elems['def_type'] == 'plane':
            for i in range(elems['first_sat_id'], (elems['first_sat_id']+elems['sats_in_plane'])):
                # figure anomaly:
                if   elems['spacing_type'] == 'even':
                    spacing = 360.0/elems['sats_in_plane']
                    m_deg = (elems['first_M_deg']+(i-elems['first_sat_id'])*spacing)%360
                elif elems['spacing_type'] == 'progressive':
                    m_deg = (elems['first_M_deg']+(i-elems['first_sat_id'])*elems['spacing_val'])%360
                elif elems['spacing_type'] == 'set':
                    raise NotImplementedError("Arbitrary set of spacings not yet implemented")
                else:
                    raise NotImplementedError("Limited types supported.")

                new_entry = {
                    "sat_id"    : "S"+str(i),
                    "def_type"  : "indv",
                    "kepler_meananom": {
                        "a_km"          : elems['plane_def']['a_km'],
                        "e"             : elems['plane_def']['e'],
                        "i_deg"         : elems['plane_def']['i_deg'],
                        "RAAN_deg"      : elems['plane_def']['RAAN_deg'],
                        "arg_per_deg"   : elems['plane_def']['arg_per_deg'],
                        "M_deg"         : m_deg
                    }
                    #"propagation_method" : elems['propagation_method']
                }
                expanded_elements.append(new_entry)
        elif elems['def_type'] == 'walker':
            # don't need to do anything since current orbit prop already handles walker
            # TODO: bring plane expanding walker function from orbit prop into here
            expanded_elements = [elems]
        else:
            raise NotImplementedError("Other descriptions not defined. If using old wwalker format may need to adjust, or use new plane format accordingly.")
            
    return expanded_elements

# Similarly to the above, except for where the sat-orbit lists are used later
# Shouldn't be combined, as they're used independently.
# TODO - Consider not using this list mechanism in general (add plane identifiers to sat sim object directly? compute whether in-plane based off elements? don't use in-plane-based numbers, compute slew times directly?)
def expand_orbits_list(orbit_params, sat_prefix):
    sat_orbital_elems = orbit_params['sat_orbital_elems']
    
    sat_ids_by_orbit = copy.copy(orbit_params['sat_ids_by_orbit_name']) # start with old copy, will override as necessary

    for elems in sat_orbital_elems:
        if elems['def_type'] == 'indv' or elems['def_type'] == 'walker':
            continue
        elif elems['def_type'] == 'plane':
            o_name = "orbit"+str(elems['orbit_indx'])
            sat_ids = []
            for i in range(elems['first_sat_id'], (elems['first_sat_id']+elems['sats_in_plane'])):
                sat_ids.append(sat_prefix+str(i))
            sat_ids_by_orbit[o_name] = sat_ids
        else:
            raise NotImplementedError("Other descriptions not defined.'indv', 'plane', or 'walker' are defined")

    # TODO - validate uniqueness of ID's, that they only exist in one orbit each, etc.

    return sat_ids_by_orbit 




def sort_input_params_by_sat_IDs(params_list,sat_id_order):

    sorted_params = []
    def sort_func(params_entry):
        return sat_id_order.index (params_entry['sat_id'])

    sorted_params_list = sorted(params_list, key= lambda x: sort_func(x))

    return sorted_params_list


def make_and_validate_sat_id_order(sat_id_order_pre,sat_id_prefix,num_satellites,all_sat_ids=None):
    """ makes (if necessary) and validates the sat ID order specification list
    
    converts the sat ID order list found in the orbit prop inputs file into a list that is usable for ordering satellites In internal CIRCINUS components. It is often specified as "default" in the input file. A valid output looks like this, for example:

    "sat_id_order": [
        0,
        1,
        "2",
        "my_favorite_satellite",
        99,
        "sat5"
    ],

    In this case, the user has chosen to replace the normal satellite IDs 3 and 4  with custom IDs.  this is perfectly fine. Note that satellite IDs can be integers, strings, floats, whatever...

    If the "sat_id_order" field in sat_params from the input file is "defaut", then the output sat_id_order will either be a list of ordinals for every satellite if all_sat_ids is  not provided, or will be equal to all_sat_ids if it is provided.

    :param sat_id_order_pre:  the "sat_id_order" from the input file
    :type sat_id_order_pre: list
    :param num_satellites:  the number of satellites
    :type num_satellites: int
    :param all_sat_ids:  list of set IDs to use as default if provided, defaults to None
    :type all_sat_ids:  list, optional
    :returns:  the canonical sat_id_order to use in internal processing
    :rtype: {list}
    :raises: Exception, Exception
    """

    sat_id_order = sat_id_order_pre
    # if the default is specified, then we'll make a default list based on the order in which we find IDs
    if sat_id_order_pre == 'default':
        #  if are provided a list of all the IDs, use that as the default
        if all_sat_ids:
            sat_id_order = [sat_id for sat_id in all_sat_ids]
        #  if we are not provided a list of the all the IDs,  we assume that every ID is just an ordinal
        else:            
            sat_id_order = ["%s%s"%(sat_id_prefix,sat_indx) for sat_indx in range (num_satellites)]
    elif not type(sat_id_order_pre) == list:
        raise RuntimeError('Expected a list here')

    if len(sat_id_order) != num_satellites:
        raise Exception ("Number of satellite IDs is not equal to number of satellites specified in input file. {} in list vs {} exected".format(len(sat_id_order), num_satellites))
    if len(set(sat_id_order)) != len(sat_id_order):
        raise Exception ("Every satellite ID should be unique") 

    return sat_id_order

def validate_ids(validator,validatee):
    for ID in validatee:
        if not ID in validator:
            raise ValueError('Did not find id in validator id list; ID: %s, validator: %s'%(ID,validator))

    for ID in validator:
        if not ID in validatee:
            raise ValueError('Did not find expected id in validatee id list; ID: %s, validatee: %s'%(ID,validatee))

def make_and_validate_gs_id_order(gs_params):
    """ makes and validates the gs ID order specification list
    
    """

    # if the default is specified, then we'll make a default list based on the order in which we find IDs
    gs_id_order = [str(station['id']) for  station in gs_params['stations']]

    if len(gs_id_order) != gs_params['num_stations']:
        raise Exception ("Number of gs IDs is not equal to number of ground stations specified in input file")
    if len(set(gs_id_order)) != len(gs_id_order):
        raise Exception ("Every gs ID should be unique") 

    return gs_id_order

def make_and_validate_target_id_order(obs_params):
    """ makes and validates the gs ID order specification list
    
    """

    # if the default is specified, then we'll make a default list based on the order in which we find IDs
    targ_id_order = [str(targ['id']) for targ in obs_params['targets']]

    if len(targ_id_order) != obs_params['num_targets']:
        raise Exception ("Number of target IDs is not equal to number of targets specified in input file")
    if len(set(targ_id_order)) != len(targ_id_order):
        raise Exception ("Every target id should be unique") 

    return targ_id_order

def parse_power_consumption_params(p_params):
    edot_by_mode = {}
    batt_storage = {}

    for mode_code in p_params['power_consumption_W'].keys():
        # ignore escaped keys
        if mode_code[0:1] == "_":
            pass
        else:
            edot_by_mode[mode_code] = p_params['power_consumption_W'][mode_code]

    batt_storage['e_min'] = p_params['battery_storage_Wh']['e_min']
    batt_storage['e_max'] = p_params['battery_storage_Wh']['e_max']

    power_units = {
        'power_consumption': 'W',
        'battery_storage': 'Wh'
    }

    charge_eff = p_params['battery_storage_Wh']['charge_efficiency']
    discharge_eff = p_params['battery_storage_Wh']['discharge_efficiency']

    return edot_by_mode,batt_storage,power_units,charge_eff,discharge_eff

def dlnk_direction_enabled(tx_sat_id,gs_id,link_disables):
    """check if dlnk between sat indx and gs is enabled"""

    if gs_id in link_disables['dlnk_direc_disabled_gs_ID_by_sat_IDstr'].get(tx_sat_id,[]):
        return False
    return True

def xlnk_direction_enabled(tx_sat_id,rx_sat_id,link_disables):
    """check if dlnk between tx sat indx and rx sat indx is enabled"""

    if rx_sat_id in link_disables['xlnk_direc_disabled_xsat_ID_by_sat_IDstr'].get(tx_sat_id,[]):
        return False
    return True
