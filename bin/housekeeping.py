#!/usr/bin/env python3

import re, json, yaml, sys, datetime
from copy import deepcopy
from isodate import date_isoformat
from os import path, environ, pardir
from pymongo import MongoClient, GEOSPHERE
from progress.bar import Bar

from bycon import *

"""
The housekeeping script contains **non-destructive** maintenance scripts which
e.g. may insert derived helper values (e.g. `age_days`).
"""

################################################################################
################################################################################
################################################################################

def main():
    housekeeping()

################################################################################

def housekeeping():

    initialize_bycon_service(byc)
    parse_variant_parameters(byc)

    select_dataset_ids(byc)
    if len(byc["dataset_ids"]) != 1:
        print("No single existing dataset was provided with -d ...")
        exit()

    # collecting the actions

    todos = {
        "individual_age_days": input("Recalculate `age_days` in individuals?\n(y|N): "),
        "datasets_counts": input("Recalculate counts for all datasets?\n(y|N): "),
        "mongodb_index_creation": input("Check & create MongoDB indexes?\n(y|N): ")
    }

    ds_id = byc["dataset_ids"][0]
    data_db = MongoClient( )[ ds_id ]


    #>---------------------- info db update ----------------------------------<#

    if "y" in todos.get("datasets_counts", "n").lower():

        i_db = byc[ "config" ][ "services_db" ]
        i_coll = byc[ "config" ][ "beacon_info_coll"]

        print(f'==> Updating dataset statistics in "{ds_id}.{i_coll}"')

        b_info = __dataset_update_counts(byc)

        info_coll = MongoClient( )[ i_db ][ i_coll ]
        info_coll.delete_many( { "date": b_info["date"] } ) #, upsert=True
        info_coll.insert_one( b_info ) #, upsert=True 
        print(f'==> updated entry {b_info["date"]} in {ds_id}.{i_coll}')

    #>------------------------ individuals -----------------------------------<#

    ind_coll = data_db[ "individuals" ]

    # age_days
    if "y" in todos.get("individual_age_days", "n").lower():

        query = {"index_disease.onset.age": {"$regex": "^P\d"}}
        no = ind_coll.count_documents(query)
        bar = Bar(f"=> `age_days` for {no} individuals", max = no, suffix='%(percent)d%%'+" of "+str(no) )

        age_c = 0
        for ind in ind_coll.find(query):
            age_days = days_from_iso8601duration(ind["index_disease"]["onset"]["age"])
            if age_days is False:
                continue
            ind_coll.update_one({"_id": ind["_id"]}, {"$set": {"index_disease.onset.age_days": age_days}})
            age_c += 1
            bar.next()

        bar.finish()

        print(f'=> {age_c} individuals received an `index_disease.onset.age_days` value.')

    #>----------------------- / individuals ----------------------------------<#

    #>-------------------- MongoDB index updates -----------------------------<#

    if "y" in todos.get("mongodb_index_creation", "n").lower():
        __update_mongodb_indexes(ds_id, byc)

    #>------------------- / MongoDB index updates ----------------------------<#

################################################################################
#################################### subs ######################################
################################################################################

def __update_mongodb_indexes(ds_id, byc):

    dt_m = byc["datatable_mappings"]
    b_rt_s = byc["service_config"]["response_types"]
    mongo_client = MongoClient( )
    data_db = mongo_client[ds_id]
    for r_t, r_d in b_rt_s.items():

        collname = r_d.get("collection", False)
        if collname is False:
            print(f"¡¡¡ Collection {collname} does not exist in {ds_id} !!!")
            continue

        i_coll = data_db[ collname ]
        io_params = dt_m["entities"][ r_t ]["parameters"]

        for p_k, p_v in io_params.items():
            i_t = p_v.get("indexed", False)
            if i_t is False:
                continue
            k = p_v["db_key"]
            print('Creating index "{}" in {} from {}'.format(k, collname, ds_id))
            m = i_coll.create_index(k)
            print(m)

        if "geoprov_lat" in io_params.keys():
            k = re.sub("properties.latitude", "geometry", io_params["geoprov_lat"]["db_key"])
            m = i_coll.create_index([(k, GEOSPHERE)])
            print(m)

################################################################################

def __dataset_update_counts(byc):

    b_info = { "date": date_isoformat(datetime.datetime.now()), "datasets": { } }
    mongo_client = MongoClient( )

    # this is independend of the dataset selected for the script & will update
    # for all in any run
    dbs = mongo_client.list_database_names()
    for i_ds_id in byc["dataset_definitions"].keys():
        if not i_ds_id in dbs:
            print(f'¡¡¡ Dataset "{i_ds_id}" does not exist !!!')
            continue

        ds_db = mongo_client[ i_ds_id ]
        b_i_ds = { "counts": { }, "updated": datetime.datetime.now().isoformat() }
        c_n = ds_db.list_collection_names()
        for c in byc["config"]["queried_collections"]:
            if c not in c_n:
                continue

            no = ds_db[ c ].estimated_document_count()
            b_i_ds["counts"].update( { c: no } )
            if c == "variants":
                v_d = { }
                bar = Bar(i_ds_id+' variants', max = no, suffix='%(percent)d%%'+" of "+str(no) )
                for v in ds_db[ c ].find({ "variant_internal_id": {"$exists": True }}):
                    v_d[ v["variant_internal_id"] ] = 1
                    bar.next()
                bar.finish()
                b_i_ds["counts"].update( { "variants_distinct": len(v_d.keys()) } )

        b_info["datasets"].update({i_ds_id: b_i_ds})
    
    return b_info

################################################################################
################################################################################

if __name__ == '__main__':
    main()
