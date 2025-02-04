#!/usr/bin/env python3

import datetime, json, re, sys, yaml
from os import path, environ, pardir
from pymongo import MongoClient
from progress.bar import Bar

dir_path = path.dirname( path.abspath(__file__) )
byconaut_path = path.join( dir_path, pardir )
parent_path = path.join( byconaut_path, pardir )
sys.path.append( parent_path )

from bycon import *
from byconaut import *

"""
## `collationsCreator`

"""

################################################################################
################################################################################
################################################################################

def main():
    collations_creator()

################################################################################

def collations_creator():

    initialize_bycon_service(byc)
    select_dataset_ids(byc)
    
    if len(byc["dataset_ids"]) > 1:
        print("Please give only one dataset using -d")
        exit()

    ds_id = byc["dataset_ids"][0]

    print( "Creating collations for " + ds_id)

    set_collation_types(byc)

    for coll_type, coll_defs in byc["filter_definitions"].items():

        collationed = coll_defs.get("collationed", True)

        if collationed is False:
            continue

        pre = coll_defs["namespace_prefix"]
        pre_h_f = path.join( byconaut_path, "rsrc", "classificationTrees", coll_type, "numbered_hierarchies.tsv" )
        collection = coll_defs["scope"]
        db_key = coll_defs["db_key"]

        if  path.exists( pre_h_f ):
            print( "Creating hierarchy for " + coll_type)
            hier =  get_prefix_hierarchy( ds_id, coll_type, pre_h_f, byc)
        elif "PMID" in coll_type:
            hier =  _make_dummy_publication_hierarchy(byc)
        else:
            # create /retrieve hierarchy tree; method to be developed
            print( "Creating dummy hierarchy for " + coll_type)
            hier =  _get_dummy_hierarchy( ds_id, coll_type, coll_defs, byc )

        coll_client = MongoClient( )
        coll_coll = coll_client[ ds_id ][ byc["config"]["collations_coll"] ]

        data_client = MongoClient( )
        data_db = data_client[ ds_id ]
        data_coll = data_db[ collection ]

        onto_ids = _get_ids_for_prefix( data_coll, coll_defs )

        is_series = coll_defs.get("is_series", False)

        onto_keys = list( set( onto_ids ) & hier.keys() )

        # get the set of all parents for sample codes
        onto_keys = set()
        for o_id in onto_ids:
            if o_id in hier.keys():
                onto_keys.update( hier[ o_id ][ "parent_terms" ] )

        if is_series is True:
            child_ids = _get_child_ids_for_prefix(data_coll, coll_defs)
            onto_keys.update(child_ids)

        sel_hiers = [ ]

        no = len(hier.keys())
        matched = 0
        
        if not byc["test_mode"]:
            bar = Bar("Writing "+pre, max = no, suffix='%(percent)d%%'+" of "+str(no) )
        
        for count, code in enumerate(hier.keys(), start=1):

            if not byc["test_mode"]:
                bar.next()

            children = list( set( hier[ code ][ "child_terms" ] ) & onto_keys )

            hier[ code ].update(  { "child_terms": children } )

            if len( children ) < 1:
                if byc["test_mode"]:
                    print(code+" w/o children")
                continue

            code_no = data_coll.count_documents( { db_key: code } )

            if code_no < 1:
                code_no = 0

            if len( children ) < 2:
                child_no = code_no
            else:
                child_no =  data_coll.count_documents( { db_key: { "$in": children } } )
 
            if child_no > 0:

                # sub_id = re.sub(pre, coll_type, code)
                sub_id = code
                update_obj = hier[ code ].copy()
                update_obj.update({
                    "id": sub_id,
                    "type": coll_defs.get("name", ""),
                    "collation_type": coll_type,
                    "reference": "https://progenetix.org/services/ids/"+code,
                    "namespace_prefix": coll_defs.get("namespace_prefix", ""),
                    "scope": coll_defs.get("scope", ""),
                    "code_matches": code_no,
                    "code": code,
                    "count": child_no,
                    "dataset_id": ds_id,
                    "updated": datetime.datetime.now().isoformat(),
                    "db_key": db_key
                })

                if "reference" in coll_defs:
                    url = coll_defs["reference"].get("root", "https://progenetix.org/services/ids/")
                    r = coll_defs["reference"].get("replace", ["___nothing___", ""])
                    ref = url+re.sub(r[0], r[1], code)
                    update_obj.update({"reference": ref })

                matched += 1

                if not byc["test_mode"]:
                    sel_hiers.append( update_obj )
                else:
                    print("{}:\t{} ({} deep) samples - {} / {} {}".format(sub_id, code_no, child_no, count, no, pre))


        # UPDATE   
        if not byc["test_mode"]:
            bar.finish()
            print("==> Updating database ...")
            if matched > 0:
                coll_coll.delete_many( { "collation_type": coll_type } )
                coll_coll.insert_many( sel_hiers )

        print("===> Found {} of {} {} codes & added them to {}.{} <===".format(matched, no, coll_type, ds_id, byc["config"]["collations_coll"]))
       
################################################################################

def get_prefix_hierarchy( ds_id, coll_type, pre_h_f, byc):

    coll_defs = byc["filter_definitions"][coll_type]
    hier = hierarchy_from_file(ds_id, coll_type, pre_h_f, byc)

    no = len(hier.keys())

    # now adding terms missing from the tree ###################################

    print("Looking for missing {} codes in {}.{} ...".format(coll_type, ds_id, coll_defs["scope"]))
    data_client = MongoClient( )
    data_db = data_client[ ds_id ]
    data_coll = data_db[coll_defs["scope"]]

    db_key = coll_defs.get("db_key", "")
    
    onto_ids = _get_ids_for_prefix( data_coll, coll_defs )

    added_no = 0

    if coll_type == "NCIT":
        added_no += 1
        no += 1
        hier.update( {
            "NCIT:C000000": {
                "id": "NCIT:C000000",
                "label": "Unplaced Entities",
                "type": coll_defs.get("type", ""),
                "collation_type": coll_type,
                "namespace_prefix": coll_defs.get("namespace_prefix", ""),
                "scope": coll_defs.get("scope", ""),
                "db_key": coll_defs.get("db_key", ""),
                "hierarchy_paths": [ { "order": no, "depth": 1, "path": [ "NCIT:C3262", "NCIT:C000000" ] } ]
            }
        } )

    for o in onto_ids:
        
        if o in hier.keys():
            continue

        added_no += 1
        no += 1

        l = _get_label_for_code(data_coll, coll_defs, o)

        if coll_type == "NCIT":
            hier.update( {
                    o: { "id": o, "label": l, "hierarchy_paths":
                        [ { "order": int(no), "depth": 3, "path": [ "NCIT:C3262", "NCIT:C000000", o ] } ]
                    }
                }
            )
        else:
            o_p = { "order": int(no), "depth": 0, "path": [ o ] }
            hier.update( { o: { "id": o, "label": l, "hierarchy_paths": [ o_p ] } } )
        print("Added:\t{}\t{}".format(o, l))

    if added_no > 0:
        print("===> Added {} {} codes from {}.{} <===".format(added_no, coll_type, ds_id, coll_defs["scope"] ) )

    ############################################################################

    no = len(hier)
    bar = Bar("    parsing parents ", max = no, suffix='%(percent)d%%'+" of "+str(no) )

    for c, h in hier.items():
        bar.next()
        all_parents = { }
        for h_p in h["hierarchy_paths"]:
            for parent in h_p["path"]:
                all_parents.update( { parent: 1 } )
        hier[ c ].update( { "parent_terms": list(all_parents.keys()) } )

    bar.finish()

    ############################################################################

    bar = Bar("    parsing children ", max = no, suffix='%(percent)d%%'+" of "+str(no) )

    for c, h in hier.items():
        bar.next()
        all_children = set()
        for c_2, h_2 in hier.items():
            if c in h_2["parent_terms"]:
                all_children.add( c_2 )
        hier[ c ].update( { "child_terms": list( all_children ) } )

    if "series_pattern" in coll_defs:
        ch_re = re.compile( coll_defs["series_pattern"] )
        for c, h in hier.items():
            all_children = set( )
            for p in h["child_terms"]:
                gsms = data_coll.distinct( db_key, { db_key: p } )
                gsms = list(filter(lambda d: ch_re.match(d), gsms))
                all_children.update(gsms)
                all_children.add(p)
            h.update({ "child_terms": list(all_children) })
    
    bar.finish()

    return hier

################################################################################

def _make_dummy_publication_hierarchy(byc):

    coll_type = "PMID"
    coll_defs = byc["filter_definitions"][coll_type]
    data_db = byc["config"]["services_db"]
    data_coll = MongoClient( )[ data_db ][ "publications" ]
    query = { "id": { "$regex": coll_defs["pattern"] } }

    hier = { }

    no = data_coll.count_documents( query )
    bar = Bar("Publications...", max = no, suffix='%(percent)d%%'+" of "+str(no) )

    for order, pub in enumerate( data_coll.find( query, { "_id": 0 } ) ):
        code = pub["id"]
        bar.next()
        hier.update( { 
            code: {
                "id":  code,
                "label": pub["label"],
                "type": coll_defs.get("type", ""),
                "collation_type": coll_type,
                "namespace_prefix": coll_defs.get("namespace_prefix", ""),
                "scope": coll_defs.get("scope", ""),
                "db_key": coll_defs.get("db_key", ""),
                "hierarchy_paths": [ { "order": int(order), "depth": 0, "path": [ code ] } ],
                "parent_terms": [ code ],
                "child_terms": [ code ]
            }
        } )
 
    bar.finish()

    return hier

################################################################################

def _get_dummy_hierarchy(ds_id, coll_type, coll_defs, byc):

    data_client = MongoClient( )
    data_db = data_client[ ds_id ]
    data_coll = data_db[ coll_defs["scope"] ]
    data_pat = coll_defs["pattern"]
    db_key = coll_defs["db_key"]

    is_series = coll_defs.get("is_series", False)

    if is_series is True: 
        s_pat = coll_defs["series_pattern"]
        s_re = re.compile( s_pat )

    pre_ids = _get_ids_for_prefix( data_coll, coll_defs )

    hier = { }
    no = len(pre_ids)
    bar = Bar(coll_type, max = no, suffix='%(percent)d%%'+" of "+str(no) )

    for order, c in enumerate(sorted(pre_ids), start=1):

        bar.next()
        hier.update( { c: _get_hierarchy_item( data_coll, coll_defs, coll_type, c, order, 0, [ c ] ) } )

        if is_series is True:

            ser_ids = data_coll.distinct( db_key, { db_key: c } )
            ser_ids = list(filter(lambda d: s_re.match(d), ser_ids))
            hier[c].update( { "child_terms": list( set(ser_ids) | set(hier[c]["child_terms"]) ) } )
   
    bar.finish()

    return hier

################################################################################

def _get_hierarchy_item(data_coll, coll_defs, coll_type, code, order, depth, path):

    return {
        "id":  code,
        "label": _get_label_for_code(data_coll, coll_defs, code),
        "type": coll_defs.get("type", ""),
        "collation_type": coll_type,
        "namespace_prefix": coll_defs.get("namespace_prefix", ""),
        "scope": coll_defs.get("scope", ""),
        "db_key": coll_defs.get("db_key", ""),
        "hierarchy_paths": [ { "order": int(order), "depth": int(depth), "path": list(path) } ],
        "parent_terms": list(path),
        "child_terms": [ code ]
    }

################################################################################

def _get_ids_for_prefix(data_coll, coll_defs):

    db_key = coll_defs["db_key"]
    pre_re = re.compile( coll_defs["pattern"] )

    pre_ids = data_coll.distinct( db_key, { db_key: { "$regex": pre_re } } )
    pre_ids = list(filter(lambda d: pre_re.match(d), pre_ids))

    return pre_ids

################################################################################

def _get_child_ids_for_prefix(data_coll, coll_defs):

    child_ids = []

    if not "series_pattern" in coll_defs:
        return child_ids

    db_key = coll_defs["db_key"]

    child_re = re.compile( coll_defs["series_pattern"] )

    child_ids = data_coll.distinct( db_key, { db_key: { "$regex": child_re } } )
    child_ids = list(filter(lambda d: child_re.match(d), child_ids))

    return child_ids

################################################################################

def _get_label_for_code(data_coll, coll_defs, code):

    label_keys = ["label", "description"]

    db_key = coll_defs["db_key"]
    id_key = re.sub(".id", "", db_key)
    example = data_coll.find_one( { db_key: code } )

    if id_key in example.keys():
        if isinstance(example[ id_key ], list):
            for o_t in example[ id_key ]:
                if code in o_t["id"]:
                    for k in label_keys:
                        if k in o_t:
                            return o_t[k]
                    continue
        else:
            o_t = example[ id_key ]
            if code in o_t["id"]:
                for k in label_keys:
                        if k in o_t:
                            return o_t[k]

    return ""

################################################################################
################################################################################
################################################################################


if __name__ == '__main__':
    main()
